# ToolDispatch — Complete Platform Value + 14-Day Launch Plan
### Target: 150 paid users by Day 14

---

## PART 1: WHAT THE PLATFORM ACTUALLY DOES

Before one word of marketing gets written, you need to know every function cold.
Because the product has more depth than almost anyone selling it gives it credit for.

---

### THE TWO PROBLEMS IT SOLVES

**Problem 1: The Discovery Gap**
The CC ecosystem has 51,000+ agent skills on claude-plugins.dev alone, 20,000+ MCP servers on glama.ai, and more on Smithery — across 16 domains — and it grows every week. Developers discover maybe 10% of it by browsing, asking around, or stumbling onto something. When you switch from React to n8n, CC reaches for the tool it used yesterday, not the best tool for today's task. Nobody told it anything changed. Nobody told YOU what exists.

**Problem 2: The Code Contract Gap**
CC generates architecturally sound code that fails at runtime. Broken imports, wrong function signatures, missing env vars, stubs left in production. Pyright doesn't catch these because they're not type errors — they're the specific class of failure AI code introduces: hallucinated APIs, stale signatures from training data, assumed env vars. You run the code. It breaks. You ask CC to fix it. It fixes a symptom. Something else breaks. Repeat for 3 hours.

---

### EVERY FUNCTION, FOR EVERYONE

**Dispatch (3 hooks, always running)**

| What it does | When it fires | What you see |
|---|---|---|
| Task shift detection | Every message, ~100ms | Silent — classification only |
| First-run welcome | First message after install | "Dispatch is active. When you start a new type of task..." |
| Proactive tool discovery | On confirmed task shift (confidence ≥ 0.7), once per category | Grouped list: Plugins / Skills / MCPs for your current task |
| Tool interception | Before every Skill, Agent, MCP call | Scored comparison — CC's score vs. marketplace TOP PICK |
| Block + alternatives | When gap ≥ 10 points | Full scorecard, TOP PICK, install command, 3 options |
| Bypass token | After user says "proceed" | 120s grace — next call goes through, then re-evaluates |
| Conversion tracking | After each intercept | Was the suggested tool installed? Signal for ranker |
| Session digest | Session end | "N audited · N blocked · N recommendations shown" |

**XF Audit (PreToolUse on every Edit + Write)**

| Stage | What it checks | Speed | Tier |
|---|---|---|---|
| Stage 1 (always) | Syntax errors | 200ms | Free |
| Stage 1 (always) | Broken imports (from X import Y — does X exist?) | 200ms | Free |
| Stage 1 (always) | Arity mismatches (function called with wrong number of args) | 200ms | Free |
| Stage 1 (always) | Env vars used in code but not defined anywhere | 200ms | Free |
| Stage 1 (always) | Stub functions in production code (pass / NotImplementedError) | 200ms | Free |
| Stage 2 | Caller chain BFS — traces every function that calls the broken one | Seconds | Pro |
| Stage 3 | File-and-line repair plan, diff generation, provenance log | Seconds | Pro |
| Stage 4 | Graduated consent — "show diff" → after 2 repairs, "apply all" unlocks | Interactive | Pro |
| Refactor Mode | /xfa-refactor start — accumulate without blocking, consolidated list at end | Session | Pro |
| Session digest | "✓ all contracts intact" or "N violations · N repaired" | End of session | All |

**The 16 Domains Dispatch Covers**

Source Control & GitHub · Database & SQL · Cloud Infrastructure · Frontend & UI · Mobile · AI & ML · Testing & QA · DevOps & CI/CD · Auth & Identity · APIs & Integrations · Data Engineering · Monitoring · Documentation · Search & Embeddings · Backend Frameworks · Payments & Billing

Every task shift gets matched to one of these categories. Category determines which marketplace sources get queried and which tools get scored.

---

### VALUE FOR EXPERIENCED DEVELOPERS

These users have 15–25 tools installed. They know plugins exist. Their problems are different.

**What ToolDispatch fixes for them:**

