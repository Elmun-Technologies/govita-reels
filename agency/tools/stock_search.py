"""Stok media: Pexels + Pixabay qidiruv, yuklab olish va lokal rasm banki.

Subbuyruqlar:
  search    --query "tired woman office" --kind video|photo [--n 8] [--previews DIR]
            → nomzodlar JSON (preview rasmlari DIR ga yuklanadi — agent ko'rib tanlaydi)
  download  --source pexels|pixabay --id ID --kind video|photo [--tags "a,b"]
            → bank/ ga saqlaydi, bank/index.json va bank/license.csv yangilanadi
  bank      --query "charchoq ofis" [--kind video|photo] [--n 10]
            → lokal bankdan teg/nom bo'yicha qidiruv (qayta ishlatish — tez va bepul)
  reindex   → bank/ dagi qo'lda qo'shilgan fayllarni (masalan Adobe Stock) indeksga qo'shadi

Litsenziyalar: Pexels License, Pixabay Content License — tijoriy foydalanish bepul,
atribut shart emas. Adobe Stock fayllarni bank/adobe/ ga qo'lda qo'ying va `reindex` qiling.
"""
from __future__ import annotations

import argparse
import csv
import re
from datetime import datetime
from pathlib import Path

from ..config import BANK_DIR, TZ, env
from ..util import http, log, print_json, read_json, write_json

INDEX = BANK_DIR / "index.json"
LICENSE_CSV = BANK_DIR / "license.csv"
MEDIA_EXT = {".mp4": "video", ".mov": "video", ".webm": "video", ".jpg": "photo", ".jpeg": "photo",
             ".png": "photo", ".webp": "photo"}
LICENSES = {"pexels": "Pexels License (https://www.pexels.com/license/)",
            "pixabay": "Pixabay Content License (https://pixabay.com/service/license-summary/)"}


# ---------- Pexels ----------
def _pexels(path: str, **params) -> dict:
    return http("GET", f"https://api.pexels.com{path}", params=params,
                headers={"Authorization": env("PEXELS_API_KEY", required=True)}).json()


def _pexels_search(query: str, kind: str, n: int) -> list[dict]:
    if kind == "video":
        data = _pexels("/videos/search", query=query, orientation="portrait", per_page=n, size="medium")
        out = []
        for v in data.get("videos", []):
            out.append({"source": "pexels", "id": str(v["id"]), "kind": "video", "width": v["width"],
                        "height": v["height"], "duration": v["duration"], "author": v["user"]["name"],
                        "page_url": v["url"], "preview_url": v["image"]})
        return out
    data = _pexels("/v1/search", query=query, orientation="portrait", per_page=n)
    return [{"source": "pexels", "id": str(p["id"]), "kind": "photo", "width": p["width"], "height": p["height"],
             "author": p["photographer"], "page_url": p["url"], "preview_url": p["src"]["medium"],
             "alt": p.get("alt", "")} for p in data.get("photos", [])]


def _pexels_file(asset_id: str, kind: str) -> tuple[str, dict]:
    if kind == "video":
        v = _pexels(f"/videos/videos/{asset_id}")
        files = [f for f in v["video_files"] if f.get("file_type") == "video/mp4" and f.get("width")]
        portrait = [f for f in files if f["height"] >= f["width"]] or files
        good = [f for f in portrait if min(f["width"], f["height"]) >= 1080] or portrait
        best = min(good, key=lambda f: f["width"] * f["height"])
        return best["link"], {"author": v["user"]["name"], "page_url": v["url"], "width": best["width"],
                              "height": best["height"], "duration": v["duration"]}
    p = _pexels(f"/v1/photos/{asset_id}")
    return p["src"]["original"], {"author": p["photographer"], "page_url": p["url"], "width": p["width"],
                                  "height": p["height"], "alt": p.get("alt", "")}


# ---------- Pixabay ----------
def _pixabay(path: str, **params) -> dict:
    params["key"] = env("PIXABAY_API_KEY", required=True)
    return http("GET", f"https://pixabay.com/api{path}", params=params).json()


