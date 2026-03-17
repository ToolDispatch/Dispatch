---
name: dispatch
description: >
  Proactively surfaces the best plugin, skill, or MCP server for your current
  task — and intercepts tool calls when a better marketplace alternative exists.
  Runs as a UserPromptSubmit + PreToolUse hook: on every task shift, surfaces
  grouped recommendations by type (Plugins/Skills/MCPs) directly in context;
  before every tool call, scores marketplace alternatives 0–100 and blocks
  (exit 2) if a better tool scores ≥10 points higher. User types "proceed" to
  bypass (one-time, no restart). Hosted Free (8 intercepts/day) and Pro
  (unlimited, Sonnet ranking, pre-ranked catalog) both include full proactive
  recommendations. BYOK available for air-gapped environments.
license: MIT
hooks:
  UserPromptSubmit:
    - type: command
      command: bash ~/.claude/hooks/dispatch.sh
      timeout_ms: 10000
  PreToolUse:
    - type: command
      command: bash ~/.claude/hooks/dispatch-preuse.sh
      timeout_ms: 10000
metadata:
  author: VisionAIrySE
  version: "1.0.0"
  repository: https://github.com/VisionAIrySE/Dispatch
  homepage: https://dispatch.visionairy.biz
  install: bash <(curl -fsSL https://raw.githubusercontent.com/VisionAIrySE/Dispatch/main/install.sh)
---

# Dispatch

Proactive tool discovery and protective intercept for Claude Code. Detects task
shifts, surfaces grouped plugin/skill/MCP recommendations before you start, and
blocks weaker tool choices mid-session — so you're always using the right tool.

## Install

```bash
bash <(curl -fsSL https://raw.githubusercontent.com/VisionAIrySE/Dispatch/main/install.sh)
```

Requires Python 3.8+ and Node.js (for `npx skills list`).

## How it works

**Hook 1 — UserPromptSubmit** (`dispatch.sh`): Detects topic shifts using Claude
Haiku (~100ms). On a confirmed shift, maps the task type to one of 16 MECE
categories using `category_mapper.py`. In BYOK mode, Stage 3 immediately surfaces
grouped tool recommendations into Claude's context — organized by Plugins, Skills,
and MCPs, 2–3 per type, with install commands. Closes with "Not sure which to
pick? Ask me — I can explain the differences." Each category's recommendations
appear once per session. Hook 1 also writes category state used by Hook 2.

**Hook 2 — PreToolUse** (`preuse_hook.sh`): Before Claude invokes a Skill, Agent,
or MCP tool, searches the marketplace using the current task category, scores all
results 0–100, and scores Claude's chosen tool on the same scale. If the top
alternative scores ≥10 points higher, blocks (exit 2) and surfaces the ranked
comparison. The user can type "proceed" to bypass (one-time, no restart needed).
Works in all modes: Free, BYOK, and Pro.

**Category-first routing**: 16 MECE categories (e.g. `mobile`, `frontend`,
`devops-cicd`, `ai-ml`). Haiku generates open-ended task type labels; the
category model translates them into targeted search queries. Unknown task types
are logged to `unknown_categories.jsonl`.

**MCP server awareness**: Dispatch searches three MCP registries alongside skills.sh:
- **glama.ai** — community MCP index, searched by category-specific MCP terms
- **Smithery.ai** — `registry.smithery.ai`, usage counts (useCount ≥ 20 filter)
- **Official MCP registry** — `registry.modelcontextprotocol.io`, curated list
Already-installed MCP servers (detected from `.mcp.json`) are excluded from
recommendations — Dispatch only surfaces tools you don't already have.

**Stack detection**: On each confirmed shift, Dispatch scans the project's manifest
files (`package.json`, `requirements.txt`, `go.mod`, `Cargo.toml`, `pubspec.yaml`,
etc.) to build a stack profile. Pro catalog results are reranked using this profile —
a Flutter project gets Flutter-specific tools ranked higher than generic mobile
tools with similar base scores.

## Modes

| Mode | Requirement | Intercepts | Proactive |
|------|------------|-----------|-----------|
| **Hosted Free** | Free token at dispatch.visionairy.biz | 8/day | ✓ |
| **Hosted Pro** | $10/mo ($6 founding) | Unlimited | ✓ |
| **BYOK** | `ANTHROPIC_API_KEY` (air-gapped only) | Unlimited | ✓ |

## Docs

- README: https://github.com/VisionAIrySE/Dispatch
- Hosted endpoint: https://dispatch.visionairy.biz
