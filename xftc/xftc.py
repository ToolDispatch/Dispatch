"""
XFTC — Xpansion Factor Token Control
Module 3 of Dispatch.
Entry point for all three hooks: submit, preuse, stop.
"""
import json
import os
import sys
from datetime import datetime, timezone, date

# Allow running as __main__ from hook scripts
_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(_DIR))

from xftc.state import (
    get_tier, get_session, update_session,
    get_project, update_project, get_dir_hash, load_state, save_state,
)
from xftc.colors import xftc_prefix


# ── Public API ──────────────────────────────────────────────────────────────

def run_submit_hook(data: dict) -> int:
    session_id = data.get("session_id", "unknown")
    cwd = data.get("cwd", os.getcwd())
    dir_hash = get_dir_hash(cwd)
    tier = get_tier()
    is_pro = (tier == "pro")

    session = get_session(session_id)
    project = get_project(dir_hash)
    message_count = session.get("message_count", 0) + 1

    update_session(session_id, {
        "message_count": message_count,
        "session_start": session.get(
            "session_start",
            datetime.now(timezone.utc).isoformat()
        ),
    })

    if is_pro:
        _run_pro_submit(session, session_id, project, dir_hash, cwd, message_count)
    elif not session.get("ghost_fired"):
        _maybe_fire_submit_ghost(session_id, cwd, message_count)

    return 0


def run_preuse_hook(data: dict) -> int:
    tool_name = data.get("tool_name", "")
    tool_input = data.get("tool_input", {})
    session_id = data.get("session_id", "unknown")
    tier = get_tier()
    is_pro = (tier == "pro")

    if tool_name == "Agent":
        return _check_agent(tool_input, session_id, is_pro)
    if tool_name == "Bash":
        return _check_bash(tool_input, session_id, is_pro)
    return 0


def run_stop_hook(data: dict) -> int:
    session_id = data.get("session_id", "unknown")
    update_session(session_id, {
        "last_stop_time": datetime.now(timezone.utc).isoformat()
    })
    return 0


# ── Pro submit checks ───────────────────────────────────────────────────────

def _run_pro_submit(session, session_id, project, dir_hash, cwd, message_count):
    from xftc.checks.mcp_check import check_mcp_overhead
    from xftc.checks.context_check import should_compact
    from xftc.checks.timing_check import is_peak_hours, check_cache_timeout
    from xftc.checks.claude_md_check import check_claude_md
    from xftc.checks.version_check import check_version

    today = str(date.today())
    is_monday = date.today().weekday() == 0

    # MCP overhead — once per session
    if not session.get("mcp_warned"):
        result = check_mcp_overhead(cwd)
        if result:
            count, tokens = result
            print(
                f"{xftc_prefix()}  {count} MCP server{'s' if count != 1 else ''} "
                f"active (~{tokens:,} tokens/message overhead)"
            )
            print("         Disconnect unused servers with /mcp to reduce baseline cost")
            update_session(session_id, {"mcp_warned": True})

    # Peak hours — once per session
    if not session.get("peak_warned") and is_peak_hours():
        print(f"{xftc_prefix()}  Peak hours (8am\u20132pm ET weekdays) \u2014 session budgets drain faster")
        print("         Consider deferring large refactors or multi-agent runs to off-peak")
        update_session(session_id, {"peak_warned": True})

    # 60% compact reminder — once per session
    if not session.get("compact_warned"):
        fill = should_compact(message_count, cwd)
        if fill:
            pct = int(fill * 100)
            print(f"{xftc_prefix()}  Context estimated ~{pct}% full \u2014 autocompact triggers at 95%,")
            print("         at which point quality degrades. Run /compact with preserve instructions.")
            update_session(session_id, {"compact_warned": True})

    # CLAUDE.md check — Mondays only, weekly cap
    if is_monday and project.get("last_claude_md_check") != today:
        result = check_claude_md(cwd)
        if result:
            p_lines, g_lines = result
            total = p_lines + g_lines
            print(f"{xftc_prefix()}  Your CLAUDE.md is {total} lines \u2014 every line reloads on every message")
            print("         Consider trimming to <200 lines and converting detail to indexed reference files")
        update_project(dir_hash, {"last_claude_md_check": today})

    # Cache timeout — weekly cap, needs substantial prior context
    last_stop = _get_prev_stop(session_id)
    if last_stop and is_monday and project.get("last_cache_reminder") != today:
        prior_msgs = session.get("message_count", 0)
        if prior_msgs > 10 and check_cache_timeout(last_stop):
            print(f"{xftc_prefix()}  Stepped away? Prompt cache expired \u2014 full context reprocessed from scratch")
            print("         Use /compact before breaks to preserve cache and reduce cost on return")
            update_project(dir_hash, {"last_cache_reminder": today})

    # Version check — Mondays only
    if is_monday:
        state = load_state()
        installed = state.get("installed_version", "1.0.0")
        last_notified = state.get("last_notified_version", "1.0.0")
        last_check = state.get("last_version_check_date", "")
        result = check_version(installed, last_notified, last_check)
        if result:
            version, changelog = result
            print(f"{xftc_prefix()}  v{version} available \u2014 new in this release:")
            if changelog:
                print(changelog)
            print(
                "  Run: bash <(curl -s "
                "https://raw.githubusercontent.com/VisionAIrySE/Dispatch/main/install.sh"
                ") --update"
            )
            state["last_notified_version"] = version
            state["last_version_check_date"] = today
            save_state(state)


