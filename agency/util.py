"""Umumiy yordamchilar: JSON I/O, HTTP retry, log, subprocess."""
from __future__ import annotations

import json
import logging
import subprocess
import sys
import time
from pathlib import Path
from typing import Any, Iterable

import requests

log = logging.getLogger("agency")
if not log.handlers:
    handler = logging.StreamHandler(sys.stderr)
    handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(name)s: %(message)s"))
    log.addHandler(handler)
    log.setLevel(logging.INFO)

SECRET_PARAMS = {"key", "api_key", "token", "access_token"}


def read_json(path: Path) -> Any:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def write_json(path: Path, data: Any) -> Path:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    tmp.replace(path)
    return path


def print_json(data: Any) -> None:
    """Agentlar uchun stdout'ga JSON chiqarish (CLI tool'lar shu orqali javob beradi)."""
    sys.stdout.write(json.dumps(data, ensure_ascii=False, indent=2) + "\n")


def _redact(url: str) -> str:
    from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

    parts = urlsplit(url)
    query = [(k, "***" if k.lower() in SECRET_PARAMS else v) for k, v in parse_qsl(parts.query)]
    return urlunsplit(parts._replace(query=urlencode(query)))


def http(
    method: str,
    url: str,
    *,
    retries: int = 3,
    backoff: float = 2.0,
    timeout: float = 60,
    ok_statuses: Iterable[int] = (200,),
    **kwargs: Any,
) -> requests.Response:
    """Exponential backoff bilan HTTP so'rov. 429/5xx qayta urinadi, 4xx darhol xato."""
    last_exc: Exception | None = None
    for attempt in range(1, retries + 1):
        try:
            resp = requests.request(method, url, timeout=timeout, **kwargs)
            if resp.status_code in ok_statuses:
                return resp
            if resp.status_code in (429, 500, 502, 503, 504) and attempt < retries:
                wait = backoff ** attempt
                retry_after = resp.headers.get("Retry-After")
                if retry_after and retry_after.isdigit():
                    wait = max(wait, int(retry_after))
                log.warning("HTTP %s %s -> %s, %ss dan keyin qayta", method, _redact(url), resp.status_code, wait)
                time.sleep(wait)
                continue
            raise RuntimeError(f"HTTP {resp.status_code} {_redact(url)}: {resp.text[:300]}")
        except (requests.ConnectionError, requests.Timeout) as exc:
            last_exc = exc
            if attempt < retries:
                time.sleep(backoff ** attempt)
                continue
    raise RuntimeError(f"HTTP so'rov muvaffaqiyatsiz: {_redact(url)}: {last_exc}")


def run(cmd: list[str], *, timeout: int = 1800, cwd: Path | None = None, env: dict | None = None,
        check: bool = True) -> subprocess.CompletedProcess:
    log.info("$ %s", " ".join(str(c) for c in cmd)[:400])
    proc = subprocess.run(
        [str(c) for c in cmd], cwd=cwd, env=env, timeout=timeout,
        capture_output=True, text=True,
    )
    if check and proc.returncode != 0:
        raise RuntimeError(
            f"Buyruq xato bilan tugadi ({proc.returncode}): {cmd[0]}\n"
            f"STDOUT: {proc.stdout[-1500:]}\nSTDERR: {proc.stderr[-1500:]}"
        )
    return proc


def ffprobe(path: Path) -> dict:
    proc = run(["ffprobe", "-v", "error", "-print_format", "json", "-show_format", "-show_streams", path])
    return json.loads(proc.stdout)


def media_duration(path: Path) -> float:
    info = ffprobe(path)
    return float(info["format"].get("duration", 0.0))