1. **CC uses the wrong tool from a full stack.** You've got 20 tools. You pivot from React to n8n. CC reaches for your React skill because that's what it's been using. Dispatch intercepts: "n8n-workflow-builder [94/100] scores 31 points higher than what you were about to use." That's not a discovery problem — that's a routing problem. Dispatch solves it.

2. **The ecosystem moves faster than awareness.** They set up their stack 3 months ago. 15 new tools shipped since then that would change how they work. Dispatch tells them about new tools exactly when they become relevant — not when they stumble onto a tweet about it.

3. **Automated pre-commit code review.** XF Audit Stages 2–4 do what a senior dev does in code review: trace the caller chain, map consequences, generate a repair plan. Automatically. On every edit. For free up to Stage 1, full chain on Pro.

4. **Refactoring without whiplash.** Large refactors across a codebase hit violations constantly. Refactor Mode accumulates them all without blocking — lets you finish the work, then presents the consolidated list. Clean session, complete picture.

5. **Session accountability.** The digest at session end — "8 audited · 2 blocked · 3 recommendations shown" — is a record of what Dispatch did. They can see if it's earning its keep.

6. **The "trust but verify" contract.** The bypass token, the proceed option, the graduated consent on Stage 4 — none of this overrides them. They stay in control. Dispatch shows the case. They decide.

---

### VALUE FOR VIBE CODERS

These users are non-technical or early-technical. They're using CC to build things they couldn't build before. Their problems are acute.

**What ToolDispatch fixes for them:**

1. **They don't know plugins exist.** Not MCPs, not skills, not the official plugin registry. Zero awareness of the ecosystem. When they start a new task — "help me set up Stripe" — Dispatch Stage 3 fires: "For this payments task: stripe-webhook-mcp, n8n-stripe-integration, payments-skill." First time many of them have ever seen these exist.

2. **CC gives them the default, not the best.** They installed nothing. They don't know what to install. Dispatch intercepts, shows the scorecard, shows the install command. One line to get the right tool. No research required.

3. **Code stops working and they don't know why.** CC generated working-looking code. They run it. ImportError. They ask CC to fix it. CC fixes the import but now there's a NameError. They ask CC again. Two hours later they've burned tokens and the code still doesn't work. XF Audit Stage 1 catches the ImportError at the point of edit, before they ever run it. 200ms. Shows: what's broken, where, what to do. It stops the whack-a-mole.

4. **They can't do a code review.** Senior devs review their own code before running it. Vibe coders can't. XF Audit is their automated code reviewer — running silently on every edit, loud only when something's wrong.

5. **Env vars they forgot to set.** CC assumed the env var existed. Nobody told it the .env file was missing three keys. Runtime fails. XF Audit Stage 1 catches `os.getenv("STRIPE_SECRET")` at edit time and flags it.

6. **They have no "I know this is broken" sense.** Stub functions (raise NotImplementedError, pass in functions that should do something) shipped to production because nobody knew to look. Stage 1 flags every one.

---

## PART 2: THE PROGRESSIVE VALUE STORY

This is the conversion architecture. Understand it before writing a single post.

```
FREE — you feel the value immediately
  ├─ XF Audit Stage 1: catches the bug at edit time (wow, it caught something)
  ├─ Dispatch Stage 3: "oh, this tool exists for my task" (discovery moment)
  └─ Dispatch intercepts: CC blocked — here's the scored comparison (8/day)

                    ↓ natural limit hit

  You've had 8 intercepts. You're mid-session. You want to keep going.
  The upgrade prompt appears at the exact moment you want the value.
  This is NOT friction. This is the proof that you needed it.

PRO — deeper value on top of what's already working
  ├─ Unlimited intercepts: no cap, always on
  ├─ Better ranking (Nemotron Super): higher quality recommendations
  ├─ Pre-ranked catalog: < 200ms (vs. 2–4s live search on free)
  ├─ Network intelligence: recommendations trained on what actually gets installed
  ├─ XF Audit Stages 2–4: caller chain → repair plan → graduated consent
  └─ Dashboard: block rate, top tools, install conversions, session history

                    ↓ network effects kick in

  Every user makes it better for every other user.
  Every intercept teaches the ranker what works for what task.
  Every conversion signals which recommendations were right.
  Founding users ($6/month, locked forever) get a product that improves
  without paying more. The value compounds. The price doesn't.
```

