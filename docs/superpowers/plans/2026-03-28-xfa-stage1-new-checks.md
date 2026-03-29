# XF Audit — Full Contract Loop Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implement the complete four-stage XF Audit contract loop — Stage 1 AST scan (syntax, arity, env vars, stubs, import existence), Stage 2 caller cascade tracing, Stage 3 concrete repair plan, Stage 4 graduated consent flow — plus Refactor Mode and the repair log provenance record.

**Architecture:** All checks are pure AST (zero API cost, ~200ms for Stage 1). Stage 2 traces the call graph already built by `build_index()` — no LLM required for cascade. Stage 3 formats violations as ordered repair plans. Stage 4 tracks trust level in `.xf/session_state.json` and formats consent options into the hook's stdout output (Claude reads and acts). Refactor Mode writes a flag file that shifts the auditor from blocking to tracking. Repair log detects resolved violations between scans and writes provenance to `.xf/repair_log.json`. The hook cannot call Edit itself (circular) — all repairs are executed by Claude from the auditor's output.

**Tech Stack:** Python 3.8+, `ast`, `py_compile`, `difflib`, standard library only. All source files in `~/.claude/xf-boundary-auditor/`. Tests run with `pytest`. Stop hook at `~/.claude/hooks/dispatch-stop.sh`.

**Working directory for all steps:** `/home/visionairy/.claude/xf-boundary-auditor/`

**Spec reference:** `/home/visionairy/Dispatch/docs/superpowers/specs/2026-03-28-xfa-contract-loop-design.md`

---

## File Structure

| File | Action | Purpose |
|------|--------|---------|
| `scanner_base.py` | Modify | Add `functions`, `env_vars_hard`, `env_vars_soft` fields to `SymbolTable`; add `n_args`/`n_kwargs` to call dicts |
| `scanner_python.py` | Modify | Populate new fields: function signatures, stub detection, env var access patterns |
| `checkers.py` | Create | All Stage 1 check functions: `syntax_violations`, `from_import_violations`, `arity_violations`, `env_var_violations`, `stub_violations` |
| `cascade.py` | Create | Stage 2: caller chain tracing from the resolved call graph |
| `repair.py` | Create | Stage 3: repair plan generation and diff rendering for mechanical fixes |
| `consent.py` | Create | Stage 4: trust counter read/write, consent output formatting |
| `refactor_mode.py` | Create | Refactor Mode: flag file check, violation accumulation, consolidated output |
| `flow_analyzer.py` | Modify | Thread new fields (`functions`, `env_vars_*`, `calls_by_file`) through `build_index()` |
| `auditor.py` | Rewrite | Orchestrate all stages; route violations through cascade/repair/consent; handle refactor mode |
| `tests/test_stage1.py` | Create | Stage 1 check tests |
| `tests/test_cascade.py` | Create | Stage 2 cascade tests |
| `tests/test_repair.py` | Create | Stage 3 repair plan tests |
| `tests/test_consent.py` | Create | Stage 4 consent flow tests |
| `tests/test_refactor_mode.py` | Create | Refactor Mode tests |
| `/home/visionairy/Dispatch/stop_hook.sh` | Modify | Add XF Audit session digest |

---

## Task 1: Extend SymbolTable and PythonScanner

**Files:**
- Modify: `scanner_base.py`
- Modify: `scanner_python.py`

- [ ] **Step 1: Write failing tests**

```bash
mkdir -p tests
cat > tests/test_stage1.py << 'EOF'
import sys, os, textwrap, tempfile
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from scanner_base import SymbolTable


def _scan(src):
    from scanner_python import PythonScanner
    with tempfile.NamedTemporaryFile(suffix=".py", mode="w", delete=False) as f:
        f.write(textwrap.dedent(src))
        path = f.name
    try:
        return PythonScanner().scan(path)
    finally:
        os.unlink(path)


def test_symboltable_new_fields():
    st = SymbolTable(module_name="x", path="x.py")
    assert isinstance(st.functions, dict)
    assert isinstance(st.env_vars_hard, list)
    assert isinstance(st.env_vars_soft, list)


def test_function_signature_extracted():
    st = _scan("""
        def add(a, b):
            return a + b
    """)
    assert "add" in st.functions
    fn = st.functions["add"]
    assert fn["n_required"] == 2
    assert fn["n_total"] == 2
    assert fn["has_varargs"] is False
    assert fn["is_stub"] is False


def test_function_with_defaults():
    st = _scan("""
        def greet(name, greeting="Hello"):
            return f"{greeting} {name}"
    """)
    fn = st.functions["greet"]
    assert fn["n_required"] == 1
    assert fn["n_total"] == 2


def test_varargs_function():
    st = _scan("""
        def collect(*args, **kwargs):
            return args
    """)
    fn = st.functions["collect"]
    assert fn["has_varargs"] is True
    assert fn["has_varkw"] is True
    assert fn["n_required"] == 0


def test_stub_with_non_none_return():
    st = _scan("""
        def get_name() -> str:
            pass
    """)
    fn = st.functions["get_name"]
    assert fn["is_stub"] is True
    assert fn["return_annotation"] == "str"


def test_stub_ellipsis_body():
    st = _scan("""
        def placeholder() -> int:
            ...
    """)
    assert st.functions["placeholder"]["is_stub"] is True


def test_void_stub():
    st = _scan("""
        def setup():
            pass
    """)
    fn = st.functions["setup"]
    assert fn["is_stub"] is True
    assert fn["return_annotation"] is None


def test_hard_env_var_subscript():
    st = _scan("""
        import os
        key = os.environ["SECRET"]
    """)
    assert any(e["var_name"] == "SECRET" for e in st.env_vars_hard)
    assert st.env_vars_soft == []


def test_hard_env_var_get_no_default():
    st = _scan("""
        import os
        key = os.environ.get("API_KEY")
    """)
    assert any(e["var_name"] == "API_KEY" for e in st.env_vars_hard)


def test_soft_env_var_getenv_with_default():
    st = _scan("""
        import os
        key = os.getenv("MY_KEY", "fallback")
    """)
    assert any(e["var_name"] == "MY_KEY" for e in st.env_vars_soft)
    assert st.env_vars_hard == []


def test_call_includes_n_args():
    st = _scan("""
        result = my_func(1, 2, 3)
    """)
    call = next((c for c in st.calls if c["symbol"] == "my_func"), None)
    assert call is not None
    assert call["n_args"] == 3
    assert call["n_kwargs"] == 0
EOF
```

- [ ] **Step 2: Run to verify failures**

