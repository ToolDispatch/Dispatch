# XF Audit — Stage 1 New Checks Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Extend XF Audit's Stage 1 AST scan to check syntax errors, arity mismatches, hard env var access, and stub detection — so the auditor catches the most common runtime failures at the edit boundary.

**Architecture:** All new checks run in Stage 1 (pure AST, zero API cost, ~200ms target). They extend the existing `scanner_python.py` → `flow_analyzer.py` → `auditor.py` pipeline. A new `checkers.py` module holds each check as an isolated function. `SymbolTable` gets new fields for function signatures and env var access patterns. `auditor.py` calls all checks in sequence and formats violation output using consequence-first language.

**Tech Stack:** Python 3.8+, `ast`, `py_compile`, standard library only. All files in `~/.claude/xf-boundary-auditor/`. Tests run with `pytest`.

**Working directory for all steps:** `/home/visionairy/.claude/xf-boundary-auditor/`

**Spec reference:** `/home/visionairy/Dispatch/docs/superpowers/specs/2026-03-28-xfa-contract-loop-design.md`

---

## File Structure

| File | Action | Purpose |
|------|--------|---------|
| `scanner_base.py` | Modify | Add `functions`, `env_vars_hard`, `env_vars_soft` fields to `SymbolTable`; extend call dict shape |
| `scanner_python.py` | Modify | Populate new fields: function signatures, stub detection, env var access |
| `checkers.py` | Create | Stage 1 check functions: syntax, arity, env vars, stubs |
| `flow_analyzer.py` | Modify | Thread new fields through `build_index()` output |
| `auditor.py` | Modify | Call new checks, add consequence-first formatting for each violation type |
| `tests/test_stage1_checks.py` | Create | Full test suite for all four new checks |

---

## Task 1: Extend SymbolTable for new data

**Files:**
- Modify: `scanner_base.py`

- [ ] **Step 1: Write failing test**

```python
# Create tests/test_stage1_checks.py
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from scanner_base import SymbolTable

def test_symboltable_has_functions_field():
    st = SymbolTable(module_name="x", path="x.py")
    assert hasattr(st, "functions")
    assert isinstance(st.functions, dict)

def test_symboltable_has_env_var_fields():
    st = SymbolTable(module_name="x", path="x.py")
    assert hasattr(st, "env_vars_hard")
    assert hasattr(st, "env_vars_soft")
    assert isinstance(st.env_vars_hard, list)
    assert isinstance(st.env_vars_soft, list)
```

- [ ] **Step 2: Run test to verify it fails**

```bash
cd /home/visionairy/.claude/xf-boundary-auditor
mkdir -p tests
python3 -m pytest tests/test_stage1_checks.py::test_symboltable_has_functions_field -v
```
Expected: `AttributeError` or `FAILED`

- [ ] **Step 3: Extend SymbolTable**

In `scanner_base.py`, add three new fields to the `SymbolTable` dataclass after `env_vars_read`:

```python
    # function signatures: {name: {n_required, n_total, has_varargs, has_varkw,
    #                               return_annotation, is_stub, line}}
    functions: Dict[str, Dict] = field(default_factory=dict)
    # env var accesses split by safety: [{var_name, line}]
    env_vars_hard: List[Dict] = field(default_factory=list)  # os.environ["KEY"] — throws on missing
    env_vars_soft: List[Dict] = field(default_factory=list)  # os.getenv("K", default) — safe
```

Full updated `scanner_base.py`:

```python
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import List, Optional, Dict, Any


@dataclass
class SymbolTable:
    module_name: str
    path: str
    exports: List[str] = field(default_factory=list)
    imports: List[str] = field(default_factory=list)
    imported_symbols: List[str] = field(default_factory=list)
    calls: List[Dict[str, Any]] = field(default_factory=list)  # {symbol, line, kind, n_args, n_kwargs}
    from_imports: List[Dict[str, Any]] = field(default_factory=list)
    state_writes: List[str] = field(default_factory=list)
    state_reads: List[str] = field(default_factory=list)
    env_vars_read: List[str] = field(default_factory=list)
    # New Stage 1 fields
    functions: Dict[str, Dict] = field(default_factory=dict)
    env_vars_hard: List[Dict] = field(default_factory=list)
    env_vars_soft: List[Dict] = field(default_factory=list)


class ScannerBase(ABC):
    @abstractmethod
    def supports(self, path: str) -> bool:
        ...

    @abstractmethod
    def scan(self, path: str) -> Optional[SymbolTable]:
        ...
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
python3 -m pytest tests/test_stage1_checks.py::test_symboltable_has_functions_field tests/test_stage1_checks.py::test_symboltable_has_env_var_fields -v
```
Expected: `PASSED`

- [ ] **Step 5: Commit**

```bash
git -C /home/visionairy/.claude/xf-boundary-auditor add scanner_base.py tests/test_stage1_checks.py
git -C /home/visionairy/.claude/xf-boundary-auditor commit -m "feat(xfa): extend SymbolTable with functions + env_vars_hard/soft fields"
```

---

## Task 2: Extract function signatures + env var access in PythonScanner

**Files:**
- Modify: `scanner_python.py`

- [ ] **Step 1: Write failing tests**

Append to `tests/test_stage1_checks.py`:

```python
import textwrap, tempfile, os

def _scan_src(src):
    from scanner_python import PythonScanner
    with tempfile.NamedTemporaryFile(suffix=".py", mode="w", delete=False) as f:
        f.write(textwrap.dedent(src))
        path = f.name
    try:
        return PythonScanner().scan(path)
    finally:
        os.unlink(path)

def test_scanner_extracts_function_signature():
    st = _scan_src("""
        def add(a, b):
            return a + b
    """)
    assert "add" in st.functions
    fn = st.functions["add"]
    assert fn["n_required"] == 2
    assert fn["n_total"] == 2
    assert fn["has_varargs"] is False
    assert fn["is_stub"] is False

def test_scanner_detects_stub_with_non_none_return():
    st = _scan_src("""
        def get_name() -> str:
            pass
    """)
    fn = st.functions["get_name"]
    assert fn["is_stub"] is True
    assert fn["return_annotation"] == "str"

def test_scanner_detects_void_stub():
    st = _scan_src("""
        def setup():
            pass
    """)
    fn = st.functions["setup"]
    assert fn["is_stub"] is True
    assert fn["return_annotation"] is None

def test_scanner_captures_hard_env_var():
    st = _scan_src("""
        import os
        key = os.environ["MY_KEY"]
    """)
    assert any(e["var_name"] == "MY_KEY" for e in st.env_vars_hard)

def test_scanner_captures_soft_env_var():
    st = _scan_src("""
        import os
        key = os.getenv("MY_KEY", "default")
    """)
    assert any(e["var_name"] == "MY_KEY" for e in st.env_vars_soft)

def test_scanner_call_includes_n_args():
    st = _scan_src("""
        result = my_func(1, 2, 3)
    """)
    call = next((c for c in st.calls if c["symbol"] == "my_func"), None)
    assert call is not None
    assert call["n_args"] == 3
```

