# flow_analyzer.py
from __future__ import annotations

import hashlib
import json
import os
from typing import Dict, List, Any

from scanner_registry import scan_file


def _iter_source_files(root: str) -> List[str]:
    out: List[str] = []
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if d not in {
            ".git", ".worktrees", ".xf", ".venv", "venv", "__pycache__", "node_modules"
        }]
        for fn in filenames:
            if fn.endswith(".py") or fn.endswith(".sh") or fn.endswith(".ts") or fn.endswith(".tsx") or fn.endswith(".dart"):
                out.append(os.path.join(dirpath, fn))
    return out


def _compute_mtime_hash(file_paths: List[str]) -> str:
    """Quick fingerprint of all source file mtimes."""
    parts = []
    for p in sorted(file_paths):
        try:
            parts.append(f"{p}:{os.path.getmtime(p)}")
        except Exception:
            pass
    return hashlib.md5("\n".join(parts).encode()).hexdigest()


def build_index(root: str) -> Dict[str, Any]:
    file_paths = _iter_source_files(root)
    xf_dir = os.path.join(root, ".xf")
    cache_path = os.path.join(xf_dir, "index_cache.json")

    current_hash = _compute_mtime_hash(file_paths)

    # Try cache
    try:
        cached = json.loads(open(cache_path).read())
        if cached.get("mtime_hash") == current_hash:
            return cached["index"]
    except Exception:
        pass

    # Full scan
    modules: Dict[str, Any] = {}
    callers: List[Dict[str, Any]] = []
    from_imports: List[Dict[str, Any]] = []
    calls_by_file: Dict[str, List] = {}
    symbol_tables = []

    for path in file_paths:
        st = scan_file(path)
        if not st:
            continue
        symbol_tables.append(st)
        rel = os.path.relpath(path, root)
        # Fix 2: use path-based key (rel without extension) instead of bare module_name
        _EXT_STRIP = (".py", ".ts", ".tsx", ".dart")
        mod_key = next((rel[:-len(e)] for e in _EXT_STRIP if rel.endswith(e)), rel)
        modules[mod_key] = {
            "path": rel,
            "exports": sorted(set(st.exports)),
            "functions": st.functions,
            "imports": sorted(set(st.imports)),
            "state_writes": st.state_writes,
            "env_vars_read": st.env_vars_read,
            "env_vars_hard": st.env_vars_hard,
            "env_vars_soft": st.env_vars_soft,
        }

    # Fix 2: reverse lookup from basename → full path-based key
    basename_to_key = {os.path.splitext(os.path.basename(k))[0]: k for k in modules}

    for st in symbol_tables:
        rel = os.path.relpath(st.path, root)
        for imp in st.from_imports or []:
            mod = (imp.get("module") or "").split(".")[-1]
            name, line = imp.get("name"), imp.get("line") or 0
            if mod and name and name != "*":
                # Fix 2: resolve callee_module to path-based key
                callee_key = basename_to_key.get(mod, mod)
                from_imports.append({
                    "caller_module": rel, "caller_line": line,
                    "callee_module": callee_key, "symbol": name,
                })
        calls_by_file[rel] = st.calls

    export_to_module: Dict[str, str] = {}
    for m, info in modules.items():
        for sym in info.get("exports", []):
            export_to_module.setdefault(sym, m)

    for st in symbol_tables:
        for c in st.calls:
            if c.get("kind") != "name":
                continue
            sym = c.get("symbol")
            callee_module = export_to_module.get(sym) if sym else None
            if callee_module:
                callers.append({
                    "caller": os.path.relpath(st.path, root),
                    "callee_module": callee_module,
                    "symbol": sym, "line": c.get("line"),
                })

    result = {"modules": modules, "callers": callers,
              "from_imports": from_imports, "calls_by_file": calls_by_file}

    # Fix 10: write mtime cache
    try:
        os.makedirs(xf_dir, exist_ok=True)
        with open(cache_path, "w") as f:
            json.dump({"mtime_hash": current_hash, "index": result}, f)
    except Exception:
        pass

    return result
