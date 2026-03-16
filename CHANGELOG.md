# Changelog

All notable changes to Dispatch are documented here.

---

## v0.9.1 — 2026-03-15

### Added

- **`/dispatch status` skill** — shows mode, plan, token (masked), hook install state, last task type, category, working dir, and bypass token status.
- **Conversion tracking** — `write_last_suggested` records the tool Dispatch recommended; `was_installed` events fire when the user installs that tool. Feeds Pro dashboard.
- **Creator outreach** — daily catalog cron opens GitHub Issues on undescribed skills (max 1/repo/30 days) asking creators to add a description.
- **Slack notifications** — signup, upgrade, downgrade, conversion, and daily cron completion events fire to `#dispatch-log`.
- **Admin dashboard** — CC Weakness Map (avg CC score vs market score by category), MRR, user table, top task types, top installed tools, creator outreach count.
- **User dashboard (Pro)** — interception history, block rate, top suggested tools, install conversion tracking.

### Fixed

- Atomic writes for all `state.json` mutations (BUG-001/003).
- `dispatch-preuse.sh` and `dispatch.sh` were writing/reading `state.json` in different directories. Fixed by syncing installed hook path to `~/.claude/dispatch/`.
- `_strip_fences` now handles newline-separated JSON markers.

---

## v0.9.0 — 2026-03-14

### Added

- **Two-tier ranking** — Pro users get pre-ranked catalog results (<200ms). Free/BYOK users get live marketplace search (~2–4s).
- **Bypass event logging** — when user says "proceed", the bypass is logged to `/api/detections` in hosted mode for analytics.
- `npx` subprocess replaced with skills.sh HTTP API in `_search_one_term` — removes Node.js dependency from the ranking hot path.

---

## v0.8.0 — 2026-03-13

### Added

- **MCP/plugin tool type system** — Dispatch now distinguishes `skill`, `mcp`, and `agent` tool types. Classifier emits `preferred_tool_type` hint. `interceptor.py` tracks `last_cc_tool_type`. Scoring is type-aware.
- **Glama.ai MCP search** — `evaluator.py` searches glama.ai for MCP servers using `mcp_search_terms` from `categories.json` (service vocabulary like `postgres`, `github` rather than task names).
- **Official + community plugins** — evaluator searches the official Claude plugin registry and community plugins. Prefixes: `plugin:anthropic:name`, `plugin:cc-marketplace:name`.
- **`llm_client.py`** — LLM-agnostic adapter. OpenRouter-first (free tier uses `llama-3.1-8b-instruct:free` at $0 cost). Falls back to Anthropic BYOK. Noop on failure.
- **`stack_scanner.py`** — detects languages, frameworks, tools, and MCP servers from manifest files (`package.json`, `requirements.txt`, `go.mod`, `Cargo.toml`, `pubspec.yaml`, etc.) and `.mcp.json`. Writes `stack_profile.json` to `~/.claude/dispatch/`.
- **Stack-aware catalog filtering** — already-installed MCP servers are excluded from recommendations. Pro catalog results boosted by stack profile match.
- **`normalize_tool_name_for_matching()`** in `interceptor.py` — handles conversion tracking across prefixed and unprefixed tool name formats.
- **SKILL.md and `.claude-plugin/plugin.json`** — enables distribution via skills.sh marketplace and Claude plugin registry.
- **`install.sh` hardening** — first-run indicator in `state.json`, `/dev/tty` fallback for terminal output, copies `llm_client.py` and `stack_scanner.py`.

### Changed

- `categories.json` extended with `mcp_search_terms` alongside existing `search_terms`.
- `catalog_by_id` lookup handles both prefixed and unprefixed key formats.

---

## v0.7.0 — 2026-03-14

### Added

- **PreToolUse interception** — `preuse_hook.sh` fires before every Skill, Agent, or MCP tool call. If a marketplace alternative scores 10+ points higher than Claude's chosen tool, it blocks (exit 2) and shows the ranked comparison.
- **Category-first model** — 16 MECE categories. Haiku generates a task type label; `category_mapper.py` maps it to a category. Marketplace search uses the category's `search_terms` rather than splitting the task type string directly.
- **`category_mapper.py`** — keyword-based mapping from open-ended Haiku task labels to MECE category IDs. Unknown task types logged to `unknown_categories.jsonl`.
- **`categories.json`** — MECE 16-category catalog with per-category search terms.
- **`interceptor.py`** — PreToolUse tool parsing, bypass token (TTL 120s), state reader helpers.
- **Bypass token** — written before exit 2; consumed on the next matching tool call so "proceed" passes through without re-blocking.

