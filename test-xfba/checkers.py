# checkers.py
from __future__ import annotations

import ast
import os
import py_compile
from typing import Dict, Any, List, Optional


# ---------- syntax_violations ----------

def syntax_violations(py_paths: List[str]) -> List[Dict[str, Any]]:
    violations = []
    for vid, path in enumerate(py_paths, 1):
        try:
            py_compile.compile(path, doraise=True)
        except py_compile.PyCompileError as e:
            line = None
            try:
                if hasattr(e, "exc_value") and hasattr(e.exc_value, "lineno"):
                    line = e.exc_value.lineno
            except Exception:
                pass
            violations.append({
                "id": f"s{vid:03d}", "type": "syntax_error", "severity": "error",
                "path": path, "caller_module": path, "caller_line": line or 0,
                "consequence": "This file will not parse. Nothing in it will run.",
                "fix": f"Fix the syntax error at line {line}." if line else "Fix the syntax error.",
                "detail": str(e).strip(), "status": "open",
            })
    return violations


# ---------- from_import_violations ----------

def from_import_violations(index: Dict[str, Any]) -> List[Dict[str, Any]]:
    modules = index.get("modules", {})
    exports_by_module = {m: set(info.get("exports", [])) for m, info in modules.items()}
    violations = []
    for vid, edge in enumerate(index.get("from_imports", []), 1):
        callee, sym = edge.get("callee_module"), edge.get("symbol")
        if not callee or not sym or callee not in exports_by_module:
            continue
        if sym in exports_by_module[callee]:
            continue
        violations.append({
            "id": f"i{vid:03d}", "type": "interface_existence", "severity": "error",
            "caller_module": edge.get("caller_module"),
            "caller_line": edge.get("caller_line") or 0,
            "callee_module": callee, "symbol": sym,
            "consequence": f"This import will fail when the module loads — '{sym}' does not exist in {callee}.",
            "fix": f"Check if '{sym}' was renamed or moved in {callee}.",
            "status": "open",
        })
    return violations


# ---------- arity_violations ----------

def arity_violations(index: Dict[str, Any]) -> List[Dict[str, Any]]:
    func_map: Dict[str, Dict] = {}
    for mod_name, mod_info in index.get("modules", {}).items():
        for fn_name, fn_sig in mod_info.get("functions", {}).items():
            func_map[fn_name] = {**fn_sig, "defined_in": mod_info.get("path", mod_name)}

    violations = []
    vid = 1
    for caller_path, calls in index.get("calls_by_file", {}).items():
        for call in calls:
            sym, kind = call.get("symbol"), call.get("kind")
            line = call.get("line") or 0
            # Total args = positional + named kwargs (both count toward required-arg check)
            n_args = call.get("n_args", 0) + call.get("n_kwargs", 0)
            if kind != "name" or not sym or sym not in func_map:
                continue
            # Skip arity check when *args or **kwargs splats are present — count is unknowable
            if call.get("has_star_args") or call.get("has_kwargs_unpack"):
                continue
            fn = func_map[sym]
            if fn.get("has_varargs"):
                continue
            n_total = fn.get("n_total", 0)
            if n_args > n_total:
                excess = n_args - n_total
                violations.append({
                    "id": f"a{vid:03d}", "type": "arity_mismatch", "severity": "error",
                    "caller_module": caller_path, "caller_line": line,
                    "symbol": sym, "n_args_passed": n_args, "n_args_accepted": n_total,
                    "defined_in": fn["defined_in"], "defined_line": fn.get("line"),
                    "consequence": (f"This will throw a TypeError when {sym}() runs — "
                                    f"called with {n_args} arguments but it only accepts {n_total}."),
                    "fix": (f"{caller_path}:{line} — remove {excess} argument(s) from the call to {sym}()"),
                    "status": "open",
                })
                vid += 1
            elif n_args < fn.get("n_required", 0):
                deficit = fn.get("n_required", 0) - n_args
                violations.append({
                    "id": f"a{vid:03d}", "type": "arity_mismatch", "severity": "error",
                    "caller_module": caller_path, "caller_line": line,
                    "symbol": sym, "n_args_passed": n_args, "n_args_accepted": fn.get("n_required", 0),
                    "defined_in": fn["defined_in"], "defined_line": fn.get("line"),
                    "consequence": (f"This will throw a TypeError when {sym}() runs — "
                                    f"called with {n_args} arguments but it requires at least {fn.get('n_required', 0)}."),
                    "fix": (f"{caller_path}:{line} — add {deficit} required argument(s) to the call to {sym}()"),
                    "status": "open",
                })
                vid += 1
    return violations


# ---------- env_var_violations ----------

def _load_dotenv(root: str) -> set:
    defined: set = set()
    env_path = os.path.join(root, ".env")
    if not os.path.isfile(env_path):
        return defined
    try:
        for line in open(env_path, "r", encoding="utf-8"):
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                defined.add(line.split("=", 1)[0].strip())
    except Exception:
        pass
    return defined


