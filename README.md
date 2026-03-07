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

**The missing layer for Claude Code — automatically surfaces the right plugins and skills before every task.**

Claude Code has 500+ plugins and skills across multiple marketplaces. You're probably using 5 of them. Dispatch watches your conversation, detects when you shift to a new task, and recommends exactly what you need — before Claude responds.

The hosted version gets smarter every day. As developers use Dispatch across thousands of sessions, aggregate patterns sharpen what gets recommended for each stack. New tools published to the skills registry are discovered automatically — no updates, no configuration, no manual curation. The longer Dispatch runs, the better it gets at knowing what you need before you do.

<!-- GIF demo goes here after Loom recording -->

```
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
 ◎ Dispatch — Flutter Fixing  [high confidence]
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
 RECOMMENDED (installed):
   + flutter-mobile-app-dev
     Direct Flutter/Dart development support

 SUGGESTED (not installed):
   ↓ systematic-debugging
     → npx skills add visionairy/systematic-debugging
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
```

---

## The problem

You're mid-session debugging a Flutter widget, then you say "actually let's write some tests." Claude proceeds — but your flutter-mobile-app-dev skill isn't loaded, and the test-driven-development skill you installed last month never comes up.

The Claude Code plugin ecosystem is powerful but invisible at runtime. You have to know what you have and manually invoke it. Most sessions, you forget.

Dispatch fixes this automatically.

---

## What it does

Every message you send, Dispatch:

