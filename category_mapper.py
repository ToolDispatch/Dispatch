import json
import os
import time
from typing import Optional

CATEGORIES_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "categories.json")
UNKNOWN_LOG_FILE = os.path.expanduser("~/.claude/skill-router/unknown_categories.jsonl")


def load_categories() -> list:
    """Load category catalog from categories.json. Returns empty list on any failure."""
    try:
        with open(CATEGORIES_FILE) as f:
            return json.load(f)
    except Exception:
        return []


def map_to_category(task_type: str, categories: list = None) -> Optional[str]:
    """Map a task_type string to a category_id via keyword matching.

    Normalizes hyphens to spaces for both task_type and search_terms before matching.
    Returns the first matching category_id, or None if no match.
    """
    if not task_type:
        return None
    if categories is None:
        categories = load_categories()

    task_normalized = task_type.lower().replace("-", " ")

    for cat in categories:
        for term in cat.get("search_terms", []):
            if term.lower().replace("-", " ") in task_normalized:
                return cat["id"]
    return None


def log_unknown_category(task_type: str, log_file: str = None):
    """Append an unrecognized task_type to the unknown categories log."""
    if log_file is None:
        log_file = UNKNOWN_LOG_FILE
    try:
        entry = json.dumps({"task_type": task_type, "logged_at": time.time()})
        with open(log_file, "a") as f:
            f.write(entry + "\n")
    except Exception:
        pass
