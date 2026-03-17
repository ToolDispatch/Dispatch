import json
import os
import re
import requests
import time
import anthropic
from llm_client import get_client, ranker_model, load_config

try:
    from category_mapper import load_categories as _load_categories
except ImportError:
    _load_categories = None

CACHE_FILE = os.path.expanduser("~/.claude/dispatch/npx_cache.json")
CACHE_TTL = 3600  # 1 hour

GLAMA_API = "https://glama.ai/api/mcp/v1/servers"
OFFICIAL_PLUGINS_URL = "https://raw.githubusercontent.com/anthropics/claude-plugins-official/main/.claude-plugin/marketplace.json"
OFFICIAL_PLUGINS_CACHE_KEY = "_official_plugins"

# Maps official plugin category labels → our MECE category IDs (v2 taxonomy)
PLUGIN_CAT_MAP = {
    "database": "data-storage",
    "deployment": "delivery",
    "design": "frontend",
    "development": "backend",
    "learning": "documentation",
    "location": "integrations",
    "migration": "data-storage",
    "monitoring": "observability",
    "productivity": "backend",
    "security": "identity-security",
    "testing": "testing",
}


def _load_cache() -> dict:
    try:
        with open(CACHE_FILE) as f:
            return json.load(f)
    except Exception:
        return {}


def _save_cache(cache: dict):
    try:
        with open(CACHE_FILE, "w") as f:
            json.dump(cache, f)
    except Exception:
        pass

RANK_SYSTEM_PROMPT = """You are a plugin recommendation engine for Claude Code.
Given a detected task type, the tool CC is about to use, and marketplace alternatives,
score CC's chosen tool AND each marketplace alternative for this specific task.

Respond with ONLY valid JSON:
{
  "cc_score": 72,
  "all": [
    {"name": "owner/repo@skill-name", "score": 88, "installed": false,
     "install_cmd": "npx skills add owner/repo@skill-name -y",
     "reason": "one specific sentence grounded in the current task"}
  ]
}

Rules:
- cc_score: 0-100 relevance score for CC's built-in tool/approach for this specific task
- all: marketplace tools only (not CC's tool); score 0-100 by relevance
- Only include marketplace tools with score >= 40
- Limit to top 5 marketplace tools, sorted by score descending
- install_cmd: if a tool has a provided install_cmd hint, use it exactly — do NOT fabricate one
- For skills (id format "owner/repo@skill-name"): install_cmd = "npx skills add owner/repo@skill-name -y"
- For MCP servers (id starting with "mcp:" or "glama:"): omit install_cmd — leave it out entirely
- For plugins (id starting with "plugin:"): use the provided install_cmd if present, else omit
- Write specific reasons grounded in what the developer is actually doing — not generic praise
- If no marketplace tools are relevant, return {"cc_score": <score>, "all": []}
- When CC tool type is "mcp": prefer MCP alternatives when scoring if they exist; a well-matched MCP
  server is directly comparable to another MCP and should score on the same 0-100 scale

Reason quality:
GOOD: "Provides Firestore query helpers directly applicable to the auth flow you are building."
BAD: "Useful for Firebase." (too generic)
GOOD: "Adds Flutter widget testing patterns matching the rendering crash you are diagnosing."
BAD: "Firebase support for agents." (repeats tool name, adds nothing)
"""


def strip_ansi(text: str) -> str:
    """Strip ANSI escape codes from text."""
    return re.sub(r'\x1b\[[0-9;]*[A-Za-z]', '', text)


def describe_cc_tool(cc_tool: str) -> str:
    """Best-effort description lookup for the tool CC is about to invoke.

    Checks installed skills cache first, then ~/.claude/.mcp.json.
    Returns empty string if nothing found — ranker uses tool name only.
    """
    if not cc_tool:
        return ""

    # Check installed skills cache (populated by search_registry calls)
    cache = _load_cache()
    skills = cache.get("installed_skills", {}).get("data", [])
    for s in skills:
        if isinstance(s, dict) and s.get("id") == cc_tool:
            return s.get("description", "")

    # Check MCP servers — cc_tool format is "server_name (operation)" or just "server_name"
    mcp_path = os.path.expanduser("~/.claude/.mcp.json")
    try:
        with open(mcp_path) as f:
            data = json.load(f)
        for server_name, config in data.get("mcpServers", {}).items():
            if server_name in cc_tool:
                return config.get("description", f"MCP server: {server_name}")
    except Exception:
        pass

    return ""


