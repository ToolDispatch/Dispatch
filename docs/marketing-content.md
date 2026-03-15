# Dispatch — Marketing Content Package

**Generated:** 2026-03-14
**Version:** v0.8.0
**Repo:** https://github.com/VisionAIrySE/Dispatch

---

## Table of Contents

1. [Show HN Post](#1-show-hn-post)
2. [r/ClaudeCode Post](#2-rclaudecode-post)
3. [r/ClaudeDev Post](#3-rclaudedev-post)
4. [Twitter/X Launch Thread](#4-twitterx-launch-thread)
5. [Discord Message Templates](#5-discord-message-templates)
6. [Blogwatcher Keyword List](#6-blogwatcher-keyword-list)
7. [Response Templates](#7-response-templates)
8. [awesome-claude-code PR Description](#8-awesome-claude-code-pr-description)
9. [Dev.to Article Outline](#9-devto-article-outline)

---

## 1. Show HN Post

**Title:**
```
Show HN: Dispatch – runtime skill router for Claude Code (detects task shifts, recommends plugins)
```

**Body:**

I built Dispatch because I kept forgetting which Claude Code plugins I had installed. I'd be debugging a Flutter widget for 45 minutes, then shift to writing GitHub Actions — and never think to switch to the github-actions skill I installed three weeks ago. The plugin ecosystem is genuinely useful; I was just bad at using it.

Dispatch is a two-hook system that runs silently in every Claude Code session. Hook 1 (UserPromptSubmit) watches your last 3 messages and uses Haiku to detect domain and mode shifts — "flutter-fixing" → "flutter-validating" counts as a shift, so does "flutter-building" → "supabase-building". Detection runs in ~100ms and exits silently when nothing changes. On a confirmed shift (confidence ≥ 0.7), it scans your installed plugins and agent skills, searches the skills.sh registry for uninstalled options, then has Haiku rank everything together on a 0–100 scale and surface the list into Claude's context before it responds. Hook 2 (PreToolUse) intercepts before Claude invokes a Skill, Agent, or MCP tool and compares it against marketplace alternatives. If a better tool scores ≥10 points higher, it blocks and shows you the recommendation — you type "proceed" to bypass.

There's no fixed taxonomy. Haiku generates labels like `react-native`, `langchain`, `github-actions-shipping` from your conversation. Task types then map to one of 16 MECE categories for registry search. 93 unit tests across 4 modules. Requires Python 3.8+, Node.js, and either a free hosted token or your own Anthropic API key.

The hosted mode (free at dispatch.visionairy.biz, $10/month for unlimited — first 250 subscribers get $6/month for life) aggregates install and bypass behavior across users. Over time, the ranking reflects actual install rates, not just LLM scoring. BYOK runs the same algorithm in isolation — it works, but it's blind to what other developers actually reach for when doing the same task.

Honest limitations: uninstalled registry skills are ranked from their ID alone (e.g., `firebase/agent-skills@firebase-firestore-basics`) — reasons for those are inferred from the name, not a full description. Recommendations are only as good as what you have installed. The more plugins in your install, the sharper it gets. And the hook adds ~100–500ms to every message (Stage 1 only) and ~3–5s on confirmed shifts — still within Claude Code's 10s hard timeout.

Install is one command:
```bash
git clone https://github.com/VisionAIrySE/Dispatch.git && cd Dispatch && ./install.sh
```

Looking for feedback on: whether the task shift detection fires at the right granularity (does it fire too often, not often enough?), whether the PreToolUse intercept is annoying or useful in practice, and any task types it consistently misses. The classifier and evaluator are the best places to contribute if you want to dig into the code.

---

## 2. r/ClaudeCode Post

**Title:**
```
Anyone else forgetting to switch plugins when they shift tasks mid-session? I built something to fix that.
```

**Body:**

I noticed I was spending the whole session with the wrong tools active. I'd be deep in Flutter debugging with the flutter-mobile-app-dev skill loaded, then pivot to writing tests — and never think to switch. The plugin was there. I just forgot.

So I built Dispatch: a Claude Code hook that watches your conversation, detects when you shift tasks, and surfaces a ranked list of relevant plugins before Claude responds. If you shift to GitHub Actions work, it shows you the github-actions skill you have installed (and any relevant ones you don't). If you're mid-way through a Supabase task and switch to Firebase, it catches that too.

It also has a second hook (PreToolUse) that intercepts before Claude invokes a skill and checks if a marketplace alternative would score ≥10 points higher. If it finds one, it blocks and shows you the recommendation — one word ("proceed") to bypass if you want to continue anyway.

No API key required to start — free hosted tier gives you 8 detections/day. BYOK works too if you prefer to keep everything local.

Repo + install: https://github.com/VisionAIrySE/Dispatch

Would be curious whether the detection granularity feels right to others — I've been tuning when it fires vs. stays silent.

---

## 3. r/ClaudeDev Post

**Title:**
```
I built a two-hook runtime for Claude Code that intercepts task shifts and PreToolUse calls — here's the architecture
```

**Body:**

I wanted to write up how Dispatch works under the hood because the hook architecture ended up being more interesting than I expected.

**Two hooks, two different jobs:**

Hook 1 is a `UserPromptSubmit` hook that fires on every message. Stage 1 calls Haiku with your last 3 messages and cwd — returns `{"shift": bool, "domain": str, "mode": str, "task_type": str, "confidence": float}`. If no shift or confidence below 0.7, it exits in ~100ms with no output. On a confirmed shift, Stage 2 maps the task_type to one of 16 MECE categories, scans installed plugins, runs `npx skills list`, hits the skills.sh registry API, ranks everything 0–100, and writes state to `~/.claude/skill-router/state.json`. Hook 1 is completely silent — no stdout, no stderr injection. It just writes state.

Hook 2 is a `PreToolUse` hook that intercepts `Skill`, `Agent`, and `mcp__*` tool calls. It reads the category from state.json, searches the marketplace for that category, scores CC's chosen tool alongside alternatives using Haiku, and exits 2 (blocks the tool call) if a marketplace tool scores ≥10 points higher. The recommendation surfaces into Claude's context. User types "proceed" — a bypass token (120s TTL) is written so the next invocation of that exact tool passes through without re-blocking.

**A few things I learned building this:**

The CC transcript format is not what you'd expect. Entries are `{"type":"user", "isMeta":bool, "message":{"role":"user","content":"..."}}` — `role` is nested inside `message`, not at the top level. `isMeta=True` entries are CC system messages (loaded skill file text) and need to be filtered. Tool results are serialized as strings starting with `[{` — also need to be filtered. I burned a day debugging why Haiku kept seeing skill file content (1,400 words) as conversation context.

Haiku reliably returns markdown-wrapped JSON regardless of prompting. Always strip ` ```json ` before `json.loads()`.

`head -n -1` is GNU-only. BSD head on macOS treats it as "print 1 line." Use `sed '$d'` for portable HTTP body extraction.

The task type taxonomy is open-ended — Haiku generates labels like `react-native`, `langchain`, `docker-aws-github-actions`. A `category_mapper.py` module does keyword matching against a `categories.json` catalog (16 MECE categories) to normalize these for registry search. Unknown categories get logged to `unknown_categories.jsonl` for review.

93 unit tests across 4 modules (classifier, evaluator, interceptor, category_mapper). The hardest part to test is the transcript parsing — the CC format has enough edge cases that I kept finding new ones.

Repo: https://github.com/VisionAIrySE/Dispatch

Happy to answer questions on the architecture or the hook API specifics.

---

## 4. Twitter/X Launch Thread

**Tweet 1 — The hook:**
```
You installed 30 Claude Code plugins. You're actively using 4.

You forget the rest exist mid-session.

I built something to fix that.

Thread: Dispatch, a runtime skill router for Claude Code 🧵
```

**Tweet 2 — Hook 1:**
```
Hook 1 fires on every message.

Haiku reads your last 3 messages, detects if you shifted tasks (flutter-debugging → writing tests), and if yes — searches your installed plugins, the skills.sh registry, and scores everything 0–100.

~100ms when nothing changed. ~3-5s on a shift.
```

**Tweet 3 — Hook 2:**
```
Hook 2 fires before Claude invokes any Skill, Agent, or MCP tool.

If a marketplace alternative scores ≥10 points higher than what Claude picked, it blocks and shows you the better option.

Type "proceed" to bypass. One word. That's it.
```

**Tweet 4 — What it surfaces:**
```
When a shift is detected, you see this before Claude responds:

  1. flutter-mobile-app-dev [92/100] ← TOP PICK
  2. systematic-debugging [78/100]
  3. firebase-basics [61/100] (not installed)
     Install: npx skills add firebase/agent-skills@firebase-basics -y && claude

Ranked. Scored. Actionable.
```

**Tweet 5 — Install:**
```
Install:

git clone https://github.com/VisionAIrySE/Dispatch.git
cd Dispatch && ./install.sh

Sign in with GitHub, copy the token, paste it back. Start a new CC session. Done.

No API key required to start.
```

**Tweet 6 — BYOK vs hosted:**
```
Two modes:

BYOK: your own Anthropic key, runs entirely locally, zero data leaving your machine. Full algorithm, no network effect.

Hosted: free token at dispatch.visionairy.biz (8 detections/day). $10/mo Pro = unlimited + Sonnet ranking + collective intelligence from real install patterns. First 250 subscribers lock in $6/mo for life.
```

**Tweet 7 — Open source:**
```
Fully open source. 93 tests across 4 modules.

classifier.py — Haiku shift detection
evaluator.py — registry search + ranking
interceptor.py — PreToolUse blocking logic
category_mapper.py — MECE 16-category taxonomy

Read every line before installing. That's the point.

https://github.com/VisionAIrySE/Dispatch
```

**Tweet 8 — Use case example 1:**
```
Example:

You're fixing a Supabase RLS bug. Shift: you say "let's write the migration."

Dispatch detects supabase-building, surfaces supabase-postgres-best-practices skill you have installed.

It was there the whole time. You just forgot you had it.
```

**Tweet 9 — Use case example 2:**
```
Example:

You're mid-session, Claude is about to run the @github skill for a PR.

Dispatch intercepts — finds a higher-scoring github-actions-specific skill in the marketplace.

You didn't know it existed. Now you do. One word to proceed with Claude's original choice.
```

**Tweet 10 — CTA:**
```
It's invisible when you don't need it.
It fires when you do.

If you use Claude Code seriously, the plugin ecosystem is deeper than most people know. Dispatch helps you actually use it.

⭐ https://github.com/VisionAIrySE/Dispatch

Feedback welcome — especially on detection granularity.
```

---

## 5. Discord Message Templates

### Variant A — General dev server #tools channel (brief, link-forward)

```
Built a small tool for Claude Code users: Dispatch is a two-hook runtime that detects when you shift tasks mid-session and surfaces relevant plugins/skills before Claude responds. Also intercepts before Claude invokes a skill and checks if a better marketplace alternative exists.

No API key needed to start (free hosted tier). BYOK mode if you prefer fully local.

GitHub: https://github.com/VisionAIrySE/Dispatch

Happy to answer questions if anyone tries it.
```

---

### Variant B — Claude Code official server (more detailed, technical)

```
Hey — I built something that addresses a gap I kept running into with Claude Code.

The plugin ecosystem has 500+ plugins and skills across multiple marketplaces. The problem is they're invisible at runtime. You install them, then forget to invoke them mid-session when your task changes.

Dispatch is a two-hook system that fixes this:

**Hook 1 (UserPromptSubmit):** Detects task domain/mode shifts using Haiku (~100ms). On a confirmed shift, scans your installed plugins + agent skills, searches the skills.sh registry, ranks everything 0–100, and injects the ranked list into Claude's context before it responds.

**Hook 2 (PreToolUse):** Before Claude invokes any Skill, Agent, or MCP tool, checks if a marketplace alternative scores ≥10 points higher. If so, blocks and shows the recommendation. Type "proceed" to bypass.

Task detection uses a 7-mode MECE taxonomy (discovering/designing/building/fixing/validating/shipping/maintaining) combined with open-ended domain labels. No fixed skill list — it searches the live registry.

Install is one command, works with either a free hosted token or your own Anthropic API key:
https://github.com/VisionAIrySE/Dispatch

93 unit tests if you want to check the internals before installing. Feedback on detection granularity especially appreciated — curious if it fires at the right frequency for different workflows.
```

---

### Variant C — MCP/plugin community server (angle: helps users find the right MCP)

```
For folks who manage MCP servers and agent skills: I built a runtime layer for Claude Code that helps users discover and reach for the right tools at the right moment.

Dispatch intercepts two hook points:
- Before each message: detects if the user shifted task context (domain + mode), then ranks installed MCPs/plugins/skills against live registry results for their current task
- Before each tool invocation: if Claude is about to invoke a Skill or MCP tool, checks if a higher-scoring marketplace alternative exists — blocks and shows the recommendation if so

From a discovery angle: it searches the skills.sh registry automatically on every detected shift. If you publish a skill, Dispatch will surface it to users who shift into that task type — no manual curation needed on their end.

Relevant for anyone building skills/MCPs who wants their tools to reach the right users at the right moment.

Repo: https://github.com/VisionAIrySE/Dispatch
```

---

## 6. Blogwatcher Keyword List

### High Intent — Actively Looking for Tools

**Claude Code plugins and skills:**
- "Claude Code plugins"
- "Claude Code skills"
- "best Claude Code plugins"
- "Claude Code marketplace"
- "npx skills"
- "skills.sh"
- "agent skills Claude Code"
- "MCP server recommendations"
- "best MCP servers"
- "Claude Code MCP"
- "which MCP should I use"
- "Claude Code hooks"
- "UserPromptSubmit hook"
- "PreToolUse hook"
- "Claude Code hook examples"

**Plugin/tool discovery pain:**
- "too many Claude Code plugins"
- "Claude Code plugin not working"
- "Claude Code skill not loading"
- "Claude Code context plugin"
- "how to use Claude Code plugins"
- "Claude Code plugin management"
- "install Claude Code skill"

### Medium Intent — Related Pain Points

**Workflow friction:**
- "Claude Code workflow tips"
- "Claude Code productivity"
- "getting more from Claude Code"
- "Claude Code mid-session"
- "Claude Code session management"
- "Claude Code loses context"
- "Claude Code best practices"
- "Claude Code setup"

**Task switching and context:**
- "AI coding tool switching"
- "context switching AI tools"
- "Claude Code different tasks"
- "Claude forgets what I'm doing"

**MCP discovery:**
- "find MCP servers"
- "MCP registry"
- "modelcontextprotocol registry"
- "MCP server list"
- "Claude MCP plugins"
- "awesome MCP servers"

### Competitor and Related Project Mentions

- "SummonAI Claude"
- "claude-plugins-official"
- "awesome-agent-skills"
- "VoltAgent skills"
- "firebase agent-skills"
- "supabase agent-skills"
- "flutter-mobile-app-dev Claude"
- "superpowers skills Claude"
- "github-actions Claude Code"
- "systematic-debugging Claude"

### Brand Monitoring

- "Dispatch VisionAIrySE"
- "dispatch.visionairy.biz"
- "VisionAIrySE"
- "skill-router Claude"
- "Dispatch Claude Code"
- "@VisionAIrySE"

### Technical Community Signals

- "UserPromptSubmit Claude"
- "PreToolUse Claude"
- "Claude Code hooks tutorial"
- "hook Claude Code session"
- "Claude Code settings.json hooks"
- "anthropic hook"

---

## 7. Response Templates

### Tier 1 — Reactive/Helpful

**Template 1A: "Which MCP should I use for X?"**

> There are a few options depending on the use case — [answer their specific question with genuine info].
>
> For finding these in the future mid-session: I built a hook called Dispatch that does this automatically. It detects when you shift tasks and searches the skills.sh registry + your installed plugins, ranks them 0–100, and injects the list before Claude responds. Saved me from having to remember what I installed.
>
> https://github.com/VisionAIrySE/Dispatch — free to use, source is open.

---

**Template 1B: "How do you manage Claude Code plugins?"**

> I was bad at this for a long time. Installed things and forgot they existed.
>
> Now I use Dispatch — a hook that watches my session and surfaces relevant plugins when I shift tasks. If I'm Flutter debugging and pivot to writing tests, it catches the shift and shows what I have installed that's relevant (plus anything uninstalled in the registry).
>
> It also has a PreToolUse hook that intercepts before Claude invokes a skill and checks if a better marketplace alternative exists. I've caught a few cases where I had a more specific tool installed that Claude wasn't reaching for.
>
> https://github.com/VisionAIrySE/Dispatch — open source, free tier.

---

**Template 1C: "Are there hooks for Claude Code?"**

> Claude Code has two hook points: `UserPromptSubmit` (fires on every message) and `PreToolUse` (fires before any tool call). They're documented at claude.ai/code.
>
> I built Dispatch on top of both. Hook 1 does task shift detection + plugin ranking. Hook 2 intercepts tool calls and checks if a better marketplace alternative exists.
>
> The code is a decent reference for how to structure hooks: https://github.com/VisionAIrySE/Dispatch — `dispatch.sh` for UserPromptSubmit, `preuse_hook.sh` for PreToolUse. Both have to complete within 10 seconds or CC bypasses them.

---

### Tier 2 — Proactive/Community

**Template 2A: "Show your setup" threads**

> Current CC setup:
>
> Plugins: claude-plugins-official marketplace + a few Firebase and Supabase skills from the skills.sh registry.
>
> The thing that actually made the plugin ecosystem useful for me: Dispatch (https://github.com/VisionAIrySE/Dispatch). It's a two-hook system — detects when I shift tasks mid-session, searches the registry, and ranks what I have vs. what exists. Also intercepts before Claude invokes a skill and surfaces better alternatives if they exist.
>
> Before this I was installing plugins and forgetting them within a week. Now the right tools show up when I actually need them.

---

**Template 2B: "What tools do you use with CC?" threads**

> Beyond the usual suspects (GitHub MCP, filesystem tools), the thing that's made the biggest difference is Dispatch: https://github.com/VisionAIrySE/Dispatch
>
> It's a hook that detects when you shift tasks mid-session and surfaces relevant plugins/skills from both your install and the live registry. I was surprised how much of my install I was leaving idle.
>
> Free hosted tier, open source, runs entirely locally in BYOK mode if you prefer. Requires Python 3.8+ and Node.js.

---

### Tier 3 — Cold Outreach (GitHub Stargazers)

**Template 3A: For stargazers of skills.sh or awesome-agent-skills**

> Hey — saw you starred [repo name]. Figured you'd be in the right crowd for something I built.
>
> Dispatch is a Claude Code hook that uses the skills.sh registry at runtime — it detects when you shift tasks mid-session and auto-searches for relevant skills (installed and uninstalled), ranks them 0–100, and surfaces the list before Claude responds. Think of it as runtime discovery on top of the registry you're already following.
>
> Free, open source: https://github.com/VisionAIrySE/Dispatch
>
> Happy to hear what you think if you try it.

---

**Template 3B: For stargazers of claude-code-related repos**

> Hey — noticed you're watching Claude Code tooling. Built something you might find useful.
>
> Dispatch is a two-hook system for CC: detects task shifts using Haiku (~100ms on every message), ranks your installed plugins against the live skills registry on confirmed shifts, and intercepts PreToolUse calls to catch when Claude reaches for a weaker tool when a better marketplace alternative exists.
>
> Source is open, 93 tests, free to run with BYOK or free hosted tier:
> https://github.com/VisionAIrySE/Dispatch
>
> Would genuinely value technical feedback if you dig into the code.

---

**Template 3C: For stargazers of MCP-related repos**

> Hi — saw you starred [repo name], so you're clearly thinking about the MCP ecosystem. Built something adjacent you might find useful.
>
> Dispatch hooks into Claude Code's PreToolUse event — before CC invokes an MCP tool, it checks the marketplace for alternatives and surfaces a higher-scoring option if one exists. From the other direction, it also does task-shift detection and auto-discovers relevant MCPs/skills from the registry mid-session.
>
> Open source: https://github.com/VisionAIrySE/Dispatch
>
> Happy to chat if you have questions about the hook architecture.

---

## 8. awesome-claude-code PR Description

**PR Title:**
```
Add Dispatch — runtime skill router hook
```

**Line to add** (in the Hooks section):

```markdown
- [Dispatch](https://github.com/VisionAIrySE/Dispatch) — Runtime skill router: detects task shifts, ranks installed plugins + skills.sh registry results 0–100, and intercepts PreToolUse calls to surface better marketplace alternatives before Claude responds.
```

**PR Body:**

```markdown
## What this adds

Dispatch is a two-hook tool for Claude Code that addresses runtime plugin discovery.

**UserPromptSubmit hook:** Detects when the user shifts task domain or mode mid-session (e.g., flutter-debugging → writing tests). On a confirmed shift, searches installed plugins, agent skills, and the skills.sh registry. Ranks everything 0–100 using Haiku (free/BYOK) or Sonnet (Pro). Injects the ranked recommendation list into Claude's context before it responds.

**PreToolUse hook:** Before Claude invokes a Skill, Agent, or MCP tool, searches the marketplace for that task category. If a marketplace tool scores ≥10 points higher than CC's chosen tool, blocks and surfaces the recommendation. User types "proceed" to bypass.

## Why it fits here

- Hooks section is the right home — both hooks are the core of the project
- Addresses the invisible plugin problem: 500+ skills/plugins exist, most users actively use a handful
- Open source (MIT), 93 unit tests, Python 3.8+ and Bash
- Works with both a free hosted token and BYOK (Anthropic API key)

## Links

- GitHub: https://github.com/VisionAIrySE/Dispatch
- Hosted tier: https://dispatch.visionairy.biz
- skills.sh registry (searched at runtime): https://skills.sh
```

---

## 9. Dev.to Article Outline

**Title:**
```
How I built a runtime skill router for Claude Code (and what I learned about hooks)
```

**Subtitle:**
```
Two hooks, 93 tests, and a discovery that Claude Code's transcript format isn't what you'd expect
```

---

### Section 1: The Problem I Was Trying to Solve

- The Claude Code plugin ecosystem: 500+ plugins and skills across multiple marketplaces
- The actual usage reality: most developers actively use a handful, forget the rest exist
- The specific failure mode: you install a skill, forget you have it, and Claude doesn't reach for it unprompted
- Why this matters: the right tool mid-task often produces qualitatively better output
- The pivot moment: mid-Flutter-debugging session, shifted to tests, realized the TDD skill I installed was sitting idle

**Narrative beat:** "I wasn't looking for a plugin discovery problem to solve. I was just annoyed."

---

### Section 2: What Dispatch Does (User-Facing)

- Hook 1 fires on every message — shift detection in ~100ms, silent when nothing changes
- On a confirmed shift: ranked list of relevant tools (installed and uninstalled) surfaces into Claude's context
- What the output looks like (include the README example output block)
- Hook 2: the PreToolUse intercept — what it catches and why the bypass design matters (one word: "proceed")
- The user experience goal: invisible when irrelevant, actionable when it fires

---

### Section 3: Architecture Decisions

**Why two hooks instead of one:**
- UserPromptSubmit is the right place to detect task context and prepare recommendations
- PreToolUse is the right place to catch tool choice mismatches at the moment of use
- Each hook has a different latency budget and a different output contract

**The task type model:**
- Open-ended Haiku-generated labels (`react-native`, `docker-aws-github-actions`)
- 7-mode MECE action taxonomy (discovering/designing/building/fixing/validating/shipping/maintaining)
- `category_mapper.py` normalizes open-ended labels → 16 MECE categories → targeted registry search
- Why MECE matters: exhaustive coverage, no overlap, clean category-to-search-terms mapping

**Ranking design:**
- All tools (installed + uninstalled) scored together on a single 0–100 scale
- Score gap truncation: cut the list at the first ≥25-point cliff (prevents irrelevant tail items)
- Only items scoring 40+ are shown; top 6 maximum
- Installed plugin descriptions are full text; uninstalled skills are ranked from ID alone — acknowledged as a limitation

**State management between hooks:**
- Hook 1 writes `state.json`; Hook 2 reads it
- Bypass token (120s TTL) prevents Hook 2 from re-blocking the same tool call
- Broad exception catches throughout — hooks must never block Claude under any circumstances

---

### Section 4: What I Learned About Claude Code Internals

**The transcript format gotcha:**
- CC transcript JSONL entries nest `role` inside `message`, not at the top level
- `isMeta=True` entries are CC system messages (loaded skill file text, up to 1,400 words) — not user input
- Tool results serialized as strings starting with `[{` — not user input
- Impact: without these filters, Haiku was receiving skill file content as conversation context, and shift detection was firing on ghost signals
- How I found it: day of debugging, eventually diffed the raw transcript against what `extract_recent_messages` was passing

**Hook output routing:**
- stdout goes into Claude's context (user never sees it directly)
- stderr is captured and suppressed by CC
- For recommendations to surface as Claude's context, stdout is the right channel
- Hook 2 (PreToolUse) uses exit code 2 to block the tool call — exit 0 passes through

**The 10-second hard timeout:**
- CC enforces a 10s total timeout per hook — hook crashes or hangs, Claude proceeds normally
- Stage 1 (Haiku): ~500ms
- Stage 2 (registry + ranking): ~3–5s
- npx timeout set to 6s, not the default 20s
- What this means for reliability: tight budget, but also means the hook can never truly block you

**Portability: GNU vs BSD:**
- `head -n -1` is GNU-only — BSD head on macOS interprets it as "print 1 line"
- `sed '$d'` (delete last line) is portable
- Found this when a colleague tried to install on macOS and the HTTP response body parser was silently eating the entire response

---

### Section 5: The Hosted Mode and Collective Intelligence

- Why local BYOK and hosted produce different recommendations over time
- What the hosted endpoint aggregates: install events and bypass events (tool interceptions where user proceeded anyway)
- How aggregate signal changes ranking: actual install rate per task type becomes a factor alongside LLM scoring
- The privacy tradeoff: what is and isn't stored (task types stored, not conversation content)
- Free tier limits (8 detections/day) vs. Pro ($10/month, unlimited + Sonnet ranking — first 250 subscribers at $6/month for life)
- Sonnet vs. Haiku for ranking: materially sharper reasons and better score calibration

---

### Section 6: Testing a Hook-Based System

- The fundamental challenge: you cannot simulate `UserPromptSubmit` or `PreToolUse` from inside a CC session
- Unit test strategy: mock the Haiku responses, test each module independently (93 tests across 4 modules)
- What the unit tests don't cover: the transcript parsing edge cases in production
- Manual testing workflow: new CC session per test run, specific message sequences to trigger shifts
- Where the gaps are: live registry responses, timing behavior at the 10s timeout boundary

**Test modules and what they verify:**
- `test_classifier.py` (19 tests): shift detection logic, confidence thresholding, smart skipping on short messages
- `test_evaluator.py` (39 tests): registry search, ranking, score gap truncation, installed vs. uninstalled handling
- `test_interceptor.py` (22 tests): bypass token lifecycle, tool name parsing, block threshold logic
- `test_category_mapper.py` (13 tests): keyword matching, unknown category logging, compound type handling

---

### Section 7: Results and Honest Assessment

- What works well: shift detection granularity (domain + mode separately), the PreToolUse intercept catching cases I wouldn't have caught manually
- What's rough: ranking quality for uninstalled skills (inferred from ID, not description), cold-start problem (needs plugins installed to be useful)
- The improvement curve: recommendations improve as you install more plugins; Pro tier improves further as more users contribute aggregate signal
- What I'd do differently: build the category mapper before the task type generator, not after

**The actual usage story:** Three weeks of daily use. Caught a case where Claude was about to invoke a generic GitHub skill when I had a GitHub Actions-specific skill installed that scored 30 points higher. That single intercept was worth the build time.

---

### Section 8: Install and Resources

- One-command install
- Requirements (Python 3.8+, Node.js, free token or Anthropic key)
- Where to look first in the source (classifier.py, preuse_hook.sh)
- Contributing: classifier taxonomy and evaluator ranking logic are the best starting points
- Link to repo, hosted tier, skills.sh registry

---

**Narrative Arc Summary:**

Discovered problem through personal frustration → built minimal solution → hit unexpected technical walls (transcript format, hook output routing, GNU/BSD portability) → architecture evolved from one hook to two as the intercept use case became clear → launched with honest limitations stated → collective intelligence as the long-term differentiation story

**Tone notes for writing:**
- First person throughout
- Lead each section with a specific example or concrete observation, not a general claim
- Acknowledge what doesn't work as readily as what does
- Don't oversell the collective intelligence angle — describe the mechanism, let readers draw their own conclusions about value
- Technical specifics are the credibility signal, not marketing language

---

*End of marketing content package.*
