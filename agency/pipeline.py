"""Kunlik pipeline orkestratori (production yo'li).

    python -m agency.pipeline run [--date YYYY-MM-DD] [--from STAGE] [--idea next|A|B|C] [--force]
    python -m agency.pipeline healthcheck          # bugungi video yuborilmagan bo'lsa alert
    python -m agency.pipeline status [--date ...]  # bosqichlar holati

Bosqichlar: research → copy ⇄ compliance → tts → assets → edit → render → qa ⇄ edit → send → finalize
Har bosqich `.stages/<stage>.done` marker yozadi → qayta ishga tushirilsa joyidan davom etadi.
"""
from __future__ import annotations

import argparse
import html
import shutil
import sys
import traceback
from datetime import datetime
from pathlib import Path

from . import state, telegram
from .claude_runner import AgentError, run_agent
from .config import TZ, RunPaths, env_bool, env_int, today
from .tools import build_composition, cover, qa_check, render
from .util import log, read_json, run, write_json
from .validate import ContractError, validate

STAGES = ["research", "copy", "compliance", "tts", "assets", "edit", "render", "qa", "send", "finalize"]
END_CARD_PAD = 1.85  # 0.25s pauza + 1.6s end-card


class StageError(RuntimeError):
    pass


# ---------------------------------------------------------------- yordamchilar
def _log(paths: RunPaths, msg: str) -> None:
    line = f"- {datetime.now(TZ).strftime('%H:%M:%S')} {msg}\n"
    with paths.log.open("a", encoding="utf-8") as fh:
        fh.write(line)
    log.info(msg)


def _rs_path(paths: RunPaths) -> Path:
    return paths.p("run_state.json")


def _rs(paths: RunPaths) -> dict:
    p = _rs_path(paths)
    return read_json(p) if p.exists() else {"idea": None, "tried_ideas": [], "copy_loops": 0, "edit_loops": 0,
                                            "feedback_copy": "", "feedback_edit": "", "warnings": []}


def _save_rs(paths: RunPaths, rs: dict) -> None:
    write_json(_rs_path(paths), rs)


def _done(paths: RunPaths, stage: str) -> bool:
    return paths.done(stage).exists()


def _mark(paths: RunPaths, stage: str) -> None:
    paths.done(stage).write_text(datetime.now(TZ).isoformat(), encoding="utf-8")


def _reset_from(paths: RunPaths, stage: str) -> None:
    for s in STAGES[STAGES.index(stage):]:
        paths.done(s).unlink(missing_ok=True)


def _agent(name: str, task: str, paths: RunPaths, stage: str, timeout_min: int | None = None) -> None:
    res = run_agent(name, task, date=paths.date, stage=stage, timeout_min=timeout_min)
    _log(paths, f"{stage}: {name} tugadi ({res.turns} turn, {res.duration_s / 60:.1f} daq)")


def _ranked_ideas(brief: dict) -> list[str]:
    def score(i: dict) -> float:
        s = i["scores"]
        return (0.3 * s["pain_relevance"] + 0.25 * s["trend_strength"] + 0.2 * s["novelty_vs_last60d"]
                + 0.15 * s["product_fit"] - 0.1 * s["compliance_risk"])
    ideas = sorted(brief["ideas"], key=score, reverse=True)
    order = [i["id"] for i in ideas]
    if brief.get("chosen") in order:
        order.remove(brief["chosen"])
        order.insert(0, brief["chosen"])
    return order


def _next_idea(paths: RunPaths, rs: dict) -> str:
    for idea in _ranked_ideas(read_json(paths.brief)):
        if idea not in rs["tried_ideas"]:
            return idea
    raise StageError("Brief'dagi barcha g'oyalar sinab ko'rildi (compliance/QA o'tmadi)")


