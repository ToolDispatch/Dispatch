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


def test_refactor_mode_deduplicates_violations():
    from refactor_mode import activate, add_violations, get_accumulated
    xf_dir = _xf_dir()
    activate(xf_dir, description="test")
    v = {"id": "a001", "type": "arity_mismatch", "consequence": "breaks"}
    add_violations(xf_dir, [v])
    add_violations(xf_dir, [v])  # same id — should not duplicate
    assert len(get_accumulated(xf_dir)) == 1


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


def test_consolidated_report_clean():
    from refactor_mode import format_consolidated_report
    text = format_consolidated_report([], "test rename")
    assert "intact" in text.lower() or "clean" in text.lower() or "complete" in text.lower()


def test_consolidated_report_with_violations():
    from refactor_mode import format_consolidated_report
    viols = [{"id": "a001", "caller_module": "a.py", "caller_line": 5,
               "consequence": "Will break.", "fix": "Fix the arg."}]
    text = format_consolidated_report(viols, "test rename")
    assert "a.py" in text
    assert "Will break" in text
