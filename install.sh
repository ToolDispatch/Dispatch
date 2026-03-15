#!/bin/bash
# =============================================================================
# Dispatch — Install Script
# Runtime skill router for Claude Code
# =============================================================================

set -euo pipefail

DISPATCH_DIR="$HOME/.claude/skill-router"
HOOKS_DIR="$HOME/.claude/hooks"
SETTINGS="$HOME/.claude/settings.json"
CONFIG_FILE="$DISPATCH_DIR/config.json"
DISPATCH_ENDPOINT="https://dispatch.visionairy.biz"

echo "Installing Dispatch..."

# ── Check dependencies ─────────────────────────────────────────────────────
if ! python3 -c "import anthropic" 2>/dev/null; then
    echo "Installing anthropic Python package..."
    python3 -m pip install anthropic --quiet --user
    # Verify — pip exits 0 even when it can't write to site-packages
    if ! python3 -c "import anthropic" 2>/dev/null; then
        echo ""
        echo "  ⚠ anthropic package installed but not importable."
        echo "    Try:  pip3 install anthropic --break-system-packages"
        echo "    Or:   pip3 install --user anthropic"
        echo "    Dispatch will run in degraded mode until this is resolved."
        echo ""
    fi
fi

if ! command -v npx &>/dev/null; then
    echo "ERROR: npx not found. Install Node.js first: https://nodejs.org"
    exit 1
fi

# ── Create directories ─────────────────────────────────────────────────────
mkdir -p "$DISPATCH_DIR" "$HOOKS_DIR"

# ── Copy Python modules ────────────────────────────────────────────────────
cp classifier.py "$DISPATCH_DIR/"
cp evaluator.py "$DISPATCH_DIR/"
cp interceptor.py "$DISPATCH_DIR/"
cp category_mapper.py "$DISPATCH_DIR/"
cp llm_client.py "$DISPATCH_DIR/"
cp stack_scanner.py "$DISPATCH_DIR/"
cp categories.json "$DISPATCH_DIR/"

# ── Seed state files ───────────────────────────────────────────────────────
# first_run=true → dispatch.sh emits one-time "active" confirmation on first message
[ -f "$DISPATCH_DIR/state.json" ] || echo '{"last_task_type":null,"last_updated":null,"first_run":true}' > "$DISPATCH_DIR/state.json"

# ── Install hook script ────────────────────────────────────────────────────
cp dispatch.sh "$HOOKS_DIR/skill-router.sh"
chmod +x "$HOOKS_DIR/skill-router.sh"
cp preuse_hook.sh "$HOOKS_DIR/preuse-hook.sh"
chmod +x "$HOOKS_DIR/preuse-hook.sh"

# ── Install /dispatch status skill ────────────────────────────────────────
SKILLS_DIR="$HOME/.claude/skills/dispatch-status"
mkdir -p "$SKILLS_DIR"
cp skills/dispatch-status/SKILL.md "$SKILLS_DIR/SKILL.md"

# ── Register hook in settings.json ────────────────────────────────────────
if [ ! -f "$SETTINGS" ]; then
    echo '{"hooks":{}}' > "$SETTINGS"
fi

python3 - <<PYEOF
import json, sys

settings_path = "$SETTINGS"
hook_cmd = "bash $HOOKS_DIR/skill-router.sh"

try:
    with open(settings_path) as f:
        settings = json.load(f)
except (json.JSONDecodeError, IOError):
    settings = {}

hooks = settings.setdefault("hooks", {})

for entry in hooks.get("UserPromptSubmit", []):
    for h in entry.get("hooks", []):
        if h.get("command") == hook_cmd:
            print("Dispatch already registered — skipping.")
            sys.exit(0)

hooks.setdefault("UserPromptSubmit", []).append({
    "hooks": [{
        "type": "command",
        "command": hook_cmd,
        "timeout_ms": 10000
    }]
})

with open(settings_path, "w") as f:
    json.dump(settings, f, indent=2)

print("Registered UserPromptSubmit hook in settings.json")
PYEOF

python3 - <<PYEOF
import json, sys

settings_path = "$SETTINGS"
hook_cmd = "bash $HOOKS_DIR/preuse-hook.sh"

try:
    with open(settings_path) as f:
        settings = json.load(f)
except (json.JSONDecodeError, IOError):
    settings = {}

hooks = settings.setdefault("hooks", {})