# ---------------------------------------------------------------- bosqichlar
def stage_research(paths: RunPaths) -> None:
    rd = paths.research_dir
    task = f"""Bugungi sana: {paths.date}. Ish papkasi: {paths.dir}
GoVita uchun bugungi Reels mavzusini tadqiq qil va {paths.brief} faylini yarat.
Xom ma'lumotlar uchun shu papkadan foydalan: {rd}
Tool'lar (Bash):
  python -m agency.state recent --days 60
  python -m agency.state feedback-stats
  python -m agency.tools.yt_trends --out {rd}/yt_trends.json
  python -m agency.tools.yt_transcripts --trends {rd}/yt_trends.json --out {rd}/transcripts.json
  python -m agency.tools.ad_library --out {rd}/ads_uz.json --country UZ
Tugagach tekshir: python -m agency.validate brief {paths.brief}  → OK bo'lishi shart."""
    _agent("researcher", task, paths, "research", timeout_min=env_int("RESEARCH_TIMEOUT_MIN", 45))
    validate("brief", paths.brief)


def stage_copy(paths: RunPaths, rs: dict) -> None:
    if not rs.get("idea"):
        rs["idea"] = _next_idea(paths, rs)
        rs["tried_ideas"].append(rs["idea"])
        _save_rs(paths, rs)
    feedback = rs.get("feedback_copy") or "yo'q (birinchi variant)"
    task = f"""Sana: {paths.date}. Brief: {paths.brief}. Tanlangan g'oya ID: {rs['idea']}.
Ssenariyni yoz va {paths.script} ga saqla.
Oldingi versiya bo'yicha tuzatish talablari (albatta bajar):
{feedback}
Tugagach: python -m agency.validate script {paths.script}  → OK bo'lishi shart."""
    _agent("copywriter", task, paths, "copy")
    validate("script", paths.script)


def stage_compliance(paths: RunPaths, rs: dict) -> str:
    task = f"""Sana: {paths.date}. Ssenariy: {paths.script}. Brief: {paths.brief}.
Ssenariyni compliance va fakt bo'yicha tekshir, natijani {paths.compliance} ga yoz.
Tugagach: python -m agency.validate compliance {paths.compliance}  → OK bo'lishi shart."""
    _agent("compliance", task, paths, "compliance")
    result = validate("compliance", paths.compliance)
    return result["status"]


def stage_tts(paths: RunPaths) -> float:
    run([sys.executable, "-m", "agency.tools.tts", "--run", str(paths.dir)], timeout=600)
    return float(read_json(paths.alignment)["duration"])


def stage_assets(paths: RunPaths) -> None:
    task = f"""Sana: {paths.date}. Ssenariy: {paths.script}. Ovoz timing: {paths.alignment}.
Har sahna uchun mos litsenziyali media top, yuklab ol va {paths.assets} ni yarat.
Preview rasmlar uchun papka: {paths.dir}/asset_previews
Tool: python -m agency.tools.stock_search (search | download | bank | reindex)
Tugagach: python -m agency.validate assets {paths.assets}  → OK bo'lishi shart."""
    _agent("asset-hunter", task, paths, "assets", timeout_min=env_int("ASSETS_TIMEOUT_MIN", 40))
    validate("assets", paths.assets)


def stage_edit(paths: RunPaths, rs: dict) -> None:
    feedback = rs.get("feedback_edit") or "yo'q (birinchi montaj)"
    task = f"""Sana: {paths.date}. Ish papkasi: {paths.dir}
Kirish: {paths.script}, {paths.assets}, {paths.alignment}, brand/brand.json, brand/music/
1) {paths.timeline} ni yarat (python -m agency.validate timeline {paths.timeline} → OK).
2) python -m agency.tools.build_composition --run {paths.dir}   (warnings bo'lsa — tuzat va qayta build)
3) Kerak bo'lsa {paths.composition}/index.html ni govita-video skill qoidalari bo'yicha boyit.
4) npx hyperframes lint {paths.composition}  va  npx hyperframes snapshot {paths.composition} --at 0.5,2,10,30
   — kadrlarni ko'rib chiq (Read), matn kesilmaganini tekshir.
QA'dan kelgan tuzatishlar (albatta bajar):
{feedback}"""
    _agent("editor", task, paths, "edit", timeout_min=env_int("EDIT_TIMEOUT_MIN", 45))
    validate("timeline", paths.timeline)
    if not (paths.composition / "index.html").exists():
        build_composition.build(paths)


