import os
from typing import Optional, List, Tuple

SKILLS_COUNT_LIMIT = 15      # warn when more than this many skills registered
SKILLS_SIZE_LIMIT_KB = 200   # warn when total SKILL.md bytes exceeds this


def _get_skills_dir() -> str:
    return os.path.expanduser("~/.claude/skills")


def _scan_skills() -> List[Tuple[str, int]]:
    """Return list of (skill_name, skill_md_bytes) for all installed skills."""
    skills_dir = _get_skills_dir()
    if not os.path.isdir(skills_dir):
        return []

    results = []
    try:
        for entry in sorted(os.listdir(skills_dir)):
            skill_path = os.path.join(skills_dir, entry)
            if not os.path.isdir(skill_path):
                continue
            skill_md = os.path.join(skill_path, "SKILL.md")
            size = 0
            if os.path.isfile(skill_md):
                try:
                    size = os.path.getsize(skill_md)
                except Exception:
                    pass
            results.append((entry, size))
    except Exception:
        pass
    return results


def check_skills() -> Optional[dict]:
    """
    Returns a dict with skill stats if the skills install warrants a nudge.
    Returns None if within acceptable limits.

    Dict keys: count, total_kb, top_heavy (list of (name, kb) for largest skills)
    """
    skills = _scan_skills()
    if not skills:
        return None

    count = len(skills)
    total_bytes = sum(size for _, size in skills)
    total_kb = total_bytes // 1024

    if count <= SKILLS_COUNT_LIMIT and total_kb <= SKILLS_SIZE_LIMIT_KB:
        return None

    # Top 5 by size
    top_heavy = sorted(skills, key=lambda x: x[1], reverse=True)[:5]
    top_heavy_kb = [(name, size // 1024) for name, size in top_heavy]

    return {
        "count": count,
        "total_kb": total_kb,
        "top_heavy": top_heavy_kb,
    }