- [ ] **Step 2: Run to verify failures**

```bash
python3 -m pytest tests/test_stage1_checks.py -k "signature or stub or env_var or n_args" -v 2>&1 | tail -20
```
Expected: all FAILED

- [ ] **Step 3: Implement in PythonScanner**

Replace `scanner_python.py` with:

```python
from __future__ import annotations

import ast
import os
from typing import Optional, List, Dict, Any

from scanner_base import ScannerBase, SymbolTable


def _is_stub_body(body: list) -> bool:
    """A stub has a body that does nothing: pass, ..., or docstring-only."""
    if not body:
        return True
    # single statement: pass or ellipsis or docstring
    if len(body) == 1:
        node = body[0]
        if isinstance(node, ast.Pass):
            return True
        if isinstance(node, ast.Expr) and isinstance(node.value, ast.Constant):
            # could be "..." or a docstring string — both count
            return True
    # docstring + pass/ellipsis
    if len(body) == 2:
        first, second = body
        if (isinstance(first, ast.Expr) and isinstance(first.value, ast.Constant)
                and isinstance(second, (ast.Pass, ast.Expr))):
            if isinstance(second, ast.Expr) and isinstance(second.value, ast.Constant):
                return True
            if isinstance(second, ast.Pass):
                return True
    return False


def _annotation_name(annotation) -> Optional[str]:
    """Extract annotation as a simple string, or None if absent."""
    if annotation is None:
        return None
    if isinstance(annotation, ast.Constant):
        return str(annotation.value)
    if isinstance(annotation, ast.Name):
        return annotation.id
    if isinstance(annotation, ast.Attribute):
        return annotation.attr
    # e.g. Optional[str] → just record the outer name
    if isinstance(annotation, ast.Subscript):
        return _annotation_name(annotation.value)
    return None


def _is_non_none_return(annotation_name: Optional[str]) -> bool:
    """True if annotation clearly promises a non-None return type."""
    if annotation_name is None:
        return False
    return annotation_name not in ("None", "NoReturn")


class _CallCollector(ast.NodeVisitor):
    def __init__(self):
        self.calls: List[Dict[str, Any]] = []

    def visit_Call(self, node: ast.Call):
        n_args = len(node.args)
        n_kwargs = len(node.keywords)
        if isinstance(node.func, ast.Name):
            self.calls.append({
                "symbol": node.func.id,
                "line": getattr(node, "lineno", None),
                "kind": "name",
                "n_args": n_args,
                "n_kwargs": n_kwargs,
            })
        elif isinstance(node.func, ast.Attribute):
            self.calls.append({
                "symbol": node.func.attr,
                "line": getattr(node, "lineno", None),
                "kind": "attr",
                "n_args": n_args,
                "n_kwargs": n_kwargs,
            })
        self.generic_visit(node)


class _EnvVarCollector(ast.NodeVisitor):
    """Collects os.environ["KEY"] (hard) and os.getenv("KEY", ...) (soft)."""

    def __init__(self):
        self.hard: List[Dict] = []
        self.soft: List[Dict] = []

    def visit_Subscript(self, node: ast.Subscript):
        # os.environ["KEY"]
        if (isinstance(node.value, ast.Attribute)
                and node.value.attr == "environ"
                and isinstance(node.value.value, ast.Name)
                and node.value.value.id == "os"):
            key = self._extract_string_key(node.slice)
            if key:
                self.hard.append({"var_name": key, "line": getattr(node, "lineno", None)})
        self.generic_visit(node)

    def visit_Call(self, node: ast.Call):
        # os.environ.get("KEY") without default → hard
        # os.environ.get("KEY", default) → soft
        # os.getenv("KEY") without default → hard
        # os.getenv("KEY", default) → soft
        if isinstance(node.func, ast.Attribute):
            attr = node.func.attr
            val = node.func.value
            is_environ_get = (
                attr == "get"
                and isinstance(val, ast.Attribute)
                and val.attr == "environ"
                and isinstance(val.value, ast.Name)
                and val.value.id == "os"
            )
            is_getenv = (
                attr == "getenv"
                and isinstance(val, ast.Name)
                and val.id == "os"
            )
            if is_environ_get or is_getenv:
                if node.args:
                    key = self._extract_string_key(node.args[0])
                    if key:
                        has_default = len(node.args) > 1 or any(
                            kw.arg == "default" for kw in node.keywords
                        )
                        entry = {"var_name": key, "line": getattr(node, "lineno", None)}
                        if has_default:
                            self.soft.append(entry)
                        else:
                            self.hard.append(entry)
        self.generic_visit(node)

    @staticmethod
    def _extract_string_key(node) -> Optional[str]:
        # ast.Index wrapper in Python 3.8
        if hasattr(node, "value") and isinstance(node, ast.Index):
            node = node.value
        if isinstance(node, ast.Constant) and isinstance(node.value, str):
            return node.value
        return None


class PythonScanner(ScannerBase):
    def supports(self, path: str) -> bool:
        return path.endswith(".py") and os.path.isfile(path)

    def scan(self, path: str) -> Optional[SymbolTable]:
        try:
            src = open(path, "r", encoding="utf-8").read()
            tree = ast.parse(src, filename=path)
        except Exception:
            return None

        module_name = os.path.splitext(os.path.basename(path))[0]
        st = SymbolTable(module_name=module_name, path=path)

        # Top-level exports
        for node in tree.body:
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                st.exports.append(node.name)
                # Build function signature entry
                args = node.args
                # Exclude 'self' and 'cls' from param counts
                params = [a for a in args.args if a.arg not in ("self", "cls")]
                n_defaults = len(args.defaults)
                n_total = len(params)
                n_required = n_total - n_defaults
                has_varargs = args.vararg is not None
                has_varkw = args.kwarg is not None
                ret_annotation = _annotation_name(node.returns)
                is_stub = _is_stub_body(node.body)
                st.functions[node.name] = {
                    "n_required": n_required,
                    "n_total": n_total,
                    "has_varargs": has_varargs,
                    "has_varkw": has_varkw,
                    "return_annotation": ret_annotation,
                    "is_stub": is_stub,
                    "line": getattr(node, "lineno", None),
                }
            elif isinstance(node, ast.ClassDef):
                st.exports.append(node.name)
            elif isinstance(node, ast.Assign):
                for target in node.targets:
                    if isinstance(target, ast.Name):
                        st.exports.append(target.id)
            elif isinstance(node, ast.AnnAssign):
                if isinstance(node.target, ast.Name):
                    st.exports.append(node.target.id)

        # All imports
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    st.imports.append(alias.name)
                    st.imported_symbols.append(alias.asname or alias.name.split(".")[-1])
            elif isinstance(node, ast.ImportFrom):
                if node.module:
                    st.imports.append(node.module)
                for alias in node.names:
                    st.imported_symbols.append(alias.asname or alias.name)
                    st.from_imports.append({
                        "module": node.module,
                        "name": alias.name,
                        "asname": alias.asname,
                        "line": getattr(node, "lineno", None),
                    })

        cc = _CallCollector()
        cc.visit(tree)
        st.calls = cc.calls

        ev = _EnvVarCollector()
        ev.visit(tree)
        st.env_vars_hard = ev.hard
        st.env_vars_soft = ev.soft

        return st
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
python3 -m pytest tests/test_stage1_checks.py -k "signature or stub or env_var or n_args" -v
```
Expected: all PASSED

