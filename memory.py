"""Basic memory storage for Nyra agent."""

import json
from pathlib import Path

MEMORY_FILE = Path(__file__).parent / "data" / "memory.json"


def _ensure_data_dir() -> Path:
    MEMORY_FILE.parent.mkdir(parents=True, exist_ok=True)
    return MEMORY_FILE


def load_memory() -> dict:
    """Load memory from disk."""
    path = _ensure_data_dir()
    if path.exists():
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            pass
    return {"facts": [], "preferences": [], "recent": []}


def save_memory(memory: dict) -> None:
    """Persist memory to disk."""
    path = _ensure_data_dir()
    path.write_text(json.dumps(memory, indent=2, ensure_ascii=False), encoding="utf-8")


def add_fact(memory: dict, fact: str) -> None:
    """Add a fact to memory."""
    memory["facts"] = memory.get("facts", [])
    if fact not in memory["facts"]:
        memory["facts"].append(fact)


def add_preference(memory: dict, preference: str) -> None:
    """Add a preference to memory."""
    memory["preferences"] = memory.get("preferences", [])
    if preference not in memory["preferences"]:
        memory["preferences"].append(preference)


def update_recent(memory: dict, summary: str, max_items: int = 5) -> None:
    """Update recent conversation summary."""
    memory["recent"] = memory.get("recent", [])
    memory["recent"].insert(0, summary)
    memory["recent"] = memory["recent"][:max_items]


def add_stellaria_seed(memory: dict, seed: str) -> None:
    """Store Stellaria memory_seed (neutral context summary)."""
    memory["stellaria_seeds"] = memory.get("stellaria_seeds", [])
    if seed and seed not in memory["stellaria_seeds"]:
        memory["stellaria_seeds"].append(seed)
        memory["stellaria_seeds"] = memory["stellaria_seeds"][-20:]  # keep last 20


def add_stellaria_memory(memory: dict, content: str) -> None:
    """Store a guardian-approved Stellaria memory."""
    memory["stellaria_memories"] = memory.get("stellaria_memories", [])
    if content and content not in memory["stellaria_memories"]:
        memory["stellaria_memories"].append(content)
        memory["stellaria_memories"] = memory["stellaria_memories"][-50:]  # keep last 50


def format_memory_for_prompt(memory: dict) -> str:
    """Format memory as context for the model."""
    parts = []
    if memory.get("facts"):
        parts.append("## Facts you remember\n" + "\n".join(f"- {f}" for f in memory["facts"]))
    if memory.get("preferences"):
        parts.append("## User preferences\n" + "\n".join(f"- {p}" for p in memory["preferences"]))
    if memory.get("stellaria_memories"):
        parts.append("## Stellaria memories (guardian-approved)\n" + "\n".join(f"- {m}" for m in memory["stellaria_memories"][-5:]))
    if memory.get("recent"):
        parts.append("## Recent context\n" + "\n".join(f"- {r}" for r in memory["recent"]))
    if not parts:
        return ""
    return "\n\n".join(parts)
