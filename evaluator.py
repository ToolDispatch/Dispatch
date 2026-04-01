import json
import os
import re
import requests
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from llm_client import get_client, ranker_model, load_config, FREE_RANKER_MODEL

try:
    from category_mapper import load_categories as _load_categories
except ImportError:
    _load_categories = None

CACHE_FILE = os.path.expanduser("~/.claude/dispatch/npx_cache.json")
CACHE_TTL = 3600        # 1 hour for registry results
DESC_CACHE_TTL = 86400  # 24 hours for descriptions

GLAMA_API = "https://glama.ai/api/mcp/v1/servers"
CLAUDE_PLUGINS_API = "https://claude-plugins.dev/api/skills"
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

# Terms that flag an MCP as belonging to a non-developer vertical.
# Glama search results sometimes surface these due to keyword overlap (e.g.,
# "playwright" matched financial tool descriptions). Filter them before surfacing.
_NON_DEV_DOMAIN_TERMS = [
    "brokerage", "fidelity investment", "schwab", "e-trade", "etrade",
    "trading account", "stock portfolio", "401k", "ira account",
    "electronic health record", "ehr ", "emr ", "patient record",
    "clinical trial", "hipaa", "insurance claim",
    "legal document", "case management", "law firm",
    "payroll processing", "accounts payable", "accounts receivable",
]


def _is_domain_irrelevant(mcp_id: str, description: str) -> bool:
    """Return True if the MCP clearly belongs to a non-dev vertical (finance, healthcare, legal, etc.).

    Prevents glama keyword matches from surfacing e.g. a Fidelity brokerage MCP when
    searching for 'playwright' (testing). Case-insensitive substring match.
    """
    text = f"{mcp_id} {description}".lower()
    return any(term in text for term in _NON_DEV_DOMAIN_TERMS)




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


def _fetch_skill_description(skill_id: str) -> str:
    """Fetch a SKILL.md description for a single skill from GitHub.

    Tries common path patterns in order:
      1. skills/{name}/SKILL.md   — most common (obra/superpowers, flutter/skills, etc.)
      2. {name}/SKILL.md          — flat repo layout
      3. README.md (first 400 chars) — last resort, gives repo-level context

    Returns description string (may be empty on failure). Never raises.
    """
    try:
        if "@" not in skill_id or "/" not in skill_id:
            return ""
        repo_part, skill_name = skill_id.split("@", 1)
        base = f"https://raw.githubusercontent.com/{repo_part}/main"
        paths = [
            f"skills/{skill_name}/SKILL.md",
            f"{skill_name}/SKILL.md",
            "README.md",
        ]
        for path in paths:
            try:
                resp = requests.get(f"{base}/{path}", timeout=2)
                if resp.status_code != 200:
                    continue
                text = resp.text[:800]
                # Extract frontmatter description field first
                for line in text.splitlines():
                    if line.startswith("description:"):
                        return line.replace("description:", "").strip().strip('"\'')
                # Fall back: first non-empty non-heading paragraph
                for line in text.splitlines():
                    line = line.strip()
                    if line and not line.startswith("#") and not line.startswith("---") and len(line) > 20:
                        return line[:200]
            except Exception:
                continue
    except Exception:
        pass
    return ""


def enrich_descriptions(skills: list) -> list:
    """Fetch GitHub descriptions for skills missing them. Parallel, cached 24h.

    Mutates each skill dict in place, adding/updating 'description'.
    Skips skills that already have a description or are in the 24h cache.
    Uses a thread pool capped at 5 workers to stay within hook budget (~1.5s).
    """
    cache = _load_cache()
    desc_cache = cache.get("_descriptions", {})
    now = time.time()

    to_fetch = []
    for skill in skills:
        sid = skill.get("id", "")
        if skill.get("description", "").strip():
            continue  # already have one
        entry = desc_cache.get(sid, {})
        if entry and (now - entry.get("fetched_at", 0)) < DESC_CACHE_TTL:
            skill["description"] = entry.get("description", "")
        else:
            to_fetch.append(skill)

    if not to_fetch:
        return skills

    def fetch_one(s):
        return s, _fetch_skill_description(s["id"])

    with ThreadPoolExecutor(max_workers=5) as pool:
        futures = {pool.submit(fetch_one, s): s for s in to_fetch}
        for future in as_completed(futures, timeout=3):
            try:
                skill, desc = future.result()
                skill["description"] = desc
                desc_cache[skill["id"]] = {"description": desc, "fetched_at": now}
            except Exception:
                pass

    cache["_descriptions"] = desc_cache
    _save_cache(cache)
    return skills

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


