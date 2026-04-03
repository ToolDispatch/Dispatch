# auditor.py
from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
from datetime import datetime, timezone
from typing import Dict, Any, List

from flow_analyzer import build_index
from checkers import (syntax_violations, from_import_violations,
                      arity_violations, env_var_violations, stub_violations,
                      silent_except_violations)
from cascade import trace_cascade, format_cascade_report, format_cascade_notification
from repair import build_repair_plan, format_repair_plan
from consent import (get_trust_level, format_consent_options,
                     append_repair_log, reset_trust, increment_trust)
from refactor_mode import (is_active as refactor_is_active, add_violations as refactor_add,
                           get_accumulated, get_description, format_status_line,
                           format_consolidated_report, should_suggest_refactor_mode,
                           format_refactor_suggestion)
from colors import XFA_CYAN, XFA_GREEN, XFA_RED, XFA_YELLOW, XFA_GRAY, XFA_RESET
from xsi import analyze as xsi_analyze

AUDIT_TOOLS = {"Edit", "Write"}


def _ensure_xf_dir(root: str) -> str:
    p = os.path.join(root, ".xf")
    os.makedirs(p, exist_ok=True)
    return p


def _write_json(path: str, obj: Dict[str, Any]) -> None:
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(obj, f, indent=2)
    os.replace(tmp, path)


def _run_check(fn, *args, name="check"):
    """Run a checker function, logging failures to stderr instead of silently swallowing."""
    try:
        return fn(*args)
    except Exception as e:
        print(f"[XFA] {name} failed: {e}", file=sys.stderr)
        return []


