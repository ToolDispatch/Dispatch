import os
import pytest


class TestClaudeMdCheck:
    def test_no_claude_md_returns_none(self, tmp_path):
        from xftc.checks.claude_md_check import check_claude_md
        assert check_claude_md(str(tmp_path)) is None

    def test_short_claude_md_returns_none(self, tmp_path):
        from xftc.checks.claude_md_check import check_claude_md
        (tmp_path / "CLAUDE.md").write_text("# Short\n" * 50)
        assert check_claude_md(str(tmp_path)) is None

    def test_long_claude_md_returns_tuple(self, tmp_path):
        from xftc.checks.claude_md_check import check_claude_md
        (tmp_path / "CLAUDE.md").write_text("line\n" * 300)
        result = check_claude_md(str(tmp_path))
        assert result is not None
        project_lines, _ = result
        assert project_lines == 300

    def test_count_claude_md_lines_project_only(self, tmp_path):
        from xftc.checks.claude_md_check import count_claude_md_lines
        (tmp_path / "CLAUDE.md").write_text("a\n" * 150)
        project_lines, global_lines = count_claude_md_lines(str(tmp_path))
        assert project_lines == 150

    def test_exactly_200_lines_returns_none(self, tmp_path, monkeypatch):
        from xftc.checks.claude_md_check import check_claude_md
        (tmp_path / "CLAUDE.md").write_text("line\n" * 200)
        # Patch global CLAUDE.md to empty so only project lines count
        monkeypatch.setenv("HOME", str(tmp_path))
        assert check_claude_md(str(tmp_path)) is None

    def test_201_lines_returns_result(self, tmp_path):
        from xftc.checks.claude_md_check import check_claude_md
        (tmp_path / "CLAUDE.md").write_text("line\n" * 201)
        assert check_claude_md(str(tmp_path)) is not None
