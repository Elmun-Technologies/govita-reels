"""Cover yaratish: timeline.json → cover → cover.jpg (1080×1920).

Foydalanish:
    python -m agency.tools.cover --run runs/DATE

timeline.cover: {"asset": "bank/...", "frame_time": 1.2, "headline": "Charchoq *sababi*",
                 "subline": "...", "tag": "Mif yoki fakt?"}
Asset video bo'lsa — frame_time dagi kadr olinadi. Asset yo'q bo'lsa — final.mp4 dan kadr.
"""
from __future__ import annotations

import argparse
import html
import re
import shutil
import tempfile
from pathlib import Path

from ..config import BRAND_DIR, ROOT, TEMPLATES_DIR, RunPaths, env
from ..util import print_json, read_json, run
from .build_composition import _font_faces


def _frame(src: Path, t: float, out: Path) -> Path:
    run(["ffmpeg", "-y", "-v", "error", "-ss", f"{t:.2f}", "-i", src, "-frames:v", "1",
         "-vf", "scale=1080:1920:force_original_aspect_ratio=increase,crop=1080:1920", "-q:v", "2", out])
    return out


def build_cover(paths: RunPaths) -> dict:
    timeline = read_json(paths.timeline)
    brand = read_json(BRAND_DIR / "brand.json")
    c = timeline["cover"]
    colors = brand["colors"]
    work = Path(tempfile.mkdtemp(prefix="cover_"))
    assets = work / "assets"
    assets.mkdir()

    src = c.get("asset")
    src_path = (ROOT / src) if src else paths.final_video
    if src_path.suffix.lower() in {".mp4", ".mov", ".webm"}:
        bg = _frame(src_path, float(c.get("frame_time", 1.0)), assets / "bg.jpg")
    else:
        bg = assets / f"bg{src_path.suffix.lower()}"
        shutil.copy2(src_path, bg)

    faces, display, body = _font_faces(brand, assets)
    logo = BRAND_DIR / brand.get("logo", {}).get("light", "logo/logo-light.png")
    if logo.exists() and logo.is_file():
        shutil.copy2(logo, assets / logo.name)
        mark = f'<img src="assets/{logo.name}" alt="GoVita" />'
    else:
        mark = html.escape(brand.get("name", "GoVita"))
    headline = re.sub(r"\*(.+?)\*", r"<mark>\1</mark>", html.escape(c["headline"]))
    tag = f'<div class="tag">{html.escape(c["tag"])}</div>' if c.get("tag") else ""
    out = ((TEMPLATES_DIR / "cover" / "cover.html.tmpl").read_text(encoding="utf-8")
           .replace("{{FONT_FACES}}", faces).replace("{{FONT_DISPLAY}}", display).replace("{{FONT_BODY}}", body)
           .replace("{{COLOR_GROUND}}", colors["ground"]).replace("{{COLOR_INK}}", colors["ink"])
           .replace("{{COLOR_ACCENT}}", colors["accent"]).replace("{{COLOR_ACCENT_INK}}", colors["accent_ink"])
           .replace("{{BG}}", f"assets/{bg.name}").replace("{{BRAND_MARK}}", mark).replace("{{TAG}}", tag)
           .replace("{{HEADLINE}}", headline).replace("{{SUBLINE}}", html.escape(c.get("subline", ""))))
    page_file = work / "cover.html"
    page_file.write_text(out, encoding="utf-8")
    shutil.copy2(page_file, paths.p("cover.html"))

    from playwright.sync_api import sync_playwright
    png = work / "cover.png"
    with sync_playwright() as pw:
        browser = pw.chromium.launch(headless=True, executable_path=env("CHROMIUM_PATH", "") or None,
                                     args=["--no-sandbox", "--disable-dev-shm-usage"])
        page = browser.new_page(viewport={"width": 1080, "height": 1920})
        page.goto(page_file.as_uri())
        page.wait_for_timeout(600)
        page.screenshot(path=str(png))
        browser.close()
    run(["ffmpeg", "-y", "-v", "error", "-i", png, "-q:v", "2", paths.cover])
    shutil.rmtree(work, ignore_errors=True)
    return {"ok": True, "cover": str(paths.cover)}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--run", required=True, type=Path)
    args = parser.parse_args()
    print_json(build_cover(RunPaths(args.run.name)))


if __name__ == "__main__":
    main()
