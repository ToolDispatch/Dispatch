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


def format_consent_options(trust_level: int, n_violations: int) -> str:
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


def append_repair_log(xf_dir: str, entry: Dict[str, Any]) -> None:
    log_path = os.path.join(xf_dir, _REPAIR_LOG)
    try:
        data = json.loads(open(log_path).read()) if os.path.isfile(log_path) else {"repairs": []}
    except Exception:
        data = {"repairs": []}
    data["repairs"].append(entry)
    tmp = log_path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)
    os.replace(tmp, log_path)
