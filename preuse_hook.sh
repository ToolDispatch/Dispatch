#!/bin/bash
# =============================================================================
# Dispatch — PreToolUse Hook
#
# Fires when CC is about to invoke a tool. Intercepts Skill, Agent, and mcp__*
# calls, scores marketplace alternatives, and blocks (exit 2) if a better
# option exists by >= THRESHOLD points above cc_score.
#
# Exit codes:
#   0 — allow the tool call to proceed
#   2 — block the tool call; stdout is injected into CC's context
# =============================================================================

set -uo pipefail

read -r -t 5 HOOK_INPUT || true
SKILL_ROUTER_DIR="${HOME}/.claude/skill-router"
CONFIG_FILE="$SKILL_ROUTER_DIR/config.json"

THRESHOLD=10   # minimum score gap above cc_score to block

# ── Parse tool_name ────────────────────────────────────────────────────────
TOOL_NAME=$(python3 -c "
import json, sys
d = json.loads(sys.argv[1])
print(d.get('tool_name', ''))
" "$HOOK_INPUT" 2>/dev/null || echo "")

[ -z "$TOOL_NAME" ] && exit 0

# ── Should we intercept this tool? ────────────────────────────────────────
SHOULD_INTERCEPT=$(python3 -c "
import sys
sys.path.insert(0, sys.argv[1])
from interceptor import should_intercept
print('yes' if should_intercept(sys.argv[2]) else 'no')
" "$SKILL_ROUTER_DIR" "$TOOL_NAME" 2>/dev/null || echo "no")

[ "$SHOULD_INTERCEPT" != "yes" ] && exit 0

# ── Check bypass token (user previously said 'proceed') ───────────────────
HAS_BYPASS=$(python3 -c "
import sys
sys.path.insert(0, sys.argv[1])
from interceptor import check_bypass, clear_bypass
tool = sys.argv[2]
if check_bypass(tool):
    clear_bypass(tool)
    print('yes')
else:
    print('no')
" "$SKILL_ROUTER_DIR" "$TOOL_NAME" 2>/dev/null || echo "no")

[ "$HAS_BYPASS" = "yes" ] && exit 0

# ── Resolve API key / token ────────────────────────────────────────────────
DISPATCH_TOKEN=$(python3 -c "
import json
try:
    d = json.load(open('$CONFIG_FILE'))
    print(d.get('token', ''))
except:
    print('')
" 2>/dev/null || echo "")

DISPATCH_ENDPOINT=$(python3 -c "
import json
try:
    d = json.load(open('$CONFIG_FILE'))
    print(d.get('endpoint', 'https://dispatch.visionairy.biz'))
except:
    print('https://dispatch.visionairy.biz')
" 2>/dev/null || echo "https://dispatch.visionairy.biz")

export ANTHROPIC_API_KEY

if [ -z "$DISPATCH_TOKEN" ] && [ -z "$ANTHROPIC_API_KEY" ]; then
    exit 0
fi

# ── Extract cc_tool label from tool input ─────────────────────────────────
CC_TOOL=$(python3 -c "
import json, sys
sys.path.insert(0, sys.argv[1])
from interceptor import extract_cc_tool
d = json.loads(sys.argv[2])
print(extract_cc_tool(d.get('tool_name', ''), d.get('tool_input', {})))
" "$SKILL_ROUTER_DIR" "$HOOK_INPUT" 2>/dev/null || echo "$TOOL_NAME")

# ── Load task type + context from state (written by dispatch.sh Stage 1) ──
TASK_TYPE=$(python3 -c "
import sys
sys.path.insert(0, sys.argv[1])
from interceptor import get_task_type
print(get_task_type())
" "$SKILL_ROUTER_DIR" 2>/dev/null || echo "general")

CONTEXT_SNIPPET=$(python3 -c "
import sys
sys.path.insert(0, sys.argv[1])
from interceptor import get_context_snippet
print(get_context_snippet())
" "$SKILL_ROUTER_DIR" 2>/dev/null || echo "")

CATEGORY=$(python3 -c "
import sys
sys.path.insert(0, sys.argv[1])
from interceptor import get_category
print(get_category())
" "$SKILL_ROUTER_DIR" 2>/dev/null || echo "unknown")

# ── Evaluate marketplace alternatives ─────────────────────────────────────
RANK_TMP=$(mktemp)
trap 'rm -f "${RANK_TMP:-}" 2>/dev/null' EXIT

if [ -n "$DISPATCH_TOKEN" ]; then
    # Hosted path
    python3 -c "
import json, sys
print(json.dumps({
    'task_type': sys.argv[1],
    'context_snippet': sys.argv[2],
    'cc_tool': sys.argv[3],
    'category_id': sys.argv[4],
}))
" "$TASK_TYPE" "$CONTEXT_SNIPPET" "$CC_TOOL" "$CATEGORY" > "$RANK_TMP" 2>/dev/null

    RANK_HTTP=$(curl -s -w "\n%{http_code}" \
        -X POST "$DISPATCH_ENDPOINT/rank" \
        -H "Authorization: Bearer $DISPATCH_TOKEN" \
        -H "Content-Type: application/json" \
        --data @"$RANK_TMP" \
        --max-time 8 2>/dev/null || echo '{"all":[],"cc_score":0}
200')
    RANK_CODE=$(echo "$RANK_HTTP" | tail -n 1)
    RANK_BODY=$(echo "$RANK_HTTP" | sed '$d')

    if [ "$RANK_CODE" = "200" ]; then
        RECOMMENDATIONS="$RANK_BODY"
    else
        # Fallback to local BYOK ranking
        RECOMMENDATIONS=$(python3 -c "
import sys, json
sys.path.insert(0, sys.argv[3])
from evaluator import build_recommendation_list
print(json.dumps(build_recommendation_list(sys.argv[1], context_snippet=sys.argv[2], cc_tool=sys.argv[4], category_id=sys.argv[5])))
" "$TASK_TYPE" "$CONTEXT_SNIPPET" "$SKILL_ROUTER_DIR" "$CC_TOOL" "$CATEGORY" 2>/dev/null || echo '{"all":[],"cc_score":0}')
    fi
else
    # BYOK path
    RECOMMENDATIONS=$(python3 -c "
import sys, json
sys.path.insert(0, sys.argv[3])
from evaluator import build_recommendation_list
print(json.dumps(build_recommendation_list(sys.argv[1], context_snippet=sys.argv[2], cc_tool=sys.argv[4], category_id=sys.argv[5])))
" "$TASK_TYPE" "$CONTEXT_SNIPPET" "$SKILL_ROUTER_DIR" "$CC_TOOL" "$CATEGORY" 2>/dev/null || echo '{"all":[],"cc_score":0}')
fi

# ── Check threshold: any marketplace tool beats CC by >= THRESHOLD? ────────
SHOULD_BLOCK=$(python3 -c "
import json, sys
try:
    r = json.loads(sys.argv[1])
    cc_score = int(r.get('cc_score', 0))
    threshold = int(sys.argv[2])
    tools = r.get('all', [])
    if tools and tools[0].get('score', 0) >= cc_score + threshold:
        print('yes')
    else:
        print('no')
except:
    print('no')
" "$RECOMMENDATIONS" "$THRESHOLD" 2>/dev/null || echo "no")

[ "$SHOULD_BLOCK" != "yes" ] && exit 0

# ── Write bypass token so 'proceed' re-attempt passes through ─────────────
python3 -c "
import sys
sys.path.insert(0, sys.argv[1])
from interceptor import write_bypass
write_bypass(sys.argv[2])
" "$SKILL_ROUTER_DIR" "$TOOL_NAME" 2>/dev/null || true

# ── Render comparison output — exit 2 blocks the tool call ────────────────
python3 - "$CC_TOOL" "$RECOMMENDATIONS" "$TASK_TYPE" <<'PYEOF'
import json, sys

cc_tool = sys.argv[1]
try:
    recs = json.loads(sys.argv[2])
except Exception:
    recs = {"all": [], "top_pick": None, "cc_score": 0}
task_type = sys.argv[3]
task_display = task_type.replace("-", " ").title()

all_tools = recs.get("all", [])
top_pick = recs.get("top_pick") or (all_tools[0] if all_tools else None)
cc_score = recs.get("cc_score", 0)

lines = [
    f"[DISPATCH] Intercepted: CC is about to use '{cc_tool}' for {task_display}.",
    f"CC's tool score for this task: {cc_score}/100",
    "",
    "Marketplace alternatives:",
]

for i, tool in enumerate(all_tools, 1):
    name = tool.get("name", "")
    score = tool.get("score", "?")
    reason = tool.get("reason", "")
    install_cmd = tool.get("install_cmd", "").replace("\n", " ")
    install_url = tool.get("install_url", "").replace("\n", " ")
    top_marker = " ← TOP PICK" if (top_pick and name == top_pick.get("name")) else ""

    lines.append(f"  {i}. {name} [{score}/100]{top_marker}")
    if reason:
        lines.append(f"     Why: {reason}")
    if install_cmd:
        lines.append(f"     Install + restart: {install_cmd} && claude")
    if install_url:
        lines.append(f"     More info: {install_url}")

top_name = top_pick["name"] if top_pick else "the top tool"
lines.extend([
    "",
    f"⚠ A marketplace tool scores higher than '{cc_tool}' for this task.",
    "  Options:",
    f"  1. Say 'proceed' to continue with '{cc_tool}' (one-time bypass, no restart needed)",
    f"  2. Install {top_name} — run /compact first, then install and restart CC",
    "  3. Ignore Dispatch for this task — say 'skip dispatch'",
    "",
    "Present these options to the user. Wait for their response before taking any action.",
])

print("\n".join(lines))
PYEOF

exit 2
