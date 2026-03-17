#!/bin/bash
# =============================================================================
# Dispatch — Skill Router Hook (UserPromptSubmit)
#
# Hosted mode:  token in config.json → calls dispatch.visionairy.biz
# BYOK mode:    ANTHROPIC_API_KEY set → calls Haiku directly (no token needed)
#
# Stage 1: Topic shift detection (~100ms, every message)
# Stage 2: Store task context for PreToolUse hook (only on confirmed shift)
# =============================================================================

set -uo pipefail

read -r -t 5 HOOK_INPUT || true
SKILL_ROUTER_DIR="${HOME}/.claude/dispatch"
STATE_FILE="$SKILL_ROUTER_DIR/state.json"
CONFIG_FILE="$SKILL_ROUTER_DIR/config.json"

# Ensure tmpfiles are always cleaned up on exit
CLASSIFY_TMP=""
trap 'rm -f "${CLASSIFY_TMP:-}" 2>/dev/null' EXIT

# Extract current prompt from hook JSON — avoids transcript timing lag (CC writes
# the current message to transcript AFTER the hook fires, not before)
CURRENT_PROMPT=$(python3 -c "import json,sys; d=json.loads(sys.argv[1]); print(d.get('prompt',''))" "$HOOK_INPUT" 2>/dev/null || echo "")
# Skip short follow-ups immediately, before any API calls ("Tool loaded.", "ok", "yes", etc.)
CURRENT_WORD_COUNT=$(echo "$CURRENT_PROMPT" | wc -w)
[ "${CURRENT_WORD_COUNT:-0}" -lt 3 ] && exit 0

# Brand icon: blue ◎ (U+25CE) via ANSI — radar sweep target in terminal
DICON=$'\033[94m◎\033[0m'

# notify MSG — write to /dev/tty if available, else stdout (CC injects into context)
notify() {
    if [ -w /dev/tty ] 2>/dev/null; then
        printf '%s\n' "$1" > /dev/tty 2>/dev/null || printf '%s\n' "$1"
    else
        printf '%s\n' "$1"
    fi
}

