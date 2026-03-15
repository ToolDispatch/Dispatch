---
name: dispatch-status
description: Show current Dispatch hook status — last task detected, category, quota usage, plan, and bypass token state
---

Show the current Dispatch status by running this command and displaying the output clearly:

```bash
python3 - << 'PYEOF'
import json, os, sys
from datetime import datetime, timezone

d = os.path.expanduser("~/.claude/dispatch")

def read_json(path):
    try:
        with open(path) as f:
            return json.load(f)
    except Exception:
        return {}

state  = read_json(os.path.join(d, "state.json"))
config = read_json(os.path.join(d, "config.json"))
bypass = read_json(os.path.join(d, "bypass_token.json"))

plan       = config.get("plan", "unknown")
token      = config.get("token", "")
token_disp = f"{token[:8]}...{token[-4:]}" if len(token) > 12 else ("set" if token else "not set")
mode       = "hosted" if token else ("byok" if os.environ.get("ANTHROPIC_API_KEY") else "unconfigured")

task_type  = state.get("last_task_type", "—")
category   = state.get("last_category", "—")
cwd        = state.get("last_cwd", "—")

bypass_status = "none"
if bypass:
    exp = bypass.get("expires_at", 0)
    if exp > datetime.now(timezone.utc).timestamp():
        bypass_status = "active (proceed typed)"

hook1 = os.path.expanduser("~/.claude/hooks/dispatch.sh")
hook2 = os.path.expanduser("~/.claude/hooks/dispatch-preuse.sh")
h1 = "installed" if os.path.exists(hook1) else "MISSING"
h2 = "installed" if os.path.exists(hook2) else "MISSING"

print("◎ Dispatch Status")
print(f"  Mode:        {mode}")
print(f"  Plan:        {plan}")
print(f"  Token:       {token_disp}")
print(f"")
print(f"  Hook 1 (UserPromptSubmit):  {h1}")
print(f"  Hook 2 (PreToolUse):        {h2}")
print(f"")
print(f"  Last task:   {task_type}")
print(f"  Category:    {category}")
print(f"  Working dir: {cwd}")
print(f"  Bypass:      {bypass_status}")
PYEOF
```

Format the output as a clean status block. If hooks are MISSING, warn the user to re-run `bash install.sh` from the Dispatch directory.
