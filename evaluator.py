import json
import os
import re
import subprocess
import glob
import time
import anthropic

PLUGINS_DIR = os.path.expanduser("~/.claude/plugins/marketplaces")
CACHE_FILE = os.path.expanduser("~/.claude/skill-router/npx_cache.json")
CACHE_TTL = 3600  # 1 hour


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
Given a detected task type and lists of available plugins/skills,
rank ALL relevant tools collectively by usefulness for the specific task.

Respond with ONLY valid JSON:
{
  "all": [
    {"name": "...", "score": 90, "installed": true, "reason": "one specific sentence grounded in the current task"},
    {"name": "...", "score": 75, "installed": false, "install_cmd": "npx skills add owner/repo@skill-name -y", "reason": "one specific sentence grounded in the current task"}
  ]
}

Rules:
- score 0-100 based on relevance to the specific task (not general quality)
- Only include tools with score >= 40
- Limit to top 6 total across installed and uninstalled
- Sort by score descending (highest first)
- For installed tools: "installed": true, no install_cmd
- For uninstalled registry tools: use the "id" field as the tool name in your response; "installed": false; include install_cmd using the exact id
- Write specific reasons grounded in what the developer is actually doing
- If nothing is relevant, return {"all": []}

Reason quality examples:
GOOD: "Provides Flutter widget testing patterns directly applicable to the crash you are diagnosing in the rendering pipeline."
BAD: "Useful for Flutter development." (too generic, not grounded in the current task)
GOOD: "Adds Firestore query helpers relevant to the user authentication flow you are building."
BAD: "Firebase support for agents." (repeats the tool name, adds nothing)
Write reasons like the GOOD examples — one sentence, specific to what the developer just said they are doing.
"""


def scan_installed_plugins(plugins_dir: str) -> list:
    """Scan all marketplace plugin.json files and return plugin metadata."""
    plugins = []
    if not os.path.isdir(plugins_dir):
        return []
    pattern = os.path.join(plugins_dir, "*", "plugins", "*", ".claude-plugin", "plugin.json")
    for path in glob.glob(pattern):
        try:
            with open(path, encoding='utf-8') as f:
                data = json.load(f)
                name = data.get("name", "")
                description = data.get("description", "")
                if name:
                    # Extract marketplace name from path: .../marketplaces/{marketplace}/plugins/...
                    parts = path.replace("\\", "/").split("/")
                    try:
                        mp_idx = parts.index("marketplaces")
                        marketplace = parts[mp_idx + 1]
                    except (ValueError, IndexError):
                        marketplace = ""
                    plugins.append({
                        "name": name,
                        "description": description[:200],
                        "marketplace": marketplace,
                        "source": "installed"
                    })
        except Exception:
            continue
    return plugins


def get_installed_skills() -> list:
    """Get list of installed agent skills via npx skills list. Cached for 1 hour."""
    cache = _load_cache()
    entry = cache.get("installed_skills", {})
    cached_data = entry.get("data", [])
    if entry and (time.time() - entry.get("fetched_at", 0)) < CACHE_TTL:
        # Guard: if cached data is legacy bare strings, treat as expired
        if not cached_data or isinstance(cached_data[0], dict):
            return cached_data
    try:
        result = subprocess.run(
            ["npx", "--yes", "skills", "list", "-g"],
            capture_output=True, text=True, timeout=6, check=False
        )
        if result.returncode != 0:
            return entry.get("data", [])
        lines = result.stdout.strip().split("\n")
        cleaned = []
        for line in lines:
            stripped = strip_ansi(line).strip()
            if not stripped or stripped.startswith("No "):
                continue
            parts = stripped.split()
            if not parts:
                continue
            skill_id = parts[0]
            # Skill IDs contain hyphens and no spaces; exclude registry-style "owner/repo@skill"
            if "-" in skill_id and "/" not in skill_id:
                description = " ".join(parts[1:]) if len(parts) > 1 else ""
                cleaned.append({"id": skill_id, "description": description})
        cache["installed_skills"] = {"data": cleaned, "fetched_at": time.time()}
        _save_cache(cache)
        return cleaned
    except Exception:
        return entry.get("data", [])


def strip_ansi(text: str) -> str:
    """Strip ANSI escape codes from text."""
    return re.sub(r'\x1b\[[0-9;]*[A-Za-z]', '', text)


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
        result = subprocess.run(
            ["npx", "--yes", "skills", "find", term],
            capture_output=True, text=True, timeout=6, check=False
        )
        lines = result.stdout.split("\n")
        skills = []
        for line in lines:
            stripped = strip_ansi(line).strip()
            if "@" not in stripped or "/" not in stripped:
                continue
            if stripped.startswith("http") or stripped.startswith("└"):
                continue
            parts = stripped.split()
            if not parts:
                continue
            skill_id = parts[0]
            if "/" in skill_id and "@" in skill_id:
                description = " ".join(parts[1:]) if len(parts) > 1 else ""
                skills.append({"id": skill_id, "description": description})
        skills = skills[:limit]
        if "registry" not in cache:
            cache["registry"] = {}
        cache["registry"][term] = {"data": skills, "fetched_at": time.time()}
        _save_cache(cache)
        return skills
    except Exception:
        return entry.get("data", [])


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


def rank_recommendations(
    task_type: str,
    installed_plugins: list,
    installed_skills: list,
    registry_results: list,
    context_snippet: str = None
) -> dict:
    """Use Haiku to rank all tools collectively by relevance. Returns {all: [...]}."""
    try:
        api_key = os.environ.get("ANTHROPIC_API_KEY")
        if not api_key:
            return {"all": []}
        client = anthropic.Anthropic(api_key=api_key)

        context_line = f"\nUser's current message: \"{context_snippet[:200]}\"" if context_snippet else ""

        # Format registry results: handle both {id, description} dicts and legacy bare strings
        registry_formatted = []
        for r in registry_results:
            if isinstance(r, dict):
                registry_formatted.append({"id": r["id"], "desc": r.get("description", "")[:200]})
            else:
                registry_formatted.append({"id": r, "desc": ""})

        skills_formatted = []
        for s in installed_skills:
            if isinstance(s, dict):
                skills_formatted.append({"id": s.get("id", ""), "desc": s.get("description", "")[:200]})
            else:
                skills_formatted.append({"id": s, "desc": ""})

        user_content = f"""Developer is working on: {task_type}{context_line}

