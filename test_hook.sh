#!/bin/bash
# =============================================================================
# Dispatch Hook Test Harness
# Tests all 4 scenarios without needing a new CC session.
# Runs dispatch.sh directly with crafted inputs.
#
# Usage: bash test_hook.sh [1|2|3|4|all]
# =============================================================================

set -euo pipefail

HOOK="$HOME/.claude/hooks/skill-router.sh"
STATE="$HOME/.claude/skill-router/state.json"
STATE_BACKUP="$STATE.bak"
TRANSCRIPT_TMP=$(mktemp /tmp/dispatch-test-transcript.XXXX.jsonl)
trap 'rm -f "$TRANSCRIPT_TMP" "$STATE_BACKUP" 2>/dev/null' EXIT

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
NC='\033[0m'

pass() { echo -e "${GREEN}PASS${NC} $1"; }
fail() { echo -e "${RED}FAIL${NC} $1"; }
info() { echo -e "${CYAN}----${NC} $1"; }
header() { echo -e "\n${YELLOW}=== Scenario $1 ===${NC}"; }

# ── Save and restore state around each test ──────────────────────────────────
save_state()    { cp "$STATE" "$STATE_BACKUP" 2>/dev/null || true; }
restore_state() { cp "$STATE_BACKUP" "$STATE" 2>/dev/null || true; }

set_state() {
    local last_task="$1" cooldown="$2"
    python3 -c "
import json
try:
    d = json.load(open('$STATE'))
except Exception:
    d = {}
d['last_task_type'] = '$last_task'
d['limit_cooldown'] = $cooldown
d['auth_invalid_cooldown'] = 0
json.dump(d, open('$STATE', 'w'))
"
}

# ── Build a CC-format transcript JSONL ───────────────────────────────────────
make_transcript() {
    # Args: prior_msg new_msg
    local prior="$1" new_msg="$2"
    rm -f "$TRANSCRIPT_TMP"
    python3 -c "
import json
entries = [
    {'type': 'user', 'message': {'role': 'user', 'content': '$prior'}, 'uuid': 'aaa'},
    {'type': 'assistant', 'message': {'role': 'assistant', 'content': 'Sure, working on it.'}, 'uuid': 'bbb'},
    {'type': 'user', 'message': {'role': 'user', 'content': '$new_msg'}, 'uuid': 'ccc'},
]
with open('$TRANSCRIPT_TMP', 'w') as f:
    for e in entries:
        f.write(json.dumps(e) + '\n')
"
}

# ── Run the hook, capture stderr (the UI output) ──────────────────────────────
run_hook() {
    local transcript="$1"
    local hook_input
    hook_input=$(python3 -c "import json; print(json.dumps({'transcript_path': '$transcript', 'cwd': '/home/visionairy/Dispatch'}))")
    bash "$HOOK" <<< "$hook_input" 2>&1 || true
}

# =============================================================================
# SCENARIO 1: No shift — same topic continued
# Expected: no Dispatch output at all (silent exit 0)
# =============================================================================
run_scenario_1() {
    header "1: No shift (same topic)"
    info "state: last_task_type=flutter | message continues flutter work"
    save_state
    set_state "flutter" 0
    make_transcript \
        "fix the ListView overflow in my Flutter widget" \
        "also make the AppBar title bold"
    OUTPUT=$(run_hook "$TRANSCRIPT_TMP")
    restore_state

    if [ -z "$OUTPUT" ]; then
        pass "Silent exit — no output shown (correct)"
    else
        fail "Expected no output, got: $OUTPUT"
    fi
}

