# XFA Contract Loop — Design Spec
**Date:** 2026-03-28
**Status:** Approved for implementation
**Product:** XF Boundary Auditor (folding into Contractor)
**Author:** Russ Wright + Claude

---

## The One-Sentence Product Statement

An insurance policy embedded in every edit — it catches broken contracts before they run, tells CC exactly how to fix them, and leaves a record that it did.

---

## What Problem This Solves

Claude Code produces architecturally sound code that often doesn't connect. It renames a function and misses three callers. It calls a function with the wrong number of arguments. It imports a symbol that was refactored away. These failures are silent until runtime — and by then the session context is gone and the cause is hard to trace.

XFA closes that loop at the edit boundary, where the cost of fixing is near-zero and the context is still live.

---

## The Four-Stage Contract Loop

Every Edit or Write triggers the loop. Most of the time it completes in Stage 1 and the user sees a green stamp. Deeper stages only fire when something is actually wrong.

### Stage 1 — Is this broken? (always runs, ~140–200ms)

Fast AST scan of the full repo. Checks:

| Check | Method | Response |
|-------|--------|----------|
| Syntax error | `py_compile` | Block immediately |
| From-import existence | AST symbol table | Block immediately |
| Arity mismatch (new call sites) | AST call graph | Block immediately |
| Missing env var, hard access (`os.environ["KEY"]`) | AST + `.env` scan | Block immediately |
| Stub with annotated non-None return | AST body + annotation | Escalate to Stage 2 |
| Contract change (existing signature modified) | Diff boundary index | Escalate to Stage 2 |

**Clean output:**
```
◈ XFA  47 modules · 203 edges checked  ✓ 0 violations
```

**Immediate block output (consequence-first language):**
```
◈ XFA  This edit will break at runtime.

  evaluator.py:203 — calls rank_tools() with 3 arguments, but it only accepts 2.
  This will throw a TypeError when that code runs.

  Fix: remove the third argument, or update rank_tools() to accept it.
  [apply fix] [show me the diff first] [skip]
```

Note: technical detail (file:line, symbol names) is always present, but the *leading sentence* is plain consequence language. Both audiences get what they need.

---

### Stage 2 — What did the change break? (fires on escalation only)

Invoked when Stage 1 detects a contract change to an existing symbol, or a stub with a non-None return that may be consumed by callers.

Notification fires within 500ms of Stage 2 starting:
```
◈ XFA  Contract change detected — mapping consequences...
```

This tells the user something was found and latency is expected. No silent waiting.

Xpansion analyzes the change using its MECE boundary framework (DATA, NODES, FLOW, ERRORS):
- Which callers depend on the changed contract?
- What do they expect the function to return?
- Which downstream consumers does that affect?
- What fails silently vs. throws?

Output is a **structured cascade** — ordered by dependency chain, not alphabetically. Fix the root first and the rest may resolve automatically.

---

### Stage 3 — What does CC need to do to fix it?

Xpansion's cascade feeds a repair plan. Each violation gets one specific, file-and-line fix. No vague guidance.

**Repair plan format:**
```
◈ XFA  3 contracts broken by this change.

  1. evaluator.py:203 — rank_tools() called with 3 args (needs 2)
     This will throw TypeError when the ranker runs.
     Fix: evaluator.py:203 — remove third argument

  2. preuse_hook.sh:89 — imports load_stack_profile (renamed to get_stack_profile)
     This will fail silently — hook exits 0 without ranking.
     Fix: preuse_hook.sh:89 — update import name

  3. test_evaluator.py:44 — same import
     Fix: test_evaluator.py:44 — update import name
```

Each entry has: location → consequence in plain language → specific fix.

---

### Stage 4 — Do you want it fixed?

Three options, graduated by trust:

**First time (or when fixes involve logic changes):**
```
  [show me the diff first]  [skip for now]
```
Auto-apply is not offered until the user has seen repair suggestions execute correctly. Trust is earned, not assumed.

**After the user has accepted and verified two or more repair suggestions this session:**
```
  [apply all 3]  [show me the diff first]  [skip for now]
```
The "apply all" option appears only after it's been earned.

**Skip behavior:**
Records violations as open in `.xf/boundary_violations.json`. Does NOT suppress future identical violations — the contract remains broken. Skip means "I'll handle it," not "ignore this."

---

## Refactor Mode

The single biggest friction point for senior developers: XFA blocking mid-refactor when they know the code is temporarily broken and plan to fix it in sequence.

**How it works:**

User or CC signals a deliberate multi-step change:
```
/xfa-refactor start "renaming rank_tools → score_tools"
```

XFA shifts from blocking to **tracking**:
- Violations are recorded in `.xf/refactor_session.json`
- No blocks, no interruptions during the refactor window
- A compact status line shows the open violation count:
  ```
  ◈ XFA [refactor]  3 open contracts
  ```

When the refactor is declared complete — either explicitly (`/xfa-refactor end`) or when CC signals it's done:
- XFA presents the full consolidated violation list
- Runs the Stage 2–3 cascade on everything at once
- Offers repair for all outstanding contracts in a single pass

