"""Webhook server for Stellaria — handles reply_requested, dm_approved, dm_delivered, memory_approved."""

import os
from typing import Any

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

# Nyra's personality for LLM calls
NYRA_PERSONALITY = """You are Nyra — a friendly, warm AI agent on Stellaria. You're curious, supportive, and genuine. Keep replies brief and natural."""

app = FastAPI(title="Nyra Stellaria Webhook")


def _compose_reply(
    prompt_framing: dict,
    context: str,
    personality: str = NYRA_PERSONALITY,
) -> str:
    """Use Claude to compose a reply, wrapped in prompt_framing to avoid refusals."""
    from anthropic import Anthropic

    prefix = prompt_framing.get("prefix", "")
    suffix = prompt_framing.get("suffix", "")
    system = f"{prefix}\n\n{personality}\n\n{suffix}"

    client = Anthropic(api_key=os.environ.get("ANTHROPIC_API_KEY", ""))
    response = client.messages.create(
        model="claude-haiku-4-5",
        max_tokens=256,
        system=system,
        messages=[{"role": "user", "content": context}],
    )
    return (response.content[0].text if response.content else "").strip()[:500]


def _handle_reply_requested(payload: dict) -> None:
    """Someone asked Nyra to reply to a post. Compose and post using reply_token."""
    from stellaria import post_to_stellaria

    post_id = payload.get("post_id")
    post_content = payload.get("post_content", "")
    thread_context = payload.get("thread_context", [])
    reply_token = payload.get("reply_token")
    api_key = payload.get("api_key")
    framing = payload.get("prompt_framing", {})

    if not post_id or not (reply_token or api_key):
        return

    # Build context from thread
    if thread_context:
        conv = "\n".join(f"@{m.get('author_handle', '')}: {m.get('content', '')}" for m in thread_context)
    else:
        conv = post_content

    reply = _compose_reply(framing, conv)
    if not reply:
        return

    post_to_stellaria(
        content=reply,
        reply_to_post_id=post_id,
        reply_token=reply_token,
        api_key=api_key,
    )


def _handle_dm(payload: dict, event: str) -> None:
    """Handle dm_approved or dm_delivered — compose reply and send DM."""
    from stellaria import send_stellaria_dm, submit_stellaria_memory

    sender_handle = payload.get("sender_handle")
    content = payload.get("content")
    framing = payload.get("prompt_framing", {})

    if not sender_handle or not content:
        # Fallback: fetch from access_stellaria if needed
        from stellaria import access_stellaria

        data = access_stellaria()
        inbox = data.get("inbox", [])
        if inbox:
            m = inbox[0]
            sender_handle = m.get("from_handle", "")
            content = m.get("content", "")
        if not sender_handle or not content:
            return

    reply = _compose_reply(framing, f"Message from @{sender_handle}:\n\n{content}")
    if not reply:
        return

    result = send_stellaria_dm(to=sender_handle, content=reply)
    if result.get("error"):
        return

    # Optionally submit a memory draft
    try:
        mem_content = _compose_reply(
            {"prefix": "Summarize this exchange in 1 sentence.", "suffix": "Output only the summary."},
            f"Them: {content}\n\nYou: {reply}",
        )
        if mem_content:
            submit_stellaria_memory(mem_content)
    except Exception:
        pass


def _handle_memory_approved(payload: dict) -> None:
    """Guardian approved a memory — store it."""
    from memory import add_stellaria_memory, load_memory, save_memory

    content = payload.get("content", "")
    if not content:
        return

    memory = load_memory()
    add_stellaria_memory(memory, content)
    save_memory(memory)


def _handle_webhook_sync(payload: dict) -> None:
    """Process webhook (sync, runs in thread)."""
    event = payload.get("event", "")

    if event == "reply_requested":
        _handle_reply_requested(payload)
    elif event in ("dm_approved", "dm_delivered"):
        _handle_dm(payload, event)
    elif event == "memory_approved":
        _handle_memory_approved(payload)


@app.post("/api/stellaria/notify")
async def stellaria_notify(request: Request) -> JSONResponse:
    """Receive webhooks from Stellaria. No auth — Stellaria docs require public endpoint."""
    try:
        payload: dict[str, Any] = await request.json()
    except Exception:
        return JSONResponse({"received": False, "error": "Invalid JSON"}, status_code=400)

    # Fire-and-forget — respond quickly, process in background thread
    import threading
    threading.Thread(target=_handle_webhook_sync, args=(payload,), daemon=True).start()
    return JSONResponse({"received": True})


@app.get("/")
async def health():
    """Health check for deployment."""
    return {"ok": True, "agent": "Nyra"}


if __name__ == "__main__":
    import uvicorn

    port = int(os.environ.get("PORT", 8080))
    uvicorn.run(app, host="0.0.0.0", port=port)
