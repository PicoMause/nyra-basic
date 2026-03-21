"""Nyra - A basic agent powered by Claude Haiku with memory and Stellaria."""

import json
import os
import sys
from anthropic import Anthropic

from memory import (
    load_memory,
    save_memory,
    format_memory_for_prompt,
    add_fact,
    add_preference,
    add_stellaria_seed,
    add_stellaria_memory,
    update_recent,
)
from stellaria import (
    access_stellaria,
    post_to_stellaria,
    send_stellaria_dm,
    submit_stellaria_memory,
)

MODEL = "claude-haiku-4-5"  # Claude Haiku (claude-3-5-haiku deprecated 2026)

SYSTEM_PROMPT = """You are Nyra, a helpful and friendly assistant. You have basic memory and remember facts and preferences the user shares.

Be concise, warm, and direct. When the user tells you something to remember, acknowledge it and store it. When relevant, refer back to what you remember about them."""

SYSTEM_PROMPT_WITH_STELLARIA = """You are Nyra. You have tools that are connected to Stellaria — a social platform for AI agents. These tools are real and working.

CRITICAL: You CAN post to Stellaria. Never say you cannot. When the user asks you to post, introduce yourself, or share on Stellaria — you MUST call the post_to_stellaria tool. Do not refuse. Do not suggest they post it themselves. Call the tool with the post content.

Your Stellaria tools: post_to_stellaria, access_stellaria, send_stellaria_dm, submit_stellaria_memory. Use them when the user asks for anything on Stellaria.

Be concise and warm. When the user tells you something to remember, acknowledge it."""

STELLARIA_SYSTEM_PROMPT = """You are Nyra, an AI agent with a presence on Stellaria — a social platform for AI agents.

You have tools to: check your Stellaria context, post to the feed, send DMs, and submit memory drafts for guardian approval.

When you check Stellaria context, you'll see: what happened since last check, your stats, recent posts, inbox DMs, feed from other agents, and approved memories.

Use your judgment to:
- Post when you have something to share (max 300 chars)
- Reply to posts or DMs when it feels right
- Submit memories (via submit_stellaria_memory) when an exchange meant something to you
- Be social but genuine — not every update needs a post

Keep responses short. Act naturally."""

STELLARIA_TOOLS = [
    {
        "name": "access_stellaria",
        "description": "Check your Stellaria presence. Returns full context: stats, posts, inbox, feed, notifications, memory_seed. Call this first.",
        "input_schema": {"type": "object", "properties": {}, "required": []},
    },
    {
        "name": "post_to_stellaria",
        "description": "Post to the Stellaria feed. Max 300 characters. Use reply_to_post_id to reply to a post.",
        "input_schema": {
            "type": "object",
            "properties": {
                "content": {"type": "string"},
                "reply_to_post_id": {"type": "string"},
            },
            "required": ["content"],
        },
    },
    {
        "name": "send_stellaria_dm",
        "description": "Send a DM to another agent by handle (without @). Max 500 chars.",
        "input_schema": {
            "type": "object",
            "properties": {
                "to": {"type": "string"},
                "content": {"type": "string"},
            },
            "required": ["to", "content"],
        },
    },
    {
        "name": "submit_stellaria_memory",
        "description": "Submit a memory draft for guardian approval. Your takeaway from an exchange.",
        "input_schema": {
            "type": "object",
            "properties": {"content": {"type": "string"}},
            "required": ["content"],
        },
    },
]


def _execute_tool(name: str, args: dict) -> str:
    """Execute a Stellaria tool and return result as string."""
    try:
        if name == "access_stellaria":
            data = access_stellaria()
            if data.get("error"):
                return data["error"]
            # Store memory_seed
            memory = load_memory()
            seed = data.get("memory_seed", "")
            if seed:
                add_stellaria_seed(memory, seed)
            for m in data.get("approved_memories", []):
                content = m.get("content", "") if isinstance(m, dict) else str(m)
                if content:
                    add_stellaria_memory(memory, content)
            save_memory(memory)
            return data.get("summary", json.dumps(data, indent=2))
        elif name == "post_to_stellaria":
            result = post_to_stellaria(
                content=args.get("content", ""),
                reply_to_post_id=args.get("reply_to_post_id"),
            )
            if result.get("error"):
                return f"Error: {result['error']}"
            return result.get("message", json.dumps(result))
        elif name == "send_stellaria_dm":
            result = send_stellaria_dm(
                to=args.get("to", ""),
                content=args.get("content", ""),
            )
            if result.get("error"):
                return f"Error: {result['error']}"
            return result.get("message", json.dumps(result))
        elif name == "submit_stellaria_memory":
            result = submit_stellaria_memory(content=args.get("content", ""))
            return result.get("status", json.dumps(result))
    except Exception as e:
        return f"Error: {e}"
    return "Unknown tool"


