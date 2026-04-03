import os
from typing import Optional

COMPACT_THRESHOLD = 0.60

# Calibration constants — proxy model until CC exposes token counts to hooks
_MSG_FILL_PER_STEP = 0.004   # each message adds ~0.4% context fill
_LINE_FILL_PER_100 = 0.015   # 100 CLAUDE.md lines ≈ 1.5% fill


def estimate_context_fill(message_count: int, cwd: str) -> float:
    """
    Estimate context fill as a fraction [0.0, 1.0].
    Proxy model: message count + CLAUDE.md size (project + global).
    Replace with CC token API when available.
    """
    fill = message_count * _MSG_FILL_PER_STEP

    for path in [
        os.path.join(cwd, "CLAUDE.md"),
        os.path.expanduser("~/.claude/CLAUDE.md"),
    ]:
        if os.path.exists(path):
            try:
                with open(path) as f:
                    lines = sum(1 for _ in f)
                fill += (lines / 100) * _LINE_FILL_PER_100
            except Exception:
                pass

    return min(fill, 1.0)


def should_compact(message_count: int, cwd: str) -> Optional[float]:
    """
    Returns estimated fill if compact is recommended (>= 60%), else None.
    """
    fill = estimate_context_fill(message_count, cwd)
    if fill >= COMPACT_THRESHOLD:
        return fill
    return None
