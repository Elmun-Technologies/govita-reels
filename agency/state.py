"""SQLite holat: ishlatilgan mavzular, hooklar, assetlar, feedback.

CLI (agentlar uchun):
    python -m agency.state recent --days 60     # oxirgi mavzular/hooklar/assetlar
    python -m agency.state feedback-stats       # 👍/👎 statistika (hook/rubrika bo'yicha)
"""
from __future__ import annotations

import argparse
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timedelta

from .config import STATE_DB, TZ
from .util import print_json

SCHEMA = """
CREATE TABLE IF NOT EXISTS reels (
    date TEXT PRIMARY KEY,
    idea_id TEXT,
    topic TEXT,
    pillar TEXT,
    hook TEXT,
    format TEXT,
    status TEXT,
    duration_s REAL,
    updated_at TEXT
);
CREATE TABLE IF NOT EXISTS assets_used (
    asset_key TEXT,
    date TEXT,
    PRIMARY KEY (asset_key, date)
);
CREATE TABLE IF NOT EXISTS feedback (
    date TEXT,
    value TEXT,
    created_at TEXT
);
CREATE TABLE IF NOT EXISTS usage (
    date TEXT,
    stage TEXT,
    model TEXT,
    turns INTEGER,
    input_tokens INTEGER,
    output_tokens INTEGER,
    cost_usd_equiv REAL,
    duration_s REAL,
    created_at TEXT
);
"""


@contextmanager
def db():
    STATE_DB.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(STATE_DB)
    conn.row_factory = sqlite3.Row
    conn.executescript(SCHEMA)
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def _now() -> str:
    return datetime.now(TZ).isoformat(timespec="seconds")


def upsert_reel(date: str, **fields) -> None:
    fields["updated_at"] = _now()
    with db() as conn:
        existing = conn.execute("SELECT date FROM reels WHERE date=?", (date,)).fetchone()
        if existing:
            sets = ", ".join(f"{k}=?" for k in fields)
            conn.execute(f"UPDATE reels SET {sets} WHERE date=?", (*fields.values(), date))
        else:
            cols = ", ".join(["date", *fields])
            marks = ", ".join("?" for _ in range(len(fields) + 1))
            conn.execute(f"INSERT INTO reels ({cols}) VALUES ({marks})", (date, *fields.values()))


def mark_assets(date: str, keys: list[str]) -> None:
    with db() as conn:
        conn.executemany("INSERT OR IGNORE INTO assets_used VALUES (?, ?)", [(k, date) for k in keys])


def add_feedback(date: str, value: str) -> None:
    with db() as conn:
        conn.execute("INSERT INTO feedback VALUES (?, ?, ?)", (date, value, _now()))


def add_usage(date: str, stage: str, model: str, turns: int, input_tokens: int, output_tokens: int,
              cost: float, duration_s: float) -> None:
    with db() as conn:
        conn.execute(
            "INSERT INTO usage VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (date, stage, model, turns, input_tokens, output_tokens, cost, duration_s, _now()),
        )


def recent(days: int = 60) -> dict:
    since = (datetime.now(TZ) - timedelta(days=days)).strftime("%Y-%m-%d")
    with db() as conn:
        reels = [dict(r) for r in conn.execute(
            "SELECT date, topic, pillar, hook, format, status FROM reels WHERE date>=? ORDER BY date DESC", (since,))]
        assets = [r["asset_key"] for r in conn.execute(
            "SELECT DISTINCT asset_key FROM assets_used WHERE date>=?", (since,))]
    return {"since": since, "reels": reels, "assets_used": assets}


def feedback_stats() -> dict:
    with db() as conn:
        rows = conn.execute(
            """SELECT r.date, r.topic, r.pillar, r.hook, r.format,
                      SUM(f.value='up') AS up, SUM(f.value='down') AS down
               FROM reels r LEFT JOIN feedback f ON f.date=r.date
               GROUP BY r.date ORDER BY r.date DESC LIMIT 90"""
        ).fetchall()
    return {"items": [dict(r) for r in rows]}


def usage_summary(date: str) -> dict:
    with db() as conn:
        rows = conn.execute(
            "SELECT stage, model, turns, input_tokens, output_tokens, cost_usd_equiv, duration_s "
            "FROM usage WHERE date=?", (date,)).fetchall()
    items = [dict(r) for r in rows]
    return {
        "items": items,
        "total_cost_usd_equiv": round(sum(i["cost_usd_equiv"] or 0 for i in items), 3),
        "total_duration_s": round(sum(i["duration_s"] or 0 for i in items), 1),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Agency holati")
    sub = parser.add_subparsers(dest="cmd", required=True)
    p_recent = sub.add_parser("recent")
    p_recent.add_argument("--days", type=int, default=60)
    sub.add_parser("feedback-stats")
    p_usage = sub.add_parser("usage")
    p_usage.add_argument("--date", required=True)
    args = parser.parse_args()
    if args.cmd == "recent":
        print_json(recent(args.days))
    elif args.cmd == "feedback-stats":
        print_json(feedback_stats())
    elif args.cmd == "usage":
        print_json(usage_summary(args.date))


if __name__ == "__main__":
    main()
