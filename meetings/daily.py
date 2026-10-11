"""Minimal client for the Daily.co REST API (https://docs.daily.co/reference/rest-api).

Each meeting gets its own private room; nobody can enter without a meeting
token, and the site only gives tokens to the member who booked and to admins.
The API key stays on the server."""

import json
import logging
import time
import urllib.error
import urllib.request
from urllib.parse import urlparse

from django.conf import settings

logger = logging.getLogger(__name__)

API = "https://api.daily.co/v1"
ROOM_HOURS = 3


class DailyError(Exception):
    pass


def configured():
    return bool(settings.DAILY_API_KEY)


def _call(method, path, payload=None):
    if not configured():
        raise DailyError("DAILY_API_KEY is not configured")
    data = json.dumps(payload).encode() if payload is not None else None
    req = urllib.request.Request(
        API + path,
        data=data,
        method=method,
        headers={"Authorization": f"Bearer {settings.DAILY_API_KEY}", "Content-Type": "application/json"},
    )
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            body = resp.read()
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode(errors="replace")[:300]
        logger.error("Daily API %s %s failed: %s %s", method, path, exc.code, detail)
        raise DailyError(f"Daily API error {exc.code}") from exc
    except (urllib.error.URLError, TimeoutError) as exc:
        logger.error("Could not reach the Daily API: %s", exc)
        raise DailyError("Daily API unreachable") from exc
    return json.loads(body) if body else {}


def create_room(name):
    """Create a private room that closes itself after a few hours. Returns its URL."""
    room = _call("POST", "/rooms", {
        "name": name,
        "privacy": "private",
        "properties": {
            "exp": int(time.time()) + ROOM_HOURS * 3600,
            "eject_at_room_exp": True,
            "enable_chat": True,
            "enable_screenshare": True,
            "lang": "fr",
        },
    })
    return room["url"]


def meeting_token(room_name, user_name, is_owner):
    data = _call("POST", "/meeting-tokens", {
        "properties": {
            "room_name": room_name,
            "user_name": user_name[:100],
            "is_owner": is_owner,
            "exp": int(time.time()) + ROOM_HOURS * 3600,
        },
    })
    return data["token"]


def delete_room(name):
    """Best effort: rooms also expire on their own."""
    try:
        _call("DELETE", f"/rooms/{name}")
    except DailyError:
        logger.warning("Could not delete Daily room %s", name)


def origin(room_url):
    parts = urlparse(room_url)
    return f"{parts.scheme}://{parts.netloc}"
