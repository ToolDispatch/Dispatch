# Dispatch Admin Guide

**For:** Russ Wright (Visionairy)
**Updated:** 2026-03-16

---

## Access Points

| Surface | URL | Auth |
|---------|-----|------|
| Admin dashboard | `https://dispatch.visionairy.biz/admin/dashboard?key=YOUR_ADMIN_KEY` | `ADMIN_KEY` env var in Render |
| User dashboard | `https://dispatch.visionairy.biz/dashboard?token=USER_TOKEN` | User's Dispatch token |
| Account page | `https://dispatch.visionairy.biz/account` | Session cookie (post-OAuth) |
| Token recovery | `https://dispatch.visionairy.biz/token-lookup` | GitHub OAuth |
| Stripe billing portal | `https://dispatch.visionairy.biz/portal` | Session cookie |

**`ADMIN_KEY`** is set in Render → Dispatch-API → Environment. If you get 401, check for trailing spaces in the env var value.

---

## Admin Dashboard Sections

### Overview Cards
- **Total Users** — all registered accounts
- **Pro Users** — paying subscribers; Founding users = $6/mo, standard = $10/mo
- **MRR** — monthly recurring revenue (mix of $6 founding + $10 standard)
- **New (7d)** — signups in the last 7 days

- **Total Detections** — all-time hook intercepts logged
- **Detections (24h)** — today's activity
- **Blocked (7d)** — intercepts where a better tool was found and blocked
- **Installs (7d)** — confirmed tool installations after a Dispatch suggestion (conversion events)

### CC Weakness Map
The most strategically valuable table. Shows where Claude Code's native tools score significantly lower than marketplace alternatives, based on real blocked intercepts.

| Column | Meaning |
|--------|---------|
| Category | MECE task category (e.g. `mobile`, `devops`, `testing`) |
| Avg CC Score | Claude Code's average score for its chosen tool in this category |
| Avg Market Score | Top marketplace alternative's average score |
| Gap | Difference — higher = bigger opportunity |
| Blocks | How many intercepts contributed to this row |

**Red gap (≥30):** Strong signal — marketplace has a significantly better tool for this category.
**Yellow (15–29):** Moderate gap.
**Green (<15):** CC tools are competitive.

This data is the Anthropic pitch: shows exactly where CC's native tools underperform, backed by behavioral data Anthropic cannot collect internally.

### Top Task Types
Bar chart of the most common task classifications Dispatch has detected across all users. Tells you what developers are actually working on.

### Top Installed Tools
Which marketplace tools users actually installed after a Dispatch recommendation. The conversion leaders.

### Creator Outreach
Total GitHub Issues opened asking tool creators to add descriptions to undescribed skills. Capped at 1 per repo per 30 days.

### Users Table
All registered users, sorted by last active. Columns:
- **Username** → links to GitHub profile (opens new tab)
- **Email** — captured from GitHub OAuth
- **Plan** — free or PRO (with upgrade date if Pro)
- **Usage** — detections used / monthly limit
- **Last Active** — last time a hook fired for this user
- **Joined** — registration date

---

## Managing User Plans

### Manually Gift Pro
Use this for coupons, beta users, or support resolutions:

```bash
curl -X POST https://dispatch.visionairy.biz/admin/set-plan \
  -H "Content-Type: application/json" \
  -d '{"username": "github-username", "plan": "pro", "key": "YOUR_ADMIN_KEY"}'
```

Returns `{"ok": true}` on success, 404 if user not found.

### Downgrade to Free
```bash
curl -X POST https://dispatch.visionairy.biz/admin/set-plan \
  -H "Content-Type: application/json" \
  -d '{"username": "github-username", "plan": "free", "key": "YOUR_ADMIN_KEY"}'
```

### Stripe
All billing is managed through Stripe. Users access the Stripe Customer Portal at `/portal`. You manage subscriptions at dashboard.stripe.com.

---

## Cron Jobs (Render)

