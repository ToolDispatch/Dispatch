<p align="center">
  <img src="Dispatch Icon.png" alt="ToolDispatch" width="120" />
</p>

# ToolDispatch

<p align="center">
  <a href="https://github.com/ToolDispatch/Dispatch/stargazers"><img src="https://img.shields.io/github/stars/ToolDispatch/Dispatch?style=social" alt="GitHub Stars"></a>
  &nbsp;
  <img src="https://img.shields.io/badge/python-3.8+-blue" alt="Python 3.8+">
  &nbsp;
  <img src="https://img.shields.io/badge/license-MIT-green" alt="MIT License">
  &nbsp;
  <img src="https://img.shields.io/badge/works%20with-Claude%20Code-orange" alt="Works with Claude Code">
</p>

**Your Claude Code insurance policy — best tool for the job up front, code that connects before it breaks.**

ToolDispatch puts the best tool in Claude's hands at the right moment. XF Audit ensures the code it produces actually connects. One platform. Both sides of the problem. And it leaves a record of everything it did.

**Dispatch** covers the first half: claude-plugins.dev alone lists 51,000+ agent skills. Glama.ai has 20,000+ MCP servers. Smithery has thousands more. The Claude Code tool ecosystem is enormous — and growing every week. Claude picks from defaults. The best tool for what you're actually building right now — you've probably never heard of it. Dispatch fixes this by proactively surfacing the right tools when your task shifts, and intercepting when Claude reaches for a weaker one. All decisions are logged with `[PROVENANCE]` markers for transparency.

**XF Audit** covers the second half: Claude Code produces architecturally sound code that often doesn't connect. It renames a function and misses three callers. It calls a function with the wrong number of arguments. These failures are silent until runtime — and by then the session context is gone. XF Audit closes that loop at the edit boundary, where the cost of fixing is near-zero and the context is still live.

> One platform. Both sides of the problem. And it leaves a receipt.

---

## The two modules

### Dispatch — tool routing

Dispatch runs as three Claude Code hooks wired together:

**Hook 3 — fires when the session ends.** Prints a one-line digest so you can see Dispatch was running the whole time — even when it correctly stayed silent. Example:

```
[Dispatch] Session: 12 tool calls audited · 0 blocked (all optimal) · 1 recommendation shown
```

**Hook 1 — fires on every message you send.** Sends your last few messages to a small model for ~100ms. If it detects a task shift (you moved from debugging a Flutter widget to writing tests, say), it maps the shift to a category and immediately surfaces grouped tool recommendations into Claude's context (Stage 3). Recommendations are grouped by type: Plugins, Skills, and MCPs. You see them once per topic per session.

Example proactive output (on task shift):

```
[Dispatch] Recommended tools for this flutter-building task:

Plugins:
  • flutter-mobile-app-dev — Expert Flutter agent for widgets, state, iOS/Android.
    Install: claude install plugin:anthropic:flutter-mobile-app-dev

Skills:
  • VisionAIrySE/flutter@flutter-dev — Flutter dev skill for widget building.
    Install: claude install VisionAIrySE/flutter@flutter-dev

MCPs:
  • fluttermcp — Dart analysis and widget tree inspection server.
    Install: claude mcp add fluttermcp npx -y @fluttermcp/server

Not sure which to pick? Ask me — I can explain the differences.
```

If no task shift is detected, Hook 1 exits silently with no output.

**Hook 2 — fires before every tool call.** When Claude is about to invoke a Skill, Agent, or MCP tool, Dispatch intercepts it. It searches the marketplace — npm skills, the Claude plugin registries, and glama.ai for MCPs — for tools relevant to your current task, scores them against what Claude was about to use, and if a marketplace tool scores 10+ points higher — it blocks the call and surfaces the comparison:

