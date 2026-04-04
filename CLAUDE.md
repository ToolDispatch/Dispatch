# ToolDispatch — Claude Code Configuration

**Stack:** Python 3.8+ · Bash · Claude Haiku (free) / Sonnet 4.6 (Pro)
**Repo:** github.com/ToolDispatch/Dispatch
**Server:** `/home/visionairy/Dispatch-API/app.py` — auto-deploys to Render on `git push`

---

## Hooks

| Hook | Trigger | Does |
|------|---------|------|
| `dispatch.sh` | UserPromptSubmit | Haiku shift detection → writes state.json |
| `dispatch-preuse.sh` | PreToolUse (Skill/Agent/mcp__*) | Scores + blocks on 10pt gap |
| `dispatch-stop.sh` | Stop | One-line session digest |
| `xftc-submit.sh` | UserPromptSubmit | Token hog nudges (MCP overhead, CLAUDE.md size, context) |
| `xftc-preuse.sh` | PreToolUse (Agent/Bash) | Sub-agent model + verbose command checks |

**Installed:** `~/.claude/hooks/` (hook scripts) · `~/.claude/dispatch/` (Python modules + state)
**State:** `~/.claude/dispatch/state.json`

---

## Key Modules

| File | Purpose |
|------|---------|
| `classifier.py` | Haiku shift detection, emits task_type + preferred_tool_type |
| `evaluator.py` | `search_by_category()`, `rank_recommendations()`, `build_recommendation_list()` |
| `interceptor.py` | PreToolUse parsing, bypass token, state readers |
| `category_mapper.py` | Maps task_type → MECE category_id; logs unknowns |
| `categories.json` | 16-category catalog with `search_terms` + `mcp_search_terms` |
| `stack_scanner.py` | Detects languages/frameworks/MCPs from project files + .mcp.json |
| `llm_client.py` | OpenRouter-first, Anthropic fallback, noop |

---

## Install / Sync

```bash
cp classifier.py evaluator.py interceptor.py category_mapper.py categories.json \
   llm_client.py stack_scanner.py ~/.claude/dispatch/
cp dispatch.sh ~/.claude/hooks/dispatch.sh
cp preuse_hook.sh ~/.claude/hooks/dispatch-preuse.sh
cp stop_hook.sh ~/.claude/hooks/dispatch-stop.sh
```

---

## Testing

```bash
cd /home/visionairy/Dispatch
python3 -m pytest test_classifier.py test_evaluator.py test_interceptor.py \
  test_category_mapper.py test_llm_client.py test_stack_scanner.py -v
```

263 client tests must pass before pushing. Live test requires a new CC session.

---

## CC Transcript Format (Critical)

Entries: `{"type":"user", "isMeta":bool, "message":{"role":"user","content":"..."}, ...}`

- `role` is nested inside `message` — `entry.get("role")` always returns `None`
- `isMeta=True` = CC system messages — exclude
- Content starting with `[{` = serialized tool result — exclude

`extract_recent_messages` handles all three. Do not revert these filters.

---

## Documentation Update Protocol

After any change affecting user-facing behavior, install steps, API contracts, or pricing:

| Change type | Update |
|-------------|--------|
| New feature / behavior | README, user-guide.md, SKILL.md |
| Install change | README, user-guide.md getting started |
| Pricing change | README table, user-guide.md, app.py upsell |
| Hook behavior change | README, user-guide.md, CLAUDE.md |
| New server env var | admin-guide.md |
| Roadmap item done | README checkboxes, CLAUDE.md roadmap |

---

## Roadmap

- [x] Three-hook pipeline (UserPromptSubmit + PreToolUse + Stop)
- [x] Category-first MECE model (16 categories)
- [x] Three-component scoring (Relevance · Signal · Velocity)
- [x] MCP + Plugin support (glama, Anthropic official, community)
- [x] Hosted endpoint — dispatch.visionairy.biz, $10/month Pro
- [x] Daily catalog cron (16,500+ tools)
- [x] Admin + User dashboards, Stripe, Slack notifications
- [x] XFTC — Module 3 (session-based token hog nudges)
- [ ] Weekly category scoring cron (zero live API at hook time)
- [ ] skills.sh distribution (`npx skills add VisionAIrySE/Dispatch`)
- [ ] CC marketplace submission
- [ ] End-to-end live session test + recording

---

## Architectural Principles

**XSIA builds on XFBA. Always. No exceptions.**

XFBA is Stage 1 — catches contract violations (wrong type, broken import, bad arity). XSIA is Stage 5 — analyzes systemic impact (what else breaks when this change lands). If XFBA finds a violation, XSIA still runs but is marked "fix XFBA first." You cannot meaningfully analyze cascade impact on broken code. XFBA is the gate, XSIA is the consequence map.

Applies to new checkers too: any JSON/YAML/config schema checker belongs in XFBA. Any cascade or field-kill-field analysis belongs in XSIA. Build XFBA first, XSIA second.

---

## Architectural Principle Protocol

When a definition, dependency rule, or design invariant is discovered that would prevent a recurring class of mistake or guide future development — commit it to this file immediately, not just to memory.

**Triggers:** a question gets answered that shouldn't need answering again ("which builds on the other?"), a bug is traced to a missing rule ("XFBA doesn't cover JSON"), or a pattern is validated in production.

**Format:** one heading, one clear statement of the rule, one sentence on why, one sentence on how to apply it. No multi-paragraph essays — if it needs more, it goes in `~/.claude/ref/`.

---

## Reference Files (load on demand)

See `~/.claude/ref/dispatch-patterns.md` for:
- Haiku markdown-wrapped JSON stripping pattern
- Hook timeout budget (10s total)
- Bypass token behavior (120s TTL)
- state.json field reference
- Scoring formula + tool name prefix system
- Known issue history
