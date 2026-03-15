# Dispatch User Guide

**Dispatch** — runtime skill router for Claude Code. Watches your work, intercepts tool calls when a better marketplace tool exists, and surfaces it before Claude proceeds.

---

## Getting started

### 1. Install

```bash
git clone https://github.com/VisionAIrySE/Dispatch.git
cd Dispatch
bash install.sh
```

`install.sh` takes ~2 minutes. It:
- Checks Python 3.8+ and Node.js are available
- Registers two hooks in `~/.claude/settings.json`
- Asks whether you want Hosted (free token) or BYOK (your own Anthropic key)

### 2. Get a free token (Hosted mode)

When `install.sh` asks for a token, visit:

```
https://dispatch.visionairy.biz/auth/github
```

Sign in with GitHub. Copy the token shown on screen and paste it into the install prompt.

**Already installed and need your token?** Visit `https://dispatch.visionairy.biz/token-lookup` — it re-runs OAuth and shows your token again.

### 3. Start a new CC session

**Critical:** hooks load at session startup. The install won't affect your current session. Open a new terminal and run `claude` (or restart your IDE's CC session).

### 4. Verify it's running

In the new session, type:

```
/dispatch status
```

You'll see your mode, plan, token (masked), and whether both hooks are installed. If a hook shows MISSING, re-run `bash install.sh`.

---

## What happens during a session

Most of the time, Dispatch is silent. Here's what's actually running:

**Every message you send** — Hook 1 runs (~100ms). It reads your last few messages and checks if you've shifted to a different type of task. If you haven't shifted, it exits immediately. If you have, it maps the shift to a category and saves it to state.

**Every tool call Claude makes** — Hook 2 runs before Claude uses a Skill, Agent, or MCP tool. It checks the marketplace for tools relevant to your current task. If it finds one that scores 10+ points higher than what Claude was about to use, it blocks and shows you the comparison.

---

## When Dispatch intercepts

You'll see something like this in your session:

```
[DISPATCH] Intercepted: CC is about to use 'superpowers:systematic-debugging' for Flutter Fixing.
CC's tool score for this task: 62/100

Marketplace alternatives:
  1. flutter-mobile-app-dev [94/100] ← TOP PICK
     Why: Purpose-built for Flutter/Dart debugging with widget tree inspection.
     Install: npx skills add flutter-mobile-app-dev -y && claude

⚠ A marketplace tool scores higher than 'superpowers:systematic-debugging' for this task.
  Options:
  1. Say 'proceed' to continue with the current tool
  2. Install flutter-mobile-app-dev (run /compact first, then install and restart CC)
  3. Say 'skip dispatch' to ignore this task type for the rest of the session
```

### Your three options

**1. Say `proceed`**
Claude uses its original tool choice. The bypass lasts for this one tool call. If Claude reaches for the same tool again, Dispatch will check again (unless you say `skip dispatch`).

**2. Install the recommended tool**
```bash
/compact          # saves your session context
npx skills add flutter-mobile-app-dev -y
claude            # restart — picks up where you left off
```
The tool is now available to Claude for future sessions.

**3. Say `skip dispatch`**
Dispatch ignores this task type for the rest of the current session. Use this when you've already got the right tools for the job and don't need suggestions.

---

## Check your status

```
/dispatch status
```

Shows:
- **Mode** — hosted, byok, or unconfigured
- **Plan** — free or pro
- **Token** — masked display
- **Hook 1 / Hook 2** — installed or MISSING
- **Last task** — most recent task type Dispatch classified
- **Category** — which of the 16 MECE categories it mapped to
- **Working dir** — where the last shift was detected
- **Bypass** — whether a bypass token is currently active

---

## Your account

**Account page:** `https://dispatch.visionairy.biz/account`
- See your plan and quota
- Copy your token
- Manage billing (Pro users get a Stripe portal link)

**Dashboard (Pro):** `https://dispatch.visionairy.biz/dashboard?token=YOUR_TOKEN`
- Interception history
- Block rate
- Top tools suggested
- Install conversions (tools you installed after a suggestion)

**Upgrade to Pro:** `https://dispatch.visionairy.biz/pro?token=YOUR_TOKEN`
- $10/month — unlimited interceptions, Sonnet ranking, pre-ranked catalog, full dashboard

---

## Plans at a glance

| | Free | Pro |
|---|---|---|
| Interceptions/day | 8 | Unlimited |
| Ranking model | Haiku | Sonnet |
| Catalog | Live search (~2–4s) | Pre-ranked (<200ms) |
| Dashboard | Upgrade teaser | Full history + stats |
| Cost | Free | $10/month |

---

## Troubleshooting

**Nothing is happening / Dispatch is silent**

This is usually correct — Dispatch only intercepts when the gap is 10+ points. To check it's actually running:
1. Type `/dispatch status` — verify both hooks show "installed"
2. Make sure you're in a **new** CC session started after install
3. Check `~/.claude/settings.json` — look for `UserPromptSubmit` and `PreToolUse` hook entries

**"UserPromptSubmit hook error" in the sidebar**

Harmless cosmetic message. Dispatch exits cleanly on any error — it never blocks Claude. This can appear when running CC in a directory that isn't a development project (e.g. the Dispatch directory itself). Doesn't affect functionality.

**Hook fires but always passes through**

Working correctly. Dispatch only blocks when a marketplace alternative scores 10+ points higher. If the tools Claude is reaching for are already well-matched to your task, you won't see intercepts.

**I'm getting too many intercepts**

Say `skip dispatch` to suppress for the rest of the session. Or increase the gap threshold by editing `SCORE_GAP_THRESHOLD` in `~/.claude/hooks/dispatch-preuse.sh` (default: 10).

**Slow intercepts (2–4 seconds)**

On Free/BYOK, Dispatch hits the live marketplace on each intercept. This is expected. Pro users get <200ms responses from the pre-ranked catalog.

**"Degraded mode" during install**

The `anthropic` Python package couldn't be imported. Usually a system Python/PEP 668 issue. Fix:
```bash
pip3 install anthropic --break-system-packages
# or use a virtual environment
```

**Lost your token**

Go to `https://dispatch.visionairy.biz/token-lookup` — signs you in with GitHub and shows your token.

**Want to uninstall**

```bash
bash uninstall.sh
```

Removes all files, hook scripts, and settings.json entries automatically.

---

## Privacy

**BYOK mode:** all Haiku calls go directly from your machine to Anthropic. Nothing passes through Dispatch servers.

**Hosted mode:** your last ~3 messages and working directory path are sent to `dispatch.visionairy.biz` for classification and immediately discarded. We store your GitHub username, task type labels (e.g. `flutter-fixing`), and tool scores. We do not store conversation content.

Full privacy table in [README](../README.md#privacy). To delete your account, email dispatch@visionairy.biz.

---

## Getting more from Dispatch

Add the official plugin marketplaces for broader search coverage:

```
/plugins add anthropics/claude-plugins-official
/plugins add ananddtyagi/claude-code-marketplace
```

Browse skills relevant to your stack:

```bash
npx skills find flutter
npx skills find supabase
npx skills find nextjs
```

The more relevant tools are installed and registered, the more often Dispatch has useful alternatives to surface.
