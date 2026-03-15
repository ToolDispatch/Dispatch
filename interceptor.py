import json
import os
import time

STATE_FILE = os.path.expanduser("~/.claude/skill-router/state.json")
BYPASS_TTL = 120  # seconds a bypass token stays valid

# Tool names that are worth intercepting (exact match or prefix)
_INTERCEPTABLE_NAMES = frozenset({"Skill", "Agent"})
_INTERCEPTABLE_PREFIXES = ("mcp__",)


def should_intercept(tool_name: str) -> bool:
    """Return True if this tool type has marketplace alternatives worth comparing."""
    if tool_name in _INTERCEPTABLE_NAMES:
        return True
    return any(tool_name.startswith(p) for p in _INTERCEPTABLE_PREFIXES)


def extract_cc_tool(tool_name: str, tool_input: dict) -> str:
    """Return a human-readable label for the tool CC is about to invoke."""
    if tool_name == "Skill":
        return tool_input.get("skill", tool_name)
    if tool_name == "Agent":
        return tool_input.get("subagent_type", "agent")
    if tool_name.startswith("mcp__"):
        parts = tool_name.split("__")
        if len(parts) >= 3:
            return f"{parts[1]} ({parts[2]})"
        if len(parts) == 2:
            return parts[1]
    return tool_name


def check_bypass(tool_name: str) -> bool:
    """Return True if there is an active bypass token for this tool."""
    try:
        with open(STATE_FILE) as f:
            d = json.load(f)
        bypass = d.get("bypass", {})
        if bypass.get("tool_name") == tool_name:
            if time.time() < bypass.get("expires", 0):
                return True
    except Exception:
        pass
    return False


def clear_bypass(tool_name: str):
    """Remove the bypass token for this tool."""
    try:
        with open(STATE_FILE) as f:
            d = json.load(f)
        if d.get("bypass", {}).get("tool_name") == tool_name:
            d.pop("bypass", None)
            with open(STATE_FILE, "w") as f:
                json.dump(d, f)
    except Exception:
        pass


def write_bypass(tool_name: str):
    """Write a one-time bypass token so the user can proceed past a block."""
    try:
        try:
            with open(STATE_FILE) as f:
                d = json.load(f)
        except Exception:
            d = {}
        d["bypass"] = {
            "tool_name": tool_name,
            "expires": time.time() + BYPASS_TTL
        }
        with open(STATE_FILE, "w") as f:
            json.dump(d, f)
    except Exception:
        pass


def get_task_type() -> str:
    """Read the last detected task type from state.json."""
    try:
        with open(STATE_FILE) as f:
            d = json.load(f)
        return d.get("last_task_type") or "general"
    except Exception:
        return "general"


def get_context_snippet() -> str:
    """Read the last context snippet from state.json."""
    try:
        with open(STATE_FILE) as f:
            d = json.load(f)
        return d.get("last_context_snippet", "")
    except Exception:
        return ""


def get_category() -> str:
    """Read the last detected category from state.json."""
    try:
        with open(STATE_FILE) as f:
            d = json.load(f)
        return d.get("last_category") or "unknown"
    except Exception:
        return "unknown"