RECOMMEND_SYSTEM_PROMPT = """You are a tool recommendation engine for Claude Code.
Given a detected task type and context, rank available marketplace tools by relevance.

Respond with ONLY valid JSON:
{
  "all": [
    {"name": "owner/repo@skill-name", "score": 88,
     "install_cmd": "npx skills add owner/repo@skill-name -y",
     "reason": "one specific sentence grounded in the current task"}
  ]
}

Rules:
- all: marketplace tools sorted by relevance score (0-100) descending
- Only include tools with score >= 55 (caller applies final floor)
- Limit to top 9 tools total, BUT ensure type diversity: include up to 3 plugins (id starts with "plugin:"), up to 3 MCPs (id starts with "mcp:"), up to 3 skills. If fewer than 3 exist of a type, include all relevant ones above the score floor.
- IMPORTANT: plugins and MCPs are hosted integrations — score them 10 points higher than equivalent skills when directly relevant, because they require no installation and work instantly.
- install_cmd: use provided hint exactly — do NOT fabricate
  - skills (format "owner/repo@name"): install_cmd = "npx skills add owner/repo@name -y"
  - MCPs (id starts with "mcp:"): omit install_cmd entirely
  - plugins (id starts with "plugin:"): omit install_cmd (plugins are activated in Claude Code settings, not via CLI)
- Write specific reasons grounded in what the developer is actually doing
- If no tools are relevant, return {"all": []}

Reason quality:
GOOD: "Adds widget testing patterns directly applicable to the rendering crash you are diagnosing."
BAD: "Useful for Flutter." (too generic)
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
    """Search claude-plugins.dev for one term. Returns list of {"id", "description"}. Cached 1hr.

    claude-plugins.dev returns descriptions, star counts, and install counts — unlike skills.sh
    which returns names only. Descriptions are essential for ranker quality.
    Falls back to skills.sh if claude-plugins.dev is unavailable.
    """
    cache = _load_cache()
    registry = cache.get("registry", {})
    entry = registry.get(term, {})
    cached_data = entry.get("data", [])
    if (entry
            and (time.time() - entry.get("fetched_at", 0)) < CACHE_TTL
            and (not cached_data or isinstance(cached_data[0], dict))):
        return cached_data

    skills = []
    try:
        resp = requests.get(
            CLAUDE_PLUGINS_API,
            params={"q": term, "limit": limit * 2},  # fetch more, we'll trim after dedup
            timeout=8,
        )
        if resp.status_code == 200:
            for s in resp.json().get("skills", []):
                ns = s.get("namespace", "")  # "@owner/repo/skill-name"
                name = s.get("name", "")
                desc = (s.get("description") or "")[:300]
                stars = s.get("stars", 0)
                installs = s.get("installs", 0)
                # Derive skill_id in "owner/repo@skill-name" format from namespace
                if ns and name:
                    parts = ns.lstrip("@").split("/")
                    if len(parts) >= 2:
                        skill_id = f"{parts[0]}/{parts[1]}@{name}"
                        skills.append({
                            "id": skill_id,
                            "description": desc,
                            "stars": stars,
                            "installs": installs,
                        })
    except Exception:
        pass

    # Fallback to skills.sh if claude-plugins.dev returned nothing
    if not skills:
        try:
            resp = requests.get(
                "https://skills.sh/api/search",
                params={"q": term, "limit": limit},
                timeout=8,
            )
            if resp.status_code == 200:
                for skill in resp.json().get("skills", []):
                    source = skill.get("source", "")
                    name = skill.get("name", "")
                    if source and name:
                        skills.append({"id": f"{source}@{name}", "description": ""})
        except Exception:
            pass

    skills = skills[:limit]
    if "registry" not in cache:
        cache["registry"] = {}
    cache["registry"][term] = {"data": skills, "fetched_at": time.time()}
    _save_cache(cache)
    return skills


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
                        "install_url": f"https://glama.ai/mcp/servers/{slug}",
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
                    "install_url": p.get("homepage") or "",
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
    results = results[:limit]
    skills_only = [r for r in results if "@" in r.get("id", "") and not r.get("description", "").strip()]
    if skills_only:
        enrich_descriptions(skills_only)
    return results


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

    # 2. Official CC plugins — pre-mapped by category (always included, not counted against skill limit)
    plugins_to_add = []
    try:
        for plugin in _search_official_plugins(category_id):
            if plugin["id"] not in seen_ids:
                seen_ids.add(plugin["id"])
                plugins_to_add.append(plugin)
    except Exception:
        pass

    # 3. glama.ai MCPs — always search (not gated on skill count), appended after limit like plugins
    mcps_to_add = []
    try:
        mcp_terms = cat.get("mcp_search_terms") or []
        glama_term = mcp_terms[0] if mcp_terms else cat.get("search_terms", [""])[0]
        if glama_term:
            for mcp in _search_glama(glama_term, limit=5):
                # Prefix with "mcp:" so type detection and display work correctly
                mcp_id = mcp["id"] if mcp["id"].startswith("mcp:") else f"mcp:{mcp['id']}"
                if mcp_id not in seen_ids and not _is_domain_irrelevant(mcp_id, mcp.get("description", "")):
                    seen_ids.add(mcp_id)
                    mcps_to_add.append({"id": mcp_id, "description": mcp.get("description", "")})
    except Exception:
        pass

    results = results[:limit] + plugins_to_add + mcps_to_add
    # Enrich any skills missing descriptions — parallel GitHub fetch, cached 24h
    skills_only = [r for r in results if "@" in r.get("id", "") and not r.get("description", "").strip()]
    if skills_only:
        enrich_descriptions(skills_only)
    return results


def rank_recommendations(
    task_type: str,
    registry_results: list,
    context_snippet: str = None,
    cc_tool: str = None,
    cc_tool_description: str = None,
    model: str = FREE_RANKER_MODEL
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
                # Trim descriptions to 120 chars — keeps tokens low, latency under 3s
                registry_formatted.append({"id": r["id"], "desc": r.get("description", "")[:120]})
            else:
                registry_formatted.append({"id": r, "desc": ""})

        user_content = f"""Task type: {task_type}{context_line}{cc_tool_line}