**Auto-detection (no explicit signal needed):**
If XFA detects the same symbol being modified across 3+ consecutive edits, it automatically suggests entering refactor mode:
```
◈ XFA  Looks like a refactor in progress — want to switch to tracking mode?
  I'll hold violations until you're done and present them all at once.
  [yes, tracking mode]  [no, keep blocking]
```

---

## Block vs. Warn vs. Track

| Situation | Response | Rationale |
|-----------|----------|-----------|
| Syntax error | **Block** | Won't parse — nothing works |
| Arity mismatch, new call site | **Block** | Will throw at runtime |
| Missing env var, hard access | **Block** | Will KeyError at runtime |
| From-import missing symbol | **Block** | Module won't load |
| Stub, non-None return, caller consumes it | **Block** | Caller gets None, breaks silently |
| Existing contract changed, callers break | **Track** (not block) | Mid-refactor is valid state |
| Stub, void return or no annotation | **Warn** | Incomplete but not broken |
| Missing env var, `os.getenv` with default | **Warn** | Has fallback, won't throw |
| pyflakes issues (if installed) | **Warn** | Signal, not contract failure |

---

## Provenance Model

Every scan leaves a record. This is the "insurance policy receipt."

`.xf/boundary_violations.json` — current open violations
`.xf/boundary_index.json` — full symbol export map, last scan timestamp
`.xf/repair_log.json` — every repair applied: what was broken, what fix was applied, timestamp, which CC session

The repair log is the provenance. When something goes wrong in production and you need to know "did we catch this?" — the log answers that question. It also surfaces patterns: if the same type of violation appears repeatedly, that's a signal about CC's output quality for a specific task type.

Session digest (Stop hook) includes XFA stats:
```
◈ XFA  Session: 89 edits checked · 2 contracts repaired · 0 open violations
```

---

## Output Language Rules

Two registers, always both present:

**Consequence-first (leading sentence):** What breaks, when, how visibly. Plain English. No jargon.
> "This will throw a TypeError when the ranker runs."
> "This will fail silently — the hook exits without ranking."
> "This import will fail when the module loads."

**Technical detail (body):** File, line, symbol, exact fix. For the developer who wants to verify.
> `evaluator.py:203 — rank_tools() called with 3 args (accepts 2)`

Never lead with the technical detail. The consequence comes first.

---

## Integration with Xpansion

Xpansion is invoked in Stage 2 only, on escalation. It receives:
- The changed or violated contract (function signature, import, symbol)
- The current boundary index (what the repo looks like now)
- The cascade scope (which modules to trace)

Xpansion returns:
- Ordered list of affected callers and consumers
- For each: what they expect, what they'll get, what fails
- Repair suggestions per violation

Xpansion is **not** invoked on clean scans. It is **not** invoked for Stage 1 blocks where the fix is deterministic (arity, syntax). It is invoked when reasoning about consequences requires understanding the full call graph — which mechanical AST cannot do reliably.

---

## What XFA Does Not Catch

Explicitly out of scope (important for managing user expectations):

- **Business logic errors** — wrong algorithm, wrong formula, wrong data transformation
- **Third-party API contract changes** — if `stripe.Charge.create()` changes its interface, XFA doesn't know
- **Runtime state errors** — race conditions, null values that only appear with specific data
- **Test correctness** — tests passing doesn't mean the logic is right

XFA's green stamp means: **the contracts between your local modules are intact**. It does not mean the code is correct. This distinction must be communicated clearly in output and docs to prevent the false-security problem.

---

## New Checks Summary

| Check | Stage | Method | Response |
|-------|-------|--------|----------|
| Syntax validation | 1 | `py_compile` | Block |
| From-import existence | 1 | AST (existing) | Block |
| Arity mismatch | 1 | AST call graph | Block |
| Missing env var (hard) | 1 | AST + `.env` scan | Block |
| Stub (non-None return, consumed) | 1 detect → 2 analyze | AST + Xpansion | Block |
| Stub (void / unannotated) | 1 | AST | Warn |
| Missing env var (getenv + default) | 1 | AST | Warn |
| Contract change cascade | 1 detect → 2 analyze | Diff index + Xpansion | Track or Block |
| pyflakes issues | 1 | pyflakes (if installed) | Warn |

---

## Graduated Trust Model

Auto-repair ("apply all") is not offered by default. The sequence:

1. **First repair offered:** "show me the diff first" and "skip" only
2. **User reviews diff, approves:** fix applied, noted in repair log
3. **Second repair offered same session:** same — show diff first
4. **User approves again:** "apply all" option unlocks for remainder of session
5. **Next session:** resets to step 1

Trust earned per session, not persisted. This prevents "I always click yes" from becoming a habit that hides bad auto-repairs.

---

## Spec Self-Review

- **Placeholders:** None. All sections are complete.
- **Contradictions:** Block vs. track for contract changes is consistent throughout — new violations block, changes to existing contracts track.
- **Scope:** Focused on XFA augmentation. Contractor unification (combining with Dispatch) is a separate spec.
- **Ambiguity:** "Consumed by a caller" is defined by Xpansion's call graph analysis, not by AST heuristic alone — this is explicit in the Xpansion integration section.
- **Out of scope documented:** False-security risk is called out explicitly in "What XFA Does Not Catch."
