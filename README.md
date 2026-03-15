<p align="center">
  <img src="Dispatch Icon.png" alt="Dispatch" width="120" />
</p>

# Dispatch

<p align="center">
  <a href="https://github.com/VisionAIrySE/Dispatch/stargazers"><img src="https://img.shields.io/github/stars/VisionAIrySE/Dispatch?style=social" alt="GitHub Stars"></a>
  &nbsp;
  <img src="https://img.shields.io/badge/python-3.8+-blue" alt="Python 3.8+">
  &nbsp;
  <img src="https://img.shields.io/badge/license-MIT-green" alt="MIT License">
  &nbsp;
  <img src="https://img.shields.io/badge/works%20with-Claude%20Code-orange" alt="Works with Claude Code">
</p>

**A runtime skill router for Claude Code — intercepts tool calls, checks whether a better tool exists for what you're doing right now, and blocks if it finds one.**

Claude Code has hundreds of plugins and marketplace skills. Most sessions you use the same handful and forget the rest exist. Dispatch watches your work in real time, detects when you shift to a new task, and — before Claude reaches for a tool — checks whether there's something better. If there is, it stops Claude and tells you.

---

## What it actually does

Dispatch runs as two Claude Code hooks wired together:

**Hook 1 — fires on every message you send.** Sends your last few messages to a small model for ~100ms. If it detects a task shift (you moved from debugging a Flutter widget to writing tests, say), it maps the shift to a category and saves it to state. Silent — you never see it.

**Hook 2 — fires before every tool call.** When Claude is about to invoke a Skill, Agent, or MCP tool, Dispatch intercepts it. It searches the marketplace for tools relevant to your current task category, scores them against what Claude was about to use, and if a marketplace tool scores 10+ points higher — it blocks the call and surfaces the comparison:

```
[DISPATCH] Intercepted: CC is about to use 'superpowers:systematic-debugging' for Flutter Fixing.
CC's tool score for this task: 62/100

Marketplace alternatives:
  1. flutter-mobile-app-dev [94/100] ← TOP PICK
     Why: Purpose-built for Flutter/Dart debugging with widget tree inspection.
     Install + restart: npx skills add flutter-mobile-app-dev -y && claude
     More info: https://github.com/VisionAIrySE/flutter-mobile-app-dev

⚠ A marketplace tool scores higher than 'superpowers:systematic-debugging' for this task.
  Options:
  1. Say 'proceed' to continue with the current tool (one-time bypass, no restart needed)
  2. Install flutter-mobile-app-dev — run /compact first, then install and restart CC
  3. Ignore Dispatch for this task — say 'skip dispatch'

Present these options to the user. Wait for their response before taking any action.
```

If no marketplace tool beats Claude's choice by 10+ points, Dispatch exits silently and the tool call goes through unchanged.

---

## Install

```bash
git clone https://github.com/VisionAIrySE/Dispatch.git
cd Dispatch
chmod +x install.sh
./install.sh
```

`install.sh` walks you through three things: checking dependencies, registering both hooks in `~/.claude/settings.json`, and connecting to the hosted endpoint (or using your own API key). Takes about two minutes.

Start a **new** Claude Code session after install — hooks load at session startup.

---

## Three ways to run it

### Hosted Free — recommended for most people

