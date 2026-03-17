import json
import os
import tempfile
import unittest
from unittest.mock import patch


SAMPLE_CATEGORIES = [
    {
        "id": "source-control",
        "label": "Source Control & GitHub",
        "search_terms": ["github", "git", "pull-request", "branch", "shipping"],
        "example_tools": []
    },
    {
        "id": "data-storage",
        "label": "Database & SQL",
        "search_terms": ["database", "sql", "postgres", "supabase", "rls"],
        "example_tools": []
    },
    {
        "id": "mobile",
        "label": "Mobile Development",
        "search_terms": ["flutter", "react-native", "ios", "android"],
        "example_tools": []
    },
]


class TestLoadCategories(unittest.TestCase):
    def test_loads_categories_json(self):
        from category_mapper import load_categories
        result = load_categories()
        assert isinstance(result, list)
        assert len(result) > 0

    def test_returns_empty_on_missing_file(self):
        from category_mapper import load_categories
        with patch("category_mapper.CATEGORIES_FILE", "/nonexistent/path.json"):
            result = load_categories()
        assert result == []

    def test_each_category_has_required_fields(self):
        from category_mapper import load_categories
        cats = load_categories()
        for cat in cats:
            assert "id" in cat, f"Missing 'id' in {cat}"
            assert "search_terms" in cat, f"Missing 'search_terms' in {cat}"
            assert isinstance(cat["search_terms"], list)


class TestMapToCategory(unittest.TestCase):
    def test_maps_github_task_to_source_control(self):
        from category_mapper import map_to_category
        result = map_to_category("github-shipping", SAMPLE_CATEGORIES)
        assert result == "source-control"

    def test_maps_supabase_to_data_storage(self):
        from category_mapper import map_to_category
        result = map_to_category("supabase-rls-policy", SAMPLE_CATEGORIES)
        assert result == "data-storage"

    def test_maps_flutter_to_mobile(self):
        from category_mapper import map_to_category
        result = map_to_category("flutter-building", SAMPLE_CATEGORIES)
        assert result == "mobile"

    def test_returns_none_for_unknown(self):
        from category_mapper import map_to_category
        result = map_to_category("quantum-computing-simulation", SAMPLE_CATEGORIES)
        assert result is None

    def test_returns_none_for_empty_task_type(self):
        from category_mapper import map_to_category
        assert map_to_category("", SAMPLE_CATEGORIES) is None

    def test_matching_is_case_insensitive(self):
        from category_mapper import map_to_category
        result = map_to_category("GitHub-PR-Review", SAMPLE_CATEGORIES)
        assert result == "source-control"

    def test_hyphen_normalized_for_matching(self):
        from category_mapper import map_to_category
        result = map_to_category("react-native-building", SAMPLE_CATEGORIES)
        assert result == "mobile"


class TestLogUnknownCategory(unittest.TestCase):
    def test_appends_to_log_file(self):
        from category_mapper import log_unknown_category
        with tempfile.NamedTemporaryFile(mode="w", suffix=".jsonl", delete=False) as f:
            log_path = f.name
        try:
            log_unknown_category("quantum-simulation", log_file=log_path)
            with open(log_path) as f:
                lines = [l for l in f.readlines() if l.strip()]
            assert len(lines) == 1
            entry = json.loads(lines[0])
            assert entry["task_type"] == "quantum-simulation"
            assert "logged_at" in entry
        finally:
            os.unlink(log_path)

    def test_appends_multiple_entries(self):
        from category_mapper import log_unknown_category
        with tempfile.NamedTemporaryFile(mode="w", suffix=".jsonl", delete=False) as f:
            log_path = f.name
        try:
            log_unknown_category("task-a", log_file=log_path)
            log_unknown_category("task-b", log_file=log_path)
            with open(log_path) as f:
                lines = [l for l in f.readlines() if l.strip()]
            assert len(lines) == 2
        finally:
            os.unlink(log_path)

    def test_silently_fails_on_bad_path(self):
        from category_mapper import log_unknown_category
        log_unknown_category("test", log_file="/nonexistent/dir/log.jsonl")


SAMPLE_TAXONOMY = {
    "version": "2.0.0",
    "categories": [
        {
            "id": "data-storage",
            "subcategories": [
                {
                    "id": "relational",
                    "leaves": [
                        {"id": "postgresql", "tags": ["postgres", "postgresql", "rls", "migration", "query", "sql"]},
                        {"id": "mysql",      "tags": ["mysql", "mariadb", "sql"]},
                    ],
                },
                {
                    "id": "key-value",
                    "leaves": [
                        {"id": "redis", "tags": ["redis", "cache", "queue", "pub-sub"]},
                    ],
                },
            ],
        },
        {
            "id": "source-control",
            "subcategories": [
                {
                    "id": "git-platforms",
                    "leaves": [
                        {"id": "github", "tags": ["github", "pr", "pull-request", "issue", "branch", "git"]},
                    ],
                },
            ],
        },
        {
            "id": "mobile",
            "subcategories": [
                {
                    "id": "cross-platform",
                    "leaves": [
                        {"id": "flutter", "tags": ["flutter", "dart", "widget", "ios", "android"]},
                    ],
                },
            ],
        },
    ],
}


