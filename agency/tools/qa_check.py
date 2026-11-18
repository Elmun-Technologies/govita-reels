"""Deterministik QA: o'lcham, fps, davomiylik, audio, LUFS, hajm + vizual tekshiruv uchun kadrlar.

Foydalanish:
    python -m agency.tools.qa_check --run runs/DATE

Natija: runs/DATE/qa_auto.json va qa_frames/*.jpg (har 3 soniyada + hook 0.5s/1.5s/2.5s + cover).
"""
from __future__ import annotations

import argparse
import re
import shutil
from pathlib import Path

from ..config import RunPaths, env_int
from ..util import ffprobe, print_json, run, write_json

MIN_S, MAX_S = env_int("REEL_MIN_SECONDS", 40), env_int("REEL_MAX_SECONDS", 90)


def loudness(path: Path) -> float | None:
    proc = run(["ffmpeg", "-hide_banner", "-nostats", "-i", path, "-af", "ebur128=framelog=quiet",
                "-f", "null", "-"], check=False, timeout=600)
    m = re.search(r"I:\s*(-?\d+(?:\.\d+)?)\s*LUFS", proc.stderr.split("Summary:")[-1])
    return float(m.group(1)) if m else None


def check(paths: RunPaths) -> dict:
    video = paths.final_video
    info = ffprobe(video)
    v = next((s for s in info["streams"] if s["codec_type"] == "video"), {})
    a = next((s for s in info["streams"] if s["codec_type"] == "audio"), None)
    duration = float(info["format"]["duration"])
    fps_num, fps_den = map(int, v.get("r_frame_rate", "0/1").split("/"))
    fps = fps_num / max(fps_den, 1)
    size = video.stat().st_size
    lufs = loudness(video) if a else None
    silent_tts = paths.alignment.exists() and '"provider": "silent"' in paths.alignment.read_text(encoding="utf-8")

    checks = {
        "resolution_1080x1920": (v.get("width"), v.get("height")) == (1080, 1920),
        "fps_30": abs(fps - 30) < 0.5,
        f"duration_{MIN_S}_{MAX_S}s": MIN_S <= duration <= MAX_S,
        "has_audio": a is not None,
        # silent TTS (test rejimi) da ovoz yo'q — LUFS tekshiruvi o'tkazib yuboriladi
        "loudness_-15_-13_lufs": silent_tts or (lufs is not None and -15.5 <= lufs <= -12.5),
        "size_le_50mb": size <= 50 * 1024 * 1024,
        "cover_exists": paths.cover.exists(),
        "h264": v.get("codec_name") == "h264",
    }

    frames = paths.qa_frames
    if frames.exists():
        shutil.rmtree(frames)
    frames.mkdir(parents=True)
    times = [0.5, 1.5, 2.5] + [float(t) for t in range(3, int(duration), 3)] + [max(duration - 0.8, 0)]
    for t in times:
        run(["ffmpeg", "-y", "-v", "error", "-ss", f"{t:.2f}", "-i", video, "-frames:v", "1",
             "-vf", "scale=540:-2", "-q:v", "4", frames / f"t{t:06.2f}.jpg"], check=False)
    if paths.cover.exists():
        run(["ffmpeg", "-y", "-v", "error", "-i", paths.cover, "-vf", "scale=540:-2", frames / "cover.jpg"],
            check=False)

    result = {
        "passed": all(checks.values()),
        "checks": checks,
        "metrics": {"duration_s": round(duration, 2), "fps": round(fps, 2), "lufs": lufs, "bytes": size,
                    "width": v.get("width"), "height": v.get("height")},
        "frames_dir": str(frames),
        "frames": sorted(p.name for p in frames.glob("*.jpg")),
    }
    write_json(paths.p("qa_auto.json"), result)
    return result


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--run", required=True, type=Path)
    args = parser.parse_args()
    print_json(check(RunPaths(args.run.name)))


if __name__ == "__main__":
    main()
