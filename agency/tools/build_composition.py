"""timeline.json + alignment.json + brand.json → HyperFrames composition (runs/DATE/composition/).

Foydalanish:
    python -m agency.tools.build_composition --run runs/DATE

Timing alignment.json'dan olinadi (ovoz bilan 100% sinxron). Editor agent faqat
ijodiy qarorlarni (qaysi kadr, harakat, overlay, o'tish) timeline.json'da beradi.
Natijada ogohlantirishlar (masalan: video klip shot'dan qisqa) JSON'da qaytadi.
"""
from __future__ import annotations

import argparse
import html
import json
import re
import shutil
from pathlib import Path

from ..config import BRAND_DIR, ROOT, TEMPLATES_DIR, RunPaths
from ..util import media_duration, print_json, read_json, write_json

GSAP_LOCAL = ROOT / "node_modules" / "gsap" / "dist" / "gsap.min.js"
PUNCT_BREAK = re.compile(r"[.!?;:,—…]$")


def chunk_words(words: list[dict], max_words: int = 3, max_dur: float = 1.5) -> list[list[dict]]:
    chunks, cur = [], []
    for w in words:
        if cur and (len(cur) >= max_words or w["end"] - cur[0]["start"] > max_dur
                    or w["scene_id"] != cur[0]["scene_id"]):
            chunks.append(cur)
            cur = []
        cur.append(w)
        if PUNCT_BREAK.search(w["text"]):
            chunks.append(cur)
            cur = []
    if cur:
        chunks.append(cur)
    return chunks


def _mark(text: str) -> str:
    """*so'z* → <mark>so'z</mark> (aksent belgilash)."""
    return re.sub(r"\*(.+?)\*", r"<mark>\1</mark>", html.escape(text))


def _overlay_inner(text: str, style: str) -> str:
    if style == "stat" and "|" in text:
        big, small = text.split("|", 1)
        return f'<span class="t">{html.escape(big.strip())}<small>{html.escape(small.strip())}</small></span>'
    return f'<span class="t">{_mark(text)}</span>'


def _font_faces(brand: dict, assets: Path) -> tuple[str, str, str]:
    faces, families = [], {}
    fonts_dir = assets / "fonts"
    for role in ("display", "body"):
        spec = brand.get("fonts", {}).get(role, {})
        family = spec.get("family", "Inter")
        fallback = spec.get("fallback", "'Inter', 'DejaVu Sans', sans-serif")
        families[role] = f"'{family}', {fallback}"
        for f in spec.get("files", []):
            src = ROOT / f["path"]
            if not src.exists():
                continue
            fonts_dir.mkdir(parents=True, exist_ok=True)
            shutil.copy2(src, fonts_dir / src.name)
            fmt = {"woff2": "woff2", "woff": "woff", "ttf": "truetype", "otf": "opentype"}.get(src.suffix[1:], "truetype")
            urange = f" unicode-range: {f['unicode_range']};" if f.get("unicode_range") else ""
            faces.append(f"@font-face {{ font-family: '{family}'; src: url('assets/fonts/{src.name}') "
                         f"format('{fmt}'); font-weight: {f.get('weight', 400)}; font-style: normal;{urange} }}")
    return "\n      ".join(faces), families["display"], families["body"]