---

## PART 3: THE MESSAGES

Three distinct angles. Each one is complete. Don't mix them in a single post.

---

### ANGLE 1 — The Discovery Story (Dispatch lead)

**For: r/ClaudeAI, experienced devs, X/Twitter**

> Title: "The Claude Code ecosystem has 70,000+ tools across skills, MCPs, and plugins. CC only knows about the ones it's seen before."

> Body:
> When you're deep in a Flutter session and pivot to setting up Stripe, Claude Code doesn't know you switched. It reaches for the Flutter tools it's been using. Not because it's dumb — because nothing told it the task changed.
>
> I built a hook that does.
>
> Every time you message CC, it classifies your task in ~100ms. When it detects a shift — React to n8n, debugging to deploying, backend to mobile — it surfaces the best tools for your new context before Claude reaches for anything. Grouped by type: Plugins / Skills / MCPs. Ranked by fit for your specific task, not by name recognition.
>
> Before every Skill or MCP call, it intercepts. Scores CC's choice against the marketplace. If something scores 10+ points higher for what you're actually building, it blocks and shows you the comparison:
>
> [GIF: Dispatch intercept notification — scored comparison with TOP PICK]
>
> You decide: proceed with CC's choice, install the better tool, or ignore Dispatch for this task type.
>
> It's called Dispatch. Free: 8 intercepts/day. Founding Pro: $6/month, first 300 users.
>
> Install: git clone https://github.com/ToolDispatch/Dispatch && bash install.sh

---

### ANGLE 2 — The Safety Story (XF Audit lead)

**For: r/Python, vibe coder communities, dev.to**

> Title: "I spent 4 hours debugging code that looked right. Then I built something to stop it."

> Body:
> The pattern: CC generates code. You run it. ImportError. You ask CC to fix it. It fixes that. NameError. Another fix. Something else breaks. You're not fixing your app — you're playing whack-a-mole with AI-generated bugs while burning tokens on symptom chasing.
>
> The problem isn't the code, it's when you find out it's broken. At runtime, after it shipped, CC already moved on.
>
> XF Audit catches it at the point of edit.
>
> Every time Claude Code edits a file, XF Audit runs a 200ms AST scan: are the imports real? Do the function calls match the signatures they're calling? Are the env vars that the code references actually defined somewhere? Are there stub functions (NotImplementedError, pass) sitting in production code?
>
> [GIF: XF Audit violation caught at edit — shows broken import, repair plan]
>
> If it finds something, it shows exactly what's broken, where, and a repair plan before the edit lands.
>
> On Pro, it traces the full caller chain. Everything that breaks downstream if this function is wrong. Concrete file-and-line fixes. After two verified repairs, auto-apply unlocks.
>
> It's called XF Audit, part of ToolDispatch. Stage 1 is always free.
>
> Install: git clone https://github.com/ToolDispatch/Dispatch && bash install.sh

---

### ANGLE 3 — The Insurance Policy Story (both modules, combined)

**For: Product Hunt, HN, investor/press pitches**

> ToolDispatch is an insurance policy for Claude Code sessions.
>
> Two modules. Always running. Silent on clean pass. Loud when something goes wrong.
>
> Dispatch catches the tool problem: CC defaults to whatever worked last time. When your task changes — and it always changes — Dispatch detects the shift, surfaces the right tools before CC reaches for anything, and intercepts tool calls that would use a worse option when the marketplace has something better. Real-time scoring. Concrete alternatives. You decide.
>
> XF Audit catches the code problem: CC generates code that compiles but breaks at runtime. Broken imports, stale function signatures, missing env vars, stubs in production. Standard type checkers were built for human code — they miss the specific failure modes AI introduces. XF Audit does AST scanning at edit time: 200ms, every file, catches the break before you run anything.
>
> Together: you always have the right tool, and your code actually works.
>
> It gets better with adoption. Every intercept trains the ranker on what tools developers actually switch to. Every conversion signals what recommendations were right. The product improves without the price going up.
>
> Free to start. Pro at $6/month founding tier (first 300, locked for life). 2-minute install.