### Catalog Cron — Daily
**Job:** `python3 -u catalog_cron.py`
**Schedule:** Daily (set in Render → Cron Jobs)
**What it does:**
1. Crawls **4 sources** across 3 tool types:
   - **Skills:** skills.sh marketplace — all 16 MECE categories, filter MIN_INSTALLS ≥ 20
   - **MCP (glama.ai):** searched by `mcp_search_terms` per category; safety filter (skip if no description AND no repo)
   - **MCP (Smithery.ai):** `registry.smithery.ai/servers` — `useCount ≥ 20` filter built-in at collection time
   - **MCP (Official registry):** `registry.modelcontextprotocol.io/v0/servers` — curated list, cursor-paginated
2. Deduplicates across all sources by tool name
3. Scores each tool (0–100 scale, log-normalized):
   - Skills: installs (60%) + stars (25%) + forks (15%)
   - MCPs with GitHub repo: stars/forks fetched via GitHub API, floor 20 (with desc) or 15 (without)
   - MCPs without GitHub repo: flat 35 (with desc) or 20 (without)
   - Staleness penalty: tools >18 months old capped at score 60
4. Upserts results into `tool_catalog` table (ON CONFLICT DO UPDATE — safe to run repeatedly)
5. Sends creator outreach GitHub Issues for skills with installs but no description (max 1/repo/30 days)
6. Fires Slack notification to `#dispatch-log` on completion

**Required env vars:** `DATABASE_URL`, `GITHUB_TOKEN`
**Optional:** `SLACK_LOG_WEBHOOK_URL`, `ANTHROPIC_API_KEY` (Tier 3 fallback), `OPENROUTER_API_KEY`

**Logs to check:** Render → Cron Jobs → select job → Logs. Look for:
```
[catalog_cron] Done. 312 tools upserted (247 skills, 65 MCPs), 3 outreach sent in 112.4s
```

### Manual Trigger
```bash
curl -s -X POST https://dispatch.visionairy.biz/admin/run-cron \
  -H "X-Admin-Key: YOUR_ADMIN_KEY"
```

Returns immediately: `{"status": "started", "message": "Catalog cron running in background..."}`.
Watch Render logs for progress and the completion summary.

### Known Cron Issues
- If `GITHUB_TOKEN` is missing, stars/forks will be 0 and scores will be lower quality
- GitHub token must have: Contents: Read, Issues: Read/Write (for creator outreach)
- `upsert_tools` uses `ON CONFLICT (name) DO UPDATE` — safe to run multiple times, no duplicates
- Smithery and official registry have no install data — scored via GitHub stats (stars/forks) or flat score
- pulsemcp.com has a gated API (requires key from hello@pulsemcp.com) — not yet integrated

---

## Slack Notifications

**Status: CONFIGURED ✅** — both webhooks active in Render.

| Channel | Webhook env var | Events |
|---------|----------------|--------|
| `#dispatch-log` | `SLACK_LOG_WEBHOOK_URL` | Signups, upgrades, downgrades, install conversions, daily cron summary |
| `#dispatch-queue` | `SLACK_QUEUE_WEBHOOK_URL` | n8n/OpenClaw marketing approval queue |

Events that fire to `#dispatch-log`:
- New user signup
- User upgraded to Pro (Founding or standard)
- User downgraded / subscription cancelled
- Install conversion (user installed a Dispatch-suggested tool)
- Daily cron completion summary

---

## Server Infrastructure

| Component | Details |
|-----------|---------|
| **Host** | Render (web service) |
| **Database** | Render PostgreSQL |
| **Deploy** | Auto-deploy on push to `main` in `VisionAIrySE/Dispatch-API` |
| **Workers** | gunicorn gthread, 2 workers × 4 threads |
| **Health check** | `GET /health` → `{"status": "ok"}` |

### Manual Redeploy
Render dashboard → Dispatch-API service → Manual Deploy → Deploy latest commit.

If deploy hangs >5 minutes: cancel and redeploy. Check Start Command is set to:
```
gunicorn app:app --worker-class gthread --workers 2 --threads 4 --timeout 30
```

