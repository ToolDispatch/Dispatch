import json
import unittest
from unittest.mock import patch, MagicMock
from classifier import classify_topic_shift, extract_recent_messages, should_skip


class TestExtractRecentMessages(unittest.TestCase):
    def test_extracts_last_3_human_messages(self):
        transcript = [
            {"role": "user", "content": "help me fix this bug"},
            {"role": "assistant", "content": "sure"},
            {"role": "user", "content": "now write a test"},
            {"role": "assistant", "content": "ok"},
            {"role": "user", "content": "deploy to Firebase"},
        ]
        result = extract_recent_messages(transcript, n=3)
        assert len(result) == 3
        assert result[-1] == "deploy to Firebase"

    def test_handles_fewer_than_n_messages(self):
        transcript = [{"role": "user", "content": "hello"}]
        result = extract_recent_messages(transcript, n=3)
        assert result == ["hello"]

    def test_handles_content_block_format(self):
        transcript = [
            {"role": "user", "content": [{"type": "text", "text": "build a Flutter widget"}]}
        ]
        result = extract_recent_messages(transcript, n=3)
        assert result == ["build a Flutter widget"]

    def test_handles_cc_nested_transcript_format(self):
        """CC transcript wraps message inside a 'message' key, not at top level."""
        transcript = [
            {"type": "user", "message": {"role": "user", "content": "fix the Flutter widget"}, "uuid": "abc"},
            {"type": "assistant", "message": {"role": "assistant", "content": "sure"}, "uuid": "def"},
            {"type": "user", "message": {"role": "user", "content": "now set up Stripe webhooks"}, "uuid": "ghi"},
        ]
        result = extract_recent_messages(transcript, n=3)
        assert len(result) == 2
        assert result[-1] == "now set up Stripe webhooks"

    def test_filters_meta_entries(self):
        """isMeta=True entries are CC system messages (skill content) — must be excluded."""
        transcript = [
            {"type": "user", "isMeta": False, "message": {"role": "user", "content": "fix the Flutter widget"}},
            {"type": "user", "isMeta": True, "message": {"role": "user", "content": "Base directory for this skill: /home/...long skill text..."}},
            {"type": "user", "isMeta": False, "message": {"role": "user", "content": "now set up Stripe webhooks"}},
        ]
        result = extract_recent_messages(transcript, n=3)
        assert len(result) == 2
        assert "Base directory" not in result[0]
        assert result[-1] == "now set up Stripe webhooks"

    def test_filters_serialized_tool_results(self):
        """Entries with content starting with '[' are serialized tool results — must be excluded."""
        transcript = [
            {"type": "user", "isMeta": False, "message": {"role": "user", "content": "fix the Flutter widget"}},
            {"type": "user", "isMeta": False, "message": {"role": "user", "content": "[{'type': 'tool_result', 'tool_use_id': 'abc', 'content': 'File read ok'}]"}},
            {"type": "user", "isMeta": False, "message": {"role": "user", "content": "now set up Stripe webhooks"}},
        ]
        result = extract_recent_messages(transcript, n=3)
        assert len(result) == 2
        assert result[-1] == "now set up Stripe webhooks"


class TestShouldSkip(unittest.TestCase):
    def test_skips_short_messages(self):
        assert should_skip("ok thanks") is True

    def test_does_not_skip_long_new_message(self):
        assert should_skip("I need to set up a new n8n workflow to process webhooks") is False

    def test_skips_very_short_message(self):
        assert should_skip("yes") is True

    def test_does_not_skip_4_word_task_shift(self):
        # 4-word messages like "set up Stripe integration" are real task shifts
        assert should_skip("set up Stripe integration") is False

    def test_does_not_skip_5_word_task_shift(self):
        assert should_skip("now set up Firebase auth") is False

    def test_skips_3_word_filler(self):
        assert should_skip("yes do that") is True