def build(paths: RunPaths) -> dict:
    alignment = read_json(paths.alignment)
    timeline = read_json(paths.timeline)
    brand = read_json(BRAND_DIR / "brand.json")
    colors = brand["colors"]
    warnings: list[str] = []

    comp = paths.composition
    if comp.exists():
        shutil.rmtree(comp)
    assets = comp / "assets"
    assets.mkdir(parents=True)

    if GSAP_LOCAL.exists():
        shutil.copy2(GSAP_LOCAL, assets / "gsap.min.js")
    else:
        warnings.append("gsap lokal topilmadi (npm ci qiling) — CDN ishlatiladi")
    shutil.copy2(paths.voice, assets / "voice.mp3")

    voice_dur = float(alignment["duration"])
    end_card = timeline.get("end_card", {})
    end_dur = float(end_card.get("duration", 1.6))
    end_start = round(voice_dur + 0.25, 3)
    total = round(end_start + end_dur, 3)

    scene_times = {s["id"]: (s["start"], s["end"]) for s in alignment["scenes"]}
    copied: dict[str, str] = {}
    elements: list[str] = []
    data = {"duration": total, "endStart": end_start, "accent": colors["accent"], "ink": colors["ink"],
            "shots": [], "overlays": [], "captions": [], "flashes": []}

    def asset_ref(src: str) -> str:
        if src in copied:
            return copied[src]
        path = (ROOT / src) if not Path(src).is_absolute() else Path(src)
        if not path.exists():
            raise FileNotFoundError(f"Asset topilmadi: {src}")
        name = f"m{len(copied):02d}{path.suffix.lower()}"
        shutil.copy2(path, assets / name)
        copied[src] = f"assets/{name}"
        return copied[src]

    shot_no = 0
    for scene in timeline["scenes"]:
        if scene["id"] not in scene_times:
            warnings.append(f"Sahna {scene['id']} alignment'da yo'q — o'tkazib yuborildi")
            continue
        s_start, s_end = scene_times[scene["id"]]
        if scene is timeline["scenes"][-1] or scene["id"] == alignment["scenes"][-1]["id"]:
            s_end = end_start  # oxirgi sahna end-card'gacha
        shots = scene["shots"]
        weights = [float(s.get("weight", 1)) for s in shots]
        t = s_start
        for shot, w in zip(shots, weights):
            dur = round((s_end - s_start) * w / sum(weights), 3)
            src = asset_ref(shot["asset"])
            kind = shot.get("kind") or ("video" if Path(src).suffix in {".mp4", ".mov", ".webm"} else "photo")
            mid = f"shot{shot_no:02d}"
            focus = {"top": "50% 20%", "bottom": "50% 80%"}.get(shot.get("focus", "center"), "50% 50%")
            common = (f'id="{mid}" class="clip media" data-start="{t:.3f}" data-duration="{dur:.3f}" '
                      f'data-track-index="0" style="object-position:{focus}"')
            if kind == "video":
                media_start = float(shot.get("media_start", 0))
                try:
                    clip_len = media_duration(comp / src)
                    if clip_len - media_start < dur:
                        warnings.append(f"{mid}: video {clip_len:.1f}s, shot {dur:.1f}s — kadr muzlab qoladi, "
                                        "boshqa klip yoki qisqaroq shot tanlang")
                except Exception:  # noqa: BLE001
                    pass
                elements.append(f'      <video {common} src="{src}" data-media-start="{media_start}" '
                                f'muted playsinline></video>')
            else:
                elements.append(f'      <img {common} src="{src}" alt="" />')
            data["shots"].append({"mediaId": mid, "start": t, "duration": dur, "motion": shot.get("motion", "zoom-in")})
            if shot.get("transition") == "flash" and shot_no > 0:
                fid = f"flash{shot_no:02d}"
                elements.append(f'      <div id="{fid}" class="clip flash" data-start="{max(t - 0.05, 0):.3f}" '
                                f'data-duration="0.2" data-track-index="8"></div>')
                data["flashes"].append({"id": fid, "start": max(t - 0.05, 0)})
            t = round(t + dur, 3)
            shot_no += 1

        ov = scene.get("overlay")
        if ov and ov.get("text") and ov.get("style", "none") != "none":
            oid = f"ov{scene['id']:02d}"
            o_start = round(s_start + float(ov.get("offset", 0)), 3)
            o_dur = round(float(ov.get("duration", s_end - o_start)), 3)
            elements.append(f'      <div id="{oid}" class="clip ov ov-{ov["style"]}" data-start="{o_start:.3f}" '
                            f'data-duration="{o_dur:.3f}" data-track-index="2">{_overlay_inner(ov["text"], ov["style"])}</div>')
            data["overlays"].append({"id": oid, "start": o_start, "duration": o_dur})

    elements.append(f'      <div id="shade" class="clip shade" data-start="0" data-duration="{end_start:.3f}" data-track-index="1"></div>')

    for ci, chunk in enumerate(chunk_words(alignment["words"])):
        cid = f"cap{ci:03d}"
        c_start = chunk[0]["start"]
        nxt = alignment["words"][alignment["words"].index(chunk[-1]) + 1:][:1]
        c_end = min(chunk[-1]["end"] + 0.25, nxt[0]["start"]) if nxt else chunk[-1]["end"] + 0.3
        c_end = min(c_end, end_start)
        spans, words_data = [], []
        for wi, w in enumerate(chunk):
            wid = f"{cid}w{wi}"
            spans.append(f'<span id="{wid}" class="w">{html.escape(w["text"])}</span>')
            words_data.append({"id": wid, "start": w["start"], "end": w["end"]})
        elements.append(f'      <div id="{cid}" class="clip cap" data-start="{c_start:.3f}" '
                        f'data-duration="{max(c_end - c_start, 0.2):.3f}" data-track-index="3">'
                        f'<span class="line">{"".join(spans)}</span></div>')
        data["captions"].append({"id": cid, "start": c_start, "words": words_data})

    elements.append(f'      <audio id="vo" src="assets/voice.mp3" data-start="0" data-duration="{voice_dur:.3f}" '
                    f'data-volume="1" data-track-index="5"></audio>')
    music = timeline.get("music") or {}
    if music.get("file"):
        msrc = asset_ref(music["file"])
        elements.append(f'      <audio id="music" src="{msrc}" data-start="0" data-duration="{total:.3f}" '
                        f'data-media-start="{float(music.get("media_start", 0))}" '
                        f'data-volume="{float(music.get("volume", 0.12))}" data-fade-in="0.5" data-fade-out="1.2" '
                        f'data-track-index="6"></audio>')

    logo = BRAND_DIR / brand.get("logo", {}).get("light", "logo/logo-light.png")
    if logo.exists() and logo.is_file():
        shutil.copy2(logo, assets / logo.name)
        mark = f'<img src="assets/{logo.name}" alt="GoVita" />'
    else:
        mark = f'<span class="wordmark">{html.escape(brand.get("name", "GoVita"))}</span>'
    url = html.escape(end_card.get("text", brand.get("url", "govita.uz")))
    sub = html.escape(end_card.get("subtext", ""))
    elements.append(f'      <div id="endcard" class="clip" data-start="{end_start:.3f}" data-duration="{end_dur:.3f}" '
                    f'data-track-index="7">{mark}<span class="url">{url}</span>'
                    + (f'<span class="sub">{sub}</span>' if sub else "") + "</div>")

    faces, display, body = _font_faces(brand, assets)
    tmpl = (TEMPLATES_DIR / "reel" / "index.html.tmpl").read_text(encoding="utf-8")
    if not GSAP_LOCAL.exists():
        tmpl = tmpl.replace('assets/gsap.min.js', 'https://cdn.jsdelivr.net/npm/gsap@3.15.0/dist/gsap.min.js')
    out = (tmpl.replace("{{FONT_FACES}}", faces)
           .replace("{{COLOR_GROUND}}", colors["ground"]).replace("{{COLOR_INK}}", colors["ink"])
           .replace("{{COLOR_ACCENT}}", colors["accent"]).replace("{{COLOR_ACCENT_INK}}", colors["accent_ink"])
           .replace("{{COLOR_BRAND}}", colors["brand"])
           .replace("{{FONT_DISPLAY}}", display).replace("{{FONT_BODY}}", body)
           .replace("{{DURATION}}", f"{total:.3f}")
           .replace("{{ELEMENTS}}", "\n".join(elements))
           .replace("{{DATA_JSON}}", json.dumps(data, ensure_ascii=False)))
    (comp / "index.html").write_text(out, encoding="utf-8")
    write_json(comp / "meta.json", {"id": f"govita-{paths.date}", "name": f"GoVita Reel {paths.date}"})
    write_json(comp / "hyperframes.json", {
        "$schema": "https://hyperframes.heygen.com/schema/hyperframes.json",
        "paths": {"blocks": "compositions", "components": "compositions/components", "assets": "assets"},
        "media": {"autoProxy": True},
    })
    return {"ok": True, "composition": str(comp), "duration": total, "voice_duration": voice_dur,
            "shots": shot_no, "captions": len(data["captions"]), "warnings": warnings}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--run", required=True, type=Path)
    args = parser.parse_args()
    print_json(build(RunPaths(args.run.name)))


if __name__ == "__main__":
    main()
