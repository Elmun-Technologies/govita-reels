"""HyperFrames render → loudnorm (−14 LUFS) → Instagram/Telegram uchun final.mp4.

Foydalanish:
    python -m agency.tools.render --run runs/DATE [--draft]
"""
from __future__ import annotations

import argparse
import os
from pathlib import Path

from ..config import ROOT, RunPaths, env, env_int
from ..util import print_json, run

MAX_BYTES = 45 * 1024 * 1024  # Telegram bot limiti 50MB, zaxira bilan


def hyperframes_bin() -> list[str]:
    local = ROOT / "node_modules" / ".bin" / "hyperframes"
    return [str(local)] if local.exists() else ["npx", "--yes", f"hyperframes@{env('HYPERFRAMES_VERSION', '0.9.65')}"]


def render(paths: RunPaths, draft: bool = False) -> dict:
    comp = paths.composition
    env_vars = {**os.environ, "HYPERFRAMES_SKIP_SKILLS": "1"}
    lint = run([*hyperframes_bin(), "lint", str(comp)], cwd=comp, env=env_vars, check=False, timeout=300)
    workers = env("RENDER_WORKERS", "auto")
    run([*hyperframes_bin(), "render", str(comp), "-o", str(paths.raw_video), "--fps", "30",
         "--quality", "draft" if draft else env("RENDER_QUALITY", "delivery"), "--workers", workers, "--quiet", "--no-wait"],
        cwd=comp, env=env_vars, timeout=env_int("RENDER_TIMEOUT_MIN", 45) * 60)

    crf = env_int("FINAL_CRF", 20)
    for _ in range(3):
        run(["ffmpeg", "-y", "-v", "error", "-i", paths.raw_video,
             "-c:v", "libx264", "-preset", "veryfast", "-crf", str(crf), "-pix_fmt", "yuv420p",
             "-profile:v", "high", "-r", "30",
             "-af", "loudnorm=I=-14:TP=-1.5:LRA=11", "-c:a", "aac", "-b:a", "192k", "-ar", "48000",
             "-movflags", "+faststart", paths.final_video], timeout=1800)
        if paths.final_video.stat().st_size <= MAX_BYTES:
            break
        crf += 3
    return {"ok": True, "final": str(paths.final_video), "bytes": paths.final_video.stat().st_size, "crf": crf,
            "lint_exit": lint.returncode, "lint_tail": (lint.stdout + lint.stderr)[-1200:]}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--run", required=True, type=Path)
    parser.add_argument("--draft", action="store_true")
    args = parser.parse_args()
    print_json(render(RunPaths(args.run.name), args.draft))


if __name__ == "__main__":
    main()