def stage_render(paths: RunPaths) -> None:
    res = render.render(paths)
    _log(paths, f"render: {res['bytes'] / 1e6:.1f}MB, crf {res['crf']}, lint exit {res['lint_exit']}")
    cover.build_cover(paths)


def stage_qa(paths: RunPaths) -> dict:
    auto = qa_check.check(paths)
    task = f"""Sana: {paths.date}. Avtomatik tekshiruv: {paths.p('qa_auto.json')}
Kadrlar: {paths.qa_frames} (Read bilan ko'r). Ssenariy: {paths.script}. Timeline: {paths.timeline}.
Video va cover sifatini baholab {paths.qa} ni yoz.
Tugagach: python -m agency.validate qa {paths.qa}  → OK bo'lishi shart."""
    _agent("qa", task, paths, "qa")
    result = validate("qa", paths.qa)
    if not auto["passed"]:
        failed = [k for k, v in auto["checks"].items() if not v]
        result["status"] = "FAIL"
        result.setdefault("fixes", []).append(f"Avtomatik tekshiruv o'tmadi: {', '.join(failed)}")
    return result


def _report(paths: RunPaths, rs: dict) -> str:
    brief, script = read_json(paths.brief), read_json(paths.script)
    idea = next((i for i in brief["ideas"] if i["id"] == rs["idea"]), {})
    comp = read_json(paths.compliance)
    qa = read_json(paths.p("qa_auto.json"))
    usage = state.usage_summary(paths.date)
    links = "\n".join(f"• {html.escape(u)}" for u in idea.get("trend_evidence", [])[:5])
    src = "\n".join(f"• {html.escape(s['url'])}" for s in script.get("sources", [])[:5])
    warn = "\n".join(f"⚠️ {html.escape(w)}" for w in rs.get("warnings", [])[:5])
    return (
        f"📊 <b>Hisobot — {paths.date}</b>\n\n"
        f"<b>Mavzu:</b> {html.escape(idea.get('topic', script['title']))}\n"
        f"<b>Og'riq:</b> {html.escape(idea.get('uz_pain', ''))}\n"
        f"<b>Nima uchun:</b> {html.escape(brief.get('reasoning', ''))}\n\n"
        f"<b>Trend dalillari:</b>\n{links or '—'}\n\n"
        f"<b>Fakt manbalari:</b>\n{src or '—'}\n\n"
        f"<b>Compliance:</b> {comp['status']} · <b>Davomiylik:</b> {qa['metrics']['duration_s']}s · "
        f"<b>LUFS:</b> {qa['metrics']['lufs']}\n"
        f"<b>Ish vaqti:</b> {usage['total_duration_s'] / 60:.0f} daq · <b>Max-ekv.:</b> ${usage['total_cost_usd_equiv']}\n"
        + (f"\n{warn}" if warn else "")
    )


def stage_send(paths: RunPaths, rs: dict) -> None:
    script = read_json(paths.script)
    qa = read_json(paths.p("qa_auto.json"))
    telegram.send_video(paths.final_video, paths.cover,
                        f"🎬 <b>{html.escape(script['title'])}</b>\n⬇️ Cover, matn va hisobot pastda",
                        duration=int(qa["metrics"]["duration_s"]))
    telegram.send_document(paths.cover, "🖼 Cover (original sifat)")
    caption = script["caption"].strip() + "\n\n" + " ".join(script["hashtags"])
    telegram.send_message(f"📝 <b>Caption</b> (bosib nusxalang):\n<code>{html.escape(caption)}</code>")
    telegram.send_message(f"📌 <b>Pin-komment:</b>\n<code>{html.escape(script['pin_comment'])}</code>")
    telegram.send_message(_report(paths, rs), reply_markup=telegram.feedback_keyboard(paths.date))