Marketplace alternatives (not installed):
{json.dumps(registry_formatted, indent=2)}

Score CC's tool and each marketplace alternative for this {task_type} task."""

        # 5s hard timeout — hook has 10s total, search+enrich takes ~1s, LLM must stay under 5s
        # Use shutdown(wait=False) so timeout actually cuts off — the with-block would wait
        _pool = ThreadPoolExecutor(max_workers=1)
        future = _pool.submit(
            llm.complete,
            system=RANK_SYSTEM_PROMPT,
            user=user_content,
            model=effective_model,
            max_tokens=400,
        )
        try:
            text = future.result(timeout=5)
        except Exception:
            _pool.shutdown(wait=False)
            return _signal_rank_fallback(registry_results)
        _pool.shutdown(wait=False)

        if not text:
            return _signal_rank_fallback(registry_results)
        parsed = json.loads(text)
        parsed.setdefault("cc_score", 0)
        parsed.setdefault("all", [])
        return parsed

    except Exception:
        return _signal_rank_fallback(registry_results)


def _signal_rank_fallback(registry_results: list) -> dict:
    """Pure signal-based ranking when LLM is unavailable or too slow.

    Scores each tool 0-100 using: description presence (40pts), install count
    log-scaled (40pts), star count log-scaled (20pts). No LLM call.
    Sets cc_score=50 as neutral baseline so tools with descriptions can beat it.
    """
    import math

    def log_score(n: int, max_val: int) -> int:
        if n <= 0:
            return 0
        return min(100, int(math.log1p(n) / math.log1p(max_val) * 100))

    scored = []
    for r in registry_results:
        if not isinstance(r, dict):
            continue
        desc = r.get("description", "").strip()
        installs = r.get("installs", 0)
        stars = r.get("stars", 0)
        desc_score = 40 if desc else 0
        install_score = log_score(installs, 50000) * 0.4
        star_score = log_score(stars, 10000) * 0.2
        total = int(desc_score + install_score + star_score)
        if total >= 40:
            scored.append({
                "name": r["id"],
                "score": min(100, total),
                "reason": desc[:100] if desc else "No description available.",
                "install_cmd": f"npx skills add {r['id']} -y" if "@" in r.get("id", "") else None,
            })

    scored.sort(key=lambda x: x["score"], reverse=True)
    return {"cc_score": 50, "all": scored[:5]}


