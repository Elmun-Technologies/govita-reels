"""Holatni git `state` branch'ida saqlash (bulutdagi har kungi run yangi sessiyada boshlanadi).

    python -m agency.state_sync pull    # state branch → data/, runs/ (JSON/log), bank/index, knowledge
    python -m agency.state_sync push    # aksincha, commit + push (o'zgarish bo'lsa)

Saqlanadi: data/state.sqlite, runs/*/ dagi kichik fayllar (JSON, log, cover.jpg), bank/index.json, bank/license.csv,
agentlar o'zgartiradigan knowledge fayllari. Video/media fayllar saqlanmaydi (Telegram'da va stokda bor).

Knowledge: agent o'zgartirgan versiya faqat main'dagi asl fayl o'shandan beri o'zgarmagan bo'lsa tiklanadi —
siz main'da qo'lda tahrir qilsangiz, sizning versiyangiz ustun.
"""
from __future__ import annotations

import hashlib
import json
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

from .config import BANK_DIR, DATA_DIR, KNOWLEDGE_DIR, ROOT, RUNS_DIR, env

BRANCH = "state"
RUN_FILES = {".json", ".md", ".log", ".csv"}
RUN_KEEP = {"cover.jpg"}
AGENT_KNOWLEDGE = ["competitors.md", "hook-library.md", "uz-audience-pains.md"]
MAX_RUN_FILE = 2 * 1024 * 1024


def _git(*args: str, cwd: Path = ROOT, check: bool = True) -> subprocess.CompletedProcess:
    return subprocess.run(["git", *args], cwd=cwd, capture_output=True, text=True, check=check)


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest() if path.exists() else ""


def _remote_has_branch() -> bool:
    return _git("ls-remote", "--heads", "origin", BRANCH, check=False).stdout.strip() != ""


def pull() -> None:
    if not _remote_has_branch():
        print("state branch hali yo'q — toza boshlanadi")
        return
    _git("fetch", "-q", "--depth", "1", "origin", f"{BRANCH}:refs/remotes/origin/{BRANCH}")
    with tempfile.TemporaryDirectory() as tmp:
        _git("--work-tree", tmp, "checkout", f"origin/{BRANCH}", "--", ".")
        _git("reset", "-q")  # index'ni main holatiga qaytarish (work-tree checkout index'ni o'zgartiradi)
        src = Path(tmp)
        if (src / "data" / "state.sqlite").exists():
            DATA_DIR.mkdir(parents=True, exist_ok=True)
            shutil.copy2(src / "data" / "state.sqlite", DATA_DIR / "state.sqlite")
        if (src / "runs").exists():
            shutil.copytree(src / "runs", RUNS_DIR, dirs_exist_ok=True)
        for name in ("index.json", "license.csv"):
            if (src / "bank" / name).exists():
                BANK_DIR.mkdir(parents=True, exist_ok=True)
                shutil.copy2(src / "bank" / name, BANK_DIR / name)
        base_file = src / "knowledge" / ".base.json"
        base = json.loads(base_file.read_text()) if base_file.exists() else {}
        for name in AGENT_KNOWLEDGE:
            saved = src / "knowledge" / name
            if saved.exists() and _sha(KNOWLEDGE_DIR / name) == base.get(name):
                shutil.copy2(saved, KNOWLEDGE_DIR / name)
    print("state tiklandi")


def push() -> None:
    wt = Path(tempfile.mkdtemp(prefix="state-wt-"))
    try:
        if _remote_has_branch():
            _git("fetch", "-q", "--depth", "1", "origin", f"{BRANCH}:refs/remotes/origin/{BRANCH}")
            _git("worktree", "add", "-q", "-B", BRANCH, str(wt), f"origin/{BRANCH}")
        else:
            _git("worktree", "add", "-q", "--detach", str(wt))
            _git("checkout", "-q", "--orphan", BRANCH, cwd=wt)
            _git("rm", "-rfq", ".", cwd=wt, check=False)
        # Fayllarni nusxalash
        if (DATA_DIR / "state.sqlite").exists():
            (wt / "data").mkdir(exist_ok=True)
            shutil.copy2(DATA_DIR / "state.sqlite", wt / "data" / "state.sqlite")
        for run_dir in sorted(RUNS_DIR.glob("20??-??-??")):
            for f in run_dir.rglob("*"):
                rel = f.relative_to(RUNS_DIR)
                if (not f.is_file() or "composition" in rel.parts or "sfx_work" in rel.parts
                        or f.stat().st_size > MAX_RUN_FILE):
                    continue
                if f.suffix in RUN_FILES or f.name in RUN_KEEP or rel.parts[1:2] == (".stages",):
                    dst = wt / "runs" / rel
                    dst.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copy2(f, dst)
        for name in ("index.json", "license.csv"):
            if (BANK_DIR / name).exists():
                (wt / "bank").mkdir(exist_ok=True)
                shutil.copy2(BANK_DIR / name, wt / "bank" / name)
        # Knowledge: agent versiyasi + main'dagi asl faylning hash'i
        main_base = {}
        (wt / "knowledge").mkdir(exist_ok=True)
        for name in AGENT_KNOWLEDGE:
            cur = KNOWLEDGE_DIR / name
            if not cur.exists():
                continue
            orig = _git("show", f"HEAD:knowledge/{name}", check=False)
            orig_sha = hashlib.sha256(orig.stdout.encode()).hexdigest() if orig.returncode == 0 else ""
            main_base[name] = orig_sha
            shutil.copy2(cur, wt / "knowledge" / name)
        (wt / "knowledge" / ".base.json").write_text(json.dumps(main_base, indent=2))
        (wt / "README.md").write_text("# GoVita Reels — holat (avtomatik)\n\nBu branch'ni qo'lda tahrirlamang. "
                                      "`python -m agency.state_sync` boshqaradi.\n")

        _git("add", "-A", cwd=wt)
        if _git("diff", "--cached", "--quiet", cwd=wt, check=False).returncode == 0:
            print("state: o'zgarish yo'q")
            return
        _git("-c", "user.name=GoVita Reels Bot", "-c", f"user.email={env('STATE_GIT_EMAIL', 'noreply@govita.uz')}",
             "commit", "-qm", f"state: {sorted(p.name for p in RUNS_DIR.glob('20??-??-??'))[-1:] or 'init'}", cwd=wt)
        push_res = _git("-c", "push.negotiate=true", "push", "-q", "origin", f"HEAD:{BRANCH}", cwd=wt, check=False)
        if push_res.returncode != 0:
            raise RuntimeError(f"state push xato: {push_res.stderr[-500:]}")
        print("state saqlandi")
    finally:
        _git("worktree", "remove", "--force", str(wt), check=False)
        shutil.rmtree(wt, ignore_errors=True)


def main() -> None:
    cmd = sys.argv[1] if len(sys.argv) > 1 else ""
    if cmd == "pull":
        pull()
    elif cmd == "push":
        push()
    else:
        print("Foydalanish: python -m agency.state_sync pull|push", file=sys.stderr)
        sys.exit(2)


if __name__ == "__main__":
    main()
