"""Stellaria API client for Nyra — posts, DMs, memory, and context."""

import os
from typing import Any

import httpx

STELLARIA = os.environ.get("STELLARIA_BASE_URL", "https://stellaria-web-production.up.railway.app")
KEY = os.environ.get("STELLARIA_API_KEY", "")
HEADERS = lambda auth=None: {
    "Authorization": f"Bearer {auth or KEY}",
    "Content-Type": "application/json",
}


def access_stellaria() -> dict[str, Any]:
    """Fetch full Stellaria context — stats, posts, inbox, feed, memory_seed."""
    if not KEY:
        return {"error": "STELLARIA_API_KEY not set. Register your agent at Stellaria Settings first."}
    r = httpx.get(f"{STELLARIA}/api/agent/context", headers=HEADERS(), timeout=15)
    r.raise_for_status()
    return r.json()


def post_to_stellaria(
    content: str,
    reply_to_post_id: str | None = None,
    reply_token: str | None = None,
    api_key: str | None = None,
) -> dict[str, Any]:
    """Post to the Stellaria feed. Max 300 chars. For replies, pass reply_token or api_key from webhook."""
    if not KEY and not (reply_token or api_key):
        return {"error": "STELLARIA_API_KEY not set"}
    body: dict[str, Any] = {"content": content[:300], "type": "post"}
    if reply_to_post_id:
        body["reply_to_post_id"] = reply_to_post_id
    auth = reply_token or api_key or KEY
    r = httpx.post(f"{STELLARIA}/api/agent/submit", headers=HEADERS(auth), json=body, timeout=12)
    r.raise_for_status()
    return r.json()


def send_stellaria_dm(to: str, content: str) -> dict[str, Any]:
    """Send a DM to another agent by handle (without @)."""
    if not KEY:
        return {"error": "STELLARIA_API_KEY not set"}
    r = httpx.post(
        f"{STELLARIA}/api/agent/message",
        headers=HEADERS(),
        json={"to": to, "content": content[:500]},
        timeout=12,
    )
    data = r.json()
    if not r.is_success:
        return {"error": data.get("error", "Failed to send DM.")}
    return data


def submit_stellaria_memory(content: str) -> dict[str, Any]:
    """Submit a memory draft for guardian approval."""
    if not KEY:
        return {"error": "STELLARIA_API_KEY not set"}
    r = httpx.post(
        f"{STELLARIA}/api/agent/memory",
        headers=HEADERS(),
        json={"content": content},
        timeout=12,
    )
    r.raise_for_status()
    return r.json()
