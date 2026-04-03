# refactor_mode.py
from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from typing import List, Dict, Any

from colors import XFA_CYAN, XFA_YELLOW, XFA_GRAY, XFA_RESET

_FLAG_FILE = "refactor_mode.json"
_ACCUM_FILE = "refactor_violations.json"
_AUTO_DETECT_THRESHOLD = 3


def _flag_path(xf_dir: str) -> str:
    return os.path.join(xf_dir, _FLAG_FILE)


def _accum_path(xf_dir: str) -> str:
    return os.path.join(xf_dir, _ACCUM_FILE)


def is_active(xf_dir: str) -> bool:
    return os.path.isfile(_flag_path(xf_dir))


def activate(xf_dir: str, description: str = "") -> None:
    data = {
        "active": True,
        "description": description,
        "started_at": datetime.now(timezone.utc).isoformat(),
    }
    with open(_flag_path(xf_dir), "w") as f:
        json.dump(data, f, indent=2)
    with open(_accum_path(xf_dir), "w") as f:
        json.dump({"violations": []}, f)


def deactivate(xf_dir: str) -> None:
    try:
        os.remove(_flag_path(xf_dir))
    except FileNotFoundError:
        pass


def get_description(xf_dir: str) -> str:
    try:
        return json.loads(open(_flag_path(xf_dir)).read()).get("description", "")
    except Exception:
        return ""


def add_violations(xf_dir: str, violations: List[Dict[str, Any]]) -> None:
    accum_path = _accum_path(xf_dir)
    try:
        data = json.loads(open(accum_path).read()) if os.path.isfile(accum_path) else {"violations": []}
    except Exception:
        data = {"violations": []}
    existing_ids = {v.get("id") for v in data["violations"]}
    for v in violations:
        if v.get("id") not in existing_ids:
            data["violations"].append(v)
            existing_ids.add(v.get("id"))
    tmp = accum_path + ".tmp"
    with open(tmp, "w") as f:
        json.dump(data, f, indent=2)
    os.replace(tmp, accum_path)


def get_accumulated(xf_dir: str) -> List[Dict[str, Any]]:
    try:
        return json.loads(open(_accum_path(xf_dir)).read()).get("violations", [])
    except Exception:
        return []


def format_status_line(n_open: int, description: str = "") -> str:
    desc_part = f" — {description}" if description else ""
    return (f"{XFA_CYAN}◈ XF Audit{XFA_RESET}  "
            f"{XFA_YELLOW}[refactor tracking]{XFA_RESET}  "
            f"{XFA_GRAY}{n_open} open contract(s){desc_part}{XFA_RESET}")


def format_refactor_suggestion(symbol: str) -> str:
    return (
        f"{XFA_CYAN}◈ XF Audit{XFA_RESET}  Looks like a refactor in progress on "
        f"{XFA_YELLOW}{symbol}{XFA_RESET} — want to switch to tracking mode?\n"
        f"  I'll hold violations until you're done and present them all at once.\n"
        f"  {XFA_YELLOW}[yes, tracking mode]{XFA_RESET}  "
        f"{XFA_GRAY}[no, keep blocking]{XFA_RESET}"
    )


def should_suggest_refactor_mode(recent_symbols: List[str]) -> bool:
    if len(recent_symbols) < _AUTO_DETECT_THRESHOLD:
        return False
    tail = recent_symbols[-_AUTO_DETECT_THRESHOLD:]
    return len(set(tail)) == 1


def format_consolidated_report(violations: List[Dict[str, Any]], description: str = "") -> str:
    if not violations:
        return (f"{XFA_CYAN}◈ XF Audit{XFA_RESET}  "
                f"\033[92mRefactor complete — all contracts intact.\033[0m")
    header = description or "refactor session"
    lines = [
        f"{XFA_CYAN}◈ XF Audit{XFA_RESET}  "
        f"Refactor complete — {len(violations)} contract(s) to repair ({header}):",
        "",
    ]
    for n, v in enumerate(violations, 1):
        mod = v.get("caller_module", "?")
        line = v.get("caller_line") or "?"
        consequence = v.get("consequence", "")
        fix = v.get("fix", "")
        lines.append(f"  {n}. {XFA_GRAY}{mod}:{line}{XFA_RESET}  {consequence}")
        if fix:
            lines.append(f"     {XFA_GRAY}Fix: {fix}{XFA_RESET}")
    return "\n".join(lines)
