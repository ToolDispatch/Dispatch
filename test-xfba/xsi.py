# xsi.py — XF System Impact Inspector
# Categorical impact rules against the XFA index + proposed change.
# Non-blocking: always returns concerns list, never exits.
# Called from auditor.py Stage 5 (Pro only).
from __future__ import annotations

import ast
import os
import re
from typing import Dict, Any, List, Optional


# ── AST helpers ──────────────────────────────────────────────────────────────

def _parse_safe(content: str, path: str = "<unknown>") -> Optional[ast.Module]:
    try:
        return ast.parse(content, filename=path)
    except SyntaxError:
        return None


def _get_imports(tree: ast.Module) -> set:
    """Return set of top-level module names imported."""
    names = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                names.add(alias.name.split(".")[0])
        elif isinstance(node, ast.ImportFrom):
            if node.module:
                names.add(node.module.split(".")[0])
    return names


def _get_functions(tree: ast.Module) -> set:
    """Return set of function names defined at module level."""
    return {
        node.name
        for node in ast.walk(tree)
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
    }


def _get_env_vars(tree: ast.Module) -> set:
    """Return set of env var names accessed (both hard and soft)."""
    names = set()
    for node in ast.walk(tree):
        # os.environ["X"] or os.environ.get("X")
        if isinstance(node, ast.Subscript):
            if (isinstance(node.value, ast.Attribute) and
                    node.value.attr == "environ" and
                    isinstance(node.value.value, ast.Name) and
                    node.value.value.id == "os"):
                key = node.slice
                if isinstance(key, ast.Constant) and isinstance(key.value, str):
                    names.add(key.value)
        # os.getenv("X"), os.environ.get("X")
        if isinstance(node, ast.Call):
            fn = node.func
            if (isinstance(fn, ast.Attribute) and fn.attr in ("getenv", "get") and
                    node.args and isinstance(node.args[0], ast.Constant)):
                names.add(node.args[0].value)
    return names


def _get_except_handlers(tree: ast.Module) -> List[Dict]:
    """Return list of {line, exc_type} for except handlers."""
    handlers = []
    for node in ast.walk(tree):
        if isinstance(node, ast.ExceptHandler):
            exc = ""
            if node.type:
                if isinstance(node.type, ast.Name):
                    exc = node.type.id
                elif isinstance(node.type, ast.Attribute):
                    exc = f"{node.type.value.id}.{node.type.attr}" if isinstance(node.type.value, ast.Name) else ""
            handlers.append({"line": node.lineno, "exc_type": exc or "bare"})
    return handlers


_SIDE_EFFECT_PATTERNS = [
    # subprocess calls
    (re.compile(r"\bsubprocess\s*\.\s*(run|Popen|call|check_output|check_call)\b"), "subprocess call"),
    # file writes
    (re.compile(r'\bopen\s*\([^)]*["\']w["\']'), "file write (open w)"),
    (re.compile(r'\bopen\s*\([^)]*["\']a["\']'), "file write (open a)"),
    # DB mutations
    (re.compile(r"\b(INSERT|UPDATE|DELETE|DROP|TRUNCATE|ALTER)\s+", re.IGNORECASE), "DB mutation"),
    # os.remove / os.replace / shutil
    (re.compile(r"\bos\s*\.\s*(remove|replace|unlink|rename)\b"), "file mutation (os)"),
]


def _get_side_effects(content: str) -> set:
    """Return set of side-effect labels found in content."""
    found = set()
    for pattern, label in _SIDE_EFFECT_PATTERNS:
        if pattern.search(content):
            found.add(label)
    return found


# ── Rules ────────────────────────────────────────────────────────────────────

def _rule_callers(index: Dict, proposed_file: str, proposed_tree: Optional[ast.Module],
                  root: str) -> List[Dict]:
    """CALLERS — a function in proposed_file has ≥2 callers in the index."""
    if not proposed_tree:
        return []
    defined_fns = _get_functions(proposed_tree)
    callers_map: Dict[str, List[str]] = {}
    for edge in index.get("callers", []):
        sym = edge.get("symbol")
        caller = edge.get("caller", "")
        if sym in defined_fns:
            callers_map.setdefault(sym, [])
            if caller not in callers_map[sym]:
                callers_map[sym].append(caller)

    concerns = []
    for fn, callers in callers_map.items():
        if len(callers) >= 2:
            concerns.append({
                "dimension": "CALLERS",
                "detail": f"{fn} — {len(callers)} caller(s) in index will be affected",
                "symbol": fn,
            })
    return concerns[:3]  # cap at 3 per dimension


def _rule_data_flow(current_content: Optional[str], proposed_content: str,
                    current_tree: Optional[ast.Module],
                    proposed_tree: Optional[ast.Module]) -> List[Dict]:
    """DATA FLOW — env vars added, removed, or changed between current and proposed."""
    if not proposed_tree:
        return []
    proposed_vars = _get_env_vars(proposed_tree)
    current_vars = _get_env_vars(current_tree) if current_tree else set()

    added   = proposed_vars - current_vars
    removed = current_vars - proposed_vars
    concerns = []
    for v in sorted(added):
        concerns.append({"dimension": "DATA FLOW", "detail": f"env var {v} added", "symbol": v})
    for v in sorted(removed):
        concerns.append({"dimension": "DATA FLOW", "detail": f"env var {v} removed", "symbol": v})
    return concerns[:3]