def env_var_violations(index: Dict[str, Any], root: str) -> List[Dict[str, Any]]:
    defined = _load_dotenv(root)
    env_exists = os.path.isfile(os.path.join(root, ".env"))
    violations = []
    vid = 1
    for mod_name, mod_info in index.get("modules", {}).items():
        path = mod_info.get("path", mod_name)
        for access in mod_info.get("env_vars_hard", []):
            var_name, line = access.get("var_name"), access.get("line") or 0
            if not var_name or var_name in defined:
                continue
            consequence = (
                f"This will throw a KeyError when the code runs — {var_name} is not defined in .env."
                if env_exists else
                f"No .env file found — {var_name} will throw a KeyError unless the environment provides it."
            )
            violations.append({
                "id": f"e{vid:03d}", "type": "missing_env_var",
                "severity": "error" if env_exists else "warning",
                "caller_module": path, "caller_line": line, "var_name": var_name,
                "consequence": consequence,
                "fix": f"Add {var_name}=<value> to .env, or switch to os.getenv('{var_name}', default)",
                "status": "open",
            })
            vid += 1
    return violations


# ---------- stub_violations ----------

def stub_violations(index: Dict[str, Any]) -> List[Dict[str, Any]]:
    called_symbols: set = {e.get("symbol") for e in index.get("callers", []) if e.get("symbol")}
    violations = []
    vid = 1
    for mod_name, mod_info in index.get("modules", {}).items():
        path = mod_info.get("path", mod_name)
        for fn_name, fn_sig in mod_info.get("functions", {}).items():
            if not fn_sig.get("is_stub"):
                continue
            ret = fn_sig.get("return_annotation")
            is_non_none = ret is not None and ret not in ("None", "NoReturn")
            has_callers = fn_name in called_symbols
            line = fn_sig.get("line") or 0
            if is_non_none and has_callers:
                severity, consequence, fix = (
                    "error",
                    f"{fn_name}() is a stub promising to return {ret} — callers will receive None and likely fail silently.",
                    f"Implement {fn_name}() or change return annotation to -> None",
                )
            elif is_non_none:
                severity, consequence, fix = (
                    "warning",
                    f"{fn_name}() is a stub promising to return {ret} but returns None. No callers detected yet.",
                    f"Implement {fn_name}() or change return annotation to -> None",
                )
            else:
                severity, consequence, fix = (
                    "warning",
                    f"{fn_name}() is unimplemented (stub body). It will silently do nothing when called.",
                    f"Implement {fn_name}() or raise NotImplementedError",
                )
            violations.append({
                "id": f"b{vid:03d}", "type": "stub_function", "severity": severity,
                "caller_module": path, "caller_line": line, "symbol": fn_name,
                "return_annotation": ret, "has_callers": has_callers,
                "consequence": consequence, "fix": fix, "status": "open",
            })
            vid += 1
    return violations


# ---------- silent_except_violations ----------

def _handler_has_propagation(body: list) -> bool:
    """True if the handler body contains raise or sys.exit() — i.e. not silently swallowed."""
    for stmt in body:
        for node in ast.walk(stmt):
            if isinstance(node, ast.Raise):
                return True
            if (isinstance(node, ast.Call) and
                    isinstance(node.func, ast.Attribute) and
                    node.func.attr == "exit" and
                    isinstance(node.func.value, ast.Name) and
                    node.func.value.id == "sys"):
                return True
    return False


def silent_except_violations(py_paths: List[str]) -> List[Dict[str, Any]]:
    """Warn on except blocks that swallow exceptions without re-raising or exiting.

    Suppress a specific handler by adding  # xfa: ignore  on the except line.
    Example:
        except Exception:  # xfa: ignore
    """
    violations = []
    vid = 1
    for path in py_paths:
        try:
            with open(path, "r", encoding="utf-8") as f:
                source = f.read()
            tree = ast.parse(source, filename=path)
        except Exception:
            continue
        source_lines = source.splitlines()
        for node in ast.walk(tree):
            if not isinstance(node, ast.ExceptHandler):
                continue
            if _handler_has_propagation(node.body):
                continue
            # Respect inline suppression comment
            try:
                except_line = source_lines[node.lineno - 1]
                if "# xfa: ignore" in except_line:
                    continue
            except (IndexError, TypeError):
                pass
            body_types = [type(s).__name__ for s in node.body]
            if all(t == "Pass" for t in body_types):
                detail = "except block is empty (pass only)"
            else:
                detail = "exception is caught but not re-raised or exited — failure will be invisible"
            exc_type = ""
            if node.type:
                if isinstance(node.type, ast.Name):
                    exc_type = node.type.id
                elif isinstance(node.type, ast.Tuple):
                    exc_type = ", ".join(
                        n.id for n in node.type.elts if isinstance(n, ast.Name)
                    )
            violations.append({
                "id": f"x{vid:03d}",
                "type": "silent_exception",
                "severity": "warning",
                "caller_module": path,
                "caller_line": node.lineno,
                "symbol": exc_type or "Exception",
                "consequence": f"If this block catches a real error, the failure will be invisible — {detail}.",
                "fix": "Add raise, sys.exit(1), or logging.exception() to propagate the failure.",
                "status": "open",
            })
            vid += 1
    return violations