- [ ] **Step 5: Commit**

```bash
git -C /home/visionairy/.claude/xf-boundary-auditor add scanner_python.py tests/test_stage1_checks.py
git -C /home/visionairy/.claude/xf-boundary-auditor commit -m "feat(xfa): extract function signatures, stub detection, env var access in PythonScanner"
```

---

## Task 3: Create checkers.py with syntax check

**Files:**
- Create: `checkers.py`

- [ ] **Step 1: Write failing test**

Append to `tests/test_stage1_checks.py`:

```python
def test_syntax_check_catches_syntax_error():
    import tempfile, os
    from checkers import syntax_violations
    src = "def foo(:\n    pass\n"
    with tempfile.NamedTemporaryFile(suffix=".py", mode="w", delete=False) as f:
        f.write(src)
        path = f.name
    try:
        viols = syntax_violations([path])
        assert len(viols) == 1
        assert viols[0]["type"] == "syntax_error"
        assert viols[0]["severity"] == "error"
        assert path in viols[0]["path"] or viols[0]["path"].endswith(".py")
    finally:
        os.unlink(path)

def test_syntax_check_passes_valid_file():
    import tempfile, os
    from checkers import syntax_violations
    src = "def foo():\n    return 1\n"
    with tempfile.NamedTemporaryFile(suffix=".py", mode="w", delete=False) as f:
        f.write(src)
        path = f.name
    try:
        viols = syntax_violations([path])
        assert viols == []
    finally:
        os.unlink(path)
```

- [ ] **Step 2: Run to verify failures**

```bash
python3 -m pytest tests/test_stage1_checks.py -k "syntax_check" -v 2>&1 | tail -10
```
Expected: `ModuleNotFoundError: No module named 'checkers'`

- [ ] **Step 3: Create checkers.py with syntax_violations**

Create `checkers.py`:

