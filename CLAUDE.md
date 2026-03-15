# Dispatch — Claude Code Configuration

**Project:** Dispatch — Runtime skill router for Claude Code
**Repo:** github.com/VisionAIrySE/Dispatch
**Stack:** Python 3.8+ · Bash · Claude Haiku API (free) / Sonnet 4.6 (Pro)

---

## Architecture

Two-hook pipeline:

**Hook 1 — dispatch.sh** (UserPromptSubmit, fires on every message)
- Stage 1: Haiku shift detection, ~100ms — returns `{shift, task_type, confidence}`
- Stage 2 (on confirmed shift only): maps task_type → category via `category_mapper.py`
  keyword match against `categories.json`; logs unknown categories to `unknown_categories.jsonl`;
  writes `last_task_type`, `last_category`, `last_context_snippet`, `last_cwd` to `state.json`
- No stdout output — completely silent

**Hook 2 — preuse_hook.sh** (PreToolUse, fires before tool invocations)
- Intercepts: `Skill`, `Agent`, `mcp__*` tool calls — passes through everything else
- Reads task category from `state.json` (written by dispatch.sh)
- Searches marketplace by category terms (more targeted than keyword split)
- Scores marketplace tools vs CC's chosen tool (Haiku/Sonnet 0–100)
- Blocks (exit 2) if top marketplace tool ≥ cc_score + 10 points
- Writes bypass token so user's "proceed" passes through without re-block

**Hosted mode (token in config.json):**
- dispatch.sh: POSTs transcript to /classify — quota on confirmed shifts only
- preuse_hook.sh: POSTs `{task_type, context_snippet, cc_tool, category_id}` to /rank
- Fallback to BYOK ranking on non-200 from either endpoint
- 402 / 401 cooldown handling preserved

**Key modules:**
- `classifier.py` — Haiku shift detection
- `evaluator.py` — `search_by_category()`, `rank_recommendations()`, `build_recommendation_list()`
- `interceptor.py` — tool intercept logic, bypass token, state readers
- `category_mapper.py` — `map_to_category()`, `log_unknown_category()`
- `categories.json` — MECE 16-category catalog

---

## Key Files

| File | Purpose |
|------|---------|
| `classifier.py` | Haiku shift detection + task classification |
| `evaluator.py` | Category search + Haiku ranking |
| `interceptor.py` | PreToolUse tool parsing, bypass token, state readers |
| `category_mapper.py` | Maps task_type → category_id; logs unknowns |
| `categories.json` | MECE category catalog (16 categories) |
| `dispatch.sh` | UserPromptSubmit hook — shift detection + state write |
| `preuse_hook.sh` | PreToolUse blocking hook — intercepts and scores |
| `install.sh` | Copies files, registers both hooks in settings.json |
| `test_classifier.py` | 19 unit tests for classifier |
| `test_evaluator.py` | 39 unit tests for evaluator |
| `test_interceptor.py` | 22 unit tests for interceptor |
| `test_category_mapper.py` | 13 unit tests for category_mapper |

**Installed location:** `~/.claude/skill-router/` (classifier.py, evaluator.py, interceptor.py, category_mapper.py, categories.json)
**Hook 1:** `~/.claude/hooks/skill-router.sh` (UserPromptSubmit)
**Hook 2:** `~/.claude/hooks/preuse-hook.sh` (PreToolUse)
**State:** `~/.claude/skill-router/state.json`

---

## Critical Patterns

**Haiku returns markdown-wrapped JSON** — Always strip code blocks before `json.loads()`:
```python
text = response.content[0].text.strip()
if text.startswith("```"):
    text = text.split("```")[1]
    if text.startswith("json"):
        text = text[4:]
return json.loads(text.strip())
```

**Hook timeout is 10 seconds total** — Budget carefully:
- dispatch.sh Stage 1 (Haiku): ~500ms
- preuse_hook.sh Stage 2 (registry + Haiku): ~3-5s
- npx timeout set to 6s, not 20s

**Compound task types** — Classifier may return `docker-aws-github-actions`. `search_by_category()` uses all category search_terms (up to 5), deduplicated. Primary term used for state tracking.

**Broad exception catches are intentional** — Hook must never block Claude. Every function returns a safe default on failure.

**Task type is open-ended** — Haiku generates descriptive labels like `react-native`, `langchain`, `github-actions`. Not a fixed list. `category_mapper.py` maps these to one of 16 MECE categories by keyword match.

**TASK_TYPE passed as argv, not interpolated** — Prevents shell injection. Always use `sys.argv[n]` in inline Python, never `'$TASK_TYPE'`.

**`head -n -1` is GNU-only** — BSD head on macOS interprets it as "print 1 line". Use `sed '$d'` (delete last line) for portable HTTP body extraction.

**Bypass token TTL is 120s** — Written by preuse_hook.sh before exit 2, consumed on the very next Skill/Agent/mcp__ call. Clears itself after use.

---

## Testing

```bash
cd /home/visionairy/Dispatch
python3 -m pytest test_classifier.py test_evaluator.py test_interceptor.py test_category_mapper.py -v
```

All 93 tests must pass before pushing (19 classifier + 39 evaluator + 22 interceptor + 13 category_mapper).

**Live test:** Requires a new CC session. Cannot simulate UserPromptSubmit or PreToolUse from inside a session.

**Manual classifier test:**
```bash
ANTHROPIC_API_KEY=sk-ant-... python3 classifier.py \
  --transcript /path/to/transcript.jsonl \
  --cwd /your/project \
  --last-task-type firebase