def _rule_callees(index: Dict, proposed_file: str,
                  current_tree: Optional[ast.Module],
                  proposed_tree: Optional[ast.Module]) -> List[Dict]:
    """CALLEES — import added/removed that references a shared module in the index."""
    if not proposed_tree:
        return []
    known_modules = {
        os.path.splitext(os.path.basename(info.get("path", "")))[0]
        for info in index.get("modules", {}).values()
    }
    proposed_imports = _get_imports(proposed_tree)
    current_imports  = _get_imports(current_tree) if current_tree else set()

    added   = (proposed_imports - current_imports) & known_modules
    removed = (current_imports - proposed_imports) & known_modules
    concerns = []
    for m in sorted(added):
        concerns.append({"dimension": "CALLEES", "detail": f"import {m} added (shared module)", "symbol": m})
    for m in sorted(removed):
        concerns.append({"dimension": "CALLEES", "detail": f"import {m} removed (shared module)", "symbol": m})
    return concerns[:3]


def _rule_side_effects(current_content: Optional[str], proposed_content: str) -> List[Dict]:
    """SIDE EFFECTS — file writes, subprocess calls, DB mutations added."""
    proposed_se = _get_side_effects(proposed_content)
    current_se  = _get_side_effects(current_content) if current_content else set()
    added = proposed_se - current_se
    return [
        {"dimension": "SIDE EFFECTS", "detail": f"{label} added", "symbol": label}
        for label in sorted(added)
    ][:3]


def _rule_state(index: Dict, proposed_file: str, root: str) -> List[Dict]:
    """STATE — proposed_file is written to by ≥2 distinct modules in the index."""
    rel_proposed = os.path.relpath(proposed_file, root) if os.path.isabs(proposed_file) else proposed_file
    basename = os.path.basename(rel_proposed)

    # Look for other modules that import or call symbols from this file
    writers = set()
    for edge in index.get("from_imports", []):
        callee = edge.get("callee_module", "")
        caller = edge.get("caller_module", "")
        if callee and (callee.endswith(rel_proposed) or os.path.basename(callee) == os.path.splitext(basename)[0]):
            if caller:
                writers.add(os.path.basename(caller))

    # Also check callers list
    for edge in index.get("callers", []):
        callee_mod = edge.get("callee_module", "")
        caller = edge.get("caller", "")
        if callee_mod and (callee_mod.endswith(rel_proposed) or
                           os.path.basename(callee_mod) == os.path.splitext(basename)[0]):
            if caller:
                writers.add(os.path.basename(caller))

    if len(writers) >= 2:
        sample = sorted(writers)[:3]
        return [{
            "dimension": "STATE",
            "detail": f"{basename} depended on by {len(writers)} modules ({', '.join(sample)}{'...' if len(writers) > 3 else ''})",
            "symbol": basename,
        }]
    return []


def _rule_error_path(current_content: Optional[str], proposed_content: str,
                     current_tree: Optional[ast.Module],
                     proposed_tree: Optional[ast.Module]) -> List[Dict]:
    """ERROR PATH — bare except added, or existing error handler removed."""
    if not proposed_tree:
        return []
    proposed_handlers = _get_except_handlers(proposed_tree)
    current_handlers  = _get_except_handlers(current_tree) if current_tree else []

    proposed_bare = sum(1 for h in proposed_handlers if h["exc_type"] in ("bare", "Exception"))
    current_bare  = sum(1 for h in current_handlers  if h["exc_type"] in ("bare", "Exception"))
    current_total = len(current_handlers)
    proposed_total = len(proposed_handlers)

    concerns = []
    if proposed_bare > current_bare:
        concerns.append({
            "dimension": "ERROR PATH",
            "detail": f"{proposed_bare - current_bare} broad except handler(s) added — failures may be silently swallowed",
            "symbol": "except",
        })
    if proposed_total < current_total:
        removed = current_total - proposed_total
        concerns.append({
            "dimension": "ERROR PATH",
            "detail": f"{removed} error handler(s) removed — previously caught failures now propagate uncaught",
            "symbol": "except",
        })
    return concerns[:2]


# ── Public API ───────────────────────────────────────────────────────────────

def analyze(index: Dict[str, Any], proposed_file: str, proposed_content: str,
            current_content: Optional[str], root: str) -> List[Dict]:
    """Run all 6 XSI categorical rules. Returns list of concern dicts.

    Each concern: {"dimension": str, "detail": str, "symbol": str}
    Empty list = no concerns (clean).
    """
    concerns: List[Dict] = []
    try:
        proposed_tree = _parse_safe(proposed_content, proposed_file)
        current_tree  = _parse_safe(current_content, proposed_file) if current_content else None

        concerns += _rule_callers(index, proposed_file, proposed_tree, root)
        concerns += _rule_data_flow(current_content, proposed_content, current_tree, proposed_tree)
        concerns += _rule_callees(index, proposed_file, current_tree, proposed_tree)
        concerns += _rule_side_effects(current_content, proposed_content)
        concerns += _rule_state(index, proposed_file, root)
        concerns += _rule_error_path(current_content, proposed_content, current_tree, proposed_tree)
    except Exception:
        pass  # XSI must never crash auditor.py
    return concerns
