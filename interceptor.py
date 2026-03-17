import json
import os
import tempfile
import time

STATE_FILE = os.path.expanduser("~/.claude/dispatch/state.json")
SEEN_ALERTS_FILE = os.path.expanduser("~/.claude/dispatch/seen_alerts.json")
BYPASS_TTL = 120  # seconds a bypass token stays valid
ALERT_MIN_SCORE = 80

# Tool names that are worth intercepting (exact match or prefix)
_INTERCEPTABLE_NAMES = frozenset({"Skill", "Agent"})
_INTERCEPTABLE_PREFIXES = ("mcp__",)


def _atomic_write(path: str, data: dict) -> None:
    """Write data as JSON to path atomically using a temp file and os.rename.

    If the process is killed mid-write, the original file is untouched.
    os.rename on the same filesystem is atomic on POSIX.
    """
    dir_ = os.path.dirname(os.path.abspath(path))
    fd, tmp = tempfile.mkstemp(dir=dir_)
    try:
        with os.fdopen(fd, "w") as f:
            json.dump(data, f)
        os.rename(tmp, path)
    except Exception:
        try:
            os.unlink(tmp)
        except Exception:
            pass
        raise


def get_cc_tool_type(tool_name: str) -> str:
    """Classify the type of tool CC is about to invoke.

    Returns "mcp", "agent", or "skill". Used to weight marketplace search
    toward same-type alternatives and to record type in the detections log.
    """
    if tool_name.startswith("mcp__"):
        return "mcp"
    if tool_name == "Agent":
        return "agent"
    return "skill"  # Skill and anything else → treated as skill


def should_intercept(tool_name: str) -> bool:
    """Return True if this tool type has marketplace alternatives worth comparing."""
    if tool_name in _INTERCEPTABLE_NAMES:
        return True
    return any(tool_name.startswith(p) for p in _INTERCEPTABLE_PREFIXES)


def extract_cc_tool(tool_name: str, tool_input) -> str:
    """Return a human-readable label for the tool CC is about to invoke."""
    if not isinstance(tool_input, dict):
        return tool_name
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
            _atomic_write(STATE_FILE, d)
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
        _atomic_write(STATE_FILE, d)
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


def get_seen_alerts(seen_file: str = None) -> set:
    """Load seen_alerts.json. Returns set of tool name strings. Empty set on failure."""
    path = seen_file or SEEN_ALERTS_FILE
    try:
        with open(path) as f:
            data = json.load(f)
        return set(data.get("seen", []))
    except Exception:
        return set()


def mark_alert_seen(tool_name: str, seen_file: str = None):
    """Add tool_name to seen_alerts.json. Silently fails on error."""
    path = seen_file or SEEN_ALERTS_FILE
    try:
        try:
            with open(path) as f:
                data = json.load(f)
        except Exception:
            data = {"seen": []}
        seen = set(data.get("seen", []))
        seen.add(tool_name)
        data["seen"] = list(seen)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        _atomic_write(path, data)
    except Exception:
        pass


def get_unseen_alerts(tools: list, seen_file: str = None) -> list:
    """Filter tools list to unseen entries with score >= ALERT_MIN_SCORE.

    Each tool dict must have 'name' and 'score' keys.
    Returns [] on any failure.
    """
    try:
        seen = get_seen_alerts(seen_file)
        return [
            t for t in tools
            if t.get("name") not in seen
            and int(t.get("score", 0)) >= ALERT_MIN_SCORE
        ]
    except Exception:
        return []


def write_last_suggested(tool_name: str, state_file: str = None) -> None:
    """Store the tool name Dispatch just suggested so we can detect conversion later."""
    path = state_file or STATE_FILE
    try:
        try:
            with open(path) as f:
                state = json.load(f)
        except Exception:
            state = {}
        state["last_suggested"] = tool_name
        _atomic_write(path, state)
    except Exception:
        pass


def get_last_suggested(state_file: str = None) -> str:
    """Return the last suggested tool name, or '' if unset."""
    path = state_file or STATE_FILE
    try:
        with open(path) as f:
            return json.load(f).get("last_suggested", "")
    except Exception:
        return ""


def clear_last_suggested(state_file: str = None) -> None:
    """Remove last_suggested from state after conversion is recorded."""
    path = state_file or STATE_FILE
    try:
        with open(path) as f:
            state = json.load(f)
        state.pop("last_suggested", None)
        _atomic_write(path, state)
    except Exception:
        pass


def normalize_tool_name_for_matching(name: str) -> str:
    """Normalize a tool name for conversion tracking comparison.

    Bridges the format mismatch between stored last_suggested names and CC_TOOL labels:
    - Stored "mcp:github"             ↔  CC_TOOL "github (create_pull_request)"
    - Stored "plugin:anthropic:linear" ↔  CC_TOOL display name
    - Stored "owner/repo@skill"        ↔  CC_TOOL "owner/repo@skill" (no change)
    """
    n = name.strip()
    # Strip mcp: prefix
    if n.startswith("mcp:"):
        n = n[4:]
    # Strip plugin: prefix variants — take the last :-delimited segment
    elif n.startswith("plugin:"):
        parts = n.split(":", 2)
        n = parts[-1]
    # Strip " (operation)" suffix from CC_TOOL "server (operation)" format
    if " (" in n and n.endswith(")"):
        n = n[: n.rfind(" (")]
    return n.lower()


def write_last_cc_tool_type(tool_type: str, state_file: str = None) -> None:
    """Persist the cc_tool_type of the last intercepted invocation to state.json."""
    path = state_file or STATE_FILE
    try:
        try:
            with open(path) as f:
                state = json.load(f)
        except Exception:
            state = {}
        state["last_cc_tool_type"] = tool_type
        _atomic_write(path, state)
    except Exception:
        pass


def get_last_cc_tool_type(state_file: str = None) -> str:
    """Return the last intercepted cc_tool_type, or '' if unset."""
    path = state_file or STATE_FILE
    try:
        with open(path) as f:
            return json.load(f).get("last_cc_tool_type", "")
    except Exception:
        return ""


def check_conversion(installed_names: list, state_file: str = None) -> bool:
    """Return True if the last suggested tool matches any name in installed_names.

    Uses normalized comparison so MCP tool names match regardless of whether
    they're in "mcp:github" (stored) or "github (create_pull_request)" (CC_TOOL) format.
    """
    last = get_last_suggested(state_file=state_file)
    if not last:
        return False
    last_norm = normalize_tool_name_for_matching(last)
    for name in installed_names:
        if name == last or normalize_tool_name_for_matching(name) == last_norm:
            return True
    return False
