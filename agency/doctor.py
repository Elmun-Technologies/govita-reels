"""O'rnatish diagnostikasi: `bin/doctor [--claude] [--telegram]`.

--claude    Claude Max auth'ni haqiqiy so'rov bilan tekshiradi (ozgina limit sarflaydi)
--telegram  Telegram'ga test xabar yuboradi
"""
from __future__ import annotations

import argparse
import json
import shutil
import subprocess

from .config import ROOT, env
from .util import http

BASE_REQUIRED = ["CLAUDE_CODE_OAUTH_TOKEN", "YOUTUBE_API_KEY", "PEXELS_API_KEY", "PIXABAY_API_KEY",
                 "TELEGRAM_BOT_TOKEN", "TELEGRAM_CHAT_ID"]
TTS_KEYS = {"elevenlabs": ["ELEVENLABS_API_KEY", "ELEVENLABS_VOICE_ID"],
            "voicelab": ["VOICELAB_API_KEY", "VOICELAB_VOICE_ID"], "silent": []}


def _ok(name: str, ok: bool, detail: str = "") -> bool:
    print(f"{'✅' if ok else '❌'} {name}{' — ' + detail if detail else ''}")
    return ok


def _try(name: str, fn) -> bool:
    try:
        return _ok(name, True, fn() or "")
    except Exception as exc:  # noqa: BLE001
        return _ok(name, False, str(exc)[:200])


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--claude", action="store_true")
    parser.add_argument("--telegram", action="store_true")
    args = parser.parse_args()
    results = []

    print("— Env kalitlari")
    provider = env("TTS_PROVIDER", "elevenlabs").lower()
    print(f"  TTS_PROVIDER={provider}")
    for key in BASE_REQUIRED + TTS_KEYS.get(provider, []):
        results.append(_ok(key, bool(env(key)), "" if env(key) else ".env da yo'q"))

    print("— Tizim")
    for binary in ("ffmpeg", "ffprobe", "yt-dlp", "claude", "node"):
        results.append(_ok(binary, shutil.which(binary) is not None))
    chromium = env("CHROMIUM_PATH", "/usr/bin/chromium")
    results.append(_ok("chromium", shutil.which(chromium) is not None or (ROOT / chromium).exists(), chromium))
    results.append(_ok("hyperframes (node_modules)", (ROOT / "node_modules" / ".bin" / "hyperframes").exists(),
                       "npm ci kerak" if not (ROOT / "node_modules").exists() else ""))
    skill = (ROOT / ".claude/skills/govita-video/SKILL.md").read_text(encoding="utf-8")
    _ok("govita-video skill", "PLACEHOLDER" not in skill, "placeholder — haqiqiy skill'ni qo'ying" if "PLACEHOLDER" in skill else "")
    music = list((ROOT / "brand/music").glob("*.mp3"))
    _ok("brand/music", bool(music), f"{len(music)} trek" if music else "musiqa yo'q (ixtiyoriy)")

    print("— Skill'lar va ovoz vositalari")
    lock = json.loads((ROOT / "skills.lock.json").read_text(encoding="utf-8"))
    for sk in lock["skills"]:
        meta = ROOT / ".claude" / "skills" / sk["name"] / ".source.json"
        ok = meta.exists() and json.loads(meta.read_text()).get("commit") == sk["commit"]
        results.append(_ok(f"skill {sk['name']}", ok, "" if ok else "bin/install-skills"))
    _ok("earshot", shutil.which("earshot") is not None, "" if shutil.which("earshot") else "o'rnatilmagan (ixtiyoriy)")
    from .pipeline import sfx_enabled
    _ok("real-sfx kutubxona (brand/sfx)", sfx_enabled(), "" if sfx_enabled() else "bo'sh — sound bosqichi o'tkaziladi")

    print("— API'lar")
    if env("YOUTUBE_API_KEY"):
        results.append(_try("YouTube Data API", lambda: http(
            "GET", "https://www.googleapis.com/youtube/v3/i18nRegions",
            params={"part": "snippet", "key": env("YOUTUBE_API_KEY")}).json() and "ok"))
    if env("PEXELS_API_KEY"):
        results.append(_try("Pexels", lambda: http("GET", "https://api.pexels.com/v1/search",
                                                   params={"query": "vitamin", "per_page": 1},
                                                   headers={"Authorization": env("PEXELS_API_KEY")}) and "ok"))
    if env("PIXABAY_API_KEY"):
        results.append(_try("Pixabay", lambda: http("GET", "https://pixabay.com/api/",
                                                    params={"key": env("PIXABAY_API_KEY"), "q": "vitamin",
                                                            "per_page": 3}) and "ok"))
    if provider == "elevenlabs" and env("ELEVENLABS_API_KEY") and env("ELEVENLABS_VOICE_ID"):
        def _el():
            v = http("GET", f"https://api.elevenlabs.io/v1/voices/{env('ELEVENLABS_VOICE_ID')}",
                     headers={"xi-api-key": env("ELEVENLABS_API_KEY")}).json()
            return f"ovoz: {v.get('name')}"
        results.append(_try("ElevenLabs", _el))
    if provider == "voicelab" and env("VOICELAB_API_KEY"):
        results.append(_try("VoiceLab", lambda: f"{len(http('GET', 'https://api.voicelab.uz/v1/voices', headers={'Authorization': 'Bearer ' + env('VOICELAB_API_KEY')}).json().get('data', []))} ta ovoz"))
    if env("TELEGRAM_BOT_TOKEN"):
        def _tg():
            me = http("GET", f"https://api.telegram.org/bot{env('TELEGRAM_BOT_TOKEN')}/getMe").json()["result"]
            if args.telegram:
                from . import telegram
                telegram.send_message("✅ GoVita Reels: doctor test xabari")
            return f"@{me['username']}"
        results.append(_try("Telegram bot", _tg))

    if args.claude:
        print("— Claude Code (Max)")
        def _claude():
            proc = subprocess.run(["claude", "-p", "Faqat OK deb javob ber.", "--output-format", "json",
                                   "--max-turns", "1"], capture_output=True, text=True, timeout=180, cwd=ROOT)
            data = json.loads(proc.stdout.strip().splitlines()[-1])
            if data.get("is_error"):
                raise RuntimeError(data.get("result"))
            return f"javob: {data.get('result', '')[:30]}"
        results.append(_try("claude -p", _claude))

    print(f"\nNatija: {sum(results)}/{len(results)} o'tdi")


if __name__ == "__main__":
    main()