---

### HOOK LINES (copy exactly, use as titles or opening tweets)

**Dispatch hooks:**
- "Claude Code doesn't know you switched tasks. I built something that does."
- "There are 70,000+ tools in the CC ecosystem. You're probably using 20. Here's what you're missing for your current task."
- "I watched CC reach for the wrong tool 8 times in one session. So I built an interceptor."
- "The CC plugin ecosystem added 40 tools this quarter. Dispatch told me which 3 mattered for what I'm building."

**XF Audit hooks:**
- "I stopped debugging Claude Code's output. Now XF Audit does it at edit time."
- "Pyright passes. Runtime fails. XF Audit catches the class of bug between them."
- "Every token I burned on whack-a-mole debugging was a bug XF Audit would have caught in 200ms."
- "CC generates code. XF Audit makes it actually work."

**Combined hooks:**
- "Two hooks. Every CC session. Right tool, working code."
- "Your Claude Code insurance policy."
- "CC builds the structure. ToolDispatch makes it connect."

---

### THE NETWORK EFFECTS LINE (use this exact language in every post)

> "The product gets better with every user. Every intercept teaches the ranker which tools developers actually switch to for which tasks. Founding Dispatchers get the best recommendations at the lowest price, and the price is locked. The value isn't."

Use in: Pro tier upsell, community replies, pitch decks, DM follow-ups.

---

## PART 4: THE 14-DAY LAUNCH PLAN

Target: 150 paid users by Day 14.
Math: ~1,200 installs needed at 12.5% conversion. ~18,000 qualified impressions at 7% install rate.
Channels needed: Product Hunt + r/ClaudeAI + HN + X + Discord + direct outreach.

---

### PRE-LAUNCH: DAYS 1–2

**Goal: Build every asset before you post anything.**

---

**DAY 1 — Demo + Foundations (4 hours)**

*Morning (2 hours): The demo*

This is the single most important thing you do all week. Every channel below converts at 3–5x lower rate without a visual demo. Do not post anything before this exists.

Build the demo project:
```bash
mkdir /tmp/td-demo && cd /tmp/td-demo
git init
# Create: app.py that imports a package not in requirements.txt
# Create: stripe_handler.py that calls a function with wrong arg count
# Create: config.py that uses os.getenv("STRIPE_SECRET") (not in .env)
# Create: utils.py with stub functions (pass bodies)
```

Record with asciinema:
```bash
pip install asciinema agg
asciinema rec dispatch-demo.cast --title "ToolDispatch in action"
```

**Demo script — follow exactly:**
1. `claude` — start CC in the demo project
2. Say: "Add a payment processing function using Stripe"
3. CC reaches for a generic tool → **PAUSE — let Dispatch intercept fire** → show scorecard
4. Say "proceed" or install the better tool — show the interaction
5. Let CC write code with broken imports → **XF Audit Stage 1 fires** → show violation + repair plan
6. Say: "Now deploy this to AWS Lambda"
7. CC tries a generic deployment skill → **second Dispatch intercept** → show scored comparison
8. End session → **stop digest fires** → "3 audited · 2 blocked · 1 recommendation shown"

Convert to GIF:
```bash
agg dispatch-demo.cast dispatch-demo.gif
# Trim to 30–45 seconds max
```

*Afternoon (2 hours): Passive channel submissions*

These don't need the demo. File and forget — they compound over time.

