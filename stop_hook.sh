#!/bin/bash
# =============================================================================
# Dispatch — Stop Hook
#
# Fires when a CC session ends. Reads session counters from state.json and
# prints a one-line digest so users can see Dispatch was active during the
# session — addresses the "silent success = invisible value" problem.
#
# Always exits 0. Never blocks session close.
# =============================================================================

SKILL_ROUTER_DIR="${HOME}/.claude/dispatch"

python3 -c "
import sys, os
sys.path.insert(0, sys.argv[1])

BLUE   = '\033[94m'
GREEN  = '\033[92m'
YELLOW = '\033[93m'
GRAY   = '\033[90m'
RESET  = '\033[0m'

try:
    from interceptor import get_session_stats
    stats  = get_session_stats()
    audits = stats['audits']
    blocks = stats['blocks']
    recs   = stats['recommendations']

    # Only output if Dispatch did anything this session
    if audits == 0 and recs == 0:
        sys.exit(0)

    block_part = (f'{YELLOW}{blocks} blocked{RESET}' if blocks > 0
                  else f'{GREEN}0 blocked (all optimal){RESET}')
    rec_word   = 'recommendations' if recs != 1 else 'recommendation'
    print(f'{BLUE}◎ Dispatch{RESET}  {GRAY}{audits} audited{RESET} · {block_part} · {GRAY}{recs} {rec_word} shown{RESET}')
except Exception:
    pass
" "$SKILL_ROUTER_DIR" 2>/dev/null || true

# XF Audit session digest
python3 -c "
import sys, os, json, time
sys.path.insert(0, os.path.expanduser('~/.claude/xf-boundary-auditor'))

XFA_CYAN   = '\033[96m'
XFA_GREEN  = '\033[92m'
XFA_YELLOW = '\033[93m'
XFA_GRAY   = '\033[90m'
XFA_RESET  = '\033[0m'

xf_dir = os.path.join(os.getcwd(), '.xf')
if not os.path.isdir(xf_dir):
    sys.exit(0)

# If refactor mode is active, present consolidated violations
try:
    from refactor_mode import is_active, get_accumulated, get_description, format_consolidated_report, deactivate
    if is_active(xf_dir):
        acc = get_accumulated(xf_dir)
        desc = get_description(xf_dir)
        print(format_consolidated_report(acc, desc))
        deactivate(xf_dir)
        sys.exit(0)
except Exception:
    pass

# Standard session digest
try:
    vio_path = os.path.join(xf_dir, 'boundary_violations.json')
    if not os.path.isfile(vio_path):
        sys.exit(0)
    mtime = os.path.getmtime(vio_path)
    if time.time() - mtime > 3600:
        sys.exit(0)  # stale
    data = json.loads(open(vio_path).read())
    total_viols = data.get('total_violations', 0)
    total_warns = data.get('total_warnings', 0)

    # Repair log count
    log_path = os.path.join(xf_dir, 'repair_log.json')
    repairs = 0
    if os.path.isfile(log_path):
        log_data = json.loads(open(log_path).read())
        repairs = len(log_data.get('repairs', []))

    repair_part = f' · {XFA_GREEN}{repairs} repaired{XFA_RESET}' if repairs > 0 else ''
    if total_viols == 0 and total_warns == 0:
        print(f'{XFA_CYAN}◈ XF Audit{XFA_RESET}  {XFA_GREEN}✓ all contracts intact{XFA_RESET}{repair_part}')
    elif total_viols == 0:
        print(f'{XFA_CYAN}◈ XF Audit{XFA_RESET}  {XFA_GREEN}✓ 0 violations{XFA_RESET}  {XFA_YELLOW}{total_warns} warning(s){XFA_RESET}{repair_part}')
    else:
        print(f'{XFA_CYAN}◈ XF Audit{XFA_RESET}  {XFA_YELLOW}{total_viols} open violation(s){XFA_RESET}{repair_part}  — run /xf-audit to fix')
except Exception:
    pass
" 2>/dev/null || true

exit 0
