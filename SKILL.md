---
name: dispatch
description: >
  Automatically surfaces the best plugin, skill, or MCP server for your
  current task. Runs as a UserPromptSubmit + PreToolUse hook — fires silently
  in the background, intercepts tool calls when a better marketplace alternative
  exists (≥10-point score gap), and shows a ranked recommendation list with
  install commands. Supports hosted mode (free, 8 detections/day) or BYOK
  (bring your own Anthropic API key, unlimited).
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
Haiku (~100ms). On a confirmed shift, maps the task type to one of 16 MECE
categories using `category_mapper.py`. Category drives the marketplace search —
more targeted than keyword-splitting the task type directly. State is written for
Hook 2. Silent — no output.

**Hook 2 — PreToolUse** (`preuse_hook.sh`): Before Claude invokes a Skill, Agent,
or MCP tool, searches the marketplace using the current task category, scores all
results 0–100, and scores Claude's chosen tool on the same scale. If the top
alternative scores ≥10 points higher, blocks (exit 2) and surfaces the ranked
comparison. The user can type "proceed" to bypass (one-time, no restart needed).

**Category-first routing**: 16 MECE categories (e.g. `mobile-development`,
`frontend-web`, `devops-infra`, `data-science`). Haiku generates open-ended task
type labels; the category model translates them into targeted search queries.
Unknown task types are logged to `unknown_categories.jsonl`.

**MCP server awareness**: Dispatch searches glama.ai for MCP servers alongside
skills.sh for skills and the Claude plugin registries. Already-installed MCP
servers (detected from `.mcp.json`) are excluded from recommendations — Dispatch
only surfaces tools you don't already have.

**Stack detection**: On each confirmed shift, Dispatch scans the project's manifest
files (`package.json`, `requirements.txt`, `go.mod`, `Cargo.toml`, `pubspec.yaml`,
etc.) to build a stack profile. Pro catalog results are reranked using this profile —
a Flutter project gets Flutter-specific tools ranked higher than generic mobile
tools with similar base scores.

## Modes

| Mode | Requirement | Detections |
|------|------------|-----------|
| **Hosted** | Free token at dispatch.visionairy.biz | 8/day free, unlimited Pro ($10/mo — first 300 get $6/mo for life) |
| **BYOK** | `ANTHROPIC_API_KEY` set | Unlimited |

## Docs

- README: https://github.com/VisionAIrySE/Dispatch
- Hosted endpoint: https://dispatch.visionairy.biz
