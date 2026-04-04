import os
import re
from typing import Optional

MEMORY_LINE_LIMIT = 180  # warn when MEMORY.md exceeds this many lines


def _memory_dir(cwd: str) -> str:
    """Return the Claude auto-memory directory for the given working directory."""
    encoded = cwd.replace('/', '-')
    return os.path.expanduser(f"~/.claude/projects/{encoded}/memory")


def check_memory_audit(cwd: str) -> Optional[dict]:
    """
    Scan MEMORY.md for broken links (referenced files that don't exist).

    Returns a dict with issue details if problems are found, None otherwise.

    Dict keys:
      memory_md   — absolute path to MEMORY.md
      memory_dir  — directory containing MEMORY.md
      broken      — list of {"title": str, "path": str} for each broken link
      count       — number of broken links
    """
    memory_dir = _memory_dir(cwd)
    memory_md = os.path.join(memory_dir, "MEMORY.md")

    if not os.path.isfile(memory_md):
        return None

    content = _read_file(memory_md)
    if content is None:
        return None

    # Find all markdown links: [title](path)
    links = re.findall(r'\[([^\]]+)\]\(([^)]+)\)', content)

    broken = []
    for title, path in links:
        # Skip external URLs and anchor links
        if path.startswith(('http://', 'https://', '#')):
            continue
        full_path = os.path.join(memory_dir, path)
        if not os.path.isfile(full_path):
            broken.append({"title": title, "path": path})

    line_count = content.count("\n") + 1
    bloated = line_count > MEMORY_LINE_LIMIT

    if not broken and not bloated:
        return None

    return {
        "memory_md": memory_md,
        "memory_dir": memory_dir,
        "broken": broken,
        "count": len(broken),
        "line_count": line_count,
        "bloated": bloated,
    }


def _read_file(path: str) -> Optional[str]:
    try:
        with open(path, encoding="utf-8") as f:
            return f.read()
    except OSError:
        return None
