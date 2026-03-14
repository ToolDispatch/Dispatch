import json
import os
import unittest
from unittest.mock import patch, MagicMock
from evaluator import (
    search_registry,
    rank_recommendations,
    build_recommendation_list
)


class TestDeletedFunctions(unittest.TestCase):
    def test_scan_installed_plugins_removed(self):
        import evaluator
        assert not hasattr(evaluator, "scan_installed_plugins"), \
            "scan_installed_plugins must be removed in v0.7.0"

    def test_scan_mcp_servers_removed(self):
        import evaluator
        assert not hasattr(evaluator, "scan_mcp_servers"), \
            "scan_mcp_servers must be removed in v0.7.0"

    def test_get_installed_skills_removed(self):
        import evaluator
        assert not hasattr(evaluator, "get_installed_skills"), \
            "get_installed_skills must be removed in v0.7.0"


class TestSearchRegistry(unittest.TestCase):
    def test_returns_list_for_known_type(self):
        result = search_registry("flutter")
        assert isinstance(result, list)

    def test_returns_empty_list_on_failure(self):
        with patch("evaluator.subprocess.run", side_effect=Exception("fail")):
            result = search_registry("anything")
        assert result == []

    def test_returns_dicts_with_id_and_description(self):
        """search_registry must return list of dicts, not bare strings."""
        result = search_registry("flutter")
        if result:  # only assert structure if results returned
            assert isinstance(result[0], dict)
            assert "id" in result[0]
            assert "description" in result[0]

    def test_multi_term_search_calls_search_for_each_term(self):
        """Compound task type searches multiple terms."""
        with patch("evaluator._search_one_term") as mock_search:
            mock_search.return_value = []
            result = search_registry("firebase-flutter")
        # Both "firebase" and "flutter" terms should be searched
        assert mock_search.call_count == 2

    def test_multi_term_deduplicates_results(self):
        """Same skill from multiple term searches appears only once."""
        with patch("evaluator._search_one_term") as mock_search:
            mock_search.return_value = [{"id": "firebase/agent-skills@firebase-basics", "description": "Firebase"}]
            result = search_registry("firebase-firebase")  # same term twice (edge case)
        assert len([r for r in result if r["id"] == "firebase/agent-skills@firebase-basics"]) == 1


class TestRankRecommendations(unittest.TestCase):
    @patch('evaluator.anthropic.Anthropic')
    @patch.dict('os.environ', {'ANTHROPIC_API_KEY': 'test-key'})
    def test_returns_all_tools_with_scores(self, mock_client_cls):
        mock_client = MagicMock()
        mock_client_cls.return_value = mock_client
        mock_client.messages.create.return_value = MagicMock(
            content=[MagicMock(text=json.dumps({
                "all": [
                    {"name": "flutter-mobile-app-dev", "score": 90, "installed": True, "reason": "Direct Flutter support"},
                    {"name": "firebase/agent-skills@firebase-basics", "score": 70, "installed": False,
                     "install_cmd": "npx skills add firebase/agent-skills@firebase-basics -y",
                     "reason": "Firebase integration"}
                ]
            }))]
        )
        result = rank_recommendations(
            task_type="flutter",
            installed_plugins=[{"name": "flutter-mobile-app-dev", "description": "Flutter dev"}],
            installed_skills=[],
            registry_results=[{"id": "firebase/agent-skills@firebase-basics", "description": "Firebase integration for agents"}]
        )
        assert "all" in result
        assert len(result["all"]) == 2
        assert result["all"][0]["name"] == "flutter-mobile-app-dev"
        assert result["all"][0]["score"] == 90
        assert result["all"][1]["installed"] is False

    @patch('evaluator.anthropic.Anthropic')
    @patch.dict('os.environ', {'ANTHROPIC_API_KEY': 'test-key'})
    def test_normalizes_old_format_to_all_list(self, mock_client_cls):
        """If Haiku returns old {installed, suggested} format, convert to {all: [...]}."""
        mock_client = MagicMock()
        mock_client_cls.return_value = mock_client
        mock_client.messages.create.return_value = MagicMock(
            content=[MagicMock(text=json.dumps({
                "installed": [{"name": "flutter-mobile-app-dev", "reason": "Flutter support"}],
                "suggested": [{"name": "firebase/agent-skills@firebase-basics",
                               "install_cmd": "npx skills add firebase/agent-skills@firebase-basics -y",
                               "reason": "Firebase"}]
            }))]
        )
        result = rank_recommendations("flutter", [], [], [])
        assert "all" in result
        assert len(result["all"]) == 2
        # installed items get score 70, suggested get 60
        installed_items = [t for t in result["all"] if t.get("installed")]
        suggested_items = [t for t in result["all"] if not t.get("installed")]
        assert len(installed_items) == 1
        assert installed_items[0]["score"] == 70
        assert len(suggested_items) == 1
        assert suggested_items[0]["score"] == 60

    @patch('evaluator.anthropic.Anthropic')
    def test_handles_ranking_failure_gracefully(self, mock_client_cls):
        mock_client = MagicMock()
        mock_client_cls.return_value = mock_client
        mock_client.messages.create.side_effect = Exception("API error")
        result = rank_recommendations("flutter", [], [], [])
        assert result == {"all": []}

    @patch('evaluator.anthropic.Anthropic')
    def test_handles_malformed_ranking_response(self, mock_client_cls):
        mock_client = MagicMock()
        mock_client_cls.return_value = mock_client
        mock_client.messages.create.return_value = MagicMock(
            content=[MagicMock(text="not json")]
        )
        result = rank_recommendations("flutter", [], [], [])
        assert result == {"all": []}

    @patch('evaluator.anthropic.Anthropic')
    @patch.dict('os.environ', {'ANTHROPIC_API_KEY': 'test-key'})
    def test_passes_full_250_char_description(self, mock_client_cls):
        """Plugin description passed to Haiku is truncated at 250, not 100."""
        mock_client = MagicMock()
        mock_client_cls.return_value = mock_client
        mock_client.messages.create.return_value = MagicMock(
            content=[MagicMock(text='{"all": []}')]
        )
        long_desc = "x" * 300
        rank_recommendations(
            task_type="flutter",
            installed_plugins=[{"name": "my-plugin", "description": long_desc}],
            installed_skills=[],
            registry_results=[]
        )
        call_args = mock_client.messages.create.call_args
        user_content = call_args[1]["messages"][0]["content"]
        assert "x" * 250 in user_content
        assert "x" * 251 not in user_content