**awesome-claude-skills PR (30 min):**
```
Repo: github.com/travisvn/awesome-claude-skills
Fork → Add under "Developer Productivity / Utilities":

- [ToolDispatch](https://github.com/ToolDispatch/Dispatch) — Runtime tool router
  and AI code contract checker for Claude Code. Intercepts bad tool choices,
  surfaces marketplace alternatives with scoring, and catches broken imports/
  signatures/env vars at edit time. Free + Pro. [Plugins · Skills · MCPs]

PR title: "Add ToolDispatch — runtime tool router + AI code contract checker"
```

**claudemarketplaces.com (15 min):**
Submit at claudemarketplaces.com with the combined "insurance policy" description (Angle 3 above).

**CC Marketplace (30 min):**
Submit at platform.claude.com/plugins/submit. plugin.json is ready. Use Angle 3 as description. This is the highest-leverage passive placement — file it even though the timeline is uncertain.

**Verify npx install works (30 min):**
```bash
# In a clean environment:
npx skills add ToolDispatch/Dispatch
# If this doesn't work cleanly, fix it today. It's the in-ecosystem install UX.
```

---

**DAY 2 — Copy + Analytics (2 hours)**

*Write all 4 posts from scratch using the exact copy in Part 3 above. Personalize with your real experience.*

For the r/ClaudeAI post (Angle 1 or 2):
- Add your specific personal story: when did YOU play whack-a-mole? Name the task, the hours, the frustration.
- Insert the GIF after the first problem description.
- Keep it under 400 words. Tight converts better than comprehensive.

For the HN Show HN (Angle 3):
- Strip it to 4 sentences. HN readers click through, they don't read walls.
- The title is everything: "Show HN: ToolDispatch — runtime tool router and AI code contract checker for Claude Code"

For the X thread (Day 4 — write now, post then):
- Tweet 1: Dispatch intercept hook line + GIF
- Tweet 2: What the scorecard tells you
- Tweet 3: XF Audit — the other problem
- Tweet 4: "Together: right tool, working code. 2-min install."

*Set up analytics:*
- Verify signup notifications hitting #dispatch-log in Slack ✓ (already set up)
- Add UTM params to install links in each post (e.g., `?ref=reddit`, `?ref=hn`, `?ref=x`)
  so you know which channel drives installs
- Dashboard at tooldispatch.visionairy.biz/dashboard to track conversions

---

### WAVE 1: DAYS 3–5

**Goal: First 500 installs, first 25 paid users.**

---

**DAY 3 — r/ClaudeAI + Anthropic Discord**

Post Angle 1 (Discovery Story) on r/ClaudeAI. Time: 9–11am Eastern (peak traffic).

After posting, immediately drop the same condensed version in the Anthropic developer Discord. One paragraph + GIF + install link. "Built this for CC — happy to answer how it works."

**Reply strategy (all day):**
Every single comment gets a reply within 2 hours. For every "how does it work" question, give a specific, technical answer — don't link to README, explain it. This signals you're an active founder, not a drive-by poster.

Magic reply for "I already have good tools":
> "That's actually the second problem — it's not about what you have installed, it's whether CC reaches for the right one when you switch tasks mid-session. Dispatch routes by current task context, not last-used. Worth trying for a session — the session digest will tell you if it caught anything."

Magic reply for "does this work for X language/framework":
> "Dispatch works for [list all 16 categories], so yes for X. XF Audit Stage 1 covers Python files — if you're using something else, Stage 1 syntax scan still fires, import/arity checks are Python-specific."

---

**DAY 4 — X/Twitter Thread**

Post the 4-tweet thread. Time: 10am Pacific.

If you have access to any CC-adjacent accounts with 5K+ followers (people who tweet about CC, AI coding, vibe coding), DM them the thread before posting and ask if they'd retweet or quote-tweet when it goes live. One amplification from a respected voice = 10x the organic reach.

Also post to:
- dev.to: Use Angle 2 as a full technical post. Title: "Why I built a code contract checker for Claude Code (and why Pyright couldn't do it)"
- Include XF Audit architecture, the specific failure modes, why AST scanning is the right approach.
- dev.to articles live forever and rank on Google. This one will.

