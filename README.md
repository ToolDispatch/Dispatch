# Dispatch

**Runtime skill router for Claude Code.**

Dispatch watches your conversation, detects when you shift to a new task, and recommends the best installed plugins and skills before Claude responds — including ones you haven't installed yet.

> ⚠️ **Status: Beta / Testing.** Unit tests pass but end-to-end live testing is in progress. Feedback via Issues is very welcome.

---

## What it does

Every time you send a message, Dispatch:

1. **Detects topic shifts** — Uses Claude Haiku (~$0.0001/message) to classify whether you've started a new type of task
2. **Evaluates your plugins** — Scans all installed Claude Code plugins and agent skills
3. **Searches the registry** — Queries [skills.sh](https://skills.sh) for relevant uninstalled options
4. **Shows recommendations** — Pauses before Claude responds so you can see what's available

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

---

## Requirements

- **[Claude Code](https://claude.ai/code)** — CLI tool from Anthropic (hooks support required, v1.x+)
- **Python 3.8+** — `python3 --version` to check
- **Node.js + npx** — [nodejs.org](https://nodejs.org) — used for skills registry search
- **Anthropic API key** — for Haiku classification (see below)
- **`anthropic` Python package** — install.sh handles this automatically

### Getting an Anthropic API key

1. Go to [console.anthropic.com](https://console.anthropic.com)
2. Sign in or create an account
3. Navigate to **API Keys** → **Create Key**
4. Copy the key (starts with `sk-ant-...`)

Dispatch uses Claude Haiku for classification. Cost is negligible — less than $0.01/day for active use.

---

## Install

```bash
git clone https://github.com/VisionAIrySE/Dispatch.git
cd Dispatch
chmod +x install.sh
./install.sh
```

Then add your API key:

```bash
export ANTHROPIC_API_KEY=sk-ant-...

# To persist across sessions, add to your shell profile:
echo 'export ANTHROPIC_API_KEY=sk-ant-...' >> ~/.bashrc   # bash
echo 'export ANTHROPIC_API_KEY=sk-ant-...' >> ~/.zshrc    # zsh
```

Start a **new** Claude Code session — Dispatch is active immediately.

> **Important:** Dispatch requires a new session to activate. It hooks into `UserPromptSubmit` which is read at session startup. Existing sessions won't see it.

---

## Getting the most out of Dispatch

Dispatch recommends plugins from wherever you have them installed. The more plugins you have, the better its recommendations. To get the full ecosystem:

**Install the official plugin marketplaces in Claude Code:**

```
/plugins add anthropics/claude-plugins-official
/plugins add ananddtyagi/claude-code-marketplace
```

**Install official stack-specific agent skills** (recommended):

```bash
# Firebase (web/mobile)
npx skills add firebase/agent-skills@firebase-firestore-basics -y
npx skills add firebase/agent-skills@firebase-auth-basics -y
npx skills add firebase/agent-skills@firebase-basics -y

# Supabase (postgres/backend)
npx skills add supabase/agent-skills@supabase-postgres-best-practices -y -g
```

**Browse 500+ community skills:**
- [skills.sh](https://skills.sh) — searchable registry (`npx skills find <query>`)
- [VoltAgent/awesome-agent-skills](https://github.com/VoltAgent/awesome-agent-skills) — curated list

Dispatch will surface any of these automatically when relevant to your task.

---

## How it works

**Stage 1 — Classification (every message, ~100ms)**
A Haiku call receives your last 3 messages + current working directory. Returns `{"shift": bool, "task_type": str, "confidence": float}`. Exits silently if no shift detected or confidence < 0.7.

**Smart skipping** — messages under 6 words and follow-up questions never trigger classification.

**Stage 2 — Evaluation (on confirmed shift only)**
Scans `~/.claude/plugins/marketplaces/` for installed plugins, queries `npx skills list` for agent skills, and searches the skills.sh registry for uninstalled options. Haiku ranks everything by relevance to your detected task type.

---

## Supported task types

`flutter` · `firebase` · `supabase` · `n8n` · `git` · `debugging` · `planning` · `testing` · `api` · `frontend` · `general`

---

## Cost

| Stage | When | Cost |
|-------|------|------|
| Stage 1 (shift detection) | Every message | ~$0.0001 |
| Stage 2 (plugin ranking) | On topic shift only | ~$0.001 |

Typical session (10 messages, 2-3 topic shifts): **< $0.005**

---

## Troubleshooting

**Dispatch isn't firing**
- Make sure you started a **new** Claude Code session after install
- Check `ANTHROPIC_API_KEY` is set: `echo $ANTHROPIC_API_KEY`
- Check the hook is registered: look for `UserPromptSubmit` in `~/.claude/settings.json`

**UI shows but no recommendations**
- You may not have many plugins installed — see [Getting the most out of Dispatch](#getting-the-most-out-of-dispatch)
- The task type may not have matched any installed plugins

**Hook fires but takes a long time**
- The hook has a 10 second total timeout — if it exceeds this Claude proceeds normally
- Check your internet connection (skills registry search requires network)

---

## Uninstall

```bash
rm -rf ~/.claude/skill-router
rm ~/.claude/hooks/skill-router.sh
```

Then remove the `UserPromptSubmit` entry from `~/.claude/settings.json`.

---

## Contributing

This is a beta release. If you try it, please open an Issue with:
- What task type you were on
- Whether recommendations were relevant
- Any errors from the hook

---

## Roadmap

- [ ] End-to-end live session testing
- [ ] Caching layer for plugin registry (reduce npx calls)
- [ ] `/dispatch status` command to check state
- [ ] V2: hosted classifier endpoint (no API key required)
- [ ] V2: skills.sh distribution
