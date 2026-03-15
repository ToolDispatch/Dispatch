"""LLM-agnostic adapter for Dispatch.

OpenRouter-first (uses openai SDK with custom base_url).
Falls back to Anthropic if OpenRouter is unavailable or unconfigured.
Never raises — returns empty string on any failure.
"""

import json
import os

CONFIG_FILE = os.path.expanduser("~/.claude/skill-router/config.json")

FREE_CLASSIFIER_MODEL = "meta-llama/llama-3.1-8b-instruct:free"
FREE_RANKER_MODEL = "meta-llama/llama-3.1-8b-instruct:free"
OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"


def load_config(config_file: str = None) -> dict:
    """Load skill-router config.json. Returns {} on any failure."""
    path = config_file or CONFIG_FILE
    try:
        with open(path) as f:
            return json.load(f)
    except Exception:
        return {}


def classify_model(config: dict) -> str:
    """Return the model string to use for classification."""
    return config.get("classifier_model") or FREE_CLASSIFIER_MODEL


def ranker_model(config: dict) -> str:
    """Return the model string to use for ranking."""
    return config.get("ranker_model") or FREE_RANKER_MODEL


def get_client(config: dict = None) -> "LLMClient":
    """Return a configured LLMClient. Loads config.json if config not provided.

    Priority: OpenRouter if openrouter_api_key present (in config or env),
              else Anthropic if anthropic api key present,
              else no-op client that returns "" on complete().
    Never raises.
    """
    if config is None:
        config = load_config()

    openrouter_key = (
        config.get("openrouter_api_key")
        or os.environ.get("OPENROUTER_API_KEY", "")
    )
    anthropic_key = (
        config.get("anthropic_api_key")
        or os.environ.get("ANTHROPIC_API_KEY", "")
    )

    if openrouter_key:
        return LLMClient(
            provider="openrouter",
            api_key=openrouter_key,
            anthropic_fallback_key=anthropic_key or None,
        )
    if anthropic_key:
        return LLMClient(provider="anthropic", api_key=anthropic_key)

    # No keys configured — return noop client
    return LLMClient(provider="noop", api_key="")


class LLMClient:
    """Thin wrapper around OpenRouter or Anthropic SDK.

    complete() always returns a string and never raises.
    Markdown code fences are stripped automatically.
    """

    def __init__(self, provider: str, api_key: str, base_url: str = None, anthropic_fallback_key: str = None):
        self.provider = provider
        self.api_key = api_key
        self.base_url = base_url or OPENROUTER_BASE_URL
        self.anthropic_fallback_key = anthropic_fallback_key

        self._openai_client = None
        self._anthropic_client = None
        self._anthropic_fallback_client = None

        if provider == "openrouter" and api_key:
            try:
                import openai
                self._openai_client = openai.OpenAI(
                    base_url=self.base_url,
                    api_key=api_key,
                )
            except Exception:
                pass
            if anthropic_fallback_key:
                try:
                    import anthropic
                    self._anthropic_fallback_client = anthropic.Anthropic(api_key=anthropic_fallback_key)
                except Exception:
                    pass

        elif provider == "anthropic" and api_key:
            try:
                import anthropic
                self._anthropic_client = anthropic.Anthropic(api_key=api_key)
            except Exception:
                pass

    def complete(
        self,
        system: str,
        user: str,
        model: str,
        max_tokens: int = 200,
    ) -> str:
        """Send a completion request. Returns the response text string.

        Strips markdown code fences. Returns "" on any failure.
        If OpenRouter fails and a fallback Anthropic key is configured, retries with Anthropic.
        """
        if self.provider == "noop" or not self.api_key:
            return ""

        if self.provider == "openrouter":
            text = self._complete_openrouter(system, user, model, max_tokens)
            if text == "" and self._anthropic_fallback_client is not None:
                text = self._complete_anthropic(
                    self._anthropic_fallback_client,
                    system, user,
                    model="claude-haiku-4-5-20251001",
                    max_tokens=max_tokens,
                )
            return text

        if self.provider == "anthropic":
            return self._complete_anthropic(
                self._anthropic_client, system, user, model, max_tokens
            )

        return ""

    def _complete_openrouter(self, system: str, user: str, model: str, max_tokens: int) -> str:
        try:
            client = self._openai_client
            if client is None:
                return ""
            response = client.chat.completions.create(
                model=model,
                max_tokens=max_tokens,
                messages=[
                    {"role": "system", "content": system},
                    {"role": "user", "content": user},
                ],
            )
            text = response.choices[0].message.content or ""
            return _strip_fences(text)
        except Exception:
            return ""

    def _complete_anthropic(self, client, system: str, user: str, model: str, max_tokens: int) -> str:
        try:
            if client is None:
                return ""
            response = client.messages.create(
                model=model,
                max_tokens=max_tokens,
                system=system,
                messages=[{"role": "user", "content": user}],
            )
            if not response.content:
                return ""
            text = response.content[0].text or ""
            return _strip_fences(text)
        except Exception:
            return ""


def _strip_fences(text: str) -> str:
    """Strip markdown code fences from LLM response."""
    text = text.strip()
    if text.startswith("```"):
        text = text.split("```")[1].lstrip("\n")
        if text.startswith("json"):
            text = text[4:]
        text = text.strip()
        # Remove closing fence if present
        if text.endswith("```"):
            text = text[:-3].strip()
    return text
