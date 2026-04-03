#!/usr/bin/env bash
# =============================================================================
# XF Boundary Auditor — PreToolUse hook
#
# Fires on Edit + Write.
# Exit 0 = allow  (stamp written to stderr — visible in terminal)
# Exit 2 = block  (violation/concern report written to stdout — CC sees it)
#
# Tier logic:
#   No token (BYOK) → once-daily upgrade teaser, exit 0
#   Free hosted     → run suite; silent exit if daily quota already exhausted
#   Pro             → run suite, unlimited
#
# Never blocks Claude on internal errors — trap 'exit 0' ERR.
# =============================================================================

trap 'exit 0' ERR

AUDITOR_DIR="${HOME}/.claude/xf-boundary-auditor"
CONFIG_FILE="${HOME}/.claude/dispatch/config.json"
TEASER_DATE_FILE="${HOME}/.claude/dispatch/xf_teaser_date"
HOOK_INPUT="$(cat)"

# Filter: only audit Edit and Write
TOOL_NAME=$(printf '%s' "$HOOK_INPUT" | python3 -c \
  'import json,sys; print(json.loads(sys.stdin.read()).get("tool_name",""))' \
  2>/dev/null || echo "")

[ "$TOOL_NAME" != "Edit" ] && [ "$TOOL_NAME" != "Write" ] && exit 0

# ── Tier + quota gate ─────────────────────────────────────────────────────
# Returns one of: "run" | "teaser" | "quota_done"
GATE=$(python3 - "$CONFIG_FILE" <<'PYEOF'
import json, sys, os, time, urllib.request
from datetime import date

config_path = sys.argv[1]
try:
    cfg = json.loads(open(config_path).read())
except Exception:
    cfg = {}

token    = cfg.get("token", "")
endpoint = cfg.get("endpoint", "https://dispatch.visionairy.biz")

# No token = BYOK open-source user → teaser
if not token:
    print("teaser")
    sys.exit(0)

# Check/refresh plan (24h cache)
plan    = cfg.get("plan", "")
checked = cfg.get("plan_checked_at", 0)
if not plan or (time.time() - checked) >= 86400:
    try:
        url = f"{endpoint}/tier?token={token}"
        with urllib.request.urlopen(url, timeout=3) as resp:
            data = json.loads(resp.read())
        plan = data.get("plan", "free")
    except Exception:
        plan = cfg.get("plan", "free")
    cfg["plan"] = plan
    cfg["plan_checked_at"] = time.time()
    try:
        import tempfile
        tmp = config_path + ".tmp"
        with open(tmp, "w") as f:
            json.dump(cfg, f, indent=2)
        os.replace(tmp, config_path)
    except Exception:
        pass

if plan == "pro":
    print("run")
    sys.exit(0)

# Free: check if quota exhausted today
exhausted_date = cfg.get("quota_exhausted_date", "")
if exhausted_date == date.today().isoformat():
    print("quota_done")
    sys.exit(0)

print("run")
PYEOF
2>/dev/null || echo "run")

# ── BYOK: once-daily teaser ───────────────────────────────────────────────
if [ "$GATE" = "teaser" ]; then
    TODAY=$(date +%Y-%m-%d)
    LAST_SHOWN=$(cat "$TEASER_DATE_FILE" 2>/dev/null || echo "")
    if [ "$LAST_SHOWN" != "$TODAY" ]; then
        echo "$TODAY" > "$TEASER_DATE_FILE"
        cat >&2 <<'TEASER'
┌─────────────────────────────────────────────────────────────────┐
│  ◈ Visionairy Xpansion™ — upgrade to unlock                    │
│                                                                 │
│  XFBA  XF Boundary Auditor — catches broken imports, arity     │
│        mismatches, and missing env vars before they hit         │
│        runtime. Blocks bad edits before Claude writes them.     │
│                                                                 │
│  XSIA  XF System Impact Analyzer — flags edits that affect     │
│        callers, change data flow, add side effects, or remove   │
│        error handling across your entire codebase.              │
│                                                                 │
│  BYOK  Unlimited Dispatch routing — free forever.              │
│  Free  5 turns/day · XFBA + XSIA included                      │
│  Pro   $10/mo · Unlimited + Sonnet ranking                      │
│                                                                 │
│  dispatch.visionairy.biz/pro                                    │
└─────────────────────────────────────────────────────────────────┘
TEASER
    fi
    exit 0
fi

# ── Free quota exhausted for today — silent ───────────────────────────────
if [ "$GATE" = "quota_done" ]; then
    exit 0
fi

# ── Run boundary auditor (Free or Pro) ───────────────────────────────────
trap - ERR
printf '%s' "$HOOK_INPUT" | python3 "$AUDITOR_DIR/auditor.py"
EXIT_CODE=$?

# Exit 2 = intentional block with violation report on stdout.
# Any other non-zero = auditor crashed — never silently block Claude.
if [ "$EXIT_CODE" -ne 0 ] && [ "$EXIT_CODE" -ne 2 ]; then
    exit 0
fi

exit $EXIT_CODE
