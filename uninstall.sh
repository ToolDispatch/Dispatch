#!/bin/bash
# =============================================================================
# Dispatch — Uninstall Script
# =============================================================================

set -uo pipefail

DISPATCH_DIR="$HOME/.claude/dispatch"
HOOKS_DIR="$HOME/.claude/hooks"
SETTINGS="$HOME/.claude/settings.json"

echo "Uninstalling Dispatch..."
echo ""

# ── Remove installed files ──────────────────────────────────────────────────
if [ -d "$DISPATCH_DIR" ]; then
    rm -rf "$DISPATCH_DIR"
    echo "  ✓ Removed $DISPATCH_DIR"
else
    echo "  – $DISPATCH_DIR not found (already removed?)"
fi

# ── Remove old skill-router dir if present (pre-v0.9.2 installs) ───────────
OLD_DIR="$HOME/.claude/skill-router"
if [ -d "$OLD_DIR" ]; then
    rm -rf "$OLD_DIR"
    echo "  ✓ Removed $OLD_DIR (old install)"
fi

# ── Remove hook scripts ─────────────────────────────────────────────────────
for hook in "dispatch.sh" "dispatch-preuse.sh" "skill-router.sh" "preuse-hook.sh"; do
    path="$HOOKS_DIR/$hook"
    if [ -f "$path" ]; then
        rm -f "$path"
        echo "  ✓ Removed $path"
    fi
done

# ── Remove dispatch skill ───────────────────────────────────────────────────
SKILL_DIR="$HOME/.claude/skills/dispatch-status"
if [ -d "$SKILL_DIR" ]; then
    rm -rf "$SKILL_DIR"
    echo "  ✓ Removed $SKILL_DIR"
fi

# ── Remove hook entries from settings.json ──────────────────────────────────
if [ -f "$SETTINGS" ]; then
    python3 - <<PYEOF
import json, sys

settings_path = "$SETTINGS"

try:
    with open(settings_path) as f:
        settings = json.load(f)
except Exception:
    print("  – Could not read settings.json")
    sys.exit(0)

hooks = settings.get("hooks", {})
changed = False

def is_dispatch_hook(h):
    cmd = h.get("command", "")
    return any(x in cmd for x in ["dispatch.sh", "dispatch-preuse.sh", "skill-router.sh", "preuse-hook.sh"])

for event in ["UserPromptSubmit", "PreToolUse"]:
    if event not in hooks:
        continue
    before = len(hooks[event])
    hooks[event] = [
        entry for entry in hooks[event]
        if not any(is_dispatch_hook(h) for h in entry.get("hooks", []))
    ]
    if len(hooks[event]) < before:
        changed = True
        print(f"  ✓ Removed Dispatch from {event} hooks")
    if not hooks[event]:
        del hooks[event]

if changed:
    with open(settings_path, "w") as f:
        json.dump(settings, f, indent=2)
else:
    print("  – No Dispatch hooks found in settings.json")
PYEOF
else
    echo "  – settings.json not found"
fi

echo ""
echo "✓ Dispatch uninstalled."
echo ""
