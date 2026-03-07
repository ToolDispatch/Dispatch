import json
import unittest
from unittest.mock import patch, MagicMock
from evaluator import (
    scan_installed_plugins,
    get_installed_skills,
    search_registry,
    rank_recommendations,
    build_recommendation_list
)

PLUGINS_DIR = "/home/visionairy/.claude/plugins/marketplaces"


class TestScanInstalledPlugins(unittest.TestCase):
    def test_returns_list_of_plugin_dicts(self):
        result = scan_installed_plugins(PLUGINS_DIR)
        assert isinstance(result, list)
        assert len(result) > 0
        assert all("name" in p for p in result)
        assert all("description" in p for p in result)
        assert all("marketplace" in p for p in result)

    def test_includes_known_plugin(self):
        result = scan_installed_plugins(PLUGINS_DIR)
        names = [p["name"] for p in result]
        assert any(n in names for n in ["ultrathink", "create-worktrees", "flutter-mobile-app-dev"])

    def test_handles_missing_dir_gracefully(self):
        result = scan_installed_plugins("/nonexistent/path")
        assert result == []


class TestGetInstalledSkills(unittest.TestCase):
    def test_returns_list(self):
        result = get_installed_skills()
        assert isinstance(result, list)


class TestSearchRegistry(unittest.TestCase):
    def test_returns_list_for_known_type(self):
        result = search_registry("flutter")
        assert isinstance(result, list)

    def test_returns_empty_list_on_failure(self):
        with patch("evaluator.subprocess.run", side_effect=Exception("fail")):
            result = search_registry("anything")
        assert result == []


class TestRankRecommendations(unittest.TestCase):
    @patch('evaluator.anthropic.Anthropic')
    @patch.dict('os.environ', {'ANTHROPIC_API_KEY': 'test-key'})
    def test_returns_ranked_installed_and_suggested(self, mock_client_cls):
        mock_client = MagicMock()
        mock_client_cls.return_value = mock_client
        mock_client.messages.create.return_value = MagicMock(
            content=[MagicMock(text=json.dumps({
                "installed": [
                    {"name": "flutter-mobile-app-dev", "reason": "Direct Flutter support"}
                ],
                "suggested": [
                    {"name": "firebase/agent-skills@firebase-basics",
                     "install_cmd": "npx skills add firebase/agent-skills@firebase-basics",
                     "reason": "Firebase setup"}
                ]
            }))]
        )
        result = rank_recommendations(
            task_type="flutter",
            installed_plugins=[{"name": "flutter-mobile-app-dev", "description": "Flutter dev"}],
            installed_skills=[],
            registry_results=["firebase/agent-skills@firebase-basics"]
        )
        assert "installed" in result
        assert "suggested" in result
        assert result["installed"][0]["name"] == "flutter-mobile-app-dev"

    @patch('evaluator.anthropic.Anthropic')
    def test_handles_ranking_failure_gracefully(self, mock_client_cls):
        mock_client = MagicMock()
        mock_client_cls.return_value = mock_client
        mock_client.messages.create.side_effect = Exception("API error")
        result = rank_recommendations("flutter", [], [], [])
        assert result == {"installed": [], "suggested": []}

    @patch('evaluator.anthropic.Anthropic')
    def test_handles_malformed_ranking_response(self, mock_client_cls):
        mock_client = MagicMock()
        mock_client_cls.return_value = mock_client
        mock_client.messages.create.return_value = MagicMock(
            content=[MagicMock(text="not json")]
        )
        result = rank_recommendations("flutter", [], [], [])
        assert result == {"installed": [], "suggested": []}


class TestBuildRecommendationList(unittest.TestCase):
    @patch('evaluator.rank_recommendations')
    def test_build_recommendation_list_returns_dict(self, mock_rank):
        mock_rank.return_value = {"installed": [], "suggested": []}
        result = build_recommendation_list("flutter")
        assert isinstance(result, dict)
        assert "installed" in result
        assert "suggested" in result

    @patch('evaluator.search_registry', return_value=[])
    @patch('evaluator.get_installed_skills', return_value=[])
    @patch('evaluator.rank_recommendations')
    def test_enriches_installed_items_with_marketplace(self, mock_rank, _skills, _registry):
        mock_rank.return_value = {
            "installed": [{"name": "my-plugin", "reason": "relevant"}],
            "suggested": []
        }
        fake_plugins = [{"name": "my-plugin", "description": "desc", "marketplace": "skillsmarket", "source": "installed"}]
        result = build_recommendation_list("flutter", installed_plugins=fake_plugins)
        assert result["installed"][0].get("marketplace") == "skillsmarket"

    @patch('evaluator.search_registry', return_value=[])
    @patch('evaluator.get_installed_skills', return_value=[])
    @patch('evaluator.rank_recommendations')
    def test_does_not_add_marketplace_when_absent(self, mock_rank, _skills, _registry):
        mock_rank.return_value = {
            "installed": [{"name": "my-plugin", "reason": "relevant"}],
            "suggested": []
        }
        fake_plugins = [{"name": "my-plugin", "description": "desc", "marketplace": "", "source": "installed"}]
        result = build_recommendation_list("flutter", installed_plugins=fake_plugins)
        assert "marketplace" not in result["installed"][0]


class TestBuildRecommendationListWithContext(unittest.TestCase):
    @patch('evaluator.search_registry', return_value=[])
    @patch('evaluator.get_installed_skills', return_value=[])
    @patch('evaluator.rank_recommendations')
    def test_passes_context_snippet_to_rank(self, mock_rank, _skills, _registry):
        """context_snippet is accepted and forwarded without crashing."""
        mock_rank.return_value = {"installed": [], "suggested": []}
        result = build_recommendation_list(
            "flutter",
            installed_plugins=[],
            context_snippet="debugging a null pointer crash in my Flutter widget"
        )
        assert isinstance(result, dict)
        assert "installed" in result
        assert "suggested" in result
        # Verify context_snippet was passed through to rank_recommendations
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
        assert result == {"installed": [], "suggested": []}


if __name__ == '__main__':
    unittest.main()
