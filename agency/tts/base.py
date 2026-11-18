from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from pathlib import Path


@dataclass
class TTSResult:
    audio_path: Path
    # Belgilar darajasidagi alignment: har belgi uchun (char, start_s, end_s)
    chars: list[str]
    starts: list[float]
    ends: list[float]


class TTSProvider(ABC):
    name = "base"

    @abstractmethod
    def synthesize(self, text: str, out_path: Path) -> TTSResult:
        """Matndan audio + belgi-darajasidagi timestamp yaratadi."""
