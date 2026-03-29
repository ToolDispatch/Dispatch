import json
import os
import time
import tempfile
import unittest
from unittest.mock import patch


class TestShouldIntercept(unittest.TestCase):
    def test_intercepts_skill(self):
        from interceptor import should_intercept
        assert should_intercept("Skill") is True

    def test_intercepts_agent(self):
        from interceptor import should_intercept
        assert should_intercept("Agent") is True

    def test_intercepts_mcp_tools(self):
        from interceptor import should_intercept
        assert should_intercept("mcp__github__create_pull_request") is True
        assert should_intercept("mcp__supabase__execute_sql") is True

    def test_does_not_intercept_file_ops(self):
        from interceptor import should_intercept
        for tool in ["Read", "Write", "Edit", "Grep", "Glob", "Bash", "LS"]:
            assert should_intercept(tool) is False, f"Should NOT intercept {tool}"

    def test_does_not_intercept_unknown(self):
        from interceptor import should_intercept
        assert should_intercept("SomeUnknownTool") is False


class TestExtractCcTool(unittest.TestCase):
    def test_skill_tool_returns_skill_name(self):
        from interceptor import extract_cc_tool
        result = extract_cc_tool("Skill", {"skill": "superpowers:brainstorming"})
        assert result == "superpowers:brainstorming"

    def test_skill_tool_missing_skill_falls_back_to_tool_name(self):
        from interceptor import extract_cc_tool
        result = extract_cc_tool("Skill", {})
        assert result == "Skill"

    def test_mcp_tool_returns_server_and_operation(self):
        from interceptor import extract_cc_tool
        result = extract_cc_tool("mcp__github__create_pull_request", {})
        assert result == "github (create_pull_request)"

    def test_mcp_tool_two_part_name(self):
        from interceptor import extract_cc_tool
        result = extract_cc_tool("mcp__github__list_issues", {})
        assert result == "github (list_issues)"

    def test_agent_returns_subagent_type(self):
        from interceptor import extract_cc_tool
        result = extract_cc_tool("Agent", {"subagent_type": "general-purpose"})
        assert result == "general-purpose"

    def test_extract_cc_tool_none_input_returns_tool_name(self):
        from interceptor import extract_cc_tool
        result = extract_cc_tool("Skill", None)
        assert result == "Skill"

    def test_extract_cc_tool_non_dict_input_returns_tool_name(self):
        from interceptor import extract_cc_tool
        result = extract_cc_tool("Skill", "not-a-dict")
        assert result == "Skill"

    def test_agent_missing_subagent_type(self):
        from interceptor import extract_cc_tool
        result = extract_cc_tool("Agent", {})
        assert result == "agent"

    def test_unknown_tool_returns_tool_name(self):
        from interceptor import extract_cc_tool
        result = extract_cc_tool("WeirdTool", {"some": "input"})
        assert result == "WeirdTool"


class TestGetCcToolType(unittest.TestCase):
    def test_skill_tool_returns_skill(self):
        from interceptor import get_cc_tool_type
        assert get_cc_tool_type("Skill") == "skill"

    def test_agent_tool_returns_agent(self):
        from interceptor import get_cc_tool_type
        assert get_cc_tool_type("Agent") == "agent"

    def test_mcp_tool_returns_mcp(self):
        from interceptor import get_cc_tool_type
        assert get_cc_tool_type("mcp__github__create_pull_request") == "mcp"
        assert get_cc_tool_type("mcp__supabase__execute_sql") == "mcp"

    def test_unknown_tool_returns_skill(self):
        from interceptor import get_cc_tool_type
        # Unrecognized tools default to skill for safe comparison
        assert get_cc_tool_type("WeirdTool") == "skill"

    def test_bare_mcp_prefix_returns_mcp(self):
        from interceptor import get_cc_tool_type
        assert get_cc_tool_type("mcp__anything") == "mcp"


