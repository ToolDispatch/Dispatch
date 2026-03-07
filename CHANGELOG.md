# Changelog

All notable changes to Dispatch are documented here.

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