def main() -> int:
    try:
        raw = sys.stdin.read()
        hook_input = json.loads(raw)
    except Exception:
        return 0

    tool_name = hook_input.get("tool_name", "")
    if tool_name not in AUDIT_TOOLS:
        return 0

    # Fix 1: git-based root detection (cwd= ensures os.getcwd() mock works in tests)
    cwd_fallback = os.getcwd()
    try:
        root = subprocess.check_output(
            ['git', 'rev-parse', '--show-toplevel'],
            cwd=cwd_fallback,
            stderr=subprocess.DEVNULL
        ).decode().strip()
    except Exception:
        root = cwd_fallback

    xf_dir = _ensure_xf_dir(root)

    # Build the index
    try:
        index = build_index(root)
    except Exception:
        return 0

    # Fix 7: Forward-look for Edit/Write — check proposed content
    tool_input = hook_input.get("tool_input", {})
    proposed_content = None
    proposed_file = None
    current_content = None  # populated for Edit; None for Write (new file)
    if tool_name == "Edit":
        proposed_file = tool_input.get("file_path", "")
        old_string = tool_input.get("old_string", "")
        new_string = tool_input.get("new_string", "")
        if proposed_file and old_string and new_string:
            try:
                with open(proposed_file, "r", encoding="utf-8") as f:
                    current_content = f.read()
                proposed_content = current_content.replace(old_string, new_string, 1)
            except Exception:
                pass
    elif tool_name == "Write":
        proposed_file = tool_input.get("file_path", "")
        proposed_content = tool_input.get("content", "")
        try:
            if proposed_file and os.path.isfile(proposed_file):
                with open(proposed_file, "r", encoding="utf-8") as f:
                    current_content = f.read()
        except Exception:
            pass

    # If we have proposed content, build a temp-based forward index
    if proposed_file and proposed_content:
        try:
            from scanner_registry import scan_file
            suffix = os.path.splitext(proposed_file)[1] or ".py"
            with tempfile.NamedTemporaryFile(suffix=suffix, mode="w",
                                             delete=False, encoding="utf-8") as tmp:
                tmp.write(proposed_content)
                tmp_path = tmp.name
            proposed_st = scan_file(tmp_path)
            if proposed_st:
                rel_proposed = os.path.relpath(proposed_file, root)
                mod_key = rel_proposed[:-3] if rel_proposed.endswith('.py') else rel_proposed
                if mod_key in index.get("modules", {}):
                    index["modules"][mod_key].update({
                        "functions": proposed_st.functions,
                        "exports": sorted(set(proposed_st.exports)),
                        "env_vars_hard": proposed_st.env_vars_hard,
                        "env_vars_soft": proposed_st.env_vars_soft,
                    })
            os.unlink(tmp_path)
        except Exception:
            pass

    module_count = len(index.get("modules", {}))
    edge_count = len(index.get("callers", []))

    # Collect .py paths for syntax check
    py_paths = []
    for info in index.get("modules", {}).values():
        p = info.get("path", "")
        if p.endswith(".py"):
            abs_p = os.path.join(root, p)
            if os.path.isfile(abs_p):
                py_paths.append(abs_p)

    # Fix 3: Load previous violations for trust increment tracking
    prev_violations = []
    vio_path = os.path.join(xf_dir, "boundary_violations.json")
    try:
        prev_data = json.loads(open(vio_path).read())
        prev_violations = prev_data.get("violations", [])
    except Exception:
        pass

    # --- Stage 1: Run all checks using _run_check for Fix 12 ---
    all_violations: List[Dict] = []
    all_warnings: List[Dict] = []

    def partition(viols):
        for v in viols:
            if v.get("severity") == "error":
                all_violations.append(v)
            else:
                all_warnings.append(v)

    partition(_run_check(syntax_violations, py_paths, name="syntax"))
    partition(_run_check(from_import_violations, index, name="from_import"))
    partition(_run_check(arity_violations, index, name="arity"))
    partition(_run_check(env_var_violations, index, root, name="env_var"))
    partition(_run_check(stub_violations, index, name="stub"))
    partition(_run_check(silent_except_violations, py_paths, name="silent_except"))

    # Load project-level suppress config — .xf/suppress.json
    # Format: {"suppress": [{"type": "silent_exception", "reason": "..."}]}
    suppress_types: set = set()
    suppress_path = os.path.join(xf_dir, "suppress.json")
    try:
        suppress_cfg = json.loads(open(suppress_path).read())
        for rule in suppress_cfg.get("suppress", []):
            t = rule.get("type")
            if t:
                suppress_types.add(t)
    except Exception:
        pass
    if suppress_types:
        all_violations = [v for v in all_violations if v.get("type") not in suppress_types]
        all_warnings   = [v for v in all_warnings   if v.get("type") not in suppress_types]

    # Fix 3: Increment trust for each resolved violation
    if prev_violations:
        prev_ids = {v.get("id") for v in prev_violations}
        curr_ids = {v.get("id") for v in all_violations}
        resolved_count = len(prev_ids - curr_ids)
        for _ in range(resolved_count):
            try:
                increment_trust(xf_dir)
            except Exception:
                pass

    # Save violations for provenance
    vio_obj = {
        "schema_version": "1.1",
        "audit_timestamp": datetime.now(timezone.utc).isoformat(),
        "cwd": root,
        "total_violations": len(all_violations),
        "total_warnings": len(all_warnings),
        "violations": all_violations,
        "warnings": all_warnings,
        "ralph_iteration": 0,
    }
    try:
        _write_json(os.path.join(xf_dir, "boundary_violations.json"), vio_obj)
    except Exception:
        pass

    # Fix 9: Track recent symbols for refactor auto-detect
    recent_symbols_path = os.path.join(xf_dir, "recent_symbols.json")
    recent = []
    try:
        recent = json.loads(open(recent_symbols_path).read()) if os.path.isfile(recent_symbols_path) else []
        if all_violations:
            primary_sym = all_violations[0].get("symbol", "")
            if primary_sym:
                recent.append(primary_sym)
                recent = recent[-10:]  # keep last 10
        with open(recent_symbols_path, "w") as f:
            json.dump(recent, f)
    except Exception:
        pass

    # --- Refactor Mode check ---
    if refactor_is_active(xf_dir):
        if all_violations:
            try:
                refactor_add(xf_dir, all_violations)
            except Exception:
                pass
        acc = []
        try:
            acc = get_accumulated(xf_dir)
        except Exception:
            pass
        desc = get_description(xf_dir)
        sys.stderr.write(format_status_line(len(acc), desc) + "\n")
        return 0  # Never blocks in refactor mode

    # --- Stage 5: XSI — System Impact Inspector ---
    xsi_concerns: List[Dict] = []
    try:
        xsi_concerns = xsi_analyze(index, proposed_file or "", proposed_content or "",
                                   current_content, root)
    except Exception:
        pass

    # --- Clean path (no XFA violations, no XSI concerns) ---
    if not all_violations and not xsi_concerns:
        warning_suffix = ""
        if all_warnings:
            warning_suffix = f"  {XFA_YELLOW}{len(all_warnings)} warning(s){XFA_RESET}"
        stamp = (
            f"{XFA_CYAN}◈ XFBA{XFA_RESET}  "
            f"{XFA_GRAY}{module_count} modules · {edge_count} edges{XFA_RESET}  "
            f"{XFA_GREEN}✓ 0 violations{XFA_RESET}{warning_suffix}\n"
            f"{XFA_CYAN}◈ XSIA{XFA_RESET}  {XFA_GREEN}✓ 0 concerns{XFA_RESET}\n"
        )
        try:
            with open("/dev/tty", "w") as tty:
                tty.write(stamp)
        except OSError:
            sys.stderr.write(stamp)
        return 0

    # --- XSI concerns only (no XFA violations) — block with choice ---
    if not all_violations and xsi_concerns:
        fname = os.path.basename(proposed_file) if proposed_file else "?"
        warning_suffix = ""
        if all_warnings:
            warning_suffix = f"  {XFA_YELLOW}{len(all_warnings)} warning(s){XFA_RESET}"
        # Clean stamp to terminal first so user sees XFBA passed
        clean_stamp = (
            f"{XFA_CYAN}◈ XFBA{XFA_RESET}  "
            f"{XFA_GRAY}{module_count} modules · {edge_count} edges{XFA_RESET}  "
            f"{XFA_GREEN}✓ 0 violations{XFA_RESET}{warning_suffix}\n"
        )
        try:
            with open("/dev/tty", "w") as tty:
                tty.write(clean_stamp)
        except OSError:
            sys.stderr.write(clean_stamp)
        # XSI block to stdout → CC context (exit 2)
        lines = [
            f"{XFA_CYAN}◈ XSIA{XFA_RESET}  "
            f"{XFA_YELLOW}{fname}  {len(xsi_concerns)} systemic concern(s){XFA_RESET}",
            "",
        ]
        for c in xsi_concerns[:5]:
            dim = c.get("dimension", "?").ljust(12)
            lines.append(f"  {XFA_GRAY}↳ {dim}{XFA_RESET}  {c.get('detail', '')}")
        lines += [
            "",
            f"  {XFA_GREEN}Say 'fix impact issues'{XFA_RESET} — I'll review and address each concern before editing.",
            f"  {XFA_GRAY}Say 'let it ride'{XFA_RESET}   — proceed with this edit as-is.",
        ]
        sys.stdout.write("\n".join(lines) + "\n")
        return 2

    # Fix 9: Auto-suggest refactor mode if same symbol appears 3+ times recently
    if not refactor_is_active(xf_dir) and all_violations:
        try:
            if should_suggest_refactor_mode(recent):
                sym = recent[-1]
                sys.stderr.write(format_refactor_suggestion(sym) + "\n")
                return 0  # Don't block when suggesting refactor mode
        except Exception:
            pass

    # --- Stage 2: Cascade tracing — Fix 4: restrict to stub_function with callers only ---
    cascade_symbols = set()
    for v in all_violations:
        sym = v.get("symbol")
        if sym and v.get("type") == "stub_function" and v.get("has_callers"):
            cascade_symbols.add(sym)

    # Fix 5: Write cascade notification to stdout before tracing
    if cascade_symbols:
        for sym in cascade_symbols:
            n_direct = len([e for e in index.get("callers", []) if e.get("symbol") == sym])
            sys.stdout.write(format_cascade_notification(sym, n_direct) + "\n")
            sys.stdout.flush()

    cascades: Dict[str, List] = {}
    for sym in cascade_symbols:
        try:
            result = trace_cascade(index, sym)
            if result:
                cascades[sym] = result
        except Exception:
            pass

    # --- Stage 3: Repair plan ---
    repair_plan = []
    try:
        repair_plan = build_repair_plan(all_violations)
    except Exception:
        pass

    # --- Stage 4: Consent options ---
    trust_level = 0
    try:
        trust_level = get_trust_level(xf_dir)
    except Exception:
        pass

    # --- Format and output ---
    output_lines = []

    output_lines.append(
        f"{XFA_CYAN}◈ XFBA{XFA_RESET}  "
        f"{XFA_RED}This edit will break at runtime.{XFA_RESET}"
    )
    output_lines.append("")

    try:
        output_lines.append(format_repair_plan(repair_plan))
    except Exception:
        for v in all_violations[:10]:
            output_lines.append(
                f"  {XFA_GRAY}{v.get('caller_module','?')}:{v.get('caller_line','?')}{XFA_RESET}  "
                f"{v.get('consequence','')}"
            )

    # Cascade output (first cascade symbol only)
    if cascades:
        sym, cascade = next(iter(cascades.items()))
        try:
            output_lines.append(format_cascade_report(sym, cascade))
        except Exception:
            pass

    # Warnings
    if all_warnings:
        output_lines.append(
            f"{XFA_YELLOW}{len(all_warnings)} warning(s) — not blocking:{XFA_RESET}"
        )
        for w in all_warnings[:5]:
            output_lines.append(
                f"  {XFA_GRAY}{w.get('caller_module','?')}:{w.get('caller_line','?')}{XFA_RESET}  "
                f"{w.get('consequence','')}"
            )

    # Consent options
    try:
        output_lines.append(format_consent_options(trust_level, len(repair_plan)))
    except Exception:
        output_lines.append(f"\n  {XFA_GRAY}Say 'show me the diff first' or 'skip for now'.{XFA_RESET}")

    # Append XSI concerns if present alongside XFA violations
    if xsi_concerns:
        fname = os.path.basename(proposed_file) if proposed_file else "?"
        output_lines.append("")
        output_lines.append(
            f"{XFA_CYAN}◈ XSIA{XFA_RESET}  "
            f"{XFA_YELLOW}{fname}  {len(xsi_concerns)} systemic concern(s) — fix XFBA first{XFA_RESET}"
        )
        for c in xsi_concerns[:5]:
            dim = c.get("dimension", "?").ljust(12)
            output_lines.append(f"  {XFA_GRAY}↳ {dim}{XFA_RESET}  {c.get('detail', '')}")

    sys.stdout.write("\n".join(output_lines) + "\n")
    return 2


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception:
        sys.exit(0)
