"""script.json → voice.mp3 + alignment.json (so'z va sahna darajasidagi timing).

Foydalanish:
    python -m agency.tools.tts --run runs/DATE

alignment.json:
  {"duration": 61.2, "provider": "elevenlabs",
   "scenes": [{"id": 1, "start": 0.0, "end": 3.1}],
   "words":  [{"text": "Agar", "start": 0.05, "end": 0.31, "scene_id": 1}]}
"""
from __future__ import annotations

import argparse
import re
from pathlib import Path

from ..config import KNOWLEDGE_DIR, RunPaths
from ..tts import get_provider
from ..util import media_duration, print_json, read_json, write_json


def apply_pronunciation(text: str) -> str:
    """knowledge/pronunciation.json lug'ati (masalan "D3" → "D-uch") — TTS to'g'ri o'qishi uchun."""
    path = KNOWLEDGE_DIR / "pronunciation.json"
    if not path.exists():
        return text
    for src, dst in read_json(path).get("replacements", {}).items():
        text = re.sub(rf"(?<!\w){re.escape(src)}(?!\w)", dst, text)
    return re.sub(r"\s+", " ", text).strip()


def build_text(scenes: list[dict]) -> tuple[str, list[tuple[int, int, int]]]:
    """Sahnalarni bitta matnga birlashtiradi; har sahna uchun (id, char_start, char_end)."""
    parts, spans, pos = [], [], 0
    for scene in scenes:
        chunk = apply_pronunciation(scene["voiceover"])
        if parts:
            parts.append(" ")
            pos += 1
        spans.append((scene["id"], pos, pos + len(chunk)))
        parts.append(chunk)
        pos += len(chunk)
    return "".join(parts), spans


def words_from_chars(chars: list[str], starts: list[float], ends: list[float],
                     spans: list[tuple[int, int, int]]) -> list[dict]:
    def scene_of(idx: int) -> int:
        for sid, a, b in spans:
            if a <= idx < b:
                return sid
        return spans[-1][0]

    words, buf, w_start, w_idx = [], "", None, 0
    for i, ch in enumerate(chars):
        if ch.isspace():
            if buf:
                words.append({"text": buf, "start": round(w_start, 3), "end": round(ends[i - 1], 3),
                              "scene_id": scene_of(w_idx)})
            buf, w_start = "", None
            continue
        if not buf:
            w_start, w_idx = starts[i], i
        buf += ch
    if buf:
        words.append({"text": buf, "start": round(w_start, 3), "end": round(ends[-1], 3),
                      "scene_id": scene_of(w_idx)})
    return words


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--run", required=True, type=Path)
    parser.add_argument("--provider")
    args = parser.parse_args()
    paths = RunPaths(args.run.name)

    script = read_json(paths.script)
    text, spans = build_text(script["scenes"])
    provider = get_provider(args.provider)
    result = provider.synthesize(text, paths.voice)
    words = words_from_chars(result.chars, result.starts, result.ends, spans)

    scenes = []
    for sid, _, _ in spans:
        sw = [w for w in words if w["scene_id"] == sid]
        if sw:
            scenes.append({"id": sid, "start": sw[0]["start"], "end": sw[-1]["end"]})
    # Sahnalar orasidagi bo'shliqlarni yopamiz: har sahna keyingisi boshlanguncha davom etadi
    for a, b in zip(scenes, scenes[1:]):
        a["end"] = b["start"]
    duration = media_duration(paths.voice)
    if scenes:
        scenes[0]["start"] = 0.0
        scenes[-1]["end"] = round(duration, 3)

    write_json(paths.alignment, {"duration": round(duration, 3), "provider": provider.name,
                                 "spoken_text": text, "scenes": scenes, "words": words})
    print_json({"ok": True, "duration": round(duration, 2), "words": len(words), "scenes": len(scenes)})


if __name__ == "__main__":
    main()
