import os, sys, json, tempfile, pytest
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from consent import format_consent_options, format_diff_view, append_repair_log


def test_consent_options_contains_fix_problem():
    violations = [{"id": "a001", "type": "arity_mismatch", "caller_module": "caller.dart",
                   "caller_line": 47, "symbol": "greet",
                   "fix": "caller.dart:47 — remove 1 argument from the call to greet()",
                   "consequence": "TypeError when greet() runs."}]
    repair = [{"id": "a001", "file": "caller.dart", "line": 47,
               "description": "remove 1 argument", "diff": "-greet('a','b','c')\n+greet('a','b')"}]
    out = format_consent_options(violations, repair, trust_level=0)
    assert "Fix problem" in out
    assert "Show diff" in out


def test_consent_options_not_apply_all():
    violations = [{"id": "a001", "type": "arity_mismatch", "caller_module": "caller.dart",
                   "caller_line": 47, "symbol": "greet",
                   "fix": "caller.dart:47 — remove 1 argument",
                   "consequence": "TypeError."}]
    repair = [{"id": "a001", "file": "caller.dart", "line": 47,
               "description": "remove 1 argument", "diff": "-foo(1,2,3)\n+foo(1,2)"}]
    out = format_consent_options(violations, repair, trust_level=0)
    assert "apply all" not in out.lower()


def test_diff_view_shows_diff():
    repair = [{"id": "a001", "file": "caller.dart", "line": 47,
               "description": "remove 1 argument from greet()",
               "diff": "-greet('Alice', 'Hi', True)\n+greet('Alice', 'Hi')"}]
    out = format_diff_view(repair)
    assert "caller.dart" in out
    assert "-greet" in out
    assert "+greet" in out


def test_diff_view_contains_apply_fix():
    repair = [{"id": "a001", "file": "caller.dart", "line": 47,
               "description": "remove 1 argument", "diff": "-foo(1,2,3)\n+foo(1,2)"}]
    out = format_diff_view(repair)
    assert "Apply fix" in out
    assert "I'll handle it" in out


def test_repair_log_accepted_field():
    with tempfile.TemporaryDirectory() as d:
        xf_dir = os.path.join(d, ".xf")
        os.makedirs(xf_dir)
        violation = {"id": "a001", "type": "arity_mismatch", "caller_module": "f.dart",
                     "caller_line": 10, "symbol": "foo", "consequence": "err", "fix": "remove arg"}
        repair = {"description": "remove arg from foo()", "file": "f.dart", "line": 10, "diff": ""}
        append_repair_log(xf_dir, violation, repair, accepted=True)
        log_path = os.path.join(xf_dir, "repair_log.json")
        entries = json.loads(open(log_path).read())
        assert entries[-1]["accepted"] is True


def test_repair_log_not_accepted():
    with tempfile.TemporaryDirectory() as d:
        xf_dir = os.path.join(d, ".xf")
        os.makedirs(xf_dir)
        violation = {"id": "a001", "type": "arity_mismatch", "caller_module": "f.dart",
                     "caller_line": 10, "symbol": "foo", "consequence": "err", "fix": "remove arg"}
        repair = {"description": "remove arg", "file": "f.dart", "line": 10, "diff": ""}
        append_repair_log(xf_dir, violation, repair, accepted=False)
        log_path = os.path.join(xf_dir, "repair_log.json")
        entries = json.loads(open(log_path).read())
        assert entries[-1]["accepted"] is False


def test_ralph_loop_promise_in_fix_output():
    violations = [{"id": "a001", "type": "arity_mismatch", "caller_module": "caller.dart",
                   "caller_line": 47, "symbol": "greet",
                   "fix": "caller.dart:47 — remove 1 argument",
                   "consequence": "TypeError."}]
    repair = [{"id": "a001", "file": "caller.dart", "line": 47,
               "description": "remove 1 argument", "diff": "-greet(a,b,c)\n+greet(a,b)"}]
    out = format_consent_options(violations, repair, trust_level=0)
    assert "XFBA_CLEAN" in out