class TestBypassToken(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False)
        self.tmp.write("{}")
        self.tmp.close()
        self.state_path = self.tmp.name

    def tearDown(self):
        os.unlink(self.state_path)

    def _patch_state(self):
        import interceptor
        return patch.object(interceptor, "STATE_FILE", self.state_path)

    def test_no_bypass_by_default(self):
        from interceptor import check_bypass
        with self._patch_state():
            assert check_bypass("Skill") is False

    def test_write_then_check_bypass(self):
        from interceptor import write_bypass, check_bypass
        with self._patch_state():
            write_bypass("Skill")
            assert check_bypass("Skill") is True

    def test_bypass_clears_after_clear_bypass(self):
        from interceptor import write_bypass, check_bypass, clear_bypass
        with self._patch_state():
            write_bypass("Skill")
            clear_bypass("Skill")
            assert check_bypass("Skill") is False

    def test_bypass_does_not_apply_to_different_tool(self):
        from interceptor import write_bypass, check_bypass
        with self._patch_state():
            write_bypass("Skill")
            assert check_bypass("mcp__github__create_pull_request") is False

    def test_expired_bypass_returns_false(self):
        from interceptor import write_bypass, check_bypass
        with self._patch_state():
            write_bypass("Skill")
            # Manually expire it
            with open(self.state_path) as f:
                d = json.load(f)
            d["bypass"]["expires"] = time.time() - 1
            with open(self.state_path, "w") as f:
                json.dump(d, f)
            assert check_bypass("Skill") is False


class TestStateHelpers(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False)
        self.tmp.write(json.dumps({
            "last_task_type": "flutter-building",
            "last_context_snippet": "fixing a widget crash"
        }))
        self.tmp.close()
        self.state_path = self.tmp.name

    def tearDown(self):
        os.unlink(self.state_path)

    def _patch_state(self):
        import interceptor
        return patch.object(interceptor, "STATE_FILE", self.state_path)

    def test_get_task_type(self):
        from interceptor import get_task_type
        with self._patch_state():
            result = get_task_type()
        assert result == "flutter-building"

    def test_get_task_type_default(self):
        from interceptor import get_task_type
        with patch("interceptor.STATE_FILE", "/nonexistent/path.json"):
            result = get_task_type()
        assert result == "general"

    def test_get_context_snippet(self):
        from interceptor import get_context_snippet
        with self._patch_state():
            result = get_context_snippet()
        assert result == "fixing a widget crash"

    def test_get_category(self):
        from interceptor import get_category
        with self._patch_state():
            # setUp writes {"last_task_type": "flutter-building", "last_context_snippet": "..."}
            # No last_category in that state — should default to "unknown"
            result = get_category()
        assert result == "unknown"

    def test_get_category_returns_stored_value(self):
        from interceptor import get_category
        import json
        with open(self.state_path, "w") as f:
            json.dump({"last_category": "mobile"}, f)
        with self._patch_state():
            result = get_category()
        assert result == "mobile"


class TestSeenAlerts(unittest.TestCase):
    def setUp(self):
        self.seen_path = tempfile.mktemp(suffix=".json")

    def tearDown(self):
        if os.path.exists(self.seen_path):
            os.unlink(self.seen_path)

    def test_get_seen_alerts_empty_on_missing_file(self):
        from interceptor import get_seen_alerts
        result = get_seen_alerts(seen_file="/nonexistent/path/alerts.json")
        assert result == set()

    def test_mark_alert_seen_writes_file(self):
        from interceptor import mark_alert_seen, get_seen_alerts
        mark_alert_seen("owner/repo@skill-name", seen_file=self.seen_path)
        result = get_seen_alerts(seen_file=self.seen_path)
        assert "owner/repo@skill-name" in result

    def test_get_unseen_alerts_filters_seen(self):
        from interceptor import mark_alert_seen, get_unseen_alerts
        mark_alert_seen("owner/repo@already-seen", seen_file=self.seen_path)
        tools = [
            {"name": "owner/repo@already-seen", "score": 90},
            {"name": "owner/repo@not-seen-yet", "score": 85},
        ]
        result = get_unseen_alerts(tools, seen_file=self.seen_path)
        names = [t["name"] for t in result]
        assert "owner/repo@already-seen" not in names
        assert "owner/repo@not-seen-yet" in names

    def test_get_unseen_alerts_requires_score_80(self):
        from interceptor import get_unseen_alerts
        tools = [
            {"name": "owner/repo@high-score", "score": 81},
            {"name": "owner/repo@low-score", "score": 75},
        ]
        result = get_unseen_alerts(tools, seen_file=self.seen_path)
        names = [t["name"] for t in result]
        assert "owner/repo@high-score" in names
        assert "owner/repo@low-score" not in names