def stage_finalize(paths: RunPaths, rs: dict) -> None:
    brief, script = read_json(paths.brief), read_json(paths.script)
    idea = next((i for i in brief["ideas"] if i["id"] == rs["idea"]), {})
    state.upsert_reel(paths.date, idea_id=rs["idea"], topic=idea.get("topic", script["title"]),
                      pillar=brief.get("pillar", ""), hook=script["scenes"][0]["voiceover"],
                      format=idea.get("format", ""), status="sent",
                      duration_s=read_json(paths.p("qa_auto.json"))["metrics"]["duration_s"])
    assets = read_json(paths.assets)
    state.mark_assets(paths.date, [a["key"] for s in assets["scenes"] for a in s["items"] if a.get("key")])
    # Bank hajmini nazorat qilish uchun og'ir oraliq fayllarni tozalash
    paths.raw_video.unlink(missing_ok=True)
    shutil.rmtree(paths.composition / "assets", ignore_errors=True)


# ---------------------------------------------------------------- orkestr
def run_pipeline(date: str, start_from: str | None = None, idea: str | None = None, force: bool = False) -> None:
    paths = RunPaths(date).ensure()
    if force:
        shutil.rmtree(paths.dir / ".stages", ignore_errors=True)
        paths.ensure()
    rs = _rs(paths)
    if start_from:
        _reset_from(paths, start_from)
    if idea:
        rs["idea"] = None if idea == "next" else idea
        if idea != "next":
            rs["tried_ideas"].append(idea)
        rs["copy_loops"] = rs["edit_loops"] = 0
        rs["feedback_copy"] = rs["feedback_edit"] = ""
        _reset_from(paths, "copy")
        _save_rs(paths, rs)

    max_copy, max_edit = env_int("MAX_COPY_LOOPS", 2), env_int("MAX_EDIT_LOOPS", 2)
    min_voice = env_int("REEL_MIN_SECONDS", 40) - END_CARD_PAD
    max_voice = env_int("REEL_MAX_SECONDS", 90) - END_CARD_PAD
    _log(paths, f"Pipeline boshlandi (from={start_from or 'resume'}, idea={rs.get('idea')})")

    if not _done(paths, "research"):
        stage_research(paths)
        _mark(paths, "research")

    # copy ⇄ compliance ⇄ tts (davomiylik) sikli
    while not (_done(paths, "copy") and _done(paths, "compliance") and _done(paths, "tts")):
        if not _done(paths, "copy"):
            stage_copy(paths, rs)
            _mark(paths, "copy")
        if not _done(paths, "compliance"):
            status = stage_compliance(paths, rs)
            _log(paths, f"compliance: {status}")
            if status == "FIX" and rs["copy_loops"] < max_copy:
                issues = read_json(paths.compliance)["issues"]
                rs["feedback_copy"] = "\n".join(f"- sahna {i.get('scene')}: {i['problem']} → {i['fix']}" for i in issues)
                rs["copy_loops"] += 1
                _save_rs(paths, rs)
                _reset_from(paths, "copy")
                continue
            if status != "PASS":
                _log(paths, f"compliance {status} — keyingi g'oyaga o'tiladi")
                rs.update(idea=None, copy_loops=0, feedback_copy="")
                _save_rs(paths, rs)
                _reset_from(paths, "copy")
                continue
            _mark(paths, "compliance")
        if not _done(paths, "tts"):
            voice = stage_tts(paths)
            _log(paths, f"tts: ovoz {voice:.1f}s")
            if not (min_voice <= voice <= max_voice):
                if rs["copy_loops"] >= max_copy:
                    raise StageError(f"Ovoz davomiyligi {voice:.1f}s — {min_voice:.0f}–{max_voice:.0f}s oralig'iga "
                                     "tushmadi (copywriter sikllari tugadi)")
                words = len(read_json(paths.alignment)["words"])
                target = int(words * 62 / voice)
                rs["feedback_copy"] = (f"- Ovoz {voice:.1f}s chiqdi; ruxsat {min_voice:.0f}–{max_voice:.0f}s, ideal ~62s. "
                                       f"Matnni ~{target} so'zga keltir (hozir {words}).")
                rs["copy_loops"] += 1
                _save_rs(paths, rs)
                _reset_from(paths, "copy")
                continue
            _mark(paths, "tts")

    if not _done(paths, "assets"):
        stage_assets(paths)
        _mark(paths, "assets")

    # edit → render → qa sikli
    while not _done(paths, "qa"):
        if not _done(paths, "edit"):
            stage_edit(paths, rs)
            _mark(paths, "edit")
        if not _done(paths, "render"):
            stage_render(paths)
            _mark(paths, "render")
        result = stage_qa(paths)
        _log(paths, f"qa: {result['status']}")
        if result["status"] == "PASS" or (result["status"] == "FAIL" and rs["edit_loops"] >= max_edit
                                          and read_json(paths.p("qa_auto.json"))["passed"]):
            if result["status"] != "PASS":
                rs["warnings"].append("QA vizual izohlari to'liq tuzatilmadi — videoni ko'rib chiqing")
            _mark(paths, "qa")
            break
        if rs["edit_loops"] >= max_edit:
            raise StageError("QA o'tmadi (montaj sikllari tugadi): " + "; ".join(result.get("fixes", []))[:800])
        rs["feedback_edit"] = "\n".join(f"- {f}" for f in result.get("fixes", []))
        rs["edit_loops"] += 1
        _save_rs(paths, rs)
        _reset_from(paths, "edit")

    if not _done(paths, "send"):
        stage_send(paths, rs)
        _mark(paths, "send")
    if not _done(paths, "finalize"):
        stage_finalize(paths, rs)
        _mark(paths, "finalize")
    _save_rs(paths, rs)
    _log(paths, "✅ Tayyor va yuborildi")


