"""Telegram Bot API — yuborish (video, cover, matn, hisobot, alert)."""
from __future__ import annotations

import html
import json
import subprocess
import tempfile
from pathlib import Path

from .config import env, env_bool
from .util import http, log

API = "https://api.telegram.org/bot{token}/{method}"
MAX_TEXT = 4000


def _token() -> str:
    return env("TELEGRAM_BOT_TOKEN", required=True)


def chat_id() -> str:
    return env("TELEGRAM_CHAT_ID", required=True)


def call(method: str, *, data: dict | None = None, files: dict | None = None, timeout: float = 120) -> dict:
    resp = http("POST", API.format(token=_token(), method=method), data=data, files=files,
                timeout=timeout, retries=3)
    payload = resp.json()
    if not payload.get("ok"):
        raise RuntimeError(f"Telegram {method}: {payload.get('description')}")
    return payload["result"]


def _prefix(text: str) -> str:
    return f"[TEST] {text}" if env_bool("DRY_RUN") else text


def send_message(text: str, *, reply_markup: dict | None = None, parse_mode: str = "HTML") -> dict:
    chunks = [text[i:i + MAX_TEXT] for i in range(0, len(text), MAX_TEXT)] or [""]
    result: dict = {}
    for i, chunk in enumerate(chunks):
        data = {"chat_id": chat_id(), "text": chunk, "parse_mode": parse_mode,
                "disable_web_page_preview": "true"}
        if reply_markup and i == len(chunks) - 1:
            data["reply_markup"] = json.dumps(reply_markup)
        result = call("sendMessage", data=data)
    return result


def _thumbnail(cover: Path) -> Path:
    """Telegram thumbnail talabi: JPEG, ≤320px, ≤200KB."""
    out = Path(tempfile.mkdtemp()) / "thumb.jpg"
    subprocess.run(["ffmpeg", "-y", "-v", "error", "-i", str(cover), "-vf", "scale=-2:320", "-q:v", "5", str(out)],
                   check=True)
    return out


def send_video(video: Path, cover: Path, caption: str, width: int = 1080, height: int = 1920,
               duration: int | None = None) -> dict:
    thumb = _thumbnail(cover)
    data = {"chat_id": chat_id(), "caption": _prefix(caption)[:1000], "parse_mode": "HTML",
            "supports_streaming": "true", "width": width, "height": height}
    if duration:
        data["duration"] = duration
    with open(video, "rb") as fv, open(thumb, "rb") as ft:
        return call("sendVideo", data=data, files={"video": fv, "thumbnail": ft}, timeout=600)


def send_document(path: Path, caption: str = "") -> dict:
    with open(path, "rb") as fh:
        return call("sendDocument", data={"chat_id": chat_id(), "caption": caption[:1000], "parse_mode": "HTML"},
                    files={"document": fh}, timeout=300)


def send_alert(text: str) -> None:
    """Xatolik xabari. O'zi xato bersa — faqat log (pipeline'ni yiqitmaydi)."""
    try:
        send_message(_prefix(f"⚠️ <b>GoVita Reels</b>\n{html.escape(text)[:3500]}"))
    except Exception as exc:  # noqa: BLE001
        log.error("Telegram alert yuborilmadi: %s", exc)


def feedback_keyboard(date: str) -> dict:
    return {"inline_keyboard": [[
        {"text": "👍 Yaxshi", "callback_data": f"fb:{date}:up"},
        {"text": "👎 Yomon", "callback_data": f"fb:{date}:down"},
        {"text": "🔁 Boshqa g'oya", "callback_data": f"regen:{date}"},
    ]]}
