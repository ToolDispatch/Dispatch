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

    def test_agent_missing_subagent_type(self):
        from interceptor import extract_cc_tool
        result = extract_cc_tool("Agent", {})
        assert result == "agent"

    def test_unknown_tool_returns_tool_name(self):
        from interceptor import extract_cc_tool
        result = extract_cc_tool("WeirdTool", {"some": "input"})
        assert result == "WeirdTool"


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


if __name__ == "__main__":
    unittest.main()