def _search_one_term(term: str, limit: int = 5) -> list:
    """Search registry for one term. Returns list of {"id", "description"}. Cached 1hr."""
    cache = _load_cache()
    registry = cache.get("registry", {})
    entry = registry.get(term, {})
    cached_data = entry.get("data", [])
    # Only use cache if fresh AND data is in new dict format (not legacy bare strings)
    if (entry
            and (time.time() - entry.get("fetched_at", 0)) < CACHE_TTL
            and (not cached_data or isinstance(cached_data[0], dict))):
        return cached_data
    try:
        resp = requests.get(
            "https://skills.sh/api/search",
            params={"q": term, "limit": limit},
            timeout=8,
        )
        if resp.status_code != 200:
            return entry.get("data", [])
        skills = []
        for skill in resp.json().get("skills", []):
            source = skill.get("source", "")
            name = skill.get("name", "")
            if source and name:
                skills.append({"id": f"{source}@{name}", "description": ""})
        skills = skills[:limit]
        if "registry" not in cache:
            cache["registry"] = {}
        cache["registry"][term] = {"data": skills, "fetched_at": time.time()}
        _save_cache(cache)
        return skills
    except Exception:
        return entry.get("data", [])


def _search_glama(term: str, limit: int = 10) -> list:
    """Search glama.ai for MCP servers matching term. Returns list of {"id", "description"}."""
    try:
        results = []
        cursor = None
        while len(results) < limit:
            params = {"first": min(20, limit - len(results)), "query": term}
            if cursor:
                params["after"] = cursor
            resp = requests.get(GLAMA_API, params=params, timeout=6)
            if resp.status_code != 200:
                break
            data = resp.json()
            servers = data.get("servers", [])
            if not servers:
                break
            for s in servers:
                slug = s.get("slug") or s.get("id") or s.get("name", "")
                if slug:
                    results.append({
                        "id": slug,
                        "description": (s.get("description") or "")[:200],
                    })
            page_info = data.get("pageInfo", {})
            if not page_info.get("hasNextPage"):
                break
            cursor = page_info.get("endCursor")
        return results[:limit]
    except Exception:
        return []


def _search_official_plugins(category_id: str) -> list:
    """Fetch official CC plugins from GitHub, filter by category_id. Cached 1hr.

    Returns list of {"id", "description"} for plugins matching the given category.
    """
    cache = _load_cache()
    plugins_entry = cache.get(OFFICIAL_PLUGINS_CACHE_KEY, {})
    if plugins_entry and (time.time() - plugins_entry.get("fetched_at", 0)) < CACHE_TTL:
        plugins = plugins_entry.get("data", [])
    else:
        try:
            resp = requests.get(OFFICIAL_PLUGINS_URL, timeout=8)
            if resp.status_code == 200:
                raw = resp.json()
                plugins = raw if isinstance(raw, list) else raw.get("plugins", [])
                cache[OFFICIAL_PLUGINS_CACHE_KEY] = {"data": plugins, "fetched_at": time.time()}
                _save_cache(cache)
            else:
                plugins = plugins_entry.get("data", [])
        except Exception:
            plugins = plugins_entry.get("data", [])

    results = []
    for p in plugins:
        p_cat = PLUGIN_CAT_MAP.get((p.get("category") or "").lower(), "")
        if p_cat == category_id:
            name = p.get("name") or p.get("id") or ""
            if name:
                # Prefix with "plugin:anthropic:" so display code and RANK_SYSTEM_PROMPT
                # can correctly identify and handle this tool type
                plugin_id = f"plugin:anthropic:{name}"
                results.append({
                    "id": plugin_id,
                    "description": (p.get("description") or "")[:200],
                })
    return results


