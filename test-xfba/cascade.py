# cascade.py
from __future__ import annotations

from collections import deque
from typing import Dict, Any, List

from colors import XFA_CYAN, XFA_YELLOW, XFA_GRAY, XFA_RESET


def trace_cascade(index: Dict[str, Any], changed_symbol: str) -> List[Dict[str, Any]]:
    """BFS over the call graph to find all callers of changed_symbol, ordered by depth.

    Returns list of {caller, symbol, line, depth, consequence, root_symbol} dicts.
    """
    callers_index: Dict[str, List[Dict]] = {}
    for edge in index.get("callers", []):
        sym = edge.get("symbol")
        if sym:
            callers_index.setdefault(sym, []).append(edge)

    result: List[Dict[str, Any]] = []
    visited: set = set()
    queue: deque = deque()

    # Seed with direct callers of changed_symbol
    for edge in callers_index.get(changed_symbol, []):
        key = (edge["caller"], edge.get("line"))
        if key not in visited:
            visited.add(key)
            item = {**edge, "depth": 1, "root_symbol": changed_symbol}
            item["consequence"] = _consequence_for(edge, changed_symbol, depth=1)
            queue.append(item)
            result.append(item)

    # BFS: for each caller module, find symbols it exports that are called by others
    while queue:
        current = queue.popleft()
        # Fix 2: use path-based key (strip .py, keep full relative path)
        caller_module_key = _path_to_module_name(current["caller"])
        mod_info = index.get("modules", {}).get(caller_module_key, {})
        for exported_sym in mod_info.get("exports", []):
            for edge in callers_index.get(exported_sym, []):
                key = (edge["caller"], edge.get("line"))
                if key not in visited:
                    visited.add(key)
                    depth = current["depth"] + 1
                    item = {**edge, "depth": depth, "root_symbol": changed_symbol}
                    item["consequence"] = _consequence_for(edge, exported_sym, depth=depth)
                    queue.append(item)
                    result.append(item)

    return result


def _path_to_module_name(path: str) -> str:
    """Convert relative file path to path-based module key (strip .py only)."""
    # Fix 2: strip .py from full relative path, don't reduce to last segment
    if path.endswith(".py"):
        return path[:-3]
    return path


def _consequence_for(edge: Dict, symbol: str, depth: int) -> str:
    caller = edge.get("caller", "unknown")
    line = edge.get("line") or "?"
    if depth == 1:
        return (f"{caller}:{line} calls {symbol}() directly — "
                f"this will break when the contract changes.")
    return (f"{caller}:{line} calls {symbol}() transitively (depth {depth}) — "
            f"may fail silently or throw depending on return value propagation.")


def format_cascade_notification(symbol: str, n_callers: int) -> str:
    """500ms notification fired when Stage 2 begins (before cascade completes)."""
    return (f"{XFA_CYAN}◈ XF Audit{XFA_RESET}  "
            f"Contract change detected on {XFA_YELLOW}{symbol}{XFA_RESET} — "
            f"mapping {n_callers} caller(s)...")


def format_cascade_report(symbol: str, cascade: List[Dict[str, Any]]) -> str:
    """Format the full cascade for Stage 2 output."""
    if not cascade:
        return (f"{XFA_CYAN}◈ XF Audit{XFA_RESET}  "
                f"No callers of {XFA_YELLOW}{symbol}{XFA_RESET} found in this repo.")
    lines = [
        f"{XFA_CYAN}◈ XF Audit{XFA_RESET}  Stage 2: Caller cascade for {XFA_YELLOW}{symbol}{XFA_RESET}",
        f"{XFA_GRAY}  {len(cascade)} caller(s) affected — fix root first, others may resolve:{XFA_RESET}",
        "",
    ]
    for item in cascade:
        depth_indent = "  " * item.get("depth", 1)
        caller = item.get("caller", "?")
        line = item.get("line") or "?"
        consequence = item.get("consequence", "")
        lines.append(f"{depth_indent}{XFA_GRAY}{caller}:{line}{XFA_RESET}")
        lines.append(f"{depth_indent}  {consequence}")
    return "\n".join(lines)
