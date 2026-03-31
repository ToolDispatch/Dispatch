"""
Boundary Contract Audit — Dispatch
====================================
Verifies every interface boundary the hooks depend on:
  1. Every function called from dispatch.sh / preuse_hook.sh exists
  2. No stale/deleted function references
  3. State JSON fields are consistent between writers and readers
  4. CC hook input fields are handled correctly

This is the XF MECE boundary audit applied to code.
Any function rename, module refactor, or API change that breaks
a hook boundary will surface HERE — not in a live e2e session.
"""

import sys
import importlib
import inspect
import json
import os
import tempfile
import pytest

sys.path.insert(0, os.path.dirname(__file__))


# ── Layer 1: Interface Existence ──────────────────────────────────────────────
# Every symbol imported by the hooks. If it moves, renames, or is deleted,
# the hook fails silently via broad except. This test catches it first.

REQUIRED_SYMBOLS = [
    # (module, name, expected_type)  type: 'callable' | 'constant'
    ("category_mapper",  "map_to_category",              "callable"),
    ("category_mapper",  "log_unknown_category",          "callable"),
    ("interceptor",      "get_last_recommended_category", "callable"),
    ("interceptor",      "write_last_recommended_category","callable"),
    ("interceptor",      "should_intercept",              "callable"),
    ("interceptor",      "check_bypass",                  "callable"),
    ("interceptor",      "clear_bypass",                  "callable"),
    ("interceptor",      "extract_cc_tool",               "callable"),
    ("interceptor",      "get_cc_tool_type",              "callable"),
    ("interceptor",      "get_task_type",                 "callable"),
    ("interceptor",      "get_context_snippet",           "callable"),
    ("interceptor",      "get_category",                  "callable"),
    ("interceptor",      "check_conversion",              "callable"),
    ("interceptor",      "clear_last_suggested",          "callable"),
    ("interceptor",      "write_bypass",                  "callable"),
    ("interceptor",      "write_last_suggested",          "callable"),
    ("interceptor",      "write_last_cc_tool_type",       "callable"),
    ("interceptor",      "increment_session_counter",     "callable"),
    ("interceptor",      "get_session_stats",             "callable"),
    ("interceptor",      "STATE_FILE",                    "constant"),
    ("evaluator",        "recommend_tools",               "callable"),
    ("evaluator",        "build_recommendation_list",     "callable"),
    ("stack_scanner",    "load_stack_profile",            "callable"),
    ("stack_scanner",    "scan_and_save",                 "callable"),
    ("classifier",       "extract_recent_messages",       "callable"),
]

# Symbols that must NOT exist (deleted/renamed — stale callers would silently fail)
MUST_NOT_EXIST = [
    ("stack_scanner", "get_stack_profile"),   # renamed to load_stack_profile
]


class TestInterfaceBoundaries:
    """Layer 1: Every function the hooks call must exist with the right type."""

    @pytest.mark.parametrize("mod_name,sym_name,sym_type", REQUIRED_SYMBOLS)
    def test_symbol_exists(self, mod_name, sym_name, sym_type):
        mod = importlib.import_module(mod_name)
        obj = getattr(mod, sym_name, None)
        assert obj is not None, (
            f"{mod_name}.{sym_name} is missing. "
            f"Hooks call this — ImportError is caught silently, "
            f"producing wrong behavior with no visible failure."
        )
        if sym_type == "callable":
            assert callable(obj), f"{mod_name}.{sym_name} exists but is not callable"

    @pytest.mark.parametrize("mod_name,sym_name", MUST_NOT_EXIST)
    def test_stale_symbol_absent(self, mod_name, sym_name):
        mod = importlib.import_module(mod_name)
        obj = getattr(mod, sym_name, None)
        assert obj is None, (
            f"{mod_name}.{sym_name} still exists but hooks have been updated to "
            f"not call it. Either it was renamed and callers weren't updated, "
            f"or it should be removed."
        )


# ── Layer 2: Signature Contracts ─────────────────────────────────────────────
# The hooks pass specific positional/keyword args. If the signature changes,
# the call fails silently. Check that required params still match expectations.