def search_registry(task_type: str, limit: int = 5) -> list:
    """Search skills.sh for all terms in compound task type. Returns list of {"id", "description"}.

    For "docker-aws-github-actions", searches "docker", "aws", "github" separately (up to 3 unique terms).
    Results are deduplicated; first match wins.
    """
    terms = task_type.split("-")
    seen_terms = []
    for t in terms:
        if t not in seen_terms:
            seen_terms.append(t)
    seen_terms = seen_terms[:3]

    seen_ids = set()
    results = []
    for term in seen_terms:
        for skill in _search_one_term(term, limit):
            if skill["id"] not in seen_ids:
                seen_ids.add(skill["id"])
                results.append(skill)
        if len(results) >= limit:
            break
    return results[:limit]


def search_by_category(category_id: str, limit: int = 10) -> list:
    """Search skills.sh + glama.ai + official plugins for a known category.

    Uses the full category term list for skills.sh and glama, plus official plugin
    category mapping for the plugin marketplace. Results are merged and deduplicated.
    Returns combined list of {"id", "description"}.
    """
    if _load_categories is None:
        return []
    try:
        categories = _load_categories()
    except Exception:
        return []

    cat = next((c for c in categories if c.get("id") == category_id), None)
    if not cat:
        return []

    seen_ids: set = set()
    results = []

    # 1. skills.sh — primary term search
    try:
        for term in cat.get("search_terms", [])[:5]:
            for skill in _search_one_term(term, limit=5):
                if skill["id"] not in seen_ids:
                    seen_ids.add(skill["id"])
                    results.append(skill)
            if len(results) >= limit:
                break
    except Exception:
        pass

    # 2. Official CC plugins — pre-mapped by category
    try:
        for plugin in _search_official_plugins(category_id):
            if plugin["id"] not in seen_ids:
                seen_ids.add(plugin["id"])
                results.append(plugin)
    except Exception:
        pass

    # 3. glama.ai MCPs — use mcp_search_terms (service names) if present,
    #    otherwise fall back to first general search term
    if len(results) < limit:
        try:
            mcp_terms = cat.get("mcp_search_terms") or []
            glama_term = mcp_terms[0] if mcp_terms else cat.get("search_terms", [""])[0]
            if glama_term:
                for mcp in _search_glama(glama_term, limit=5):
                    # Prefix with "mcp:" so type detection and display work correctly
                    mcp_id = mcp["id"] if mcp["id"].startswith("mcp:") else f"mcp:{mcp['id']}"
                    if mcp_id not in seen_ids:
                        seen_ids.add(mcp_id)
                        results.append({"id": mcp_id, "description": mcp.get("description", "")})
        except Exception:
            pass

    return results[:limit]


def rank_recommendations(
    task_type: str,
    registry_results: list,
    context_snippet: str = None,
    cc_tool: str = None,
    cc_tool_description: str = None,
    model: str = "claude-haiku-4-5-20251001"
) -> dict:
    """Score CC's chosen tool + marketplace alternatives collectively.

    Returns {"cc_score": int, "all": [{name, score, installed, reason, install_cmd?}]}
    """
    try:
        config = load_config()
        llm = get_client(config)
        # model param kept as override — if provided, takes priority over config
        effective_model = model if model else ranker_model(config)

        context_line = f"\nUser's current task: \"{context_snippet[:200]}\"" if context_snippet else ""

        cc_tool_line = ""
        if cc_tool:
            desc = f" — {cc_tool_description[:150]}" if cc_tool_description else ""
            cc_tool_line = f"\nCC's chosen tool: {cc_tool}{desc}"

        registry_formatted = []
        for r in registry_results:
            if isinstance(r, dict):
                registry_formatted.append({"id": r["id"], "desc": r.get("description", "")[:200]})
            else:
                registry_formatted.append({"id": r, "desc": ""})

        user_content = f"""Task type: {task_type}{context_line}{cc_tool_line}

Marketplace alternatives (not installed):
{json.dumps(registry_formatted, indent=2)}

Score CC's tool and each marketplace alternative for this {task_type} task."""

        text = llm.complete(system=RANK_SYSTEM_PROMPT, user=user_content, model=effective_model, max_tokens=600)
        if not text:
            return {"cc_score": 0, "all": []}
        parsed = json.loads(text)
        parsed.setdefault("cc_score", 0)
        parsed.setdefault("all", [])
        return parsed

    except Exception:
        return {"cc_score": 0, "all": []}