class TestLastSuggestedTracking(unittest.TestCase):
    """Tests for write_last_suggested, get_last_suggested, clear_last_suggested, check_conversion."""

    def setUp(self):
        self.state_file = tempfile.mktemp(suffix=".json")

    def tearDown(self):
        try:
            os.unlink(self.state_file)
        except Exception:
            pass

    def test_write_and_get_last_suggested(self):
        """write_last_suggested persists tool name, get_last_suggested retrieves it."""
        from interceptor import write_last_suggested, get_last_suggested
        write_last_suggested("flutter/skills@flutter-layout", state_file=self.state_file)
        assert get_last_suggested(state_file=self.state_file) == "flutter/skills@flutter-layout"

    def test_get_last_suggested_returns_empty_when_unset(self):
        """get_last_suggested returns '' when nothing written."""
        from interceptor import get_last_suggested
        assert get_last_suggested(state_file=self.state_file) == ""

    def test_clear_last_suggested(self):
        """clear_last_suggested removes the stored value."""
        from interceptor import write_last_suggested, get_last_suggested, clear_last_suggested
        write_last_suggested("flutter/skills@flutter-layout", state_file=self.state_file)
        clear_last_suggested(state_file=self.state_file)
        assert get_last_suggested(state_file=self.state_file) == ""

    def test_check_conversion_true_when_suggested_now_installed(self):
        """check_conversion returns True if last_suggested tool is now in installed list."""
        from interceptor import write_last_suggested, check_conversion
        write_last_suggested("flutter/skills@flutter-layout", state_file=self.state_file)
        result = check_conversion(
            ["other/repo@skill", "flutter/skills@flutter-layout"],
            state_file=self.state_file
        )
        assert result is True

    def test_check_conversion_false_when_not_installed(self):
        """check_conversion returns False if last_suggested is not in installed list."""
        from interceptor import write_last_suggested, check_conversion
        write_last_suggested("flutter/skills@flutter-layout", state_file=self.state_file)
        result = check_conversion(["other/repo@different-skill"], state_file=self.state_file)
        assert result is False

    def test_check_conversion_false_when_nothing_suggested(self):
        """check_conversion returns False when no last_suggested set."""
        from interceptor import check_conversion
        result = check_conversion(["flutter/skills@flutter-layout"], state_file=self.state_file)
        assert result is False


class TestNormalizeToolName(unittest.TestCase):
    """Tests for normalize_tool_name_for_matching."""

    def test_strips_mcp_prefix(self):
        from interceptor import normalize_tool_name_for_matching
        assert normalize_tool_name_for_matching("mcp:github") == "github"

    def test_strips_operation_suffix_from_cc_tool(self):
        from interceptor import normalize_tool_name_for_matching
        assert normalize_tool_name_for_matching("github (create_pull_request)") == "github"

    def test_mcp_stored_matches_cc_tool_format(self):
        """mcp:github stored form normalizes to same value as CC_TOOL 'github (op)'."""
        from interceptor import normalize_tool_name_for_matching
        assert (normalize_tool_name_for_matching("mcp:github") ==
                normalize_tool_name_for_matching("github (create_pull_request)"))

    def test_strips_plugin_anthropic_prefix(self):
        from interceptor import normalize_tool_name_for_matching
        assert normalize_tool_name_for_matching("plugin:anthropic:linear") == "linear"

    def test_strips_plugin_cc_marketplace_prefix(self):
        from interceptor import normalize_tool_name_for_matching
        assert normalize_tool_name_for_matching("plugin:cc-marketplace:foo") == "foo"

    def test_skill_id_unchanged(self):
        from interceptor import normalize_tool_name_for_matching
        # Skills have owner/repo@name format — no prefix to strip
        assert normalize_tool_name_for_matching("owner/repo@skill-name") == "owner/repo@skill-name"

    def test_lowercases_result(self):
        from interceptor import normalize_tool_name_for_matching
        assert normalize_tool_name_for_matching("mcp:GitHub") == "github"

    def test_empty_string(self):
        from interceptor import normalize_tool_name_for_matching
        assert normalize_tool_name_for_matching("") == ""


