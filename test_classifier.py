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
    @patch('classifier.anthropic.Anthropic')
    def test_returns_structured_result_on_shift(self, mock_client_cls):
        mock_client = MagicMock()
        mock_client_cls.return_value = mock_client
        mock_client.messages.create.return_value = MagicMock(
            content=[MagicMock(text=json.dumps({
                "shift": True,
                "domain": "flutter",
                "mode": "building",
                "task_type": "flutter-building",
                "confidence": 0.92
            }))]
        )
        result = classify_topic_shift(
            messages=["fix supabase query", "now build a Flutter widget"],
            cwd="/home/visionairy/SNAP-app",
            last_task_type="supabase"
        )
        assert result["shift"] is True
        assert result["task_type"] == "flutter-building"
        assert result["confidence"] == 0.92

    @patch('classifier.anthropic.Anthropic')
    def test_returns_no_shift_on_continuation(self, mock_client_cls):
        mock_client = MagicMock()
        mock_client_cls.return_value = mock_client
        mock_client.messages.create.return_value = MagicMock(
            content=[MagicMock(text=json.dumps({
                "shift": False,
                "domain": "flutter",
                "mode": "building",
                "task_type": "flutter-building",
                "confidence": 0.95
            }))]
        )
        result = classify_topic_shift(
            messages=["add a new screen", "make the button blue"],
            cwd="/home/visionairy/SNAP-app",
            last_task_type="flutter"
        )
        assert result["shift"] is False

    @patch('classifier.anthropic.Anthropic')
    def test_handles_malformed_response_gracefully(self, mock_client_cls):
        mock_client = MagicMock()
        mock_client_cls.return_value = mock_client
        mock_client.messages.create.return_value = MagicMock(
            content=[MagicMock(text="not json")]
        )
        result = classify_topic_shift(
            messages=["something"],
            cwd="/home/visionairy",
            last_task_type=None
        )
        assert result["shift"] is False
        assert result["task_type"] == "general"
        assert result["confidence"] == 0.0


if __name__ == '__main__':
    unittest.main()
