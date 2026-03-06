# Dispatch — Claude Code Configuration

**Project:** Dispatch — Runtime skill router for Claude Code
**Repo:** github.com/VisionAIrySE/Dispatch
**Stack:** Python 3.8+ · Bash · Claude Haiku API

---

## Architecture

Two-stage UserPromptSubmit hook:

**Stage 1 — classifier.py** (every message, ~100ms)
- Haiku call with last 3 transcript messages + cwd
- Returns `{"shift": bool, "task_type": str, "confidence": float}`
- Exits silently if no shift or confidence < 0.7
- Task type is open-ended (not a fixed list) — Haiku generates the most specific label it can

**Stage 2 — evaluator.py** (on confirmed shift only)
- Scans `~/.claude/plugins/marketplaces/` for installed plugins (extracts marketplace name from path)
- Runs `npx skills list -g` for installed agent skills (cached 1hr in npx_cache.json)
- Runs `npx skills find <primary_term>` for registry search (also cached)
- Haiku ranks all results by relevance, returns top 4 installed + top 3 suggested
- Post-ranking: enriches installed items with marketplace name for display

**Hosted mode (token in config.json):**
- Stage 1: POSTs transcript to /classify endpoint; quota consumed only on confirmed shifts
- Stage 2: sends locally-scanned plugins/skills to /rank; falls back to BYOK ranking on non-200
- 402 (limit reached): shown once with upgrade URL, suppressed for next 5 shifts via limit_cooldown
- 401 (invalid token): shown once with re-auth URL, suppressed for next 20 messages via auth_invalid_cooldown

**dispatch.sh** — orchestrates Stage 1 + 2, renders UI, updates state.json
- 3s wait only fires when there are actual recommendations (skipped on "no skills found")
- Trap cleans up mktemp tmpfiles on any exit

---

## Key Files

| File | Purpose |
|------|---------|
| `classifier.py` | Haiku shift detection + task classification |
| `evaluator.py` | Plugin inventory + Haiku ranking |
| `dispatch.sh` | Main hook — orchestrates everything |
| `install.sh` | Copies files, registers hook in settings.json |
| `test_classifier.py` | 9 unit tests for classifier |
| `test_evaluator.py` | 13 unit tests for evaluator |

**Installed location:** `~/.claude/skill-router/` (classifier.py, evaluator.py)
**Hook location:** `~/.claude/hooks/skill-router.sh`
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
- Stage 1 (Haiku): ~500ms
- Stage 2 (npx + Haiku): ~3-5s
- UI wait: 3s
- npx timeout set to 6s, not 20s

**Compound task types** — Classifier may return `docker-aws-github-actions`. Registry search uses only the primary term (`docker`) via `.split("-")[0]`.

**Broad exception catches are intentional** — Hook must never block Claude. Every function returns a safe default on failure.

**Task type is open-ended** — Haiku generates descriptive labels like `react-native`, `langchain`, `github-actions`. Not a fixed list. New skills in the registry are auto-discoverable.

**TASK_TYPE passed as argv, not interpolated** — Prevents shell injection. Always use `sys.argv[n]` in inline Python, never `'$TASK_TYPE'`.

**`head -n -1` is GNU-only** — BSD head on macOS interprets it as "print 1 line". Use `sed '$d'` (delete last line) for portable HTTP body extraction.

---

## Testing

```bash
cd ~/.claude/skill-router
python3 -m pytest test_classifier.py test_evaluator.py -v
```

All 22 tests must pass before pushing.

**Live test:** Requires a new CC session. Cannot simulate UserPromptSubmit from inside a session.

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
cp classifier.py evaluator.py ~/.claude/skill-router/
cp dispatch.sh ~/.claude/hooks/skill-router.sh
```

install.sh handles this automatically for fresh installs.

---

## Known Issues / History

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

---

## Roadmap

- [x] Hosted endpoint — live at dispatch.visionairy.biz, $6/month Pro
- [x] Caching layer for plugin registry (npx_cache.json, 1hr TTL)
- [ ] End-to-end live session testing + screen recording for promotion
- [ ] `/dispatch status` command
- [ ] skills.sh distribution
