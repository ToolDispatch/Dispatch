# Dispatch Admin Guide

**For:** Russ Wright (Visionairy)
**Updated:** 2026-03-15

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
- **Pro Users** — paying subscribers; `Pro Users × $10 = MRR`
- **MRR** — monthly recurring revenue at $10/user
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
1. Crawls skills.sh marketplace for all 16 MECE categories
2. Scores each tool by installs (60%) + stars (25%) + forks (15%), log scale
3. Applies staleness penalty (tools >18 months old capped at score 60)
4. Upserts results into `tool_catalog` table
5. Sends creator outreach GitHub Issues for tools with installs but no description (max 1/repo/30 days)
6. Fires Slack notification to `#dispatch-log` on completion

**Required env vars:** `DATABASE_URL`, `GITHUB_TOKEN`
**Optional:** `SLACK_LOG_WEBHOOK_URL`

**Logs to check:** Render → Cron Jobs → select job → Logs. Look for:
```
[catalog_cron] Done. 247 tools upserted, 3 outreach sent in 87.3s
```

### Known Cron Issues
- If `GITHUB_TOKEN` is missing, stars/forks will be 0 and scores will be lower quality
- GitHub token must have: Contents: Read, Issues: Read/Write (for creator outreach)
- `upsert_tools` uses `ON CONFLICT (name) DO UPDATE` — safe to run multiple times, no duplicates

---

## Slack Notifications

**Status: NOT YET CONFIGURED** — code is written, waiting for webhook setup.

Once you create the Slack app and webhooks, add to Render env vars:
- `SLACK_LOG_WEBHOOK_URL` → `#dispatch-log` (product ops events)
- `SLACK_QUEUE_WEBHOOK_URL` → `#dispatch-queue` (n8n/OpenClaw marketing approval)

Events that fire to `#dispatch-log`:
- New user signup
- User upgraded to Pro
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
| `ADMIN_KEY` | Protects `/admin/dashboard` and `/admin/set-plan` |
| `GITHUB_TOKEN` | Fine-grained PAT for cron (Contents: Read + Issues: Read/Write) |
| `ANTHROPIC_API_KEY` | Used by classifier for BYOK fallback ranking |
| `SLACK_LOG_WEBHOOK_URL` | Slack webhook for `#dispatch-log` (optional) |
| `SLACK_QUEUE_WEBHOOK_URL` | Slack webhook for `#dispatch-queue` (optional) |

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
| `evaluator.py` | Marketplace search + Haiku ranking — `search_by_category()`, `rank_recommendations()` |
| `interceptor.py` | PreToolUse logic — bypass token, state readers, tool type detection |
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

**User says they're not being intercepted**
→ Ask them to run `/dispatch status` in a CC session. Checks if hooks are installed and shows last task detected.

**User hit free tier limit (8/day)**
→ They'll see quota errors. Direct to `/pro?token=TOKEN` or gift Pro via `/admin/set-plan`.

**Deploy stuck**
→ Cancel and manually redeploy. Verify Start Command in Render service settings.
