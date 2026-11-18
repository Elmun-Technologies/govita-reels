"""Telegram bot tinglovchisi (alohida servis): 👍/👎 feedback, 🔁 qayta yaratish, buyruqlar.

Buyruqlar (faqat TELEGRAM_CHAT_ID dan):
  /status        — bugungi bosqichlar holati
  /run           — bugungi pipeline'ni ishga tushirish / davom ettirish
  /regen         — bugun boshqa g'oya bilan qayta (research saqlanadi)
"""
from __future__ import annotations

import subprocess
import time

from . import state, telegram
from .config import ROOT, today
from .util import http, log

RUN_DAILY = str(ROOT / "bin" / "run-daily")


def _spawn(*args: str) -> None:
    subprocess.Popen([RUN_DAILY, *args], cwd=ROOT, start_new_session=True,
                     stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


def _status(date: str) -> str:
    proc = subprocess.run(["python3", "-m", "agency.pipeline", "status", "--date", date],
                          cwd=ROOT, capture_output=True, text=True)
    return proc.stdout or proc.stderr


def handle(update: dict) -> None:
    allowed = str(telegram.chat_id())
    if cb := update.get("callback_query"):
        if str(cb["message"]["chat"]["id"]) != allowed:
            return
        data = cb.get("data", "")
        if data.startswith("fb:"):
            _, date, value = data.split(":")
            state.add_feedback(date, value)
            telegram.call("answerCallbackQuery", data={"callback_query_id": cb["id"], "text": "Rahmat, saqlandi ✅"})
        elif data.startswith("regen:"):
            date = data.split(":")[1]
            telegram.call("answerCallbackQuery", data={"callback_query_id": cb["id"], "text": "Boshqa g'oya bilan boshlandi 🔁"})
            _spawn("--date", date, "--idea", "next")
        return

    msg = update.get("message") or {}
    if str(msg.get("chat", {}).get("id")) != allowed:
        return
    text = (msg.get("text") or "").strip()
    if text.startswith("/status"):
        telegram.send_message(f"<pre>{_status(today())}</pre>")
    elif text.startswith("/run"):
        _spawn()
        telegram.send_message("▶️ Pipeline ishga tushirildi (yoki davom ettirilmoqda).")
    elif text.startswith("/regen"):
        _spawn("--idea", "next")
        telegram.send_message("🔁 Boshqa g'oya bilan qayta boshlandi.")


def main() -> None:
    offset = 0
    token = telegram._token()
    log.info("Bot listener ishga tushdi")
    while True:
        try:
            resp = http("GET", f"https://api.telegram.org/bot{token}/getUpdates",
                        params={"offset": offset, "timeout": 50}, timeout=70, retries=2)
            for upd in resp.json().get("result", []):
                offset = upd["update_id"] + 1
                try:
                    handle(upd)
                except Exception as exc:  # noqa: BLE001
                    log.error("Update xato: %s", exc)
        except Exception as exc:  # noqa: BLE001
            log.warning("Polling xato: %s", exc)
            time.sleep(10)


if __name__ == "__main__":
    main()