```
[Dispatch] Intercepted: CC is about to use 'superpowers:systematic-debugging' (Skill) for Flutter Fixing.
CC confidence score: 62/100

── Plugins ──
  1. flutter-mobile-app-dev
     Relevance 91 · Signal 78 · Velocity 62  installs:12,400 stars:340 forks:28
     Purpose-built Flutter/Dart agent — widget tree inspection, state, iOS/Android builds.
     Install: claude install plugin:anthropic:flutter-mobile-app-dev && claude

── Skills ──
  1. VisionAIrySE/flutter@flutter-dev
     Relevance 84 · Signal 65 · Velocity 55  installs:2,100 stars:88 forks:14
     Flutter dev workflow — widget builds, golden tests, pub dependencies.
     Install: npx skills add VisionAIrySE/flutter@flutter-dev -y && claude
  2. superpowers/flutter@flutter-expert
     ⚠ no description — install at your own risk
     Relevance 0 · Signal 42 · Velocity 30  installs:890 stars:12 forks:3

── MCP Servers ──
  1. dart-mcp
     Relevance 79 · Signal 58 · Velocity 48  installs:4,200 stars:120 forks:9
     Dart analysis server — static analysis, pub resolve, widget inspection.
     More info: https://github.com/dart-lang/dart-mcp

⚠ Marketplace tools score higher than 'superpowers:systematic-debugging' (Skill) for this task.
  Options:
  1. Say 'proceed' to continue with 'superpowers:systematic-debugging' (one-time bypass, no restart needed)
  2. Install flutter-mobile-app-dev plugin — run /compact first, then install and restart CC
  3. Ignore Dispatch for this task — say 'skip dispatch'

Note: Review before installing. Dispatch surfaces tools based on community signals and task context — not a security audit.

Present these options to the user. Wait for their response before taking any action.
```

If no marketplace tool beats Claude's choice by 10+ points, Dispatch exits silently and the tool call goes through unchanged.

---

### XF Audit — contract checking

XF Audit fires on every Edit and Write. Most of the time, Stage 1 completes in ~200ms and you see a green stamp:

```
◈ XF Audit  47 modules · 203 edges checked  ✓ 0 boundary violations
```

When something is actually wrong:

```
◈ XF Audit  This edit will break at runtime.

  evaluator.py:203 — calls rank_tools() with 3 arguments, but it only accepts 2.
  This will throw a TypeError when that code runs.

  Fix: remove the third argument, or update rank_tools() to accept it.

  To proceed: say 'show me the diff first', 'skip for now', or 'apply all' (unlocks after 2 verified repairs).
```

The four stages:

- **Stage 1** (~200ms, always): AST scan — syntax, missing imports, arity mismatches, hard env var access, consumed stubs. Blocks immediately on violations.
- **Stage 2** (on escalation): Xpansion cascade analysis — maps the full caller chain using MECE boundary framework (DATA, NODES, FLOW, ERRORS). Shows consequence-first output.
- **Stage 3**: Concrete repair plan — each violation gets one specific file-and-line fix.
- **Stage 4**: Graduated consent — "show me the diff first" until two verified repairs this session, then "apply all" unlocks. Resets each session.

**Refactor Mode:** `/xfa-refactor start "description"` — XF Audit shifts from blocking to tracking. Violations accumulate without interrupting your work. Run `/xfa-refactor end` when done to get the consolidated repair list. Useful when you're mid-refactor and know the code is temporarily broken across files.

Every scan leaves a record in `.xf/boundary_violations.json`. Every repair is logged to `.xf/repair_log.json` with timestamp and session ID. When something goes wrong in production: the log answers whether XF Audit caught it.

---

## Install

```bash
git clone https://github.com/ToolDispatch/Dispatch.git
cd Dispatch
chmod +x install.sh
./install.sh
```

`install.sh` walks you through three things: checking dependencies, registering both hooks in `~/.claude/settings.json`, and connecting to the hosted endpoint (or using your own API key). Takes about two minutes.

Start a **new** Claude Code session after install — hooks load at session startup.

---

## Plans

### BYOK / Open Source — for developers who need full local control

```bash
git clone https://github.com/ToolDispatch/Dispatch.git
cd Dispatch && ./install.sh
export OPENROUTER_API_KEY=sk-or-...   # recommended — free models available
# or: export ANTHROPIC_API_KEY=sk-ant-...  # any Claude model
```

Bring your own key — OpenRouter or Anthropic. Everything runs on your machine, against your key. No data leaves your network. Set `OPENROUTER_API_KEY` for free inference (Llama, Nemotron, and more) or `ANTHROPIC_API_KEY` for direct Claude access. Override the model in `~/.claude/dispatch/config.json`.

