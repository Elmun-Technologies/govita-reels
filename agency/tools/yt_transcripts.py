"""yt-dlp orqali top videolar subtitrlarini olish (FAQAT tahlil uchun — video yuklanmaydi).

Foydalanish:
    python -m agency.tools.yt_transcripts --trends runs/DATE/research/yt_trends.json \
        --out runs/DATE/research/transcripts.json [--top 10]

Natija: har video uchun to'liq matn + birinchi ~3 soniyadagi hook.
YouTube bot-tekshiruvi bo'lsa `partial: true` qaytadi (pipeline yiqilmaydi).
"""
from __future__ import annotations

import argparse
import re
import subprocess
import tempfile
from pathlib import Path

from ..util import log, print_json, read_json, write_json

TS = re.compile(r"(\d+):(\d+):(\d+)[.,](\d+)\s+-->")


def _parse_vtt(text: str) -> tuple[str, str]:
    lines, hook, current_start = [], [], 0.0
    for raw in text.splitlines():
        m = TS.match(raw)
        if m:
            h, mi, s, ms = map(int, m.groups())
            current_start = h * 3600 + mi * 60 + s + ms / 1000
            continue
        line = re.sub(r"<[^>]+>", "", raw).strip()
        if not line or line.startswith(("WEBVTT", "Kind:", "Language:", "NOTE")) or line.isdigit():
            continue
        if lines and lines[-1] == line:
            continue
        lines.append(line)
        if current_start <= 3.5:
            hook.append(line)
    return " ".join(lines), " ".join(dict.fromkeys(hook))


def fetch(video_id: str, workdir: Path) -> dict:
    cmd = [
        "yt-dlp", "--skip-download", "--write-auto-subs", "--write-subs",
        "--sub-langs", "uz.*,ru.*,en.*", "--sub-format", "vtt",
        "-o", str(workdir / "%(id)s.%(ext)s"), f"https://www.youtube.com/watch?v={video_id}",
    ]
    try:
        subprocess.run(cmd, capture_output=True, text=True, timeout=90, check=False)
    except subprocess.TimeoutExpired:
        return {"video_id": video_id, "error": "timeout"}
    subs = sorted(workdir.glob(f"{video_id}*.vtt"))
    if not subs:
        return {"video_id": video_id, "error": "subtitr topilmadi"}
    full, hook = _parse_vtt(subs[0].read_text(encoding="utf-8", errors="ignore"))
    return {"video_id": video_id, "lang_file": subs[0].name, "hook_first_3s": hook[:300],
            "transcript": full[:4000]}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--trends", required=True, type=Path)
    parser.add_argument("--out", required=True, type=Path)
    parser.add_argument("--top", type=int, default=10)
    args = parser.parse_args()

    videos = read_json(args.trends).get("top", [])[: args.top]
    results = []
    with tempfile.TemporaryDirectory() as tmp:
        for v in videos:
            item = fetch(v["video_id"], Path(tmp))
            item.update({"title": v.get("title"), "url": v.get("url"), "views": v.get("views")})
            results.append(item)
            if "error" in item:
                log.warning("Transkript: %s — %s", v["video_id"], item["error"])
    ok = sum(1 for r in results if "error" not in r)
    write_json(args.out, {"items": results, "partial": ok < len(results)})
    print_json({"ok": True, "out": str(args.out), "with_transcript": ok, "total": len(results)})


if __name__ == "__main__":
    main()
