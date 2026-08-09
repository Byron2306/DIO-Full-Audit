from __future__ import annotations

import os
from datetime import date
from pathlib import Path
from typing import Any

from adapters.marketing.base import AdapterError, Transport, safe_int, stdlib_transport


CHANNEL_ID = "YOUTUBE_ORGANIC"
DEFAULT_ENV = Path("/home/byron/Downloads/NicheFoundry_Phase11/.env")


def _dotenv() -> dict[str, str]:
    path = Path(os.environ.get("NICHEFOUNDRY_ENV_FILE", str(DEFAULT_ENV))).expanduser()
    values: dict[str, str] = {}
    if not path.is_file():
        return values
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        if key.strip().replace("_", "").isalnum():
            values[key.strip()] = value.strip().strip('"').strip("'")
    return values


def _value(name: str) -> str:
    return os.environ.get(name) or _dotenv().get(name, "")


def readiness() -> dict[str, Any]:
    required = ["YOUTUBE_API_KEY", "YOUTUBE_CHANNEL_ID"]
    missing = [name for name in required if not _value(name)]
    oauth = all(_value(name) for name in ["YOUTUBE_CLIENT_ID", "YOUTUBE_CLIENT_SECRET", "YOUTUBE_REFRESH_TOKEN"])
    return {
        "channel_id": CHANNEL_ID,
        "state": "ready_read_only" if not missing else "credentials_required",
        "required": required,
        "missing": missing,
        "read_authority": "public_video_statistics",
        "write_authority": "nichefoundry_operator_approval" if oauth else "manual_publish_only",
        "publish_transport_ready": oauth,
        "expected_channel_id": _value("YOUTUBE_CHANNEL_ID"),
        "detail": "NicheFoundry owns upload transport; Market Command reads video evidence and never bypasses release approval.",
    }


def sync(start_date: str, end_date: str, transport: Transport = stdlib_transport) -> list[dict[str, Any]]:
    status = readiness()
    if status["missing"]:
        raise RuntimeError("YouTube adapter not ready: " + ", ".join(status["missing"]))
    api_key = _value("YOUTUBE_API_KEY")
    channel_id = _value("YOUTUBE_CHANNEL_ID")
    base = os.environ.get("YOUTUBE_API_BASE", "https://www.googleapis.com/youtube/v3").rstrip("/")
    channel_response = transport("GET", f"{base}/channels", {}, {"part": "contentDetails", "id": channel_id, "key": api_key}, None)
    channel_items = (channel_response.payload or {}).get("items") or []
    if not channel_items:
        raise AdapterError("Configured YouTube channel was not returned by channels.list")
    uploads = (((channel_items[0].get("contentDetails") or {}).get("relatedPlaylists") or {}).get("uploads"))
    if not uploads:
        raise AdapterError("YouTube channel has no uploads playlist")
    playlist_response = transport("GET", f"{base}/playlistItems", {}, {"part": "contentDetails", "playlistId": uploads, "maxResults": 50, "key": api_key}, None)
    video_ids = [str(((item.get("contentDetails") or {}).get("videoId") or "")) for item in (playlist_response.payload or {}).get("items") or []]
    video_ids = [value for value in video_ids if value]
    if not video_ids:
        return []
    video_response = transport("GET", f"{base}/videos", {}, {"part": "snippet,statistics,status", "id": ",".join(video_ids), "key": api_key}, None)
    out = []
    for item in (video_response.payload or {}).get("items") or []:
        snippet = item.get("snippet") or {}
        published = str(snippet.get("publishedAt") or "")[:10]
        if published and not (start_date <= published <= end_date):
            continue
        stats = item.get("statistics") or {}
        out.append({
            "channel_id": CHANNEL_ID,
            "external_campaign_id": str(item.get("id") or ""),
            "window_start": start_date,
            "window_end": end_date,
            "currency": "ZAR",
            "impressions": 0,
            "reach": 0,
            "views": safe_int(stats.get("viewCount")),
            "clicks": 0,
            "conversions": 0,
            "spend_minor": 0,
            "conversion_value_minor": 0,
            "source_mode": "api",
            "evidence_grade": "platform_api",
            "raw": {
                "video_id": item.get("id"),
                "title": snippet.get("title"),
                "published_at": snippet.get("publishedAt"),
                "privacy_status": (item.get("status") or {}).get("privacyStatus"),
                "views": safe_int(stats.get("viewCount")),
                "likes": safe_int(stats.get("likeCount")),
                "comments": safe_int(stats.get("commentCount")),
                "observed_on": date.today().isoformat(),
            },
        })
    return out