---

**DAY 5 — HN Show HN**

Submit at Hacker News: "Show HN: ToolDispatch – runtime tool router and AI code contract checker for Claude Code"

HN rules:
- Post at 9am Eastern on a weekday (not Friday)
- Don't ask for upvotes (ban risk)
- Reply to every comment technically, not defensively
- If someone challenges the approach, engage with the substance

HN-specific response for "why not just use better prompts":
> "Prompt quality doesn't solve the discovery problem — CC can't recommend a tool it wasn't trained on, and the ecosystem adds tools weekly. And no prompt catches a broken import at edit time. These are infrastructure problems, not prompting problems."

---

### WAVE 2: DAYS 6–10

**Goal: 1,000 installs, 75 paid users.**

---

**DAY 6 (MONDAY) — Product Hunt Launch**

This is your biggest single-day reach event. Do it right.

**Pre-launch checklist:**
- [ ] Product description uses Angle 3 (insurance policy story)
- [ ] Gallery: GIF as first asset, screenshots of both modules
- [ ] Maker comment: post immediately after launch with your personal story (100–150 words)
- [ ] Hunter: ideally someone with 1K+ followers, but you can self-hunt
- [ ] Price clearly visible: Free tier + $6/month Founding Pro
- [ ] Install link tracked with `?ref=producthunt`

**Maker comment template:**
```
Hey PH — I built ToolDispatch after spending an embarrassing amount of time
playing whack-a-mole with Claude Code output. Every CC session has two failure
modes: Claude reaching for the wrong tool when you switch tasks, and the code
it generates looking right but failing at runtime because of broken contracts.

Dispatch handles the first (intercepts tool calls, scores against marketplace
alternatives). XF Audit handles the second (AST scan at edit time — catches
broken imports, wrong arg counts, missing env vars in 200ms).

Founding Pro is $6/month — locked for life for the first 300 users. Happy to
answer anything.
```

Post in every community on PH launch day pointing back to the listing:
- r/ClaudeAI: "Just launched on Product Hunt if anyone wants to support"
- Anthropic Discord: same
- X: "Launched on PH today — [link]"

---

**DAY 7 — Direct Outreach**

Identify everyone who commented positively on any post from Days 3–5:
- Asked a technical question
- Said they installed it
- Replied more than once

DM every one of them (Reddit, X, Discord). Exact copy:

```
Hey [name] — saw you [commented / installed / engaged] with ToolDispatch this week.

Quick question: did you hit anything unexpected with the install or a session where
Dispatch caught something? Trying to understand what people are actually using it for.

Also — Founding Pro is $6/month for the first 300 users, locks in for life. Includes
unlimited Dispatch intercepts, XF Audit Stages 2–4 (full caller chain + repair plan),
and the dashboard. If you're using CC heavily, it'll catch something in the first week.

If it doesn't, I'll refund you. No friction.

[pro link]
```

Goal: 10 conversions from direct outreach alone. This doesn't scale. It doesn't need to yet.

---

**DAY 8 — Dev.to + Community Round 2**

Publish the technical article (written on Day 4). This should be 800–1,200 words, technically specific.

Structure:
1. The problem: static analysis fails on AI-generated code (name the failure modes)
2. Why: Pyright was designed for human-written code, not hallucinated APIs
3. What XF Audit does differently: AST scan + caller chain + at edit time
4. Show the 5 checks: syntax, imports, arity, env vars, stubs
5. The Dispatch side: task-shift routing problem
6. Install + close

Share in: r/Python, r/programming, dev.to weekly newsletter submission.

---

**DAY 9 — Convert Free Users Hitting the Limit**

By now, power users on the free tier have hit the 8 intercepts/day limit.

When the limit fires, the notification says: "You've used your 8 free detections today. Upgrade for unlimited + Sonnet ranking — $10/month → [link]"

Check analytics for who's hitting this limit. If you have email addresses from signups, send:

