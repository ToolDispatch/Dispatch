import json
import os
import tempfile
import unittest
from unittest.mock import patch, MagicMock


class TestLoadConfig(unittest.TestCase):
    def test_load_config_returns_empty_on_missing_file(self):
        from llm_client import load_config
        result = load_config("/nonexistent/path/config.json")
        assert result == {}

    def test_load_config_reads_fields(self):
        from llm_client import load_config
        data = {
            "token": "tok_abc",
            "provider": "openrouter",
            "openrouter_api_key": "sk-or-123",
            "classifier_model": "meta-llama/llama-3.1-8b-instruct:free",
            "ranker_model": "meta-llama/llama-3.1-8b-instruct:free",
        }
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            json.dump(data, f)
            path = f.name
        try:
            result = load_config(path)
            assert result["token"] == "tok_abc"
            assert result["provider"] == "openrouter"
            assert result["openrouter_api_key"] == "sk-or-123"
        finally:
            os.unlink(path)


class TestModelSelection(unittest.TestCase):
    def test_classify_model_free_default(self):
        from llm_client import classify_model
        result = classify_model({})
        assert result == "meta-llama/llama-3.1-8b-instruct:free"

    def test_classify_model_uses_config_override(self):
        from llm_client import classify_model
        result = classify_model({"classifier_model": "anthropic/claude-haiku-4-5"})
        assert result == "anthropic/claude-haiku-4-5"

    def test_ranker_model_free_default(self):
        from llm_client import ranker_model
        result = ranker_model({})
        assert result == "meta-llama/llama-3.1-8b-instruct:free"


class TestGetClient(unittest.TestCase):
    def test_get_client_returns_llm_client_instance(self):
        from llm_client import get_client, LLMClient
        with patch.dict(os.environ, {"OPENROUTER_API_KEY": "sk-or-test"}):
            client = get_client({"provider": "openrouter", "openrouter_api_key": "sk-or-test"})
        assert isinstance(client, LLMClient)

    def test_get_client_no_key_returns_noop_client(self):
        from llm_client import get_client
        # No keys in config or environment
        env = {k: v for k, v in os.environ.items()
               if k not in ("OPENROUTER_API_KEY", "ANTHROPIC_API_KEY")}
        with patch.dict(os.environ, env, clear=True):
            client = get_client({})
        # Noop client returns empty string and never raises
        result = client.complete(system="s", user="u", model="m")
        assert result == ""


class TestComplete(unittest.TestCase):
    def test_complete_strips_markdown_fences(self):
        from llm_client import LLMClient
        client = LLMClient(provider="anthropic", api_key="sk-test")
        mock_response = MagicMock()
        mock_response.content = [MagicMock(text='```json\n{"shift": true}\n```')]
        with patch("anthropic.Anthropic") as MockAnthropic:
            MockAnthropic.return_value.messages.create.return_value = mock_response
            client._anthropic_client = MockAnthropic.return_value
            result = client.complete(system="sys", user="usr", model="claude-haiku-4-5-20251001")
        assert result == '{"shift": true}'

    def test_complete_strips_fences_with_json_on_newline(self):
        """Haiku sometimes returns ```\njson\n{...} — json marker on separate line."""
        from llm_client import LLMClient
        client = LLMClient(provider="anthropic", api_key="sk-test")
        mock_response = MagicMock()
        mock_response.content = [MagicMock(text='```\njson\n{"shift": true}\n```')]
        with patch("anthropic.Anthropic") as MockAnthropic:
            MockAnthropic.return_value.messages.create.return_value = mock_response
            client._anthropic_client = MockAnthropic.return_value
            result = client.complete(system="sys", user="usr", model="claude-haiku-4-5-20251001")
        assert result == '{"shift": true}'

    def test_complete_returns_empty_on_exception(self):
        from llm_client import LLMClient
        client = LLMClient(provider="anthropic", api_key="sk-test")
        with patch("anthropic.Anthropic") as MockAnthropic:
            MockAnthropic.return_value.messages.create.side_effect = Exception("network error")
            client._anthropic_client = MockAnthropic.return_value
            result = client.complete(system="sys", user="usr", model="claude-haiku-4-5-20251001")
        assert result == ""

    def test_complete_openrouter_provider_calls_openai_sdk(self):
        from llm_client import LLMClient
        client = LLMClient(provider="openrouter", api_key="sk-or-test")
        mock_choice = MagicMock()
        mock_choice.message.content = '{"cc_score": 80, "all": []}'
        mock_response = MagicMock()
        mock_response.choices = [mock_choice]
        with patch("openai.OpenAI") as MockOpenAI:
            MockOpenAI.return_value.chat.completions.create.return_value = mock_response
            client._openai_client = MockOpenAI.return_value
            result = client.complete(system="sys", user="usr", model="meta-llama/llama-3.1-8b-instruct:free")
        assert result == '{"cc_score": 80, "all": []}'
        MockOpenAI.return_value.chat.completions.create.assert_called_once()

    def test_complete_anthropic_provider_calls_anthropic_sdk(self):
        from llm_client import LLMClient
        client = LLMClient(provider="anthropic", api_key="sk-ant-test")
        mock_response = MagicMock()
        mock_response.content = [MagicMock(text='{"shift": false}')]
        with patch("anthropic.Anthropic") as MockAnthropic:
            MockAnthropic.return_value.messages.create.return_value = mock_response
            client._anthropic_client = MockAnthropic.return_value
            result = client.complete(system="sys", user="usr", model="claude-haiku-4-5-20251001")
        assert result == '{"shift": false}'
        MockAnthropic.return_value.messages.create.assert_called_once()

    def test_complete_anthropic_fallback_when_openrouter_fails(self):
        from llm_client import LLMClient
        client = LLMClient(
            provider="openrouter",
            api_key="sk-or-test",
            anthropic_fallback_key="sk-ant-fallback"
        )
        mock_anthropic_response = MagicMock()
        mock_anthropic_response.content = [MagicMock(text='{"shift": true}')]

        with patch("openai.OpenAI") as MockOpenAI, \
             patch("anthropic.Anthropic") as MockAnthropic:
            MockOpenAI.return_value.chat.completions.create.side_effect = Exception("openrouter down")
            MockAnthropic.return_value.messages.create.return_value = mock_anthropic_response
            client._openai_client = MockOpenAI.return_value
            client._anthropic_fallback_client = MockAnthropic.return_value
            result = client.complete(system="sys", user="usr", model="meta-llama/llama-3.1-8b-instruct:free")

        assert result == '{"shift": true}'
        MockAnthropic.return_value.messages.create.assert_called_once()


if __name__ == "__main__":
    unittest.main()
