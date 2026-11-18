"""TTS provider adapterlari. Yangi provider: base.TTSProvider'dan meros olib, REGISTRY ga qo'shing."""
from __future__ import annotations

from ..config import env
from .base import TTSProvider, TTSResult


def get_provider(name: str | None = None) -> TTSProvider:
    name = (name or env("TTS_PROVIDER", "elevenlabs")).lower()
    if name == "elevenlabs":
        from .elevenlabs import ElevenLabsTTS
        return ElevenLabsTTS()
    if name == "silent":
        from .silent import SilentTTS
        return SilentTTS()
    raise ValueError(f"Noma'lum TTS_PROVIDER: {name}")


__all__ = ["TTSProvider", "TTSResult", "get_provider"]
