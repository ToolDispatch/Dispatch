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
        "id": "database",
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

    def test_maps_supabase_to_database(self):
        from category_mapper import map_to_category
        result = map_to_category("supabase-rls-policy", SAMPLE_CATEGORIES)
        assert result == "database"

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


if __name__ == "__main__":
    unittest.main()
