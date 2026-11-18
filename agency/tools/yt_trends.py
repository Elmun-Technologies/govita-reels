"""YouTube Data API v3 — vitamin/farma nishidagi eng ko'p ko'rilayotgan qisqa videolar.

Foydalanish:
    python -m agency.tools.yt_trends --out runs/DATE/research/yt_trends.json [--days 14] [--max-queries 24]

Kvota: search.list = 100 unit, videos.list/channels.list = 1 unit. Bepul kunlik limit 10 000.
Default sozlama ~2 500 unit sarflaydi. So'rovlar: knowledge/yt_queries.json
"""
from __future__ import annotations

import argparse
from datetime import datetime, timedelta, timezone
from pathlib import Path

from ..config import KNOWLEDGE_DIR, env
from ..util import http, log, print_json, read_json, write_json

API = "https://www.googleapis.com/youtube/v3"


def _get(endpoint: str, **params) -> dict:
    params["key"] = env("YOUTUBE_API_KEY", required=True)
    return http("GET", f"{API}/{endpoint}", params=params, timeout=30).json()


def _iso_age_days(published: str) -> float:
    ts = datetime.fromisoformat(published.replace("Z", "+00:00"))
    return max((datetime.now(timezone.utc) - ts).total_seconds() / 86400, 0.25)


def search(queries: list[dict], days: int) -> dict[str, dict]:
    after = (datetime.now(timezone.utc) - timedelta(days=days)).strftime("%Y-%m-%dT%H:%M:%SZ")
    found: dict[str, dict] = {}
    for q in queries:
        params = {
            "part": "snippet", "q": q["q"], "type": "video", "maxResults": 25,
            "order": q.get("order", "viewCount"), "publishedAfter": after,
            "videoDuration": q.get("duration", "short"),
        }
        if q.get("region"):
            params["regionCode"] = q["region"]
        if q.get("lang"):
            params["relevanceLanguage"] = q["lang"]
        try:
            items = _get("search", **params).get("items", [])
        except RuntimeError as exc:
            log.warning("YouTube search xato (%s): %s", q["q"], exc)
            if "quota" in str(exc).lower():
                break
            continue
        for it in items:
            vid = it["id"]["videoId"]
            found.setdefault(vid, {"video_id": vid, "queries": [], "segment": q.get("segment", "global")})
            found[vid]["queries"].append(q["q"])
    return found


def enrich(found: dict[str, dict]) -> list[dict]:
    ids = list(found)
    channels: dict[str, dict] = {}
    for i in range(0, len(ids), 50):
        data = _get("videos", part="snippet,statistics,contentDetails", id=",".join(ids[i:i + 50]))
        for v in data.get("items", []):
            st, sn = v.get("statistics", {}), v["snippet"]
            views = int(st.get("viewCount", 0))
            age = _iso_age_days(sn["publishedAt"])
            found[v["id"]].update({
                "title": sn["title"],
                "channel_id": sn["channelId"],
                "channel": sn["channelTitle"],
                "published_at": sn["publishedAt"],
                "lang": sn.get("defaultAudioLanguage") or sn.get("defaultLanguage"),
                "duration": v["contentDetails"]["duration"],
                "views": views,
                "likes": int(st.get("likeCount", 0)),
                "comments": int(st.get("commentCount", 0)),
                "age_days": round(age, 1),
                "views_per_day": round(views / age),
                "like_rate": round(int(st.get("likeCount", 0)) / views, 4) if views else 0,
                "comment_rate": round(int(st.get("commentCount", 0)) / views, 5) if views else 0,
                "url": f"https://www.youtube.com/shorts/{v['id']}",
                "tags": sn.get("tags", [])[:10],
                "description": sn.get("description", "")[:300],
            })
            channels[sn["channelId"]] = {}
    ch_ids = list(channels)
    for i in range(0, len(ch_ids), 50):
        data = _get("channels", part="statistics", id=",".join(ch_ids[i:i + 50]))
        for c in data.get("items", []):
            st = c.get("statistics", {})
            vids = max(int(st.get("videoCount", 1)), 1)
            channels[c["id"]] = {
                "subscribers": int(st.get("subscriberCount", 0)),
                "avg_views": int(st.get("viewCount", 0)) // vids,
            }
    videos = []
    for v in found.values():
        if "views" not in v:
            continue
        ch = channels.get(v["channel_id"], {})
        v["channel_subscribers"] = ch.get("subscribers", 0)
        v["outlier_score"] = round(v["views"] / max(ch.get("avg_views", 1), 1), 2)
        videos.append(v)
    videos.sort(key=lambda x: (x["views_per_day"] * min(x["outlier_score"], 20)), reverse=True)
    return videos


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", required=True, type=Path)
    parser.add_argument("--days", type=int, default=14)
    parser.add_argument("--max-queries", type=int, default=24)
    parser.add_argument("--top", type=int, default=40)
    args = parser.parse_args()

    queries = read_json(KNOWLEDGE_DIR / "yt_queries.json")["queries"][: args.max_queries]
    found = search(queries, args.days)
    videos = enrich(found) if found else []
    result = {
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "window_days": args.days,
        "queries_used": len(queries),
        "total_found": len(videos),
        "top": videos[: args.top],
    }
    write_json(args.out, result)
    print_json({"ok": True, "out": str(args.out), "total_found": len(videos),
                "top5": [{k: v[k] for k in ("title", "views", "views_per_day", "outlier_score", "url")}
                         for v in videos[:5]]})


if __name__ == "__main__":
    main()