### Changed

- `dispatch.sh` is now silent — Stage 1 (Haiku classification) and state write only. All UI output moved to `preuse_hook.sh`.
- `build_recommendation_list` is marketplace-only; `cc_score` passed through as baseline for comparison.

---

## v0.6.0 — 2026-03-08

### Added

- **Full discovery mode** — evaluator searches all 16 MECE category terms in parallel when no prior task state exists. Ensures cold-start sessions still surface relevant tools.
- **Stack scanner improvements** — broader manifest file coverage, MCP server detection from `.mcp.json`.

---

## v0.5.0 — 2026-03-07

### Added

- **Multi-term compound task type search** — when Haiku returns a compound label like `docker-aws-github-actions`, all terms are searched against the registry and deduplicated. Previously only the primary term was used.
- **MCP server scanning** — reads installed MCP servers from `.mcp.json` in the working directory. Already-installed MCPs excluded from recommendations.
- **Score gap truncation** — 25-point cliff: if the best marketplace alternative scores more than 25 points above the next-best, the gap is truncated to prevent a single outlier dominating the list.
- **Sonnet for Pro tier ranking** — Pro users get Sonnet scoring for sharper relevance judgements and better one-line reasons. Free/BYOK uses Haiku.
- **Rich descriptions** — evaluator passes full tool descriptions (not just names) to the ranker. Reasons are grounded in actual tool capabilities.

### Changed

- Registry search now uses all category `search_terms` (up to 5 per category), deduplicated. More recall, same precision threshold.

---

## v0.4.0 — 2026-03-07

### Added

- **Collective ranking with scores** — All available tools (installed and marketplace) are now ranked together on a 0-100 scale. Haiku evaluates them as one pool against the specific task context, not as separate lists. Score reflects relevance to what you're actually doing right now.
- **Numbered selection list** — Output is a ranked numbered list. The TOP PICK is marked. Claude announces it explicitly, explains why in one sentence, and asks if you want something else before proceeding.
- **Install + restart in one command** — Each uninstalled tool shows a combined `npx skills add ... && claude` command. Copy it, paste it in your terminal — installs the tool and relaunches CC in one step.
- **GitHub URL for uninstalled tools** — Each uninstalled skill shows a `More info:` GitHub URL derived from the skill ID. No searching required.
- **Pre-install guidance** — When the top pick isn't installed, Dispatch suggests running `/compact` to save session context before restarting. Your session transcript path is also shown for reference.

### Changed

- **`build_recommendation_list` return format** — Now returns `{all, top_pick, installed, suggested}`. `installed` and `suggested` are derived from `all` for backward compatibility. `top_pick` is the highest-scored item.
- **Marketplace shown in status** — Installed tools now show `(installed via marketplace-name)` instead of just `(installed)`.
- **Score threshold** — Only tools with relevance score >= 40 are shown. Irrelevant tools are excluded entirely rather than ranked low.

---

## v0.3.0 — 2026-03-07

### Added

- **Contextual "why" in recommendations** — Dispatch now passes the last 3 conversation messages to Haiku during ranking. Each recommendation includes a one-line reason grounded in what the user is actually working on (e.g., "you're setting up Stripe webhooks" instead of generic descriptions).
- **`recommendations_log` table** — Every confirmed shift now logs `(token, task_type, recommended_tools, context_snippet, created_at)` to Postgres for analytics.
- **`/analytics` endpoint (Pro only)** — Returns per-user recommendation history: top task types, most-recommended tools, detection count by day. 401 on missing token, 403 on free plan, 200 + JSON on Pro.
- **Free tier increased to 8 detections/day** — Up from 5. Enough for a full day of natural task switching without hitting the wall.

### Changed

- **stdout injection replaces `/dev/tty`** — Hook output now writes directly to stdout via the `stopReason: block` + `hookSpecificOutput` JSON protocol. Eliminates the terminal race condition where recommendations appeared garbled or interleaved with Claude's response. Output is clean and deterministic in both CLI and TUI modes.
- **Word threshold changed to `< 3`** — Previously `< 4`. Messages of exactly 3 words now pass through to Haiku classification instead of being skipped. Catches short but meaningful task shifts like "fix the crash".
- **BYOK fallback updated to 5-field format** — Local classifier now returns `shift`, `domain`, `mode`, `task_type`, and `confidence` (matching hosted format). Previously returned 3 fields, causing evaluator mismatches when running without a token.