```

---

## Install / Sync

After editing source files, sync to installed location:
```bash
cp classifier.py evaluator.py interceptor.py category_mapper.py categories.json ~/.claude/skill-router/
cp dispatch.sh ~/.claude/hooks/skill-router.sh
cp preuse_hook.sh ~/.claude/hooks/preuse-hook.sh
```

install.sh handles this automatically for fresh installs.

---

## CC Transcript Format — Critical

CC transcript JSONL entries are `{"type":"user", "isMeta":bool, "message":{"role":"user","content":"..."}, ...}`.

- `role` is nested inside `message`, NOT at top level — `entry.get("role")` always returns `None`
- `isMeta=True` entries are CC system messages (loaded skill file text, tool responses) — exclude them
- String content starting with `[{` is a serialized tool result — exclude it
- `userType` is always `"external"` — cannot distinguish real user messages from tool results this way

`extract_recent_messages` handles all three cases. Do not revert these filters.

## Known Issues / History

- **2026-03-14:** v0.7.0 — PreToolUse interception added. dispatch.sh now silent (Stage 1 + state write only). preuse_hook.sh intercepts Skill/Agent/mcp__* calls, scores marketplace alternatives vs CC's chosen tool, blocks on 10+ point gap. Category-first model: task_type maps to MECE category for targeted search. Unknown categories logged to unknown_categories.jsonl.
- **2026-03-05:** Haiku markdown wrapping bug — fixed in classifier.py and evaluator.py
- **2026-03-05:** Compound task types broke registry search — fixed with primary term split
- **2026-03-05:** Shell injection via TASK_TYPE — fixed with argv passing
- **2026-03-05:** Open-ended taxonomy — removed fixed task type list, Haiku now generates labels freely
- **2026-03-05:** Hook UI invisible (stdout vs stderr) — all UI output to stderr
- **2026-03-05:** 402 fired on every message when limit hit — server now only charges on confirmed shifts
- **2026-03-05:** Unbound $TASK_TYPE crashed hook after 402 display — fixed with ${LAST_TASK_TYPE:-}
- **2026-03-05:** Server evaluator used npx (unavailable on Render) — replaced with skills.sh HTTP API
- **2026-03-05:** Hosted /rank never sent client installed plugins — fixed in Stage 2 payload
- **2026-03-05:** 3s wait fired even with "no skills found" — gated on HAS_RECS check
- **2026-03-05:** Tmpfile leak on unexpected exit — trap EXIT added
- **2026-03-05:** Invalid token gave no indication — 401 handler with auth_invalid_cooldown
- **2026-03-05:** Marketplace name missing from installed plugin display — extracted from path, shown as "(via marketplace)"
- **2026-03-05:** /rank failure silently returned empty — fallback to BYOK local ranking added
- **2026-03-05:** settings.json malformed JSON crashed install — wrapped in try/except
- **2026-03-05:** `head -n -1` (GNU-only) broke HTTP parsing on macOS — replaced with `sed '$d'`
- **2026-03-05:** `pip3 install` in install.sh could fail without sudo — changed to `python3 -m pip install --user`
- **2026-03-05:** Token string-interpolated into Python source in install.sh — changed to sys.argv
- **2026-03-05:** /rank endpoint missing rate limit — matched to /classify (30/min)
- **2026-03-05:** DB error in check_and_increment returned (False,0,0) → false 402 — returns (None,0,0) → 500
- **2026-03-05:** Concurrent OAuth completions caused UniqueViolation — replaced SELECT+INSERT with upsert
- **2026-03-05:** admin set-plan silently succeeded on unknown username — now returns 404
- **2026-03-05:** Flask session cookies lacked Secure/SameSite flags — SESSION_COOKIE_SECURE/HTTPONLY/SAMESITE=Lax
- **2026-03-05:** gunicorn single sync worker — switched to gthread 2 workers × 4 threads (Procfile)
- **2026-03-05:** `extract_recent_messages` read `entry['role']` — CC nests role at `entry['message']['role']` — Dispatch never fired (BUG-022) — fixed client + server, deployed
- **2026-03-05:** `extract_recent_messages` included isMeta entries (skill text) and `[{` strings (tool results) as user messages — polluted Haiku context (BUG-023) — filtered out

---

## Roadmap

- [x] Hosted endpoint — live at dispatch.visionairy.biz, $10/month Pro
- [x] Caching layer for plugin registry (npx_cache.json, 1hr TTL)
- [x] Collective 0–100 ranked list with TOP PICK + install info (v0.4.0)
- [x] Rich descriptions fed to ranker — grounded reasons (v0.5.0)
- [x] Multi-term compound task type search (v0.5.0)
- [x] MCP server scanning from .mcp.json (v0.5.0)
- [x] Score gap truncation — 25-point cliff (v0.5.0)
- [x] Sonnet for Pro tier ranking (v0.5.0)
- [x] PreToolUse interception — blocks on 10+ point gap (v0.7.0)
- [x] Category-first model — MECE 16-category catalog (v0.7.0)
- [ ] Daily catalog cron — crawl all sources, build enriched tool_catalog.json (v0.8.0)
- [ ] Weekly category scoring cron — zero live API calls at hook time (v0.8.0)
- [ ] End-to-end live session testing + screen recording for promotion
- [ ] `/dispatch status` command
- [ ] skills.sh distribution
