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

## Plans

### Free — start here

[Sign up with GitHub](https://dispatch.visionairy.biz/auth/github) — no API key, no card required. `install.sh` will ask for your token.

- 8 interceptions/day
- Haiku ranking
- Live marketplace search

**What leaves your machine:** your last ~3 messages and working directory path, sent to classify the task. Not stored — we keep your GitHub username, usage count, and task type labels (e.g., `flutter-fixing`). No conversation content.

---

### Pro — $10/month

> **Founding Dispatcher offer:** First 300 subscribers lock in **$6/month for life**. After 300, standard rate applies.

[Upgrade at dispatch.visionairy.biz/pro](https://dispatch.visionairy.biz/pro)

- **Unlimited interceptions**
- **Sonnet for ranking** — sharper scores, better reasons, fewer misses
- **Pre-ranked catalog** — tools scored daily from real install data and GitHub signal, not live search. Faster and more accurate
- **Network intelligence** — every confirmed install across all Pro users feeds back into catalog scores. The longer you run it, the better it gets at knowing which tools actually work for your stack
- **Full dashboard** — interception history, block rate, top tools, conversion tracking

The catalog is the compounding advantage. BYOK and Free users get a snapshot of the marketplace in real time. Pro users get a ranked, signal-weighted view built from aggregate behavior across the whole network — and it improves every day.

---

### BYOK — air-gapped or enterprise environments

If your security policy prohibits sending any data to external services:

```bash
export ANTHROPIC_API_KEY=sk-ant-...
```

Dispatch runs entirely locally. No account, no data leaves your machine. You lose the catalog intelligence, Sonnet ranking, and dashboard — but the core intercept loop works. API costs are negligible (~$0.00005/session).

| | Free | Pro | BYOK |
|---|---|---|---|
| **Interceptions/day** | 8 | Unlimited | Unlimited |
| **Ranking model** | Haiku | Sonnet | Haiku |
| **Catalog** | Live search | Pre-ranked + network signal | Live search only |
| **Dashboard** | — | ✓ | — |
| **Network intelligence** | — | ✓ | — |
| **Cost** | Free | $10/month | API costs (~$0) |
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

Unknown task types are logged to `unknown_categories.jsonl` in the dispatch directory — if you're working in a niche stack and Dispatch consistently misses, that file tells you why.

---

## Stack detection

On install, and again whenever you change working directories, Dispatch scans your project's manifest files (`package.json`, `requirements.txt`, `go.mod`, `Cargo.toml`, `pubspec.yaml`, etc.) to build a stack profile. Pro users' catalog results are reranked using this profile — a Flutter project gets `flutter-mobile-app-dev` ranked higher than a generic mobile tool even if their base scores are similar.

The stack profile lives at `~/.claude/dispatch/stack_profile.json` and updates automatically.

---

## Troubleshooting

**Dispatch isn't intercepting anything**
- Start a **new** Claude Code session after install — hooks load at startup
- Check both hooks are registered: look for `UserPromptSubmit` and `PreToolUse` entries in `~/.claude/settings.json`
- Verify your key or token: `cat ~/.claude/dispatch/config.json`

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
bash uninstall.sh
```

Removes all installed files, hook scripts, and settings.json entries automatically. Also cleans up pre-v0.9.2 installs if present.

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

**Hosted (Free and Pro):** The following data is sent to and stored at dispatch.visionairy.biz:

| Data | Stored? | Notes |
|------|---------|-------|
| Last ~3 messages | **No** | Sent for classification, discarded immediately |
| Working directory path | **No** | Sent for context, not stored |
| GitHub username + email | **Yes** | Collected via GitHub OAuth at signup |
| Task type label (e.g. `flutter-fixing`) | **Yes** | Stored per interception event |
| Tool intercepted + relevance scores | **Yes** | Tool name, CC score, marketplace score |
| Blocked / bypassed / installed | **Yes** | Powers your Pro dashboard |
| Stack profile (languages/frameworks) | **Local only** | Stored in `~/.claude/dispatch/stack_profile.json` |

We don't store conversation content. We don't sell individual user data. Aggregate, anonymized patterns (e.g. what percentage of mobile developers install Flutter skills after a Dispatch suggestion) improve catalog rankings network-wide.

**Creator outreach:** When the daily catalog crawl finds a skill with install activity but no description, Dispatch may open a GitHub issue on that repo asking the creator to add a description. At most once per repo per 30 days. Issues include a note that the creator can close with no action required.

To delete your account and all stored data, email dispatch@visionairy.biz. To stop all data sharing immediately, switch to BYOK mode.

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
- [x] Pre-ranked catalog — daily cron, signal-scored (installs/stars/forks/freshness)
- [x] Stack detection — auto-detects languages/frameworks from manifest files
- [x] Pro dashboard — interception history, block rate, install conversions, quota
- [x] Install conversion tracking — detects when users install suggested tools
- [x] Creator outreach — GitHub issues for undescribed skills (max 1/repo/month)
- [x] Slack notifications — signup, upgrade, conversion, daily digest, cron completion
- [x] `/dispatch status` command
- [ ] skills.sh distribution (`npx skills add VisionAIrySE/Dispatch`)
- [ ] CC marketplace submission
- [ ] Weekly new-tool digest email for Pro users
- [ ] Aggregate insights API (category trends, CC gap analysis)