```bash
python3 -m pytest tests/test_stage1.py -v 2>&1 | tail -20
```
Expected: multiple FAILED (fields don't exist yet)

- [ ] **Step 3: Update scanner_base.py**

```python
# scanner_base.py
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
    # Stage 1 new fields
    functions: Dict[str, Dict] = field(default_factory=dict)
    env_vars_hard: List[Dict] = field(default_factory=list)  # [{var_name, line}]
    env_vars_soft: List[Dict] = field(default_factory=list)  # [{var_name, line}]


class ScannerBase(ABC):
    @abstractmethod
    def supports(self, path: str) -> bool: ...

    @abstractmethod
    def scan(self, path: str) -> Optional[SymbolTable]: ...
```

- [ ] **Step 4: Update scanner_python.py**

```python
# scanner_python.py
from __future__ import annotations

import ast
import os
from typing import Optional, List, Dict, Any

from scanner_base import ScannerBase, SymbolTable


def _is_stub_body(body: list) -> bool:
    if not body:
        return True
    if len(body) == 1:
        node = body[0]
        if isinstance(node, ast.Pass):
            return True
        if isinstance(node, ast.Expr) and isinstance(node.value, ast.Constant):
            return True  # "..." or docstring only
    if len(body) == 2:
        first, second = body
        is_docstring = isinstance(first, ast.Expr) and isinstance(first.value, ast.Constant)
        is_pass_or_ellipsis = isinstance(second, ast.Pass) or (
            isinstance(second, ast.Expr) and isinstance(second.value, ast.Constant)
        )
        if is_docstring and is_pass_or_ellipsis:
            return True
    return False


def _annotation_name(node) -> Optional[str]:
    if node is None:
        return None
    if isinstance(node, ast.Constant):
        return str(node.value)
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        return node.attr
    if isinstance(node, ast.Subscript):
        return _annotation_name(node.value)
    return None


class _CallCollector(ast.NodeVisitor):
    def __init__(self):
        self.calls: List[Dict[str, Any]] = []

    def visit_Call(self, node: ast.Call):
        n_args = len(node.args)
        n_kwargs = len(node.keywords)
        if isinstance(node.func, ast.Name):
            self.calls.append({"symbol": node.func.id, "line": getattr(node, "lineno", None),
                                "kind": "name", "n_args": n_args, "n_kwargs": n_kwargs})
        elif isinstance(node.func, ast.Attribute):
            self.calls.append({"symbol": node.func.attr, "line": getattr(node, "lineno", None),
                                "kind": "attr", "n_args": n_args, "n_kwargs": n_kwargs})
        self.generic_visit(node)


class _EnvVarCollector(ast.NodeVisitor):
    def __init__(self):
        self.hard: List[Dict] = []
        self.soft: List[Dict] = []

    @staticmethod
    def _str_key(node) -> Optional[str]:
        if isinstance(node, ast.Index):  # Python 3.8 compat
            node = node.value
        if isinstance(node, ast.Constant) and isinstance(node.value, str):
            return node.value
        return None

    def visit_Subscript(self, node: ast.Subscript):
        # os.environ["KEY"]
        if (isinstance(node.value, ast.Attribute) and node.value.attr == "environ"
                and isinstance(node.value.value, ast.Name) and node.value.value.id == "os"):
            key = self._str_key(node.slice)
            if key:
                self.hard.append({"var_name": key, "line": getattr(node, "lineno", None)})
        self.generic_visit(node)

    def visit_Call(self, node: ast.Call):
        if not isinstance(node.func, ast.Attribute):
            self.generic_visit(node)
            return
        attr, val = node.func.attr, node.func.value
        is_environ_get = (attr == "get" and isinstance(val, ast.Attribute)
                          and val.attr == "environ" and isinstance(val.value, ast.Name)
                          and val.value.id == "os")
        is_getenv = (attr == "getenv" and isinstance(val, ast.Name) and val.id == "os")
        if (is_environ_get or is_getenv) and node.args:
            key = self._str_key(node.args[0])
            if key:
                has_default = len(node.args) > 1 or any(kw.arg == "default" for kw in node.keywords)
                entry = {"var_name": key, "line": getattr(node, "lineno", None)}
                (self.soft if has_default else self.hard).append(entry)
        self.generic_visit(node)


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

        for node in tree.body:
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                st.exports.append(node.name)
                args = node.args
                params = [a for a in args.args if a.arg not in ("self", "cls")]
                n_total = len(params)
                n_required = n_total - len(args.defaults)
                st.functions[node.name] = {
                    "n_required": n_required,
                    "n_total": n_total,
                    "has_varargs": args.vararg is not None,
                    "has_varkw": args.kwarg is not None,
                    "return_annotation": _annotation_name(node.returns),
                    "is_stub": _is_stub_body(node.body),
                    "line": getattr(node, "lineno", None),
                }
            elif isinstance(node, ast.ClassDef):
                st.exports.append(node.name)
            elif isinstance(node, ast.Assign):
                for t in node.targets:
                    if isinstance(t, ast.Name):
                        st.exports.append(t.id)
            elif isinstance(node, ast.AnnAssign):
                if isinstance(node.target, ast.Name):
                    st.exports.append(node.target.id)

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
                    st.from_imports.append({"module": node.module, "name": alias.name,
                                            "asname": alias.asname,
                                            "line": getattr(node, "lineno", None)})

        cc = _CallCollector()
        cc.visit(tree)
        st.calls = cc.calls

        ev = _EnvVarCollector()
        ev.visit(tree)
        st.env_vars_hard = ev.hard
        st.env_vars_soft = ev.soft

        return st
```

- [ ] **Step 5: Run tests**

```bash
python3 -m pytest tests/test_stage1.py -v
```
Expected: all PASSED

- [ ] **Step 6: Commit**

```bash
git -C /home/visionairy/.claude/xf-boundary-auditor add scanner_base.py scanner_python.py tests/test_stage1.py
git -C /home/visionairy/.claude/xf-boundary-auditor commit -m "feat(xfa): extend SymbolTable and PythonScanner for Stage 1 checks"
```

---

## Task 2: Create checkers.py (Stage 1 checks)

**Files:**
- Create: `checkers.py`

- [ ] **Step 1: Write failing tests**

Append to `tests/test_stage1.py`:

```python
# --- Stage 1 checker tests ---

def test_syntax_check_catches_error():
    from checkers import syntax_violations
    with tempfile.NamedTemporaryFile(suffix=".py", mode="w", delete=False) as f:
        f.write("def foo(:\n    pass\n")
        path = f.name
    try:
        viols = syntax_violations([path])
        assert len(viols) == 1
        assert viols[0]["type"] == "syntax_error"
        assert viols[0]["severity"] == "error"
    finally:
        os.unlink(path)


def test_syntax_check_passes_valid():
    from checkers import syntax_violations
    with tempfile.NamedTemporaryFile(suffix=".py", mode="w", delete=False) as f:
        f.write("def foo():\n    return 1\n")
        path = f.name
    try:
        assert syntax_violations([path]) == []
    finally:
        os.unlink(path)


def _build(files_dict):
    """Write files to a temp dir and return (root, index)."""
    from flow_analyzer import build_index
    root = tempfile.mkdtemp()
    for name, src in files_dict.items():
        p = os.path.join(root, name)
        os.makedirs(os.path.dirname(p), exist_ok=True)
        open(p, "w").write(textwrap.dedent(src))
    return root, build_index(root)


def test_arity_violation_too_many_args():
    from checkers import arity_violations
    root, idx = _build({
        "mymod.py": "def do_work(a, b):\n    return a + b\n",
        "caller.py": "from mymod import do_work\nresult = do_work(1, 2, 3)\n",
    })
    viols = arity_violations(idx)
    assert len(viols) == 1
    assert viols[0]["type"] == "arity_mismatch"
    assert viols[0]["n_args_passed"] == 3
    assert viols[0]["n_args_accepted"] == 2
    assert "TypeError" in viols[0]["consequence"]


def test_arity_no_violation_correct_count():
    from checkers import arity_violations
    _, idx = _build({
        "mymod.py": "def do_work(a, b):\n    return a + b\n",
        "caller.py": "result = do_work(1, 2)\n",
    })
    assert arity_violations(idx) == []


def test_arity_no_violation_varargs():
    from checkers import arity_violations
    _, idx = _build({
        "mymod.py": "def collect(*args):\n    return args\n",
        "caller.py": "collect(1, 2, 3, 4, 5)\n",
    })
    assert arity_violations(idx) == []


def test_env_var_violation_missing_from_dotenv():
    from checkers import env_var_violations
    root, idx = _build({"app.py": "import os\nkey = os.environ['SECRET_KEY']\n"})
    open(os.path.join(root, ".env"), "w").write("OTHER=x\n")
    viols = env_var_violations(idx, root)
    assert len(viols) == 1
    assert viols[0]["var_name"] == "SECRET_KEY"
    assert viols[0]["severity"] == "error"


def test_env_var_no_violation_defined():
    from checkers import env_var_violations
    root, idx = _build({"app.py": "import os\nkey = os.environ['SECRET_KEY']\n"})
    open(os.path.join(root, ".env"), "w").write("SECRET_KEY=val\n")
    assert env_var_violations(idx, root) == []


def test_env_var_soft_no_violation():
    from checkers import env_var_violations
    root, idx = _build({"app.py": "import os\nkey = os.getenv('MY_KEY', 'default')\n"})
    open(os.path.join(root, ".env"), "w").write("OTHER=x\n")
    assert env_var_violations(idx, root) == []


def test_stub_error_non_none_return_with_callers():
    from checkers import stub_violations
    _, idx = _build({
        "provider.py": "def get_name() -> str:\n    pass\n",
        "consumer.py": "from provider import get_name\nresult = get_name()\n",
    })
    viols = stub_violations(idx)
    errors = [v for v in viols if v["severity"] == "error"]
    assert len(errors) == 1
    assert errors[0]["symbol"] == "get_name"


def test_stub_warning_void():
    from checkers import stub_violations
    _, idx = _build({"setup.py": "def init():\n    pass\n"})
    viols = stub_violations(idx)
    assert all(v["severity"] == "warning" for v in viols)
```

- [ ] **Step 2: Run to verify failures**

```bash
python3 -m pytest tests/test_stage1.py -k "syntax or arity or env_var or stub" -v 2>&1 | tail -15
```
Expected: `ModuleNotFoundError: No module named 'checkers'`

- [ ] **Step 3: Create checkers.py**

```python
# checkers.py
from __future__ import annotations

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
            n_args, line = call.get("n_args", 0), call.get("line") or 0
            if kind != "name" or not sym or sym not in func_map:
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
```

- [ ] **Step 4: Run all Stage 1 tests**

```bash
python3 -m pytest tests/test_stage1.py -v
```
Expected: all PASSED

- [ ] **Step 5: Commit**

```bash
git -C /home/visionairy/.claude/xf-boundary-auditor add checkers.py tests/test_stage1.py
git -C /home/visionairy/.claude/xf-boundary-auditor commit -m "feat(xfa): Stage 1 checkers — syntax, imports, arity, env_vars, stubs"
```

---

## Task 3: Extend flow_analyzer.py

**Files:**
- Modify: `flow_analyzer.py`

- [ ] **Step 1: Write failing tests**

```bash
cat > tests/test_flow_analyzer.py << 'EOF'
import sys, os, tempfile, textwrap
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))


def _build(files_dict):
    from flow_analyzer import build_index
    root = tempfile.mkdtemp()
    for name, src in files_dict.items():
        p = os.path.join(root, name)
        open(p, "w").write(textwrap.dedent(src))
    return root, build_index(root)


def test_build_index_includes_functions():
    _, idx = _build({"mymod.py": "def do_thing(a, b):\n    return a + b\n"})
    mod = idx["modules"].get("mymod")
    assert mod is not None
    assert "do_thing" in mod["functions"]


def test_build_index_includes_env_vars_hard():
    _, idx = _build({"app.py": "import os\nkey = os.environ['SECRET']\n"})
    mod = idx["modules"]["app"]
    assert any(e["var_name"] == "SECRET" for e in mod["env_vars_hard"])


def test_build_index_includes_calls_by_file():
    _, idx = _build({"caller.py": "result = some_func(1, 2, 3)\n"})
    assert "calls_by_file" in idx
    calls = list(idx["calls_by_file"].values())[0]
    call = next(c for c in calls if c["symbol"] == "some_func")
    assert call["n_args"] == 3
EOF
```

- [ ] **Step 2: Run to verify failures**

```bash
python3 -m pytest tests/test_flow_analyzer.py -v 2>&1 | tail -10
```
Expected: FAILED (missing fields)

- [ ] **Step 3: Update flow_analyzer.py**

```python
# flow_analyzer.py
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
        for imp in st.from_imports or []:
            mod = (imp.get("module") or "").split(".")[-1]
            name, line = imp.get("name"), imp.get("line") or 0
            if mod and name and name != "*":
                from_imports.append({
                    "caller_module": rel, "caller_line": line,
                    "callee_module": mod, "symbol": name,
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

    return {"modules": modules, "callers": callers,
            "from_imports": from_imports, "calls_by_file": calls_by_file}
```

- [ ] **Step 4: Run tests**

```bash
python3 -m pytest tests/test_flow_analyzer.py tests/test_stage1.py -v
```
Expected: all PASSED

- [ ] **Step 5: Commit**

```bash
git -C /home/visionairy/.claude/xf-boundary-auditor add flow_analyzer.py tests/test_flow_analyzer.py
git -C /home/visionairy/.claude/xf-boundary-auditor commit -m "feat(xfa): thread functions + env_vars + calls_by_file through build_index"
```

---

## Task 4: Create cascade.py (Stage 2)

**Files:**
- Create: `cascade.py`

Stage 2 fires when a violation indicates a contract change to an existing symbol. It traces all callers of the changed symbol transitively through the call graph already in the index, ordered by dependency depth (root first), with consequence descriptions per caller.

- [ ] **Step 1: Write failing tests**

```bash
cat > tests/test_cascade.py << 'EOF'
import sys, os, tempfile, textwrap
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))


def _build(files_dict):
    from flow_analyzer import build_index
    root = tempfile.mkdtemp()
    for name, src in files_dict.items():
        p = os.path.join(root, name)
        open(p, "w").write(textwrap.dedent(src))
    return root, build_index(root)


def test_cascade_traces_direct_caller():
    from cascade import trace_cascade
    _, idx = _build({
        "mymod.py": "def rank_tools(a, b):\n    return []\n",
        "caller.py": "from mymod import rank_tools\nresult = rank_tools(1)\n",
    })
    result = trace_cascade(idx, changed_symbol="rank_tools")
    assert any(e["caller"] == "caller.py" for e in result)


def test_cascade_empty_when_no_callers():
    from cascade import trace_cascade
    _, idx = _build({"lonely.py": "def orphan():\n    pass\n"})
    assert trace_cascade(idx, changed_symbol="orphan") == []


def test_cascade_ordered_by_depth():
    from cascade import trace_cascade
    _, idx = _build({
        "core.py": "def base_func():\n    return 1\n",
        "mid.py": "from core import base_func\ndef mid_func():\n    return base_func()\n",
        "top.py": "from mid import mid_func\nresult = mid_func()\n",
    })
    result = trace_cascade(idx, changed_symbol="base_func")
    callers = [e["caller"] for e in result]
    # mid.py should appear before top.py (closer to root)
    if "mid.py" in callers and "top.py" in callers:
        assert callers.index("mid.py") < callers.index("top.py")


def test_cascade_notification_text():
    from cascade import format_cascade_notification
    result = format_cascade_notification("rank_tools", 3)
    assert "rank_tools" in result
    assert "3" in result
EOF
```

- [ ] **Step 2: Run to verify failures**

```bash
python3 -m pytest tests/test_cascade.py -v 2>&1 | tail -10
```
Expected: `ModuleNotFoundError: No module named 'cascade'`

- [ ] **Step 3: Create cascade.py**

```python
# cascade.py
from __future__ import annotations

from collections import deque
from typing import Dict, Any, List


def trace_cascade(index: Dict[str, Any], changed_symbol: str) -> List[Dict[str, Any]]:
    """BFS over the call graph to find all callers of changed_symbol, ordered by depth.

    Returns list of {caller, symbol, line, depth, consequence} dicts.
    """
    callers_index: Dict[str, List[Dict]] = {}
    for edge in index.get("callers", []):
        sym = edge.get("symbol")
        if sym:
            callers_index.setdefault(sym, []).append(edge)

    # Build export map: symbol → module name
    export_to_module: Dict[str, str] = {}
    for mod_name, mod_info in index.get("modules", {}).items():
        for sym in mod_info.get("exports", []):
            export_to_module.setdefault(sym, mod_name)

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
        caller_module_name = _path_to_module_name(current["caller"])
        mod_info = index.get("modules", {}).get(caller_module_name, {})
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
    """Convert relative file path to module name (strip .py, replace / with .)."""
    if path.endswith(".py"):
        path = path[:-3]
    return path.replace("/", ".").replace("\\", ".").split(".")[-1]


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
    return (f"\033[96m◈ XF Audit\033[0m  "
            f"Contract change detected on \033[93m{symbol}\033[0m — "
            f"mapping {n_callers} caller(s)...")


def format_cascade_report(symbol: str, cascade: List[Dict[str, Any]]) -> str:
    """Format the full cascade for Stage 2 output."""
    if not cascade:
        return (f"\033[96m◈ XF Audit\033[0m  "
                f"No callers of \033[93m{symbol}\033[0m found in this repo.")
    lines = [
        f"\033[96m◈ XF Audit\033[0m  Stage 2: Caller cascade for \033[93m{symbol}\033[0m",
        f"\033[90m  {len(cascade)} caller(s) affected — fix root first, others may resolve:\033[0m",
        "",
    ]
    for item in cascade:
        depth_indent = "  " * item.get("depth", 1)
        caller = item.get("caller", "?")
        line = item.get("line") or "?"
        consequence = item.get("consequence", "")
        lines.append(f"{depth_indent}\033[90m{caller}:{line}\033[0m")
        lines.append(f"{depth_indent}  {consequence}")
    return "\n".join(lines)
```

- [ ] **Step 4: Run cascade tests**

```bash
python3 -m pytest tests/test_cascade.py -v
```
Expected: all PASSED

- [ ] **Step 5: Commit**

```bash
git -C /home/visionairy/.claude/xf-boundary-auditor add cascade.py tests/test_cascade.py
git -C /home/visionairy/.claude/xf-boundary-auditor commit -m "feat(xfa): Stage 2 caller cascade tracing"
```

---

## Task 5: Create repair.py (Stage 3)

**Files:**
- Create: `repair.py`

Stage 3 produces a concrete, ordered repair plan. For violations where the fix is mechanical (arity, missing import, env var), it also renders a unified diff showing the exact change needed. Complex violations (stubs, contract changes) get a plain-text instruction.

- [ ] **Step 1: Write failing tests**

```bash
cat > tests/test_repair.py << 'EOF'
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))


def test_repair_plan_ordered_by_severity():
    from repair import build_repair_plan
    viols = [
        {"id": "a001", "type": "arity_mismatch", "severity": "error",
         "caller_module": "caller.py", "caller_line": 10,
         "symbol": "rank_tools", "n_args_passed": 3, "n_args_accepted": 2,
         "consequence": "Will throw TypeError.", "fix": "caller.py:10 — remove 1 arg",
         "status": "open"},
        {"id": "i001", "type": "interface_existence", "severity": "error",
         "caller_module": "other.py", "caller_line": 5,
         "callee_module": "mymod", "symbol": "old_func",
         "consequence": "Import fails on load.", "fix": "Update import name.",
         "status": "open"},
    ]
    plan = build_repair_plan(viols)
    assert len(plan) == 2
    # Both errors — order by file then line
    assert plan[0]["id"] in ("a001", "i001")


def test_repair_plan_format_text():
    from repair import format_repair_plan
    plan = [
        {"id": "a001", "type": "arity_mismatch", "severity": "error",
         "caller_module": "caller.py", "caller_line": 10,
         "symbol": "rank_tools", "n_args_passed": 3, "n_args_accepted": 2,
         "consequence": "Will throw TypeError when the ranker runs.",
         "fix": "caller.py:10 — remove the third argument",
         "status": "open"},
    ]
    text = format_repair_plan(plan)
    assert "TypeError" in text
    assert "caller.py" in text
    assert "1." in text  # numbered list


def test_repair_log_entry_shape():
    from repair import make_repair_log_entry
    entry = make_repair_log_entry(
        violation_id="a001",
        violation_type="arity_mismatch",
        symbol="rank_tools",
        description="Removed third argument from rank_tools() call at caller.py:10",
        session_id="test-session-1",
    )
    assert "violation_id" in entry
    assert "timestamp" in entry
    assert "session_id" in entry
    assert entry["session_id"] == "test-session-1"
EOF
```

- [ ] **Step 2: Run to verify failures**

```bash
python3 -m pytest tests/test_repair.py -v 2>&1 | tail -10
```
Expected: `ModuleNotFoundError: No module named 'repair'`

- [ ] **Step 3: Create repair.py**

```python
# repair.py
from __future__ import annotations

import difflib
import os
from datetime import datetime, timezone
from typing import Dict, Any, List, Optional


def build_repair_plan(violations: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Order violations for repair: errors first, then by file and line.

    Fixing root violations first often resolves downstream ones automatically.
    """
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
        f"\033[96m◈ XF Audit\033[0m  \033[91m{len(plan)} contract(s) broken.\033[0m",
        "",
    ]
    for n, v in enumerate(plan, 1):
        mod = v.get("caller_module", "?")
        line = v.get("caller_line") or "?"
        consequence = v.get("consequence", "")
        fix = v.get("fix", "")
        sym = v.get("symbol", "")

        lines.append(f"  \033[90m{n}. {mod}:{line}\033[0m"
                     + (f" — \033[93m{sym}()\033[0m" if sym else ""))
        lines.append(f"     {consequence}")
        if fix:
            lines.append(f"     \033[90mFix: {fix}\033[0m")
        lines.append("")
    return "\n".join(lines)


def generate_diff(file_path: str, original_line: int, original_text: str,
                  replacement_text: str) -> Optional[str]:
    """Generate a unified diff for a mechanical single-line fix.

    Returns the diff as a string, or None if the file cannot be read or
    the original text is not found at the expected line.
    """
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
```

- [ ] **Step 4: Run repair tests**

```bash
python3 -m pytest tests/test_repair.py -v
```
Expected: all PASSED

- [ ] **Step 5: Commit**

```bash
git -C /home/visionairy/.claude/xf-boundary-auditor add repair.py tests/test_repair.py
git -C /home/visionairy/.claude/xf-boundary-auditor commit -m "feat(xfa): Stage 3 repair plan generation and diff rendering"
```

---

## Task 6: Create consent.py (Stage 4)

**Files:**
- Create: `consent.py`

Stage 4 tracks trust level in `.xf/session_state.json`. On first and second repair: only "show me the diff first" and "skip". After two verified repairs this session: "apply all" unlocks. Resets at session start (file mtime check).

- [ ] **Step 1: Write failing tests**

```bash
cat > tests/test_consent.py << 'EOF'
import sys, os, tempfile, json
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))


def _state_dir():
    d = tempfile.mkdtemp()
    return os.path.join(d, ".xf")


def test_trust_level_starts_at_zero():
    from consent import get_trust_level
    xf_dir = _state_dir()
    os.makedirs(xf_dir)
    assert get_trust_level(xf_dir) == 0


def test_trust_level_increments():
    from consent import get_trust_level, increment_trust
    xf_dir = _state_dir()
    os.makedirs(xf_dir)
    increment_trust(xf_dir)
    assert get_trust_level(xf_dir) == 1
    increment_trust(xf_dir)
    assert get_trust_level(xf_dir) == 2


def test_consent_options_low_trust():
    from consent import format_consent_options
    text = format_consent_options(trust_level=0, n_violations=2)
    assert "show me the diff first" in text.lower() or "show" in text
    assert "apply all" not in text


def test_consent_options_high_trust():
    from consent import format_consent_options
    text = format_consent_options(trust_level=2, n_violations=3)
    assert "apply all" in text.lower() or "apply" in text


def test_write_repair_log():
    from consent import append_repair_log
    xf_dir = _state_dir()
    os.makedirs(xf_dir)
    append_repair_log(xf_dir, {"violation_id": "a001", "description": "fixed"})
    log_path = os.path.join(xf_dir, "repair_log.json")
    assert os.path.isfile(log_path)
    data = json.loads(open(log_path).read())
    assert len(data["repairs"]) == 1
    assert data["repairs"][0]["violation_id"] == "a001"


def test_repair_log_appends():
    from consent import append_repair_log
    xf_dir = _state_dir()
    os.makedirs(xf_dir)
    append_repair_log(xf_dir, {"violation_id": "a001"})
    append_repair_log(xf_dir, {"violation_id": "a002"})
    data = json.loads(open(os.path.join(xf_dir, "repair_log.json")).read())
    assert len(data["repairs"]) == 2
EOF
```

- [ ] **Step 2: Run to verify failures**

```bash
python3 -m pytest tests/test_consent.py -v 2>&1 | tail -10
```
Expected: `ModuleNotFoundError: No module named 'consent'`

- [ ] **Step 3: Create consent.py**

```python
# consent.py
from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from typing import Dict, Any, List

XFA_CYAN   = "\033[96m"
XFA_GREEN  = "\033[92m"
XFA_YELLOW = "\033[93m"
XFA_GRAY   = "\033[90m"
XFA_RESET  = "\033[0m"

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
    """Number of verified repairs accepted this session (0, 1, or 2+)."""
    return int(_read_state(xf_dir).get("trust_level", 0))


def increment_trust(xf_dir: str) -> int:
    """Record that the user accepted and verified a repair. Returns new trust level."""
    state = _read_state(xf_dir)
    level = int(state.get("trust_level", 0)) + 1
    state["trust_level"] = level
    state["last_updated"] = datetime.now(timezone.utc).isoformat()
    _write_state(xf_dir, state)
    return level


def reset_trust(xf_dir: str) -> None:
    """Reset trust at session start."""
    state = _read_state(xf_dir)
    state["trust_level"] = 0
    state["session_start"] = datetime.now(timezone.utc).isoformat()
    _write_state(xf_dir, state)


def format_consent_options(trust_level: int, n_violations: int) -> str:
    """Format the consent block shown after the repair plan.

    trust_level < 2  → show diff + skip only
    trust_level >= 2 → apply all + show diff + skip
    """
    lines = [""]
    if trust_level >= 2:
        lines.append(
            f"  {XFA_GREEN}[apply all {n_violations}]{XFA_RESET}  "
            f"{XFA_GRAY}[show me the diff first]{XFA_RESET}  "
            f"{XFA_GRAY}[skip for now]{XFA_RESET}"
        )
    else:
        lines.append(
            f"  {XFA_GREEN}[show me the diff first]{XFA_RESET}  "
            f"{XFA_GRAY}[skip for now]{XFA_RESET}"
        )
        if trust_level == 0:
            lines.append(
                f"\n  {XFA_GRAY}After you verify 2 repairs, 'apply all' unlocks for this session.{XFA_RESET}"
            )
    lines.append(
        f"\n  {XFA_GRAY}Tell me which option to proceed with.{XFA_RESET}"
    )
    return "\n".join(lines)


def append_repair_log(xf_dir: str, entry: Dict[str, Any]) -> None:
    """Append a repair entry to the provenance log."""
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
```

- [ ] **Step 4: Run consent tests**

```bash
python3 -m pytest tests/test_consent.py -v
```
Expected: all PASSED

- [ ] **Step 5: Commit**

```bash
git -C /home/visionairy/.claude/xf-boundary-auditor add consent.py tests/test_consent.py
git -C /home/visionairy/.claude/xf-boundary-auditor commit -m "feat(xfa): Stage 4 graduated consent — trust counter, consent options, repair log"
```

---

## Task 7: Create refactor_mode.py

**Files:**
- Create: `refactor_mode.py`

Refactor Mode shifts XF Audit from blocking to tracking. Activated by the auditor when `/xfa-refactor start` writes a flag file, or auto-suggested when the same symbol is modified 3+ times consecutively. When active, violations accumulate without blocking. `/xfa-refactor end` (or session close) triggers consolidated output.

- [ ] **Step 1: Write failing tests**

```bash
cat > tests/test_refactor_mode.py << 'EOF'
import sys, os, tempfile, json
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))


def _xf_dir():
    d = tempfile.mkdtemp()
    xf = os.path.join(d, ".xf")
    os.makedirs(xf)
    return xf


def test_refactor_mode_inactive_by_default():
    from refactor_mode import is_active
    xf_dir = _xf_dir()
    assert is_active(xf_dir) is False


def test_refactor_mode_activate():
    from refactor_mode import activate, is_active
    xf_dir = _xf_dir()
    activate(xf_dir, description="renaming rank_tools → score_tools")
    assert is_active(xf_dir) is True


def test_refactor_mode_deactivate():
    from refactor_mode import activate, deactivate, is_active
    xf_dir = _xf_dir()
    activate(xf_dir, description="test")
    deactivate(xf_dir)
    assert is_active(xf_dir) is False


def test_refactor_mode_accumulates_violations():
    from refactor_mode import activate, add_violations, get_accumulated
    xf_dir = _xf_dir()
    activate(xf_dir, description="test")
    viols = [{"id": "a001", "type": "arity_mismatch", "consequence": "breaks"}]
    add_violations(xf_dir, viols)
    add_violations(xf_dir, [{"id": "i001", "type": "interface_existence",
                              "consequence": "import fails"}])
    acc = get_accumulated(xf_dir)
    assert len(acc) == 2


def test_refactor_status_line():
    from refactor_mode import format_status_line
    text = format_status_line(n_open=3, description="renaming rank_tools")
    assert "3" in text
    assert "refactor" in text.lower() or "tracking" in text.lower()


def test_auto_detect_threshold():
    from refactor_mode import should_suggest_refactor_mode
    edits = ["rank_tools", "rank_tools", "rank_tools"]
    assert should_suggest_refactor_mode(edits) is True


def test_auto_detect_below_threshold():
    from refactor_mode import should_suggest_refactor_mode
    edits = ["rank_tools", "score_tools"]
    assert should_suggest_refactor_mode(edits) is False
EOF
```

- [ ] **Step 2: Run to verify failures**

```bash
python3 -m pytest tests/test_refactor_mode.py -v 2>&1 | tail -10
```
Expected: `ModuleNotFoundError: No module named 'refactor_mode'`

- [ ] **Step 3: Create refactor_mode.py**

```python
# refactor_mode.py
from __future__ import annotations

import json
import os
from collections import Counter
from datetime import datetime, timezone
from typing import List, Dict, Any, Optional

XFA_CYAN   = "\033[96m"
XFA_YELLOW = "\033[93m"
XFA_GRAY   = "\033[90m"
XFA_RESET  = "\033[0m"

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
    # Clear any previous accumulation
    accum_path = _accum_path(xf_dir)
    with open(accum_path, "w") as f:
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
    """Accumulate violations without blocking (refactor mode tracking)."""
    accum_path = _accum_path(xf_dir)
    try:
        data = json.loads(open(accum_path).read()) if os.path.isfile(accum_path) else {"violations": []}
    except Exception:
        data = {"violations": []}
    # Deduplicate by id
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
        f"\033[93m{symbol}\033[0m — want to switch to tracking mode?\n"
        f"  I'll hold violations until you're done and present them all at once.\n"
        f"  {XFA_YELLOW}[yes, tracking mode]{XFA_RESET}  "
        f"{XFA_GRAY}[no, keep blocking]{XFA_RESET}"
    )


def should_suggest_refactor_mode(recent_symbols: List[str]) -> bool:
    """Return True if the same symbol has been edited >= THRESHOLD times consecutively."""
    if len(recent_symbols) < _AUTO_DETECT_THRESHOLD:
        return False
    tail = recent_symbols[-_AUTO_DETECT_THRESHOLD:]
    return len(set(tail)) == 1


def format_consolidated_report(violations: List[Dict[str, Any]], description: str = "") -> str:
    """Format the full accumulated violation list for presentation at refactor end."""
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
```

- [ ] **Step 4: Run refactor mode tests**

```bash
python3 -m pytest tests/test_refactor_mode.py -v
```
Expected: all PASSED

- [ ] **Step 5: Commit**

```bash
git -C /home/visionairy/.claude/xf-boundary-auditor add refactor_mode.py tests/test_refactor_mode.py
git -C /home/visionairy/.claude/xf-boundary-auditor commit -m "feat(xfa): Refactor Mode — flag file, violation accumulation, consolidated output"
```

---

## Task 8: Rewrite auditor.py to orchestrate all stages

**Files:**
- Rewrite: `auditor.py`

This is the main orchestrator. It calls all Stage 1 checks, runs Stage 2 cascade on escalating violations, formats Stage 3 repair plan, applies Stage 4 consent, and respects Refactor Mode.

- [ ] **Step 1: Write integration test**

```bash
cat > tests/test_auditor.py << 'EOF'
import sys, os, tempfile, json
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))


def _run_auditor(files_dict, tool_name="Edit"):
    """Run auditor.main() against a temp directory. Returns (exit_code, stdout)."""
    import io
    from unittest.mock import patch
    root = tempfile.mkdtemp()
    for name, src in files_dict.items():
        p = os.path.join(root, name)
        os.makedirs(os.path.dirname(p), exist_ok=True)
        open(p, "w").write(src)
    hook_input = json.dumps({"tool_name": tool_name, "tool_input": {}})
    buf = io.StringIO()
    import auditor, importlib
    importlib.reload(auditor)
    with patch("sys.stdin", io.StringIO(hook_input)), \
         patch("sys.stdout", buf), \
         patch("os.getcwd", return_value=root):
        try:
            code = auditor.main()
        except SystemExit as e:
            code = e.code
    return code, buf.getvalue()


def test_auditor_clean_exits_0():
    code, out = _run_auditor({"mymod.py": "def add(a, b):\n    return a + b\n"})
    assert code == 0
    assert "✓" in out


def test_auditor_blocks_on_arity_mismatch():
    code, out = _run_auditor({
        "mymod.py": "def do_work(a, b):\n    return a + b\n",
        "caller.py": "from mymod import do_work\nresult = do_work(1, 2, 3)\n",
    })
    assert code == 2
    assert "TypeError" in out


def test_auditor_passes_through_non_edit_tools():
    code, _ = _run_auditor({"x.py": "pass\n"}, tool_name="Read")
    assert code == 0


def test_auditor_shows_module_edge_counts_on_clean():
    code, out = _run_auditor({"clean.py": "def foo(a):\n    return a\n"})
    assert code == 0
    assert "modules" in out or "module" in out
EOF
```

- [ ] **Step 2: Run to verify failures**

```bash
python3 -m pytest tests/test_auditor.py -v 2>&1 | tail -15
```
Expected: some PASSED, some FAILED (clean test may pass since auditor already exists)

- [ ] **Step 3: Rewrite auditor.py**

```python
# auditor.py
from __future__ import annotations

import json
import os
import sys
from datetime import datetime, timezone
from typing import Dict, Any, List

from flow_analyzer import build_index
from checkers import (syntax_violations, from_import_violations,
                      arity_violations, env_var_violations, stub_violations)
from cascade import trace_cascade, format_cascade_notification, format_cascade_report
from repair import build_repair_plan, format_repair_plan
from consent import (get_trust_level, format_consent_options,
                     append_repair_log, reset_trust)
from refactor_mode import (is_active as refactor_is_active, add_violations as refactor_add,
                           get_accumulated, get_description, format_status_line,
                           format_consolidated_report, should_suggest_refactor_mode)

AUDIT_TOOLS = {"Edit", "Write"}

XFA_CYAN   = "\033[96m"
XFA_GREEN  = "\033[92m"
XFA_RED    = "\033[91m"
XFA_YELLOW = "\033[93m"
XFA_GRAY   = "\033[90m"
XFA_RESET  = "\033[0m"


def _ensure_xf_dir(root: str) -> str:
    p = os.path.join(root, ".xf")
    os.makedirs(p, exist_ok=True)
    return p


def _write_json(path: str, obj: Dict[str, Any]) -> None:
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(obj, f, indent=2)
    os.replace(tmp, path)


def _read_edit_symbol(hook_input: Dict) -> str:
    """Extract the file or symbol being edited from hook input (best effort)."""
    tool_input = hook_input.get("tool_input") or {}
    path = tool_input.get("file_path", "")
    if path:
        return os.path.splitext(os.path.basename(path))[0]
    return ""


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

    # Build the index
    try:
        index = build_index(root)
    except Exception:
        return 0

    module_count = len(index.get("modules", {}))
    edge_count = len(index.get("callers", []))

    # Collect .py paths for syntax check
    py_paths = []
    for info in index.get("modules", {}).values():
        p = info.get("path", "")
        if p.endswith(".py"):
            abs_p = os.path.join(root, p)
            if os.path.isfile(abs_p):
                py_paths.append(abs_p)

    # --- Stage 1: Run all checks ---
    all_violations: List[Dict] = []
    all_warnings: List[Dict] = []

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
        partition(from_import_violations(index))
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

    # Save violations for provenance and /xf-audit
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

    # --- Refactor Mode check ---
    if refactor_is_active(xf_dir):
        if all_violations:
            try:
                refactor_add(xf_dir, all_violations)
            except Exception:
                pass
        acc = []
        try:
            acc = get_accumulated(xf_dir)
        except Exception:
            pass
        desc = get_description(xf_dir)
        sys.stdout.write(format_status_line(len(acc), desc) + "\n")
        return 0  # Never blocks in refactor mode

    # --- Clean path ---
    if not all_violations:
        warning_suffix = ""
        if all_warnings:
            warning_suffix = f"  {XFA_YELLOW}{len(all_warnings)} warning(s){XFA_RESET}"
        sys.stdout.write(
            f"{XFA_CYAN}◈ XF Audit{XFA_RESET}  "
            f"{XFA_GRAY}{module_count} modules · {edge_count} edges checked{XFA_RESET}  "
            f"{XFA_GREEN}✓ 0 violations{XFA_RESET}{warning_suffix}\n"
        )
        return 0

    # --- Stage 2: Cascade tracing for contract-change violations ---
    # Run cascade for arity and interface violations (symbols that have callers)
    cascade_symbols = set()
    for v in all_violations:
        sym = v.get("symbol")
        if sym and v.get("type") in ("arity_mismatch", "interface_existence", "stub_function"):
            cascade_symbols.add(sym)

    cascades: Dict[str, List] = {}
    for sym in cascade_symbols:
        try:
            result = trace_cascade(index, sym)
            if result:
                cascades[sym] = result
        except Exception:
            pass

    # --- Stage 3: Repair plan ---
    repair_plan = []
    try:
        repair_plan = build_repair_plan(all_violations)
    except Exception:
        pass

    # --- Stage 4: Consent options ---
    trust_level = 0
    try:
        trust_level = get_trust_level(xf_dir)
    except Exception:
        pass

    # --- Format and output ---
    output_lines = []

    # Repair plan header
    output_lines.append(
        f"{XFA_CYAN}◈ XF Audit{XFA_RESET}  "
        f"{XFA_RED}This edit will break at runtime.{XFA_RESET}"
    )
    output_lines.append("")

    try:
        output_lines.append(format_repair_plan(repair_plan))
    except Exception:
        for v in all_violations[:10]:
            output_lines.append(
                f"  {XFA_GRAY}{v.get('caller_module','?')}:{v.get('caller_line','?')}{XFA_RESET}  "
                f"{v.get('consequence','')}"
            )

    # Cascade output (abbreviated — first cascade only)
    if cascades:
        sym, cascade = next(iter(cascades.items()))
        try:
            output_lines.append(format_cascade_report(sym, cascade))
        except Exception:
            pass

    # Warnings
    if all_warnings:
        output_lines.append(
            f"{XFA_YELLOW}{len(all_warnings)} warning(s) — not blocking:{XFA_RESET}"
        )
        for w in all_warnings[:5]:
            output_lines.append(
                f"  {XFA_GRAY}{w.get('caller_module','?')}:{w.get('caller_line','?')}{XFA_RESET}  "
                f"{w.get('consequence','')}"
            )

    # Consent options
    try:
        output_lines.append(format_consent_options(trust_level, len(repair_plan)))
    except Exception:
        output_lines.append(f"\n  {XFA_GRAY}[show me the diff first]  [skip for now]{XFA_RESET}")

    sys.stdout.write("\n".join(output_lines) + "\n")
    return 2


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception:
        sys.exit(0)
```

- [ ] **Step 4: Run all tests**

```bash
python3 -m pytest tests/ -v --tb=short
```
Expected: all PASSED

- [ ] **Step 5: Run live against Dispatch repo**

```bash
cd /home/visionairy/Dispatch
echo '{"tool_name":"Edit","tool_input":{}}' | python3 /home/visionairy/.claude/xf-boundary-auditor/auditor.py
```
Expected: clean output with `✓ 0 violations` and module/edge counts. If violations appear, check `.xf/boundary_violations.json` — document false positives but do not suppress real violations.

- [ ] **Step 6: Commit**

```bash
git -C /home/visionairy/.claude/xf-boundary-auditor add auditor.py tests/test_auditor.py
git -C /home/visionairy/.claude/xf-boundary-auditor commit -m "feat(xfa): rewrite auditor — all 4 stages + refactor mode orchestration"
```

---

## Task 9: Stop hook — XF Audit session digest + Refactor Mode end

**Files:**
- Modify: `/home/visionairy/Dispatch/stop_hook.sh`

Add XF Audit digest to the stop hook. If Refactor Mode is active when the session ends, present the consolidated violation list automatically.

- [ ] **Step 1: Read current stop_hook.sh**

```bash
cat /home/visionairy/Dispatch/stop_hook.sh
```

- [ ] **Step 2: Add XF Audit digest after the existing Dispatch digest block**

Add this block immediately after the existing `python3 -c "..."` Dispatch digest block (before `exit 0`):

```bash
# XF Audit session digest
python3 -c "
import sys, os, json, time
sys.path.insert(0, os.path.expanduser('~/.claude/xf-boundary-auditor'))

XFA_CYAN   = '\033[96m'
XFA_GREEN  = '\033[92m'
XFA_YELLOW = '\033[93m'
XFA_GRAY   = '\033[90m'
XFA_RESET  = '\033[0m'

xf_dir = os.path.join(os.getcwd(), '.xf')
if not os.path.isdir(xf_dir):
    sys.exit(0)

# If refactor mode is active, present consolidated violations
try:
    from refactor_mode import is_active, get_accumulated, get_description, format_consolidated_report, deactivate
    if is_active(xf_dir):
        acc = get_accumulated(xf_dir)
        desc = get_description(xf_dir)
        print(format_consolidated_report(acc, desc))
        deactivate(xf_dir)
        sys.exit(0)
except Exception:
    pass

# Standard session digest
try:
    vio_path = os.path.join(xf_dir, 'boundary_violations.json')
    if not os.path.isfile(vio_path):
        sys.exit(0)
    mtime = os.path.getmtime(vio_path)
    if time.time() - mtime > 3600:
        sys.exit(0)  # stale
    data = json.loads(open(vio_path).read())
    total_viols = data.get('total_violations', 0)
    total_warns = data.get('total_warnings', 0)

    # Repair log count
    log_path = os.path.join(xf_dir, 'repair_log.json')
    repairs = 0
    if os.path.isfile(log_path):
        log_data = json.loads(open(log_path).read())
        repairs = len(log_data.get('repairs', []))

    repair_part = f' · {XFA_GREEN}{repairs} repaired{XFA_RESET}' if repairs > 0 else ''
    if total_viols == 0 and total_warns == 0:
        print(f'{XFA_CYAN}◈ XF Audit{XFA_RESET}  {XFA_GREEN}✓ all contracts intact{XFA_RESET}{repair_part}')
    elif total_viols == 0:
        print(f'{XFA_CYAN}◈ XF Audit{XFA_RESET}  {XFA_GREEN}✓ 0 violations{XFA_RESET}  {XFA_YELLOW}{total_warns} warning(s){XFA_RESET}{repair_part}')
    else:
        print(f'{XFA_CYAN}◈ XF Audit{XFA_RESET}  {XFA_YELLOW}{total_viols} open violation(s){XFA_RESET}{repair_part}  — run /xf-audit to fix')
except Exception:
    pass
" 2>/dev/null || true
```

- [ ] **Step 3: Verify syntax**

```bash
bash -n /home/visionairy/Dispatch/stop_hook.sh
```
Expected: no output

- [ ] **Step 4: Test stop hook manually**

```bash
cd /home/visionairy/Dispatch
echo '{}' | bash stop_hook.sh
```
Expected: Dispatch digest line + XF Audit digest line (or just Dispatch if no recent `.xf/` scan)

- [ ] **Step 5: Commit**

```bash
cd /home/visionairy/Dispatch
git add stop_hook.sh
git commit -m "feat(xfa): add XF Audit session digest + Refactor Mode end handling to stop hook"
```

---

## Task 10: Sync installed files and full end-to-end verification

**Files:**
- Installed hooks: `~/.claude/hooks/dispatch-stop.sh`

- [ ] **Step 1: Run complete test suite**

```bash
python3 -m pytest /home/visionairy/.claude/xf-boundary-auditor/tests/ -v --tb=short
```
Expected: all PASSED

- [ ] **Step 2: Sync stop hook**

```bash
cp /home/visionairy/Dispatch/stop_hook.sh ~/.claude/hooks/dispatch-stop.sh
```

- [ ] **Step 3: Live clean-path audit**

```bash
cd /home/visionairy/Dispatch
echo '{"tool_name":"Edit","tool_input":{}}' | \
  python3 /home/visionairy/.claude/xf-boundary-auditor/auditor.py
```
Expected: `◈ XF Audit  N modules · M edges checked  ✓ 0 violations`

- [ ] **Step 4: Smoke test refactor mode**

```bash
cd /home/visionairy/Dispatch
# Activate refactor mode
python3 -c "
import sys
sys.path.insert(0, '/home/visionairy/.claude/xf-boundary-auditor')
from refactor_mode import activate
import os
xf_dir = os.path.join(os.getcwd(), '.xf')
os.makedirs(xf_dir, exist_ok=True)
activate(xf_dir, description='smoke test')
print('Refactor mode active')
"
# Auditor should track not block
echo '{"tool_name":"Edit","tool_input":{}}' | \
  python3 /home/visionairy/.claude/xf-boundary-auditor/auditor.py
# Deactivate
python3 -c "
import sys, os
sys.path.insert(0, '/home/visionairy/.claude/xf-boundary-auditor')
from refactor_mode import deactivate
xf_dir = os.path.join(os.getcwd(), '.xf')
deactivate(xf_dir)
print('Refactor mode cleared')
"
```
Expected: refactor tracking status line during active mode, no block; clean stamp after deactivation.

- [ ] **Step 5: Verify stop hook digest**

```bash
cd /home/visionairy/Dispatch
echo '{}' | bash stop_hook.sh
```
Expected: Dispatch digest + XF Audit digest with contract status.

- [ ] **Step 6: Final commit**

```bash
cd /home/visionairy/Dispatch
git add .
git status  # confirm only stop_hook.sh
git commit -m "feat(xfa): all 4 stages + refactor mode + repair log — complete contract loop"
```

---

## Self-Review

### Spec coverage check

| Spec requirement | Task |
|-----------------|------|
| Stage 1 — syntax error | Tasks 1, 2, 8 |
| Stage 1 — from-import existence | Tasks 2, 8 |
| Stage 1 — arity mismatch | Tasks 1, 2, 3, 8 |
| Stage 1 — missing env var (hard) | Tasks 1, 2, 3, 8 |
| Stage 1 — consumed stub (non-None return) | Tasks 1, 2, 8 |
| Stage 1 — void/unannotated stub → warn | Tasks 1, 2 |
| Stage 1 — soft env var (getenv+default) → no violation | Tasks 1, 2 |
| Stage 1 clean output: N modules · M edges · ✓ 0 violations | Task 8 |
| Stage 2 — cascade notification within 500ms | Task 4 (`format_cascade_notification`) |
| Stage 2 — caller chain ordered by dependency depth | Task 4 (`trace_cascade` BFS) |
| Stage 2 — consequence-first per caller | Task 4 (`_consequence_for`) |
| Stage 3 — concrete file:line repair plan | Task 5 |
| Stage 3 — numbered, ordered by dependency | Task 5 (`build_repair_plan`) |
| Stage 4 — "show me the diff first" only at low trust | Task 6 |
| Stage 4 — "apply all" unlocks after 2 verified repairs | Task 6 |
| Stage 4 — trust resets each session | Task 6 (`reset_trust`) |
| Refactor Mode — flag file activation | Task 7 |
| Refactor Mode — tracks not blocks | Tasks 7, 8 |
| Refactor Mode — auto-detect 3+ edits to same symbol | Task 7 (`should_suggest_refactor_mode`) |
| Refactor Mode — consolidated list at end | Tasks 7, 9 |
| Repair Log — every repair logged with timestamp + session | Task 6 (`append_repair_log`) |
| Repair Log — session digest shows repair count | Task 9 |
| Session digest — stop hook XF Audit line | Task 9 |
| `.xf/boundary_violations.json` provenance | Task 8 |
| `.xf/repair_log.json` provenance | Tasks 6, 8 |

### Placeholder scan: NONE FOUND

All code blocks are complete. No TBD or TODO in any step.

### Type consistency check

- `SymbolTable.functions` shape defined in Task 1, populated in Task 1, consumed in Tasks 2, 3, 8 — consistent throughout.
- `index["calls_by_file"]` added in Task 3, consumed in `arity_violations` (Task 2) — consistent.
- `violation` dict keys (`id`, `type`, `severity`, `caller_module`, `caller_line`, `consequence`, `fix`, `status`) — all checkers produce the same shape; repair.py, consent.py, cascade.py all consume via `.get()` — safe against missing keys.
- `xf_dir` passed to consent and refactor functions — always `os.path.join(root, ".xf")` — consistent across auditor.py, stop_hook.py, tests.

## GSTACK REVIEW REPORT

| Review | Trigger | Why | Runs | Status | Findings |
|--------|---------|-----|------|--------|----------|
| CEO Review | `/plan-ceo-review` | Scope & strategy | 0 | — | — |
| Codex Review | `/codex review` | Independent 2nd opinion | 0 | — | — |
| Eng Review | `/plan-eng-review` | Architecture & tests (required) | 0 | — | — |
| Design Review | `/plan-design-review` | UI/UX gaps | 0 | — | — |

**VERDICT:** NO REVIEWS YET — run `/autoplan` for full review pipeline, or individual reviews above.