def _pixabay_search(query: str, kind: str, n: int) -> list[dict]:
    n = max(3, min(n, 200))
    if kind == "video":
        data = _pixabay("/videos/", q=query, per_page=n, safesearch="true")
        out = []
        for v in data.get("hits", []):
            large = v["videos"].get("large") or v["videos"].get("medium")
            out.append({"source": "pixabay", "id": str(v["id"]), "kind": "video", "width": large["width"],
                        "height": large["height"], "duration": v["duration"], "author": v["user"],
                        "page_url": v["pageURL"], "preview_url": large.get("thumbnail") or "",
                        "tags": v.get("tags", "")})
        return out
    data = _pixabay("/", q=query, per_page=n, image_type="photo", orientation="vertical", safesearch="true")
    return [{"source": "pixabay", "id": str(p["id"]), "kind": "photo", "width": p["imageWidth"],
             "height": p["imageHeight"], "author": p["user"], "page_url": p["pageURL"],
             "preview_url": p["webformatURL"], "tags": p.get("tags", "")} for p in data.get("hits", [])]


def _pixabay_file(asset_id: str, kind: str) -> tuple[str, dict]:
    if kind == "video":
        v = _pixabay("/videos/", id=asset_id)["hits"][0]
        best = v["videos"].get("large") or v["videos"]["medium"]
        if not best.get("url"):
            best = v["videos"]["medium"]
        return best["url"], {"author": v["user"], "page_url": v["pageURL"], "width": best["width"],
                             "height": best["height"], "duration": v["duration"], "tags": v.get("tags", "")}
    p = _pixabay("/", id=asset_id)["hits"][0]
    url = p.get("largeImageURL") or p["webformatURL"]
    return url, {"author": p["user"], "page_url": p["pageURL"], "width": p["imageWidth"],
                 "height": p["imageHeight"], "tags": p.get("tags", "")}


# ---------- Bank ----------
def _index() -> list[dict]:
    return read_json(INDEX)["items"] if INDEX.exists() else []


def _save_index(items: list[dict]) -> None:
    write_json(INDEX, {"items": items})


def _append_license(row: dict) -> None:
    new = not LICENSE_CSV.exists()
    LICENSE_CSV.parent.mkdir(parents=True, exist_ok=True)
    with LICENSE_CSV.open("a", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=["key", "path", "source", "author", "page_url", "license", "added"])
        if new:
            writer.writeheader()
        writer.writerow({k: row.get(k, "") for k in writer.fieldnames})


def cmd_search(args) -> None:
    results: list[dict] = []
    errors = []
    for fn in (_pexels_search, _pixabay_search):
        try:
            results += fn(args.query, args.kind, args.n)
        except Exception as exc:  # noqa: BLE001
            errors.append(f"{fn.__name__}: {exc}")
            log.warning("Qidiruv xato: %s", exc)
    used = set()
    if args.exclude_used:
        from ..state import recent
        used = set(recent(60)["assets_used"])
    results = [r for r in results if f"{r['source']}:{r['id']}" not in used]
    if args.previews:
        prev_dir = Path(args.previews)
        prev_dir.mkdir(parents=True, exist_ok=True)
        for r in results:
            if not r.get("preview_url"):
                continue
            target = prev_dir / f"{r['source']}_{r['id']}.jpg"
            try:
                if not target.exists():
                    target.write_bytes(http("GET", r["preview_url"], timeout=30).content)
                r["preview_file"] = str(target)
            except Exception as exc:  # noqa: BLE001
                log.warning("Preview yuklanmadi %s: %s", r["id"], exc)
    for r in results:
        r["key"] = f"{r['source']}:{r['id']}"
    print_json({"query": args.query, "kind": args.kind, "count": len(results), "results": results,
                "errors": errors})


