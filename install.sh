#!/bin/bash
# =============================================================================
# Dispatch — Install Script
# Runtime skill router for Claude Code
# =============================================================================

set -euo pipefail

DISPATCH_DIR="$HOME/.claude/dispatch"
HOOKS_DIR="$HOME/.claude/hooks"
SETTINGS="$HOME/.claude/settings.json"
CONFIG_FILE="$DISPATCH_DIR/config.json"
DISPATCH_ENDPOINT="https://dispatch.visionairy.biz"

# ── Detect tier for XFTC ──────────────────────────────────────────────────
XFTC_TIER="free"
if [ -f "$CONFIG_FILE" ]; then
    EXISTING_TOKEN=$(python3 -c "
import json
try:
    d = json.load(open('$CONFIG_FILE'))
    print(d.get('token', ''))
except:
    print('')
" 2>/dev/null || echo "")

    if [ -n "$EXISTING_TOKEN" ]; then
        PLAN=$(curl -sf "$DISPATCH_ENDPOINT/usage?token=$EXISTING_TOKEN" \
            | python3 -c "import json,sys; d=json.load(sys.stdin); print(d.get('plan','free'))" \
            2>/dev/null || echo "free")
        XFTC_TIER="$PLAN"
    elif [ -n "${ANTHROPIC_API_KEY:-}" ]; then
        XFTC_TIER="byok"
    fi
fi

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

# ── Migrate from old skill-router directory if present ─────────────────────
OLD_DIR="$HOME/.claude/skill-router"
if [ -d "$OLD_DIR" ]; then
    echo "  Migrating from ~/.claude/skill-router → ~/.claude/dispatch ..."
    mkdir -p "$DISPATCH_DIR"
    # Preserve existing config (token) and state (last_task_type etc.)
    [ -f "$OLD_DIR/config.json" ] && [ ! -f "$DISPATCH_DIR/config.json" ] && cp "$OLD_DIR/config.json" "$DISPATCH_DIR/"
    [ -f "$OLD_DIR/state.json" ]  && [ ! -f "$DISPATCH_DIR/state.json"  ] && cp "$OLD_DIR/state.json"  "$DISPATCH_DIR/"
    rm -rf "$OLD_DIR"
    # Remove old hook scripts
    rm -f "$HOOKS_DIR/skill-router.sh" "$HOOKS_DIR/preuse-hook.sh"
    # Remove old hook entries from settings.json
    python3 - <<PYEOF
import json
try:
    with open("$SETTINGS") as f:
        s = json.load(f)
    old_basenames = {"skill-router.sh", "preuse-hook.sh"}
    for event in ["UserPromptSubmit", "PreToolUse"]:
        if event in s.get("hooks", {}):
            for entry in s["hooks"][event]:
                entry["hooks"] = [
                    h for h in entry.get("hooks", [])
                    if not any(x in h.get("command", "") for x in old_basenames)
                ]
            # Remove entries that are now empty (had only old hook commands)
            s["hooks"][event] = [e for e in s["hooks"][event] if e.get("hooks")]
    with open("$SETTINGS", "w") as f:
        json.dump(s, f, indent=2)
except Exception:
    pass
PYEOF
    echo "  ✓ Migration complete"
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
cp taxonomy.json "$DISPATCH_DIR/"

# ── Seed state files ───────────────────────────────────────────────────────
# first_run=true → dispatch.sh emits one-time "active" confirmation on first message
[ -f "$DISPATCH_DIR/state.json" ] || echo '{"last_task_type":null,"last_updated":null,"first_run":true}' > "$DISPATCH_DIR/state.json"

# ── Install hook script ────────────────────────────────────────────────────
cp dispatch.sh "$HOOKS_DIR/dispatch.sh"
chmod +x "$HOOKS_DIR/dispatch.sh"
cp preuse_hook.sh "$HOOKS_DIR/dispatch-preuse.sh"
chmod +x "$HOOKS_DIR/dispatch-preuse.sh"
cp stop_hook.sh "$HOOKS_DIR/dispatch-stop.sh"
chmod +x "$HOOKS_DIR/dispatch-stop.sh"

# ── Install XFTC Module 3 ──────────────────────────────────────────────────
XFTC_DEST="${HOME}/.claude/xftc"
mkdir -p "$XFTC_DEST/checks" "$XFTC_DEST/tests"

cp -r xftc/*.py "$XFTC_DEST/"
cp -r xftc/checks/*.py "$XFTC_DEST/checks/"
touch "$XFTC_DEST/__init__.py" "$XFTC_DEST/checks/__init__.py"

# Seed XFTC state (preserves existing state on --update)
XFTC_STATE="$DISPATCH_DIR/xftc_state.json"
if [ ! -f "$XFTC_STATE" ]; then
    python3 -c "
import json, sys
state = {
    'tier': sys.argv[1],
    'installed_version': '1.0.0',
    'last_notified_version': '1.0.0',
    'last_version_check_date': '',
    'sessions': {},
    'projects': {}
}
with open(sys.argv[2], 'w') as f:
    json.dump(state, f, indent=2)
" "${XFTC_TIER:-free}" "$XFTC_STATE"
else
    python3 -c "
import json, sys
try:
    with open(sys.argv[1]) as f:
        s = json.load(f)
    s['installed_version'] = '1.0.0'
    with open(sys.argv[1], 'w') as f:
        json.dump(s, f, indent=2)
except Exception:
    pass
" "$XFTC_STATE"
fi

cp xftc-submit.sh "$HOOKS_DIR/xftc-submit.sh"
cp xftc-preuse.sh "$HOOKS_DIR/xftc-preuse.sh"
cp xftc-stop.sh  "$HOOKS_DIR/xftc-stop.sh"
chmod +x "$HOOKS_DIR/xftc-submit.sh" "$HOOKS_DIR/xftc-preuse.sh" "$HOOKS_DIR/xftc-stop.sh"

# ── Install skills ─────────────────────────────────────────────────────────
SKILLS_DIR="$HOME/.claude/skills/dispatch-status"
mkdir -p "$SKILLS_DIR"
cp skills/dispatch-status/SKILL.md "$SKILLS_DIR/SKILL.md"

COMPACT_SKILLS_DIR="$HOME/.claude/skills/dispatch-compact-md"
mkdir -p "$COMPACT_SKILLS_DIR"
cp skills/dispatch-compact-md/SKILL.md "$COMPACT_SKILLS_DIR/SKILL.md"

# ── Register hook in settings.json ────────────────────────────────────────
if [ ! -f "$SETTINGS" ]; then
    echo '{"hooks":{}}' > "$SETTINGS"
fi

python3 - <<PYEOF
import json, sys, os

settings_path = "$SETTINGS"
hook_cmd = "bash $HOOKS_DIR/dispatch.sh"

try:
    with open(settings_path) as f:
        settings = json.load(f)
except (json.JSONDecodeError, IOError):
    settings = {}

hooks = settings.setdefault("hooks", {})

hook_basename = os.path.basename(hook_cmd.split()[-1])  # e.g. "dispatch.sh"
for entry in hooks.get("UserPromptSubmit", []):
    for h in entry.get("hooks", []):
        if hook_basename in h.get("command", ""):
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
import json, sys, os

settings_path = "$SETTINGS"
hook_cmd = "bash $HOOKS_DIR/dispatch-preuse.sh"

try:
    with open(settings_path) as f:
        settings = json.load(f)
except (json.JSONDecodeError, IOError):
    settings = {}

hooks = settings.setdefault("hooks", {})

hook_basename = os.path.basename(hook_cmd.split()[-1])  # e.g. "dispatch-preuse.sh"
for entry in hooks.get("PreToolUse", []):
    for h in entry.get("hooks", []):
        if hook_basename in h.get("command", ""):
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

python3 - <<PYEOF
import json, sys, os

settings_path = "$SETTINGS"
hook_cmd = "bash $HOOKS_DIR/dispatch-stop.sh"

try:
    with open(settings_path) as f:
        settings = json.load(f)
except (json.JSONDecodeError, IOError):
    settings = {}

hooks = settings.setdefault("hooks", {})

hook_basename = os.path.basename(hook_cmd.split()[-1])  # e.g. "dispatch-stop.sh"
for entry in hooks.get("Stop", []):
    for h in entry.get("hooks", []):
        if hook_basename in h.get("command", ""):
            print("Stop hook already registered — skipping.")
            sys.exit(0)

hooks.setdefault("Stop", []).append({
    "hooks": [{
        "type": "command",
        "command": hook_cmd,
        "timeout_ms": 3000
    }]
})

with open(settings_path, "w") as f:
    json.dump(settings, f, indent=2)

print("Registered Stop hook in settings.json")
PYEOF

# Register XFTC UserPromptSubmit hook
python3 - <<PYEOF
import json, sys, os
settings_path = "$SETTINGS"
hook_cmd = "bash $HOOKS_DIR/xftc-submit.sh"
try:
    with open(settings_path) as f:
        settings = json.load(f)
except (json.JSONDecodeError, IOError):
    settings = {}
hooks = settings.setdefault("hooks", {})
hook_basename = "xftc-submit.sh"
for entry in hooks.get("UserPromptSubmit", []):
    for h in entry.get("hooks", []):
        if hook_basename in h.get("command", ""):
            print("XFTC UserPromptSubmit hook already registered — skipping.")
            sys.exit(0)
hooks.setdefault("UserPromptSubmit", []).append({
    "hooks": [{"type": "command", "command": hook_cmd, "timeout_ms": 8000}]
})
with open(settings_path, "w") as f:
    json.dump(settings, f, indent=2)
print("Registered XFTC UserPromptSubmit hook")
PYEOF

# Register XFTC PreToolUse hook
python3 - <<PYEOF
import json, sys, os
settings_path = "$SETTINGS"
hook_cmd = "bash $HOOKS_DIR/xftc-preuse.sh"
try:
    with open(settings_path) as f:
        settings = json.load(f)
except (json.JSONDecodeError, IOError):
    settings = {}
hooks = settings.setdefault("hooks", {})
hook_basename = "xftc-preuse.sh"
for entry in hooks.get("PreToolUse", []):
    for h in entry.get("hooks", []):
        if hook_basename in h.get("command", ""):
            print("XFTC PreToolUse hook already registered — skipping.")
            sys.exit(0)
hooks.setdefault("PreToolUse", []).append({
    "hooks": [{"type": "command", "command": hook_cmd, "timeout_ms": 8000}]
})
with open(settings_path, "w") as f:
    json.dump(settings, f, indent=2)
print("Registered XFTC PreToolUse hook")
PYEOF

# Register XFTC Stop hook
python3 - <<PYEOF
import json, sys, os
settings_path = "$SETTINGS"
hook_cmd = "bash $HOOKS_DIR/xftc-stop.sh"
try:
    with open(settings_path) as f:
        settings = json.load(f)
except (json.JSONDecodeError, IOError):
    settings = {}
hooks = settings.setdefault("hooks", {})
hook_basename = "xftc-stop.sh"
for entry in hooks.get("Stop", []):
    for h in entry.get("hooks", []):
        if hook_basename in h.get("command", ""):
            print("XFTC Stop hook already registered — skipping.")
            sys.exit(0)
hooks.setdefault("Stop", []).append({
    "hooks": [{"type": "command", "command": hook_cmd, "timeout_ms": 3000}]
})
with open(settings_path, "w") as f:
    json.dump(settings, f, indent=2)
print("Registered XFTC Stop hook")
PYEOF

# ── Configure XFTC status line ─────────────────────────────────────────────
python3 - <<PYEOF
import json, os
settings_path = "$SETTINGS"
STATUS_LINE_FORMAT = "{model} | {context_bar} {context_percent}% | {context_tokens_used} of {context_window} tokens"
try:
    with open(settings_path) as f:
        settings = json.load(f)
except (json.JSONDecodeError, IOError):
    settings = {}
existing_sl = settings.get("statusLine")
# Replace if: not set, OR already a shell-script-command type (not a format string)
is_shell_script = isinstance(existing_sl, dict) and existing_sl.get("type") == "command"
if not existing_sl or is_shell_script:
    settings["statusLine"] = STATUS_LINE_FORMAT
    with open(settings_path, "w") as f:
        json.dump(settings, f, indent=2)
    if is_shell_script:
        print("Status line updated (replaced shell script with XFTC format string)")
    else:
        print("Status line configured")
else:
    print("Status line already configured — skipping")
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
echo "✓ XFTC Module 3 installed"
echo "✓ Status line configured — open a new terminal to see it"
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
    echo "  Plan:      Free — 8 detections/day"
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
echo "  Docs:    https://github.com/ToolDispatch/Dispatch"
echo ""