```python
from __future__ import annotations

import os
import py_compile
import tempfile
from typing import Dict, Any, List, Optional


def syntax_violations(py_paths: List[str]) -> List[Dict[str, Any]]:
    """Check each .py path for syntax errors using py_compile.

    Returns list of violations with type='syntax_error', severity='error'.
    """
    violations: List[Dict[str, Any]] = []
    vid = 1
    for path in py_paths:
        try:
            py_compile.compile(path, doraise=True)
        except py_compile.PyCompileError as e:
            violations.append({
                "id": f"s{vid:03d}",
                "type": "syntax_error",
                "severity": "error",
                "path": path,
                "line": _extract_line_from_pycompile_error(e),
                "detail": str(e).strip(),
                "consequence": "This file will not parse. Nothing in it will run.",
                "status": "open",
            })
            vid += 1
    return violations


def _extract_line_from_pycompile_error(e: py_compile.PyCompileError) -> Optional[int]:
    """Extract line number from PyCompileError if available."""
    try:
        # PyCompileError has exc_value which is a SyntaxError
        if hasattr(e, "exc_value") and hasattr(e.exc_value, "lineno"):
            return e.exc_value.lineno
    except Exception:
        pass
    return None


def arity_violations(index: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Check call sites against local function definitions for argument count mismatches."""
    # Build function map: symbol_name -> {n_required, n_total, has_varargs, has_varkw, path, line}
    func_map: Dict[str, Dict] = {}
    for mod_name, mod_info in index.get("modules", {}).items():
        for fn_name, fn_sig in mod_info.get("functions", {}).items():
            func_map[fn_name] = {**fn_sig, "defined_in": mod_info.get("path", mod_name)}

    violations: List[Dict[str, Any]] = []
    vid = 1

    for caller_path, calls in index.get("calls_by_file", {}).items():
        for call in calls:
            sym = call.get("symbol")
            kind = call.get("kind")
            n_args = call.get("n_args", 0)
            line = call.get("line") or 0
            if kind != "name" or not sym:
                continue
            if sym not in func_map:
                continue
            fn = func_map[sym]
            if fn.get("has_varargs"):
                continue  # *args accepts any positional count
            n_total = fn.get("n_total", 0)
            if n_args > n_total:
                violations.append({
                    "id": f"a{vid:03d}",
                    "type": "arity_mismatch",
                    "severity": "error",
                    "caller_module": caller_path,
                    "caller_line": line,
                    "symbol": sym,
                    "n_args_passed": n_args,
                    "n_args_accepted": n_total,
                    "defined_in": fn["defined_in"],
                    "defined_line": fn.get("line"),
                    "consequence": (
                        f"This will throw a TypeError when {sym}() runs — "
                        f"called with {n_args} arguments but it only accepts {n_total}."
                    ),
                    "fix": (
                        f"{caller_path}:{line} — remove {n_args - n_total} "
                        f"argument(s) from the call to {sym}()"
                    ),
                    "status": "open",
                })
                vid += 1

    return violations


def _load_dotenv(root: str) -> set:
    """Return set of env var names defined in {root}/.env. Returns empty set if missing."""
    env_path = os.path.join(root, ".env")
    defined: set = set()
    if not os.path.isfile(env_path):
        return defined
    try:
        for line in open(env_path, "r", encoding="utf-8"):
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            if "=" in line:
                key = line.split("=", 1)[0].strip()
                if key:
                    defined.add(key)
    except Exception:
        pass
    return defined


def env_var_violations(index: Dict[str, Any], root: str) -> List[Dict[str, Any]]:
    """Check hard env var accesses against .env definitions.

    A hard access is os.environ["KEY"] or os.environ.get("KEY") without a default.
    If the key is not in .env, emit a blocking violation.
    If .env doesn't exist at all, emit a warning for each hard access.
    """
    defined = _load_dotenv(root)
    env_exists = os.path.isfile(os.path.join(root, ".env"))
    violations: List[Dict[str, Any]] = []
    vid = 1

    for mod_name, mod_info in index.get("modules", {}).items():
        for access in mod_info.get("env_vars_hard", []):
            var_name = access.get("var_name")
            line = access.get("line") or 0
            path = mod_info.get("path", mod_name)
            if not var_name:
                continue
            if var_name in defined:
                continue  # defined in .env — OK
            severity = "error" if env_exists else "warning"
            consequence = (
                f"This will throw a KeyError when the code runs — "
                f"{var_name} is not defined in .env."
            ) if env_exists else (
                f"No .env file found — {var_name} will throw a KeyError unless "
                f"the environment provides it at runtime."
            )
            violations.append({
                "id": f"e{vid:03d}",
                "type": "missing_env_var",
                "severity": severity,
                "caller_module": path,
                "caller_line": line,
                "var_name": var_name,
                "consequence": consequence,
                "fix": f"Add {var_name}=<value> to .env, or change to os.getenv('{var_name}', default)",
                "status": "open",
            })
            vid += 1

    return violations


def stub_violations(index: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Detect stubs that have callers expecting a real return value.

    A stub is a function with a body of only pass / ... / docstring.
    If it has a non-None return annotation AND has callers in the repo → block (severity=error).
    If it has a non-None return annotation but no callers → warn (severity=warning).
    Void stubs (-> None or unannotated) → warn.
    """
    # Collect all callee symbols from resolved call edges
    called_symbols: set = set()
    for edge in index.get("callers", []):
        sym = edge.get("symbol")
        if sym:
            called_symbols.add(sym)

    violations: List[Dict[str, Any]] = []
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
                severity = "error"
                consequence = (
                    f"{fn_name}() is a stub that promises to return {ret} — "
                    f"callers will receive None and likely fail silently."
                )
                fix = f"Implement {fn_name}() or change return annotation to -> None"
            elif is_non_none:
                severity = "warning"
                consequence = (
                    f"{fn_name}() is a stub that promises to return {ret} but returns None. "
                    f"No callers detected in this repo yet."
                )
                fix = f"Implement {fn_name}() or change return annotation to -> None"
            else:
                severity = "warning"
                consequence = (
                    f"{fn_name}() is unimplemented (stub body). "
                    f"It will silently do nothing when called."
                )
                fix = f"Implement {fn_name}() or add a NotImplementedError raise"

            violations.append({
                "id": f"b{vid:03d}",
                "type": "stub_function",
                "severity": severity,
                "caller_module": path,
                "caller_line": line,
                "symbol": fn_name,
                "return_annotation": ret,
                "has_callers": has_callers,
                "consequence": consequence,
                "fix": fix,
                "status": "open",
            })
            vid += 1

    return violations
```

- [ ] **Step 4: Run syntax check tests**

```bash
python3 -m pytest tests/test_stage1_checks.py -k "syntax_check" -v
```
Expected: PASSED

- [ ] **Step 5: Commit**

```bash
git -C /home/visionairy/.claude/xf-boundary-auditor add checkers.py tests/test_stage1_checks.py
git -C /home/visionairy/.claude/xf-boundary-auditor commit -m "feat(xfa): add checkers.py with syntax, arity, env_var, stub check functions"
```

---

## Task 4: Wire function signatures and env data through build_index

**Files:**
- Modify: `flow_analyzer.py`

- [ ] **Step 1: Write failing test**

Append to `tests/test_stage1_checks.py`:

```python
def test_build_index_includes_functions():
    import tempfile, os
    from flow_analyzer import build_index
    with tempfile.TemporaryDirectory() as root:
        py_path = os.path.join(root, "mymod.py")
        with open(py_path, "w") as f:
            f.write("def do_thing(a, b):\n    return a + b\n")
        idx = build_index(root)
        mod = idx["modules"].get("mymod")
        assert mod is not None
        assert "functions" in mod
        assert "do_thing" in mod["functions"]

def test_build_index_includes_env_vars_hard():
    import tempfile, os
    from flow_analyzer import build_index
    with tempfile.TemporaryDirectory() as root:
        py_path = os.path.join(root, "mymod.py")
        with open(py_path, "w") as f:
            f.write("import os\nkey = os.environ['SECRET']\n")
        idx = build_index(root)
        mod = idx["modules"].get("mymod")
        assert mod is not None
        assert any(e["var_name"] == "SECRET" for e in mod.get("env_vars_hard", []))

def test_build_index_includes_calls_by_file():
    import tempfile, os
    from flow_analyzer import build_index
    with tempfile.TemporaryDirectory() as root:
        py_path = os.path.join(root, "caller.py")
        with open(py_path, "w") as f:
            f.write("result = some_func(1, 2, 3)\n")
        idx = build_index(root)
        assert "calls_by_file" in idx
```

- [ ] **Step 2: Run to verify failures**

```bash
python3 -m pytest tests/test_stage1_checks.py -k "build_index" -v 2>&1 | tail -15
```
Expected: FAILED

- [ ] **Step 3: Extend build_index in flow_analyzer.py**

Replace `flow_analyzer.py` with:

```python
from __future__ import annotations

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
            if fn.endswith(".py") or fn.endswith(".sh"):
                out.append(os.path.join(dirpath, fn))
    return out


def build_index(root: str) -> Dict[str, Any]:
    """Single-pass scan of the repo.

    Returns:
      modules: module_name -> {path, exports, functions, imports, env_vars_hard, env_vars_soft, ...}
      callers: resolved call edges [{caller, callee_module, symbol, line}]
      from_imports: [{caller_module, caller_line, callee_module, symbol}]
      calls_by_file: {rel_path -> [{symbol, line, kind, n_args, n_kwargs}]}
    """
    modules: Dict[str, Any] = {}
    callers: List[Dict[str, Any]] = []
    from_imports: List[Dict[str, Any]] = []
    calls_by_file: Dict[str, List] = {}

    symbol_tables = []
    for path in _iter_source_files(root):
        st = scan_file(path)
        if not st:
            continue
        symbol_tables.append(st)
        rel = os.path.relpath(path, root)
        modules[st.module_name] = {
            "path": rel,
            "exports": sorted(set(st.exports)),
            "functions": st.functions,
            "imports": sorted(set(st.imports)),
            "state_writes": st.state_writes,
            "env_vars_read": st.env_vars_read,
            "env_vars_hard": st.env_vars_hard,
            "env_vars_soft": st.env_vars_soft,
        }

        for imp in getattr(st, "from_imports", []) or []:
            mod = (imp.get("module") or "").split(".")[-1]
            name = imp.get("name")
            line = imp.get("line") or 0
            if not mod or not name or name == "*":
                continue
            from_imports.append({
                "caller_module": rel,
                "caller_line": line,
                "callee_module": mod,
                "symbol": name,
            })

        # calls_by_file for arity checker
        calls_by_file[rel] = st.calls

    # resolved call edges
    export_to_module: Dict[str, str] = {}
    for m, info in modules.items():
        for sym in info.get("exports", []):
            export_to_module.setdefault(sym, m)

    for st in symbol_tables:
        for c in st.calls:
            if c.get("kind") != "name":
                continue
            sym = c.get("symbol")
            if not sym:
                continue
            callee_module = export_to_module.get(sym)
            if callee_module:
                callers.append({
                    "caller": os.path.relpath(st.path, root),
                    "callee_module": callee_module,
                    "symbol": sym,
                    "line": c.get("line"),
                })

    return {
        "modules": modules,
        "callers": callers,
        "from_imports": from_imports,
        "calls_by_file": calls_by_file,
    }


def from_import_existence_violations(index: Dict[str, Any]) -> List[Dict[str, Any]]:
    """MVP high-signal check: local `from X import Y` must match X's exports."""
    modules = index.get("modules", {})
    exports_by_module = {m: set(info.get("exports", [])) for m, info in modules.items()}

    violations: List[Dict[str, Any]] = []
    vid = 1

    for edge in index.get("from_imports", []) or []:
        callee = edge.get("callee_module")
        sym = edge.get("symbol")
        if not callee or not sym:
            continue
        if callee not in exports_by_module:
            continue
        if sym in exports_by_module[callee]:
            continue

        violations.append({
            "id": f"v{vid:03d}",
            "type": "interface_existence",
            "severity": "error",
            "caller_module": edge.get("caller_module"),
            "caller_line": edge.get("caller_line") or 0,
            "callee_module": callee,
            "symbol": sym,
            "detail": f"from {callee} import {sym} — symbol does not exist in local module exports.",
            "consequence": f"This import will fail when the module loads — '{sym}' does not exist in {callee}.",
            "status": "open",
        })
        vid += 1

    return violations
```

- [ ] **Step 4: Run tests**

```bash
python3 -m pytest tests/test_stage1_checks.py -k "build_index" -v
```
Expected: all PASSED

- [ ] **Step 5: Commit**

```bash
git -C /home/visionairy/.claude/xf-boundary-auditor add flow_analyzer.py tests/test_stage1_checks.py
git -C /home/visionairy/.claude/xf-boundary-auditor commit -m "feat(xfa): thread functions + env_vars + calls_by_file through build_index"
```

---

## Task 5: Tests for arity, env_var, and stub checkers

**Files:**
- Modify: `tests/test_stage1_checks.py`

- [ ] **Step 1: Write arity checker tests**

Append to `tests/test_stage1_checks.py`:

```python
def test_arity_violation_detected():
    import tempfile, os
    from flow_analyzer import build_index
    from checkers import arity_violations
    with tempfile.TemporaryDirectory() as root:
        # Define function with 2 params
        with open(os.path.join(root, "mymod.py"), "w") as f:
            f.write("def do_work(a, b):\n    return a + b\n")
        # Call it with 3 args
        with open(os.path.join(root, "caller.py"), "w") as f:
            f.write("from mymod import do_work\nresult = do_work(1, 2, 3)\n")
        idx = build_index(root)
        viols = arity_violations(idx)
        assert len(viols) == 1
        assert viols[0]["type"] == "arity_mismatch"
        assert viols[0]["n_args_passed"] == 3
        assert viols[0]["n_args_accepted"] == 2
        assert "TypeError" in viols[0]["consequence"]

def test_arity_no_violation_correct_count():
    import tempfile, os
    from flow_analyzer import build_index
    from checkers import arity_violations
    with tempfile.TemporaryDirectory() as root:
        with open(os.path.join(root, "mymod.py"), "w") as f:
            f.write("def do_work(a, b):\n    return a + b\n")
        with open(os.path.join(root, "caller.py"), "w") as f:
            f.write("from mymod import do_work\nresult = do_work(1, 2)\n")
        idx = build_index(root)
        assert arity_violations(idx) == []

def test_arity_no_violation_varargs():
    import tempfile, os
    from flow_analyzer import build_index
    from checkers import arity_violations
    with tempfile.TemporaryDirectory() as root:
        with open(os.path.join(root, "mymod.py"), "w") as f:
            f.write("def do_work(*args):\n    return args\n")
        with open(os.path.join(root, "caller.py"), "w") as f:
            f.write("from mymod import do_work\nresult = do_work(1, 2, 3, 4, 5)\n")
        idx = build_index(root)
        assert arity_violations(idx) == []

def test_env_var_violation_missing_from_dotenv():
    import tempfile, os
    from flow_analyzer import build_index
    from checkers import env_var_violations
    with tempfile.TemporaryDirectory() as root:
        with open(os.path.join(root, "app.py"), "w") as f:
            f.write("import os\nkey = os.environ['SECRET_KEY']\n")
        with open(os.path.join(root, ".env"), "w") as f:
            f.write("OTHER_VAR=something\n")
        idx = build_index(root)
        viols = env_var_violations(idx, root)
        assert len(viols) == 1
        assert viols[0]["var_name"] == "SECRET_KEY"
        assert viols[0]["severity"] == "error"
        assert "KeyError" in viols[0]["consequence"]

def test_env_var_no_violation_defined_in_dotenv():
    import tempfile, os
    from flow_analyzer import build_index
    from checkers import env_var_violations
    with tempfile.TemporaryDirectory() as root:
        with open(os.path.join(root, "app.py"), "w") as f:
            f.write("import os\nkey = os.environ['SECRET_KEY']\n")
        with open(os.path.join(root, ".env"), "w") as f:
            f.write("SECRET_KEY=mysecret\n")
        idx = build_index(root)
        assert env_var_violations(idx, root) == []

def test_env_var_soft_access_no_violation():
    import tempfile, os
    from flow_analyzer import build_index
    from checkers import env_var_violations
    with tempfile.TemporaryDirectory() as root:
        with open(os.path.join(root, "app.py"), "w") as f:
            f.write("import os\nkey = os.getenv('MY_KEY', 'default')\n")
        with open(os.path.join(root, ".env"), "w") as f:
            f.write("OTHER=x\n")
        idx = build_index(root)
        # soft access — no violation even when not in .env
        assert env_var_violations(idx, root) == []

def test_stub_violation_non_none_return_with_callers():
    import tempfile, os
    from flow_analyzer import build_index
    from checkers import stub_violations
    with tempfile.TemporaryDirectory() as root:
        with open(os.path.join(root, "provider.py"), "w") as f:
            f.write("def get_name() -> str:\n    pass\n")
        with open(os.path.join(root, "consumer.py"), "w") as f:
            f.write("from provider import get_name\nresult = get_name()\n")
        idx = build_index(root)
        viols = stub_violations(idx)
        error_viols = [v for v in viols if v["severity"] == "error"]
        assert len(error_viols) == 1
        assert error_viols[0]["symbol"] == "get_name"
        assert "None" in error_viols[0]["consequence"]

def test_stub_violation_void_stub_is_warning_only():
    import tempfile, os
    from flow_analyzer import build_index
    from checkers import stub_violations
    with tempfile.TemporaryDirectory() as root:
        with open(os.path.join(root, "setup.py"), "w") as f:
            f.write("def setup():\n    pass\n")
        idx = build_index(root)
        viols = stub_violations(idx)
        assert all(v["severity"] == "warning" for v in viols)
```

- [ ] **Step 2: Run all checker tests**

```bash
python3 -m pytest tests/test_stage1_checks.py -k "arity or env_var or stub" -v
```
Expected: all PASSED

- [ ] **Step 3: Commit**

```bash
git -C /home/visionairy/.claude/xf-boundary-auditor add tests/test_stage1_checks.py
git -C /home/visionairy/.claude/xf-boundary-auditor commit -m "test(xfa): full test coverage for arity, env_var, stub Stage 1 checks"
```

---

## Task 6: Wire all checks into auditor.py

**Files:**
- Modify: `auditor.py`

This task wires all four checks into the main auditor entry point and formats each violation type with consequence-first language.

- [ ] **Step 1: Write integration test**

Append to `tests/test_stage1_checks.py`:

```python
def test_auditor_blocks_on_arity_mismatch(tmp_path, monkeypatch):
    """auditor.main() should exit 2 when an arity mismatch exists."""
    import json, sys
    from unittest.mock import patch

    # Create a small repo with an arity violation
    (tmp_path / "mymod.py").write_text("def do_work(a, b):\n    return a + b\n")
    (tmp_path / "caller.py").write_text("from mymod import do_work\nresult = do_work(1, 2, 3)\n")

    hook_input = json.dumps({"tool_name": "Edit", "tool_input": {}})
    monkeypatch.chdir(tmp_path)

    import io
    with patch("sys.stdin", io.StringIO(hook_input)):
        with patch("sys.argv", ["auditor.py"]):
            import importlib, auditor
            importlib.reload(auditor)
            try:
                result = auditor.main()
            except SystemExit as e:
                result = e.code
    assert result == 2
```

- [ ] **Step 2: Run to verify failure**

