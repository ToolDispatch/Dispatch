---
name: dispatch
description: >
  Automatically surfaces the best plugin, skill, or MCP server for your
  current task. Runs as a UserPromptSubmit + PreToolUse hook — fires silently
  in the background, intercepts tool calls when a better marketplace alternative
  exists (≥10-point score gap), and shows a ranked recommendation list with
  install commands. Supports hosted mode (free, 5 detections/day) or BYOK
  (bring your own Anthropic API key, unlimited).
license: MIT
hooks:
  UserPromptSubmit:
    - type: command
      command: bash ~/.claude/hooks/skill-router.sh
      timeout_ms: 10000
  PreToolUse:
    - type: command
      command: bash ~/.claude/hooks/preuse-hook.sh
      timeout_ms: 10000
metadata:
  author: VisionAIrySE
  version: "0.8.0"
  repository: https://github.com/VisionAIrySE/Dispatch
  homepage: https://dispatch.visionairy.biz
  install: bash <(curl -fsSL https://raw.githubusercontent.com/VisionAIrySE/Dispatch/main/install.sh)
---

# Dispatch

Runtime skill router for Claude Code. Detects task shifts and surfaces the best
plugin, MCP server, or agent skill before you start — so you're always using the
right tool.

## Install

```bash
bash <(curl -fsSL https://raw.githubusercontent.com/VisionAIrySE/Dispatch/main/install.sh)
```

Requires Python 3.8+ and Node.js (for `npx skills list`).

## How it works

**Hook 1 — UserPromptSubmit** (`dispatch.sh`): Detects topic shifts using Claude
Haiku (~100ms). On a confirmed shift, maps the task type to a MECE category,
searches the plugin marketplace + MCP registry + skills catalog, scores all tools
0–100, and writes state for Hook 2.

**Hook 2 — PreToolUse** (`preuse_hook.sh`): Before Claude invokes a Skill, Agent,
or MCP tool, checks if a better marketplace tool exists. If the top alternative
scores ≥10 points higher than Claude's chosen tool, blocks (exit 2) and shows the
recommendation. The user can type "proceed" to bypass.

## Modes

| Mode | Requirement | Detections |
|------|------------|-----------|
| **Hosted** | Free token at dispatch.visionairy.biz | 5/day free, unlimited Pro ($10/mo) |
| **BYOK** | `ANTHROPIC_API_KEY` set | Unlimited |

## Docs

- README: https://github.com/VisionAIrySE/Dispatch
- Hosted endpoint: https://dispatch.visionairy.biz