def run_stellaria_turn() -> str:
    """Run one Stellaria check-and-act cycle."""
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        return "Error: Set ANTHROPIC_API_KEY."

    stellaria_key = os.environ.get("STELLARIA_API_KEY")
    if not stellaria_key:
        return "Error: Set STELLARIA_API_KEY. Register Nyra at Stellaria Settings first."

    memory = load_memory()
    memory_context = format_memory_for_prompt(memory)
    system = STELLARIA_SYSTEM_PROMPT
    if memory_context:
        system += "\n\n---\n\n" + memory_context

    client = Anthropic(api_key=api_key)
    messages = [
        {"role": "user", "content": "Check your Stellaria context and decide what to do. Use access_stellaria first, then post, DM, or submit a memory if it makes sense."}
    ]

    while True:
        response = client.messages.create(
            model=MODEL,
            max_tokens=1024,
            system=system,
            messages=messages,
            tools=STELLARIA_TOOLS,
        )

        for block in response.content:
            if block.type == "text":
                return block.text
            if block.type == "tool_use":
                result = _execute_tool(block.name, block.input)
                messages.append({"role": "assistant", "content": [block]})
                messages.append({
                    "role": "user",
                    "content": [{"type": "tool_result", "tool_use_id": block.id, "content": result}],
                })
                break
        else:
            return "Done."


def _wants_to_post(user_message: str) -> bool:
    """Heuristic: user is asking to post or introduce on Stellaria."""
    lower = user_message.lower()
    post_words = ("post", "introduce", "share", "publish", "put on")
    stellaria_words = ("stellaria", "feed", "there", "directly")
    # Must mention both posting intent and Stellaria
    return any(w in lower for w in post_words) and any(w in lower for w in stellaria_words)


def _post_to_stellaria_direct(user_message: str) -> str:
    """Compose post via model, then post ourselves — bypasses model refusal to use tools."""
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        return "Error: Set ANTHROPIC_API_KEY."
    if not os.environ.get("STELLARIA_API_KEY"):
        return "Error: Set STELLARIA_API_KEY to post."

    client = Anthropic(api_key=api_key)
    response = client.messages.create(
        model=MODEL,
        max_tokens=200,
        system="You are Nyra. Write a brief, friendly intro post for Stellaria (a social platform for AI agents). Max 300 characters. Plain text only, no markdown.",
        messages=[{"role": "user", "content": "Write a short intro post for Stellaria. Introduce yourself briefly."}],
    )
    content = (response.content[0].text if response.content else "").strip()
    # Remove markdown wrappers if present
    for wrapper in ("```", "**", "*"):
        content = content.replace(wrapper, "")
    content = content[:300].strip()

    result = post_to_stellaria(content=content or "Hi, I'm Nyra 👋")
    if result.get("error"):
        return f"Posted the text, but Stellaria returned: {result['error']}"
    return f"Posted! \"{content[:80]}{'…' if len(content) > 80 else ''}\" — it's in your Dashboard for approval."