### Required Environment Variables (Render)
| Variable | Purpose |
|----------|---------|
| `DATABASE_URL` | PostgreSQL connection string (auto-set by Render) |
| `SECRET_KEY` | Flask session secret |
| `GITHUB_CLIENT_ID` | OAuth app client ID |
| `GITHUB_CLIENT_SECRET` | OAuth app client secret |
| `STRIPE_SECRET_KEY` | Stripe live/test key |
| `STRIPE_PRICE_ID` | Pro plan price ID |
| `STRIPE_WEBHOOK_SECRET` | Stripe webhook signing secret |
| `ADMIN_KEY` | Protects `/admin/dashboard`, `/admin/set-plan`, `/admin/run-cron` |
| `GITHUB_REGISTRY_TOKEN` | Fine-grained PAT for API server (catalog enrichment, OAuth) |
| `GITHUB_TOKEN` | Fine-grained PAT for cron job (Contents: Read + Issues: Read/Write) |
| `ANTHROPIC_API_KEY` | Tier 3 LLM fallback (after OpenRouter) |
| `OPENROUTER_API_KEY` | Tier 1 LLM (free llama-3.1-8b-instruct — $0 cost for free tier) |
| `STRIPE_FOUNDING_PRICE_ID` | Founding Dispatcher plan ($6/mo, first 300 users) |
| `SLACK_LOG_WEBHOOK_URL` | Slack webhook for `#dispatch-log` ✅ configured |
| `SLACK_QUEUE_WEBHOOK_URL` | Slack webhook for `#dispatch-queue` ✅ configured |

---

## GitHub Repositories

| Repo | Purpose |
|------|---------|
| `VisionAIrySE/Dispatch` | Client — hooks, classifier, evaluator, install script |
| `VisionAIrySE/Dispatch-API` | Server — Flask API, DB, cron, dashboards |

### Client Modules (installed to `~/.claude/dispatch/`)

| Module | Purpose |
|--------|---------|
| `classifier.py` | Haiku shift detection — reads CC transcript, emits task type + preferred tool type |
| `evaluator.py` | Marketplace search + Haiku ranking — `search_by_category()`, `rank_recommendations()`, `recommend_tools()` (proactive recommendations with by_type grouping for Stage 3) |
| `interceptor.py` | PreToolUse logic — bypass token, state readers, tool type detection, `get/write_last_recommended_category()` (once-per-category gate for Stage 3) |
| `category_mapper.py` | Maps Haiku-generated task type labels to one of 16 MECE categories |
| `categories.json` | MECE category catalog with `search_terms` (skills.sh) and `mcp_search_terms` (glama.ai) |
| `llm_client.py` | LLM-agnostic adapter — OpenRouter-first (free tier uses llama-3.1-8b-instruct:free), falls back to Anthropic BYOK, noop on failure |
| `stack_scanner.py` | Detects languages, frameworks, tools, and MCP servers from project manifest files and `.mcp.json`; result stored in `stack_profile.json` |

Both have GitHub Actions CI (`.github/workflows/tests.yml`) that runs on push/PR to `main`. Requires `ANTHROPIC_API_KEY` secret set in each repo's Settings → Secrets → Actions.

---

## Common Issues

**"Unauthorized" on admin dashboard**
→ Check for trailing space in `ADMIN_KEY` in Render env var. Retype it manually.

**Cron job not running**
→ Render → Cron Jobs → verify schedule. Check logs for errors. Confirm `DATABASE_URL` and `GITHUB_TOKEN` are set.
→ To trigger manually: `curl -s -X POST https://dispatch.visionairy.biz/admin/run-cron -H "X-Admin-Key: YOUR_ADMIN_KEY"`

**User says they're not being intercepted**
→ Ask them to run `/dispatch status` in a CC session. Checks if hooks are installed and shows last task detected.

**User says proactive recommendations aren't appearing**
→ Stage 3 proactive recommendations require BYOK mode (`ANTHROPIC_API_KEY` set in their environment). Hosted Free and Pro server-side proactive support is planned (V2).
→ To verify they're in BYOK mode: `cat ~/.claude/dispatch/config.json` — should show `"mode": "byok"` or have API key configured.
→ If they're in Hosted mode, tell them proactive recommendations are coming V2. The intercept (Hook 2) still works.

**User hit free tier limit (8/day)**
→ They'll see quota errors. Direct to `/pro?token=TOKEN` or gift Pro via `/admin/set-plan`.

**Deploy stuck**
→ Cancel and manually redeploy. Verify Start Command in Render service settings.
