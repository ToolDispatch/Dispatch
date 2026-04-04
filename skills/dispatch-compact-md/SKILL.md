---
name: dispatch-compact-md
description: Compact oversized CLAUDE.md files by moving reference-only sections to ~/.claude/ref/ files Claude reads on demand — reduces per-message token overhead
---

Compact the CLAUDE.md files flagged by XFTC as oversized. Follow these steps precisely:

## Step 1 — Find and measure targets

Run the following to identify candidates:

```bash
python3 - << 'PYEOF'
import os

targets = [
    os.path.expanduser("~/CLAUDE.md"),
    os.path.expanduser("~/.claude/CLAUDE.md"),
    os.path.join(os.getcwd(), "CLAUDE.md"),
    os.path.join(os.getcwd(), ".claude/CLAUDE.md"),
]

found = []
for path in targets:
    if os.path.exists(path):
        with open(path) as f:
            lines = f.readlines()
        count = len(lines)
        flag = "⚠️ over limit" if count > 200 else "✓ ok"
        found.append((path, count, flag))

if not found:
    print("No CLAUDE.md files found.")
else:
    for path, count, flag in found:
        print(f"{flag}  {count} lines  {path}")
PYEOF
```

If $ARGUMENTS is provided, restrict to that file path only. If all files are under 200 lines, report that and stop.

## Step 2 — Identify ref-eligible sections

For each file over 200 lines, read it and identify sections that are **ref-eligible** — content Claude only needs occasionally, not on every message:

**Ref-eligible** (move to `~/.claude/ref/`):
- Inline code examples and full command snippets (more than 5 lines)
- Long tables (more than 8 rows) that are lookup references, not rules
- Version history, known issue changelogs, migration notes
- Detailed architecture descriptions with sub-bullets
- Testing patterns, SQL patterns, bash API patterns
- Step-by-step procedures with numbered sub-steps

**Keep in CLAUDE.md** (never move):
- Protocol names and their one-line rule summaries
- Tool/app tables with 3–5 columns and fewer than 10 rows
- Pointer lines referencing ref files (e.g., `See ~/.claude/ref/foo.md for...`)
- Any rule with the word SUPREME, NEVER, or ALWAYS in it
- Section headers and their first 1–2 sentences of context

## Step 3 — Propose the restructuring

Before making any changes, show the user a compact plan:

```
CLAUDE.md compact plan: <filepath>
Current: <N> lines → Target: ~<M> lines

Sections to move to ~/.claude/ref/:
  → ref/<name>.md  — <section heading> (~N lines)
  → ref/<name>.md  — <section heading> (~N lines)
  ...

Sections staying in CLAUDE.md:
  ✓ <section heading>
  ✓ <section heading>
  ...

Proceed? (yes to apply / no to cancel)
```

Wait for explicit confirmation before making any edits.

## Step 4 — Apply

For each section being moved:
1. Determine a short filename: lowercase, hyphen-separated, descriptive (e.g., `playwright-testing.md`, `dispatch-patterns.md`)
2. Check if `~/.claude/ref/<name>.md` already exists — if so, append to it rather than overwrite
3. Write the section content to `~/.claude/ref/<name>.md` with a header comment: `# <Section Title>\n\nLoad when: <one-line description of when this is relevant>.\n\n---\n\n<content>`
4. Replace the section in CLAUDE.md with a single pointer line: `See \`~/.claude/ref/<name>.md\` for <brief description>.`

Apply all moves in one pass. Do not edit any section you are not moving.

## Step 5 — Verify and report

After all edits:
1. Read back the updated CLAUDE.md and count lines
2. Run `git diff <filepath>` — confirm only moved sections changed
3. List each new or updated ref file with its line count

Report:
```
✅ Compact complete
  <filepath>: 287 lines → 94 lines (-193)

  Created/updated ref files:
    ~/.claude/ref/<name>.md  (N lines)
    ~/.claude/ref/<name>.md  (N lines)

  CLAUDE.md now loads pointer lines — ref files load on demand only.
```

If anything looks wrong in the diff, stop and report to the user before continuing.