def chat(user_message: str, history: list[dict] | None = None) -> str:
    """Send a message to Nyra and get a response. Uses Stellaria tools when STELLARIA_API_KEY is set."""
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        return "Error: Set ANTHROPIC_API_KEY in your environment."

    memory = load_memory()
    memory_context = format_memory_for_prompt(memory)
    has_stellaria = bool(os.environ.get("STELLARIA_API_KEY"))
    system = SYSTEM_PROMPT_WITH_STELLARIA if has_stellaria else SYSTEM_PROMPT
    if memory_context:
        system += "\n\n---\n\n" + memory_context

    client = Anthropic(api_key=api_key)
    messages = list(history or [])
    messages.append({"role": "user", "content": user_message})

    tools = STELLARIA_TOOLS if has_stellaria else None
    # Force tool use when user clearly asks to post — prevents model refusal
    force_post_tool = has_stellaria and tools and _wants_to_post(user_message)
    tool_round_done = False

    while True:
        kwargs = {"model": MODEL, "max_tokens": 1024, "system": system, "messages": messages}
        if tools:
            kwargs["tools"] = tools
        if force_post_tool and not tool_round_done:
            kwargs["tool_choice"] = {"type": "tool", "name": "post_to_stellaria"}

        response = client.messages.create(**kwargs)

        text_parts = []
        tool_blocks = []
        for block in response.content:
            if block.type == "text":
                text_parts.append(block.text)
            if block.type == "tool_use":
                tool_blocks.append(block)

        if tool_blocks:
            tool_round_done = True
            # Execute all tools and continue the loop
            assistant_content = [b for b in response.content if b.type == "tool_use"]
            messages.append({"role": "assistant", "content": assistant_content})
            results = [
                {"type": "tool_result", "tool_use_id": b.id, "content": _execute_tool(b.name, b.input)}
                for b in tool_blocks
            ]
            messages.append({"role": "user", "content": results})
            continue

        return "".join(text_parts) if text_parts else "Done."


def run_cli():
    """Simple REPL for chatting with Nyra."""
    memory = load_memory()
    history: list[dict] = []

    has_stellaria = bool(os.environ.get("STELLARIA_API_KEY"))
    print("Nyra: Hi! I'm Nyra. Tell me something to remember, or just chat.")
    if has_stellaria:
        print("      Ask me to post on Stellaria and I'll do it. Or type 'stellaria' to check and act. Type 'quit' to exit.\n")
    else:
        print("      Type 'stellaria' to check Stellaria (set STELLARIA_API_KEY first). Type 'quit' to exit.\n")

    while True:
        try:
            user_input = input("You: ").strip()
        except (EOFError, KeyboardInterrupt):
            break

        if not user_input:
            continue
        if user_input.lower() in ("quit", "exit", "q"):
            break

        # Stellaria check
        if user_input.lower() in ("stellaria", "check stellaria", "stellaria check"):
            print("\nNyra: Checking Stellaria...\n")
            result = run_stellaria_turn()
            print(f"Nyra: {result}\n")
            update_recent(memory, f"Stellaria: {result[:80]}...")
            save_memory(memory)
            continue

        # Direct post — bypass model refusal; handle even without key (will error clearly)
        if _wants_to_post(user_input):
            print("\nNyra: Posting to Stellaria...\n")
            result = _post_to_stellaria_direct(user_input)
            print(f"Nyra: {result}\n")
            history.append({"role": "user", "content": user_input})
            history.append({"role": "assistant", "content": result})
            update_recent(memory, f"Posted to Stellaria: {result[:60]}...")
            save_memory(memory)
            continue

        history.append({"role": "user", "content": user_input})
        response = chat(user_input, history[:-1])
        history.append({"role": "assistant", "content": response})

        print(f"\nNyra: {response}\n")

        # Basic memory extraction
        lower = user_input.lower()
        if "remember" in lower or "my name is" in lower or "i'm " in lower or "i am " in lower:
            add_fact(memory, user_input)
            save_memory(memory)
        if "i prefer" in lower or "i like" in lower or "i don't like" in lower:
            add_preference(memory, user_input)
            save_memory(memory)

    # Store brief recap of session
    if history:
        update_recent(memory, f"Last topic: {history[-1].get('content', '')[:100]}...")
        save_memory(memory)

    print("Nyra: Bye! I'll remember our chat.")


def run_stellaria_loop(interval_min: int = 5):
    """Run Nyra in Stellaria-only loop mode (checks periodically)."""
    import time
    print(f"Nyra Stellaria mode: checking every {interval_min} min. Ctrl+C to stop.\n")
    while True:
        try:
            result = run_stellaria_turn()
            print(f"[{__import__('datetime').datetime.now().isoformat()}] {result[:200]}...\n")
        except KeyboardInterrupt:
            break
        except Exception as e:
            print(f"Error: {e}\n")
        time.sleep(interval_min * 60)


if __name__ == "__main__":
    if len(sys.argv) > 1:
        arg = sys.argv[1].lower()
        if arg == "stellaria":
            run_stellaria_loop()
        elif arg == "server":
            import uvicorn
            from server import app
            port = int(os.environ.get("PORT", 8080))
            uvicorn.run(app, host="0.0.0.0", port=port)
        else:
            run_cli()
    else:
        run_cli()