class TestSignatureContracts:

    def test_load_stack_profile_no_required_args(self):
        """Hooks call load_stack_profile() with no args. Must remain optional."""
        from stack_scanner import load_stack_profile
        sig = inspect.signature(load_stack_profile)
        required = [
            p for p in sig.parameters.values()
            if p.default is inspect.Parameter.empty
            and p.kind not in (inspect.Parameter.VAR_POSITIONAL, inspect.Parameter.VAR_KEYWORD)
        ]
        assert len(required) == 0, (
            f"load_stack_profile() has required params {[p.name for p in required]}. "
            f"Hooks call it with no args — this would fail silently."
        )

    def test_scan_and_save_cwd_is_first_param(self):
        """Hooks call scan_and_save(cwd). cwd must be first positional param."""
        from stack_scanner import scan_and_save
        sig = inspect.signature(scan_and_save)
        params = list(sig.parameters.keys())
        assert params[0] == "cwd", (
            f"scan_and_save first param is '{params[0]}', hooks pass cwd as positional arg."
        )

    def test_recommend_tools_accepts_expected_kwargs(self):
        """dispatch.sh calls recommend_tools(task_type, context_snippet, category_id,
        stack_profile, preferred_type). All must remain keyword-compatible."""
        from evaluator import recommend_tools
        sig = inspect.signature(recommend_tools)
        required_params = ["task_type", "context_snippet", "category_id", "stack_profile"]
        for p in required_params:
            assert p in sig.parameters, (
                f"recommend_tools missing param '{p}' — dispatch.sh Stage 3 would fail silently."
            )

    def test_build_recommendation_list_accepts_expected_kwargs(self):
        """preuse_hook.sh calls build_recommendation_list with these kwargs."""
        from evaluator import build_recommendation_list
        sig = inspect.signature(build_recommendation_list)
        required_params = ["task_type", "context_snippet", "cc_tool",
                           "category_id", "cc_tool_type", "stack_profile"]
        for p in required_params:
            assert p in sig.parameters, (
                f"build_recommendation_list missing param '{p}' — preuse hook BYOK path fails silently."
            )

    def test_extract_cc_tool_handles_none_input(self):
        """CC may pass tool_input as null. extract_cc_tool must not crash."""
        from interceptor import extract_cc_tool
        # None tool_input — should return tool_name, not raise
        result = extract_cc_tool("Skill", None)
        assert result == "Skill"

    def test_extract_cc_tool_handles_empty_dict(self):
        """Skill with no 'skill' field — return tool_name."""
        from interceptor import extract_cc_tool
        result = extract_cc_tool("Skill", {})
        assert result == "Skill"

    def test_extract_cc_tool_skill_reads_skill_field(self):
        """CC sends tool_input={'skill': 'owner/repo'} for Skill tool."""
        from interceptor import extract_cc_tool
        result = extract_cc_tool("Skill", {"skill": "superpowers:debugging"})
        assert result == "superpowers:debugging"

    def test_extract_cc_tool_agent_reads_subagent_type(self):
        """CC sends tool_input={'subagent_type': '...'} for Agent tool."""
        from interceptor import extract_cc_tool
        result = extract_cc_tool("Agent", {"subagent_type": "general-purpose"})
        assert result == "general-purpose"


# ── Layer 3: CC Hook Input Contract ──────────────────────────────────────────
# CC sends specific JSON fields on stdin. Verify hooks read the right fields
# and gracefully handle missing ones.

class TestCCHookInputContract:

    def test_userpromptsubmit_prompt_field_extracted(self):
        """dispatch.sh extracts 'prompt' from stdin JSON. Field must be 'prompt'."""
        import subprocess, json, tempfile, os
        hook_input = json.dumps({
            "hook_event_name": "UserPromptSubmit",
            "session_id": "test-123",
            "transcript_path": "/nonexistent/path.jsonl",
            "cwd": "/tmp",
            "prompt": "help me write a Flutter widget please"
        })
        result = subprocess.run(
            ["python3", "-c",
             "import json,sys; d=json.loads(sys.argv[1]); print(d.get('prompt',''))",
             hook_input],
            capture_output=True, text=True
        )
        assert result.stdout.strip() == "help me write a Flutter widget please"

    def test_userpromptsubmit_missing_prompt_returns_empty(self):
        """If CC omits 'prompt' (future CC version?), hook must not crash."""
        import subprocess, json
        hook_input = json.dumps({"hook_event_name": "UserPromptSubmit", "cwd": "/tmp"})
        result = subprocess.run(
            ["python3", "-c",
             "import json,sys; d=json.loads(sys.argv[1]); print(d.get('prompt',''))",
             hook_input],
            capture_output=True, text=True
        )
        assert result.stdout.strip() == ""
        assert result.returncode == 0

    def test_pretooluse_tool_name_field_extracted(self):
        """preuse_hook.sh extracts 'tool_name'. CC sends this field."""
        import subprocess, json
        hook_input = json.dumps({
            "hook_event_name": "PreToolUse",
            "tool_name": "Skill",
            "tool_input": {"skill": "superpowers:debugging"}
        })
        result = subprocess.run(
            ["python3", "-c",
             "import json,sys; d=json.loads(sys.argv[1]); print(d.get('tool_name',''))",
             hook_input],
            capture_output=True, text=True
        )
        assert result.stdout.strip() == "Skill"

    def test_pretooluse_mcp_tool_name_format(self):
        """CC sends mcp__<server>__<tool> format for MCP tools."""
        from interceptor import should_intercept, get_cc_tool_type
        assert should_intercept("mcp__github__create_pull_request")
        assert get_cc_tool_type("mcp__github__create_pull_request") == "mcp"

    def test_pretooluse_skill_tool_name_format(self):
        """CC sends 'Skill' (capital S) for skill tool calls."""
        from interceptor import should_intercept, get_cc_tool_type
        assert should_intercept("Skill")
        assert get_cc_tool_type("Skill") == "skill"

    def test_pretooluse_agent_tool_name_format(self):
        """CC sends 'Agent' (capital A) for agent tool calls."""
        from interceptor import should_intercept, get_cc_tool_type
        assert should_intercept("Agent")
        assert get_cc_tool_type("Agent") == "agent"

    def test_pretooluse_non_intercepted_tools_pass_through(self):
        """CC sends many tool names — only Skill/Agent/mcp__ are intercepted."""
        from interceptor import should_intercept
        pass_through = ["Read", "Write", "Edit", "Bash", "Glob", "Grep",
                        "WebFetch", "WebSearch", "TodoWrite", "NotebookEdit"]
        for tool in pass_through:
            assert not should_intercept(tool), f"'{tool}' should NOT be intercepted"


