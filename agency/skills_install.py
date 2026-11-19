"""Tashqi skill'larni skills.lock.json bo'yicha (pinned commit) o'rnatish.

    bin/install-skills            # loyiha: .claude/skills/<name>
    bin/install-skills --global   # foydalanuvchi: ~/.claude/skills/<name>
    bin/install-skills --check    # nimalar o'rnatilgan

Har skill o'rnatilganda `.source.json` yoziladi (repo, commit) — commit o'zgarsa qayta o'rnatiladi.
"""
from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

from .config import ROOT, env


def read_json(path: Path):
    """util.read_json o'rniga: host (Mac) da requests o'rnatilmagan bo'lsa ham ishlashi uchun."""
    return json.loads(Path(path).read_text(encoding="utf-8"))

LOCK = ROOT / "skills.lock.json"


def _fetch(repo: str, commit: str, dest: Path) -> None:
    dest.mkdir(parents=True, exist_ok=True)
    git = ["git", "-C", str(dest)]
    subprocess.run(git + ["init", "-q"], check=True)
    subprocess.run(git + ["remote", "add", "origin", f"https://github.com/{repo}.git"], check=True)
    subprocess.run(git + ["fetch", "-q", "--depth", "1", "origin", commit], check=True)
    subprocess.run(git + ["checkout", "-q", "FETCH_HEAD"], check=True)


def install(target: Path, only: set[str] | None = None) -> list[str]:
    lock = read_json(LOCK)
    target.mkdir(parents=True, exist_ok=True)
    done = []
    by_repo: dict[tuple[str, str], list[dict]] = {}
    for s in lock["skills"]:
        if only and s["name"] not in only:
            continue
        meta = target / s["name"] / ".source.json"
        if meta.exists() and read_json(meta).get("commit") == s["commit"]:
            continue
        by_repo.setdefault((s["repo"], s["commit"]), []).append(s)
    for (repo, commit), skills in by_repo.items():
        with tempfile.TemporaryDirectory() as tmp:
            print(f"↓ {repo}@{commit[:7]}")
            _fetch(repo, commit, Path(tmp))
            for s in skills:
                src, dst = Path(tmp) / s["path"], target / s["name"]
                if not (src / "SKILL.md").exists():
                    print(f"  ⚠ {s['name']}: SKILL.md topilmadi ({s['path']})", file=sys.stderr)
                    continue
                if dst.exists():
                    shutil.rmtree(dst)
                shutil.copytree(src, dst, ignore=shutil.ignore_patterns(".git", "__pycache__", "tests", "evals"))
                (dst / ".source.json").write_text(json.dumps({"repo": repo, "commit": commit, "path": s["path"]}))
                print(f"  ✓ {s['name']} → {dst}")
                done.append(s["name"])
    _setup_real_sfx(target)
    return done


def _setup_real_sfx(target: Path) -> None:
    """real-sfx: SFX kutubxonasi sifatida brand/sfx/ ni ulaydi (audio fayllar bo'lsa) va indeks quradi."""
    skill = target / "real-sfx"
    if not skill.exists():
        return
    sfx_dir = Path(env("SFX_LIBRARY_DIR", str(ROOT / "brand" / "sfx")))
    has_audio = sfx_dir.exists() and any(p.suffix.lower() in {".wav", ".mp3", ".ogg", ".flac", ".aif", ".aiff"}
                                         for p in sfx_dir.rglob("*"))
    if not has_audio:
        print(f"  ℹ real-sfx: {sfx_dir} da SFX yo'q — faqat uisfx (UI tovushlar) mavjud")
        return
    subprocess.run([sys.executable, "scripts/setup.py", "init", "--library", f"govita={sfx_dir}", "--force", "--index"],
                   cwd=skill, check=False)


def check(target: Path) -> None:
    lock = read_json(LOCK)
    for s in lock["skills"]:
        meta = target / s["name"] / ".source.json"
        state = "✅" if meta.exists() and read_json(meta).get("commit") == s["commit"] else "⬜"
        print(f"{state} {s['name']:<30} {s['repo']}@{s['commit'][:7]}  ({', '.join(s['used_by'])})")
    for s in lock.get("not_installed", []):
        print(f"➖ {s['name']:<30} {s['reason']}")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--global", dest="global_", action="store_true")
    parser.add_argument("--check", action="store_true")
    parser.add_argument("--only", default="")
    args = parser.parse_args()
    target = (Path.home() / ".claude" / "skills") if args.global_ else (ROOT / ".claude" / "skills")
    if args.check:
        check(target)
        return
    only = {x.strip() for x in args.only.split(",") if x.strip()} or None
    names = install(target, only)
    print(f"Tayyor: {len(names)} ta skill o'rnatildi/yangilandi → {target}")


if __name__ == "__main__":
    main()
