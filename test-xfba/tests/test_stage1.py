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


# --- Stage 1 checker tests ---

import tempfile as _tempfile


def test_syntax_check_catches_error():
    from checkers import syntax_violations
    with _tempfile.NamedTemporaryFile(suffix=".py", mode="w", delete=False) as f:
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
    with _tempfile.NamedTemporaryFile(suffix=".py", mode="w", delete=False) as f:
        f.write("def foo():\n    return 1\n")
        path = f.name
    try:
        assert syntax_violations([path]) == []
    finally:
        os.unlink(path)


def _build(files_dict):
    """Write files to a temp dir and return (root, index)."""
    from flow_analyzer import build_index
    root = _tempfile.mkdtemp()
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
    # Manually build calls_by_file since flow_analyzer doesn't yet (Task 3)
    # The arity checker reads from index["calls_by_file"]
    # Inject it directly for this test
    from scanner_python import PythonScanner
    caller_path = os.path.join(root, "caller.py")
    st = PythonScanner().scan(caller_path)
    idx["calls_by_file"] = {"caller.py": st.calls}
    idx["modules"]["mymod"]["functions"] = {"do_work": {
        "n_required": 2, "n_total": 2, "has_varargs": False,
        "has_varkw": False, "return_annotation": None, "is_stub": False, "line": 1,
    }}
    viols = arity_violations(idx)
    assert len(viols) == 1
    assert viols[0]["type"] == "arity_mismatch"
    assert viols[0]["n_args_passed"] == 3
    assert viols[0]["n_args_accepted"] == 2
    assert "TypeError" in viols[0]["consequence"]


def test_arity_no_violation_correct_count():
    from checkers import arity_violations
    root, idx = _build({
        "mymod.py": "def do_work(a, b):\n    return a + b\n",
        "caller.py": "result = do_work(1, 2)\n",
    })
    from scanner_python import PythonScanner
    st = PythonScanner().scan(os.path.join(root, "caller.py"))
    idx["calls_by_file"] = {"caller.py": st.calls}
    idx["modules"]["mymod"]["functions"] = {"do_work": {
        "n_required": 2, "n_total": 2, "has_varargs": False,
        "has_varkw": False, "return_annotation": None, "is_stub": False, "line": 1,
    }}
    assert arity_violations(idx) == []


def test_arity_no_violation_varargs():
    from checkers import arity_violations
    root, idx = _build({
        "mymod.py": "def collect(*args):\n    return args\n",
        "caller.py": "collect(1, 2, 3, 4, 5)\n",
    })
    from scanner_python import PythonScanner
    st = PythonScanner().scan(os.path.join(root, "caller.py"))
    idx["calls_by_file"] = {"caller.py": st.calls}
    idx["modules"]["mymod"]["functions"] = {"collect": {
        "n_required": 0, "n_total": 0, "has_varargs": True,
        "has_varkw": False, "return_annotation": None, "is_stub": False, "line": 1,
    }}
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
    # Inject functions and callers so the checker has what it needs
    idx["modules"]["provider"]["functions"] = {"get_name": {
        "n_required": 0, "n_total": 0, "has_varargs": False,
        "has_varkw": False, "return_annotation": "str", "is_stub": True, "line": 1,
    }}
    idx["callers"] = [{"caller": "consumer.py", "callee_module": "provider",
                       "symbol": "get_name", "line": 2}]
    viols = stub_violations(idx)
    errors = [v for v in viols if v["severity"] == "error"]
    assert len(errors) == 1
    assert errors[0]["symbol"] == "get_name"


def test_stub_warning_void():
    from checkers import stub_violations
    _, idx = _build({"setup.py": "def init():\n    pass\n"})
    idx["modules"]["setup"]["functions"] = {"init": {
        "n_required": 0, "n_total": 0, "has_varargs": False,
        "has_varkw": False, "return_annotation": None, "is_stub": True, "line": 1,
    }}
    idx["callers"] = []
    viols = stub_violations(idx)
    assert all(v["severity"] == "warning" for v in viols)


# --- Fix 6: arity under-supply (too few args) ---

