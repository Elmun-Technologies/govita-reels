"""Meta Ad Library (veb-interfeys) — O'zbekiston va boshqa mamlakatlarda faol reklamalar.

Rasmiy Ad Library API faqat siyosiy/EU reklamalarni beradi, shuning uchun headless
brauzer bilan ochiq sahifa o'qiladi. Faqat metadata va screenshot olinadi.

Foydalanish:
    python -m agency.tools.ad_library --out runs/DATE/research/ads.json \
        [--country UZ] [--keywords "vitamin,витамины,omega 3"] [--max-per-keyword 15]

Bloklansa yoki login so'rasa — `partial: true` bilan qaytadi, pipeline to'xtamaydi.
"""
from __future__ import annotations

import argparse
import re
from pathlib import Path
from urllib.parse import quote

from ..config import KNOWLEDGE_DIR, env
from ..util import log, print_json, read_json, write_json

URL = ("https://www.facebook.com/ads/library/?active_status=active&ad_type=all&country={country}"
       "&q={q}&search_type=keyword_unordered&media_type=all")
STARTED = re.compile(r"(Started running on|Показ начат|Запуск)\s+([^\n]+)", re.I)


def scrape(keywords: list[str], country: str, limit: int, shots_dir: Path) -> tuple[list[dict], bool]:
    from playwright.sync_api import sync_playwright

    ads: list[dict] = []
    partial = False
    shots_dir.mkdir(parents=True, exist_ok=True)
    with sync_playwright() as pw:
        browser = pw.chromium.launch(
            headless=True,
            executable_path=env("CHROMIUM_PATH", "") or None,
            args=["--no-sandbox", "--disable-dev-shm-usage"],
        )
        page = browser.new_page(viewport={"width": 1280, "height": 2000}, locale="en-US")
        for kw in keywords:
            try:
                page.goto(URL.format(country=country, q=quote(kw)), timeout=60_000, wait_until="domcontentloaded")
                page.wait_for_timeout(5000)
                for _ in range(3):
                    page.mouse.wheel(0, 2500)
                    page.wait_for_timeout(1500)
                text = page.inner_text("body")
                if "Log in" in text[:500] and "Ad Library" not in text:
                    partial = True
                    continue
                safe = re.sub(r"\W+", "_", kw)[:40]
                shot = shots_dir / f"meta_{country}_{safe}.png"
                page.screenshot(path=str(shot), full_page=False)
                blocks = re.split(r"\n(?=Library ID|ID библиотеки)", text)
                for block in blocks[1: limit + 1]:
                    started = STARTED.search(block)
                    body = re.sub(r"\s+", " ", block)[:700]
                    ads.append({"keyword": kw, "country": country,
                                "started": started.group(2).strip() if started else None,
                                "text": body, "screenshot": str(shot)})
            except Exception as exc:  # noqa: BLE001
                log.warning("Ad Library (%s): %s", kw, exc)
                partial = True
        browser.close()
    return ads, partial


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", required=True, type=Path)
    parser.add_argument("--country", default="UZ")
    parser.add_argument("--keywords", default="")
    parser.add_argument("--max-per-keyword", type=int, default=15)
    args = parser.parse_args()

    keywords = [k.strip() for k in args.keywords.split(",") if k.strip()]
    if not keywords:
        keywords = read_json(KNOWLEDGE_DIR / "yt_queries.json").get("ad_library_keywords", [])
    ads, partial = scrape(keywords, args.country, args.max_per_keyword, args.out.parent / "ads_screens")
    write_json(args.out, {"country": args.country, "items": ads, "partial": partial})
    print_json({"ok": True, "out": str(args.out), "ads": len(ads), "partial": partial})


if __name__ == "__main__":
    main()
