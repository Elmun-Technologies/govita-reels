"""Claude Code CLI'ni headless rejimda subagent sifatida ishga tushirish.

Max obuna: konteynerda CLAUDE_CODE_OAUTH_TOKEN env (host'da `claude setup-token`).
Har bosqich alohida `claude -p --agent <name>` jarayoni — kontekst kichik, timeout va
resume oson, bitta bosqich yiqilsa boshqalari ta'sirlanmaydi.
"""
from __future__ import annotations

import json
import subprocess
import time
from dataclasses import dataclass

from . import state
from .config import ROOT, env, env_int
from .util import log


@dataclass
class AgentResult:
    ok: bool
    text: str
    turns: int
    cost_usd_equiv: float
    duration_s: float


class AgentError(RuntimeError):
    pass


def run_agent(agent: str, task: str, *, date: str, stage: str, timeout_min: int | None = None) -> AgentResult:
    """`.claude/agents/<agent>.md` agentini `task` bilan ishga tushiradi."""
    claude_bin = env("CLAUDE_BIN", "claude")
    timeout = 60 * (timeout_min or env_int("AGENT_TIMEOUT_MIN", 40))
    cmd = [
        claude_bin, "-p", task,
        "--agent", agent,
        "--output-format", "json",
        "--no-session-persistence",
    ]
    # Ruxsatlar: default — .claude/settings.json allowlist (+ fayl tahrirlari avtomatik).
    # "bypass" faqat izolyatsiyalangan non-root konteynerda ishlatilsin.
    if env("AGENT_PERMISSION_MODE", "allowlist") == "bypass":
        cmd.append("--dangerously-skip-permissions")
    else:
        cmd += ["--permission-mode", "acceptEdits"]
    max_turns = env("AGENT_MAX_TURNS", "")
    if max_turns:
        cmd += ["--max-turns", max_turns]

    log.info("Agent ishga tushdi: %s (bosqich: %s)", agent, stage)
    started = time.monotonic()
    try:
        proc = subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True, timeout=timeout)
    except subprocess.TimeoutExpired as exc:
        raise AgentError(f"{agent}: {timeout // 60} daqiqada tugamadi (timeout)") from exc
    duration = time.monotonic() - started

    payload: dict = {}
    try:
        payload = json.loads(proc.stdout.strip().splitlines()[-1]) if proc.stdout.strip() else {}
    except (json.JSONDecodeError, IndexError):
        payload = {}

    usage = payload.get("usage") or {}
    model = ",".join((payload.get("modelUsage") or {}).keys()) or agent
    state.add_usage(
        date, stage, model,
        int(payload.get("num_turns") or 0),
        int(usage.get("input_tokens") or 0) + int(usage.get("cache_read_input_tokens") or 0),
        int(usage.get("output_tokens") or 0),
        float(payload.get("total_cost_usd") or 0.0),
        duration,
    )

    if proc.returncode != 0 or payload.get("is_error"):
        detail = payload.get("result") or proc.stderr[-1500:] or proc.stdout[-1500:]
        if "limit" in str(detail).lower() and "usage" in str(detail).lower():
            raise AgentError(f"{agent}: Max obuna limiti tugagan — {detail[:300]}")
        raise AgentError(f"{agent}: xato (exit {proc.returncode}) — {str(detail)[:800]}")

    return AgentResult(
        ok=True,
        text=str(payload.get("result", "")),
        turns=int(payload.get("num_turns") or 0),
        cost_usd_equiv=float(payload.get("total_cost_usd") or 0.0),
        duration_s=duration,
    )