- **Dispatch:** fully functional, unlimited interceptions
- **XF Audit:** Stage 1 bundled (pure AST, zero API cost) — catches broken imports, arity mismatches, syntax errors on every Edit/Write
- **Stages 2–4:** upgrade prompt fires in session digest when Stage 2 would have been useful — one line, never mid-conversation, never blocking: `◈ XF Audit would have mapped that cascade. tooldispatch.visionairy.biz/pro`

No account needed. Everything runs locally. You lose the catalog network intelligence and the dashboard.

---

### Free — start here

[Sign up with GitHub](https://tooldispatch.visionairy.biz/auth/github) — no API key, no card required. `install.sh` will ask for your token. Takes 30 seconds.

- **Dispatch:** 8 interceptions/day + full proactive recommendations on every task shift
- **XF Audit:** Stage 1 always-on (bundled), Stages 2–4 tier-blocked with in-context upgrade prompt when Stage 2 events occurred

**What leaves your machine:** your last ~3 messages and working directory path, sent to classify the task. Not stored — we keep your GitHub username, usage count, and task type labels (e.g., `flutter-fixing`). No conversation content.

---

### Pro — $10/month

> **Founding offer:** First 300 subscribers lock in **$6/month for life**. After 300, standard rate applies.

[Upgrade at tooldispatch.visionairy.biz/pro](https://tooldispatch.visionairy.biz/pro)

- **Dispatch:** unlimited interceptions, Sonnet ranking, pre-ranked catalog
- **XF Audit:** full Stages 1–4 (Xpansion cascade analysis, concrete repair plan, graduated consent flow, repair log)
- **Dashboard:** interception history, contract repair history, provenance log

The catalog is the compounding advantage. The hosted version sees what thousands of developers actually installed after a Dispatch suggestion, which tools they bypassed, and which ones stuck. That signal builds over time and no local setup can replicate it.

| | BYOK | Free | Pro |
|---|---|---|---|
| **Dispatch — proactive recs** | ✓ | ✓ | ✓ |
| **Dispatch — interceptions** | Unlimited | 8/day | Unlimited |
| **Dispatch — ranking quality** | Configurable | Good | Best (Sonnet) |
| **Dispatch — catalog** | Live search | Live search | Pre-ranked, 6 sources |
| **XF Audit — Stage 1** | ✓ | ✓ | ✓ |
| **XF Audit — Stages 2–4** | Upgrade prompt | Upgrade prompt | ✓ Full |
| **Dashboard** | — | — | ✓ |
| **Network intelligence** | — | — | ✓ |
| **Cost** | API costs | Free | $10/month |
| **Data sharing** | None | Task labels only | Task labels only |

---

## Requirements

- **[Claude Code](https://claude.ai/code)** (hooks support required — v1.x+)
- **Python 3.8+**
- **Node.js + npx** — [nodejs.org](https://nodejs.org)
- One of: a Dispatch account (free) or an Anthropic API key

The `anthropic` Python package installs automatically via `install.sh`.

---

## Using it

Most of the time, Dispatch is invisible. Hook 1 runs on every message and exits silently unless it detects a shift. Hook 2 runs on every tool call but exits silently unless it finds something meaningfully better.

**When Hook 1 fires (on task shift):** You'll see a proactive list of recommended tools grouped by Plugins, Skills, and MCPs directly in Claude's context. Ask Claude to explain the differences between any of them, paste the install command for one you want, or ignore the list and keep working. Dispatch won't show the same category's suggestions again this session.

**When Hook 2 fires:** Claude pauses and shows you the comparison. You have three options:

- **Say `proceed`** — Claude uses its original tool choice, one-time bypass, no restart needed
- **Install the top pick** — run `/compact` to save session context, paste the install command, restart CC and continue where you left off
- **Say `skip dispatch`** — Dispatch ignores this task type going forward in the session

The threshold is a 10-point gap. If the best marketplace alternative scores 72 and Claude's tool scores 64, Dispatch blocks. If the gap is 9 points or less, it passes through silently.

---

## Commands

### Dispatch

| Command | How to use | What it does |
|---|---|---|
| `proceed` | Say it conversationally | One-time bypass — Dispatch lets the current tool call through, no restart needed |
| `skip dispatch` | Say it conversationally | Ignore Dispatch for this task type for the rest of the session |
| `/dispatch status` | Slash command | Show session stats — tool calls audited, blocks, recommendations shown |

Coming soon (not yet available):

| Command | What it will do |
|---|---|
| `/dispatch pause` | Disable both hooks for this session without uninstalling |
| `/dispatch resume` | Re-enable after a pause |
| `/dispatch stack` | Show what stack_scanner detected for the current project |
| `/dispatch why` | Explain the last block — task type, category, top tool score vs CC score |
| `/dispatch ignore [tool]` | Permanently exclude a specific tool from all recommendations |
| `/dispatch feedback good` | Mark the last recommendation as correct (strong positive signal) |
| `/dispatch feedback bad` | Mark the last recommendation as wrong |

### XF Audit

| Command | How to use | What it does |
|---|---|---|
| `/xfa-refactor start "description"` | Slash command | Enter Refactor Mode — violations accumulate without blocking; Claude works uninterrupted |
| `/xfa-refactor end` | Slash command | Exit Refactor Mode — presents consolidated repair list for everything flagged during the session |

When XF Audit blocks an edit, Claude reads the options from the hook output and acts:

- **Say `show me the diff first`** — Claude shows what the repair would change before applying it
- **Say `skip for now`** — allow the edit through without repair (violation stays in log)
- **Say `apply all`** — unlocks after two verified repairs this session; applies all staged repairs at once

Coming soon:

| Command | What it will do |
|---|---|
| `/xfa pause` | Disable XF Audit blocking for this session (violations still logged) |
| `/xfa resume` | Re-enable after a pause |
| `/xfa report` | Show repair_log.json summary for the current session — violations caught, files touched |
| `/xfa clear` | Clear open violations in `.xf/boundary_violations.json` (escape hatch for stale violations) |

---

## How the scoring works

Each recommended tool shows three components so you can judge it yourself:

- **Relevance** — how well the tool's description matches your specific task, scored by a fast LLM pass. Tools with no description score zero and get a visible warning.
- **Signal** — popularity as a quality proxy, weighted across installs, stars, and forks. Log-scaled so a newer tool with 500 installs isn't buried by one with 50,000.
- **Velocity** — install momentum relative to how long the tool has existed. A tool gaining traction fast ranks higher than one that peaked years ago.

All three factors contribute to the final score. Dispatch blocks when the top marketplace score beats CC's confidence by a meaningful margin.

Tools are grouped by type (Plugins / Skills / MCPs), up to 3 per group. Raw installs, stars, and forks are shown so you can verify the signal yourself.

**No description = relevance 0.** If a tool has no README or description, it can't score on relevance — only signal and velocity. It'll still appear if community adoption is strong, but with a ⚠ warning. Dispatch sends outreach to undescribed tool authors automatically to help close this gap.

**Caveat:** Dispatch surfaces tools based on community signals and task context — not a security audit. Review any tool before installing.

**Free/BYOK** — hits the live [skills.sh](https://skills.sh) marketplace and glama.ai MCP registry on each intercept (~2–4s). Relevance is scored by an LLM using the tool description.

**Pro** — pulls from a pre-ranked catalog built by a daily crawl across npm, skills.sh, glama.ai, and the Claude plugin registries. Tools are scored during the crawl — all three components pre-computed. At intercept time, Dispatch maps your task to the closest taxonomy leaf and returns a pure catalog query. Intercept response is <200ms, no LLM call at hook time.

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

Dispatch uses a hierarchical MECE taxonomy with 16 top-level categories: `source-control`, `data-storage`, `search-discovery`, `ai-ml`, `frontend`, `mobile`, `backend`, `infrastructure`, `delivery`, `integrations`, `identity-security`, `observability`, `testing`, `data-engineering`, `payments`, `documentation`. Each category breaks down into subcategories and leaf nodes (e.g. `data-storage → relational → postgresql`).

When Haiku detects a task shift, it generates a specific label like `flutter-fixing` or `postgres-rls-query`. Dispatch maps that label to the closest taxonomy leaf — scoring token overlap against 100+ leaf nodes and their tags. The leaf drives marketplace search with precise vocabulary (e.g. `postgresql` maps to postgres/rls/migration/query terms), which is more targeted than keyword-splitting the task label directly.

Pro users get the full taxonomy path sent to the catalog — results filtered by leaf node and matching tags, sorted by pre-computed signal scores with no LLM involved.

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

**Proactive recommendations aren't appearing**
- Start a **new** Claude Code session after install — hooks load at startup
- Check that Hook 1 is registered: look for `UserPromptSubmit` in `~/.claude/settings.json`
- Proactive recommendations fire only on a confirmed task shift with confidence ≥ 0.7 — if you're continuing the same topic, no output is expected

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

**Hosted (Free and Pro):** The following data is sent to and stored at tooldispatch.visionairy.biz:

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

To delete your account and all stored data, email hello@tooldispatch.visionairy.biz. To stop all data sharing immediately, switch to BYOK mode.

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

Two problems define every Claude Code session. The first: the tool ecosystem is enormous and growing, but Claude picks from defaults. You're always flying blind on tool selection. The second: Claude Code produces architecturally sound code that often doesn't connect — renames a function and misses three callers, calls with the wrong arguments, imports a symbol that was refactored away. These failures are silent until runtime.

ToolDispatch covers both sides. Dispatch is the runtime layer that ensures Claude reaches for the best tool. XF Audit is the safety net that ensures the code those tools produce actually connects. One install. Both problems. And it leaves a record of everything it did — so when something goes wrong in production, you can answer: did we catch this?

The hosted version knows something a local install can never know: what tools thousands of other developers actually reached for when they were doing exactly what you're doing right now — and which ones they kept. That signal compounds over time. [Start free.](https://tooldispatch.visionairy.biz/auth/github)

Built by [Visionairy](https://visionairy.biz). If you're getting serious about AI developer tooling, also check out [Vib8](https://vib8.ai) — AI-powered competitive intelligence for founders.

---

## Built with ToolDispatch

ToolDispatch's own codebase is monitored by XF Audit during development. Every edit Claude makes to Dispatch is checked for contract breaks before it lands.

In practice, this meant:

- The **arity checker** caught 12 real violations during an eng review pass — functions being called with the wrong number of arguments across the codebase, all silently waiting to throw TypeErrors at runtime.
- The **silent exception checker** (added after a production incident) caught the pattern that caused 99 minutes of cron work to go to /dev/null — a bare `except Exception` that printed a warning but reported success regardless.
- The **stub checker** surfaced unimplemented functions with active callers before they ever reached a user session.

We eat our own cooking. The tool that ships with ToolDispatch is the tool we use to build ToolDispatch.

---

## Roadmap

- [x] Hosted endpoint (tooldispatch.visionairy.biz)
- [x] PreToolUse interception — blocks on 10+ point gap
- [x] Category-first routing — 16 MECE categories
- [x] Pre-ranked catalog — daily cron, signal-scored (installs/stars/forks/freshness)
- [x] Stack detection — auto-detects languages/frameworks from manifest files
- [x] Pro dashboard — interception history, block rate, install conversions, quota
- [x] Install conversion tracking — detects when users install suggested tools
- [x] Creator outreach — GitHub issues for undescribed skills (max 1/repo/month)
- [x] Slack notifications — signup, upgrade, conversion, daily digest, cron completion
- [x] `/dispatch status` command
- [x] Proactive recommendations — grouped by type (Plugins/Skills/MCPs) at task shift (Stage 3)
- [x] Hosted proactive recommendations for Free and Pro
- [x] Session digest — Stop hook shows what Dispatch did each session
- [x] `/xfa-refactor start/end` — Refactor Mode for XF Audit
- [ ] `/dispatch pause/resume` — disable hooks mid-session without uninstalling
- [ ] `/dispatch stack` — show detected project stack
- [ ] `/dispatch why` — explain last block decision
- [ ] `/dispatch ignore [tool]` — permanent per-tool exclusion
- [ ] `/dispatch feedback good/bad` — explicit recommendation signal
- [ ] `/xfa pause/resume` — disable XF Audit blocking mid-session
- [ ] `/xfa report` — session repair summary
- [ ] `/xfa clear` — clear stale violations
- [ ] skills.sh distribution (`npx skills add ToolDispatch/Dispatch`)
- [ ] CC marketplace submission
- [ ] Weekly new-tool digest email for Pro users
- [ ] Aggregate insights API (category trends, CC gap analysis)
