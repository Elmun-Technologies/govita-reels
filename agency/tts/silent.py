"""Test/DRY_RUN uchun: jim audio + taxminiy timing (ElevenLabs kreditini sarflamaydi).

Tezlik o'zbekcha og'zaki nutqqa yaqin: ~14 belgi/soniya (~2.3 so'z/soniya).
"""
from __future__ import annotations

import subprocess
from pathlib import Path

from .base import TTSProvider, TTSResult

CHARS_PER_SEC = 14.0


class SilentTTS(TTSProvider):
    name = "silent"

    def synthesize(self, text: str, out_path: Path) -> TTSResult:
        starts, ends = [], []
        t = 0.0
        step = 1 / CHARS_PER_SEC
        for ch in text:
            dur = step * (4 if ch in ".!?" else 2 if ch in ",;:—" else 1)
            starts.append(round(t, 3))
            t += dur
            ends.append(round(t, 3))
        out_path.parent.mkdir(parents=True, exist_ok=True)
        subprocess.run(
            ["ffmpeg", "-y", "-v", "error", "-f", "lavfi", "-i", "anullsrc=r=44100:cl=mono",
             "-t", f"{t + 0.2:.2f}", "-q:a", "9", str(out_path)],
            check=True,
        )
        return TTSResult(out_path, list(text), starts, ends)