# ── First-run confirmation (one-time) ─────────────────────────────────────
# Outputs to stdout on first message after install so Claude confirms Dispatch is active.
# CC injects stdout into context — Claude will mention it in its response naturally.
FIRST_RUN=$(python3 -c "
import json
try:
    d = json.load(open('$STATE_FILE'))
    print('yes' if d.get('first_run') else 'no')
except:
    print('no')
" 2>/dev/null || echo "no")

if [ "$FIRST_RUN" = "yes" ]; then
    python3 -c "
import json, os, tempfile
state_file = '$STATE_FILE'
try:
    d = json.load(open(state_file))
except:
    d = {}
d['first_run'] = False
dir_ = os.path.dirname(os.path.abspath(state_file))
fd, tmp = tempfile.mkstemp(dir=dir_)
try:
    with os.fdopen(fd, 'w') as f: json.dump(d, f)
    os.rename(tmp, state_file)
except Exception:
    try: os.unlink(tmp)
    except: pass
" 2>/dev/null || true
    echo "[Dispatch is active. When you start a new type of task, it will recommend the best available plugins, skills, and MCPs — right here in context, grouped by type. Not sure which to pick? Just ask.]"
fi

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

# ── Resolve API key (BYOK fallback) ───────────────────────────────────────
export ANTHROPIC_API_KEY="${ANTHROPIC_API_KEY:-}"

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
prompt = sys.argv[4] if len(sys.argv) > 4 else ''
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
print(json.dumps({'transcript': transcript, 'cwd': cwd, 'last_task_type': last_task_type, 'prompt': prompt}))
" "$TRANSCRIPT_PATH" "$CWD" "$LAST_TASK_TYPE" "$CURRENT_PROMPT" 2>/dev/null || echo '{}')

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

    HTTP_BODY=$(echo "$HTTP_RESPONSE" | sed '$d')
    HTTP_CODE=$(echo "$HTTP_RESPONSE" | tail -n 1)

    # Validate HTTP_CODE is a 3-digit number; treat anything else as a curl failure
    if ! echo "$HTTP_CODE" | grep -qE '^[0-9]{3}$'; then
        HTTP_CODE="000"
    fi

    # Handle limit reached (402)
    if [ "$HTTP_CODE" = "402" ]; then
        # Suppress notice for 5 triggers after first display
        if [ "$LIMIT_COOLDOWN" -gt 0 ]; then
            python3 -c "
import json, sys, os, tempfile
from datetime import datetime
state_file, task_type = sys.argv[1], sys.argv[2]
try:
    d = json.load(open(state_file))
except Exception:
    d = {}
d['limit_cooldown'] = max(0, int(d.get('limit_cooldown', 1)) - 1)
d['last_task_type'] = task_type
d['last_updated'] = datetime.now().isoformat()
dir_ = os.path.dirname(os.path.abspath(state_file))
fd, tmp = tempfile.mkstemp(dir=dir_)
try:
    with os.fdopen(fd, 'w') as f: json.dump(d, f)
    os.rename(tmp, state_file)
except Exception:
    try: os.unlink(tmp)
    except: pass
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
        SEP=$(printf '━%.0s' $(seq 1 $W))
        notify "
$SEP
 ${DICON} Dispatch  →  Task shift detected
$SEP
 You've used your 8 free detections today.
 Upgrade for unlimited + Sonnet ranking — \$10/month → $UPGRADE_URL
$SEP"
        # Set cooldown: suppress for next 5 triggers
        python3 -c "
import json, sys, os, tempfile
from datetime import datetime
state_file, task_type = sys.argv[1], sys.argv[2]
try:
    d = json.load(open(state_file))
except Exception:
    d = {}
d['limit_cooldown'] = 5
d['last_task_type'] = task_type
d['last_updated'] = datetime.now().isoformat()
dir_ = os.path.dirname(os.path.abspath(state_file))
fd, tmp = tempfile.mkstemp(dir=dir_)
try:
    with os.fdopen(fd, 'w') as f: json.dump(d, f)
    os.rename(tmp, state_file)
except Exception:
    try: os.unlink(tmp)
    except: pass
" "$STATE_FILE" "${LAST_TASK_TYPE:-}" 2>/dev/null || true
        exit 0
    fi

    # Handle invalid/expired token (401)
    if [ "$HTTP_CODE" = "401" ]; then
        if [ "$AUTH_COOLDOWN" -gt 0 ]; then
            python3 -c "
import json, sys, os, tempfile
from datetime import datetime
state_file = sys.argv[1]
try:
    d = json.load(open(state_file))
except Exception:
    d = {}
d['auth_invalid_cooldown'] = max(0, int(d.get('auth_invalid_cooldown', 1)) - 1)
d['last_updated'] = datetime.now().isoformat()
dir_ = os.path.dirname(os.path.abspath(state_file))
fd, tmp = tempfile.mkstemp(dir=dir_)
try:
    with os.fdopen(fd, 'w') as f: json.dump(d, f)
    os.rename(tmp, state_file)
except Exception:
    try: os.unlink(tmp)
    except: pass
" "$STATE_FILE" 2>/dev/null || true
            exit 0
        fi
        W=52
        SEP=$(printf '━%.0s' $(seq 1 $W))
        notify "
$SEP
 ${DICON} Dispatch  →  Token invalid or expired
 Re-authenticate: $DISPATCH_ENDPOINT/token-lookup
$SEP"
        python3 -c "
import json, sys, os, tempfile
from datetime import datetime
state_file = sys.argv[1]
try:
    d = json.load(open(state_file))
except Exception:
    d = {}
d['auth_invalid_cooldown'] = 5
d['last_updated'] = datetime.now().isoformat()
dir_ = os.path.dirname(os.path.abspath(state_file))
fd, tmp = tempfile.mkstemp(dir=dir_)
try:
    with os.fdopen(fd, 'w') as f: json.dump(d, f)
    os.rename(tmp, state_file)
except Exception:
    try: os.unlink(tmp)
    except: pass
" "$STATE_FILE" 2>/dev/null || true
        exit 0
    fi

    # Any other non-200 (403, 500, HTML error pages, etc.) — fall through to BYOK
    if [ "$HTTP_CODE" != "200" ] && [ "$HTTP_CODE" != "000" ]; then
        CLASSIFICATION=""
    else
        CLASSIFICATION="$HTTP_BODY"
    fi
else
    # ── BYOK mode ─────────────────────────────────────────────────────────
    CLASSIFICATION=$(python3 "$SKILL_ROUTER_DIR/classifier.py" \
        --transcript "$TRANSCRIPT_PATH" \
        --cwd "$CWD" \
        --last-task-type "$LAST_TASK_TYPE" \
        --prompt "$CURRENT_PROMPT" \
        2>/dev/null || echo '{"shift":false,"domain":"general","mode":"building","task_type":"general-building","confidence":0}')
fi

# Hosted returned non-200 — fall back to BYOK if API key is available
if [ -z "$CLASSIFICATION" ] && [ -n "$ANTHROPIC_API_KEY" ]; then
    CLASSIFICATION=$(python3 "$SKILL_ROUTER_DIR/classifier.py" \
        --transcript "$TRANSCRIPT_PATH" \
        --cwd "$CWD" \
        --last-task-type "$LAST_TASK_TYPE" \
        --prompt "$CURRENT_PROMPT" \
        2>/dev/null || echo '{"shift":false,"domain":"general","mode":"building","task_type":"general-building","confidence":0}')
fi

# If still empty (no API key, no valid hosted response) — exit silently
[ -z "$CLASSIFICATION" ] && exit 0

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

# ── Map task type to category ─────────────────────────────────────────────
CATEGORY=$(python3 -c "
import sys
sys.path.insert(0, sys.argv[1])
from category_mapper import map_to_category
result = map_to_category(sys.argv[2])
print(result if result else 'unknown')
" "$SKILL_ROUTER_DIR" "$TASK_TYPE" 2>/dev/null || echo "unknown")

# Log unknown categories for future catalog expansion
if [ "$CATEGORY" = "unknown" ]; then
    python3 -c "
import sys
sys.path.insert(0, sys.argv[1])
from category_mapper import log_unknown_category
log_unknown_category(sys.argv[2])
" "$SKILL_ROUTER_DIR" "$TASK_TYPE" 2>/dev/null || true
fi

# ── Read last recommended category (once-per-category-per-session gate) ──
LAST_RECOMMENDED_CATEGORY=$(python3 -c "
import sys
sys.path.insert(0, sys.argv[1])
from interceptor import get_last_recommended_category
print(get_last_recommended_category())
" "$SKILL_ROUTER_DIR" 2>/dev/null || echo "")

# ── Extract preferred tool type hint from classifier ──────────────────────
PREFERRED_TOOL_TYPE=$(python3 -c "
import json, sys
print(json.loads(sys.argv[1]).get('preferred_tool_type', '') or '')
" "$CLASSIFICATION" 2>/dev/null || echo "")

# ── Read previous cwd before state write (for rescan check) ──────────────
PREV_CWD=$(python3 -c "
import json
try:
    d = json.load(open('$STATE_FILE'))
    print(d.get('last_cwd', ''))
except:
    print('')
" 2>/dev/null || echo "")

# ── Stage 2: Store state for PreToolUse hook ───────────────────────────────
# Extract last 3 user messages to build context snippet for preuse_hook.sh
CONTEXT_SNIPPET=$(python3 -c "
import json, sys, os
sys.path.insert(0, sys.argv[1])
try:
    from classifier import extract_recent_messages
    transcript_path = sys.argv[2]
    transcript = []
    if transcript_path and os.path.exists(transcript_path):
        with open(transcript_path) as f:
            for line in f:
                line = line.strip()
                if line:
                    try: transcript.append(json.loads(line))
                    except: pass
    recent = extract_recent_messages(transcript, n=3)
except Exception:
    recent = []
current = sys.argv[3] if len(sys.argv) > 3 else ''
if current:
    recent.append(current)
    recent = recent[-3:]
print(' | '.join(recent))
" "$SKILL_ROUTER_DIR" "$TRANSCRIPT_PATH" "$CURRENT_PROMPT" 2>/dev/null || echo "$CURRENT_PROMPT")

# Write task_type + context + cwd to state — preuse_hook.sh reads these
python3 -c "
import json, sys, os, tempfile
from datetime import datetime
state_file, task_type, category, context_snippet, cwd = sys.argv[1], sys.argv[2], sys.argv[3], sys.argv[4], sys.argv[5]
try:
    d = json.load(open(state_file))
except Exception:
    d = {}
d['last_task_type'] = task_type
d['last_category'] = category
d['last_context_snippet'] = context_snippet
d['last_cwd'] = cwd
d['last_updated'] = datetime.now().isoformat()
dir_ = os.path.dirname(os.path.abspath(state_file))
fd, tmp = tempfile.mkstemp(dir=dir_)
try:
    with os.fdopen(fd, 'w') as f: json.dump(d, f)
    os.rename(tmp, state_file)
except Exception:
    try: os.unlink(tmp)
    except: pass
" "$STATE_FILE" "$TASK_TYPE" "$CATEGORY" "$CONTEXT_SNIPPET" "$CWD" 2>/dev/null || true

# ── Trigger stack rescan if cwd changed ──────────────────────────────────
if [ "$CWD" != "$PREV_CWD" ]; then
    python3 -c "
import sys
sys.path.insert(0, sys.argv[1])
from stack_scanner import scan_and_save
scan_and_save(sys.argv[2])
" "$SKILL_ROUTER_DIR" "$CWD" 2>/dev/null || true
fi

# ── Stage 3: Proactive recommendations ────────────────────────────────────
# Fires only when category changes (once-per-category-per-session).
# Outputs grouped recommendations to stdout — CC injects before response.
if [ "$CATEGORY" != "unknown" ] && [ "$CATEGORY" != "$LAST_RECOMMENDED_CATEGORY" ]; then
    STAGE3_OUTPUT=$(python3 -c "
import sys, json, signal
sys.path.insert(0, sys.argv[1])

task_type       = sys.argv[2]
category_id     = sys.argv[3]
context_snippet = sys.argv[4]
preferred_type  = sys.argv[5] if len(sys.argv) > 5 else ''

def _timeout_handler(signum, frame):
    raise TimeoutError('stage3 timeout')

signal.signal(signal.SIGALRM, _timeout_handler)
signal.alarm(4)

try:
    from evaluator import recommend_tools

    stack_profile = {}
    try:
        from interceptor import STATE_FILE
        cwd = json.load(open(STATE_FILE)).get('last_cwd', '')
        if cwd:
            from stack_scanner import get_stack_profile
            stack_profile = get_stack_profile(cwd) or {}
    except Exception:
        pass

    result = recommend_tools(
        task_type=task_type,
        context_snippet=context_snippet,
        category_id=category_id,
        stack_profile=stack_profile,
        preferred_type=preferred_type or None,
    )

    signal.alarm(0)

    by_type = result.get('by_type', {})
    plugins = by_type.get('plugin', [])
    skills  = by_type.get('skill', [])
    mcps    = by_type.get('mcp', [])

    # Only output if at least one section has results
    if not plugins and not skills and not mcps:
        print('')
        sys.exit(0)

    def fmt_tool(t):
        name = t.get('name', '')
        reason = (t.get('reason', '') or '').rstrip('.')
        install_cmd = t.get('install_cmd', '')
        # Display name: strip prefixes for readability
        if name.startswith('plugin:anthropic:'):
            display = name[len('plugin:anthropic:'):]
        elif name.startswith('plugin:'):
            display = name[7:]
        elif name.startswith('mcp:'):
            display = name[4:]
        else:
            display = name
        lines = [f'  \u2022 {display} \u2014 {reason}.']
        if install_cmd:
            lines.append(f'    Install: {install_cmd}')
        return '\n'.join(lines)

    sections = []
    sections.append(f'[Dispatch] Recommended tools for this {task_type} task:')

    if plugins:
        sections.append('')
        sections.append('Plugins:')
        for t in plugins:
            sections.append(fmt_tool(t))

    if skills:
        sections.append('')
        sections.append('Skills:')
        for t in skills:
            sections.append(fmt_tool(t))

    if mcps:
        sections.append('')
        sections.append('MCPs:')
        for t in mcps:
            sections.append(fmt_tool(t))

    sections.append('')
    sections.append('Not sure which to pick? Ask me \u2014 I can explain the differences.')

    print('\n'.join(sections))

except TimeoutError:
    print('')
except Exception:
    print('')
" "$SKILL_ROUTER_DIR" "$TASK_TYPE" "$CATEGORY" "$CONTEXT_SNIPPET" "$PREFERRED_TOOL_TYPE" 2>/dev/null || echo "")

    if [ -n "$STAGE3_OUTPUT" ] && [ "$STAGE3_OUTPUT" != "" ]; then
        echo "$STAGE3_OUTPUT"
        python3 -c "
import sys
sys.path.insert(0, sys.argv[1])
from interceptor import write_last_recommended_category
write_last_recommended_category(sys.argv[2])
" "$SKILL_ROUTER_DIR" "$CATEGORY" 2>/dev/null || true
    fi
fi

exit 0