def cmd_download(args) -> None:
    key = f"{args.source}:{args.id}"
    items = _index()
    existing = next((i for i in items if i["key"] == key), None)
    if existing and Path(existing["path"]).exists():
        print_json({"ok": True, "cached": True, **existing})
        return
    url, meta = (_pexels_file if args.source == "pexels" else _pixabay_file)(args.id, args.kind)
    ext = ".mp4" if args.kind == "video" else (Path(url.split("?")[0]).suffix.lower() or ".jpg")
    target = BANK_DIR / args.source / f"{args.id}{ext}"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(http("GET", url, timeout=300).content)
    tags = sorted({t.strip().lower() for t in (args.tags + "," + meta.get("tags", "")).split(",") if t.strip()})
    entry = {"key": key, "path": str(target), "kind": args.kind, "source": args.source, "id": args.id,
             "author": meta.get("author"), "page_url": meta.get("page_url"), "license": LICENSES[args.source],
             "width": meta.get("width"), "height": meta.get("height"), "duration": meta.get("duration"),
             "tags": tags, "added": datetime.now(TZ).isoformat(timespec="seconds")}
    items = [i for i in items if i["key"] != key] + [entry]
    _save_index(items)
    _append_license(entry)
    print_json({"ok": True, "cached": False, **entry})


def _tokens(text: str) -> set[str]:
    return {t for t in re.split(r"[^\w']+", text.lower()) if len(t) > 2}


def cmd_bank(args) -> None:
    q = _tokens(args.query)
    scored = []
    for item in _index():
        if args.kind and item["kind"] != args.kind:
            continue
        if not Path(item["path"]).exists():  # bulutda media saqlanmaydi — qayta `download` qilinadi
            continue
        hay = _tokens(" ".join(item.get("tags", [])) + " " + Path(item["path"]).stem.replace("-", " "))
        score = len(q & hay)
        if score:
            scored.append((score, item))
    scored.sort(key=lambda x: -x[0])
    print_json({"query": args.query, "results": [i for _, i in scored[: args.n]]})


def cmd_reindex(_args) -> None:
    items = _index()
    known = {i["path"] for i in items}
    added = 0
    for path in BANK_DIR.rglob("*"):
        kind = MEDIA_EXT.get(path.suffix.lower())
        if not kind or str(path) in known or path.name.startswith("."):
            continue
        source = path.relative_to(BANK_DIR).parts[0] if len(path.relative_to(BANK_DIR).parts) > 1 else "manual"
        tags = sorted(_tokens(path.stem.replace("_", " ").replace("-", " ")))
        entry = {"key": f"{source}:{path.stem}", "path": str(path), "kind": kind, "source": source,
                 "id": path.stem, "author": "", "page_url": "",
                 "license": "Adobe Stock (litsenziyalangan)" if source == "adobe" else "qo'lda qo'shilgan",
                 "tags": tags, "added": datetime.now(TZ).isoformat(timespec="seconds")}
        items.append(entry)
        _append_license(entry)
        added += 1
    _save_index(items)
    print_json({"ok": True, "added": added, "total": len(items)})


def main() -> None:
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("search")
    s.add_argument("--query", required=True)
    s.add_argument("--kind", choices=["video", "photo"], default="video")
    s.add_argument("--n", type=int, default=8)
    s.add_argument("--previews")
    s.add_argument("--exclude-used", action="store_true", default=True)
    d = sub.add_parser("download")
    d.add_argument("--source", choices=["pexels", "pixabay"], required=True)
    d.add_argument("--id", required=True)
    d.add_argument("--kind", choices=["video", "photo"], required=True)
    d.add_argument("--tags", default="")
    b = sub.add_parser("bank")
    b.add_argument("--query", required=True)
    b.add_argument("--kind", choices=["video", "photo"])
    b.add_argument("--n", type=int, default=10)
    sub.add_parser("reindex")
    args = parser.parse_args()
    {"search": cmd_search, "download": cmd_download, "bank": cmd_bank, "reindex": cmd_reindex}[args.cmd](args)


if __name__ == "__main__":
    main()
