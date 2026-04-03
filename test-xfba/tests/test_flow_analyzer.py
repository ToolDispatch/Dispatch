import sys, os, tempfile, textwrap
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))


def _build(files_dict):
    from flow_analyzer import build_index
    root = tempfile.mkdtemp()
    for name, src in files_dict.items():
        p = os.path.join(root, name)
        os.makedirs(os.path.dirname(p), exist_ok=True)
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


def test_build_index_calls_by_file_uses_relative_path():
    root, idx = _build({"myfile.py": "foo(1, 2)\n"})
    # Keys should be relative paths, not absolute
    for key in idx["calls_by_file"]:
        assert not os.path.isabs(key), f"Expected relative path, got: {key}"


def test_build_index_functions_have_correct_signature():
    _, idx = _build({"mymod.py": "def greet(name, greeting='Hello'):\n    return greeting\n"})
    fn = idx["modules"]["mymod"]["functions"]["greet"]
    assert fn["n_required"] == 1
    assert fn["n_total"] == 2
    assert fn["is_stub"] is False


# --- Fix 2: path-based module keys (no collision for same-named files in subdirs) ---

def test_module_keys_are_path_based():
    """Two files named the same but in different dirs must get distinct keys."""
    root, idx = _build({
        "pkg/utils.py": "def helper():\n    pass\n",
        "other/utils.py": "def other_helper():\n    pass\n",
    })
    keys = list(idx["modules"].keys())
    # Both should be present as distinct keys
    assert len(keys) == 2
    assert not any(k == "utils" for k in keys), f"Bare module name found: {keys}"
    # Keys should contain the subdirectory
    assert any("pkg" in k for k in keys)
    assert any("other" in k for k in keys)


def test_from_imports_use_path_based_callee_key():
    """from_imports callee_module should resolve to path-based key, not bare name."""
    root, idx = _build({
        "mymod.py": "def do_work(a, b):\n    return a + b\n",
        "caller.py": "from mymod import do_work\nresult = do_work(1, 2)\n",
    })
    fi = idx.get("from_imports", [])
    assert len(fi) > 0
    callee = fi[0]["callee_module"]
    # Should be path-based key (e.g. "mymod"), not a bare basename that differs from path key
    assert callee in idx["modules"], f"callee_module '{callee}' not found in modules keys: {list(idx['modules'].keys())}"


# --- Fix 10: mtime-based index cache ---

def test_mtime_cache_is_written():
    """build_index should write an index_cache.json to the .xf dir."""
    root, idx = _build({"app.py": "def foo():\n    pass\n"})
    cache_path = os.path.join(root, ".xf", "index_cache.json")
    assert os.path.isfile(cache_path), "index_cache.json was not written"
    import json
    cached = json.loads(open(cache_path).read())
    assert "mtime_hash" in cached
    assert "index" in cached


def test_mtime_cache_returns_same_index_on_unchanged_files():
    """Second call with unchanged files should return cached result."""
    from flow_analyzer import build_index
    root = tempfile.mkdtemp()
    p = os.path.join(root, "app.py")
    open(p, "w").write("def foo():\n    pass\n")

    idx1 = build_index(root)
    idx2 = build_index(root)
    # Both should have same modules
    assert set(idx1["modules"].keys()) == set(idx2["modules"].keys())
