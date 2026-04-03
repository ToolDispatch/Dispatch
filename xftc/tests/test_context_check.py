import os
import tempfile
import pytest


class TestContextCheck:
    def test_zero_messages_empty_dir_returns_low_fill(self, tmp_path):
        from xftc.checks.context_check import estimate_context_fill
        fill = estimate_context_fill(0, str(tmp_path))
        assert fill < 0.10

    def test_many_messages_returns_higher_fill(self, tmp_path):
        from xftc.checks.context_check import estimate_context_fill
        fill_low = estimate_context_fill(5, str(tmp_path))
        fill_high = estimate_context_fill(50, str(tmp_path))
        assert fill_high > fill_low

    def test_large_claude_md_increases_fill(self, tmp_path):
        from xftc.checks.context_check import estimate_context_fill
        fill_without = estimate_context_fill(10, str(tmp_path))
        (tmp_path / "CLAUDE.md").write_text("\n" * 500)
        fill_with = estimate_context_fill(10, str(tmp_path))
        assert fill_with > fill_without

    def test_fill_capped_at_1(self, tmp_path):
        from xftc.checks.context_check import estimate_context_fill
        fill = estimate_context_fill(10000, str(tmp_path))
        assert fill <= 1.0

    def test_should_compact_returns_none_below_threshold(self, tmp_path):
        from xftc.checks.context_check import should_compact
        result = should_compact(2, str(tmp_path))
        assert result is None

    def test_should_compact_returns_fill_above_threshold(self, tmp_path):
        from xftc.checks.context_check import should_compact
        # 200 messages should push well over 60%
        result = should_compact(200, str(tmp_path))
        assert result is not None
        assert result >= 0.60
