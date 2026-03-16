"""Stack detection for Dispatch.

Scans a project directory for manifest files to identify languages, frameworks,
and tools. Builds stack_profile.json used by the ranker to boost relevant tools.
Never raises — returns empty profile on any failure.
"""

import json
import os
import signal
from datetime import datetime, timezone

STACK_FILE = os.path.expanduser("~/.claude/dispatch/stack_profile.json")

MANIFEST_LANGUAGES = {
    "package.json":     "javascript",
    "requirements.txt": "python",
    "Pipfile":          "python",
    "pyproject.toml":   "python",
    "go.mod":           "go",
    "Cargo.toml":       "rust",
    "pom.xml":          "java",
    "build.gradle":     "java",
    "pubspec.yaml":     "dart",
}

JS_FRAMEWORK_KEYS = ["react", "vue", "angular", "next", "svelte", "express", "fastify", "nestjs", "vite", "nuxt"]
PYTHON_FRAMEWORK_KEYS = ["fastapi", "django", "flask", "langchain", "llama-index", "pandas", "pytest"]

TOOL_CHECKS = [
    ("Dockerfile",             "docker"),
    ("docker-compose.yml",     "docker"),
    ("docker-compose.yaml",    "docker"),
    (".github/workflows",      "github-actions"),
    (".terraform",             "terraform"),
    ("k8s",                    "kubernetes"),
    ("kubernetes",             "kubernetes"),
]


def _timeout_handler(signum, frame):
    raise TimeoutError("stack scan timed out")


def detect_stack(cwd: str) -> dict:
    """Scan cwd for manifest files to identify languages, frameworks, and tools.

    Returns:
        {
            "languages": [...],
            "frameworks": [...],
            "tools": [...],
            "scanned_at": "2026-03-14T...",
            "cwd": "/path/to/project"
        }

    Never raises. Returns empty lists on any failure.
    """
    empty = {"languages": [], "frameworks": [], "tools": [], "scanned_at": _now(), "cwd": cwd}
    try:
        # 1-second timeout guard for hung filesystems
        signal.signal(signal.SIGALRM, _timeout_handler)
        signal.alarm(1)
        try:
            result = _scan(cwd)
        finally:
            signal.alarm(0)
        return result
    except Exception:
        return empty


def _scan(cwd: str) -> dict:
    if not os.path.isdir(cwd):
        return {"languages": [], "frameworks": [], "tools": [], "scanned_at": _now(), "cwd": cwd}

    languages = []
    frameworks = []

    for filename, lang in MANIFEST_LANGUAGES.items():
        path = os.path.join(cwd, filename)
        if os.path.isfile(path):
            if lang not in languages:
                languages.append(lang)
            # Extract frameworks from manifest content
            if filename == "package.json":
                frameworks.extend(f for f in _detect_js_frameworks(path) if f not in frameworks)
            elif filename in ("requirements.txt", "Pipfile"):
                frameworks.extend(f for f in _detect_python_frameworks(path) if f not in frameworks)
            elif filename == "pubspec.yaml":
                if "flutter" not in frameworks:
                    frameworks.append("flutter")

    tools = _detect_tools(cwd)
    mcp_servers = _detect_mcp_servers(cwd)

    return {
        "languages": languages,
        "frameworks": frameworks,
        "tools": tools,
        "mcp_servers": mcp_servers,
        "scanned_at": _now(),
        "cwd": cwd,
    }


def _detect_js_frameworks(package_json_path: str) -> list:
    """Read package.json and return list of known framework names. Returns [] on failure."""
    try:
        with open(package_json_path) as f:
            data = json.load(f)
        all_deps = {}
        all_deps.update(data.get("dependencies", {}))
        all_deps.update(data.get("devDependencies", {}))
        found = []
        for key in JS_FRAMEWORK_KEYS:
            if any(key in dep for dep in all_deps):
                if key not in found:
                    found.append(key)
        return found
    except Exception:
        return []


def _detect_python_frameworks(req_path: str) -> list:
    """Read requirements.txt or Pipfile and return list of known framework names. Returns [] on failure."""
    try:
        with open(req_path) as f:
            content = f.read().lower()
        found = []
        for key in PYTHON_FRAMEWORK_KEYS:
            if key in content:
                found.append(key)
        return found
    except Exception:
        return []


def _detect_tools(cwd: str) -> list:
    """Check cwd for tool config files/dirs. Returns [] on failure."""
    try:
        found = []
        for check, tool in TOOL_CHECKS:
            path = os.path.join(cwd, check)
            if os.path.exists(path) and tool not in found:
                found.append(tool)
        return found
    except Exception:
        return []


def _detect_mcp_servers(cwd: str) -> list:
    """Read .mcp.json files and return list of configured MCP server names.

    Checks user-global ~/.claude/.mcp.json and project-local {cwd}/.mcp.json.
    Returns [] on any failure — never raises.
    """
    found = []
    paths = [
        os.path.expanduser("~/.claude/.mcp.json"),
        os.path.join(cwd, ".mcp.json"),
    ]
    for path in paths:
        try:
            with open(path) as f:
                data = json.load(f)
            for name in data.get("mcpServers", {}):
                if name not in found:
                    found.append(name)
        except Exception:
            pass
    return found


def load_stack_profile(stack_file: str = None) -> dict:
    """Load existing stack profile from disk. Returns empty profile on failure."""
    path = stack_file or STACK_FILE
    try:
        with open(path) as f:
            return json.load(f)
    except Exception:
        return {"languages": [], "frameworks": [], "tools": [], "mcp_servers": [], "cwd": ""}


def save_stack_profile(profile: dict, stack_file: str = None):
    """Write stack profile to disk. Silently fails on any error."""
    path = stack_file or STACK_FILE
    try:
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w") as f:
            json.dump(profile, f)
    except Exception:
        pass


def scan_and_save(cwd: str, stack_file: str = None) -> dict:
    """Detect stack for cwd and persist to disk. Returns the profile dict."""
    profile = detect_stack(cwd)
    save_stack_profile(profile, stack_file)
    return profile


def should_rescan(cwd: str, stack_file: str = None) -> bool:
    """Return True if cwd differs from saved profile's cwd OR profile is >24h old."""
    try:
        profile = load_stack_profile(stack_file)
        if profile.get("cwd") != cwd:
            return True
        scanned_at = profile.get("scanned_at", "")
        if not scanned_at:
            return True
        then = datetime.fromisoformat(scanned_at.replace("Z", "+00:00"))
        # Make timezone-aware if naive
        if then.tzinfo is None:
            then = then.replace(tzinfo=timezone.utc)
        now = datetime.now(tz=timezone.utc)
        age_hours = (now - then).total_seconds() / 3600
        return age_hours > 24
    except Exception:
        return True


def _now() -> str:
    return datetime.now(tz=timezone.utc).isoformat()