class TestBuildRecommendationList(unittest.TestCase):
    @patch('evaluator.rank_recommendations')
    def test_build_recommendation_list_returns_dict(self, mock_rank):
        mock_rank.return_value = {"all": []}
        result = build_recommendation_list("flutter")
        assert isinstance(result, dict)
        assert "all" in result
        assert "top_pick" in result
        assert "installed" in result
        assert "suggested" in result

    @patch('evaluator.search_registry', return_value=[])
    @patch('evaluator.rank_recommendations')
    def test_enriches_installed_items_with_marketplace(self, mock_rank, _registry):
        mock_rank.return_value = {
            "all": [{"name": "my-plugin", "score": 80, "installed": True, "reason": "relevant"}]
        }
        fake_plugins = [{"name": "my-plugin", "description": "desc", "marketplace": "skillsmarket", "source": "installed"}]
        result = build_recommendation_list("flutter", installed_plugins=fake_plugins)
        assert result["all"][0].get("marketplace") == "skillsmarket"
        assert result["installed"][0].get("marketplace") == "skillsmarket"

    @patch('evaluator.search_registry', return_value=[])
    @patch('evaluator.rank_recommendations')
    def test_does_not_add_marketplace_when_absent(self, mock_rank, _registry):
        mock_rank.return_value = {
            "all": [{"name": "my-plugin", "score": 80, "installed": True, "reason": "relevant"}]
        }
        fake_plugins = [{"name": "my-plugin", "description": "desc", "marketplace": "", "source": "installed"}]
        result = build_recommendation_list("flutter", installed_plugins=fake_plugins)
        assert "marketplace" not in result["all"][0]


class TestBuildRecommendationListWithContext(unittest.TestCase):
    @patch('evaluator.search_registry', return_value=[])
    @patch('evaluator.rank_recommendations')
    def test_passes_context_snippet_to_rank(self, mock_rank, _registry):
        """context_snippet is accepted and forwarded without crashing."""
        mock_rank.return_value = {"all": []}
        result = build_recommendation_list(
            "flutter",
            installed_plugins=[],
            context_snippet="debugging a null pointer crash in my Flutter widget"
        )
        assert isinstance(result, dict)
        assert "all" in result
        assert "installed" in result
        assert "suggested" in result
        _, kwargs = mock_rank.call_args
        assert kwargs.get("context_snippet") == "debugging a null pointer crash in my Flutter widget"


class TestRankHandlesEmptyContentList(unittest.TestCase):
    @patch('evaluator.anthropic.Anthropic')
    @patch.dict('os.environ', {'ANTHROPIC_API_KEY': 'test-key'})
    def test_rank_handles_empty_content_list(self, mock_client_cls):
        mock_client = MagicMock()
        mock_client_cls.return_value = mock_client
        mock_response = MagicMock()
        mock_response.content = []
        mock_client.messages.create.return_value = mock_response
        result = rank_recommendations("flutter", [], [], [])
        assert result == {"all": []}


