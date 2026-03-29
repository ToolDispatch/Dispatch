# ToolDispatch — Marketing Content Package

**Updated:** 2026-03-28
**Version:** v1.0.0
**Repo:** https://github.com/ToolDispatch/Dispatch
**Platform:** https://tooldispatch.visionairy.biz

**Core tagline:** Your Claude Code insurance policy — best tool for the job up front, code that connects before it breaks.
**Dispatch half:** "best tool for the job up front" | **XF Audit half:** "code that connects before it breaks"

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
Show HN: ToolDispatch – Claude Code insurance policy: best tool for the job up front, code that connects before it breaks
```

**Body:**

Last week I shifted to Flutter work mid-session. Before I typed a single word, Dispatch had already injected this into Claude's context:

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

I hadn't asked. Claude hadn't started. Dispatch just knew I shifted tasks and showed me exactly what existed — grouped by type, with install commands. That's the problem it solves first.

Then, ten minutes later, Claude was about to invoke a generic debugging skill. It had no idea I had a purpose-built Flutter tool installed. It scored 30 points higher for what I was doing. That's the second problem Dispatch solves.

Claude Code has access to 10,978 tools across 6 sources — skills.sh, glama.ai, Smithery.ai, the official MCP registry, and both plugin marketplaces. At runtime, Claude picks from a handful of defaults. It has no mechanism to know what's available, what's installed, or what actually performs best for the task in front of it. Every session, you're flying blind on tool selection.

And it's getting worse, not better. New tools ship every week. The ecosystem is exploding. The gap between what Claude knows about at runtime and what actually exists widens every day. You can't track it manually. Most developers don't even try. They use the same tools they installed months ago, unaware that something purpose-built for exactly their stack launched last Tuesday.

Dispatch is two hooks. Hook 1 (UserPromptSubmit) runs on every message — ~100ms, silent when nothing changed. When you shift tasks, it maps the shift to one of 16 MECE categories, queries the catalog, and surfaces a grouped Plugins/Skills/MCPs block with install commands directly into Claude's context before it responds. Hook 2 (PreToolUse) fires before Claude invokes any Skill, Agent, or MCP tool. It compares CC's chosen tool against marketplace alternatives on a 0–100 scale. If a better tool scores 10+ points higher, it blocks and shows you the comparison. One word — "proceed" — to override.

The catalog isn't static. It's rebuilt daily from live sources, scored by real behavioral signals: install counts, GitHub stars, forks, freshness. Tools that developers actually reach for score higher than tools that just exist. And every time a Dispatch user installs a recommended tool — or bypasses a block — that signal feeds back into the scores. The more developers use it, the sharper it gets for everyone.

This is the part I find most interesting: we now have category-level data on where Claude Code's native tool choices consistently underperform marketplace alternatives. Not anecdotes — scored intercepts across real sessions. I'm calling it the CC Weakness Map. It's currently showing the biggest gaps in mobile development, database tooling, and cloud infrastructure. That's behavioral data Anthropic can't collect internally.

Install is one command:
```bash
bash <(curl -fsSL https://raw.githubusercontent.com/ToolDispatch/Dispatch/main/install.sh)
```

Requires Python 3.8+ and Node.js. Two modes: BYOK (your own Anthropic/OpenRouter key, full dual-layer locally) or Hosted (free token at tooldispatch.visionairy.biz, 8 detections/day free, Pro for unlimited + pre-ranked catalog). 372 tests across 8 modules if you want to read the code before installing.

One more thing worth saying: if you're newer to Claude Code and feel like it's not quite clicking — like the results aren't as good as you hoped — this is often why. Native CC with no tool awareness is Claude reaching for whatever it knows. CC with Dispatch is Claude reaching for the best tool available for what you're actually doing. The difference is significant. You need it today. You'll need it more tomorrow.

Honest limitations: the intercept is only as good as what's in the catalog. Tools with no description or no GitHub repo get a lower baseline score. Cold-start is real — the more you use it, the better the catalog gets for your stack. And adding ~100–500ms to every message (Stage 1) and ~3–5s on confirmed shifts is a real cost — still within CC's 10s hook timeout, but not nothing.

Looking for feedback on: whether the 10-point gap threshold feels right, whether the proactive grouping format is useful or noisy, whether the PreToolUse intercept is useful or annoying in practice, and what task types it consistently misses. The category mapper is the easiest place to contribute.

---

## 2. r/ClaudeCode Post

**Title:**
```
Claude keeps picking mediocre tools when better ones exist. I built something that intercepts it — and tells you what to install before you even ask.
```

**Body:**

Here's a thing that happens silently every CC session: Claude reaches for a tool. Not because it's the best one for your task — because it's the one it knows about. The GitHub skill when you have a GitHub Actions-specific skill installed. The generic testing approach when you have a purpose-built TDD skill. The built-in filesystem tool when you have an MCP that scores 40 points higher for exactly what you're doing.

But here's the deeper problem, and it's getting worse: most users never manually invoke a tool at all. They don't know what exists. They installed three MCPs six months ago, installed two more last week, and have no idea which one Claude should reach for mid-session. And new tools ship every week — the ecosystem is exploding. You can't track it manually. Claude certainly can't.

If you're newer to CC and feel like it's not quite clicking — the results aren't as sharp as you hoped — this is often why. Native CC has no runtime awareness of the tool ecosystem. It doesn't know about skills.sh. It doesn't know what you installed last week. It doesn't know what's in the MCP registries. It picks what it knows. The jump from CC native to CC with the right tools for every task is real. That's the gap Dispatch closes.

I catalogued 10,978 tools this week across 6 sources (skills.sh, glama.ai, Smithery.ai, official MCP registry, both CC plugin marketplaces). Then I built Dispatch: two hooks that fire at the two moments that matter.

**At every task shift:** ~100ms check. When you shift topics, it surfaces a grouped list of Plugins, Skills, and MCPs available for that category — with install commands — directly into Claude's context before it responds. You find out what exists before Claude has to guess.

**Before every tool call:** If Claude is about to invoke a Skill, Agent, or MCP and a marketplace alternative scores 10+ points higher, it blocks. You see the comparison. One word to proceed if you disagree.

BYOK gets both layers — proactive discovery and intercept — fully local. Hosted free tier gets the intercept; proactive layer coming in V2.

The thing that surprised me most building this: we now have category-level data on where Claude's native tool selection is weakest. Mobile development. Database tooling. Cloud infrastructure. Not impressions — scored behavioral data from real intercepts. The gap in some categories is significant.

Repo: https://github.com/ToolDispatch/Dispatch

Would be curious whether the detection granularity feels right for different workflows.

---

## 3. r/ClaudeDev Post

**Title:**
```
I built a two-hook runtime that proactively surfaces tools and intercepts Claude's tool selection — here's what 10,978 catalogued tools revealed about where CC underperforms
```

**Body:**

I want to write up the architecture because the findings were more interesting than the implementation.

**The setup:** Two hooks — UserPromptSubmit for task shift detection, PreToolUse for tool selection interception. Hook 1 runs in three stages: Stage 1 classifies the shift with Haiku (~100ms), Stage 2 maps the task type to one of 16 MECE categories and writes state, Stage 3 queries the pre-ranked catalog and injects a grouped Plugins/Skills/MCPs block with install commands directly into Claude's context before it responds. Hook 2 reads that state, scores CC's chosen tool alongside alternatives (0–100), and exits 2 to block if the gap is 10+ points.

The Stage 3 output format looks like this:

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
```

This fires once per topic per session. Not on every message.

**What the catalog revealed:**

I crawled skills.sh, glama.ai, Smithery.ai, registry.modelcontextprotocol.io, and both CC plugin marketplaces. After dedup and a MIN_INSTALLS ≥ 20 filter on skills, the catalog settled at ~11K tools. Scored by installs (60%), GitHub stars (25%), forks (15%), staleness penalty above 18 months.

Then I ran the first real sessions and looked at where blocks were firing. The CC Weakness Map — category-level comparison of average CC tool scores vs. top marketplace alternatives — showed consistent gaps in:

- **Mobile development:** CC defaults score in the 50s. Purpose-built Flutter/React Native skills score in the 90s.
- **Database tooling:** Generic approach vs. stack-specific MCPs. 25–35 point gaps common.
- **Cloud infrastructure:** Same pattern. CC doesn't reach for the Terraform/AWS-specific tools that score 2x higher for those tasks.

That's not a surprise — it's exactly what you'd expect when Claude doesn't have runtime marketplace awareness. But having it scored and categorized is the interesting part. This is the data you'd need to make the argument to Anthropic that the plugin ecosystem is underutilized by default.

**A few things I learned building this:**

CC transcript JSONL nests `role` inside `message`, not at the top level. `isMeta=True` entries are loaded skill file content — not user messages. Tool results serialize as strings starting with `[{`. Without filtering all three, Haiku sees skill file text as conversation context and fires on ghost signals. Burned a day on this.

Haiku returns markdown-wrapped JSON even when you ask it not to. Always strip the fence.

`head -n -1` is GNU-only. `sed '$d'` is portable. Found this the hard way on macOS.

Exit code 2 from a PreToolUse hook blocks the tool call. Exit 0 passes through. Stdout goes into Claude's context. Stderr is suppressed. The whole hook must complete within 10 seconds or CC bypasses it regardless.

372 tests across 8 modules. The hardest thing to test is transcript parsing — the edge cases keep multiplying.

Repo: https://github.com/ToolDispatch/Dispatch

Happy to go deep on the hook architecture or the catalog scoring logic.

---

## 4. Twitter/X Launch Thread

**Tweet 1 — The hook:**
```
Claude just picked the wrong tool for your task.

There's a better one installed on your machine.
It scores 35 points higher.
Claude doesn't know it exists.

This happens every session.

Thread: Dispatch, a dual-layer runtime for Claude Code 🧵
```

**Tweet 2 — The scale + urgency:**
```
I crawled 10,978 tools this week.

skills.sh. Smithery.ai. glama.ai.
Official MCP registry. Both CC plugin marketplaces.

Scored by real signals — installs, stars, forks, freshness.

Claude Code knows about almost none of them at runtime.

And new ones ship every week.
The gap between what Claude knows and what exists — grows every day.

You don't know what you don't know.
Neither does Claude.
And that's going to get worse, not better.
```

**Tweet 3 — Hook 1 (proactive discovery):**
```
Hook 1 fires on every message. ~100ms.

Detects if you shifted tasks (flutter-debugging → writing tests).

On a confirmed shift: queries the catalog, groups what's available by type — Plugins, Skills, MCPs — and injects them into Claude's context with install commands before it responds.

You see what exists before Claude has to guess.
```

**Tweet 4 — What it looks like:**
```
What proactive discovery looks like when it fires:

[Dispatch] Recommended tools for flutter-building:

Plugins:
  • flutter-mobile-app-dev [94/100]
    Install: claude install plugin:anthropic:flutter-mobile-app-dev

Skills:
  • VisionAIrySE/flutter@flutter-dev [88/100]
    Install: claude install VisionAIrySE/flutter@flutter-dev

MCPs:
  • fluttermcp [82/100]
    Install: claude mcp add fluttermcp npx -y @fluttermcp/server

Before you've typed a single word.
```

**Tweet 5 — Hook 2 (the intercept):**
```
Hook 2 is the safety net.

Fires before Claude invokes any Skill, Agent, or MCP.

Scores CC's chosen tool vs marketplace alternatives: 0–100.

Gap ≥ 10 points → blocks. Shows you the comparison.

"proceed" to override. That's it. One word.

(You already know what was available — Hook 1 told you.)
```

**Tweet 6 — The intercept moment:**
```
What it looks like when it fires:

[DISPATCH] CC is about to use 'superpowers:systematic-debugging' for Flutter work.
CC score: 58/100

1. flutter-mobile-app-dev [94/100] ← TOP PICK
   Purpose-built for Flutter/Dart. Widget tree inspection.
   Install: npx skills add flutter-mobile-app-dev -y

Gap: 36 points. Claude was about to leave 36 points on the table.
```

**Tweet 7 — The data:**
```
The CC Weakness Map.

Category-level data on where Claude's tool selection consistently underperforms:

📱 Mobile: CC ~55, market ~92 (+37)
🗄️ Database: CC ~61, market ~88 (+27)
☁️ Cloud infra: CC ~58, market ~85 (+27)

Not impressions. Scored behavioral data from real intercepts.
```

**Tweet 8 — Network effect:**
```
Here's the part that compounds.

Every install after a Dispatch recommendation → signal.
Every bypass → signal.
Every blocked intercept → signal.

The catalog scores update from real developer behavior.
Not LLM guesses. What developers actually reach for.

Gets sharper with every user.
```

**Tweet 9 — Founding tier:**
```
Hosted Pro: pre-ranked catalog, <200ms responses, Sonnet ranking.

First 300 users: $6/month, locked for life.
After that: $10/month.

You're not just buying a tool.
You're locking in a rate before the network effect makes this obviously worth more.

300 seats. Building now.
```

**Tweet 10 — Install:**
```
Install:

bash <(curl -fsSL https://raw.githubusercontent.com/ToolDispatch/Dispatch/main/install.sh)

Sign in with GitHub. Copy the token. Start a new CC session.

Free hosted tier to start.
No API key required.

https://github.com/ToolDispatch/Dispatch
```

**Tweet 11 — CTA:**
```
372 tests. MIT licensed. Read every line before installing.

The plugin ecosystem is deeper than most Claude Code users know.

Dispatch makes Claude actually use it — and tells you what exists before Claude has to guess.

⭐ https://github.com/ToolDispatch/Dispatch
tooldispatch.visionairy.biz
```

---

## 5. Discord Message Templates

### Variant A — General dev server #tools channel

```
If you use Claude Code seriously, this is the gap nobody talks about: Claude has no runtime awareness of the tool ecosystem. It picks what it knows — not what's best for your task. And most of what exists, you've never heard of.

I catalogued 10,978 tools across skills.sh, Smithery.ai, glama.ai, and the MCP registries. Then built Dispatch: two CC hooks that fire at the two moments that matter.

Hook 1: When you shift tasks, Dispatch immediately surfaces the best available tools — grouped by type (Plugins, Skills, MCPs) with install commands — directly in Claude's context before it responds. You find out what exists before Claude starts guessing.

Hook 2: Before Claude invokes a tool, it scores CC's choice against marketplace alternatives (0–100). If the gap is 10+ points, it blocks. One word to proceed.

GitHub: https://github.com/ToolDispatch/Dispatch
Free to start, no API key required. BYOK gets both layers.
```

---

### Variant B — Claude Code official server

```
Something I've been working on that's relevant here: Dispatch is a two-hook runtime for CC that addresses a gap I kept running into.

The problem: Claude picks tools from what it knows — its defaults and whatever you've explicitly invoked before. It has no awareness of the 10,000+ tools across skills.sh, Smithery, glama.ai, the official MCP registry, and both plugin marketplaces. No signal about which tools actually perform best for which tasks. Most users don't even know what exists.

**What Dispatch does:**

Hook 1 (UserPromptSubmit, ~100ms): Detects task shifts. On a confirmed shift, maps to one of 16 MECE categories, queries the catalog, and injects a grouped Plugins/Skills/MCPs block with install commands into Claude's context before it responds. Silent when nothing changed. Fires once per topic per session.

Hook 2 (PreToolUse): Before Claude invokes any Skill, Agent, or MCP — scores CC's choice vs marketplace alternatives on a 0–100 scale. Blocks if a better tool scores 10+ points higher. You type "proceed" to override.

BYOK gets both layers, fully local. Hosted free tier gets Hook 2 intercept; Hook 1 proactive discovery coming V2.

The catalog is built from 10,978 tools crawled daily, scored by real signals (installs, stars, forks, freshness). Behavioral data from intercepts feeds back in. Gets sharper with use.

Free hosted tier (8/day) or BYOK. Pro = pre-ranked catalog (<200ms), Sonnet ranking, unlimited.

https://github.com/ToolDispatch/Dispatch

372 tests if you want to audit before installing. Happy to discuss the hook architecture.
```

---

### Variant C — MCP community server

```
For folks building or maintaining MCPs: I built a runtime layer for CC that actively surfaces your tools to the right users at the right moment — both proactively and at tool-call time.

Hook 1 (proactive): When a CC user shifts to a task category matching your MCP's purpose, Dispatch surfaces it in a grouped Plugins/Skills/MCPs block — with install command — directly in Claude's context before they type anything. This fires once per topic per session. Your MCP gets seen before Claude has to guess.

Hook 2 (intercept): When Claude is about to invoke a tool and your MCP scores higher for that task category, it gets surfaced in the comparison — scored, with install command — before Claude proceeds.

The catalog now covers 4,800+ MCPs across glama.ai, Smithery.ai, and the official registry. Scored by GitHub stars/forks/freshness. Better quality signal than raw install count for repos that are newer.

From the distribution angle: if you publish an MCP, Dispatch surfaces it to CC users doing exactly the tasks it's built for — at both the discovery moment and the decision moment. No manual discovery required on their end.

Repo: https://github.com/ToolDispatch/Dispatch
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
- "Claude Code tool selection"
- "Claude picks wrong tool"

**Plugin/tool discovery pain:**
- "too many Claude Code plugins"
- "Claude Code plugin not working"
- "Claude Code skill not loading"
- "Claude Code context plugin"
- "how to use Claude Code plugins"
- "Claude Code plugin management"
- "install Claude Code skill"
- "Claude Code ignoring my skills"
- "Claude not using installed plugins"

### Medium Intent — Related Pain Points

**Workflow friction:**
- "Claude Code workflow tips"
- "Claude Code productivity"
- "getting more from Claude Code"
- "Claude Code mid-session"
- "Claude Code session management"
- "Claude Code best practices"
- "Claude Code setup"
- "improve Claude Code"

**MCP discovery:**
- "find MCP servers"
- "MCP registry"
- "modelcontextprotocol registry"
- "MCP server list"
- "Claude MCP plugins"
- "awesome MCP servers"
- "Smithery MCP"
- "glama MCP"

**Task switching and context:**
- "AI coding tool switching"
- "Claude Code different tasks"
- "Claude wrong tool"
- "Claude Code tool choice"

**Proactive discovery:**
- "claude code tool discovery"
- "claude code plugin recommendations"
- "best plugins for my task"
- "claude code what tools to install"
- "claude code proactive recommendations"

### Competitor and Related Project Mentions

- "SummonAI Claude"
- "claude-plugins-official"
- "awesome-agent-skills"
- "firebase agent-skills"
- "supabase agent-skills"
- "flutter-mobile-app-dev Claude"
- "superpowers skills Claude"
- "github-actions Claude Code"
- "systematic-debugging Claude"

### Brand Monitoring

- "Dispatch VisionAIrySE"
- "tooldispatch.visionairy.biz"
- "VisionAIrySE"
- "Dispatch Claude Code"
- "skill router Claude"
- "@VisionAIrySE"

### Technical Community Signals

- "UserPromptSubmit Claude"
- "PreToolUse Claude"
- "Claude Code hooks tutorial"
- "hook Claude Code session"
- "Claude Code settings.json hooks"
- "Claude hook exit code 2"
- "PreToolUse block tool call"

---

## 7. Response Templates

### Tier 1 — Reactive/Helpful

**Template 1A: "Claude isn't using my installed plugins/skills"**

> This is actually a real gap in how CC works — Claude has no runtime awareness of what's in the ecosystem, installed or not. It reaches for defaults.
>
> I built Dispatch specifically for this: two hooks that address both sides of the problem. Hook 1 proactively surfaces available tools grouped by type (Plugins, Skills, MCPs with install commands) when you shift tasks — before Claude has to pick. Hook 2 intercepts before Claude invokes a tool and checks if something better-suited to your current task exists. If you have a purpose-built skill installed that scores higher, it surfaces it before Claude proceeds.
>
> Free to start: https://github.com/ToolDispatch/Dispatch

---

**Template 1B: "Which MCP should I use for X?"**

> [Answer their specific question with genuine info — specific tool names, honest tradeoffs.]
>
> For finding the right MCP for a task automatically mid-session: I built Dispatch — a CC hook that proactively surfaces relevant MCPs when you shift tasks (grouped with install commands, before Claude starts), and also intercepts before Claude invokes a tool to surface better alternatives from a catalog of 4,800+ MCPs scored by real signals. It fires at the moment it matters, not at install time.
>
> https://github.com/ToolDispatch/Dispatch — free tier, open source.

---

**Template 1C: "Are there hooks for Claude Code?"**

> CC has two hook points: `UserPromptSubmit` (fires on every message) and `PreToolUse` (fires before any tool call). Both take a command, get 10 seconds, and exit code 2 on a PreToolUse hook blocks the tool call.
>
> I built Dispatch on both — UserPromptSubmit for task shift detection, catalog query, and proactive grouped recommendations (Plugins/Skills/MCPs with install commands); PreToolUse for intercepting bad tool choices before they happen. The code is a decent real-world reference for both hooks:
>
> https://github.com/ToolDispatch/Dispatch — `dispatch.sh` and `dispatch-preuse.sh`.

---

**Template 1D: "How do you get Claude to use better tools?"**

> Two-part answer: you want to know what exists before Claude picks, and you want a safety net when it picks wrong.
>
> I built Dispatch for both. Hook 1 fires when you shift tasks and immediately shows you the best available tools — grouped by type (Plugins, Skills, MCPs) with install commands — in Claude's context before it responds. You find out what's available before Claude has to guess. Hook 2 intercepts before Claude invokes any Skill, Agent, or MCP, scores CC's choice against a catalog of 10,978 marketplace tools (0–100), and blocks if a better-suited tool scores 10+ points higher. One word to override.
>
> https://github.com/ToolDispatch/Dispatch

---

### Tier 2 — Proactive/Community

**Template 2A: "Show your CC setup" threads**

> Current setup beyond the usual MCPs:
>
> Dispatch (https://github.com/ToolDispatch/Dispatch) — a two-hook runtime. When I shift tasks, it immediately shows me what tools exist for that category — Plugins, Skills, MCPs, grouped with install commands — before Claude starts. Then if Claude still reaches for something suboptimal, Hook 2 intercepts and shows the scoring comparison. I've had it surface a purpose-built skill I'd installed months ago and never reached for manually. The proactive layer is the one I didn't expect to find useful.
>
> Free to run, BYOK or hosted free tier. If you're already invested in the CC plugin ecosystem, it's the layer that makes that investment actually pay off.

---

**Template 2B: "What tools are you using with CC?" threads**

> The one that changed how I think about the plugin ecosystem: Dispatch.
>
> It's a dual-layer runtime — Hook 1 proactively surfaces available tools (grouped by type: Plugins, Skills, MCPs with install commands) when you shift tasks, so you know what exists before Claude picks. Hook 2 intercepts before Claude picks a tool, compares it against 10,978+ catalogued alternatives scored by real signals, and blocks if something better-suited scores 10+ points higher.
>
> What I didn't expect: the CC Weakness Map it generates. Category-level data showing where Claude's default tool choices consistently underperform. Mobile development and database tooling have the biggest gaps in my sessions.
>
> https://github.com/ToolDispatch/Dispatch

---

### Tier 3 — Cold Outreach (GitHub Stargazers)

**Template 3A: Stargazers of skills.sh or awesome-agent-skills**

> Hey — saw you starred [repo]. Figured you're thinking about the CC tool ecosystem.
>
> I catalogued 10,978 tools this week across skills.sh, Smithery, glama.ai, and the MCP registries. Then built Dispatch: two CC hooks. The first proactively shows you what tools exist for your task the moment you shift topics — Plugins, Skills, MCPs grouped with install commands, in Claude's context before it responds. The second intercepts before Claude commits to a tool choice and shows you the scoring comparison if a better option exists.
>
> The gap between what Claude defaults to and what's available is bigger than I expected. Some categories are 30+ points apart.
>
> Free, open source: https://github.com/ToolDispatch/Dispatch
>
> Happy to hear what you think if you try it.

---

**Template 3B: Stargazers of claude-code-related repos**

> Hey — noticed you're watching CC tooling. Built something you might find worth trying.
>
> Dispatch is a dual-layer runtime for CC. On task shift, it proactively injects the best available tools — grouped by type with install commands — into Claude's context before it responds. Before every tool call, it compares CC's choice against 10K+ catalogued alternatives on a 0–100 scale. If a better tool exists for the current task, it surfaces it. You decide whether to proceed.
>
> The catalog is rebuilt daily from live sources scored by real behavioral signals. Gets sharper with use.
>
> Source open, 372 tests: https://github.com/ToolDispatch/Dispatch
>
> Technical feedback welcome — especially on detection granularity.

---

**Template 3C: Stargazers of MCP-related repos**

> Hi — saw you starred [repo]. You're clearly invested in the MCP ecosystem.
>
> I built Dispatch: a dual-layer CC runtime that surfaces MCPs at two moments. Hook 1 proactively shows relevant MCPs when CC users shift to a matching task category — grouped with install commands, before Claude starts. Hook 2 intercepts before Claude invokes an MCP and checks whether a higher-scoring alternative exists in a catalog of 4,800+ MCPs (glama.ai, Smithery, official registry). If the gap is 10+ points, it blocks and shows the comparison.
>
> From the distribution angle: if you publish an MCP, Dispatch surfaces it to CC users doing the exact tasks it's built for — at the discovery moment and at the decision moment.
>
> Open source: https://github.com/ToolDispatch/Dispatch

---

## 8. awesome-claude-code PR Description

**PR Title:**
```
Add Dispatch — dual-layer tool discovery and intercept runtime for Claude Code
```

**Line to add** (Hooks section):

```markdown
- [Dispatch](https://github.com/ToolDispatch/Dispatch) — Dual-layer CC runtime: on task shift, proactively surfaces Plugins/Skills/MCPs with install commands grouped by type into Claude's context; before every tool call, scores CC's choice against 10,978 catalogued alternatives (0–100) and blocks when a better-suited tool exists. Free hosted tier or BYOK.
```

**PR Body:**

```markdown
## What this adds

Dispatch is a two-hook CC runtime that addresses the tool discovery gap at both ends — before Claude picks, and at the moment Claude picks.

**The problem it addresses:** Claude has no awareness of the plugin/MCP ecosystem at runtime. It picks from defaults — not from what's installed, not from what's available, not from what actually performs best for the current task. Most users don't know what exists. With 10,978+ tools now catalogued across skills.sh, Smithery.ai, glama.ai, the official MCP registry, and both CC plugin marketplaces, the gap between what Claude picks and what's available is significant.

**Hook 1 (UserPromptSubmit):** Detects task domain/mode shifts (~100ms). On a confirmed shift, maps to one of 16 MECE categories, queries the pre-ranked catalog, and injects a grouped Plugins/Skills/MCPs block with install commands into Claude's context before it responds. Fires once per topic per session. Available in BYOK mode; Hosted V2.

**Hook 2 (PreToolUse):** Before Claude invokes any Skill, Agent, or MCP — scores CC's chosen tool vs catalog alternatives 0–100. Blocks (exit 2) if a better-suited tool scores 10+ points higher. User types "proceed" to override. Works in all modes.

## Why it fits here

- Hooks section is the right home — both hooks are the core of the project
- Addresses a structural gap: the CC plugin ecosystem is deep, Claude doesn't use it at runtime
- Open source (MIT), 372 tests, Python 3.8+ and Bash
- Free hosted tier (8 detections/day) or BYOK (unlimited)

## Links

- GitHub: https://github.com/ToolDispatch/Dispatch
- Hosted tier: https://tooldispatch.visionairy.biz
- Catalog sources: skills.sh, Smithery.ai, glama.ai, registry.modelcontextprotocol.io
```

---

## 9. Dev.to Article Outline

**Title:**
```
I catalogued 10,978 Claude Code tools and built a dual-layer runtime. Here's what the data shows.
```

**Subtitle:**
```
Two hooks, 372 tests, and a map of exactly where Claude's tool selection underperforms
```

---

### Section 1: The Problem Nobody Talks About

- Claude Code has 10,978+ tools across 6 marketplaces. At runtime, Claude picks from a handful of defaults.
- It's not a gap in capability — it's a gap in awareness. Claude has no mechanism to know what's available, what's installed, or what performs best for the current task.
- The specific failure mode: you install a skill or MCP, Claude never reaches for it unprompted, you eventually forget you have it. The gap between your install list and Claude's actual tool usage grows over time.
- Why this gets worse over time: the MCP ecosystem alone crossed 5,000 registered servers. The surface area of "things Claude doesn't know about" expands daily.
- The deeper problem: most users don't even know what exists. Discovery is as broken as selection.
- The pivot moment: Claude was about to use a generic GitHub skill. I had a GitHub Actions-specific skill installed. It scored 35 points higher for what I was doing. Claude had no idea it was there.

**Narrative beat:** "The problem isn't that the tools don't exist. The problem is nothing connects them to Claude at runtime — at the discovery moment or the decision moment."

---

### Section 2: What Dispatch Does — Three Stages, Two Hooks

- Two hooks, two jobs, three stages total
- Hook 1 Stage 1 (task shift detection): the ~100ms background layer — runs on every message, exits fast when nothing changed
- Hook 1 Stage 2 (state write): maps confirmed shift to one of 16 MECE categories, writes state for Hook 2
- Hook 1 Stage 3 (proactive discovery): queries the catalog, groups results by type — Plugins, Skills, MCPs — injects them with install commands into Claude's context before it responds. Fires once per topic per session. This is the first thing users see.
- Show the Stage 3 proactive output format. This is the sizzle:
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
  ```
- Hook 2 (PreToolUse intercept): the safety net — before Claude commits to a tool choice
- Show the intercept output. Make it vivid.
- "proceed" as a design decision — one word, no friction, user stays in control
- The bypass token (120s TTL) — why it exists and how it prevents re-blocking the same choice
- Mode differences: BYOK gets full dual-layer (both hooks). Hosted free gets Hook 2 intercept; Hook 1 proactive in V2.

---

### Section 3: Building the Catalog

- 6 sources: skills.sh, glama.ai, Smithery.ai, registry.modelcontextprotocol.io, anthropics/claude-plugins-official, ananddtyagi/claude-code-marketplace
- What each source contributes and what it lacks (skills.sh has install counts, MCPs often don't)
- Scoring: installs 60% + GitHub stars 25% + forks 15%, log-normalized, staleness penalty
- MIN_INSTALLS ≥ 20 filter: why — noise reduction, quality signal, safety
- MCP safety note: MCPs run as processes with full tool access. No description + no GitHub repo = skip.
- What came back: 12,635 raw skills → 5,962 after filter. 4,821 MCPs. 195 plugins. 10,978 unique after dedup.
- The daily rebuild: why not incremental (simplicity, freshness), why it works at this scale (~5 minutes)

---

### Section 4: The CC Weakness Map

- What it shows: category-level comparison of average CC tool score vs. top marketplace alternative
- The categories with the biggest gaps: mobile development, database tooling, cloud infrastructure
- Why these gaps exist: Claude's defaults are general-purpose. The marketplace has purpose-built specialists.
- What this data means for the Anthropic relationship: behavioral data on CC tool selection gaps that Anthropic cannot collect internally. The pitch writes itself.
- The compounding signal: every Dispatch intercept adds a data point. More users = sharper map = better recommendations = more users.

---

### Section 5: Architecture Decisions and What I Learned

**The two-hook, three-stage split:**
- Why not one hook: UserPromptSubmit and PreToolUse have different latency budgets, different output contracts, different trigger conditions
- Hook 1 is context-building (discovery + state). Hook 2 is decision-interception. They're different jobs.
- Why Stage 3 (proactive output) matters as much as the intercept: most users never manually invoke a tool — they need to know what exists first

**The transcript format:**
- `role` nested inside `message` — `entry.get("role")` always returns None
- `isMeta=True` entries are loaded skill file content — up to 1,400 words of noise
- `[{` strings are serialized tool results — not user messages
- How to filter: three conditions, all required
- How I found it: a day of ghost signals and eventually diffing raw transcript vs. what Haiku was seeing

**Hook output routing:**
- stdout → Claude's context (this is how recommendations surface)
- stderr → suppressed by CC
- exit 2 → blocks the tool call (PreToolUse only)
- The 10-second hard limit: real constraint, real design budget

**GNU vs. BSD:**
- `head -n -1` destroys you on macOS. `sed '$d'` works everywhere.
- This one broke a colleague's install and took 45 minutes to trace.

**State between hooks:**
- Hook 1 writes `~/.claude/dispatch/state.json`. Hook 2 reads it.
- Bypass token: 120s TTL, single-use. Prevents re-blocking the same tool invocation.
- Broad exception catches throughout — a hook that throws is a hook that blocks Claude. Never acceptable.

---

### Section 6: The Collective Intelligence Layer

- BYOK and Hosted run the same algorithm. BYOK is good. Hosted gets better with users.
- What aggregate data adds: install rates per category, bypass rates (signals where Claude's choice was actually right), conversion patterns
- How this changes scores over time: tools that developers actually reach for after a recommendation rise. Tools that get bypassed fall.
- The founding tier story: 300 seats at $6/month locked for life. You're not buying a current tool — you're buying in when the catalog is young and the behavioral data is just starting to compound.

---

### Section 7: Results and Honest Assessment

- The CC Weakness Map numbers (mobile, database, cloud infra gaps)
- What works well: the proactive grouped discovery, the PreToolUse intercept, category-level routing, the 10-point gap threshold
- What's rough: cold start without many plugins installed, MCPs without GitHub repos get flat scores, catalog is only as good as what's crawlable, Hosted proactive layer is V2
- The one intercept that made the build worth it: the GitHub Actions case
- What I'd do differently: build the category taxonomy before the task type generator

---

### Section 8: Install and What to Read First

- One-command install, requirements, what to do after
- Where to look in the source first: `dispatch.sh` for the full three-stage Hook 1 logic, `dispatch-preuse.sh` for the intercept logic, `categories.json` for the taxonomy, `catalog_cron.py` for how the catalog is built
- Contributing: category mapper and scoring logic are the best entry points
- What the 372 tests cover and where the gaps are

---

**Tone notes:**
- Lead every section with a specific example or concrete number, not a general claim
- The data is the credibility — use the catalog numbers everywhere
- Acknowledge what doesn't work as readily as what does
- Technical specifics are the sizzle for a dev audience — precision sells
- Don't oversell the collective intelligence story — describe the mechanism, let developers understand the compounding math themselves

---

*End of marketing content package.*