def test_arity_violation_too_few_args():
    """Calling a function with fewer args than required should produce a violation."""
    from checkers import arity_violations
    root, idx = _build({
        "mymod.py": "def greet(name, greeting):\n    return f'{greeting} {name}'\n",
        "caller.py": "from mymod import greet\nresult = greet('Alice')\n",
    })
    from scanner_python import PythonScanner
    caller_path = os.path.join(root, "caller.py")
    st = PythonScanner().scan(caller_path)
    idx["calls_by_file"] = {"caller.py": st.calls}
    # Inject function with 2 required args
    mod_key = [k for k in idx["modules"] if "mymod" in k][0]
    idx["modules"][mod_key]["functions"] = {"greet": {
        "n_required": 2, "n_total": 2, "has_varargs": False,
        "has_varkw": False, "return_annotation": None, "is_stub": False, "line": 1,
    }}
    viols = arity_violations(idx)
    assert len(viols) == 1
    assert viols[0]["type"] == "arity_mismatch"
    assert viols[0]["n_args_passed"] == 1
    assert "TypeError" in viols[0]["consequence"]
    assert "requires at least 2" in viols[0]["consequence"]


def test_arity_no_violation_between_required_and_total():
    """Calling with optional args filled should not violate."""
    from checkers import arity_violations
    root, idx = _build({
        "mymod.py": "def greet(name, greeting='Hello'):\n    return f'{greeting} {name}'\n",
        "caller.py": "from mymod import greet\nresult = greet('Alice')\n",
    })
    from scanner_python import PythonScanner
    st = PythonScanner().scan(os.path.join(root, "caller.py"))
    idx["calls_by_file"] = {"caller.py": st.calls}
    mod_key = [k for k in idx["modules"] if "mymod" in k][0]
    idx["modules"][mod_key]["functions"] = {"greet": {
        "n_required": 1, "n_total": 2, "has_varargs": False,
        "has_varkw": False, "return_annotation": None, "is_stub": False, "line": 1,
    }}
    assert arity_violations(idx) == []


# ---------- silent_except_violations ----------

def _write_py(src: str) -> str:
    """Write src to a temp .py file, return path."""
    with _tempfile.NamedTemporaryFile(suffix=".py", mode="w", delete=False, encoding="utf-8") as f:
        f.write(textwrap.dedent(src))
        return f.name


def test_silent_except_pass():
    from checkers import silent_except_violations
    path = _write_py("""
        def foo():
            try:
                risky()
            except Exception:
                pass
    """)
    try:
        viols = silent_except_violations([path])
        assert len(viols) == 1
        assert viols[0]["type"] == "silent_exception"
        assert viols[0]["severity"] == "warning"
        assert "pass only" in viols[0]["consequence"]
    finally:
        os.unlink(path)


def test_silent_except_return_default():
    from checkers import silent_except_violations
    path = _write_py("""
        def foo():
            try:
                return risky()
            except Exception:
                return ""
    """)
    try:
        viols = silent_except_violations([path])
        assert len(viols) == 1
        assert viols[0]["type"] == "silent_exception"
    finally:
        os.unlink(path)


def test_silent_except_print_then_return():
    from checkers import silent_except_violations
    path = _write_py("""
        def foo():
            try:
                risky()
            except Exception as e:
                print(f"WARNING: {e}")
                return []
    """)
    try:
        viols = silent_except_violations([path])
        assert len(viols) == 1
        assert "invisible" in viols[0]["consequence"]
    finally:
        os.unlink(path)


def test_silent_except_not_flagged_when_reraises():
    from checkers import silent_except_violations
    path = _write_py("""
        def foo():
            try:
                risky()
            except Exception as e:
                raise RuntimeError("wrapped") from e
    """)
    try:
        assert silent_except_violations([path]) == []
    finally:
        os.unlink(path)


def test_silent_except_not_flagged_bare_raise():
    from checkers import silent_except_violations
    path = _write_py("""
        def foo():
            try:
                risky()
            except Exception:
                raise
    """)
    try:
        assert silent_except_violations([path]) == []
    finally:
        os.unlink(path)


def test_silent_except_not_flagged_sys_exit():
    from checkers import silent_except_violations
    path = _write_py("""
        import sys
        def foo():
            try:
                risky()
            except Exception as e:
                print(e)
                sys.exit(1)
    """)
    try:
        assert silent_except_violations([path]) == []
    finally:
        os.unlink(path)


def test_silent_except_multiple_handlers():
    from checkers import silent_except_violations
    path = _write_py("""
        def foo():
            try:
                risky()
            except ValueError:
                raise
            except Exception:
                return None
    """)
    try:
        viols = silent_except_violations([path])
        assert len(viols) == 1
        assert viols[0]["symbol"] == "Exception"
    finally:
        os.unlink(path)


def test_silent_except_exc_type_in_output():
    from checkers import silent_except_violations
    path = _write_py("""
        def foo():
            try:
                risky()
            except KeyError:
                return {}
    """)
    try:
        viols = silent_except_violations([path])
        assert len(viols) == 1
        assert viols[0]["symbol"] == "KeyError"
    finally:
        os.unlink(path)
