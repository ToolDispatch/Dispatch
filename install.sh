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

# ── Seed state files ───────────────────────────────────────────────────────
[ -f "$DISPATCH_DIR/state.json" ] || echo '{"last_task_type":null,"last_updated":null}' > "$DISPATCH_DIR/state.json"

# ── Install hook script ────────────────────────────────────────────────────
cp dispatch.sh "$HOOKS_DIR/skill-router.sh"
chmod +x "$HOOKS_DIR/skill-router.sh"

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

# ── Add pending_notification entry to global CLAUDE.md ─────────────────────
GLOBAL_CLAUDE_MD="$HOME/.claude/CLAUDE.md"
DISPATCH_MARKER="## Dispatch Hook Notifications"
NOTIF_PATH="$DISPATCH_DIR/pending_notification.json"

if ! grep -q "$DISPATCH_MARKER" "$GLOBAL_CLAUDE_MD" 2>/dev/null; then
    touch "$GLOBAL_CLAUDE_MD"
    printf '\n## Dispatch Hook Notifications\nAt the start of each response, check if `%s` exists.\nIf it does:\n1. Read it and display a concise block showing the detected task type and recommended tools (installed first, then suggested with install commands)\n2. Delete the file\n3. Ask the user if they want to install or explore any of the suggested tools before continuing\n4. Wait for their response — do NOT answer their original question yet\nOnly proceed with the original question after the user confirms they are ready to continue.\n' "$NOTIF_PATH" >> "$GLOBAL_CLAUDE_MD"
    echo "Added Dispatch notification instruction to ~/.claude/CLAUDE.md"
fi

# ── Pre-warm npx cache (prevents first-run hook timeout) ───────────────────
echo "Pre-warming skill registry cache..."
python3 -c "
import sys
sys.path.insert(0, '$DISPATCH_DIR')
try:
    from evaluator import get_installed_skills
    get_installed_skills()
except Exception:
    pass
" 2>/dev/null || true

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
    echo " 4. Paste it here and press Enter:"
    echo ""
    printf "    Token: "
    read -r USER_TOKEN < /dev/tty

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
echo "Next steps:"
echo "  Start a new Claude Code session — Dispatch fires automatically on topic shifts"
echo ""
