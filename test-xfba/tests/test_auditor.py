import sys, os, tempfile, json
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))


def _run_auditor(files_dict, tool_name="Edit"):
    """Run auditor.main() against a temp directory. Returns (exit_code, combined stdout+stderr)."""
    import io
    from unittest.mock import patch
    root = tempfile.mkdtemp()
    for name, src_content in files_dict.items():
        p = os.path.join(root, name)
        os.makedirs(os.path.dirname(p), exist_ok=True)
        open(p, "w").write(src_content)
    hook_input = json.dumps({"tool_name": tool_name, "tool_input": {}})
    buf_out = io.StringIO()
    buf_err = io.StringIO()
    import auditor, importlib
    importlib.reload(auditor)
    with patch("sys.stdin", io.StringIO(hook_input)), \
         patch("sys.stdout", buf_out), \
         patch("sys.stderr", buf_err), \
         patch("os.getcwd", return_value=root):
        try:
            code = auditor.main()
        except SystemExit as e:
            code = e.code
    return code, buf_out.getvalue() + buf_err.getvalue()


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
    assert "module" in out.lower()


def test_auditor_exits_0_on_malformed_stdin():
    import io
    from unittest.mock import patch
    import auditor, importlib
    importlib.reload(auditor)
    buf = io.StringIO()
    with patch("sys.stdin", io.StringIO("not json {")), \
         patch("sys.stdout", buf):
        try:
            code = auditor.main()
        except SystemExit as e:
            code = e.code
    assert code == 0


# --- Fix 3: trust increments when violation resolved ---

def test_trust_increments_when_violation_resolved():
    """Running twice — first with violation, then clean — should increment trust."""
    import io
    from unittest.mock import patch
    import auditor, importlib

    # First run: arity violation (caller.py calls do_work with 3 args, takes 2)
    root = tempfile.mkdtemp()
    files_v1 = {
        "mymod.py": "def do_work(a, b):\n    return a + b\n",
        "caller.py": "from mymod import do_work\nresult = do_work(1, 2, 3)\n",
    }
    for name, src in files_v1.items():
        open(os.path.join(root, name), "w").write(src)

    xf_dir = os.path.join(root, ".xf")
    os.makedirs(xf_dir, exist_ok=True)

    hook_input = json.dumps({"tool_name": "Edit", "tool_input": {}})
    importlib.reload(auditor)
    buf = io.StringIO()
    with patch("sys.stdin", io.StringIO(hook_input)), \
         patch("sys.stdout", buf), \
         patch("os.getcwd", return_value=root):
        code1 = auditor.main()
    assert code1 == 2  # should block

    # Second run: violation fixed (correct call)
    files_v2 = {
        "mymod.py": "def do_work(a, b):\n    return a + b\n",
        "caller.py": "from mymod import do_work\nresult = do_work(1, 2)\n",
    }
    for name, src in files_v2.items():
        open(os.path.join(root, name), "w").write(src)

    # Also invalidate cache by touching files
    import time
    time.sleep(0.01)
    for name in files_v2:
        p = os.path.join(root, name)
        os.utime(p, None)

    importlib.reload(auditor)
    buf2 = io.StringIO()
    with patch("sys.stdin", io.StringIO(hook_input)), \
         patch("sys.stdout", buf2), \
         patch("os.getcwd", return_value=root):
        code2 = auditor.main()
    assert code2 == 0  # should pass clean

    # Trust should have incremented on second run
    from consent import get_trust_level
    trust = get_trust_level(xf_dir)
    assert trust >= 1, f"Expected trust >= 1 after resolving a violation, got {trust}"


# --- Fix 12: _run_check logs to stderr instead of silent swallow ---

def test_run_check_logs_exception_to_stderr():
    """_run_check should log checker failures to stderr and return [] instead of crashing."""
    import io
    from unittest.mock import patch
    import auditor, importlib
    importlib.reload(auditor)

    def bad_checker(*args):
        raise RuntimeError("simulated checker failure")

    stderr_buf = io.StringIO()
    with patch("sys.stderr", stderr_buf):
        result = auditor._run_check(bad_checker, name="test_check")

    assert result == []
    assert "test_check" in stderr_buf.getvalue()
    assert "simulated checker failure" in stderr_buf.getvalue()


# --- Fix 11: colors.py exports correct constants ---

def test_colors_module_exports():
    """colors.py should export all six ANSI color constants."""
    import colors
    for const in ("XFA_CYAN", "XFA_GREEN", "XFA_RED", "XFA_YELLOW", "XFA_GRAY", "XFA_RESET"):
        val = getattr(colors, const, None)
        assert val is not None, f"colors.{const} missing"
        assert "\033[" in val, f"colors.{const} does not look like an ANSI code: {repr(val)}"