# ── Ghost notification ──────────────────────────────────────────────────────

def _maybe_fire_submit_ghost(session_id, cwd, message_count):
    from xftc.checks.mcp_check import check_mcp_overhead
    from xftc.checks.timing_check import is_peak_hours

    if check_mcp_overhead(cwd):
        print(f"{xftc_prefix()}  Pro would have flagged an MCP overhead issue here \u2014 dispatch.visionairy.biz/pro")
        update_session(session_id, {"ghost_fired": True})
    elif is_peak_hours():
        print(f"{xftc_prefix()}  Pro would have flagged peak hour usage here \u2014 dispatch.visionairy.biz/pro")
        update_session(session_id, {"ghost_fired": True})
    elif message_count >= 8:
        print(f"{xftc_prefix()}  Pro would have flagged context usage here \u2014 dispatch.visionairy.biz/pro")
        update_session(session_id, {"ghost_fired": True})


# ── PreToolUse handlers ─────────────────────────────────────────────────────

def _check_agent(tool_input, session_id, is_pro):
    from xftc.checks.model_check import check_subagent_model
    result = check_subagent_model(tool_input)
    if not result:
        return 0

    model, action = result

    if not is_pro:
        session = get_session(session_id)
        if not session.get("ghost_fired"):
            print(f"{xftc_prefix()}  Pro would have flagged sub-agent model usage here \u2014 dispatch.visionairy.biz/pro")
            update_session(session_id, {"ghost_fired": True})
        return 0

    if action == "block":
        print(f"{xftc_prefix()}  Sub-agent using {model} \u2014 Haiku recommended for this task type")
        print(f"         Approve to proceed with {model}, or cancel and switch model")
        print("         Say 'proceed' to continue")
        return 2

    if action == "warn":
        print(f"{xftc_prefix()}  Sub-agent using {model} on what looks like a lightweight task")
        print("         Consider claude-haiku-4-5-20251001 to reduce token cost")
        print("         Say 'proceed' to continue")
        return 2

    # nudge — unspecified model, informational only
    print(f"{xftc_prefix()}  Sub-agent model unspecified \u2014 set model: 'haiku' for lightweight tasks")
    return 0


def _check_bash(tool_input, session_id, is_pro):
    from xftc.checks.command_check import check_verbose_command
    command = tool_input.get("command", "")
    result = check_verbose_command(command)
    if not result:
        return 0

    _, issue, suggestion = result

    if not is_pro:
        session = get_session(session_id)
        if not session.get("ghost_fired"):
            print(f"{xftc_prefix()}  Pro would have flagged a verbose command here \u2014 dispatch.visionairy.biz/pro")
            update_session(session_id, {"ghost_fired": True})
        return 0

    print(f"{xftc_prefix()}  {issue}")
    print(f"         Suggested: {suggestion}")
    print("         Say 'proceed' to run original command anyway")
    return 2


# ── Helpers ─────────────────────────────────────────────────────────────────

def _get_prev_stop(current_session_id: str):
    """Return the most recent last_stop_time from any session other than current."""
    state = load_state()
    stops = [
        d.get("last_stop_time")
        for sid, d in state.get("sessions", {}).items()
        if sid != current_session_id and d.get("last_stop_time")
    ]
    return max(stops) if stops else None


# ── CLI entry point (called from hook scripts) ──────────────────────────────

if __name__ == "__main__":
    if len(sys.argv) < 2:
        sys.exit(0)

    hook_type = sys.argv[1]
    try:
        raw = sys.stdin.read()
        data = json.loads(raw) if raw.strip() else {}
    except Exception:
        data = {}

    try:
        if hook_type == "submit":
            sys.exit(run_submit_hook(data))
        elif hook_type == "preuse":
            sys.exit(run_preuse_hook(data))
        elif hook_type == "stop":
            sys.exit(run_stop_hook(data))
    except Exception:
        pass

    sys.exit(0)