Sign up at [dispatch.visionairy.biz/auth/github](https://dispatch.visionairy.biz/auth/github) with GitHub. You get a token that `install.sh` asks for. No API key needed on your end — the hosted endpoint handles classification and ranking.

**What you get:**
- 5 interceptions/day (resets daily)
- Haiku for shift detection and scoring
- Live marketplace search on each intercept
- Dashboard at `dispatch.visionairy.biz/dashboard?token=YOUR_TOKEN`

**What leaves your machine:** your last ~3 messages and working directory path, sent to dispatch.visionairy.biz for classification. Passed to Haiku and discarded — we don't store conversation content. We store your GitHub username, usage count, and task type labels (e.g., `flutter-fixing`).

### Hosted Pro — $10/month

Everything in Free, plus:

- **Unlimited interceptions**
- **Sonnet for ranking** — materially sharper scores and reasons, fewer irrelevant suggestions
- **Pre-ranked catalog** — tools pre-scored daily by category, so `/catalog` responses come back in milliseconds instead of hitting live registries in real time
- **Pro dashboard** — see your interception history, block rate, top tools suggested, and quota at a glance

[Upgrade at dispatch.visionairy.biz/pro](https://dispatch.visionairy.biz/pro)

The catalog is the compounding advantage. As more developers use Dispatch across different stacks, the signal on which tools actually matter for which tasks gets sharper. BYOK users run the same algorithm in isolation; Pro users benefit from aggregate patterns across the whole network.

### BYOK — bring your own API key

If you'd rather run entirely on your own infrastructure with no data leaving your machine:

```bash
export ANTHROPIC_API_KEY=sk-ant-...

# Persist across sessions:
echo 'export ANTHROPIC_API_KEY=sk-ant-...' >> ~/.bashrc   # bash
echo 'export ANTHROPIC_API_KEY=sk-ant-...' >> ~/.zshrc    # zsh
```

No token, no server, no data sharing. Dispatch runs the full algorithm locally using Haiku. Your API costs for a typical session (10 messages, 2–3 shifts) are under $0.00005 — less than a cent for a full month of heavy use.

| | Hosted Free | Hosted Pro | BYOK |
|---|---|---|---|
| **Setup** | GitHub OAuth, no API key | GitHub OAuth + Stripe | API key only |
| **Interceptions/day** | 5 | Unlimited | Unlimited |
| **Ranking model** | Haiku | Sonnet | Haiku |
| **Catalog** | Live search | Pre-ranked | Live search |
| **Dashboard** | Upgrade teaser | ✓ | — |
| **Cost** | Free | $10/month | ~$0/month API |
| **Data sharing** | Task labels only | Task labels only | None |

---

## Requirements

- **[Claude Code](https://claude.ai/code)** (hooks support required — v1.x+)
- **Python 3.8+**
- **Node.js + npx** — [nodejs.org](https://nodejs.org)
- One of: a Dispatch account (free) or an Anthropic API key

The `anthropic` Python package installs automatically via `install.sh`.

---

## Using it

Most of the time, Dispatch is invisible. Hook 1 runs on every message but exits silently unless it detects a shift. Hook 2 runs on every tool call but exits silently unless it finds something meaningfully better.

When it fires, Claude pauses and shows you the comparison. You have three options:

- **Say `proceed`** — Claude uses its original tool choice, one-time bypass, no restart needed
- **Install the top pick** — run `/compact` to save session context, paste the install command, restart CC and continue where you left off
- **Say `skip dispatch`** — Dispatch ignores this task type going forward in the session

The threshold is a 10-point gap. If the best marketplace alternative scores 72 and Claude's tool scores 64, Dispatch blocks. If the gap is 9 points or less, it passes through silently.

---

## How the scoring works

When Hook 2 intercepts a tool call, it:

1. Reads the current task category from state (written by Hook 1 on the last detected shift)
2. Searches the marketplace for tools matching that category's keywords
3. Scores each result 0–100 for relevance to the specific task — considering tool name, description, and the task context
4. Scores Claude's chosen tool on the same scale
5. Blocks if the top result beats Claude's score by 10+, passes through otherwise

**Free/BYOK** — hits the live [skills.sh](https://skills.sh) marketplace on each intercept (~2–4s)

**Pro** — pulls from a pre-ranked catalog built by a daily crawl across npm, skills.sh, and Claude plugin registries, scored by Haiku during the crawl. Intercept response is <200ms.

---

## Get more out of it

Dispatch recommends from the full marketplace — installed or not. But its scores improve with better tool descriptions. Add the official marketplaces to give it more signal:

```
/plugins add anthropics/claude-plugins-official
/plugins add ananddtyagi/claude-code-marketplace
```

Browse for skills relevant to your stack:

```bash
npx skills find flutter
npx skills find supabase
npx skills find react
```

The more skills in the registry that match your work, the more often Dispatch has something useful to surface.

---

## How the categories work

Dispatch uses 16 MECE categories to route marketplace searches — things like `mobile-development`, `frontend-web`, `devops-infra`, `data-science`. When Haiku detects a shift, it generates a specific task type label like `flutter-fixing` or `nextjs-building`, then maps that label to a category. The category drives the marketplace search, which is more targeted than keyword-splitting the task type directly.

Unknown task types are logged to `unknown_categories.jsonl` in the skill-router directory — if you're working in a niche stack and Dispatch consistently misses, that file tells you why.

---

## Stack detection

On install, and again whenever you change working directories, Dispatch scans your project's manifest files (`package.json`, `requirements.txt`, `go.mod`, `Cargo.toml`, `pubspec.yaml`, etc.) to build a stack profile. Pro users' catalog results are reranked using this profile — a Flutter project gets `flutter-mobile-app-dev` ranked higher than a generic mobile tool even if their base scores are similar.

The stack profile lives at `~/.claude/skill-router/stack_profile.json` and updates automatically.

---

## Troubleshooting

**Dispatch isn't intercepting anything**
- Start a **new** Claude Code session after install — hooks load at startup
- Check both hooks are registered: look for `UserPromptSubmit` and `PreToolUse` entries in `~/.claude/settings.json`
- Verify your key or token: `cat ~/.claude/skill-router/config.json`

**Dispatch fires but passes everything through**
- This is correct behavior most of the time — it only blocks when the gap is 10+ points
- If marketplace search returns nothing, there's nothing to compare against

**Hook is slow**
- 10s hard timeout — Claude proceeds normally if exceeded
- Pro catalog responses are <200ms; BYOK/Free search takes 2–4s

**"Degraded mode" warning during install**
- The `anthropic` package installed but Python can't import it (common on system Python with PEP 668 restrictions)
- Fix: `pip3 install anthropic --break-system-packages` or use a virtualenv

---

## Uninstall

```bash
rm -rf ~/.claude/skill-router
rm ~/.claude/hooks/skill-router.sh
rm ~/.claude/hooks/preuse-hook.sh
```

Then remove the `UserPromptSubmit` and `PreToolUse` entries from `~/.claude/settings.json`.

---

## Security

- **No `~/.claude/CLAUDE.md` modification** — Dispatch doesn't touch your global Claude instructions
- **No credential harvesting** — reads only `ANTHROPIC_API_KEY` from your environment
- **No shell injection** — task type labels always passed as `sys.argv`, never interpolated into shell strings
- **Open source** — every line of both hooks and all Python modules is in this repo; verify before installing
- **10-second hard timeout** — enforced by Claude Code; Dispatch cannot hang your session

---

## Privacy

**BYOK:** Haiku calls go directly from your machine to Anthropic. Nothing passes through our servers.

**Hosted:** Your last ~3 messages and working directory are sent to dispatch.visionairy.biz for classification. We pass this to Haiku and discard it — we don't store conversation content. We store: GitHub username, email, usage count, and task type labels. We don't sell individual data. Aggregate patterns may improve recommendations in anonymized form. You can switch to BYOK mode at any time for zero data sharing.

---

## Contributing

Open source, MIT licensed. The classifier taxonomy and category mapping are the most impactful places to contribute — better category coverage means better marketplace routing for everyone.

Open an issue with:
- What task type Dispatch detected
- Whether the recommendations were relevant
- Stack you were working in

Pull requests welcome.

---

## Why this exists

The Claude Code plugin ecosystem is genuinely underutilized. Most developers install a handful of tools and forget the rest exist. The problem isn't that good tools aren't available — it's that you have to already know what you need, and remember to reach for it, mid-session, while you're focused on something else.

Dispatch is the runtime layer that was missing. It knows what you're doing because it reads your conversation. It knows what's available because it searches the marketplace. It connects them automatically, and only bothers you when it actually has something better.

Run it with your own key if you want — it works. The hosted version knows something your local copy doesn't: what tools other developers reach for when they're doing exactly what you're doing right now. That signal compounds over time.

Built by [Visionairy](https://visionairy.biz). If you're getting serious about AI developer tooling, also check out [Vib8](https://vib8.ai) — AI-powered competitive intelligence for founders.

---

## Roadmap

- [x] Hosted endpoint (dispatch.visionairy.biz)
- [x] PreToolUse interception — blocks on 10+ point gap
- [x] Category-first routing — 16 MECE categories
- [x] Pre-ranked catalog — daily cron, <200ms Pro responses
- [x] Stack detection — auto-detects languages/frameworks from manifest files
- [x] Pro dashboard — interception history, block rate, quota
- [ ] `/dispatch status` command
- [ ] skills.sh distribution (`npx skills add VisionAIrySE/Dispatch`)
- [ ] Weekly new-tool digest for Pro users