Installed plugins ({len(installed_plugins)}):
{json.dumps([{"name": p["name"], "desc": p["description"][:250]} for p in installed_plugins], indent=2)}

Installed skills:
{json.dumps(skills_formatted, indent=2)}

Available from registry (not installed):
{json.dumps(registry_formatted, indent=2)}

Rank ALL relevant tools collectively for a {task_type} task."""

        response = client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=600,
            system=RANK_SYSTEM_PROMPT,
            messages=[{"role": "user", "content": user_content}]
        )

        if not response.content:
            return {"all": []}
        text = response.content[0].text.strip()
        if text.startswith("```"):
            text = text.split("```")[1]
            if text.startswith("json"):
                text = text[4:]
        parsed = json.loads(text.strip())
        # Normalize: if Haiku returns old format, convert it
        if "all" not in parsed and ("installed" in parsed or "suggested" in parsed):
            combined = []
            for item in parsed.get("installed", []):
                item.setdefault("installed", True)
                item.setdefault("score", 70)
                combined.append(item)
            for item in parsed.get("suggested", []):
                item.setdefault("installed", False)
                item.setdefault("score", 60)
                combined.append(item)
            parsed = {"all": combined}
        return parsed

    except Exception:
        return {"all": []}


def build_recommendation_list(task_type: str, installed_plugins: list = None, installed_skills: list = None, context_snippet: str = None) -> dict:
    """Full evaluation pipeline: scan installed -> search registry -> rank collectively.

    Returns:
        {
            "all": [{name, score, installed, reason, install_cmd?, install_url?, marketplace?}],
            "top_pick": {name, score, installed, reason, ...} or None,
            "installed": [...],   # backward-compat: items from all where installed=True
            "suggested": [...],   # backward-compat: items from all where installed=False
        }
    """
    if installed_plugins is None:
        installed_plugins = scan_installed_plugins(PLUGINS_DIR)
    if installed_skills is None:
        installed_skills = get_installed_skills()
    registry_results = search_registry(task_type)
    result = rank_recommendations(
        task_type=task_type,
        installed_plugins=installed_plugins,
        installed_skills=installed_skills,
        registry_results=registry_results,
        context_snippet=context_snippet
    )

    all_tools = result.get("all", [])

    # Score gap truncation: cut list at first gap >= 25 points
    if len(all_tools) > 1:
        cutoff = len(all_tools)
        for i in range(1, len(all_tools)):
            gap = all_tools[i-1].get("score", 0) - all_tools[i].get("score", 0)
            if gap >= 25:
                cutoff = i
                break
        all_tools = all_tools[:cutoff]

    plugin_map = {p["name"]: p for p in installed_plugins}

    for item in all_tools:
        name = item.get("name", "")
        if item.get("installed", False):
            # Add marketplace from local plugin scan
            mp = plugin_map.get(name, {}).get("marketplace", "")
            if mp:
                item["marketplace"] = mp
        else:
            # Derive GitHub URL from skill ID: "owner/repo@skill-name" -> "https://github.com/owner/repo"
            if "@" in name and "/" in name and "install_url" not in item:
                repo_part = name.split("@")[0]
                item["install_url"] = f"https://github.com/{repo_part}"

    top_pick = all_tools[0] if all_tools else None
    installed_list = [t for t in all_tools if t.get("installed", False)]
    suggested_list = [t for t in all_tools if not t.get("installed", False)]

    return {
        "all": all_tools,
        "top_pick": top_pick,
        "installed": installed_list,
        "suggested": suggested_list,
    }