class TestCheckConversionNormalized(unittest.TestCase):
    """Tests for check_conversion using normalized MCP name matching."""

    def setUp(self):
        self.state_file = tempfile.mktemp(suffix=".json")

    def tearDown(self):
        try:
            os.unlink(self.state_file)
        except Exception:
            pass

    def test_mcp_stored_matches_cc_tool_operation_format(self):
        """mcp:github stored last_suggested matches 'github (create_pull_request)' CC_TOOL."""
        from interceptor import write_last_suggested, check_conversion
        write_last_suggested("mcp:github", state_file=self.state_file)
        result = check_conversion(["github (create_pull_request)"], state_file=self.state_file)
        assert result is True

    def test_mcp_stored_matches_plain_server_name(self):
        """mcp:supabase stored matches 'supabase (execute_sql)' CC_TOOL."""
        from interceptor import write_last_suggested, check_conversion
        write_last_suggested("mcp:supabase", state_file=self.state_file)
        result = check_conversion(["supabase (execute_sql)"], state_file=self.state_file)
        assert result is True

    def test_different_mcp_does_not_match(self):
        """mcp:github does not match supabase (execute_sql)."""
        from interceptor import write_last_suggested, check_conversion
        write_last_suggested("mcp:github", state_file=self.state_file)
        result = check_conversion(["supabase (execute_sql)"], state_file=self.state_file)
        assert result is False

    def test_plugin_stored_matches_display_name(self):
        """plugin:anthropic:linear stored matches 'linear' in installed list."""
        from interceptor import write_last_suggested, check_conversion
        write_last_suggested("plugin:anthropic:linear", state_file=self.state_file)
        result = check_conversion(["linear"], state_file=self.state_file)
        assert result is True

    def test_exact_match_still_works(self):
        """Exact string match still works for skills."""
        from interceptor import write_last_suggested, check_conversion
        write_last_suggested("owner/repo@skill-name", state_file=self.state_file)
        result = check_conversion(["owner/repo@skill-name"], state_file=self.state_file)
        assert result is True


class TestAtomicWrite(unittest.TestCase):
    """State file writes must be atomic — no partial/corrupt JSON on crash."""

    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.state_file = os.path.join(self.tmp, "state.json")

    def tearDown(self):
        import shutil
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_write_last_suggested_uses_atomic_write(self):
        """write_last_suggested must go through _atomic_write."""
        import interceptor
        calls = []
        orig = interceptor._atomic_write
        def tracked(*a, **kw):
            calls.append(a[0])
            return orig(*a, **kw)
        with patch.object(interceptor, "_atomic_write", tracked):
            interceptor.write_last_suggested("owner/repo@skill", state_file=self.state_file)
        assert len(calls) == 1

    def test_clear_last_suggested_uses_atomic_write(self):
        """clear_last_suggested must go through _atomic_write."""
        import interceptor
        interceptor.write_last_suggested("owner/repo@skill", state_file=self.state_file)
        calls = []
        orig = interceptor._atomic_write
        def tracked(*a, **kw):
            calls.append(a[0])
            return orig(*a, **kw)
        with patch.object(interceptor, "_atomic_write", tracked):
            interceptor.clear_last_suggested(state_file=self.state_file)
        assert len(calls) == 1

    def test_write_bypass_uses_atomic_write(self):
        """write_bypass must go through _atomic_write."""
        import interceptor
        calls = []
        orig = interceptor._atomic_write
        def tracked(*a, **kw):
            calls.append(a[0])
            return orig(*a, **kw)
        with patch.object(interceptor, "_atomic_write", tracked):
            interceptor.write_bypass("Skill", state_file=self.state_file)
        assert len(calls) == 1

    def test_state_file_valid_json_after_write(self):
        """State file must contain valid JSON after any write operation."""
        import interceptor
        interceptor.write_last_suggested("owner/repo@skill", state_file=self.state_file)
        with open(self.state_file) as f:
            data = json.load(f)
        assert isinstance(data, dict)
        assert data["last_suggested"] == "owner/repo@skill"


class TestLastCcToolType(unittest.TestCase):
    """write_last_cc_tool_type / get_last_cc_tool_type roundtrip."""

    def setUp(self):
        import tempfile
        fd, self.state_file = tempfile.mkstemp(suffix=".json")
        os.close(fd)
        with open(self.state_file, "w") as f:
            json.dump({}, f)

    def tearDown(self):
        if os.path.exists(self.state_file):
            os.unlink(self.state_file)

    def test_write_and_read_roundtrip(self):
        import interceptor
        interceptor.write_last_cc_tool_type("mcp", state_file=self.state_file)
        result = interceptor.get_last_cc_tool_type(state_file=self.state_file)
        assert result == "mcp"

    def test_write_skill_type(self):
        import interceptor
        interceptor.write_last_cc_tool_type("skill", state_file=self.state_file)
        assert interceptor.get_last_cc_tool_type(state_file=self.state_file) == "skill"

    def test_get_returns_empty_string_when_unset(self):
        import interceptor
        result = interceptor.get_last_cc_tool_type(state_file=self.state_file)
        assert result == ""

    def test_overwrites_previous_value(self):
        import interceptor
        interceptor.write_last_cc_tool_type("mcp", state_file=self.state_file)
        interceptor.write_last_cc_tool_type("agent", state_file=self.state_file)
        assert interceptor.get_last_cc_tool_type(state_file=self.state_file) == "agent"

    def test_preserves_other_state_keys(self):
        import interceptor
        with open(self.state_file, "w") as f:
            json.dump({"last_task_type": "flutter-building"}, f)
        interceptor.write_last_cc_tool_type("mcp", state_file=self.state_file)
        with open(self.state_file) as f:
            data = json.load(f)
        assert data["last_task_type"] == "flutter-building"
        assert data["last_cc_tool_type"] == "mcp"

    def test_get_returns_empty_on_missing_file(self):
        import interceptor
        result = interceptor.get_last_cc_tool_type(state_file="/nonexistent/path.json")
        assert result == ""


