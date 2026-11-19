"""VoiceLab (voicelab.uz) TTS — o'zbekcha nativ ovoz.

VoiceLab /v1/tts timestamp qaytarmaydi, shuning uchun:
  1) POST /v1/tts            → audio
  2) POST /v1/stt (+ poll)   → so'z-darajasidagi timing (start_ms/end_ms)
  3) STT so'zlari asl matn tokenlariga moslanadi (difflib) → belgi-darajasidagi alignment
Subtitrlar asl matndan olinadi (STT xatolari ekranga chiqmaydi), timing esa haqiqiy ovozdan.

API: https://api.voicelab.uz, `Authorization: Bearer <VOICELAB_API_KEY>`, `Idempotency-Key` majburiy.
"""
from __future__ import annotations

import difflib
import re
import subprocess
import tempfile
import time
import uuid
from pathlib import Path

from ..config import env, env_int
from ..util import http, log
from .base import TTSProvider, TTSResult

BASE = "https://api.voicelab.uz"
APOS = str.maketrans({"ʻ": "'", "ʼ": "'", "’": "'", "‘": "'", "`": "'"})


def _norm(token: str) -> str:
    return re.sub(r"[^\w']+", "", token.translate(APOS).lower())


def align_words(text: str, stt_words: list[dict]) -> tuple[list[str], list[float], list[float]]:
    """Asl matn tokenlariga STT so'z vaqtlarini moslab, belgi-darajasidagi (char, start, end) qaytaradi."""
    tokens = [(m.start(), m.end(), m.group()) for m in re.finditer(r"\S+", text)]
    a = [_norm(t[2]) for t in tokens]
    b = [_norm(w["text"]) for w in stt_words]
    times: list[tuple[float, float] | None] = [None] * len(tokens)
    sm = difflib.SequenceMatcher(a=a, b=b, autojunk=False)
    for tag, i1, i2, j1, j2 in sm.get_opcodes():
        if tag == "equal":
            for k in range(i2 - i1):
                w = stt_words[j1 + k]
                times[i1 + k] = (w["start_ms"] / 1000, w["end_ms"] / 1000)
        elif tag == "replace" and j2 > j1:
            # Bir nechta token ↔ bir nechta STT so'z: oraliqni belgilar soniga qarab bo'lamiz
            start, end = stt_words[j1]["start_ms"] / 1000, stt_words[j2 - 1]["end_ms"] / 1000
            lengths = [len(tokens[i][2]) for i in range(i1, i2)]
            total, t = sum(lengths) or 1, start
            for i, ln in zip(range(i1, i2), lengths):
                dur = (end - start) * ln / total
                times[i] = (t, t + dur)
                t += dur

    # Moslanmagan tokenlar: qo'shnilar orasida interpolyatsiya
    total_end = stt_words[-1]["end_ms"] / 1000 if stt_words else len(text) / 14
    i = 0
    while i < len(times):
        if times[i] is not None:
            i += 1
            continue
        j = i
        while j < len(times) and times[j] is None:
            j += 1
        left = times[i - 1][1] if i > 0 else 0.0
        right = times[j][0] if j < len(times) else total_end
        right = max(right, left + 0.05 * (j - i))
        lengths = [len(tokens[k][2]) for k in range(i, j)]
        total, t = sum(lengths) or 1, left
        for k, ln in zip(range(i, j), lengths):
            dur = (right - left) * ln / total
            times[k] = (t, t + dur)
            t += dur
        i = j

    chars, starts, ends = list(text), [0.0] * len(text), [0.0] * len(text)
    prev_end = 0.0
    tok_iter = iter(zip(tokens, times))
    cur = next(tok_iter, None)
    for idx in range(len(text)):
        while cur and idx >= cur[0][1]:
            prev_end = cur[1][1]
            cur = next(tok_iter, None)
        if cur and cur[0][0] <= idx < cur[0][1]:
            (s, e, tok), (ts, te) = cur
            step = (te - ts) / max(len(tok), 1)
            starts[idx] = round(ts + step * (idx - s), 3)
            ends[idx] = round(ts + step * (idx - s + 1), 3)
        else:
            starts[idx] = ends[idx] = round(prev_end, 3)
    return chars, starts, ends


class VoiceLabTTS(TTSProvider):
    name = "voicelab"

    def _headers(self) -> dict:
        return {"Authorization": f"Bearer {env('VOICELAB_API_KEY', required=True)}",
                "Idempotency-Key": str(uuid.uuid4())}

    def _stt_words(self, audio: Path) -> list[dict]:
        with open(audio, "rb") as fh:
            data = http("POST", f"{BASE}/v1/stt", headers=self._headers(), timeout=300, retries=2,
                        ok_statuses=(200, 201, 202),
                        data={"language": env("VOICELAB_LANGUAGE", "uz"), "include_speakers": "false"},
                        files={"audio": (audio.name, fh, "audio/mpeg")}).json()
        deadline = time.monotonic() + env_int("VOICELAB_STT_TIMEOUT_S", 300)
        while data.get("status") in {"queued", "processing"}:
            if time.monotonic() > deadline:
                raise RuntimeError("VoiceLab STT timeout")
            time.sleep(3)
            data = http("GET", f"{BASE}/v1/stt/transcriptions/{data['id']}",
                        headers={"Authorization": f"Bearer {env('VOICELAB_API_KEY')}"}).json()
        if data.get("status") == "failed":
            raise RuntimeError(f"VoiceLab STT xato: {data.get('error')}")
        words = [w for seg in data.get("segments", []) for w in (seg.get("words") or [])]
        if not words:  # so'z darajasi bo'lmasa — segmentlardan
            words = [{"text": seg["text"], "start_ms": seg["start_ms"], "end_ms": seg["end_ms"]}
                     for seg in data.get("segments", [])]
        return words

    def synthesize(self, text: str, out_path: Path) -> TTSResult:
        body = {"text": text, "language": env("VOICELAB_LANGUAGE", "uz"),
                "voice_id": env("VOICELAB_VOICE_ID", required=True),
                "speed": float(env("VOICELAB_SPEED", "1.0"))}
        resp = http("POST", f"{BASE}/v1/tts", headers={**self._headers(), "Content-Type": "application/json"},
                    json=body, timeout=300, retries=2)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory() as tmp:
            raw = Path(tmp) / "voicelab_raw"
            raw.write_bytes(resp.content)
            subprocess.run(["ffmpeg", "-y", "-v", "error", "-i", str(raw), "-ar", "44100", "-ac", "1",
                            "-b:a", "160k", str(out_path)], check=True)
        words = self._stt_words(out_path)
        log.info("VoiceLab: %d STT so'z", len(words))
        chars, starts, ends = align_words(text, words)
        return TTSResult(out_path, chars, starts, ends)