def healthcheck(date: str) -> int:
    paths = RunPaths(date)
    if paths.done("send").exists():
        print("OK: yuborilgan")
        return 0
    last = paths.log.read_text(encoding="utf-8").strip().splitlines()[-3:] if paths.log.exists() else ["log yo'q"]
    telegram.send_alert(f"{date}: video hali yuborilmagan.\nOxirgi log:\n" + "\n".join(last))
    return 1


def main() -> None:
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="cmd", required=True)
    r = sub.add_parser("run")
    r.add_argument("--date", default=None)
    r.add_argument("--from", dest="start_from", choices=STAGES)
    r.add_argument("--idea", help="next | A | B | C")
    r.add_argument("--force", action="store_true")
    h = sub.add_parser("healthcheck")
    h.add_argument("--date", default=None)
    s = sub.add_parser("status")
    s.add_argument("--date", default=None)
    args = parser.parse_args()
    date = args.date or today()

    if args.cmd == "healthcheck":
        sys.exit(healthcheck(date))
    if args.cmd == "status":
        paths = RunPaths(date)
        for st in STAGES:
            print(f"{'✅' if paths.done(st).exists() else '⬜'} {st}")
        return

    try:
        run_pipeline(date, args.start_from, args.idea, args.force)
    except (StageError, AgentError, ContractError, RuntimeError, FileNotFoundError) as exc:
        paths = RunPaths(date).ensure()
        _log(paths, f"❌ XATO: {exc}")
        log.error(traceback.format_exc())
        stage = next((s for s in STAGES if not paths.done(s).exists()), "?")
        telegram.send_alert(f"{date} — '{stage}' bosqichida xato:\n{exc}\n\n"
                            f"Davom ettirish: docker compose exec agency bin/run-daily")
        sys.exit(1)


if __name__ == "__main__":
    if env_bool("DRY_RUN"):
        log.info("DRY_RUN rejimi: Telegram xabarlari [TEST] prefiksi bilan")
    main()