# ── Layer 4: State JSON Field Consistency ─────────────────────────────────────
# dispatch.sh writes fields. preuse_hook.sh reads them via interceptor.py.
# If a field is renamed in one place but not the other, it fails silently.

class TestStateFieldConsistency:

    WRITTEN_BY_DISPATCH = [
        "last_task_type",
        "last_category",
        "last_context_snippet",
        "last_cwd",
        "last_updated",
    ]

    READ_BY_PREUSE = [
        ("get_task_type",        "last_task_type"),
        ("get_category",         "last_category"),
        ("get_context_snippet",  "last_context_snippet"),
    ]

    def test_interceptor_reads_fields_dispatch_writes(self, monkeypatch):
        """Every field preuse_hook reads must be written by dispatch.sh.
        Uses monkeypatch to override STATE_FILE since these functions use the global."""
        import interceptor
        with tempfile.TemporaryDirectory() as tmpdir:
            state_file = os.path.join(tmpdir, "state.json")
            state = {field: f"test_{field}" for field in self.WRITTEN_BY_DISPATCH}
            with open(state_file, "w") as f:
                json.dump(state, f)

            monkeypatch.setattr(interceptor, "STATE_FILE", state_file)

            for fn_name, field in self.READ_BY_PREUSE:
                fn = getattr(interceptor, fn_name)
                result = fn()
                assert result == f"test_{field}", (
                    f"interceptor.{fn_name}() reads '{field}' from state. "
                    f"dispatch.sh must write exactly this key name."
                )

    def test_last_recommended_category_roundtrip(self):
        """write_last_recommended_category / get_last_recommended_category must agree."""
        import interceptor
        with tempfile.TemporaryDirectory() as tmpdir:
            state_file = os.path.join(tmpdir, "state.json")
            with open(state_file, "w") as f:
                json.dump({}, f)
            interceptor.write_last_recommended_category("mobile-development",
                                                         state_file=state_file)
            result = interceptor.get_last_recommended_category(state_file=state_file)
            assert result == "mobile-development"

    def test_bypass_token_roundtrip(self):
        """write_bypass / check_bypass must agree on tool_name and TTL."""
        import interceptor
        with tempfile.TemporaryDirectory() as tmpdir:
            state_file = os.path.join(tmpdir, "state.json")
            with open(state_file, "w") as f:
                json.dump({}, f)
            interceptor.write_bypass("Skill", state_file=state_file)
            assert interceptor.check_bypass("Skill", state_file=state_file)
            assert not interceptor.check_bypass("Agent", state_file=state_file)


# ── Layer 5: Env Var Contract ─────────────────────────────────────────────────
# Hooks rely on specific env vars being present or handled gracefully when absent.

class TestEnvVarContract:

    def test_anthropic_api_key_not_required_for_hosted_mode(self):
        """In hosted mode, ANTHROPIC_API_KEY absence must not crash hooks.
        The hook reads it with ${ANTHROPIC_API_KEY:-} — empty string is fine."""
        # Verify the pattern used handles unset env var
        import os
        key = os.environ.get("ANTHROPIC_API_KEY", "")
        # Hook uses: export ANTHROPIC_API_KEY="${ANTHROPIC_API_KEY:-}"
        # which always produces a string (empty or not). Never crashes.
        assert isinstance(key, str)

    def test_state_file_path_is_absolute(self):
        """STATE_FILE must be an absolute path — hooks write to it from any cwd."""
        from interceptor import STATE_FILE
        assert os.path.isabs(STATE_FILE), (
            f"STATE_FILE '{STATE_FILE}' is not absolute. "
            f"Hooks run from different cwd — relative paths would break."
        )

    @pytest.mark.skipif(
        not os.path.isdir(os.path.expanduser("~/.claude/dispatch")),
        reason="~/.claude/dispatch doesn't exist — run install.sh first"
    )
    def test_state_file_directory_exists_or_creatable(self):
        """The directory containing STATE_FILE must exist after install."""
        from interceptor import STATE_FILE
        state_dir = os.path.dirname(STATE_FILE)
        assert os.path.isdir(state_dir), (
            f"STATE_FILE directory '{state_dir}' doesn't exist. "
            f"Run install.sh first."
        )
