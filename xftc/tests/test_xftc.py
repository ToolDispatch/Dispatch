import json as _json
import os
import tempfile
from unittest.mock import patch, MagicMock
import pytest

# Import modules once at collection time
from xftc import xftc as _xftc_mod
from xftc import state as _state_mod


def fresh_state_file(tmp_path):
    """Return path to a fresh temp state file."""
    return str(tmp_path / "xftc_state.json")


class TestXftcOrchestrator:
    """Integration tests for the xftc.py orchestrator."""

    def _make_submit_data(self, session_id="test-session", cwd=None):
        return {
            "session_id": session_id,
            "cwd": cwd or tempfile.mkdtemp(),
        }

    def _make_preuse_data(self, tool_name, tool_input, session_id="test-session"):
        return {
            "tool_name": tool_name,
            "tool_input": tool_input,
            "session_id": session_id,
        }

    def test_stop_hook_records_timestamp(self, tmp_path):
        sf = fresh_state_file(tmp_path)
        with patch.object(_state_mod, "STATE_FILE", sf):
            _xftc_mod.run_stop_hook({"session_id": "s1"})
        raw = _json.loads((tmp_path / "xftc_state.json").read_text())
        assert "last_stop_time" in raw.get("sessions", {}).get("s1", {})

    def test_submit_hook_increments_message_count(self, tmp_path):
        sf = fresh_state_file(tmp_path)
        with patch.object(_state_mod, "STATE_FILE", sf):
            _xftc_mod.run_submit_hook({"session_id": "s1", "cwd": str(tmp_path)})
            assert _state_mod.get_session("s1")["message_count"] == 1
            _xftc_mod.run_submit_hook({"session_id": "s1", "cwd": str(tmp_path)})
            assert _state_mod.get_session("s1")["message_count"] == 2

    def test_preuse_hook_passes_haiku_agent(self, tmp_path):
        sf = fresh_state_file(tmp_path)
        with patch.object(_state_mod, "STATE_FILE", sf):
            exit_code = _xftc_mod.run_preuse_hook(
                self._make_preuse_data("Agent", {"model": "claude-haiku-4-5-20251001", "prompt": "search files"})
            )
            assert exit_code == 0

    def test_preuse_hook_blocks_opus_agent_for_pro(self, tmp_path, capsys):
        sf = fresh_state_file(tmp_path)
        # Patch get_tier in xftc module (direct import reference)
        with patch.object(_state_mod, "STATE_FILE", sf):
            with patch("xftc.xftc.get_tier", return_value="pro"):
                exit_code = _xftc_mod.run_preuse_hook(
                    self._make_preuse_data("Agent", {"model": "claude-opus-4-6", "prompt": "do work"})
                )
                assert exit_code == 2

    def test_preuse_hook_fires_ghost_for_free_on_opus(self, tmp_path, capsys):
        sf = fresh_state_file(tmp_path)
        with patch.object(_state_mod, "STATE_FILE", sf):
            with patch("xftc.xftc.get_tier", return_value="free"):
                exit_code = _xftc_mod.run_preuse_hook(
                    self._make_preuse_data("Agent", {"model": "claude-opus-4-6", "prompt": "do work"})
                )
                assert exit_code == 0
                captured = capsys.readouterr()
                assert "Pro would have flagged" in captured.out

    def test_preuse_hook_passes_bash_clean(self, tmp_path):
        sf = fresh_state_file(tmp_path)
        with patch.object(_state_mod, "STATE_FILE", sf):
            exit_code = _xftc_mod.run_preuse_hook(
                self._make_preuse_data("Bash", {"command": "git status"})
            )
            assert exit_code == 0

    def test_preuse_hook_blocks_verbose_bash_for_pro(self, tmp_path, capsys):
        sf = fresh_state_file(tmp_path)
        with patch.object(_state_mod, "STATE_FILE", sf):
            with patch("xftc.xftc.get_tier", return_value="pro"):
                exit_code = _xftc_mod.run_preuse_hook(
                    self._make_preuse_data("Bash", {"command": "git log"})
                )
                assert exit_code == 2

    def test_ghost_fires_only_once_per_session(self, tmp_path, capsys):
        sf = fresh_state_file(tmp_path)
        with patch.object(_state_mod, "STATE_FILE", sf):
            with patch("xftc.xftc.get_tier", return_value="free"):
                # First opus call fires ghost
                _xftc_mod.run_preuse_hook(
                    self._make_preuse_data("Agent", {"model": "opus", "prompt": "work"}, "s1")
                )
                out1 = capsys.readouterr().out
                # Second opus call in same session should be silent
                _xftc_mod.run_preuse_hook(
                    self._make_preuse_data("Agent", {"model": "opus", "prompt": "work"}, "s1")
                )
                out2 = capsys.readouterr().out
                assert "Pro would have flagged" in out1
                assert out2 == ""