1. **Detects action mode shifts** — Uses Claude Haiku to classify whether you've shifted domain or mode within a domain
2. **Evaluates your plugins** — Scans every installed Claude Code plugin and agent skill
3. **Searches the registry** — Queries [skills.sh](https://skills.sh) for relevant uninstalled options
4. **Shows recommendations** — Injects tool recommendations directly into Claude's context. Claude surfaces them inline, explains why each is relevant to your current work, and waits for your response before proceeding

It's invisible when you don't need it. It surfaces when you do.

---

## Install

```bash
git clone https://github.com/VisionAIrySE/Dispatch.git
cd Dispatch
chmod +x install.sh
./install.sh
```

`install.sh` will prompt you to connect via GitHub — sign in, copy the token, paste it back. That's it. No API key needed.

Start a **new** Claude Code session. Dispatch is active immediately.

> Dispatch hooks into `UserPromptSubmit` which loads at session startup — existing sessions won't pick it up.

### BYOK mode (bring your own API key)

If you prefer to run entirely self-hosted with your own Anthropic key:

```bash
export ANTHROPIC_API_KEY=sk-ant-...

# Persist across sessions:
echo 'export ANTHROPIC_API_KEY=sk-ant-...' >> ~/.bashrc   # bash
echo 'export ANTHROPIC_API_KEY=sk-ant-...' >> ~/.zshrc    # zsh
```

Dispatch will use your key directly — no token, no server, no data leaving your machine.

---

## Requirements

- **[Claude Code](https://claude.ai/code)** v1.x+ (hooks support required)
- **Python 3.8+**
- **Node.js + npx** — [nodejs.org](https://nodejs.org)
- **Either:** a free Dispatch account (recommended) **or** an Anthropic API key

The `anthropic` Python package installs automatically via `install.sh`.

---

## Cost

**Hosted (recommended):** Free for 8 detections/day. Upgrade for unlimited at **$6/month** → [dispatch.visionairy.biz/pro](https://dispatch.visionairy.biz/pro)

The hosted version is more than convenience — it's collective intelligence. Every session across every user improves what gets recommended for your stack. BYOK runs the same algorithm in isolation; hosted runs it with the benefit of aggregate signal from the whole community.

New tools added to the skills registry are picked up automatically. You don't update Dispatch — Dispatch updates itself.

**Pro subscribers get more than unlimited detections.** As Dispatch grows, Pro is the tier where new capabilities ship first:
- **Curated registry** — hand-picked, production-tested tool recommendations per stack, vetted by the Dispatch team (live now)
- **Usage analytics dashboard** — see what task types you shift to most, which tools get recommended, session patterns over time
- **Weekly digest** — new tools published to your stacks, surfaced before you go looking
- Every new feature built on top of the usage data gets better the more people use it — and Pro users are the ones feeding that signal

**BYOK (self-hosted):** Runs the raw algorithm with your own Anthropic key. No data sharing, no curated picks, no network effect. Good for privacy-first setups.

| Stage | Trigger | Cost |
|-------|---------|------|
| Shift detection | Every message | ~$0.0001 |
| Plugin ranking | On topic shift only | ~$0.001 |

**Typical session (10 messages, 2-3 topic shifts): less than $0.005.**

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

Dispatch fires when you shift to a new **action mode** or a new **domain** — whichever comes first.

**Action modes** (7 MECE categories):

| Mode | You're... |
|---|---|
| `discovering` | Researching, exploring, learning something new |
| `designing` | Planning, architecting, deciding on approach |
| `building` | Writing new code, implementing features |
| `fixing` | Debugging, diagnosing errors, tracing failures |
| `validating` | Testing, reviewing, verifying correctness |
| `shipping` | Deploying, releasing, going live |
| `maintaining` | Refactoring, cleaning up, paying down tech debt |

Moving from `flutter-building` to `flutter-fixing` triggers a shift. So does moving from `flutter` to `supabase`. Both get you the right tools at the right time.

Detection uses Claude Haiku with semantic understanding — not keywords. *"This blows up with a null"* → `fixing`. *"Let me sanity check this"* → `validating`.

**Stage 1 — Classification (every message, ~100ms)**

Haiku receives your last 3 messages and current working directory. Returns `{"shift": bool, "domain": str, "mode": str, "task_type": str, "confidence": float}`. If no shift or confidence below 0.7, exits silently — you never see it.

**Smart skipping** — messages of 2 words or fewer skip classification entirely.

**Stage 2 — Evaluation (on confirmed shift only)**

Scans `~/.claude/plugins/marketplaces/` for installed plugins, runs `npx skills list` for agent skills, searches the registry for uninstalled matches. Haiku ranks everything by relevance and presents the top results.

---

## Supported task types

Any. Dispatch doesn't use a fixed list — it generates the most specific label it can from your conversation and uses that to search the live skills registry. If a skill exists for what you're doing, Dispatch will find it.

Examples of what it detects: `flutter-building` · `flutter-fixing` · `react-building` · `nextjs-shipping` · `supabase-fixing` · `firebase-building` · `python-building` · `docker-shipping` · `aws-devops` · `stripe-building` · `github-actions-shipping` · and anything else in the registry.

As new skills get published to [skills.sh](https://skills.sh), Dispatch picks them up automatically — no updates required.

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

- [x] Caching layer for plugin registry (reduce npx latency)
- [x] Hosted endpoint — no API key required (live at dispatch.visionairy.biz)
- [x] Open-ended task type taxonomy — Haiku generates specific labels, not a fixed list
- [ ] `/dispatch status` command to inspect current state
- [ ] skills.sh distribution

---

## Why this exists

Other tools in this space — like SummonAI — charge $100 to write custom skills tailored to your current stack. That's a great product if you know exactly what you need and want it built for you.

Dispatch is a different bet entirely.

Instead of building tools for a fixed stack, Dispatch finds the best tools for whatever you're doing right now — across any stack, any task, mid-session. Already have Flutter skills installed? It surfaces them when you switch to a Flutter task. Want to know if there's a better Supabase skill than the one you're using? It checks the registry before you even think to ask.

It doesn't care what your stack is. It cares what you're doing in the next five minutes.

The Claude Code plugin ecosystem is genuinely underutilized. Most developers install a handful of plugins and forget the rest exist. Dispatch is the runtime layer that was missing — a router that knows your context and connects you to the right tools automatically.

The code is open source. Run it yourself if you want — it works. But the hosted version knows something your local copy doesn't: what tools thousands of other developers reach for when they're doing exactly what you're doing right now. That gap widens every day.

Built because I needed it. Shared because you probably do too.

This is a vibe coding project — I built Dispatch for myself over a weekend using Claude Code, then cleaned it up enough to share. If you're getting serious about AI tooling, check out [Vib8](https://www.vib8ai.com) — a prompt engineering and optimization platform for 100+ AI tools that pairs well with what Dispatch does inside Claude Code.

---

## Security

Dispatch was designed to be auditable and minimal:

- **No `~/.claude/CLAUDE.md` modification** — install.sh does not touch your global Claude instructions. Recommendations surface via Claude Code's native hook context injection.
- **No credential harvesting** — Dispatch reads only `ANTHROPIC_API_KEY` from your environment. It does not read other tool config files (e.g., `.mcp.json`).
- **No shell injection** — task type labels are always passed as `sys.argv`, never interpolated into shell strings.
- **Open source** — every line of `dispatch.sh`, `classifier.py`, and `evaluator.py` is in this repo. Verify what runs on your machine before installing.
- **10-second hard timeout** — Claude Code enforces a 10s limit on the hook. Dispatch cannot block or hang your session.

---

## Privacy

**Self-hosted (BYOK):** Haiku API calls go directly from your machine to Anthropic. No data passes through our servers, ever.

**Hosted:** Your current message and working directory are sent to dispatch.visionairy.biz for classification. This data is passed to Claude Haiku and immediately discarded — we do not store conversation content. We store only your GitHub username, email, usage count, and detected task types (e.g., `flutter-fixing`). We will never sell individual data. Aggregate patterns may be used to improve recommendations in anonymized form.

You'll always have the self-hosted option with zero data leaving your machine.

---

## Support

Free plan gives you 8 detections/day — enough to evaluate whether Dispatch fits your workflow across multiple sessions.

If it does, [upgrade to Pro for $6/month](https://dispatch.visionairy.biz/pro). Unlimited detections, and you're contributing to the data pool that makes recommendations sharper for everyone. The more Pro users, the better the signal.

You can also fork it, run it with your own API key, and never pay a cent. The code is open — the value is in the service. If you'd rather just say thanks, [buy me a coffee](https://github.com/sponsors/VisionAIrySE).

Star it if it helps. Share it if someone else would use it.