class TestClassifyTopicShift(unittest.TestCase):
    @patch('classifier.get_client')
    def test_returns_structured_result_on_shift(self, mock_get_client):
        mock_llm = MagicMock()
        mock_get_client.return_value = mock_llm
        mock_llm.complete.return_value = json.dumps({
            "shift": True,
            "domain": "flutter",
            "mode": "building",
            "task_type": "flutter-building",
            "confidence": 0.92
        })
        result = classify_topic_shift(
            messages=["fix supabase query", "now build a Flutter widget"],
            cwd="/home/visionairy/SNAP-app",
            last_task_type="supabase"
        )
        assert result["shift"] is True
        assert result["task_type"] == "flutter-building"
        assert result["confidence"] == 0.92

    @patch('classifier.get_client')
    def test_returns_no_shift_on_continuation(self, mock_get_client):
        mock_llm = MagicMock()
        mock_get_client.return_value = mock_llm
        mock_llm.complete.return_value = json.dumps({
            "shift": False,
            "domain": "flutter",
            "mode": "building",
            "task_type": "flutter-building",
            "confidence": 0.95
        })
        result = classify_topic_shift(
            messages=["add a new screen", "make the button blue"],
            cwd="/home/visionairy/SNAP-app",
            last_task_type="flutter"
        )
        assert result["shift"] is False

    @patch('classifier.get_client')
    def test_handles_malformed_response_gracefully(self, mock_get_client):
        mock_llm = MagicMock()
        mock_get_client.return_value = mock_llm
        mock_llm.complete.return_value = "not json"
        result = classify_topic_shift(
            messages=["something"],
            cwd="/home/visionairy",
            last_task_type=None
        )
        assert result["shift"] is False
        assert result["task_type"] == "general-building"
        assert result["confidence"] == 0.0


    @patch('classifier.get_client')
    def test_intra_domain_mode_shift(self, mock_get_client):
        """Shift within same domain when action mode changes (building → fixing)"""
        mock_llm = MagicMock()
        mock_get_client.return_value = mock_llm
        mock_llm.complete.return_value = json.dumps({
            "shift": True,
            "domain": "flutter",
            "mode": "fixing",
            "task_type": "flutter-fixing",
            "confidence": 0.88
        })
        result = classify_topic_shift(
            messages=["this blows up with a null pointer"],
            cwd="/home/user/myapp",
            last_task_type="flutter-building"
        )
        assert result["shift"] is True
        assert result["mode"] == "fixing"
        assert result["task_type"] == "flutter-fixing"

    @patch('classifier.get_client')
    def test_same_domain_same_mode_no_shift(self, mock_get_client):
        """No shift when domain and mode are both unchanged"""
        mock_llm = MagicMock()
        mock_get_client.return_value = mock_llm
        mock_llm.complete.return_value = json.dumps({
            "shift": False,
            "domain": "flutter",
            "mode": "building",
            "task_type": "flutter-building",
            "confidence": 0.15
        })
        result = classify_topic_shift(
            messages=["what was that widget called again?"],
            cwd="/home/user/myapp",
            last_task_type="flutter-building"
        )
        assert result["shift"] is False

    @patch('classifier.anthropic.Anthropic')
    def test_mode_field_is_valid_enum_value(self, mock_client_cls):
        """mode field in result must be one of the 7 valid action modes"""
        valid_modes = {
            "discovering", "designing", "building",
            "fixing", "validating", "shipping", "maintaining"
        }
        mock_client = MagicMock()
        mock_client_cls.return_value = mock_client
        mock_client.messages.create.return_value = MagicMock(
            content=[MagicMock(text=json.dumps({
                "shift": True,
                "domain": "react",
                "mode": "building",
                "task_type": "react-building",
                "confidence": 0.85
            }))]
        )
        result = classify_topic_shift(
            messages=["add a new login form component"],
            cwd="/home/user/webapp",
            last_task_type="react-designing"
        )
        assert result["mode"] in valid_modes

    @patch('classifier.get_client')
    def test_malformed_response_returns_all_5_fields(self, mock_get_client):
        """Safe default on malformed response must include all 5 fields"""
        mock_llm = MagicMock()
        mock_get_client.return_value = mock_llm
        mock_llm.complete.side_effect = Exception("API error")
        result = classify_topic_shift(
            messages=["write the auth middleware"],
            cwd="/home/user/project",
            last_task_type="general"
        )
        assert "shift" in result
        assert "domain" in result
        assert "mode" in result
        assert "task_type" in result
        assert "confidence" in result
        assert result["shift"] is False


class TestPreferredToolType(unittest.TestCase):
    """T2.1: classifier must emit preferred_tool_type when context suggests MCPs."""

    def _mock_llm_response(self, result_dict):
        with patch("classifier.get_client") as mock_get_client:
            mock_llm = MagicMock()
            mock_get_client.return_value = mock_llm
            mock_llm.complete.return_value = json.dumps(result_dict)
            yield mock_llm

    def test_mcp_flavored_message_emits_mcp_preferred_tool_type(self):
        """Messages mentioning MCP servers by name → preferred_tool_type = 'mcp'."""
        payload = {
            "shift": True, "domain": "database", "mode": "building",
            "task_type": "database-building", "confidence": 0.9,
            "preferred_tool_type": "mcp"
        }
        with patch("classifier.get_client") as mock_get_client:
            mock_llm = MagicMock()
            mock_get_client.return_value = mock_llm
            mock_llm.complete.return_value = json.dumps(payload)
            result = classify_topic_shift(
                ["connect to postgres via mcp server", "query the users table"],
                cwd="/project"
            )
        assert result.get("preferred_tool_type") == "mcp"

    def test_non_mcp_message_emits_null_preferred_tool_type(self):
        """General dev tasks → preferred_tool_type = null."""
        payload = {
            "shift": True, "domain": "flutter", "mode": "building",
            "task_type": "flutter-building", "confidence": 0.85,
            "preferred_tool_type": None
        }
        with patch("classifier.get_client") as mock_get_client:
            mock_llm = MagicMock()
            mock_get_client.return_value = mock_llm
            mock_llm.complete.return_value = json.dumps(payload)
            result = classify_topic_shift(
                ["write a flutter widget for the home screen"],
                cwd="/project"
            )
        assert result.get("preferred_tool_type") is None

    def test_preferred_tool_type_in_system_prompt(self):
        """SYSTEM_PROMPT must mention preferred_tool_type so LLM knows to emit it."""
        from classifier import SYSTEM_PROMPT
        assert "preferred_tool_type" in SYSTEM_PROMPT

    def test_classify_still_returns_required_fields(self):
        """Adding preferred_tool_type must not break existing required fields."""
        payload = {
            "shift": False, "domain": "general", "mode": "building",
            "task_type": "general-building", "confidence": 0.5,
            "preferred_tool_type": None
        }
        with patch("classifier.get_client") as mock_get_client:
            mock_llm = MagicMock()
            mock_get_client.return_value = mock_llm
            mock_llm.complete.return_value = json.dumps(payload)
            result = classify_topic_shift(["hello"], cwd="/project")
        for key in ("shift", "domain", "mode", "task_type", "confidence"):
            assert key in result, f"Missing required field: {key}"


if __name__ == '__main__':
    unittest.main()
