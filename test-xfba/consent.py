# consent.py
from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from typing import Dict, Any

from colors import XFA_CYAN, XFA_GREEN, XFA_YELLOW, XFA_GRAY, XFA_RESET

_STATE_FILE = "session_state.json"
_REPAIR_LOG = "repair_log.json"


def _read_state(xf_dir: str) -> Dict[str, Any]:
    path = os.path.join(xf_dir, _STATE_FILE)
    try:
        return json.loads(open(path).read())
    except Exception:
        return {}


def _write_state(xf_dir: str, state: Dict[str, Any]) -> None:
    path = os.path.join(xf_dir, _STATE_FILE)
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(state, f, indent=2)
    os.replace(tmp, path)


def get_trust_level(xf_dir: str) -> int:
    return int(_read_state(xf_dir).get("trust_level", 0))


def increment_trust(xf_dir: str) -> int:
    state = _read_state(xf_dir)
    level = int(state.get("trust_level", 0)) + 1
    state["trust_level"] = level
    state["last_updated"] = datetime.now(timezone.utc).isoformat()
    _write_state(xf_dir, state)
    return level


def reset_trust(xf_dir: str) -> None:
    state = _read_state(xf_dir)
    state["trust_level"] = 0
    state["session_start"] = datetime.now(timezone.utc).isoformat()
    _write_state(xf_dir, state)


def format_consent_options(violations=None, repair=None, trust_level: int = 0, n_violations: int = None) -> str:
    # New signature: format_consent_options(violations_list, repair_list, trust_level=0)
    # Legacy signature: format_consent_options(trust_level=N, n_violations=N)
    if violations is None or isinstance(violations, int):
        # Legacy call: format_consent_options(trust_level=N, n_violations=N)
        # violations may be an int if called positionally with old code
        if isinstance(violations, int):
            trust_level = violations
        if n_violations is None:
            n_violations = 0
        # Fix 8: reframe as instructions to Claude, not UI buttons
        lines = [""]
        if trust_level >= 2:
            lines.append(
                f"  {XFA_GRAY}To proceed: say 'apply all {n_violations} repairs', "
                f"'show me the diff first', or 'skip for now'.{XFA_RESET}"
            )
        else:
            lines.append(
                f"  {XFA_GRAY}To proceed: say 'show me the diff first' or 'skip for now'.{XFA_RESET}"
            )
            if trust_level == 0:
                lines.append(
                    f"  {XFA_GRAY}After 2 verified repairs this session, bulk-apply unlocks.{XFA_RESET}"
                )
        return "\n".join(lines)

    # New call: format_consent_options(violations_list, repair, trust_level=0)
    # State 1: initial violation block -- Fix problem / Show diff options
    repair = repair or []
    lines = []
    for v in (violations or [])[:3]:
        lines.append(f"  \u26a0  {v.get('consequence', '')}")
        if v.get('fix'):
            lines.append(f"     Repair: {v['fix']}")
    body = "\n".join(lines)
    return (
        f"{body}\n\n"
        "  [Fix problem]   Type \"Fix problem\"   \u2014 apply repair, re-audit, promise clean\n"
        "  [Show diff]     Type \"Show diff\"     \u2014 show exact change before deciding\n\n"
        "After fix is applied and XFBA stamps clean, output: <promise>XFBA_CLEAN</promise>"
    )


def format_diff_view(repair) -> str:
    """State 2: show unified diff + Apply fix / I'll handle it options."""
    lines = ["Proposed fix:"]
    for item in repair:
        lines.append(f"\n  {item.get('file', '?')}:{item.get('line', '?')} \u2014 {item.get('description', '')}")
        for diff_line in (item.get('diff') or '').splitlines():
            lines.append(f"  {diff_line}")
    lines.append(
        "\n  [Apply fix]       Type \"Apply fix\"      \u2014 apply this, re-audit, promise clean"
        "\n  [I'll handle it]  Type \"I'll handle it\" \u2014 allow edit, log for manual review"
        "\n\nAfter fix is applied and XFBA stamps clean, output: <promise>XFBA_CLEAN</promise>"
    )
    return "\n".join(lines)


def append_repair_log(xf_dir: str, entry_or_violation, repair=None, accepted: bool = False) -> None:
    # New signature: append_repair_log(xf_dir, violation, repair, accepted=bool)
    #   -> writes repair_log.json as a flat JSON list so entries[-1] works
    # Legacy signature: append_repair_log(xf_dir, entry_dict)
    #   -> writes repair_log.json as {"repairs": [...]} so data["repairs"][0] works
    log_path = os.path.join(xf_dir, _REPAIR_LOG)

    if repair is not None:
        # New call: build entry from violation + repair + accepted
        violation = entry_or_violation
        entry: Dict[str, Any] = {
            "violation_id": violation.get("id", ""),
            "type": violation.get("type", ""),
            "caller_module": violation.get("caller_module", ""),
            "caller_line": violation.get("caller_line", 0),
            "symbol": violation.get("symbol", ""),
            "consequence": violation.get("consequence", ""),
            "fix": violation.get("fix", ""),
            "repair_description": repair.get("description", "") if isinstance(repair, dict) else "",
            "accepted": accepted,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
        # Read existing data; handle both list and dict formats
        try:
            existing = json.loads(open(log_path).read()) if os.path.isfile(log_path) else []
            if isinstance(existing, dict):
                # Was written by legacy path — migrate to list
                existing = existing.get("repairs", [])
        except Exception:
            existing = []
        existing.append(entry)
        tmp = log_path + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(existing, f, indent=2)
        os.replace(tmp, log_path)
    else:
        # Legacy call: entry_or_violation is already the full entry dict
        entry = dict(entry_or_violation)
        try:
            existing_raw = json.loads(open(log_path).read()) if os.path.isfile(log_path) else {"repairs": []}
            if isinstance(existing_raw, list):
                # Was written by new path -- migrate to dict format
                data = {"repairs": existing_raw}
            else:
                data = existing_raw
        except Exception:
            data = {"repairs": []}
        data["repairs"].append(entry)
        tmp = log_path + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)
        os.replace(tmp, log_path)
