"""Markaziy konfiguratsiya: yo'llar, env, sana."""
from __future__ import annotations

import os
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT = Path(os.environ.get("AGENCY_ROOT", Path(__file__).resolve().parent.parent))
TZ = ZoneInfo(os.environ.get("TZ", "Asia/Tashkent"))

RUNS_DIR = ROOT / "runs"
BANK_DIR = ROOT / "bank"
DATA_DIR = ROOT / "data"
BRAND_DIR = ROOT / "brand"
KNOWLEDGE_DIR = ROOT / "knowledge"
SCHEMAS_DIR = ROOT / "schemas"
TEMPLATES_DIR = ROOT / "templates"
STATE_DB = DATA_DIR / "state.sqlite"


def _load_dotenv() -> None:
    """`.env` faylini yuklaydi (agar mavjud bo'lsa). Mavjud env ustun."""
    env_file = ROOT / ".env"
    if not env_file.exists():
        return
    for line in env_file.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        key, value = key.strip(), value.split(" #", 1)[0].strip().strip('"').strip("'")
        os.environ.setdefault(key, value)


_load_dotenv()


def env(name: str, default: str | None = None, required: bool = False) -> str:
    value = os.environ.get(name, default)
    if required and not value:
        raise RuntimeError(f"Env o'zgaruvchi topilmadi: {name} (.env faylini tekshiring)")
    return value or ""


def env_bool(name: str, default: bool = False) -> bool:
    return env(name, "1" if default else "0").lower() in {"1", "true", "yes", "on"}


def env_int(name: str, default: int) -> int:
    try:
        return int(env(name, str(default)))
    except ValueError:
        return default


def today() -> str:
    return datetime.now(TZ).strftime("%Y-%m-%d")


@dataclass(frozen=True)
class RunPaths:
    date: str

    @property
    def dir(self) -> Path:
        return RUNS_DIR / self.date

    def p(self, name: str) -> Path:
        return self.dir / name

    # Kontrakt fayllari
    @property
    def research_dir(self) -> Path:
        return self.dir / "research"

    @property
    def brief(self) -> Path:
        return self.p("brief.json")

    @property
    def script(self) -> Path:
        return self.p("script.json")

    @property
    def compliance(self) -> Path:
        return self.p("compliance.json")

    @property
    def assets(self) -> Path:
        return self.p("assets.json")

    @property
    def voice(self) -> Path:
        return self.p("voice.mp3")

    @property
    def alignment(self) -> Path:
        return self.p("alignment.json")

    @property
    def timeline(self) -> Path:
        return self.p("timeline.json")

    @property
    def composition(self) -> Path:
        return self.dir / "composition"

    @property
    def raw_video(self) -> Path:
        return self.p("raw.mp4")

    @property
    def final_video(self) -> Path:
        return self.p("final.mp4")

    @property
    def cover(self) -> Path:
        return self.p("cover.jpg")

    @property
    def qa(self) -> Path:
        return self.p("qa.json")

    @property
    def qa_frames(self) -> Path:
        return self.dir / "qa_frames"

    @property
    def log(self) -> Path:
        return self.p("log.md")

    def done(self, stage: str) -> Path:
        return self.dir / ".stages" / f"{stage}.done"

    def ensure(self) -> "RunPaths":
        (self.dir / ".stages").mkdir(parents=True, exist_ok=True)
        self.research_dir.mkdir(parents=True, exist_ok=True)
        return self
