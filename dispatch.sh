#!/bin/bash
# =============================================================================
# Dispatch — Skill Router Hook (UserPromptSubmit)
#
# Stage 1: Haiku topic shift detection (~100ms, every message)
# Stage 2: Plugin evaluation + interactive UI (only on confirmed shift)
# =============================================================================

set -uo pipefail

HOOK_INPUT=$(cat)
SKILL_ROUTER_DIR="/home/visionairy/.claude/skill-router"
STATE_FILE="$SKILL_ROUTER_DIR/state.json"

# ── Resolve API key (env or from mcp.json) ────────────────────────────────
if [ -z "${ANTHROPIC_API_KEY:-}" ]; then
    ANTHROPIC_API_KEY=$(python3 -c "
import json
try:
    d = json.load(open('/home/visionairy/.mcp.json'))
    print(d['mcpServers']['xpansion']['env']['ANTHROPIC_API_KEY'])
except:
    print('')
" 2>/dev/null || echo "")
fi
export ANTHROPIC_API_KEY

# ── Extract transcript path + cwd ─────────────────────────────────────────
TRANSCRIPT_PATH=$(python3 -c "
import sys, json
d = json.loads(sys.stdin.read())
print(d.get('transcript_path', ''))
" <<< "$HOOK_INPUT" 2>/dev/null || echo "")

CWD=$(python3 -c "
import sys, json
d = json.loads(sys.stdin.read())
print(d.get('cwd', '$PWD'))
" <<< "$HOOK_INPUT" 2>/dev/null || echo "$PWD")

# ── Load last task type ────────────────────────────────────────────────────
LAST_TASK_TYPE=$(python3 -c "
import json
try:
    d = json.load(open('$STATE_FILE'))
    v = d.get('last_task_type')
    print(v if v else '')
except:
    print('')
" 2>/dev/null || echo "")

# ── Stage 1: Classify ──────────────────────────────────────────────────────
CLASSIFICATION=$(python3 "$SKILL_ROUTER_DIR/classifier.py" \
    --transcript "$TRANSCRIPT_PATH" \
    --cwd "$CWD" \
    --last-task-type "$LAST_TASK_TYPE" \
    2>/dev/null || echo '{"shift":false,"task_type":"general","confidence":0}')

SHIFT=$(python3 -c "
import json, sys
d = json.loads(sys.argv[1])
print('true' if d.get('shift') else 'false')
" "$CLASSIFICATION" 2>/dev/null || echo "false")

TASK_TYPE=$(python3 -c "
import json, sys
print(json.loads(sys.argv[1]).get('task_type','general'))
" "$CLASSIFICATION" 2>/dev/null || echo "general")

CONFIDENCE=$(python3 -c "
import json, sys
print(json.loads(sys.argv[1]).get('confidence', 0))
" "$CLASSIFICATION" 2>/dev/null || echo "0")

# ── Exit early: no shift or low confidence ────────────────────────────────
[ "$SHIFT" != "true" ] && exit 0

CONF_OK=$(python3 -c "print('yes' if float('$CONFIDENCE') >= 0.7 else 'no')" 2>/dev/null || echo "no")
[ "$CONF_OK" != "yes" ] && exit 0

# ── Stage 2: Evaluate + render UI ─────────────────────────────────────────
RECOMMENDATIONS=$(python3 -c "
import sys, json
sys.path.insert(0, '$SKILL_ROUTER_DIR')
from evaluator import build_recommendation_list
task_type = sys.argv[1]
print(json.dumps(build_recommendation_list(task_type)))
" "$TASK_TYPE" 2>/dev/null || echo '{"installed":[],"suggested":[]}')

# Render and prompt
python3 - "$TASK_TYPE" "$RECOMMENDATIONS" <<'PYEOF'
import json, sys

task_type = sys.argv[1]
try:
    recs = json.loads(sys.argv[2])
except Exception:
    recs = {"installed": [], "suggested": []}

installed = recs.get("installed", [])
suggested = recs.get("suggested", [])

if not installed and not suggested:
    sys.exit(0)

W = 52
bar = "━" * W
print(f"\n{bar}", flush=True)
print(f" ⚡ Dispatch  →  {task_type.replace('-', ' ').title()} task detected", flush=True)
print(bar, flush=True)

if installed:
    print(" RECOMMENDED (installed):", flush=True)
    for p in installed:
        print(f"   + {p['name']}", flush=True)
        reason = p.get('reason', '')
        if reason:
            print(f"     {reason}", flush=True)

if suggested:
    print("\n SUGGESTED (not installed):", flush=True)
    for s in suggested:
        print(f"   ↓ {s['name']}", flush=True)
        cmd = s.get('install_cmd', '')
        if cmd:
            print(f"     → {cmd}", flush=True)

print(f"\n [Enter] or wait 3s to proceed", flush=True)
print(bar, flush=True)
PYEOF

# Wait for user confirmation (3s max — hook has 10s total timeout)
read -r -t 3 < /dev/tty 2>/dev/null || true

# ── Update state ───────────────────────────────────────────────────────────
python3 -c "
import json, sys
from datetime import datetime
state_file, task_type = sys.argv[1], sys.argv[2]
with open(state_file, 'w') as f:
    json.dump({'last_task_type': task_type, 'last_updated': datetime.now().isoformat()}, f)
" "$STATE_FILE" "$TASK_TYPE" 2>/dev/null || true

exit 0
