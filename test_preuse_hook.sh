#!/bin/bash
# =============================================================================
# Dispatch PreToolUse Hook Test Harness
#
# Mocks evaluator.py and state.json to exercise all intercept paths.
#
# Usage: bash test_preuse_hook.sh [1-5|all]
#
# Path matrix:
#   1  — Non-interceptable tool (Read) → pass-through (exit 0)
#   2  — Interceptable tool, no credentials → pass-through (exit 0)
#   3  — Bypass token active → pass-through + token consumed (exit 0)
#   4  — Above threshold (gap >= 10) → block (exit 2) + comparison output
#   5  — Below threshold (gap < 10) → pass-through (exit 0)
# =============================================================================

set -euo pipefail

HOOK="$HOME/.claude/hooks/preuse-hook.sh"
STATE="$HOME/.claude/skill-router/state.json"
CONFIG="$HOME/.claude/skill-router/config.json"
SKILL_DIR="$HOME/.claude/skill-router"

STATE_BAK="${STATE}.testbak"
CONFIG_BAK="${CONFIG}.testbak"
EVALUATOR_BAK="${SKILL_DIR}/evaluator.py.testbak"

PASS=0; FAIL=0
RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'; NC='\033[0m'
pass() { echo -e "${GREEN}PASS${NC}  $1"; ((PASS++)) || true; }
fail() { echo -e "${RED}FAIL${NC}  $1"; ((FAIL++)) || true; }
header() { echo -e "\n${YELLOW}=== Scenario $1 ===${NC}"; }

cleanup() {
    rm -f "$STATE_BAK" "$CONFIG_BAK" "$EVALUATOR_BAK" 2>/dev/null || true
    echo ""
    echo "Results: ${PASS} passed  ${FAIL} failed"
}
trap cleanup EXIT

# ── Helpers ──────────────────────────────────────────────────────────────────
save_state()    { cp "$STATE"  "$STATE_BAK"  2>/dev/null || echo '{}' > "$STATE_BAK"; }
restore_state() { cp "$STATE_BAK"  "$STATE"  2>/dev/null || true; }
save_config()   { cp "$CONFIG" "$CONFIG_BAK" 2>/dev/null || echo '{}' > "$CONFIG_BAK"; }
restore_config(){ cp "$CONFIG_BAK" "$CONFIG" 2>/dev/null || true; }
save_evaluator()    { cp "$SKILL_DIR/evaluator.py" "$EVALUATOR_BAK" 2>/dev/null || true; }
restore_evaluator() { cp "$EVALUATOR_BAK" "$SKILL_DIR/evaluator.py" 2>/dev/null || true; }

set_state() {
    # set_state task_type category
    python3 -c "
import json
try:
    d = json.load(open('$STATE'))
except Exception:
    d = {}
d.update({'last_task_type': '${1:-general}', 'last_category': '${2:-unknown}', 'last_context_snippet': 'test context'})
json.dump(d, open('$STATE', 'w'))
"
}

set_config() {
    local tok="${1:-}" ep="${2:-https://dispatch.visionairy.biz}"
    python3 -c "
import json
try:
    d = json.load(open('$CONFIG'))
except Exception:
    d = {}
d['token'] = '$tok'
d['endpoint'] = '$ep'
json.dump(d, open('$CONFIG', 'w'))
"
}

write_bypass() {
    # write a live bypass token for tool_name
    python3 -c "
import json, time
try:
    d = json.load(open('$STATE'))
except Exception:
    d = {}
d['bypass'] = {'tool_name': '${1:-Skill}', 'expires': time.time() + 120}
json.dump(d, open('$STATE', 'w'))
"
}

run_hook() {
    # run_hook tool_name tool_input_json [api_key]
    local _default_input='{"skill":"superpowers:brainstorming"}'
    local tool_name="${1:-Skill}"
    local tool_input="${2:-$_default_input}"
    local api_key="${3:-}"
    # Build hook_input directly — avoids bash $() closing on ) inside Python string
    local hook_input="{\"tool_name\":\"${tool_name}\",\"tool_input\":${tool_input},\"transcript_path\":\"\",\"cwd\":\"/tmp\"}"
    HOOK_EXIT=0
    OUTPUT=$(ANTHROPIC_API_KEY="$api_key" bash "$HOOK" <<< "$hook_input" 2>/dev/null) || HOOK_EXIT=$?
}

mock_above_threshold() {
    # evaluator returns cc_score=50, top tool score=80 (gap=30 >= threshold=10) → should block
    cat > "$SKILL_DIR/evaluator.py" << 'STUB'
import json
def build_recommendation_list(task_type, **kwargs):
    return {
        "all": [
            {"name": "stripe-mcp", "score": 80, "reason": "Native Stripe API coverage", "installed": False,
             "install_cmd": "npx @stripe/mcp", "install_url": "https://github.com/stripe/mcp"}
        ],
        "top_pick": {"name": "stripe-mcp", "score": 80, "reason": "Native Stripe API coverage"},
        "installed": [],
        "suggested": [{"name": "stripe-mcp", "score": 80}],
        "cc_score": 50
    }
STUB
}

mock_below_threshold() {
    # evaluator returns cc_score=70, top tool score=75 (gap=5 < threshold=10) → should pass through
    cat > "$SKILL_DIR/evaluator.py" << 'STUB'
import json
def build_recommendation_list(task_type, **kwargs):
    return {
        "all": [
            {"name": "stripe-mcp", "score": 75, "reason": "Native Stripe API coverage", "installed": False}
        ],
        "top_pick": {"name": "stripe-mcp", "score": 75},
        "installed": [],
        "suggested": [{"name": "stripe-mcp", "score": 75}],
        "cc_score": 70
    }
STUB
}

# =============================================================================
# SCENARIO 1: Non-interceptable tool → pass-through (exit 0)
# =============================================================================
run_scenario_1() {
    header "1: Non-interceptable tool (Read) → pass-through"
    save_state; save_config
    set_state "stripe" "payments-billing"
    set_config ""
    run_hook "Read" '{"file_path":"/tmp/test.txt"}' "stub-key"
    restore_state; restore_config
    if [ "$HOOK_EXIT" = "0" ]; then
        pass "Read tool passes through (exit 0)"
    else
        fail "Expected exit 0, got $HOOK_EXIT"
    fi
}

# =============================================================================
# SCENARIO 2: Interceptable tool, no credentials → pass-through (exit 0)
# =============================================================================
run_scenario_2() {
    header "2: Skill tool, no API key, no token → pass-through"
    save_state; save_config
    set_state "stripe" "payments-billing"
    set_config ""
    run_hook "Skill" '{"skill":"superpowers:brainstorming"}' ""
    restore_state; restore_config
    if [ "$HOOK_EXIT" = "0" ] && [ -z "$OUTPUT" ]; then
        pass "Silent pass-through — no credentials"
    else
        fail "Expected exit 0 + empty output, got exit=$HOOK_EXIT output='$OUTPUT'"
    fi
}

# =============================================================================
# SCENARIO 3: Bypass token active → pass-through + token consumed (exit 0)
# =============================================================================
run_scenario_3() {
    header "3: Bypass token active → pass-through (token consumed)"
    save_state; save_evaluator
    set_state "stripe" "payments-billing"
    write_bypass "Skill"
    mock_above_threshold  # would block if bypass wasn't active
    run_hook "Skill" '{"skill":"superpowers:brainstorming"}' "stub-key"
    # Check token was consumed
    BYPASS_CLEARED=$(python3 -c "
import json
try:
    d = json.load(open('$STATE'))
    print('cleared' if 'bypass' not in d else 'present')
except Exception:
    print('cleared')
" 2>/dev/null || echo "cleared")
    restore_state; restore_evaluator
    if [ "$HOOK_EXIT" = "0" ]; then
        pass "Bypass token honored — exit 0"
        [ "$BYPASS_CLEARED" = "cleared" ] && pass "Bypass token consumed after use" \
                                           || fail "Bypass token NOT consumed"
    else
        fail "Expected exit 0 with active bypass, got exit=$HOOK_EXIT"
    fi
}

# =============================================================================
# SCENARIO 4: Above threshold → block (exit 2) + comparison output
# =============================================================================
run_scenario_4() {
    header "4: Evaluator returns gap >= 10 → block (exit 2)"
    save_state; save_config; save_evaluator
    set_state "stripe" "payments-billing"
    set_config ""
    mock_above_threshold
    run_hook "Skill" '{"skill":"superpowers:brainstorming"}' "stub-key"
    restore_config; restore_evaluator; restore_state
    if [ "$HOOK_EXIT" = "2" ]; then
        pass "Hook blocked (exit 2)"
        if echo "$OUTPUT" | grep -q "\[DISPATCH\] Intercepted"; then
            pass "Comparison output contains [DISPATCH] header"
        else
            fail "Output missing [DISPATCH] header — got: $OUTPUT"
        fi
        if echo "$OUTPUT" | grep -q "stripe-mcp"; then
            pass "Output names the marketplace alternative"
        else
            fail "Output missing tool name — got: $OUTPUT"
        fi
    else
        fail "Expected exit 2, got exit=$HOOK_EXIT (output: $OUTPUT)"
    fi
}

# =============================================================================
# SCENARIO 5: Below threshold → pass-through (exit 0)
# =============================================================================
run_scenario_5() {
    header "5: Evaluator returns gap < 10 → pass-through"
    save_state; save_config; save_evaluator
    set_state "stripe" "payments-billing"
    set_config ""
    mock_below_threshold
    run_hook "Skill" '{"skill":"superpowers:brainstorming"}' "stub-key"
    restore_config; restore_evaluator; restore_state
    if [ "$HOOK_EXIT" = "0" ]; then
        pass "Below threshold — exit 0"
    else
        fail "Expected exit 0, got exit=$HOOK_EXIT (output: $OUTPUT)"
    fi
}

# =============================================================================
# Main
# =============================================================================
case "${1:-all}" in
    1)   run_scenario_1 ;;
    2)   run_scenario_2 ;;
    3)   run_scenario_3 ;;
    4)   run_scenario_4 ;;
    5)   run_scenario_5 ;;
    all) run_scenario_1; run_scenario_2; run_scenario_3; run_scenario_4; run_scenario_5 ;;
    *)   echo "Usage: $0 [1-5|all]"; exit 1 ;;
esac
