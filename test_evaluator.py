import json
import os
import unittest
from unittest.mock import patch, MagicMock
from evaluator import (
    search_registry,
    rank_recommendations,
    build_recommendation_list,
    describe_cc_tool
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


class TestSearchOneTermHTTP(unittest.TestCase):
    """_search_one_term must use skills.sh HTTP API, not npx subprocess."""

    def _mock_get(self, skills):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {"skills": skills}
        return mock_resp

    def test_parses_api_response_into_skill_id_format(self):
        """source@name format must be constructed from API fields."""
        api_skills = [
            {"name": "flutter-layout", "source": "flutter/skills", "id": "flutter/skills/flutter-layout", "installs": 100},
            {"name": "flutter-state", "source": "flutter/skills", "id": "flutter/skills/flutter-state", "installs": 80},
        ]
        with patch("evaluator.requests.get", return_value=self._mock_get(api_skills)), \
             patch("evaluator._load_cache", return_value={}), \
             patch("evaluator._save_cache"):
            from evaluator import _search_one_term
            result = _search_one_term("flutter")
        assert len(result) == 2
        assert result[0]["id"] == "flutter/skills@flutter-layout"
        assert "description" in result[0]

    def test_returns_empty_on_http_exception(self):
        """Must return [] without raising when requests throws."""
        with patch("evaluator.requests.get", side_effect=Exception("network error")), \
             patch("evaluator._load_cache", return_value={}):
            from evaluator import _search_one_term
            result = _search_one_term("anything")
        assert result == []

    def test_returns_empty_on_non_200_response(self):
        """Must return [] when API returns non-200 status."""
        mock_resp = MagicMock()
        mock_resp.status_code = 503
        with patch("evaluator.requests.get", return_value=mock_resp), \
             patch("evaluator._load_cache", return_value={}):
            from evaluator import _search_one_term
            result = _search_one_term("anything")
        assert result == []

    def test_does_not_use_subprocess(self):
        """subprocess must not be called — HTTP API replaced it."""
        import evaluator
        assert not hasattr(evaluator, "subprocess"), \
            "subprocess import must be removed from evaluator.py"


class TestSearchRegistry(unittest.TestCase):
    def test_returns_list_for_known_type(self):
        result = search_registry("flutter")
        assert isinstance(result, list)

    def test_returns_empty_list_on_failure(self):
        with patch("evaluator.requests.get", side_effect=Exception("fail")), \
             patch("evaluator._load_cache", return_value={}):
            result = search_registry("anything")
        assert result == []

    def test_returns_dicts_with_id_and_description(self):
        """search_registry must return list of dicts, not bare strings."""
        result = search_registry("flutter")
        if result:
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
    def _mock_response(self, text):
        mock_resp = MagicMock()
        mock_resp.content = [MagicMock(text=text)]
        return mock_resp

    def test_returns_cc_score_and_all(self):
        from evaluator import rank_recommendations
        payload = json.dumps({
            "cc_score": 72,
            "all": [{"name": "owner/repo@skill", "score": 88, "installed": False,
                     "install_cmd": "npx skills add owner/repo@skill -y",
                     "reason": "Better for this task"}]
        })
        with patch("evaluator.get_client") as mock_get_client:
            mock_llm = MagicMock()
            mock_get_client.return_value = mock_llm
            mock_llm.complete.return_value = payload
            result = rank_recommendations(
                task_type="flutter-building",
                registry_results=[{"id": "owner/repo@skill", "description": "Flutter skill"}],
                context_snippet="building a flutter widget",
                cc_tool="superpowers:brainstorming",
                cc_tool_description="Brainstorm before building"
            )
        assert "cc_score" in result
        assert isinstance(result["cc_score"], int)
        assert "all" in result
        assert len(result["all"]) == 1

    def test_returns_safe_default_on_api_failure(self):
        from evaluator import rank_recommendations
        with patch("evaluator.get_client", side_effect=Exception("no key")):
            result = rank_recommendations("flutter", [], cc_tool="some-tool")
        assert result == {"cc_score": 0, "all": []}

    def test_strips_markdown_wrapper(self):
        from evaluator import rank_recommendations
        # llm_client.complete() strips fences before returning — so evaluator receives clean JSON
        clean = '{"cc_score": 65, "all": []}'
        with patch("evaluator.get_client") as mock_get_client:
            mock_llm = MagicMock()
            mock_get_client.return_value = mock_llm
            mock_llm.complete.return_value = clean
            result = rank_recommendations("general", [], cc_tool="x")
        assert result["cc_score"] == 65

    def test_no_cc_tool_still_works(self):
        from evaluator import rank_recommendations
        payload = json.dumps({"cc_score": 0, "all": []})
        with patch("evaluator.get_client") as mock_get_client:
            mock_llm = MagicMock()
            mock_get_client.return_value = mock_llm
            mock_llm.complete.return_value = payload
            result = rank_recommendations("general", [])
        assert result == {"cc_score": 0, "all": []}


class TestBuildRecommendationList(unittest.TestCase):
    def _mock_rank(self, task_type, registry_results, context_snippet=None, cc_tool=None, cc_tool_description=None, model=None):
        return {
            "cc_score": 70,
            "all": [
                {"name": "owner/repo@flutter-skill", "score": 88, "installed": False,
                 "install_cmd": "npx skills add owner/repo@flutter-skill -y",
                 "reason": "Highly relevant"}
            ]
        }

    def test_returns_required_keys(self):
        with patch("evaluator.search_registry", return_value=[]), \
             patch("evaluator.rank_recommendations", side_effect=self._mock_rank):
            result = build_recommendation_list("flutter-building", cc_tool="superpowers:brainstorming")
        assert "all" in result
        assert "top_pick" in result
        assert "cc_score" in result

    def test_cc_score_passed_through(self):
        with patch("evaluator.search_registry", return_value=[]), \
             patch("evaluator.rank_recommendations", side_effect=self._mock_rank):
            result = build_recommendation_list("flutter-building", cc_tool="superpowers:brainstorming")
        assert result["cc_score"] == 70

    def test_score_gap_truncation_applied(self):
        tools = [
            {"name": "a", "score": 90, "installed": False},
            {"name": "b", "score": 60, "installed": False},  # 30-point gap — truncate here
            {"name": "c", "score": 55, "installed": False},
        ]
        with patch("evaluator.search_registry", return_value=[]), \
             patch("evaluator.rank_recommendations", return_value={"cc_score": 50, "all": tools}):
            result = build_recommendation_list("anything")
        assert len(result["all"]) == 1
        assert result["all"][0]["name"] == "a"

    def test_install_url_derived_from_skill_id(self):
        tools = [{"name": "vercel-labs/skills@react-skill", "score": 80, "installed": False,
                  "install_cmd": "npx skills add vercel-labs/skills@react-skill -y"}]
        with patch("evaluator.search_registry", return_value=[]), \
             patch("evaluator.rank_recommendations", return_value={"cc_score": 60, "all": tools}):
            result = build_recommendation_list("react")
        item = result["all"][0]
        assert item.get("install_url") == "https://github.com/vercel-labs/skills"

    def test_no_installed_or_suggested_keys(self):
        with patch("evaluator.search_registry", return_value=[]), \
             patch("evaluator.rank_recommendations", return_value={"cc_score": 0, "all": []}):
            result = build_recommendation_list("general")
        assert "installed" not in result
        assert "suggested" not in result

    def test_uses_category_search_when_category_id_provided(self):
        from evaluator import build_recommendation_list
        search_calls = []
        def mock_search_by_cat(category_id):
            search_calls.append(category_id)
            return []
        with patch("evaluator.search_by_category", side_effect=mock_search_by_cat), \
             patch("evaluator.search_registry", return_value=[]) as mock_registry, \
             patch("evaluator.rank_recommendations", return_value={"cc_score": 0, "all": []}):
            build_recommendation_list("flutter-building", category_id="mobile")
        assert len(search_calls) == 1
        assert search_calls[0] == "mobile"
        mock_registry.assert_not_called()


class TestBuildRecommendationListWithContext(unittest.TestCase):
    @patch('evaluator.search_registry', return_value=[])
    @patch('evaluator.rank_recommendations')
    def test_passes_context_snippet_to_rank(self, mock_rank, _registry):
        """context_snippet is accepted and forwarded without crashing."""
        mock_rank.return_value = {"cc_score": 0, "all": []}
        result = build_recommendation_list(
            "flutter",
            context_snippet="debugging a null pointer crash in my Flutter widget"
        )
        assert isinstance(result, dict)
        assert "all" in result
        assert "cc_score" in result
        _, kwargs = mock_rank.call_args
        assert kwargs.get("context_snippet") == "debugging a null pointer crash in my Flutter widget"


class TestRankHandlesEmptyContentList(unittest.TestCase):
    def test_rank_handles_empty_content_list(self):
        with patch("evaluator.get_client") as mock_get_client:
            mock_llm = MagicMock()
            mock_get_client.return_value = mock_llm
            mock_llm.complete.return_value = ""
            result = rank_recommendations("flutter", [])
        assert result == {"cc_score": 0, "all": []}


class TestBuildRecommendationListInstallUrl(unittest.TestCase):
    @patch('evaluator.search_registry', return_value=[])
    @patch('evaluator.rank_recommendations')
    def test_adds_install_url_for_uninstalled_skill(self, mock_rank, _registry):
        mock_rank.return_value = {
            "cc_score": 0,
            "all": [{"name": "firebase/agent-skills@firebase-basics", "score": 75,
                     "installed": False, "install_cmd": "npx skills add firebase/agent-skills@firebase-basics -y",
                     "reason": "Firebase support"}]
        }
        result = build_recommendation_list("flutter")
        item = result["all"][0]
        assert item.get("install_url") == "https://github.com/firebase/agent-skills"
        assert len(result["all"]) == 1

    @patch('evaluator.search_registry', return_value=[])
    @patch('evaluator.rank_recommendations')
    def test_top_pick_is_first_item(self, mock_rank, _registry):
        mock_rank.return_value = {
            "cc_score": 0,
            "all": [
                {"name": "top-tool", "score": 90, "installed": False, "reason": "best"},
                {"name": "second-tool", "score": 70, "installed": False,
                 "install_cmd": "npx skills add owner/repo@second-tool -y", "reason": "good"}
            ]
        }
        result = build_recommendation_list("flutter")
        assert result["top_pick"]["name"] == "top-tool"
        assert result["top_pick"]["score"] == 90

    @patch('evaluator.search_registry', return_value=[])
    @patch('evaluator.rank_recommendations')
    def test_top_pick_is_none_when_no_tools(self, mock_rank, _registry):
        mock_rank.return_value = {"cc_score": 0, "all": []}
        result = build_recommendation_list("flutter")
        assert result["top_pick"] is None


class TestScoreGapTruncation(unittest.TestCase):
    @patch('evaluator.search_registry', return_value=[])
    @patch('evaluator.rank_recommendations')
    def test_cuts_after_25_point_cliff(self, mock_rank, _registry):
        mock_rank.return_value = {
            "cc_score": 0,
            "all": [
                {"name": "a", "score": 90, "installed": False, "reason": "top"},
                {"name": "b", "score": 85, "installed": False, "reason": "good"},
                {"name": "c", "score": 72, "installed": False, "reason": "ok"},
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
            "cc_score": 0,
            "all": [
                {"name": "a", "score": 90, "installed": False, "reason": "top"},
                {"name": "b", "score": 68, "installed": False, "reason": "ok"},
            ]
        }
        result = build_recommendation_list("flutter")
        # 90 → 68 = 22-point gap, under threshold — keep both
        assert len(result["all"]) == 2

    @patch('evaluator.search_registry', return_value=[])
    @patch('evaluator.rank_recommendations')
    def test_cut_at_exact_25_point_gap(self, mock_rank, _registry):
        mock_rank.return_value = {
            "cc_score": 0,
            "all": [
                {"name": "a", "score": 80, "installed": False, "reason": "top"},
                {"name": "b", "score": 55, "installed": False, "install_cmd": "npx skills add x/y@b -y", "reason": "ok"},
                {"name": "c", "score": 50, "installed": False, "install_cmd": "npx skills add x/y@c -y", "reason": "low"},
            ]
        }
        result = build_recommendation_list("flutter")
        # 80 → 55 = exactly 25-point gap — cut after "a"
        assert len(result["all"]) == 1
        assert result["all"][0]["name"] == "a"


class TestRankRecommendationsModel(unittest.TestCase):
    def test_uses_provided_model(self):
        """rank_recommendations passes the model param to llm_client.complete."""
        with patch("evaluator.get_client") as mock_get_client:
            mock_llm = MagicMock()
            mock_get_client.return_value = mock_llm
            mock_llm.complete.return_value = '{"all": []}'

            rank_recommendations("flutter", [], model="claude-sonnet-4-6")

            _, kwargs = mock_llm.complete.call_args
            assert kwargs["model"] == "claude-sonnet-4-6"

    @patch('evaluator.search_registry', return_value=[])
    @patch('evaluator.rank_recommendations')
    def test_build_passes_model_to_rank(self, mock_rank, _registry):
        """build_recommendation_list forwards model param to rank_recommendations."""
        mock_rank.return_value = {"cc_score": 0, "all": []}
        build_recommendation_list("flutter", model="claude-sonnet-4-6")
        _, kwargs = mock_rank.call_args
        assert kwargs.get("model") == "claude-sonnet-4-6"

    @patch('evaluator.search_registry', return_value=[])
    @patch('evaluator.rank_recommendations')
    def test_build_defaults_to_haiku(self, mock_rank, _registry):
        """build_recommendation_list defaults to Haiku when model not specified."""
        mock_rank.return_value = {"cc_score": 0, "all": []}
        build_recommendation_list("flutter")
        _, kwargs = mock_rank.call_args
        assert kwargs.get("model") == "claude-haiku-4-5-20251001"


class TestDescribeCcTool(unittest.TestCase):
    def test_returns_string(self):
        result = describe_cc_tool("superpowers:brainstorming")
        assert isinstance(result, str)

    def test_returns_empty_string_on_unknown(self):
        result = describe_cc_tool("nonexistent-tool-xyz-abc")
        assert result == ""

    def test_finds_skill_in_cache(self):
        fake_cache = {
            "installed_skills": {
                "data": [
                    {"id": "superpowers:brainstorming", "description": "Brainstorm before building"}
                ],
                "fetched_at": 9999999999
            }
        }
        with patch("evaluator._load_cache", return_value=fake_cache):
            result = describe_cc_tool("superpowers:brainstorming")
        assert result == "Brainstorm before building"

    def test_finds_mcp_server_by_prefix(self):
        fake_mcp = json.dumps({
            "mcpServers": {
                "github": {"description": "GitHub API integration"}
            }
        })
        with patch("builtins.open", unittest.mock.mock_open(read_data=fake_mcp)):
            result = describe_cc_tool("github (create_pull_request)")
        assert "GitHub" in result

    def test_empty_string_input_returns_empty(self):
        result = describe_cc_tool("")
        assert result == ""


class TestSearchByCategory(unittest.TestCase):
    def test_returns_empty_when_load_categories_unavailable(self):
        from evaluator import search_by_category
        with patch("evaluator._load_categories", None):
            result = search_by_category("mobile")
        assert result == []

    def test_returns_list(self):
        from evaluator import search_by_category
        mock_cats = [{"id": "mobile", "search_terms": ["flutter", "react-native"]}]
        with patch("evaluator._load_categories", return_value=mock_cats):
            with patch("evaluator._search_one_term", return_value=[]):
                result = search_by_category("mobile")
        assert isinstance(result, list)

    def test_unknown_category_id_returns_empty(self):
        from evaluator import search_by_category
        mock_cats = [{"id": "mobile", "search_terms": ["flutter"]}]
        with patch("evaluator._load_categories", return_value=mock_cats):
            result = search_by_category("nonexistent-category-xyz")
        assert result == []

    def test_searches_category_terms(self):
        from evaluator import search_by_category
        mock_cats = [{"id": "mobile", "search_terms": ["flutter", "react-native"]}]
        calls = []
        def mock_search(term, limit=5):
            calls.append(term)
            return []
        with patch("evaluator._load_categories", return_value=mock_cats):
            with patch("evaluator._search_one_term", side_effect=mock_search):
                search_by_category("mobile")
        assert calls == ["flutter", "react-native"]

    def test_deduplicates_results(self):
        from evaluator import search_by_category
        mock_cats = [{"id": "mobile", "search_terms": ["flutter", "react-native"]}]
        duplicate = {"id": "owner/repo@skill", "description": "desc"}
        with patch("evaluator._load_categories", return_value=mock_cats):
            with patch("evaluator._search_one_term", return_value=[duplicate]):
                result = search_by_category("mobile")
        ids = [r["id"] for r in result]
        assert len(ids) == len(set(ids))


class TestMcpServerFiltering(unittest.TestCase):
    """T1.4b: build_recommendation_list must filter already-installed MCPs."""

    def test_filters_mcp_already_in_stack_profile(self):
        """mcp:github should be excluded when stack_profile contains 'github'."""
        tools = [
            {"name": "mcp:github", "score": 80, "installed": False, "reason": "GitHub"},
            {"name": "mcp:postgres", "score": 75, "installed": False, "reason": "Postgres"},
        ]
        with patch("evaluator.search_registry", return_value=[]), \
             patch("evaluator.rank_recommendations", return_value={"cc_score": 60, "all": tools}):
            result = build_recommendation_list(
                "github-building",
                stack_profile={"mcp_servers": ["github"], "languages": []}
            )
        names = [t["name"] for t in result["all"]]
        assert "mcp:github" not in names, "Already-installed MCP must be filtered out"
        assert "mcp:postgres" in names

    def test_filters_multiple_installed_mcps(self):
        tools = [
            {"name": "mcp:github", "score": 85, "installed": False, "reason": "a"},
            {"name": "mcp:postgres", "score": 80, "installed": False, "reason": "b"},
            {"name": "owner/repo@skill", "score": 70, "installed": False, "reason": "c"},
        ]
        with patch("evaluator.search_registry", return_value=[]), \
             patch("evaluator.rank_recommendations", return_value={"cc_score": 50, "all": tools}):
            result = build_recommendation_list(
                "task",
                stack_profile={"mcp_servers": ["github", "postgres"], "languages": []}
            )
        names = [t["name"] for t in result["all"]]
        assert "mcp:github" not in names
        assert "mcp:postgres" not in names
        assert "owner/repo@skill" in names

    def test_no_stack_profile_returns_all(self):
        tools = [{"name": "mcp:github", "score": 80, "installed": False, "reason": "a"}]
        with patch("evaluator.search_registry", return_value=[]), \
             patch("evaluator.rank_recommendations", return_value={"cc_score": 50, "all": tools}):
            result = build_recommendation_list("task", stack_profile=None)
        assert len(result["all"]) == 1

    def test_empty_mcp_servers_list_returns_all(self):
        tools = [{"name": "mcp:github", "score": 80, "installed": False, "reason": "a"}]
        with patch("evaluator.search_registry", return_value=[]), \
             patch("evaluator.rank_recommendations", return_value={"cc_score": 50, "all": tools}):
            result = build_recommendation_list(
                "task", stack_profile={"mcp_servers": [], "languages": []}
            )
        assert len(result["all"]) == 1


class TestOfficialPluginNoInstallCmd(unittest.TestCase):
    """T4.2: official plugins must never have install_cmd set — install_url only."""

    def test_search_official_plugins_returns_no_install_cmd(self):
        """_search_official_plugins results must not include install_cmd."""
        from evaluator import _search_official_plugins
        fake_plugins = [
            {"name": "typescript-lsp", "description": "TS language server",
             "category": "development", "source": "./plugins/typescript-lsp"}
        ]
        with patch("evaluator.requests.get") as mock_get, \
             patch("evaluator._load_cache", return_value={}), \
             patch("evaluator._save_cache"):
            mock_resp = MagicMock()
            mock_resp.status_code = 200
            mock_resp.json.return_value = fake_plugins
            mock_get.return_value = mock_resp
            result = _search_official_plugins("backend-frameworks")

        for item in result:
            assert "install_cmd" not in item or not item["install_cmd"], \
                f"Official plugin must not have install_cmd, got: {item}"


class TestSearchByCategoryPrefixBehavior(unittest.TestCase):
    """BUG-B: search_by_category must use mcp_search_terms for glama, prefix results correctly."""

    def _cat(self, search_terms=None, mcp_search_terms=None):
        return [{"id": "database", "search_terms": search_terms or ["sql"],
                 "mcp_search_terms": mcp_search_terms or ["postgresql", "mysql"]}]

    def test_uses_mcp_search_terms_for_glama_not_search_terms(self):
        """Glama call uses mcp_search_terms[0], not search_terms[0]."""
        from evaluator import search_by_category
        glama_calls = []

        def mock_glama(term, limit=5):
            glama_calls.append(term)
            return []

        cats = self._cat(search_terms=["sql"], mcp_search_terms=["postgresql"])
        with patch("evaluator._load_categories", return_value=cats), \
             patch("evaluator._search_one_term", return_value=[]), \
             patch("evaluator._search_official_plugins", return_value=[]), \
             patch("evaluator._search_glama", side_effect=mock_glama):
            search_by_category("database")

        assert "postgresql" in glama_calls, f"Expected 'postgresql' glama call, got {glama_calls}"
        assert "sql" not in glama_calls, "Glama must use mcp_search_terms not search_terms"

    def test_glama_results_prefixed_with_mcp(self):
        """Glama results must have 'mcp:' prefix in returned ids."""
        from evaluator import search_by_category
        cats = self._cat()
        with patch("evaluator._load_categories", return_value=cats), \
             patch("evaluator._search_one_term", return_value=[]), \
             patch("evaluator._search_official_plugins", return_value=[]), \
             patch("evaluator._search_glama", return_value=[{"id": "postgres", "description": "PG MCP"}]):
            result = search_by_category("database")

        ids = [r["id"] for r in result]
        assert any(i.startswith("mcp:") for i in ids), f"No mcp: prefix found in {ids}"
        assert "mcp:postgres" in ids

    def test_official_plugins_prefixed_with_plugin_anthropic(self):
        """Official plugin results must have 'plugin:anthropic:' prefix."""
        from evaluator import search_by_category
        cats = [{"id": "testing", "search_terms": ["test"],
                 "mcp_search_terms": ["pytest"]}]
        with patch("evaluator._load_categories", return_value=cats), \
             patch("evaluator._search_one_term", return_value=[]), \
             patch("evaluator._search_official_plugins", return_value=[
                 {"id": "plugin:anthropic:my-plugin", "description": "Official plugin"}
             ]), \
             patch("evaluator._search_glama", return_value=[]):
            result = search_by_category("testing")

        ids = [r["id"] for r in result]
        assert any(i.startswith("plugin:anthropic:") for i in ids), f"No plugin:anthropic: prefix in {ids}"

    def test_search_by_category_merges_all_three_sources(self):
        """When all sources return data, result contains entries from all three."""
        from evaluator import search_by_category
        cats = self._cat()
        with patch("evaluator._load_categories", return_value=cats), \
             patch("evaluator._search_one_term", return_value=[
                 {"id": "owner/repo@sql-skill", "description": "SQL skill"}
             ]), \
             patch("evaluator._search_official_plugins", return_value=[
                 {"id": "plugin:anthropic:db-plugin", "description": "DB plugin"}
             ]), \
             patch("evaluator._search_glama", return_value=[
                 {"id": "postgres-mcp", "description": "Postgres MCP"}
             ]):
            result = search_by_category("database")

        ids = [r["id"] for r in result]
        assert any("@" in i for i in ids), "Missing skill result"
        assert any(i.startswith("plugin:anthropic:") for i in ids), "Missing plugin result"
        assert any(i.startswith("mcp:") for i in ids), "Missing MCP result"


class TestTwoTierRanking(unittest.TestCase):
    """build_recommendation_list returns described/general split."""

    def _make_tools(self):
        return [
            {"name": "owner/repo@with-desc", "score": 85, "installed": False,
             "reason": "Has a real description.", "install_cmd": "npx skills add owner/repo@with-desc -y",
             "description": "Provides Flutter widget testing patterns."},
            {"name": "owner/repo@no-desc", "score": 80, "installed": False,
             "reason": "", "install_cmd": "npx skills add owner/repo@no-desc -y",
             "description": ""},
        ]

    def test_described_tools_in_described_list(self):
        """Tools with non-empty description go into 'described' list."""
        import evaluator
        with patch.object(evaluator, "search_by_category", return_value=[]), \
             patch.object(evaluator, "rank_recommendations", return_value={
                 "cc_score": 60, "all": self._make_tools()}):
            result = evaluator.build_recommendation_list("flutter-fixing", category_id="mobile-development")
        described_names = [t["name"] for t in result["described"]]
        assert "owner/repo@with-desc" in described_names

    def test_undescribed_tools_in_general_list(self):
        """Tools without description go into 'general' list."""
        import evaluator
        with patch.object(evaluator, "search_by_category", return_value=[]), \
             patch.object(evaluator, "rank_recommendations", return_value={
                 "cc_score": 60, "all": self._make_tools()}):
            result = evaluator.build_recommendation_list("flutter-fixing", category_id="mobile-development")
        general_names = [t["name"] for t in result["general"]]
        assert "owner/repo@no-desc" in general_names

    def test_top_pick_comes_from_described_first(self):
        """top_pick is first item from described list, not general."""
        import evaluator
        with patch.object(evaluator, "search_by_category", return_value=[]), \
             patch.object(evaluator, "rank_recommendations", return_value={
                 "cc_score": 60, "all": self._make_tools()}):
            result = evaluator.build_recommendation_list("flutter-fixing", category_id="mobile-development")
        assert result["top_pick"]["name"] == "owner/repo@with-desc"

    def test_all_list_still_populated_for_backward_compat(self):
        """'all' key still present and contains union of both tiers."""
        import evaluator
        with patch.object(evaluator, "search_by_category", return_value=[]), \
             patch.object(evaluator, "rank_recommendations", return_value={
                 "cc_score": 60, "all": self._make_tools()}):
            result = evaluator.build_recommendation_list("flutter-fixing", category_id="mobile-development")
        assert "all" in result
        assert len(result["all"]) == 2


if __name__ == '__main__':
    unittest.main()
