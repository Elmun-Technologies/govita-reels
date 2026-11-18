"""ElevenLabs TTS — /with-timestamps endpoint (audio + belgi-darajasidagi alignment)."""
from __future__ import annotations

import base64
from pathlib import Path

from ..config import env
from ..util import http
from .base import TTSProvider, TTSResult

URL = "https://api.elevenlabs.io/v1/text-to-speech/{voice_id}/with-timestamps"


class ElevenLabsTTS(TTSProvider):
    name = "elevenlabs"

    def synthesize(self, text: str, out_path: Path) -> TTSResult:
        voice_id = env("ELEVENLABS_VOICE_ID", required=True)
        body: dict = {
            "text": text,
            "model_id": env("ELEVENLABS_MODEL", "eleven_multilingual_v2"),
            "voice_settings": {
                "stability": float(env("ELEVENLABS_STABILITY", "0.45")),
                "similarity_boost": float(env("ELEVENLABS_SIMILARITY", "0.8")),
                "style": float(env("ELEVENLABS_STYLE", "0.25")),
                "use_speaker_boost": True,
                "speed": float(env("ELEVENLABS_SPEED", "1.05")),
            },
        }
        lang = env("ELEVENLABS_LANGUAGE_CODE", "")
        if lang:
            body["language_code"] = lang
        resp = http(
            "POST", URL.format(voice_id=voice_id),
            params={"output_format": "mp3_44100_128"},
            headers={"xi-api-key": env("ELEVENLABS_API_KEY", required=True), "Content-Type": "application/json"},
            json=body, timeout=180, retries=2,
        )
        data = resp.json()
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_bytes(base64.b64decode(data["audio_base64"]))
        al = data.get("alignment") or data.get("normalized_alignment")
        return TTSResult(out_path, al["characters"], al["character_start_times_seconds"],
                         al["character_end_times_seconds"])
