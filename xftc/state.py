import json
import os
import hashlib
from datetime import datetime, timezone

STATE_FILE = os.path.expanduser("~/.claude/dispatch/xftc_state.json")


def load_state() -> dict:
    if not os.path.exists(STATE_FILE):
        return {}
    try:
        with open(STATE_FILE) as f:
            return json.load(f)
    except Exception:
        return {}


def save_state(state: dict) -> None:
    os.makedirs(os.path.dirname(STATE_FILE), exist_ok=True)
    try:
        with open(STATE_FILE, "w") as f:
            json.dump(state, f, indent=2)
    except Exception:
        pass


def get_tier() -> str:
    return load_state().get("tier", "free")


def get_session(session_id: str) -> dict:
    return load_state().get("sessions", {}).get(session_id, {})


def update_session(session_id: str, updates: dict) -> None:
    state = load_state()
    sessions = state.setdefault("sessions", {})
    session = sessions.setdefault(session_id, {})
    session.update(updates)
    cutoff = datetime.now(timezone.utc).timestamp() - 86400
    to_prune = [
        sid for sid, d in sessions.items()
        if sid != session_id and _is_old(d.get("session_start", ""), cutoff)
    ]
    for sid in to_prune:
        del sessions[sid]
    save_state(state)


def _is_old(ts: str, cutoff: float) -> bool:
    try:
        t = datetime.fromisoformat(ts)
        if t.tzinfo is None:
            t = t.replace(tzinfo=timezone.utc)
        return t.timestamp() < cutoff
    except Exception:
        return False


def get_project(dir_hash: str) -> dict:
    return load_state().get("projects", {}).get(dir_hash, {})


def update_project(dir_hash: str, updates: dict) -> None:
    state = load_state()
    projects = state.setdefault("projects", {})
    project = projects.setdefault(dir_hash, {})
    project.update(updates)
    save_state(state)


def get_dir_hash(cwd: str) -> str:
    return hashlib.md5(cwd.encode()).hexdigest()[:8]