### Removed

- **CLAUDE.md modification removed from `install.sh`** — Install no longer appends the notification instruction to `~/.claude/CLAUDE.md`. The pending_notification.json mechanism handles context injection without modifying user config files.
- **`mcp.json` API key reading removed** — Dispatch no longer attempts to read `ANTHROPIC_API_KEY` from `.mcp.json`. Key must be set as an environment variable. Removes an unintended credential access path.

---

## v0.2.0 — 2026-03-06

### Added

- **Action mode detection** — Dispatch now fires on mode shifts within the same domain, not just domain changes. Moving from `flutter-building` to `flutter-fixing` triggers a shift. 7 MECE action modes: `discovering`, `designing`, `building`, `fixing`, `validating`, `shipping`, `maintaining`.
- **Semantic mode classification** — Detection uses Claude Haiku with natural language understanding, not keywords. "This blows up with a null" → `fixing`. "Let me sanity check this" → `validating`.
- **5-field classifier output** — Classifier now returns `shift`, `domain`, `mode`, `task_type` (compound `domain-mode` format), and `confidence`. Terminal renders `Flutter Fixing` instead of just `Flutter`.
- **pending_notification.json** — Hook writes a notification file on confirmed shifts. Claude reads it at response start, surfaces recommendations inline, and pauses to ask before proceeding. Works in both CLI and TUI modes.
- **Auto CLAUDE.md setup** — `install.sh` now appends the Dispatch notification instruction to `~/.claude/CLAUDE.md` automatically.
- **ANSI color improvements** — Terminal output: task type in cyan bold, installed tools in green (`+`), suggested in yellow (`↓`), confidence shown as `high`/`medium` label.

### Changed

- **Shift detection broadened** — A shift now triggers on domain change OR mode change within same domain. Previously only domain changes counted.
- **No more 3-second pause** — Notification stays in scroll buffer; user can scroll back anytime. Removed the blocking wait.
- **Claude pauses for recommendations** — Instead of barelling forward, Claude asks if you want to install or explore suggested tools before continuing.

### Fixed

- `extract_recent_messages` now reads CC transcript format correctly — `role` is nested at `entry['message']['role']`, not top-level. Dispatch was silently not firing due to this (BUG-022).
- `isMeta=True` entries (skill file text) and `[{` strings (tool results) excluded from Haiku context (BUG-023).
- Haiku markdown-wrapped JSON responses stripped before `json.loads()`.
- Compound task types (`docker-aws-github-actions`) now use only primary term for registry search.
- Shell injection via TASK_TYPE fixed — passed as `sys.argv`, never interpolated.
- `head -n -1` (GNU-only) replaced with `sed '$d'` for macOS compatibility.
- 402 limit-reached response now only fires on confirmed shifts, not on every message after limit hit.
- 3s wait removed (no longer blocks Claude).
- Invalid token (401) shows re-auth URL with cooldown; no longer silent.
- `/rank` failure falls back to local BYOK ranking instead of returning empty.
- `settings.json` malformed JSON now handled gracefully during install.
- gunicorn switched to gthread workers for better concurrency on Render.

---

## v0.1.0 — 2026-03-05

### Added

- Initial release
- Two-stage `UserPromptSubmit` hook: classify (Haiku, every message) + evaluate/rank (on confirmed shift only)
- Hosted endpoint at dispatch.visionairy.biz — free tier 5 detections/day, Pro at $6/month
- GitHub OAuth for hosted mode — no API key required
- BYOK mode — run with your own `ANTHROPIC_API_KEY`, no server, no data sharing
- Plugin scanning — reads `~/.claude/plugins/marketplaces/` and `npx skills list`
- Registry search via skills.sh — discovers uninstalled skills automatically
- Haiku ranking of results — top 4 installed + top 3 suggested
- Curated registry for Pro users — hand-picked, tested recommendations per stack
- Stripe integration — $6/month Pro plan with webhook-based plan management
- Rate limiting — 30 req/min per token on `/classify` and `/rank`
- Daily reset on free tier usage count
- `install.sh` — single-command install, hook registration, token setup
- `state.json` — persists last task type across sessions
- npx cache — 1hr TTL to avoid hitting registry on every evaluation