class TestLoadTaxonomy(unittest.TestCase):
    def test_loads_taxonomy_json(self):
        from category_mapper import load_taxonomy
        result = load_taxonomy()
        # taxonomy.json must exist and have categories list
        assert isinstance(result, dict)
        # Allow empty dict if file missing in test env; just verify no crash
        assert "categories" in result or result == {}

    def test_returns_empty_on_missing_file(self):
        from category_mapper import load_taxonomy
        with patch("category_mapper.TAXONOMY_FILE", "/nonexistent/path.json"):
            result = load_taxonomy()
        assert result == {}


class TestMapToTaxonomyPath(unittest.TestCase):
    def test_postgres_task_maps_to_postgresql_leaf(self):
        from category_mapper import map_to_taxonomy_path
        result = map_to_taxonomy_path("postgres-query-building", SAMPLE_TAXONOMY)
        assert result["category_id"] == "data-storage"
        assert result["leaf_node_id"] == "postgresql"
        assert result["subcategory_id"] == "relational"

    def test_flutter_task_maps_to_flutter_leaf(self):
        from category_mapper import map_to_taxonomy_path
        result = map_to_taxonomy_path("flutter-building", SAMPLE_TAXONOMY)
        assert result["category_id"] == "mobile"
        assert result["leaf_node_id"] == "flutter"

    def test_github_task_maps_to_source_control(self):
        from category_mapper import map_to_taxonomy_path
        result = map_to_taxonomy_path("github-pr-review", SAMPLE_TAXONOMY)
        assert result["category_id"] == "source-control"
        assert result["leaf_node_id"] == "github"

    def test_redis_cache_maps_to_key_value(self):
        from category_mapper import map_to_taxonomy_path
        result = map_to_taxonomy_path("redis-cache-building", SAMPLE_TAXONOMY)
        assert result["category_id"] == "data-storage"
        assert result["leaf_node_id"] == "redis"

    def test_matched_tags_included_in_result(self):
        from category_mapper import map_to_taxonomy_path
        result = map_to_taxonomy_path("postgres-rls-query", SAMPLE_TAXONOMY)
        tags = result.get("tags", [])
        assert "postgres" in tags or "rls" in tags or "query" in tags

    def test_returns_dict_with_required_keys(self):
        from category_mapper import map_to_taxonomy_path
        result = map_to_taxonomy_path("postgres-building", SAMPLE_TAXONOMY)
        for key in ("category_id", "subcategory_id", "leaf_node_id", "tags", "confidence"):
            assert key in result, f"Missing key: {key}"

    def test_empty_task_returns_null_category(self):
        from category_mapper import map_to_taxonomy_path
        result = map_to_taxonomy_path("", SAMPLE_TAXONOMY)
        assert result["category_id"] is None
        assert result["leaf_node_id"] == ""

    def test_unknown_task_falls_back_gracefully(self):
        from category_mapper import map_to_taxonomy_path
        result = map_to_taxonomy_path("quantum-holographic-simulation", SAMPLE_TAXONOMY)
        # Should not raise; category_id may be None or a fallback
        assert isinstance(result, dict)
        assert "category_id" in result

    def test_confidence_positive_on_good_match(self):
        from category_mapper import map_to_taxonomy_path
        result = map_to_taxonomy_path("postgres-query-building", SAMPLE_TAXONOMY)
        assert result["confidence"] > 0

    def test_uses_real_taxonomy_when_no_arg(self):
        from category_mapper import map_to_taxonomy_path
        # Should not raise even if taxonomy.json content varies
        result = map_to_taxonomy_path("postgres-query-building")
        assert isinstance(result, dict)


class TestInterceptorTaxonomyReaders(unittest.TestCase):
    """get_subcategory / get_leaf_node / get_tags must read from state.json."""

    def _write_state(self, path, data):
        import json
        with open(path, "w") as f:
            json.dump(data, f)

    def test_get_subcategory_reads_state(self):
        import tempfile, json
        from category_mapper import map_to_taxonomy_path  # noqa: F401
        from interceptor import get_subcategory
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            json.dump({"last_subcategory": "relational"}, f)
            path = f.name
        try:
            with patch("interceptor.STATE_FILE", path):
                assert get_subcategory() == "relational"
        finally:
            os.unlink(path)

    def test_get_leaf_node_reads_state(self):
        import tempfile, json
        from interceptor import get_leaf_node
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            json.dump({"last_leaf_node": "postgresql"}, f)
            path = f.name
        try:
            with patch("interceptor.STATE_FILE", path):
                assert get_leaf_node() == "postgresql"
        finally:
            os.unlink(path)

    def test_get_tags_reads_state(self):
        import tempfile, json
        from interceptor import get_tags
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            json.dump({"last_tags": ["postgres", "rls"]}, f)
            path = f.name
        try:
            with patch("interceptor.STATE_FILE", path):
                result = get_tags()
                assert "postgres" in result
                assert "rls" in result
        finally:
            os.unlink(path)

    def test_get_subcategory_returns_empty_on_missing_file(self):
        from interceptor import get_subcategory
        with patch("interceptor.STATE_FILE", "/nonexistent/state.json"):
            assert get_subcategory() == ""

    def test_get_tags_returns_list_on_missing_file(self):
        from interceptor import get_tags
        with patch("interceptor.STATE_FILE", "/nonexistent/state.json"):
            assert get_tags() == []


if __name__ == "__main__":
    unittest.main()