class TestBuildRecommendationListInstallUrl(unittest.TestCase):
    @patch('evaluator.search_registry', return_value=[])
    @patch('evaluator.rank_recommendations')
    def test_adds_install_url_for_uninstalled_skill(self, mock_rank, _registry):
        mock_rank.return_value = {
            "all": [{"name": "firebase/agent-skills@firebase-basics", "score": 75,
                     "installed": False, "install_cmd": "npx skills add firebase/agent-skills@firebase-basics -y",
                     "reason": "Firebase support"}]
        }
        result = build_recommendation_list("flutter", installed_plugins=[])
        item = result["all"][0]
        assert item.get("install_url") == "https://github.com/firebase/agent-skills"
        assert len(result["suggested"]) == 1
        assert len(result["installed"]) == 0

    @patch('evaluator.search_registry', return_value=[])
    @patch('evaluator.rank_recommendations')
    def test_top_pick_is_first_item(self, mock_rank, _registry):
        mock_rank.return_value = {
            "all": [
                {"name": "top-tool", "score": 90, "installed": True, "reason": "best"},
                {"name": "second-tool", "score": 70, "installed": False,
                 "install_cmd": "npx skills add owner/repo@second-tool -y", "reason": "good"}
            ]
        }
        result = build_recommendation_list("flutter", installed_plugins=[])
        assert result["top_pick"]["name"] == "top-tool"
        assert result["top_pick"]["score"] == 90

    @patch('evaluator.search_registry', return_value=[])
    @patch('evaluator.rank_recommendations')
    def test_top_pick_is_none_when_no_tools(self, mock_rank, _registry):
        mock_rank.return_value = {"all": []}
        result = build_recommendation_list("flutter", installed_plugins=[])
        assert result["top_pick"] is None


class TestScoreGapTruncation(unittest.TestCase):
    @patch('evaluator.search_registry', return_value=[])
    @patch('evaluator.rank_recommendations')
    def test_cuts_after_25_point_cliff(self, mock_rank, _registry):
        mock_rank.return_value = {
            "all": [
                {"name": "a", "score": 90, "installed": True, "reason": "top"},
                {"name": "b", "score": 85, "installed": True, "reason": "good"},
                {"name": "c", "score": 72, "installed": True, "reason": "ok"},
                {"name": "d", "score": 44, "installed": False, "install_cmd": "npx skills add x/y@d -y", "reason": "weak"},
                {"name": "e", "score": 42, "installed": False, "install_cmd": "npx skills add x/y@e -y", "reason": "weak"},
            ]
        }
        result = build_recommendation_list("flutter")
        # 72 → 44 is a 28-point cliff; keep a, b, c only
        assert len(result["all"]) == 3
        assert result["all"][-1]["name"] == "c"

    @patch('evaluator.search_registry', return_value=[])
    @patch('evaluator.rank_recommendations')
    def test_no_cut_when_gap_under_25(self, mock_rank, _registry):
        mock_rank.return_value = {
            "all": [
                {"name": "a", "score": 90, "installed": True, "reason": "top"},
                {"name": "b", "score": 68, "installed": True, "reason": "ok"},
            ]
        }
        result = build_recommendation_list("flutter")
        # 90 → 68 = 22-point gap, under threshold — keep both
        assert len(result["all"]) == 2

    @patch('evaluator.search_registry', return_value=[])
    @patch('evaluator.rank_recommendations')
    def test_cut_at_exact_25_point_gap(self, mock_rank, _registry):
        mock_rank.return_value = {
            "all": [
                {"name": "a", "score": 80, "installed": True, "reason": "top"},
                {"name": "b", "score": 55, "installed": False, "install_cmd": "npx skills add x/y@b -y", "reason": "ok"},
                {"name": "c", "score": 50, "installed": False, "install_cmd": "npx skills add x/y@c -y", "reason": "low"},
            ]
        }
        result = build_recommendation_list("flutter")
        # 80 → 55 = exactly 25-point gap — cut after "a"
        assert len(result["all"]) == 1
        assert result["all"][0]["name"] == "a"


class TestRankRecommendationsModel(unittest.TestCase):
    @patch('evaluator.anthropic.Anthropic')
    @patch.dict('os.environ', {'ANTHROPIC_API_KEY': 'test-key'})
    def test_uses_provided_model(self, mock_client_cls):
        """rank_recommendations passes the model param to the Anthropic client."""
        mock_client = MagicMock()
        mock_client_cls.return_value = mock_client
        mock_response = MagicMock()
        mock_response.content = [MagicMock(text='{"all": []}')]
        mock_client.messages.create.return_value = mock_response

        rank_recommendations("flutter", [], [], [], model="claude-sonnet-4-6")

        _, kwargs = mock_client.messages.create.call_args
        assert kwargs["model"] == "claude-sonnet-4-6"

    @patch('evaluator.search_registry', return_value=[])
    @patch('evaluator.rank_recommendations')
    def test_build_passes_model_to_rank(self, mock_rank, _registry):
        """build_recommendation_list forwards model param to rank_recommendations."""
        mock_rank.return_value = {"all": []}
        build_recommendation_list("flutter", installed_plugins=[], model="claude-sonnet-4-6")
        _, kwargs = mock_rank.call_args
        assert kwargs.get("model") == "claude-sonnet-4-6"

    @patch('evaluator.search_registry', return_value=[])
    @patch('evaluator.rank_recommendations')
    def test_build_defaults_to_haiku(self, mock_rank, _registry):
        """build_recommendation_list defaults to Haiku when model not specified."""
        mock_rank.return_value = {"all": []}
        build_recommendation_list("flutter", installed_plugins=[])
        _, kwargs = mock_rank.call_args
        assert kwargs.get("model") == "claude-haiku-4-5-20251001"


if __name__ == '__main__':
    unittest.main()