# =============================================================================
# SCENARIO 2: Shift detected — recommendations shown
# Expected: Dispatch UI with task header + installed/suggested skills
# (uses BYOK mode by temporarily removing token; requires ANTHROPIC_API_KEY)
# =============================================================================
run_scenario_2() {
    header "2: Shift detected — recommendations shown"
    info "state: last_task_type=flutter | message shifts to stripe"
    info "mode: BYOK (tests client classifier with real API call)"

    if [ -z "${ANTHROPIC_API_KEY:-}" ]; then
        echo -e "${YELLOW}SKIP${NC} ANTHROPIC_API_KEY not set — cannot run BYOK classification"
        return
    fi

    # Temporarily remove token to force BYOK mode
    local CONFIG="$HOME/.claude/skill-router/config.json"
    local CONFIG_BAK="$CONFIG.bak"
    cp "$CONFIG" "$CONFIG_BAK"
    python3 -c "
import json
d = json.load(open('$CONFIG'))
d['token'] = ''
json.dump(d, open('$CONFIG', 'w'))
"
    save_state
    set_state "flutter" 0
    make_transcript \
        "fix the ListView overflow in my Flutter widget" \
        "set up a Stripe webhook endpoint and verify the signature"

    OUTPUT=$(run_hook "$TRANSCRIPT_TMP")
    restore_state
    cp "$CONFIG_BAK" "$CONFIG"
    rm -f "$CONFIG_BAK"

    if echo "$OUTPUT" | grep -q "Dispatch"; then
        pass "Dispatch UI shown"
        echo "$OUTPUT"
    elif echo "$OUTPUT" | grep -q "shift"; then
        pass "Shift detected (no skills found for task type)"
        echo "$OUTPUT"
    else
        fail "No Dispatch output — classifier may have returned no-shift"
        echo "Got: $OUTPUT"
    fi
}

# =============================================================================
# SCENARIO 3: 402 limit notice shown (quota exhausted, cooldown=0)
# Expected: "You've used your 5 free detections today" upgrade notice
# Requires: hosted token set AND server quota currently exhausted
# =============================================================================
run_scenario_3() {
    header "3: 402 limit notice (quota exhausted, cooldown=0)"
    info "state: last_task_type=flutter, limit_cooldown=0 | shift message"
    info "requires: hosted token + exhausted server quota"
    save_state
    set_state "flutter" 0
    make_transcript \
        "fix the ListView overflow in my Flutter widget" \
        "set up a Stripe webhook endpoint and verify the signature"

    OUTPUT=$(run_hook "$TRANSCRIPT_TMP")
    restore_state

    if echo "$OUTPUT" | grep -q "free detections"; then
        pass "402 notice shown with upgrade URL"
        echo "$OUTPUT"
    elif echo "$OUTPUT" | grep -q "Dispatch"; then
        info "Quota not exhausted — got normal recommendations instead (quota available)"
        echo "$OUTPUT"
    elif [ -z "$OUTPUT" ]; then
        fail "No output — limit_cooldown may have been > 0 at test time, or no shift detected"
    else
        info "Got: $OUTPUT"
    fi
}

# =============================================================================
# SCENARIO 4: 402 silently suppressed (cooldown > 0)
# Expected: no output (silent exit)
# =============================================================================
run_scenario_4() {
    header "4: 402 silently suppressed (cooldown=3)"
    info "state: last_task_type=flutter, limit_cooldown=3 | shift message"
    save_state
    set_state "flutter" 3
    make_transcript \
        "fix the ListView overflow in my Flutter widget" \
        "set up a Stripe webhook endpoint and verify the signature"

    OUTPUT=$(run_hook "$TRANSCRIPT_TMP")
    # Check cooldown decremented
    NEW_COOLDOWN=$(python3 -c "import json; print(json.load(open('$STATE')).get('limit_cooldown', '?'))")
    restore_state

    if [ -z "$OUTPUT" ]; then
        pass "Silent exit — no output shown (correct)"
        if [ "$NEW_COOLDOWN" = "2" ]; then
            pass "limit_cooldown decremented: 3 → 2"
        else
            fail "limit_cooldown should be 2, got: $NEW_COOLDOWN"
        fi
    else
        fail "Expected silent exit, got output: $OUTPUT"
    fi
}

# =============================================================================
# Main
# =============================================================================
SCENARIO="${1:-all}"

case "$SCENARIO" in
    1) run_scenario_1 ;;
    2) run_scenario_2 ;;
    3) run_scenario_3 ;;
    4) run_scenario_4 ;;
    all)
        run_scenario_1
        run_scenario_2
        run_scenario_3
        run_scenario_4
        echo ""
        info "Done. For end-to-end testing, start a new CC session after syncing."
        ;;
    *)
        echo "Usage: bash test_hook.sh [1|2|3|4|all]"
        exit 1
        ;;
esac