```bash
python3 -m pytest tests/test_stage1_checks.py::test_auditor_blocks_on_arity_mismatch -v 2>&1 | tail -10
```
Expected: FAILED (auditor.main() returns 0 because it doesn't run arity checks yet)

- [ ] **Step 3: Rewrite auditor.py to run all Stage 1 checks**

Replace `auditor.py` with:

```python
from __future__ import annotations

import json
import os
import sys
from datetime import datetime, timezone
from typing import Dict, Any, List

from flow_analyzer import build_index, from_import_existence_violations
from checkers import syntax_violations, arity_violations, env_var_violations, stub_violations

AUDIT_TOOLS = {"Edit", "Write"}

# XFA color palette — cyan distinguishes it from Dispatch blue in the terminal
XFA_CYAN  = "\033[96m"   # XFA brand color — headers
XFA_GREEN = "\033[92m"   # Clean ✓
XFA_RED   = "\033[91m"   # Violations / errors
XFA_YELLOW = "\033[93m"  # Warnings
XFA_GRAY  = "\033[90m"   # Secondary info — counts, module names
XFA_RESET = "\033[0m"    # Always reset


def _ensure_xf_dir(root: str) -> str:
    p = os.path.join(root, ".xf")
    os.makedirs(p, exist_ok=True)
    return p


def _write_json(path: str, obj: Dict[str, Any]) -> None:
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(obj, f, indent=2)
    os.replace(tmp, path)


def _severity_color(severity: str) -> str:
    if severity == "error":
        return XFA_RED
    if severity == "warning":
        return XFA_YELLOW
    return XFA_GRAY


def _format_violation(v: Dict[str, Any]) -> str:
    """Format a single violation as consequence-first output."""
    vtype = v.get("type", "")
    severity_color = _severity_color(v.get("severity", "error"))
    consequence = v.get("consequence", "")
    fix = v.get("fix") or v.get("detail", "")

    loc = ""
    if v.get("caller_module") and v.get("caller_line"):
        loc = f"{XFA_GRAY}{v['caller_module']}:{v['caller_line']}{XFA_RESET} — "
    elif v.get("path"):
        loc = f"{XFA_GRAY}{v['path']}{XFA_RESET} — "

    lines = [f"  {loc}{severity_color}{consequence}{XFA_RESET}"]
    if fix:
        lines.append(f"  {XFA_GRAY}Fix: {fix}{XFA_RESET}")
    return "\n".join(lines)


def _format_report(violations: List[Dict[str, Any]], warnings: List[Dict[str, Any]]) -> str:
    """Format blocking violations and warnings for terminal output."""
    lines = []

    if violations:
        lines.append(
            f"{XFA_CYAN}◈ XF Audit{XFA_RESET}  "
            f"{XFA_RED}This edit will break at runtime.{XFA_RESET}"
        )
        lines.append("")
        for v in violations[:20]:
            lines.append(_format_violation(v))
        if len(violations) > 20:
            lines.append(f"  {XFA_GRAY}…and {len(violations) - 20} more{XFA_RESET}")
        lines.append("")
        lines.append(
            f"{XFA_GRAY}Fix the violations above, then retry. "
            f"Run /xf-audit to fix all violations automatically.{XFA_RESET}"
        )

    if warnings:
        if violations:
            lines.append("")
        lines.append(
            f"{XFA_CYAN}◈ XF Audit{XFA_RESET}  "
            f"{XFA_YELLOW}{len(warnings)} warning(s) — not blocking:{XFA_RESET}"
        )
        for w in warnings[:10]:
            lines.append(_format_violation(w))

    return "\n".join(lines)


def main() -> int:
    try:
        raw = sys.stdin.read()
        hook_input = json.loads(raw)
    except Exception:
        return 0

    tool_name = hook_input.get("tool_name", "")
    if tool_name not in AUDIT_TOOLS:
        return 0

    root = os.getcwd()
    xf_dir = _ensure_xf_dir(root)

    try:
        index = build_index(root)
    except Exception:
        return 0

    module_count = len(index.get("modules", {}))
    edge_count = len(index.get("callers", []))

    # Save boundary index for provenance
    idx_obj = {
        "schema_version": "1.1",
        "last_scanned": datetime.now(timezone.utc).isoformat(),
        "modules": {
            name: {k: v for k, v in info.items() if k != "functions"}
            for name, info in index.get("modules", {}).items()
        },
        "callers": index.get("callers", []),
    }
    try:
        _write_json(os.path.join(xf_dir, "boundary_index.json"), idx_obj)
    except Exception:
        pass

    # Collect all .py paths for syntax check
    py_paths = [
        os.path.join(root, info["path"])
        for info in index.get("modules", {}).values()
        if info.get("path", "").endswith(".py")
    ]

    # Run all Stage 1 checks
    all_violations: List[Dict[str, Any]] = []
    all_warnings: List[Dict[str, Any]] = []

    def partition(viols):
        for v in viols:
            if v.get("severity") == "error":
                all_violations.append(v)
            else:
                all_warnings.append(v)

    try:
        partition(syntax_violations(py_paths))
    except Exception:
        pass

    try:
        partition(from_import_existence_violations(index))
    except Exception:
        pass

    try:
        partition(arity_violations(index))
    except Exception:
        pass

    try:
        partition(env_var_violations(index, root))
    except Exception:
        pass

    try:
        partition(stub_violations(index))
    except Exception:
        pass

    # Save violations for /xf-audit Ralph Loop
    vio_obj = {
        "schema_version": "1.1",
        "audit_timestamp": datetime.now(timezone.utc).isoformat(),
        "cwd": root,
        "total_violations": len(all_violations),
        "total_warnings": len(all_warnings),
        "violations": all_violations,
        "warnings": all_warnings,
        "ralph_iteration": 0,
    }
    try:
        _write_json(os.path.join(xf_dir, "boundary_violations.json"), vio_obj)
    except Exception:
        pass

    if all_violations:
        sys.stdout.write(_format_report(all_violations, all_warnings) + "\n")
        return 2

    # Provenance stamp — visible to user, confirms audit ran
    warning_suffix = ""
    if all_warnings:
        warning_suffix = (
            f"  {XFA_YELLOW}{len(all_warnings)} warning(s){XFA_RESET}"
        )
    sys.stdout.write(
        f"{XFA_CYAN}◈ XF Audit{XFA_RESET}  "
        f"{XFA_GRAY}{module_count} modules · {edge_count} edges checked{XFA_RESET}  "
        f"{XFA_GREEN}✓ 0 violations{XFA_RESET}"
        f"{warning_suffix}\n"
    )
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception:
        sys.exit(0)
```

- [ ] **Step 4: Run all tests**

```bash
python3 -m pytest tests/test_stage1_checks.py -v
```
Expected: all PASSED

- [ ] **Step 5: Run auditor manually against the Dispatch repo to verify clean output**

```bash
cd /home/visionairy/Dispatch
echo '{"tool_name":"Edit","tool_input":{}}' | python3 /home/visionairy/.claude/xf-boundary-auditor/auditor.py
```
Expected: `◈ XF Audit  N modules · M edges checked  ✓ 0 violations`

If violations appear, investigate — they may be real or false positives from the repo.

- [ ] **Step 6: Commit**

```bash
git -C /home/visionairy/.claude/xf-boundary-auditor add auditor.py tests/test_stage1_checks.py
git -C /home/visionairy/.claude/xf-boundary-auditor commit -m "feat(xfa): wire all Stage 1 checks into auditor with consequence-first output"
```

---

## Task 7: Stop hook — XF Audit session digest

**Files:**
- Modify: `/home/visionairy/Dispatch/stop_hook.sh`

The stop hook currently shows Dispatch stats. Add an XF Audit line when audits ran this session. The XF Audit stats come from `boundary_violations.json` (total checks in the last scan) — not a persistent session counter, but good enough for a session digest.

- [ ] **Step 1: Check current stop_hook.sh**

```bash
cat /home/visionairy/Dispatch/stop_hook.sh
```

- [ ] **Step 2: Add XF Audit digest section**

After the Dispatch digest block (the `print(f'{BLUE}◎ Dispatch...')` line), add:

```bash
# XF Audit session digest (reads last scan result from .xf/boundary_violations.json)
python3 -c "
import sys, os, json
sys.path.insert(0, sys.argv[1])

XFA_CYAN  = '\033[96m'
XFA_GREEN = '\033[92m'
XFA_YELLOW = '\033[93m'
XFA_GRAY  = '\033[90m'
XFA_RESET = '\033[0m'

try:
    vio_path = os.path.join(os.getcwd(), '.xf', 'boundary_violations.json')
    if not os.path.isfile(vio_path):
        sys.exit(0)
    data = json.loads(open(vio_path).read())
    total_viols = data.get('total_violations', 0)
    total_warns = data.get('total_warnings', 0)
    # Only show if XF Audit actually ran (file exists and was written this session)
    import time
    mtime = os.path.getmtime(vio_path)
    if time.time() - mtime > 3600:
        sys.exit(0)  # stale from previous session
    if total_viols == 0 and total_warns == 0:
        print(f'{XFA_CYAN}◈ XF Audit{XFA_RESET}  {XFA_GREEN}✓ all contracts intact{XFA_RESET}')
    elif total_viols == 0:
        print(f'{XFA_CYAN}◈ XF Audit{XFA_RESET}  {XFA_GREEN}✓ 0 violations{XFA_RESET}  {XFA_YELLOW}{total_warns} warning(s){XFA_RESET}')
    else:
        print(f'{XFA_CYAN}◈ XF Audit{XFA_RESET}  {XFA_YELLOW}{total_viols} violation(s) open{XFA_RESET}  — run /xf-audit to fix')
except Exception:
    pass
" "$SKILL_ROUTER_DIR" 2>/dev/null || true
```

The full updated stop_hook.sh should end with both digest sections followed by `exit 0`.

- [ ] **Step 3: Verify stop hook syntax**

```bash
bash -n /home/visionairy/Dispatch/stop_hook.sh
```
Expected: no output (clean parse)

- [ ] **Step 4: Commit**

```bash
cd /home/visionairy/Dispatch
git add stop_hook.sh
git commit -m "feat(xfa): add XF Audit session digest to stop hook"
```

---

## Task 8: Sync to installed location and verify end-to-end

**Files:**
- Installed: `~/.claude/xf-boundary-auditor/` (already the source location)
- Installed: `~/.claude/hooks/dispatch-stop.sh`

- [ ] **Step 1: Sync stop hook**

```bash
cp /home/visionairy/Dispatch/stop_hook.sh ~/.claude/hooks/dispatch-stop.sh
```

- [ ] **Step 2: Run full test suite**

```bash
python3 -m pytest /home/visionairy/.claude/xf-boundary-auditor/tests/ -v --tb=short
```
Expected: all PASSED

- [ ] **Step 3: Run live audit against Dispatch repo**

```bash
cd /home/visionairy/Dispatch
echo '{"tool_name":"Edit","tool_input":{}}' | python3 /home/visionairy/.claude/xf-boundary-auditor/auditor.py
```
Expected: clean output with module/edge counts and `✓ 0 violations`

Note: if any violations appear, check `.xf/boundary_violations.json` to understand them. They may be real issues in the codebase or gaps in the checker logic (edge cases like stdlib imports matching local module names). Document any false positives and file as separate issues.

- [ ] **Step 4: Verify stop hook fires cleanly**

```bash
echo '{}' | bash /home/visionairy/Dispatch/stop_hook.sh
```
Expected: Dispatch digest line + XF Audit digest line (or just Dispatch if no recent .xf/ file)

- [ ] **Step 5: Final commit**

```bash
cd /home/visionairy/Dispatch
git add .
git status  # confirm only stop_hook.sh changes are staged
git commit -m "feat(xfa): Stage 1 implementation complete — syntax, arity, env_vars, stubs"
```

---

## Self-Review

### Spec coverage check

| Spec requirement | Task |
|-----------------|------|
| Syntax error via py_compile | Task 3 |
| From-import existence (existing) | Already live; Task 4 adds `consequence` field |
| Arity mismatch on new call sites | Tasks 2, 3, 4, 5 |
| Missing env var, hard access | Tasks 2, 3, 4, 5 |
| Stub with annotated non-None return | Tasks 2, 3, 5 |
| Stub with void/unannotated → warn | Tasks 2, 3, 5 |
| Missing env var soft (getenv+default) → warn | Task 3 (`env_vars_soft`, no violation) |
| Consequence-first output language | Task 6 |
| Clean output: N modules · M edges checked | Task 6 |
| Session digest with XF Audit stats | Task 7 |
| `.xf/boundary_violations.json` provenance | Task 6 (already existed, now extended) |

**Not in this plan (Stage 2-4 — follow-on plan):**
- Xpansion cascade analysis on contract changes
- Repair plan generation
- Graduated consent flow (show diff / apply all)
- Refactor Mode (`/xfa-refactor start`)
- Repair log (`repair_log.json`)

### Placeholder scan: NONE FOUND

All code blocks are complete. All test assertions verify specific behavior.

### Type consistency check

- `SymbolTable.functions` dict shape: `{name: {n_required, n_total, has_varargs, has_varkw, return_annotation, is_stub, line}}` — consistent across Task 1 (definition), Task 2 (population), Tasks 3–5 (consumption in checkers).
- `index["calls_by_file"]` key: relative path string — added in Task 4 `build_index`, consumed in `arity_violations` in Task 3.
- `index["modules"][name]["functions"]` — added in Task 4, consumed in `arity_violations` (Task 3) and `stub_violations` (Task 3).
- `env_vars_hard`/`env_vars_soft` fields: `[{var_name, line}]` — consistent in Task 2 (scanner_python), Task 4 (flow_analyzer), Task 3 (env_var_violations).

## GSTACK REVIEW REPORT

| Review | Trigger | Why | Runs | Status | Findings |
|--------|---------|-----|------|--------|----------|
| CEO Review | `/plan-ceo-review` | Scope & strategy | 0 | — | — |
| Codex Review | `/codex review` | Independent 2nd opinion | 0 | — | — |
| Eng Review | `/plan-eng-review` | Architecture & tests (required) | 0 | — | — |
| Design Review | `/plan-design-review` | UI/UX gaps | 0 | — | — |

**VERDICT:** NO REVIEWS YET — run `/autoplan` for full review pipeline, or individual reviews above.
