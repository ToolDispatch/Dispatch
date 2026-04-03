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
    assert plan[0]["id"] in ("a001", "i001")


def test_repair_plan_errors_before_warnings():
    from repair import build_repair_plan
    viols = [
        {"id": "b001", "type": "stub_function", "severity": "warning",
         "caller_module": "a.py", "caller_line": 1, "symbol": "init",
         "consequence": "Stub.", "fix": "Implement.", "status": "open"},
        {"id": "a001", "type": "arity_mismatch", "severity": "error",
         "caller_module": "b.py", "caller_line": 5, "symbol": "foo",
         "consequence": "TypeError.", "fix": "Fix.", "status": "open"},
    ]
    plan = build_repair_plan(viols)
    assert plan[0]["severity"] == "error"
    assert plan[1]["severity"] == "warning"


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
    assert "1." in text


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


def test_generate_diff_returns_diff():
    import tempfile
    from repair import generate_diff
    with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False) as f:
        f.write("result = do_work(1, 2, 3)\n")
        path = f.name
    try:
        diff = generate_diff(path, 1, "do_work(1, 2, 3)", "do_work(1, 2)")
        assert diff is not None
        assert "do_work" in diff
    finally:
        os.unlink(path)