def build_recommendation_list(
    task_type: str,
    context_snippet: str = None,
    cc_tool: str = None,
    model: str = None,
    category_id: str = None,
    stack_profile: dict = None,
    cc_tool_type: str = "skill"
) -> dict:
    """Search marketplace registry and rank against CC's chosen tool.

    Returns:
        {
            "all":      [{name, score, installed=False, reason, install_cmd, install_url}],
            "top_pick": {first item} or None,
            "cc_score": int (0-100 score for CC's chosen tool),
        }
    """
    # Use category-based search when available — more targeted than keyword splitting
    if category_id and category_id != "unknown":
        registry_results = search_by_category(category_id)
    else:
        registry_results = search_registry(task_type)

    # Type-aware ordering: when CC is using an MCP, float same-type results to top
    # so the ranker sees the most relevant alternatives first
    if cc_tool_type == "mcp":
        mcp_results = [r for r in registry_results if r.get("id", "").startswith("mcp:") or "mcp" in r.get("id", "").lower()]
        other_results = [r for r in registry_results if r not in mcp_results]
        registry_results = mcp_results + other_results
    elif cc_tool_type == "agent":
        # Agent calls → general skills and agent-type tools are most relevant; keep ordering as-is
        pass

    # Filter out MCPs the user already has installed (stack_scanner detected them)
    installed_mcps = set()
    if stack_profile:
        for srv in stack_profile.get("mcp_servers", []):
            installed_mcps.add(srv.lower())
    if installed_mcps:
        from interceptor import normalize_tool_name_for_matching
        registry_results = [
            r for r in registry_results
            if normalize_tool_name_for_matching(r.get("id", "")) not in installed_mcps
        ]

    cc_desc = describe_cc_tool(cc_tool) if cc_tool else ""

    # Build stack context hint for ranker prompt
    stack_context = None
    if stack_profile:
        terms = stack_profile.get("languages", []) + stack_profile.get("frameworks", [])
        if terms:
            stack_context = "Developer's current stack: " + ", ".join(terms[:6])

    # Include cc_tool_type in context so ranker understands what CC was using
    type_hint = f"\nCC tool type: {cc_tool_type}" if cc_tool_type and cc_tool_type != "skill" else ""
    effective_context = (context_snippet or "")
    if stack_context:
        effective_context = f"{effective_context}\n{stack_context}".strip()
    if type_hint:
        effective_context = f"{effective_context}{type_hint}".strip()

    result = rank_recommendations(
        task_type=task_type,
        registry_results=registry_results,
        context_snippet=effective_context or None,
        cc_tool=cc_tool,
        cc_tool_description=cc_desc,
        model=model or "claude-haiku-4-5-20251001"
    )

    all_tools = result.get("all", [])
    cc_score = result.get("cc_score", 0)

    # Filter out any installed MCPs the ranker may have included despite pre-filter
    if installed_mcps:
        from interceptor import normalize_tool_name_for_matching
        all_tools = [
            t for t in all_tools
            if normalize_tool_name_for_matching(t.get("name", "")) not in installed_mcps
        ]

    # Score gap truncation: cut at first gap >= 25 points
    if len(all_tools) > 1:
        cutoff = len(all_tools)
        for i in range(1, len(all_tools)):
            gap = all_tools[i-1].get("score", 0) - all_tools[i].get("score", 0)
            if gap >= 25:
                cutoff = i
                break
        all_tools = all_tools[:cutoff]

    # Derive GitHub install_url from skill ID format: "owner/repo@skill-name"
    for item in all_tools:
        name = item.get("name", "")
        if "@" in name and "/" in name and "install_url" not in item:
            repo_part = name.split("@")[0]
            item["install_url"] = f"https://github.com/{repo_part}"

    # Two-tier split: described tools are best matches, undescribed are general keyword matches
    described = [t for t in all_tools if t.get("description", "").strip()]
    general = [t for t in all_tools if not t.get("description", "").strip()]

    top_pick = described[0] if described else (general[0] if general else None)

    return {
        "all": all_tools,
        "described": described,
        "general": general,
        "top_pick": top_pick,
        "cc_score": cc_score,
    }
