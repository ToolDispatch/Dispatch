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

# Intentionally no set -e or set -o pipefail — hook must never crash and block Claude.
# All individual commands have || fallbacks. Safety net catches any unhandled exit.
trap 'exit 0' ERR

# Provenance logging function
log_decision() {
    local decision="${1:-}"
    local confidence="${2:-}"
    local rules="${3:-}"
    echo "[PROVENANCE] $(date -Iseconds) preuse_hook.sh: $decision (confidence=$confidence, rules=$rules)" >&2
}

log_decision "Hook initialization" 0.95 "script-start"

read -r -t 5 HOOK_INPUT || true
SKILL_ROUTER_DIR="${HOME}/.claude/dispatch"
CONFIG_FILE="$SKILL_ROUTER_DIR/config.json"

THRESHOLD=10   # minimum score gap above cc_score to block

# ── Parse tool_name ────────────────────────────────────────────────────────
TOOL_NAME=$(python3 -c "
import json, sys
d = json.loads(sys.argv[1])
print(d.get('tool_name', ''))
" "$HOOK_INPUT" 2>/dev/null || echo "")

[ -z "$TOOL_NAME" ] && exit 0

# ── Extract session_id for counter tracking ────────────────────────────────
SESSION_ID=$(python3 -c "
import json, sys
d = json.loads(sys.argv[1])
print(d.get('session_id', ''))
" "$HOOK_INPUT" 2>/dev/null || echo "")

# ── Derive CC_TOOL_TYPE early — needed by bypass logging path ─────────────
# Must happen before bypass check (line ~54) which logs it to /api/detections.
CC_TOOL_TYPE=$(python3 -c "
import json, sys
sys.path.insert(0, sys.argv[1])
from interceptor import get_cc_tool_type
d = json.loads(sys.argv[2])
print(get_cc_tool_type(d.get('tool_name', '')))
" "$SKILL_ROUTER_DIR" "$HOOK_INPUT" 2>/dev/null || echo "skill")

# ── Should we intercept this tool? ────────────────────────────────────────
SHOULD_INTERCEPT=$(python3 -c "
import sys
sys.path.insert(0, sys.argv[1])
from interceptor import should_intercept
print('yes' if should_intercept(sys.argv[2]) else 'no')
" "$SKILL_ROUTER_DIR" "$TOOL_NAME" 2>/dev/null || echo "no")

[ "$SHOULD_INTERCEPT" != "yes" ] && exit 0

# ── Increment session audit counter ───────────────────────────────────────
if [ -n "$SESSION_ID" ]; then
    python3 -c "
import sys
sys.path.insert(0, sys.argv[1])
from interceptor import increment_session_counter
increment_session_counter('session_audits', sys.argv[2])
" "$SKILL_ROUTER_DIR" "$SESSION_ID" 2>/dev/null || true
fi

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

if [ "$HAS_BYPASS" = "yes" ]; then
    # Log bypass event (user said 'proceed') — fire-and-forget
    BY_TOKEN=$(python3 -c "
import json
try:
    d = json.load(open('$CONFIG_FILE'))
    print(d.get('token', ''))
except:
    print('')
" 2>/dev/null || echo "")
    if [ -n "$BY_TOKEN" ]; then
        BY_ENDPOINT=$(python3 -c "
import json
try:
    d = json.load(open('$CONFIG_FILE'))
    print(d.get('endpoint', 'https://dispatch.visionairy.biz'))
except:
    print('https://dispatch.visionairy.biz')
" 2>/dev/null || echo "https://dispatch.visionairy.biz")
        BY_TASK=$(python3 -c "
import sys
sys.path.insert(0, sys.argv[1])
from interceptor import get_task_type
print(get_task_type())
" "$SKILL_ROUTER_DIR" 2>/dev/null || echo "")
        BY_CAT=$(python3 -c "
import sys
sys.path.insert(0, sys.argv[1])
from interceptor import get_category
print(get_category())
" "$SKILL_ROUTER_DIR" 2>/dev/null || echo "unknown")
        BY_BODY=$(python3 -c "
import json, sys
print(json.dumps({
    'task_type': sys.argv[1],
    'category_id': sys.argv[2],
    'tool_suggested': sys.argv[3],
    'was_blocked': False,
    'was_bypassed': True,
    'cc_tool_type': sys.argv[4],
}))
" "$BY_TASK" "$BY_CAT" "$TOOL_NAME" "${CC_TOOL_TYPE:-}" 2>/dev/null || echo "{}")
        curl -s -X POST "$BY_ENDPOINT/api/detections" \
            -H "Authorization: Bearer $BY_TOKEN" \
            -H "Content-Type: application/json" \
            --data "$BY_BODY" \
            --max-time 2 >/dev/null 2>&1 &
    fi
    exit 0
fi

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

export ANTHROPIC_API_KEY="${ANTHROPIC_API_KEY:-}"

if [ -z "$DISPATCH_TOKEN" ] && [ -z "$ANTHROPIC_API_KEY" ]; then
    exit 0
fi

# ── Extract cc_tool label and type from tool input ────────────────────────
CC_TOOL=$(python3 -c "
import json, sys
sys.path.insert(0, sys.argv[1])
from interceptor import extract_cc_tool
d = json.loads(sys.argv[2])
print(extract_cc_tool(d.get('tool_name', ''), d.get('tool_input', {})))
" "$SKILL_ROUTER_DIR" "$HOOK_INPUT" 2>/dev/null || echo "$TOOL_NAME")

# ── Persist cc_tool_type to state (conversion tracking + stage 3 hint) ───
python3 -c "
import sys
sys.path.insert(0, sys.argv[1])
from interceptor import write_last_cc_tool_type
write_last_cc_tool_type(sys.argv[2])
" "$SKILL_ROUTER_DIR" "$CC_TOOL_TYPE" 2>/dev/null || true

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

CWD_BASENAME=$(python3 -c "
import sys, json, os
try:
    d = json.load(open(sys.argv[1]))
    cwd = d.get('last_cwd', '')
    print(os.path.basename(cwd) if cwd else '')
except:
    print('')
" "$STATE_FILE" 2>/dev/null || echo "")

# ── Check conversion: did user install our last suggested tool? ────────────
if [ -n "$DISPATCH_TOKEN" ]; then
    CONVERTED=$(python3 -c "
import sys
sys.path.insert(0, sys.argv[1])
from interceptor import check_conversion, clear_last_suggested
if check_conversion([sys.argv[2]]):
    clear_last_suggested()
    print('yes')
else:
    print('no')
" "$SKILL_ROUTER_DIR" "$CC_TOOL" 2>/dev/null || echo "no")
    if [ "$CONVERTED" = "yes" ]; then
        CONV_BODY=$(python3 -c "
import json, sys
print(json.dumps({
    'task_type': sys.argv[1],
    'category_id': sys.argv[2],
    'tool_suggested': sys.argv[3],
    'was_blocked': False,
    'was_installed': True,
    'cc_tool_type': sys.argv[4],
}))
" "$TASK_TYPE" "$CATEGORY" "$CC_TOOL" "$CC_TOOL_TYPE" 2>/dev/null || echo "{}")
        curl -s -X POST "$DISPATCH_ENDPOINT/api/detections" \
            -H "Authorization: Bearer $DISPATCH_TOKEN" \
            -H "Content-Type: application/json" \
            --data "$CONV_BODY" \
            --max-time 2 >/dev/null 2>&1 &
    fi
fi

# ── Evaluate marketplace alternatives ─────────────────────────────────────
RANK_TMP=$(mktemp)
trap 'rm -f "${RANK_TMP:-}" 2>/dev/null' EXIT

if [ -n "$DISPATCH_TOKEN" ]; then
    # Hosted path
    python3 -c "
import json, sys
sys.path.insert(0, sys.argv[1])
from interceptor import STATE_FILE
try:
    import json as _j
    cwd = _j.load(open(STATE_FILE)).get('last_cwd', '')
except Exception:
    cwd = ''
stack_profile = {}
if cwd:
    try:
        from stack_scanner import load_stack_profile
        stack_profile = load_stack_profile() or {}
    except Exception:
        pass
print(json.dumps({
    'task_type': sys.argv[2],
    'context_snippet': sys.argv[3],
    'cc_tool': sys.argv[4],
    'category_id': sys.argv[5],
    'cc_tool_type': sys.argv[6],
    'stack_profile': stack_profile,
}))
" "$SKILL_ROUTER_DIR" "$TASK_TYPE" "$CONTEXT_SNIPPET" "$CC_TOOL" "$CATEGORY" "$CC_TOOL_TYPE" > "$RANK_TMP" 2>/dev/null

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
from interceptor import STATE_FILE
try:
    cwd = json.load(open(STATE_FILE)).get('last_cwd', '')
except Exception:
    cwd = ''
stack_profile = {}
if cwd:
    try:
        from stack_scanner import load_stack_profile
        stack_profile = load_stack_profile() or {}
    except Exception:
        pass
print(json.dumps(build_recommendation_list(sys.argv[1], context_snippet=sys.argv[2], cc_tool=sys.argv[4], category_id=sys.argv[5], cc_tool_type=sys.argv[6], stack_profile=stack_profile, cwd_basename=sys.argv[7])))
" "$TASK_TYPE" "$CONTEXT_SNIPPET" "$SKILL_ROUTER_DIR" "$CC_TOOL" "$CATEGORY" "$CC_TOOL_TYPE" "$CWD_BASENAME" 2>/dev/null || echo '{"all":[],"cc_score":0}')
    fi
else
    # BYOK path
    RECOMMENDATIONS=$(python3 -c "
import sys, json
sys.path.insert(0, sys.argv[3])
from evaluator import build_recommendation_list
from interceptor import STATE_FILE
try:
    cwd = json.load(open(STATE_FILE)).get('last_cwd', '')
except Exception:
    cwd = ''
stack_profile = {}
if cwd:
    try:
        from stack_scanner import load_stack_profile
        stack_profile = load_stack_profile() or {}
    except Exception:
        pass
print(json.dumps(build_recommendation_list(sys.argv[1], context_snippet=sys.argv[2], cc_tool=sys.argv[4], category_id=sys.argv[5], cc_tool_type=sys.argv[6], stack_profile=stack_profile, cwd_basename=sys.argv[7])))
" "$TASK_TYPE" "$CONTEXT_SNIPPET" "$SKILL_ROUTER_DIR" "$CC_TOOL" "$CATEGORY" "$CC_TOOL_TYPE" "$CWD_BASENAME" 2>/dev/null || echo '{"all":[],"cc_score":0}')
fi

# ── Check threshold: any marketplace tool beats CC by >= THRESHOLD? ────────
SHOULD_BLOCK=$(python3 -c "
import json, sys
try:
    r = json.loads(sys.argv[1])
    cc_score = int(r.get('cc_score', 0))
    threshold = int(sys.argv[2])
    max_weighted = int(r.get('max_weighted', 0))
    if max_weighted >= cc_score + threshold:
        print('yes')
    else:
        print('no')
except:
    print('no')
" "$RECOMMENDATIONS" "$THRESHOLD" 2>/dev/null || echo "no")

# ── Extract top tool name unconditionally (used for bypass + conversion tracking) ──
TOP_TOOL_NAME=$(python3 -c "
import json, sys
try:
    r = json.loads(sys.argv[1])
    tools = r.get('all', [])
    print(tools[0].get('name', '') if tools else '')
except:
    print('')
" "$RECOMMENDATIONS" 2>/dev/null || echo "")

# ── Log intercept event to hosted API (fire-and-forget, hosted mode only) ──
if [ -n "$DISPATCH_TOKEN" ]; then
    DETECTION_BODY=$(python3 -c "
import json, sys
try:
    r = json.loads(sys.argv[1])
    tools = r.get('all', [])
    top_score = int(r.get('max_weighted', 0))
    cc_score = int(r.get('cc_score', 0))
except:
    top_score = 0
    cc_score = 0
print(json.dumps({
    'task_type': sys.argv[2],
    'category_id': sys.argv[3],
    'tool_suggested': sys.argv[4],
    'was_blocked': sys.argv[5] == 'yes',
    'cc_score': cc_score,
    'top_pick_score': top_score,
    'cc_tool_type': sys.argv[6],
}))
" "$RECOMMENDATIONS" "$TASK_TYPE" "$CATEGORY" "$TOP_TOOL_NAME" "$SHOULD_BLOCK" "$CC_TOOL_TYPE" 2>/dev/null || echo "{}")
    curl -s -X POST "$DISPATCH_ENDPOINT/api/detections" \
        -H "Authorization: Bearer $DISPATCH_TOKEN" \
        -H "Content-Type: application/json" \
        --data "$DETECTION_BODY" \
        --max-time 2 >/dev/null 2>&1 &
fi

if [ "$SHOULD_BLOCK" != "yes" ]; then
    PASS_MSG="[Dispatch] ✓ ${CC_TOOL} — no better match"
    printf '%s\n' "$PASS_MSG" > /dev/tty 2>/dev/null || printf '%s\n' "$PASS_MSG" >&2
    exit 0
fi

# ── Write bypass token so 'proceed' re-attempt passes through ─────────────
python3 -c "
import sys
sys.path.insert(0, sys.argv[1])
from interceptor import write_bypass
write_bypass(sys.argv[2])
" "$SKILL_ROUTER_DIR" "$TOOL_NAME" 2>/dev/null || true

# ── Record last suggested tool for conversion tracking ────────────────────
python3 -c "
import sys
sys.path.insert(0, sys.argv[1])
from interceptor import write_last_suggested
write_last_suggested(sys.argv[2])
" "$SKILL_ROUTER_DIR" "$TOP_TOOL_NAME" 2>/dev/null || true

# ── Render comparison output — exit 2 blocks the tool call ────────────────
python3 - "$CC_TOOL" "$RECOMMENDATIONS" "$TASK_TYPE" "$CC_TOOL_TYPE" <<'PYEOF'
import json, sys

BLUE   = '\033[94m'
YELLOW = '\033[93m'
GRAY   = '\033[90m'
GREEN  = '\033[92m'
CYAN   = '\033[96m'
RESET  = '\033[0m'

cc_tool      = sys.argv[1]
cc_tool_type = sys.argv[4] if len(sys.argv) > 4 else "skill"
try:
    recs = json.loads(sys.argv[2])
except Exception:
    recs = {"skills": [], "mcps": [], "plugins": [], "all": [], "cc_score": 0}
task_type    = sys.argv[3]
task_display = task_type.replace("-", " ").title()

skills      = recs.get("skills", [])
mcps        = recs.get("mcps", [])
plugins     = recs.get("plugins", [])
cc_score    = recs.get("cc_score", 0)
caveat      = recs.get("caveat", "")

cc_type_label = {"mcp": "MCP server", "agent": "Agent", "skill": "Skill"}.get(cc_tool_type, "Skill")

OSC = chr(27) + "]8;;"
ST  = chr(27) + chr(92)

def link(display, href):
    if href:
        return f"{OSC}{href}{ST}{BLUE}{display}{RESET}{OSC}{ST}"
    return f"{BLUE}{display}{RESET}"

def display_name_linked(name, install_url):
    if name.startswith("mcp:"):
        dn = name[4:]
        return link(dn, install_url)
    if name.startswith("plugin:anthropic:"):
        dn = name[len("plugin:anthropic:"):]
        return link(dn, install_url)
    if name.startswith("plugin:"):
        parts = name.split(":", 2)
        dn = parts[2] if len(parts) > 2 else name
        return link(dn, install_url)
    if "@" in name and "/" in name:
        _, skill_name = name.rsplit("@", 1)
        url = install_url or f"https://github.com/{name.split('@')[0]}"
        return link(skill_name, url)
    return link(name, install_url)

def render_tool(tool, idx):
    name        = tool.get("name", "")
    rel         = tool.get("relevance", 0)
    sig         = tool.get("signal", 0)
    vel         = tool.get("velocity", 0)
    installs    = tool.get("installs", 0)
    stars       = tool.get("stars", 0)
    forks       = tool.get("forks", 0)
    install_cmd = (tool.get("install_cmd") or "").replace("\n", " ").strip()
    install_url = (tool.get("install_url") or "").replace("\n", " ").strip()
    no_desc     = tool.get("no_description", False)
    desc        = (tool.get("description") or "").strip()

    out = []
    linked = display_name_linked(name, install_url)
    out.append(f"  {idx}. {linked}")
    score_line = f"     {GRAY}Relevance {rel} · Signal {sig} · Velocity {vel}"
    score_line += f"  installs:{installs:,} stars:{stars:,} forks:{forks:,}{RESET}"
    out.append(score_line)
    if no_desc:
        out.append(f"     {YELLOW}⚠ no description — install at your own risk{RESET}")
    elif desc:
        out.append(f"     {GRAY}{desc[:120]}{RESET}")
    if install_cmd:
        out.append(f"     {GRAY}Install: {install_cmd} && claude{RESET}")
    return out

lines = [
    f"{BLUE}[Dispatch] Intercepted:{RESET} CC is about to use {YELLOW}'{cc_tool}'{RESET} ({cc_type_label}) for {task_display}.",
    f"{GRAY}CC confidence score: {cc_score}/100{RESET}",
    "",
]

if skills:
    lines.append(f"{CYAN}── Skills ──{RESET}")
    for i, t in enumerate(skills, 1):
        lines.extend(render_tool(t, i))
    lines.append("")

if mcps:
    lines.append(f"{CYAN}── MCP Servers ──{RESET}")
    for i, t in enumerate(mcps, 1):
        lines.extend(render_tool(t, i))
    lines.append("")

if plugins:
    lines.append(f"{CYAN}── Plugins ──{RESET}")
    for i, t in enumerate(plugins, 1):
        lines.extend(render_tool(t, i))
    lines.append("")

# Derive top pick for install hint from combined all list
all_tools = recs.get("all", [])
top_pick = all_tools[0] if all_tools else None

if top_pick:
    tp_name = top_pick.get("name", "")
    td = display_name(tp_name)
    if tp_name.startswith("mcp:"):
        install_hint = f"  2. Configure {td} — add it to .mcp.json, then restart CC"
    elif tp_name.startswith("plugin:"):
        install_hint = f"  2. Install {td} plugin — run /compact first, then install and restart CC"
    else:
        install_hint = f"  2. Install {td} — run /compact first, then install and restart CC"
else:
    install_hint = f"  2. Install a tool above — run /compact first, then install and restart CC"

lines.extend([
    f"{YELLOW}⚠ Marketplace tools score higher than '{cc_tool}' ({cc_type_label}) for this task.{RESET}",
    "  Options:",
    f"  1. Say {GREEN}'proceed'{RESET} to continue with '{cc_tool}' (one-time bypass, no restart needed)",
    install_hint,
    "  3. Ignore Dispatch for this task — say 'skip dispatch'",
    "",
])

if caveat:
    lines.append(f"{GRAY}Note: {caveat}{RESET}")
    lines.append("")

lines.append(f"{GRAY}Present these options to the user. Wait for their response before taking any action.{RESET}")

print("\n".join(lines))
PYEOF

# Increment session block counter
if [ -n "$SESSION_ID" ]; then
    python3 -c "
import sys
sys.path.insert(0, sys.argv[1])
from interceptor import increment_session_counter
increment_session_counter('session_blocks', sys.argv[2])
" "$SKILL_ROUTER_DIR" "$SESSION_ID" 2>/dev/null || true
fi

exit 2
