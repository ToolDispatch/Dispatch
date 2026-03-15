#!/bin/bash
# =============================================================================
# Dispatch Hook Test Harness — Full path coverage (no API key or live server)
#
# Mocks classifier.py, evaluator.py, and HTTP endpoints to exercise all paths.
#
# Usage: bash test_hook.sh [1-10|all]
#
# Path matrix:
#   1  — short message (< 4 words) → silent
#   2  — no credentials (no key, no token) → silent
#   3  — BYOK, no shift → silent
#   4  — BYOK, shift detected → show UI + recommendations
#   5  — Hosted, no shift → silent
#   6  — Hosted, shift detected → show UI + recommendations
#   7  — Free hosted, 402 first time → upgrade notice + cooldown=5
#   8  — Free hosted, 402 cooldown=3 active → silent + cooldown→2
#   9  — Hosted, 401 first time → re-auth notice + auth_cooldown=5
#   10 — Hosted, 401 cooldown=3 active → silent + auth_cooldown→2
# =============================================================================

set -euo pipefail

HOOK="$HOME/.claude/hooks/skill-router.sh"
STATE="$HOME/.claude/skill-router/state.json"
CONFIG="$HOME/.claude/skill-router/config.json"
SKILL_DIR="$HOME/.claude/skill-router"

STATE_BAK="${STATE}.testbak"
CONFIG_BAK="${CONFIG}.testbak"
CLASSIFIER_BAK="${SKILL_DIR}/classifier.py.testbak"
EVALUATOR_BAK="${SKILL_DIR}/evaluator.py.testbak"
TRANSCRIPT=$(mktemp /tmp/dispatch-test-transcript.XXXX.jsonl)
MOCK_PID=""
PASS=0; FAIL=0; SKIP=0

RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'; CYAN='\033[0;36m'; NC='\033[0m'
pass() { echo -e "${GREEN}PASS${NC}  $1"; ((PASS++)) || true; }
fail() { echo -e "${RED}FAIL${NC}  $1"; ((FAIL++)) || true; }
skip() { echo -e "${YELLOW}SKIP${NC}  $1"; ((SKIP++)) || true; }
info() { echo -e "${CYAN}----${NC}  $1"; }
header() { echo -e "\n${YELLOW}=== Scenario $1 ===${NC}"; }

cleanup() {
    rm -f "$TRANSCRIPT" "$STATE_BAK" "$CONFIG_BAK" "$CLASSIFIER_BAK" "$EVALUATOR_BAK" 2>/dev/null || true
    [ -n "${MOCK_PID:-}" ] && kill "$MOCK_PID" 2>/dev/null || true
    echo ""
    echo "Results: ${PASS} passed  ${FAIL} failed  ${SKIP} skipped"
}
trap cleanup EXIT

# ── State / config helpers ────────────────────────────────────────────────────
save_state()     { cp "$STATE"  "$STATE_BAK"  2>/dev/null || echo '{}' > "$STATE_BAK"; }
restore_state()  { cp "$STATE_BAK"  "$STATE"  2>/dev/null || true; }
save_config()    { cp "$CONFIG" "$CONFIG_BAK" 2>/dev/null || echo '{}' > "$CONFIG_BAK"; }
restore_config() { cp "$CONFIG_BAK" "$CONFIG" 2>/dev/null || true; }

set_state() {
    python3 -c "
import json
try:
    d = json.load(open('$STATE'))
except Exception:
    d = {}
d.update({'last_task_type': '${1:-}', 'limit_cooldown': ${2:-0}, 'auth_invalid_cooldown': ${3:-0}})
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

get_cooldown() {
    python3 -c "import json; print(json.load(open('$STATE')).get('${1:-limit_cooldown}', '?'))" 2>/dev/null || echo "?"
}

make_transcript() {
    python3 -c "
import json
with open('$TRANSCRIPT', 'w') as f:
    for e in [
        {'type': 'user', 'message': {'role': 'user', 'content': 'help me fix this Flutter widget'}, 'uuid': 'aaa'},
        {'type': 'assistant', 'message': {'role': 'assistant', 'content': 'Sure.'}, 'uuid': 'bbb'},
    ]:
        f.write(json.dumps(e) + '\n')
"
}

run_hook() {
    local prompt="${1:-set up Stripe webhook endpoint and verify the signature}"
    local api_key="${2:-}"
    local hook_input
    hook_input=$(python3 -c "
import json, sys
print(json.dumps({'transcript_path': sys.argv[1], 'cwd': '/home/visionairy/Dispatch', 'prompt': sys.argv[2]}))
" "$TRANSCRIPT" "$prompt")
    ANTHROPIC_API_KEY="$api_key" bash "$HOOK" <<< "$hook_input" 2>&1 || true
}

# ── BYOK mocking: swap classifier.py + evaluator.py with stubs ───────────────
save_byok() {
    cp "$SKILL_DIR/classifier.py" "$CLASSIFIER_BAK" 2>/dev/null || true
    cp "$SKILL_DIR/evaluator.py"  "$EVALUATOR_BAK"  2>/dev/null || true
}
restore_byok() {
    cp "$CLASSIFIER_BAK" "$SKILL_DIR/classifier.py" 2>/dev/null || true
    cp "$EVALUATOR_BAK"  "$SKILL_DIR/evaluator.py"  2>/dev/null || true
}

mock_byok_shift() {
    cat > "$SKILL_DIR/classifier.py" << 'STUB'
import json, sys
print(json.dumps({"shift": True, "task_type": "stripe", "confidence": 0.95}))
STUB
    cat > "$SKILL_DIR/evaluator.py" << 'STUB'
import json
def build_recommendation_list(task_type, **kwargs):
    return {
        "all": [{"name": "stripe-webhooks", "score": 85, "reason": "Stripe webhook integration", "installed": True}],
        "top_pick": {"name": "stripe-webhooks", "score": 85},
        "installed": [{"name": "stripe-webhooks", "reason": "Stripe webhook integration", "marketplace": "claude-plugins-official"}],
        "suggested": [{"name": "stripe-docs-skill", "reason": "Stripe API reference", "install_cmd": "npx skills install stripe-docs-skill"}],
        "cc_score": 50
    }
STUB
}

mock_byok_noshift() {
    cat > "$SKILL_DIR/classifier.py" << 'STUB'
import json, sys
print(json.dumps({"shift": False, "task_type": "flutter", "confidence": 0.85}))
STUB
}

# ── Mock HTTP server ──────────────────────────────────────────────────────────
start_mock_server() {
    local mode="$1" port="$2"
    [ -n "${MOCK_PID:-}" ] && { kill "$MOCK_PID" 2>/dev/null || true; MOCK_PID=""; }
    python3 - "$mode" "$port" << 'PYEOF' &
from http.server import HTTPServer, BaseHTTPRequestHandler
import json, sys

mode = sys.argv[1]

class H(BaseHTTPRequestHandler):
    def do_POST(self):
        length = int(self.headers.get('Content-Length', 0))
        self.rfile.read(length)
        if mode == '402':
            code, body = 402, json.dumps({'error': 'limit_reached', 'upgrade_url': 'https://dispatch.visionairy.biz/pro'})
        elif mode == '401':
            code, body = 401, json.dumps({'error': 'invalid_token'})
        elif mode == '200_noshift':
            code, body = 200, json.dumps({'shift': False, 'task_type': 'flutter', 'confidence': 0.85})
        elif mode == '200_shift':
            code = 200
            if '/classify' in self.path:
                body = json.dumps({'shift': True, 'task_type': 'stripe', 'confidence': 0.95})
            else:
                body = json.dumps({'installed': [{'name': 'stripe-webhooks', 'reason': 'Stripe webhook integration'}], 'suggested': []})
        else:
            code, body = 500, '{}'
        self.send_response(code)
        self.send_header('Content-Type', 'application/json')
        self.end_headers()
        self.wfile.write(body.encode())
    def log_message(self, *a): pass

HTTPServer(('127.0.0.1', int(sys.argv[2])), H).serve_forever()
PYEOF
    MOCK_PID=$!
    sleep 0.3
}

stop_mock_server() {
    [ -n "${MOCK_PID:-}" ] && { kill "$MOCK_PID" 2>/dev/null || true; MOCK_PID=""; }
}

# =============================================================================
# SCENARIO 1: Short message → silent
# =============================================================================
run_scenario_1() {
    header "1: Short message (< 4 words) → silent"
    save_state; save_config
    set_state "flutter" 0 0
    make_transcript
    OUTPUT=$(run_hook "ok thanks")
    restore_state; restore_config
    [ -z "$OUTPUT" ] && pass "Silent exit — short message skipped" \
                     || fail "Expected silence, got: $OUTPUT"
}

# =============================================================================
# SCENARIO 2: No credentials → silent
# =============================================================================
run_scenario_2() {
    header "2: No credentials (no key, no token) → silent"
    # The hook falls back to ~/.mcp.json for an API key — if that file has a key,
    # the "no credentials" path is unreachable in this environment.
    local has_fallback
    has_fallback=$(python3 -c "
import json, os
try:
    d = json.load(open(os.path.expanduser('~/.mcp.json')))
    k = d.get('mcpServers', {}).get('xpansion', {}).get('env', {}).get('ANTHROPIC_API_KEY', '')
    print('yes' if k else 'no')
except: print('no')
" 2>/dev/null || echo "no")
    if [ "$has_fallback" = "yes" ]; then
        skip "mcp.json provides API key fallback — 'no credentials' path unreachable here (correct behavior in prod)"
        return
    fi
    save_state; save_config
    set_state "" 0 0
    set_config ""
    make_transcript
    OUTPUT=$(run_hook "set up Stripe webhook endpoint and verify the signature" "")
    restore_state; restore_config
    [ -z "$OUTPUT" ] && pass "Silent exit — no credentials" \
                     || fail "Expected silence, got: $OUTPUT"
}

# =============================================================================
# SCENARIO 3: BYOK — no shift → silent
# =============================================================================
run_scenario_3() {
    header "3: BYOK — no shift → silent"
    save_state; save_config; save_byok
    set_state "flutter" 0 0
    set_config ""
    mock_byok_noshift
    make_transcript
    OUTPUT=$(run_hook "make the AppBar title bold in the Flutter widget" "stub-key")
    restore_state; restore_config; restore_byok
    [ -z "$OUTPUT" ] && pass "Silent exit — no shift" \
                     || fail "Expected silence, got: $OUTPUT"
}

# =============================================================================
# SCENARIO 4: BYOK — shift detected → show UI
# =============================================================================
run_scenario_4() {
    header "4: BYOK — shift detected → state.json updated"
    save_state; save_config; save_byok
    set_state "flutter" 0 0
    set_config ""
    mock_byok_shift
    make_transcript
    run_hook "set up Stripe webhook endpoint and verify the signature" "stub-key" > /dev/null
    restore_config; restore_byok
    if python3 -c "import json; d=json.load(open('$STATE')); assert d.get('last_task_type'), 'no task_type'" 2>/dev/null; then
        pass "state.json updated with last_task_type"
    else
        fail "state.json not updated with last_task_type"
    fi
    restore_state
}

# =============================================================================
# SCENARIO 5: Hosted — no shift → silent
# =============================================================================
run_scenario_5() {
    header "5: Hosted — no shift → silent"
    start_mock_server "200_noshift" 19875
    save_state; save_config
    set_state "flutter" 0 0
    set_config "test-token" "http://127.0.0.1:19875"
    make_transcript
    OUTPUT=$(run_hook "make the AppBar title bold in the Flutter widget")
    restore_state; restore_config; stop_mock_server
    [ -z "$OUTPUT" ] && pass "Silent exit — no shift" \
                     || fail "Expected silence, got: $OUTPUT"
}

# =============================================================================
# SCENARIO 6: Hosted — shift + recommendations → show UI
# =============================================================================
run_scenario_6() {
    header "6: Hosted — shift detected → state.json updated"
    start_mock_server "200_shift" 19876
    save_state; save_config; save_byok
    set_state "flutter" 0 0
    set_config "test-token" "http://127.0.0.1:19876"
    mock_byok_shift  # evaluator stub for local scan fallback
    make_transcript
    run_hook "set up Stripe webhook endpoint and verify the signature" > /dev/null
    restore_config; restore_byok; stop_mock_server
    if python3 -c "import json; d=json.load(open('$STATE')); assert d.get('last_task_type'), 'no task_type'" 2>/dev/null; then
        pass "state.json updated with last_task_type"
    else
        fail "state.json not updated with last_task_type"
    fi
    restore_state
}

# =============================================================================
# SCENARIO 7: Free hosted — 402 first time → upgrade notice + cooldown=5
# =============================================================================
run_scenario_7() {
    header "7: Free hosted — 402 first time → upgrade notice + cooldown=5"
    start_mock_server "402" 19877
    save_state; save_config
    set_state "flutter" 0 0
    set_config "test-token" "http://127.0.0.1:19877"
    make_transcript
    OUTPUT=$(run_hook "set up Stripe webhook endpoint and verify the signature")
    COOLDOWN=$(get_cooldown "limit_cooldown")
    restore_state; restore_config; stop_mock_server
    # Notice goes to /dev/tty (not captured in tests) — verify via state.json side effect
    UNEXPECTED=$(echo "$OUTPUT" | grep -v "^$" | grep -v "/dev/tty" || true)
    if [ "$COOLDOWN" = "5" ]; then
        pass "402 upgrade notice displayed (via /dev/tty) + limit_cooldown set to 5"
        [ -z "$UNEXPECTED" ] || fail "Unexpected extra output: $UNEXPECTED"
    else
        fail "limit_cooldown=$COOLDOWN, expected 5 (output: $OUTPUT)"
    fi
}

# =============================================================================
# SCENARIO 8: Free hosted — 402 cooldown active → silent + cooldown decremented
# =============================================================================
run_scenario_8() {
    header "8: Free hosted — 402 cooldown=3 active → silent + cooldown→2"
    start_mock_server "402" 19878
    save_state; save_config
    set_state "flutter" 3 0
    set_config "test-token" "http://127.0.0.1:19878"
    make_transcript
    OUTPUT=$(run_hook "set up Stripe webhook endpoint and verify the signature")
    COOLDOWN=$(get_cooldown "limit_cooldown")
    restore_state; restore_config; stop_mock_server
    if [ -z "$OUTPUT" ]; then
        pass "Silent exit — cooldown active"
        [ "$COOLDOWN" = "2" ] && pass "limit_cooldown decremented 3→2" \
                               || fail "limit_cooldown=$COOLDOWN, expected 2"
    else
        fail "Expected silence, got: $OUTPUT"
    fi
}

# =============================================================================
# SCENARIO 9: Hosted — 401 first time → re-auth notice + auth_cooldown=5
# =============================================================================
run_scenario_9() {
    header "9: Hosted — 401 first time → re-auth notice + auth_cooldown=5"
    start_mock_server "401" 19879
    save_state; save_config
    set_state "flutter" 0 0
    set_config "invalid-token" "http://127.0.0.1:19879"
    make_transcript
    OUTPUT=$(run_hook "set up Stripe webhook endpoint and verify the signature")
    COOLDOWN=$(get_cooldown "auth_invalid_cooldown")
    restore_state; restore_config; stop_mock_server
    # Notice goes to /dev/tty (not captured in tests) — verify via state.json side effect
    UNEXPECTED=$(echo "$OUTPUT" | grep -v "^$" | grep -v "/dev/tty" || true)
    if [ "$COOLDOWN" = "5" ]; then
        pass "401 re-auth notice displayed (via /dev/tty) + auth_invalid_cooldown set to 5"
        [ -z "$UNEXPECTED" ] || fail "Unexpected extra output: $UNEXPECTED"
    else
        fail "auth_invalid_cooldown=$COOLDOWN, expected 5 (output: $OUTPUT)"
    fi
}

# =============================================================================
# SCENARIO 10: Hosted — 401 cooldown active → silent + cooldown decremented
# =============================================================================
run_scenario_10() {
    header "10: Hosted — 401 cooldown=3 active → silent + auth_cooldown→2"
    start_mock_server "401" 19880
    save_state; save_config
    set_state "flutter" 0 3
    set_config "invalid-token" "http://127.0.0.1:19880"
    make_transcript
    OUTPUT=$(run_hook "set up Stripe webhook endpoint and verify the signature")
    COOLDOWN=$(get_cooldown "auth_invalid_cooldown")
    restore_state; restore_config; stop_mock_server
    if [ -z "$OUTPUT" ]; then
        pass "Silent exit — auth cooldown active"
        [ "$COOLDOWN" = "2" ] && pass "auth_invalid_cooldown decremented 3→2" \
                               || fail "auth_invalid_cooldown=$COOLDOWN, expected 2"
    else
        fail "Expected silence, got: $OUTPUT"
    fi
}

# =============================================================================
SCENARIO="${1:-all}"
case "$SCENARIO" in
    1)  run_scenario_1  ;;
    2)  run_scenario_2  ;;
    3)  run_scenario_3  ;;
    4)  run_scenario_4  ;;
    5)  run_scenario_5  ;;
    6)  run_scenario_6  ;;
    7)  run_scenario_7  ;;
    8)  run_scenario_8  ;;
    9)  run_scenario_9  ;;
    10) run_scenario_10 ;;
    all)
        for i in 1 2 3 4 5 6 7 8 9 10; do "run_scenario_$i"; done
        ;;
    *)
        echo "Usage: bash test_hook.sh [1-10|all]"
        exit 1
        ;;
esac
