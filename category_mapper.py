import json
import os
import time
from typing import Optional

CATEGORIES_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "categories.json")
TAXONOMY_FILE   = os.path.join(os.path.dirname(os.path.abspath(__file__)), "taxonomy.json")
UNKNOWN_LOG_FILE = os.path.expanduser("~/.claude/dispatch/unknown_categories.jsonl")


def load_taxonomy() -> dict:
    """Load taxonomy v2 from taxonomy.json. Returns empty dict on failure."""
    try:
        with open(TAXONOMY_FILE) as f:
            return json.load(f)
    except Exception:
        return {}


def map_to_taxonomy_path(task_type: str, taxonomy: dict = None) -> dict:
    """Map a task_type string to a taxonomy v2 path by keyword matching.

    Tokenizes task_type (split on hyphens/spaces) then scores each taxonomy leaf
    by overlap with its id and tags[].

    Returns:
        {category_id, subcategory_id, leaf_node_id, tags, confidence}
    Falls back to map_to_category() for category_id when no good leaf match found.
    """
    if not task_type:
        return {"category_id": None, "subcategory_id": "", "leaf_node_id": "", "tags": [], "confidence": 0}

    if taxonomy is None:
        taxonomy = load_taxonomy()

    tokens = set(task_type.lower().replace("-", " ").split())

    best_score = 0
    best_result = None

    for category in taxonomy.get("categories", []):
        cat_id = category["id"]
        for subcat in category.get("subcategories", []):
            subcat_id = subcat["id"]
            for leaf in subcat.get("leaves", []):
                leaf_id  = leaf["id"]
                leaf_tags = set(leaf.get("tags", []))

                score = 0
                # Exact leaf id in tokens
                if leaf_id in tokens:
                    score += 20
                # Leaf id substring match (both directions, min length 4)
                elif any(len(t) >= 4 and (leaf_id in t or t in leaf_id) for t in tokens):
                    score += 8
                # Token overlap with tags
                matched = tokens & leaf_tags
                score += len(matched) * 5
                # Partial tag match
                for token in tokens:
                    if len(token) < 4:
                        continue
                    for tag in leaf_tags:
                        if tag not in matched and (token in tag or tag in token):
                            score += 1

                if score > best_score:
                    best_score = score
                    best_result = {
                        "category_id":   cat_id,
                        "subcategory_id": subcat_id,
                        "leaf_node_id":  leaf_id,
                        "tags":          sorted(tokens & leaf_tags),
                        "confidence":    min(100, score * 3),
                    }

    if best_result and best_score >= 5:
        return best_result

    # Low-confidence fallback — at least get category_id from flat keyword match
    cat = map_to_category(task_type)
    return {"category_id": cat, "subcategory_id": "", "leaf_node_id": "", "tags": [], "confidence": 10 if cat else 0}


def load_categories() -> list:
    """Load category catalog from categories.json. Returns empty list on any failure."""
    try:
        with open(CATEGORIES_FILE) as f:
            return json.load(f)
    except Exception:
        return []



# Task type prefixes that don't map to a tech domain — the noun after the prefix
# tells us what category to use. E.g. "dispatch-building" → look at "building" context,
# fall back to "backend" as a general dev-tooling category.
# "general-*" and "dispatch-*" are meta-labels Haiku uses when the task is about
# the tooling/workflow itself rather than a specific technology domain.
_GENERIC_PREFIX_FALLBACK = {
    "dispatch": "backend",
    "general":  "backend",
    "tooling":  "backend",
    "coding":   "backend",
    "software": "backend",
    "agent":    "backend",
    "workflow": "integrations",
    "config":   "delivery",
    "setup":    "delivery",
    "install":  "delivery",
    "deploy":   "delivery",
    "debug":    "testing",
    "fix":      "testing",
    "fixing":   "testing",
    "debug":    "testing",
    "debugging":"testing",
    "test":     "testing",
    "testing":  "testing",
    "github":   "source-control",
    "git":      "source-control",
    "actions":  "delivery",
    "document": "documentation",
    "docs":     "documentation",
    "api":      "integrations",
    "data":     "data-storage",
    "db":       "data-storage",
    "auth":     "identity-security",
    "security": "identity-security",
    "monitor":  "observability",
    "log":      "observability",
    "search":   "search-discovery",
    "ml":       "ai-ml",
    "ai":       "ai-ml",
    "llm":      "ai-ml",
    "payment":  "payments",
    "billing":  "payments",
}


def map_to_category(task_type: str, categories: list = None) -> Optional[str]:
    """Map a task_type string to a category_id via keyword matching.

    Normalizes hyphens to spaces for both task_type and search_terms before matching.
    Falls back to prefix-based heuristics for meta task types like "dispatch-building"
    or "general-fixing" that don't contain domain-specific keywords.
    Returns the first matching category_id, or None if no match.
    """
    if not task_type:
        return None
    if categories is None:
        categories = load_categories()

    task_words = set(task_type.lower().replace("-", " ").split())

    best_cat = None
    best_len = 0
    for cat in categories:
        for term in cat.get("search_terms", []):
            term_words = term.lower().replace("-", " ").split()
            if all(w in task_words for w in term_words):
                if len(term_words) > best_len:
                    best_len = len(term_words)
                    best_cat = cat["id"]

    if best_cat:
        return best_cat

    # Prefix fallback: scan all tokens, prefer specific ones over generic catch-alls.
    # "general" and "dispatch" are low-priority — only use them if nothing more specific matches.
    _LOW_PRIORITY = {"general", "dispatch", "tooling", "coding", "software", "agent", "building", "discovering", "designing", "validating"}
    tokens = task_type.lower().replace("-", " ").split()
    specific_match = None
    generic_match = None
    for token in tokens:
        if token in _GENERIC_PREFIX_FALLBACK:
            if token in _LOW_PRIORITY:
                if generic_match is None:
                    generic_match = _GENERIC_PREFIX_FALLBACK[token]
            else:
                if specific_match is None:
                    specific_match = _GENERIC_PREFIX_FALLBACK[token]
    return specific_match or generic_match or None


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
