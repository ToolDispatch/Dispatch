#!/bin/bash
# =============================================================================
# Dispatch — Skill Router Hook (UserPromptSubmit)
#
# Hosted mode:  token in config.json → calls dispatch.visionairy.biz
# BYOK mode:    ANTHROPIC_API_KEY set → calls Haiku directly (no token needed)
#
# Stage 1: Topic shift detection (~100ms, every message)
# Stage 2: Plugin evaluation + interactive UI (only on confirmed shift)
# =============================================================================

set -uo pipefail

HOOK_INPUT=$(cat)
SKILL_ROUTER_DIR="${HOME}/.claude/skill-router"
STATE_FILE="$SKILL_ROUTER_DIR/state.json"
CONFIG_FILE="$SKILL_ROUTER_DIR/config.json"

# Ensure tmpfiles are always cleaned up on exit
CLASSIFY_TMP=""
RANK_TMP=""
trap 'rm -f "${CLASSIFY_TMP:-}" "${RANK_TMP:-}" 2>/dev/null' EXIT

# Brand icon: blue ◎ (U+25CE) via ANSI — radar sweep target in terminal
DICON=$'\033[94m◎\033[0m'

# ── Load hosted config (token + endpoint) ─────────────────────────────────
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

# ── Resolve API key (env or from mcp.json) — BYOK fallback ───────────────
if [ -z "${ANTHROPIC_API_KEY:-}" ]; then
    ANTHROPIC_API_KEY=$(python3 -c "
import json
try:
    import os; d = json.load(open(os.path.expanduser('~/.mcp.json')))
    print(d['mcpServers']['xpansion']['env']['ANTHROPIC_API_KEY'])
except:
    print('')
" 2>/dev/null || echo "")
fi
export ANTHROPIC_API_KEY

# ── If no token AND no API key, exit silently ─────────────────────────────
if [ -z "$DISPATCH_TOKEN" ] && [ -z "$ANTHROPIC_API_KEY" ]; then
    exit 0
fi

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

# ── Load last task type + limit cooldown ──────────────────────────────────
LAST_TASK_TYPE=$(python3 -c "
import json
try:
    d = json.load(open('$STATE_FILE'))
    v = d.get('last_task_type')
    print(v if v else '')
except:
    print('')
" 2>/dev/null || echo "")

LIMIT_COOLDOWN=$(python3 -c "
import json
try:
    d = json.load(open('$STATE_FILE'))
    print(int(d.get('limit_cooldown', 0)))
except:
    print(0)
" 2>/dev/null || echo "0")

AUTH_COOLDOWN=$(python3 -c "
import json
try:
    d = json.load(open('$STATE_FILE'))
    print(int(d.get('auth_invalid_cooldown', 0)))
except:
    print(0)
" 2>/dev/null || echo "0")

# ── Stage 1: Classify ──────────────────────────────────────────────────────
if [ -n "$DISPATCH_TOKEN" ]; then
    # ── Hosted mode ──────────────────────────────────────────────────────────
    CLASSIFY_PAYLOAD=$(python3 -c "
import json, sys, os
transcript_path = sys.argv[1]
cwd = sys.argv[2]
last_task_type = sys.argv[3] or None
transcript = []
if transcript_path and os.path.exists(transcript_path):
    try:
        with open(transcript_path) as f:
            for line in f:
                line = line.strip()
                if line:
                    try:
                        transcript.append(json.loads(line))
                    except Exception:
                        pass
    except Exception:
        pass
transcript = transcript[-20:]  # Keep last 20 entries to limit payload size
print(json.dumps({'transcript': transcript, 'cwd': cwd, 'last_task_type': last_task_type}))
" "$TRANSCRIPT_PATH" "$CWD" "$LAST_TASK_TYPE" 2>/dev/null || echo '{}')

    CLASSIFY_TMP=$(mktemp)
    echo "$CLASSIFY_PAYLOAD" > "$CLASSIFY_TMP"
    HTTP_RESPONSE=$(curl -s -w "\n%{http_code}" \
        -X POST "$DISPATCH_ENDPOINT/classify" \
        -H "Authorization: Bearer $DISPATCH_TOKEN" \
        -H "Content-Type: application/json" \
        --data @"$CLASSIFY_TMP" \
        --max-time 5 2>/dev/null || echo '{"shift":false}
200')
    rm -f "$CLASSIFY_TMP"

    HTTP_BODY=$(echo "$HTTP_RESPONSE" | head -n -1)
    HTTP_CODE=$(echo "$HTTP_RESPONSE" | tail -n 1)

    # Handle limit reached (402)
    if [ "$HTTP_CODE" = "402" ]; then
        # Suppress notice for 5 triggers after first display
        if [ "$LIMIT_COOLDOWN" -gt 0 ]; then
            python3 -c "
import json, sys
from datetime import datetime
state_file, task_type = sys.argv[1], sys.argv[2]
try:
    d = json.load(open(state_file))
except Exception:
    d = {}
d['limit_cooldown'] = max(0, int(d.get('limit_cooldown', 1)) - 1)
d['last_task_type'] = task_type
d['last_updated'] = datetime.now().isoformat()
with open(state_file, 'w') as f:
    json.dump(d, f)
" "$STATE_FILE" "${LAST_TASK_TYPE:-}" 2>/dev/null || true
            exit 0
        fi
        UPGRADE_URL=$(python3 -c "
import json, sys
try:
    d = json.loads(sys.argv[1])
    print(d.get('upgrade_url', 'https://dispatch.visionairy.biz/pro'))
except:
    print('https://dispatch.visionairy.biz/pro')
" "$HTTP_BODY" 2>/dev/null || echo "https://dispatch.visionairy.biz/pro")
        W=52
        echo "" >&2
        printf '━%.0s' $(seq 1 $W) >&2; echo >&2
        echo " ${DICON} Dispatch  →  Task shift detected" >&2
        printf '━%.0s' $(seq 1 $W) >&2; echo >&2
        echo " You've used your 5 free detections today." >&2
        echo " Upgrade for unlimited — \$6/month → $UPGRADE_URL" >&2
        printf '━%.0s' $(seq 1 $W) >&2; echo >&2
        # Set cooldown: suppress for next 5 triggers
        python3 -c "
import json, sys
from datetime import datetime
state_file, task_type = sys.argv[1], sys.argv[2]
try:
    d = json.load(open(state_file))
except Exception:
    d = {}
d['limit_cooldown'] = 5
d['last_task_type'] = task_type
d['last_updated'] = datetime.now().isoformat()
with open(state_file, 'w') as f:
    json.dump(d, f)
" "$STATE_FILE" "${LAST_TASK_TYPE:-}" 2>/dev/null || true
        exit 0
    fi

    # Handle invalid/expired token (401)
    if [ "$HTTP_CODE" = "401" ]; then
        if [ "$AUTH_COOLDOWN" -gt 0 ]; then
            python3 -c "
import json, sys
from datetime import datetime
state_file = sys.argv[1]
try:
    d = json.load(open(state_file))
except Exception:
    d = {}
d['auth_invalid_cooldown'] = max(0, int(d.get('auth_invalid_cooldown', 1)) - 1)
d['last_updated'] = datetime.now().isoformat()
with open(state_file, 'w') as f:
    json.dump(d, f)
" "$STATE_FILE" 2>/dev/null || true
            exit 0
        fi
        W=52
        echo "" >&2
        printf '━%.0s' $(seq 1 $W) >&2; echo >&2
        echo " ${DICON} Dispatch  →  Token invalid or expired" >&2
        echo " Re-authenticate: $DISPATCH_ENDPOINT/token-lookup" >&2
        printf '━%.0s' $(seq 1 $W) >&2; echo >&2
        python3 -c "
import json, sys
from datetime import datetime
state_file = sys.argv[1]
try:
    d = json.load(open(state_file))
except Exception:
    d = {}
d['auth_invalid_cooldown'] = 20
d['last_updated'] = datetime.now().isoformat()
with open(state_file, 'w') as f:
    json.dump(d, f)
" "$STATE_FILE" 2>/dev/null || true
        exit 0
    fi

    CLASSIFICATION="$HTTP_BODY"
else
    # ── BYOK mode ─────────────────────────────────────────────────────────
    CLASSIFICATION=$(python3 "$SKILL_ROUTER_DIR/classifier.py" \
        --transcript "$TRANSCRIPT_PATH" \
        --cwd "$CWD" \
        --last-task-type "$LAST_TASK_TYPE" \
        2>/dev/null || echo '{"shift":false,"task_type":"general","confidence":0}')
fi

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
if [ -n "$DISPATCH_TOKEN" ]; then
    # ── Hosted rank ────────────────────────────────────────────────────────
    RANK_TMP=$(mktemp)
    python3 -c "
import json, sys
sys.path.insert(0, sys.argv[2])
try:
    from evaluator import scan_installed_plugins, get_installed_skills, PLUGINS_DIR
    installed_plugins = scan_installed_plugins(PLUGINS_DIR)
    installed_skills = get_installed_skills()
except Exception:
    installed_plugins = []
    installed_skills = []
print(json.dumps({
    'task_type': sys.argv[1],
    'installed_plugins': installed_plugins,
    'installed_skills': installed_skills
}))
" "$TASK_TYPE" "$SKILL_ROUTER_DIR" > "$RANK_TMP" 2>/dev/null || python3 -c "import json,sys; print(json.dumps({'task_type':sys.argv[1],'installed_plugins':[],'installed_skills':[]}))" "$TASK_TYPE" > "$RANK_TMP"
    RANK_HTTP=$(curl -s -w "\n%{http_code}" \
        -X POST "$DISPATCH_ENDPOINT/rank" \
        -H "Authorization: Bearer $DISPATCH_TOKEN" \
        -H "Content-Type: application/json" \
        --data @"$RANK_TMP" \
        --max-time 5 2>/dev/null || echo '{"installed":[],"suggested":[]}
200')
    rm -f "$RANK_TMP"
    RANK_BODY=$(echo "$RANK_HTTP" | head -n -1)
    RANK_CODE=$(echo "$RANK_HTTP" | tail -n 1)
    if [ "$RANK_CODE" = "200" ]; then
        RECOMMENDATIONS="$RANK_BODY"
    else
        # Server rank failed — fall back to local BYOK ranking
        RECOMMENDATIONS=$(python3 -c "
import sys, json
sys.path.insert(0, '$SKILL_ROUTER_DIR')
from evaluator import build_recommendation_list
print(json.dumps(build_recommendation_list(sys.argv[1])))
" "$TASK_TYPE" 2>/dev/null || echo '{"installed":[],"suggested":[]}')
    fi
else
    # ── BYOK rank ──────────────────────────────────────────────────────────
    RECOMMENDATIONS=$(python3 -c "
import sys, json
sys.path.insert(0, '$SKILL_ROUTER_DIR')
from evaluator import build_recommendation_list
task_type = sys.argv[1]
print(json.dumps(build_recommendation_list(task_type)))
" "$TASK_TYPE" 2>/dev/null || echo '{"installed":[],"suggested":[]}')
fi

# Render and prompt
python3 - "$TASK_TYPE" "$RECOMMENDATIONS" <<'PYEOF'
import json, sys

def p(msg=""):
    print(msg, file=sys.stderr, flush=True)

task_type = sys.argv[1]
try:
    recs = json.loads(sys.argv[2])
except Exception:
    recs = {"installed": [], "suggested": []}

installed = recs.get("installed", [])
suggested = recs.get("suggested", [])

if not installed and not suggested:
    W2 = 52
    print(f"\n{'━' * W2}", file=sys.stderr, flush=True)
    print(f" \033[94m◎\033[0m Dispatch  →  {task_type.replace('-', ' ').title()} task detected", file=sys.stderr, flush=True)
    print(f" No skills found for this task type.", file=sys.stderr, flush=True)
    print(f"{'━' * W2}", file=sys.stderr, flush=True)
    sys.exit(0)

W = 52
bar = "━" * W
p(f"\n{bar}")
p(f" \033[94m◎\033[0m Dispatch  →  {task_type.replace('-', ' ').title()} task detected")
p(bar)

if installed:
    p(" RECOMMENDED (installed):")
    for plug in installed:
        marketplace = plug.get('marketplace', '')
        label = f"   + {plug['name']}  (via {marketplace})" if marketplace else f"   + {plug['name']}"
        p(label)
        reason = plug.get('reason', '')
        if reason:
            p(f"     {reason}")

if suggested:
    p("\n SUGGESTED (not installed):")
    for s in suggested:
        p(f"   ↓ {s['name']}")
        reason = s.get('reason', '')
        if reason:
            p(f"     {reason}")
        cmd = s.get('install_cmd', '')
        if cmd:
            p(f"     → {cmd}")

p(f"\n [Enter] or wait 3s to proceed")
p(bar)
PYEOF

# Only pause when there are recommendations — no point waiting for a no-results notice
HAS_RECS=$(python3 -c "
import json, sys
try:
    r = json.loads(sys.argv[1])
    print('yes' if r.get('installed') or r.get('suggested') else 'no')
except:
    print('no')
" "$RECOMMENDATIONS" 2>/dev/null || echo "no")
if [ "$HAS_RECS" = "yes" ]; then
    read -r -t 3 < /dev/tty 2>/dev/null || true
fi

# ── Update state ───────────────────────────────────────────────────────────
python3 -c "
import json, sys
from datetime import datetime
state_file, task_type = sys.argv[1], sys.argv[2]
try:
    d = json.load(open(state_file))
except Exception:
    d = {}
d['last_task_type'] = task_type
d['last_updated'] = datetime.now().isoformat()
with open(state_file, 'w') as f:
    json.dump(d, f)
" "$STATE_FILE" "$TASK_TYPE" 2>/dev/null || true

exit 0
