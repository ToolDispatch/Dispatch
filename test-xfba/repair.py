# repair.py
from __future__ import annotations

import difflib
import os
from datetime import datetime, timezone
from typing import Dict, Any, List, Optional

from colors import XFA_CYAN, XFA_RED, XFA_YELLOW, XFA_GRAY, XFA_RESET


def build_repair_plan(violations: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Order violations for repair: errors first, then by file and line."""
    def sort_key(v):
        severity_order = {"error": 0, "warning": 1}
        return (
            severity_order.get(v.get("severity", "warning"), 1),
            v.get("caller_module", ""),
            v.get("caller_line", 0),
        )
    return sorted(violations, key=sort_key)


def format_repair_plan(plan: List[Dict[str, Any]]) -> str:
    """Format the ordered repair plan as consequence-first numbered list."""
    lines = [
        f"{XFA_CYAN}◈ XF Audit{XFA_RESET}  {XFA_RED}{len(plan)} contract(s) broken.{XFA_RESET}",
        "",
    ]
    for n, v in enumerate(plan, 1):
        mod = v.get("caller_module", "?")
        line = v.get("caller_line") or "?"
        consequence = v.get("consequence", "")
        fix = v.get("fix", "")
        sym = v.get("symbol", "")

        lines.append(f"  {XFA_GRAY}{n}. {mod}:{line}{XFA_RESET}"
                     + (f" — {XFA_YELLOW}{sym}(){XFA_RESET}" if sym else ""))
        lines.append(f"     {consequence}")
        if fix:
            lines.append(f"     {XFA_GRAY}Fix: {fix}{XFA_RESET}")
        lines.append("")
    return "\n".join(lines)


def generate_diff(file_path: str, original_line: int, original_text: str,
                  replacement_text: str) -> Optional[str]:
    """Generate a unified diff for a mechanical single-line fix."""
    try:
        lines = open(file_path, "r", encoding="utf-8").readlines()
    except Exception:
        return None

    idx = original_line - 1  # 0-based
    if idx < 0 or idx >= len(lines):
        return None
    if original_text.strip() not in lines[idx]:
        return None

    new_lines = lines[:]
    new_lines[idx] = lines[idx].replace(original_text.strip(), replacement_text.strip(), 1)

    diff = list(difflib.unified_diff(
        lines, new_lines,
        fromfile=f"a/{os.path.basename(file_path)}",
        tofile=f"b/{os.path.basename(file_path)}",
        lineterm="",
    ))
    return "\n".join(diff) if diff else None


def make_repair_log_entry(violation_id: str, violation_type: str, symbol: str,
                          description: str, session_id: str) -> Dict[str, Any]:
    """Create a provenance record for a completed repair."""
    return {
        "violation_id": violation_id,
        "violation_type": violation_type,
        "symbol": symbol,
        "description": description,
        "session_id": session_id,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }
