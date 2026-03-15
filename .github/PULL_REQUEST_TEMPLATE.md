## What does this PR do?

<!-- One sentence description -->

## Why?

<!-- Context: bug fix, new feature, improvement? Link to issue if one exists -->

## Testing

- [ ] All existing tests pass (`python3 -m pytest test_*.py -v`)
- [ ] New tests added for new behavior
- [ ] Manually tested with a live CC session (if hook behavior changed)

## Checklist

- [ ] No production code added without a failing test first
- [ ] Hook still exits 0 on all failure paths (never blocks Claude)
- [ ] No shell injection risks (user input via sys.argv, not string interpolation)
- [ ] `sed '$d'` used instead of `head -n -1` for portability