class TestLastRecommendedCategory(unittest.TestCase):
    def test_returns_empty_string_when_no_state(self):
        from interceptor import get_last_recommended_category
        with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as f:
            tmp = f.name
        os.unlink(tmp)
        result = get_last_recommended_category(state_file=tmp)
        assert result == ""

    def test_returns_category_after_write(self):
        from interceptor import get_last_recommended_category, write_last_recommended_category
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            tmp = f.name
            json.dump({}, f)
        try:
            write_last_recommended_category("mobile", state_file=tmp)
            result = get_last_recommended_category(state_file=tmp)
            assert result == "mobile"
        finally:
            os.unlink(tmp)

    def test_write_preserves_existing_state_fields(self):
        from interceptor import write_last_recommended_category
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            tmp = f.name
            json.dump({"last_task_type": "flutter-building"}, f)
        try:
            write_last_recommended_category("mobile", state_file=tmp)
            with open(tmp) as f:
                d = json.load(f)
            assert d["last_task_type"] == "flutter-building"
            assert d["last_recommended_category"] == "mobile"
        finally:
            os.unlink(tmp)

    def test_get_returns_empty_on_corrupt_file(self):
        from interceptor import get_last_recommended_category
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            tmp = f.name
            f.write("NOT JSON")
        try:
            result = get_last_recommended_category(state_file=tmp)
            assert result == ""
        finally:
            os.unlink(tmp)


class TestSessionCounters(unittest.TestCase):

    def setUp(self):
        self.tmp = tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False)
        json.dump({}, self.tmp)
        self.tmp.close()
        self.state_file = self.tmp.name

    def tearDown(self):
        os.unlink(self.state_file)

    def test_increment_initializes_counters_on_new_session(self):
        from interceptor import increment_session_counter, get_session_stats
        increment_session_counter("session_audits", "sess-abc", state_file=self.state_file)
        stats = get_session_stats(state_file=self.state_file)
        self.assertEqual(stats["audits"], 1)
        self.assertEqual(stats["blocks"], 0)
        self.assertEqual(stats["recommendations"], 0)

    def test_increment_accumulates_within_session(self):
        from interceptor import increment_session_counter, get_session_stats
        increment_session_counter("session_audits", "sess-abc", state_file=self.state_file)
        increment_session_counter("session_audits", "sess-abc", state_file=self.state_file)
        increment_session_counter("session_blocks", "sess-abc", state_file=self.state_file)
        stats = get_session_stats(state_file=self.state_file)
        self.assertEqual(stats["audits"], 2)
        self.assertEqual(stats["blocks"], 1)

    def test_increment_resets_on_new_session_id(self):
        from interceptor import increment_session_counter, get_session_stats
        increment_session_counter("session_audits", "sess-old", state_file=self.state_file)
        increment_session_counter("session_audits", "sess-old", state_file=self.state_file)
        # New session — should reset
        increment_session_counter("session_audits", "sess-new", state_file=self.state_file)
        stats = get_session_stats(state_file=self.state_file)
        self.assertEqual(stats["audits"], 1)

    def test_get_session_stats_returns_zeros_on_missing_file(self):
        from interceptor import get_session_stats
        stats = get_session_stats(state_file="/nonexistent/path/state.json")
        self.assertEqual(stats, {"audits": 0, "blocks": 0, "recommendations": 0})

    def test_increment_recommendations_counter(self):
        from interceptor import increment_session_counter, get_session_stats
        increment_session_counter("session_recommendations", "sess-abc", state_file=self.state_file)
        stats = get_session_stats(state_file=self.state_file)
        self.assertEqual(stats["recommendations"], 1)


if __name__ == "__main__":
    unittest.main()
