<p align="center">
  <img src="Dispatch Icon.png" alt="Dispatch" width="120" />
</p>

# Dispatch

**The missing layer for Claude Code — automatically surfaces the right plugins and skills before every task.**

Claude Code has 500+ plugins and skills across multiple marketplaces. You're probably using 5 of them. Dispatch watches your conversation, detects when you shift to a new task, and recommends exactly what you need — before Claude responds.

```
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
 ⚡ Dispatch  →  Flutter task detected
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
 RECOMMENDED (installed):
   + flutter-mobile-app-dev
     Direct Flutter/Dart development support
   + firebase-firestore-basics
     Firestore queries and Security Rules

 SUGGESTED (not installed):
   ↓ firebase/agent-skills@firebase-app-hosting
     → npx skills add firebase/agent-skills@firebase-app-hosting

 [Enter] or wait 3s to proceed
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
```

> **Early release.** Works well in testing. If something breaks, open an Issue — this project moves fast.

---

## The problem

You're mid-session debugging a Flutter widget, then you say "actually let's write some tests." Claude proceeds — but your flutter-mobile-app-dev skill isn't loaded, and the test-driven-development skill you installed last month never comes up.

The Claude Code plugin ecosystem is powerful but invisible at runtime. You have to know what you have and manually invoke it. Most sessions, you forget.

Dispatch fixes this automatically.

---

## What it does

Every message you send, Dispatch:

1. **Detects topic shifts** — Uses Claude Haiku to classify whether you've started a new type of task
2. **Evaluates your plugins** — Scans every installed Claude Code plugin and agent skill
3. **Searches the registry** — Queries [skills.sh](https://skills.sh) for relevant uninstalled options
4. **Shows recommendations** — Pauses 3 seconds so you can see what's available, then proceeds automatically

It's invisible when you don't need it. It surfaces when you do.

---

## Install

```bash
git clone https://github.com/VisionAIrySE/Dispatch.git
cd Dispatch
chmod +x install.sh
./install.sh
```

Then add your Anthropic API key:

```bash
export ANTHROPIC_API_KEY=sk-ant-...

# Persist across sessions:
echo 'export ANTHROPIC_API_KEY=sk-ant-...' >> ~/.bashrc   # bash
echo 'export ANTHROPIC_API_KEY=sk-ant-...' >> ~/.zshrc    # zsh
```

Start a **new** Claude Code session. Dispatch is active immediately.

> Dispatch hooks into `UserPromptSubmit` which loads at session startup — existing sessions won't pick it up.

---

## Requirements

- **[Claude Code](https://claude.ai/code)** v1.x+ (hooks support required)
- **Python 3.8+**
- **Node.js + npx** — [nodejs.org](https://nodejs.org)
- **Anthropic API key** — for Haiku classification ([get one here](https://console.anthropic.com))

The `anthropic` Python package installs automatically via `install.sh`.

---

## Cost

Dispatch uses Claude Haiku — the fastest, cheapest Claude model — only for classification.

| Stage | Trigger | Cost |
|-------|---------|------|
| Shift detection | Every message | ~$0.0001 |
| Plugin ranking | On topic shift only | ~$0.001 |

**Typical session (10 messages, 2-3 topic shifts): less than $0.005.**

A full day of heavy Claude Code use costs less than $0.10.

---

## Getting the most out of Dispatch

Dispatch recommends from whatever you have installed. The more plugins you have, the better it gets.

**Add the official marketplaces in Claude Code:**

```
/plugins add anthropics/claude-plugins-official
/plugins add ananddtyagi/claude-code-marketplace
```

**Add official stack-specific skills:**

```bash
# Firebase
npx skills add firebase/agent-skills@firebase-firestore-basics -y
npx skills add firebase/agent-skills@firebase-auth-basics -y
npx skills add firebase/agent-skills@firebase-basics -y

# Supabase
npx skills add supabase/agent-skills@supabase-postgres-best-practices -y -g
```

**Browse the full registry:**
- [skills.sh](https://skills.sh) — 500+ skills (`npx skills find <query>`)
- [VoltAgent/awesome-agent-skills](https://github.com/VoltAgent/awesome-agent-skills) — curated list

---

## How it works

**Stage 1 — Classification (every message, ~100ms)**

Haiku receives your last 3 messages and current working directory. Returns `{"shift": bool, "task_type": str, "confidence": float}`. If no shift or confidence below 0.7, exits silently — you never see it.

**Smart skipping** — messages under 6 words and follow-up questions skip classification entirely.

**Stage 2 — Evaluation (on confirmed shift only)**

Scans `~/.claude/plugins/marketplaces/` for installed plugins, runs `npx skills list` for agent skills, searches the registry for uninstalled matches. Haiku ranks everything by relevance and presents the top results.

---

## Supported task types

`flutter` · `firebase` · `supabase` · `n8n` · `git` · `debugging` · `planning` · `testing` · `api` · `frontend` · `general`

More coming. Open an Issue to request one.

---

## Troubleshooting

**Dispatch isn't firing**
- Start a **new** Claude Code session after install
- Verify your key: `echo $ANTHROPIC_API_KEY`
- Check it's registered: look for `UserPromptSubmit` in `~/.claude/settings.json`

**UI shows but no recommendations**
- Install more plugins — see [Getting the most out of Dispatch](#getting-the-most-out-of-dispatch)
- The detected task type may not match any installed plugins yet

**Hook takes a long time**
- 10 second hard timeout — Claude proceeds normally if exceeded
- Check your internet connection (registry search requires network)

---

## Uninstall

```bash
rm -rf ~/.claude/skill-router
rm ~/.claude/hooks/skill-router.sh
```

Then remove the `UserPromptSubmit` entry from `~/.claude/settings.json`.

---

## Contributing

This is an early release. The most valuable thing you can do is use it and report back.

Open an Issue with:
- What task type triggered Dispatch
- Whether the recommendations were relevant
- Any errors you saw

Pull requests welcome. The classifier taxonomy and evaluator ranking logic are the best places to start.

---

## Roadmap

- [ ] Caching layer for plugin registry (reduce npx latency)
- [ ] `/dispatch status` command to inspect current state
- [ ] Expand task type taxonomy (React, Python, Docker, AWS...)
- [ ] V2: Hosted classifier — no API key required
- [ ] V2: skills.sh distribution

---

## Why this exists

Other tools in this space — like SummonAI — charge $100 to write custom skills tailored to your current stack. That's a great product if you know exactly what you need and want it built for you.

Dispatch is a different bet entirely.

Instead of building tools for a fixed stack, Dispatch finds the best tools for whatever you're doing right now — across any stack, any task, mid-session. Already have Flutter skills installed? It surfaces them when you switch to a Flutter task. Want to know if there's a better Supabase skill than the one you're using? It checks the registry before you even think to ask.

It doesn't care what your stack is. It cares what you're doing in the next five minutes.

The Claude Code plugin ecosystem is genuinely underutilized. Most developers install a handful of plugins and forget the rest exist. Dispatch is the runtime layer that was missing — a router that knows your context and connects you to the right tools automatically.

Built because I needed it. Shared because you probably do too.

This is a vibe coding project — I built Dispatch for myself over a weekend using Claude Code, then cleaned it up enough to share. If you're curious what else gets built this way, check out [Vib8](https://www.vib8ai.com) — an AI-powered prospecting engine built the same way.

---

## Support

If Dispatch saved you some time and made your Claude Code experience better, you can [buy me a coffee](https://github.com/sponsors/VisionAIrySE). That's it. No pressure, no tiers, no newsletter.

Star it if it helps. Share it if someone else would use it.
