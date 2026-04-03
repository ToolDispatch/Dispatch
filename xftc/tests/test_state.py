import json
import os
import tempfile
import pytest
from unittest.mock import patch


def make_state_module(path):
    """Create a state module backed by a temp file."""
    import importlib.util, types
    src = f"""
import json, os, hashlib
from datetime import datetime, timezone

STATE_FILE = {repr(path)}

def load_state():
    if not os.path.exists(STATE_FILE):
        return {{}}
    try:
        with open(STATE_FILE) as f:
            return json.load(f)
    except Exception:
        return {{}}

def save_state(state):
    os.makedirs(os.path.dirname(STATE_FILE), exist_ok=True)
    with open(STATE_FILE, 'w') as f:
        json.dump(state, f, indent=2)

def get_tier():
    return load_state().get("tier", "free")

def get_session(session_id):
    return load_state().get("sessions", {{}}).get(session_id, {{}})

def update_session(session_id, updates):
    state = load_state()
    sessions = state.setdefault("sessions", {{}})
    session = sessions.setdefault(session_id, {{}})
    session.update(updates)
    from datetime import datetime, timezone
    cutoff = datetime.now(timezone.utc).timestamp() - 86400
    to_prune = [
        sid for sid, d in sessions.items()
        if sid != session_id and _is_old(d.get("session_start", ""), cutoff)
    ]
    for sid in to_prune:
        del sessions[sid]
    save_state(state)

def _is_old(ts, cutoff):
    try:
        t = datetime.fromisoformat(ts)
        if t.tzinfo is None:
            t = t.replace(tzinfo=timezone.utc)
        return t.timestamp() < cutoff
    except Exception:
        return False

def get_project(dir_hash):
    return load_state().get("projects", {{}}).get(dir_hash, {{}})

def update_project(dir_hash, updates):
    state = load_state()
    projects = state.setdefault("projects", {{}})
    project = projects.setdefault(dir_hash, {{}})
    project.update(updates)
    save_state(state)

def get_dir_hash(cwd):
    import hashlib
    return hashlib.md5(cwd.encode()).hexdigest()[:8]
"""
    mod = types.ModuleType("state_test_instance")
    exec(compile(src, "<state>", "exec"), mod.__dict__)
    return mod


class TestState:
    def setup_method(self):
        self.tmp = tempfile.NamedTemporaryFile(suffix=".json", delete=False)
        self.tmp.close()
        os.unlink(self.tmp.name)  # start clean
        self.state = make_state_module(self.tmp.name)

    def teardown_method(self):
        if os.path.exists(self.tmp.name):
            os.unlink(self.tmp.name)

    def test_load_state_returns_empty_when_missing(self):
        assert self.state.load_state() == {}

    def test_save_and_load_roundtrip(self):
        self.state.save_state({"tier": "pro"})
        assert self.state.load_state() == {"tier": "pro"}

    def test_get_tier_defaults_to_free(self):
        assert self.state.get_tier() == "free"

    def test_get_tier_reads_from_state(self):
        self.state.save_state({"tier": "pro"})
        assert self.state.get_tier() == "pro"

    def test_get_session_returns_empty_for_unknown(self):
        assert self.state.get_session("abc") == {}

    def test_update_session_creates_and_persists(self):
        self.state.update_session("sess1", {"message_count": 5})
        assert self.state.get_session("sess1") == {"message_count": 5}

    def test_update_session_merges_existing(self):
        self.state.update_session("sess1", {"message_count": 1})
        self.state.update_session("sess1", {"mcp_warned": True})
        s = self.state.get_session("sess1")
        assert s["message_count"] == 1
        assert s["mcp_warned"] is True

    def test_get_project_returns_empty_for_unknown(self):
        assert self.state.get_project("abcd1234") == {}

    def test_update_project_creates_and_persists(self):
        self.state.update_project("abcd1234", {"last_claude_md_check": "2026-04-03"})
        assert self.state.get_project("abcd1234") == {"last_claude_md_check": "2026-04-03"}

    def test_get_dir_hash_is_8_chars(self):
        h = self.state.get_dir_hash("/home/user/project")
        assert len(h) == 8

    def test_get_dir_hash_is_deterministic(self):
        h1 = self.state.get_dir_hash("/home/user/project")
        h2 = self.state.get_dir_hash("/home/user/project")
        assert h1 == h2

    def test_get_dir_hash_differs_for_different_paths(self):
        h1 = self.state.get_dir_hash("/home/user/project1")
        h2 = self.state.get_dir_hash("/home/user/project2")
        assert h1 != h2
