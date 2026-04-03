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


def test_cascade_report_no_callers():
    from cascade import format_cascade_report
    text = format_cascade_report("orphan", [])
    assert "orphan" in text
    assert "No callers" in text or "no caller" in text.lower()


def test_cascade_report_with_callers():
    from cascade import format_cascade_report
    cascade = [{"caller": "a.py", "line": 5, "depth": 1, "symbol": "foo",
                "consequence": "Will break."}]
    text = format_cascade_report("foo", cascade)
    assert "a.py" in text
    assert "foo" in text
