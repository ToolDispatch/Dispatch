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
recommend the most relevant ones.

Respond with ONLY valid JSON:
{
  "installed": [{"name": "...", "reason": "one sentence why"}],
  "suggested": [{"name": "...", "install_cmd": "...", "reason": "one sentence why"}]
}

Limit to top 4 installed and top 3 suggested. Only include genuinely relevant ones.
If nothing is relevant, return empty lists.
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
    if entry and (time.time() - entry.get("fetched_at", 0)) < CACHE_TTL:
        return entry["data"]
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
            # Keep only lines that look like skill identifiers (hyphenated, no spaces)
            if stripped and not stripped.startswith("No ") and " " not in stripped and "-" in stripped:
                cleaned.append(stripped)
        cache["installed_skills"] = {"data": cleaned, "fetched_at": time.time()}
        _save_cache(cache)
        return cleaned
    except Exception:
        return entry.get("data", [])


def strip_ansi(text: str) -> str:
    """Strip ANSI escape codes from text."""
    return re.sub(r'\x1b\[[0-9;]*[A-Za-z]', '', text)


def search_registry(task_type: str, limit: int = 5) -> list:
    """Search skills.sh registry for task-type matches. Cached per primary term for 1 hour."""
    primary = task_type.split("-")[0]
    cache = _load_cache()
    registry = cache.get("registry", {})
    entry = registry.get(primary, {})
    if entry and (time.time() - entry.get("fetched_at", 0)) < CACHE_TTL:
        return entry["data"]
    try:
        result = subprocess.run(
            ["npx", "--yes", "skills", "find", primary],
            capture_output=True, text=True, timeout=6, check=False
        )
        lines = result.stdout.split("\n")
        skills = []
        for line in lines:
            stripped = strip_ansi(line).strip()
            # Skill identifiers look like "owner/repo@skill-name"
            if "@" in stripped and "/" in stripped and not stripped.startswith("http") and not stripped.startswith("└"):
                parts = stripped.split()
                if parts:
                    skill_id = parts[0]
                    if "/" in skill_id and "@" in skill_id:
                        skills.append(skill_id)
        skills = skills[:limit]
        if "registry" not in cache:
            cache["registry"] = {}
        cache["registry"][primary] = {"data": skills, "fetched_at": time.time()}
        _save_cache(cache)
        return skills
    except Exception:
        return entry.get("data", [])


def rank_recommendations(
    task_type: str,
    installed_plugins: list,
    installed_skills: list,
    registry_results: list
) -> dict:
    """Use Haiku to rank and filter recommendations by relevance."""
    try:
        api_key = os.environ.get("ANTHROPIC_API_KEY")
        if not api_key:
            return {"installed": [], "suggested": []}
        client = anthropic.Anthropic(api_key=api_key)

        user_content = f"""Task type: {task_type}

Installed plugins ({len(installed_plugins)}):
{json.dumps([{"name": p["name"], "desc": p["description"][:100]} for p in installed_plugins], indent=2)}

Installed skills:
{json.dumps(installed_skills, indent=2)}

Available from registry (not installed):
{json.dumps(registry_results, indent=2)}

Which are most relevant for a {task_type} task?"""

        response = client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=500,
            system=RANK_SYSTEM_PROMPT,
            messages=[{"role": "user", "content": user_content}]
        )

        if not response.content:
            return {"installed": [], "suggested": []}
        text = response.content[0].text.strip()
        if text.startswith("```"):
            text = text.split("```")[1]
            if text.startswith("json"):
                text = text[4:]
        return json.loads(text.strip())

    except Exception:
        return {"installed": [], "suggested": []}


def build_recommendation_list(task_type: str, installed_plugins: list = None, installed_skills: list = None) -> dict:
    """Full evaluation pipeline: scan installed -> search registry -> rank."""
    if installed_plugins is None:
        installed_plugins = scan_installed_plugins(PLUGINS_DIR)
    if installed_skills is None:
        installed_skills = get_installed_skills()
    registry_results = search_registry(task_type)
    result = rank_recommendations(
        task_type=task_type,
        installed_plugins=installed_plugins,
        installed_skills=installed_skills,
        registry_results=registry_results
    )
    # Enrich ranked installed items with marketplace info from the original scan
    plugin_map = {p["name"]: p for p in installed_plugins}
    for item in result.get("installed", []):
        mp = plugin_map.get(item["name"], {}).get("marketplace", "")
        if mp:
            item["marketplace"] = mp
    return result