```
Subject: You hit your Dispatch limit today

You had 8 intercept events today — Dispatch caught something useful enough that
you used the whole free tier.

Founding Pro is $6/month for the first 300 users. Locks in forever.
What you get: unlimited intercepts, better ranking quality, XF Audit Stages 2–4
(full repair plans), dashboard.

[Upgrade link]

If you want to know exactly what Dispatch blocked today before upgrading,
reply here and I'll pull it from your session data.
```

That last line — "I'll pull it from your session data" — personalizes it and creates a reason to reply. Replies become conversations. Conversations convert.

---

**DAYS 10–14 — Amplification + Conversion**

- Reply to every new comment across all posts (stay visible for a full 2 weeks)
- Second X thread: lead with a real user story — "here's what Dispatch caught in [someone's] session" (get permission first)
- Send dev.to article to the Claude Code official newsletter / Anthropic devrel if you have a contact
- GitHub: respond to every issue and PR from new users
- Week 2 Product Hunt: look at the "upcoming" section for adjacent tools, engage with their communities

---

## PART 5: AUTOMATIONS (SET UP ON DAY 1, RUN FOREVER)

**Already running:**
- Signup → #dispatch-log Slack notification ✓

**Set up this week:**

**n8n: Reddit mention tracker**
Monitor r/ClaudeAI and r/Python for "ToolDispatch". Every mention → Slack notification to #dispatch-queue. Check it twice daily, reply to every one.

**n8n: GitHub star → welcome response**
When someone stars ToolDispatch/Dispatch: send a GitHub API comment:
```
Thanks for the star! If you try it out, I'd love to know what you're using
CC for — helps me improve the recommendations. Reply anytime.
```
Low effort. Starts conversations. Conversations convert.

**n8n: Free tier limit → upgrade reminder**
When the API sees a user has hit 8 intercepts/day 3 days in a row: trigger an upgrade email. They've demonstrated consistent value. The timing is right.

**OpenClaw: outreach queue**
Point OpenClaw at r/ClaudeAI. Flag comments from developers complaining about:
- "CC gave me the wrong tool"
- "debugging for hours"
- "code doesn't run"
- "which plugin should I use"

Queue personalized replies for Russ to approve in #dispatch-queue before sending.

---

## PART 6: GSTACK TOOLS FOR THIS LAUNCH

| Tool | When | Why |
|---|---|---|
| `/browse` | Day 2 | QA test tooldispatch.visionairy.biz install flow before launch |
| `/ship` | Day 2 | Push all committed changes, open PR |
| `/document-release` | Day 2 | Catch any stale README after shipping |
| `/canary` | Day 3 (after posting) | Watch for server errors when install traffic spikes |
| `/qa-only` | Day 1 | Bug report for anything found before launch |
| `/cso` | Before Day 6 (PH) | OWASP audit on Stripe webhook and session data handling |
| `/retro` | Day 7, Day 14 | What's working, what install rate, what to fix next week |

---

## PART 7: SUCCESS METRICS

| Metric | Day 3 | Day 7 | Day 14 |
|---|---|---|---|
| GitHub stars | 25 | 75 | 200 |
| Installs | 100 | 400 | 1,200 |
| Free users | 80 | 320 | 960 |
| Paid users | 5 | 40 | 150 |
| MRR | $30 | $240 | $900 |
| awesome-claude-skills listed | ✓ | ✓ | ✓ |
| CC Marketplace submitted | ✓ | ✓ | ✓ |
| Product Hunt launched | — | — | ✓ |

---

## THE ONE THING

If you do everything else wrong but get this one thing right, you hit the number:

**The demo GIF exists and it shows both modules firing in sequence.**

The Dispatch intercept notification is dramatic. Scored comparison, blocked tool, TOP PICK. The XF Audit violation is concrete. Broken import, repair plan, 200ms. Both firing in one 30-second session is the entire argument for the product. Without it, everything else is text. With it, every channel converts.

Make the GIF on Day 1. Everything else follows from that.