def build_recommendation_list(
    task_type: str,
    context_snippet: str = None,
    cc_tool: str = None,
    model: str = None,
    category_id: str = None,
    stack_profile: dict = None,
    cc_tool_type: str = "skill",
    cwd_basename: str = None,
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
    if cwd_basename:
        effective_context = f"Project: {cwd_basename}\n{effective_context}".strip()
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
        model=model or FREE_RANKER_MODEL
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

    # Enrich each tool with grouped-format fields (BYOK: no catalog signal/velocity)
    def _tool_type(name: str) -> str:
        if name.startswith("mcp:"):
            return "mcp"
        if name.startswith("plugin:"):
            return "plugin"
        return "skill"

    enriched = []
    for t in all_tools:
        name    = t.get("name", "")
        score   = t.get("score", 0)
        desc    = (t.get("description") or t.get("reason") or "").strip()
        no_desc = not bool(desc)
        enriched.append({
            "name":           name,
            "tool_type":      _tool_type(name),
            "relevance":      score,   # LLM score is the relevance signal for BYOK
            "signal":         0,
            "velocity":       0,
            "weighted":       score,
            "installs":       t.get("installs", 0),
            "stars":          t.get("stars", 0),
            "forks":          t.get("forks", 0),
            "description":    desc[:150],
            "install_cmd":    (t.get("install_cmd") or "").strip(),
            "install_url":    (t.get("install_url") or "").strip(),
            "no_description": no_desc,
            "installed":      False,
        })

    def top3(ttype):
        group = [t for t in enriched if t["tool_type"] == ttype]
        return group[:3]

    skills  = top3("skill")
    mcps    = top3("mcp")
    plugins = top3("plugin")

    all_grouped = sorted(skills + mcps + plugins, key=lambda t: t["weighted"], reverse=True)
    max_weighted = all_grouped[0]["weighted"] if all_grouped else 0
    top_pick = all_grouped[0] if all_grouped else None

    caveat = "Review before installing. Dispatch surfaces tools based on community signals and task context — not a security audit."

    return {
        "skills":       skills,
        "mcps":         mcps,
        "plugins":      plugins,
        "all":          all_grouped,
        "top_pick":     top_pick,
        "cc_score":     cc_score,
        "max_weighted": max_weighted,
        "caveat":       caveat,
    }


def recommend_tools(
    task_type: str,
    context_snippet: str = None,
    category_id: str = None,
    stack_profile: dict = None,
    preferred_type: str = None,
    model: str = None,
    cwd_basename: str = None,
) -> dict:
    """Proactive recommendation — no cc_tool comparison.

    Searches all three tool types (skills, MCPs, plugins) for the given category,
    ranks by task relevance, applies diversity caps and score floor.

    Returns {"all": [...], "top_pick": {...} or None}
    """
    SCORE_FLOOR = 55
    MAX_PER_TYPE = 3
    MAX_TOTAL = 9

    try:
        # 1. Fetch candidates
        if category_id and category_id != "unknown":
            candidates = search_by_category(category_id, limit=25)
        else:
            candidates = search_registry(task_type, limit=10)

        # 2. Filter already-installed MCPs
        installed_mcps: set = set()
        if stack_profile:
            for srv in stack_profile.get("mcp_servers", []):
                installed_mcps.add(srv.lower())
        if installed_mcps:
            from interceptor import normalize_tool_name_for_matching
            candidates = [
                c for c in candidates
                if normalize_tool_name_for_matching(c.get("id", "")) not in installed_mcps
            ]

        # 3. Build stack context hint
        stack_hint = ""
        if stack_profile:
            terms = stack_profile.get("languages", []) + stack_profile.get("frameworks", [])
            if terms:
                stack_hint = "\nDeveloper stack: " + ", ".join(terms[:6])

        project_line = f"Project: {cwd_basename}\n" if cwd_basename else ""
        context_line = f"\n{project_line}Task context: \"{(context_snippet or '')[:200]}\""
        if stack_hint:
            context_line += stack_hint

        registry_formatted = [
            {"id": c["id"], "desc": c.get("description", "")[:200]}
            for c in candidates
        ]

        user_content = f"""Task type: {task_type}{context_line}

Available tools:
{json.dumps(registry_formatted, indent=2)}

Rank these tools for this {task_type} task."""

        config = load_config()
        llm = get_client(config)
        effective_model = model or ranker_model(config) or FREE_RANKER_MODEL

        text = llm.complete(
            system=RECOMMEND_SYSTEM_PROMPT,
            user=user_content,
            model=effective_model,
            max_tokens=1500,
        )
        if not text:
            return {"all": [], "by_type": {}, "top_pick": None}

        # Resilient parse: recover complete tool objects even if response is truncated
        try:
            parsed = json.loads(text)
        except json.JSONDecodeError:
            import re as _re
            tool_matches = _re.findall(r'\{[^{}]*"score"[^{}]*\}', text, _re.DOTALL)
            recovered = []
            for m in tool_matches:
                try:
                    recovered.append(json.loads(m))
                except json.JSONDecodeError:
                    pass
            parsed = {"all": recovered}
        all_tools = parsed.get("all", [])

        # 4. Apply score floor (safe cast: handle float scores)
        all_tools = [t for t in all_tools if int(float(t.get("score", 0))) >= SCORE_FLOOR]
        if not all_tools:
            return {"all": [], "by_type": {}, "top_pick": None}

        # Capture top_pick before preferred_type reordering
        # (top_pick should always be globally highest-scored, not preferred_type first)
        best_by_score = max(all_tools, key=lambda t: float(t.get("score", 0))) if all_tools else None

        # 5. Sort by preferred_type first, then score descending
        def _type_of(name: str) -> str:
            if name.startswith("plugin:"):
                return "plugin"
            if name.startswith("mcp:"):
                return "mcp"
            return "skill"

        if preferred_type:
            all_tools.sort(key=lambda t: (
                0 if _type_of(t.get("name", "")) == preferred_type else 1,
                -t.get("score", 0)
            ))
        else:
            all_tools.sort(key=lambda t: -t.get("score", 0))

        # 6. Diversity cap: max MAX_PER_TYPE per type, MAX_TOTAL total
        type_counts: dict = {}
        trimmed = []
        for t in all_tools:
            ttype = _type_of(t.get("name", ""))
            if type_counts.get(ttype, 0) < MAX_PER_TYPE:
                type_counts[ttype] = type_counts.get(ttype, 0) + 1
                trimmed.append(t)
            if len(trimmed) >= MAX_TOTAL:
                break
        all_tools = trimmed

        # 7. Derive install_url for skills
        for item in all_tools:
            name = item.get("name", "")
            if "@" in name and "/" in name and "install_url" not in item:
                item["install_url"] = f"https://github.com/{name.split('@')[0]}"

        # Group by tool type for sectioned display
        by_type: dict = {"plugin": [], "skill": [], "mcp": []}
        for t in all_tools:
            ttype = _type_of(t.get("name", ""))
            if ttype in by_type:
                by_type[ttype].append(t)

        top_pick = best_by_score
        return {"all": all_tools, "by_type": by_type, "top_pick": top_pick}

    except Exception:
        return {"all": [], "by_type": {}, "top_pick": None}
