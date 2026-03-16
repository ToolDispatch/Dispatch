# Contributing to Dispatch

Thanks for your interest. Dispatch is a small, focused tool — contributions that keep it that way are most welcome.

---

## What's most useful

### Bug reports

Open an Issue with:
- What you were doing when it happened
- The task type Dispatch detected (or failed to detect)
- Any error output from `~/.claude/hooks/dispatch.sh` or `~/.claude/hooks/dispatch-preuse.sh`
- Your OS, Python version, and whether you're using hosted or BYOK mode

### Classifier improvements

The classifier (`classifier.py`) is the highest-leverage place to contribute. It determines what counts as a shift and what action mode you're in.

Good contributions here:
- Natural language examples that the current prompt misclassifies
- Edge cases where the 7-mode taxonomy breaks down
- Prompt wording improvements that make Haiku more consistent

To test classifier changes:
```bash
cd /path/to/Dispatch
python3 -m pytest test_classifier.py -v
```

All 23 tests must pass. Add a test for any new behavior.

### Evaluator improvements

The evaluator (`evaluator.py`) handles plugin scanning and ranking. Good contributions:
- Better relevance ranking between installed plugins and the detected task
- Support for new plugin marketplace path formats
- Caching improvements

To test:
```bash
cd /path/to/Dispatch
python3 -m pytest test_evaluator.py -v
```

### Registry additions

If a skill on [skills.sh](https://skills.sh) or a Claude Code marketplace is useful for a common task type and isn't being surfaced, open an Issue describing:
- The task type (e.g., `flutter-fixing`)
- The skill name and install command
- Why it's better than what's currently being recommended

---

## How to submit a PR

1. Fork the repo
2. Create a branch: `git checkout -b fix/your-description`
3. Make your change — keep it focused, one thing per PR
4. Run the test suite: `python3 -m pytest test_classifier.py test_evaluator.py test_interceptor.py test_category_mapper.py test_llm_client.py test_stack_scanner.py -v`
5. All tests must pass before submitting
6. Open a PR with a clear description of what changed and why

---

## What we won't merge

- Changes that add new dependencies without strong justification (the hook has a 10s timeout — weight matters)
- New configuration options for behavior that should just work automatically
- Anything that makes the hook block Claude or slow it down meaningfully
- Changes to the fixed-cost classifier path that increase Haiku call frequency

---

## Code style

- Python: standard library where possible, no type annotations required
- Bash: POSIX-compatible where possible, avoid bashisms
- Tests: follow the existing `unittest` + `patch` pattern in `test_classifier.py`
- Commit messages: imperative, lowercase, one line if possible

---

Questions? Open an Issue. This project moves fast and we're happy to talk through ideas before you build them.