for entry in hooks.get("PreToolUse", []):
    for h in entry.get("hooks", []):
        if h.get("command") == hook_cmd:
            print("PreToolUse hook already registered — skipping.")
            sys.exit(0)

hooks.setdefault("PreToolUse", []).append({
    "hooks": [{
        "type": "command",
        "command": hook_cmd,
        "timeout_ms": 10000
    }]
})

with open(settings_path, "w") as f:
    json.dump(settings, f, indent=2)

print("Registered PreToolUse hook in settings.json")
PYEOF

# ── Auth / API key setup ───────────────────────────────────────────────────
echo ""

# Check if already have a token
EXISTING_TOKEN=$(python3 -c "
import json
try:
    d = json.load(open('$CONFIG_FILE'))
    t = d.get('token', '')
    print(t if t else '')
except:
    print('')
" 2>/dev/null || echo "")

if [ -n "$EXISTING_TOKEN" ]; then
    echo "✓ Dispatch token found — using hosted endpoint."
elif [ -n "${ANTHROPIC_API_KEY:-}" ]; then
    echo "✓ ANTHROPIC_API_KEY found — running in BYOK mode."
    echo "  (Register at $DISPATCH_ENDPOINT/auth/github to use the hosted endpoint)"
else
    # No token, no API key — offer registration
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    echo " $(printf '\033[94m\xe2\x97\x8e\033[0m') Connect Dispatch to the hosted endpoint (free)"
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    echo ""
    echo " 1. Open this URL in your browser:"
    echo "    $DISPATCH_ENDPOINT/auth/github"
    echo ""
    echo " 2. Sign in with GitHub"
    echo " 3. Copy the token shown on screen"
    # Only prompt if running in an interactive terminal
    if [ -t 0 ]; then
        echo " 4. Paste it here and press Enter:"
        echo ""
        printf "    Token: "
        read -r USER_TOKEN
    else
        echo " 4. Then add your token:"
        echo "    echo '{\"endpoint\":\"$DISPATCH_ENDPOINT\",\"token\":\"YOUR_TOKEN\"}' > $CONFIG_FILE"
        echo ""
        USER_TOKEN=""
    fi

    if [ -n "$USER_TOKEN" ]; then
        python3 -c "
import json, sys
config = {'endpoint': sys.argv[1], 'token': sys.argv[2]}
with open(sys.argv[3], 'w') as f:
    json.dump(config, f, indent=2)
print('Token saved.')
" "$DISPATCH_ENDPOINT" "$USER_TOKEN" "$CONFIG_FILE" 2>/dev/null && echo "✓ Token saved to $CONFIG_FILE"
    else
        echo ""
        echo "  No token entered. Set ANTHROPIC_API_KEY to use BYOK mode, or"
        echo "  re-run install.sh after registering at $DISPATCH_ENDPOINT/auth/github"
    fi
    echo ""
fi

echo ""
echo "✓ Dispatch installed."
echo ""

# ── Status summary ─────────────────────────────────────────────────────────
FINAL_TOKEN=$(python3 -c "
import json
try:
    d = json.load(open('$CONFIG_FILE'))
    t = d.get('token', '')
    print(t if t else '')
except:
    print('')
" 2>/dev/null || echo "")

if [ -n "$FINAL_TOKEN" ]; then
    echo "  Mode:      Hosted  (token: $(echo "$FINAL_TOKEN" | cut -c1-12)...)"
    echo "  Plan:      Free — 5 detections/day"
    echo "  Upgrade:   $DISPATCH_ENDPOINT/pro  (\$10/month — unlimited + Sonnet)"
    echo "  Dashboard: $DISPATCH_ENDPOINT/dashboard?token=$FINAL_TOKEN"
elif [ -n "${ANTHROPIC_API_KEY:-}" ]; then
    echo "  Mode:    BYOK  (using ANTHROPIC_API_KEY)"
else
    echo "  Mode:    ⚠  Inactive — no API key or token configured"
    echo "  Fix:     export ANTHROPIC_API_KEY=sk-ant-..."
    echo "           or re-run install.sh after visiting $DISPATCH_ENDPOINT/auth/github"
fi

echo ""
echo "  Start a new Claude Code session — Dispatch will confirm it's active"
echo "  on your first message."
echo ""
echo "  Docs:    https://github.com/VisionAIrySE/Dispatch"
echo ""
