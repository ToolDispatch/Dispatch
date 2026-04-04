import os
import pytest
from unittest.mock import patch


class TestSkillsCheck:

    def _make_skills_dir(self, tmp_path, skills: dict) -> str:
        """Create a fake skills dir. skills = {name: skill_md_bytes}"""
        skills_dir = tmp_path / "skills"
        skills_dir.mkdir()
        for name, size in skills.items():
            skill_dir = skills_dir / name
            skill_dir.mkdir()
            (skill_dir / "SKILL.md").write_bytes(b"x" * size)
        return str(skills_dir)

    def test_no_skills_dir_returns_none(self, tmp_path):
        from xftc.checks.skills_check import check_skills
        with patch("xftc.checks.skills_check._get_skills_dir",
                   return_value=str(tmp_path / "nonexistent")):
            assert check_skills() is None

    def test_empty_skills_dir_returns_none(self, tmp_path):
        from xftc.checks.skills_check import check_skills
        skills_dir = self._make_skills_dir(tmp_path, {})
        with patch("xftc.checks.skills_check._get_skills_dir", return_value=skills_dir):
            assert check_skills() is None

    def test_few_small_skills_returns_none(self, tmp_path):
        from xftc.checks.skills_check import check_skills
        # 5 skills, 10KB each = 50KB total — under both limits
        skills = {f"skill_{i}": 10 * 1024 for i in range(5)}
        skills_dir = self._make_skills_dir(tmp_path, skills)
        with patch("xftc.checks.skills_check._get_skills_dir", return_value=skills_dir):
            assert check_skills() is None

    def test_too_many_skills_triggers(self, tmp_path):
        from xftc.checks.skills_check import check_skills, SKILLS_COUNT_LIMIT
        # Over count limit
        skills = {f"skill_{i}": 1024 for i in range(SKILLS_COUNT_LIMIT + 1)}
        skills_dir = self._make_skills_dir(tmp_path, skills)
        with patch("xftc.checks.skills_check._get_skills_dir", return_value=skills_dir):
            result = check_skills()
            assert result is not None
            assert result["count"] == SKILLS_COUNT_LIMIT + 1

    def test_large_total_size_triggers(self, tmp_path):
        from xftc.checks.skills_check import check_skills, SKILLS_SIZE_LIMIT_KB
        # 4 skills each slightly over a quarter of the limit → total clearly over
        size_each = (SKILLS_SIZE_LIMIT_KB * 1024) // 3
        skills = {f"skill_{i}": size_each for i in range(4)}
        skills_dir = self._make_skills_dir(tmp_path, skills)
        with patch("xftc.checks.skills_check._get_skills_dir", return_value=skills_dir):
            result = check_skills()
            assert result is not None
            assert result["total_kb"] > SKILLS_SIZE_LIMIT_KB

    def test_result_includes_top_heavy(self, tmp_path):
        from xftc.checks.skills_check import check_skills, SKILLS_COUNT_LIMIT
        skills = {f"skill_{i:02d}": (i + 1) * 5 * 1024 for i in range(SKILLS_COUNT_LIMIT + 2)}
        skills_dir = self._make_skills_dir(tmp_path, skills)
        with patch("xftc.checks.skills_check._get_skills_dir", return_value=skills_dir):
            result = check_skills()
            assert result is not None
            assert "top_heavy" in result
            assert len(result["top_heavy"]) <= 5
            # Should be sorted largest first
            sizes = [kb for _, kb in result["top_heavy"]]
            assert sizes == sorted(sizes, reverse=True)

    def test_result_count_and_total_kb(self, tmp_path):
        from xftc.checks.skills_check import check_skills, SKILLS_COUNT_LIMIT
        n = SKILLS_COUNT_LIMIT + 1
        skills = {f"skill_{i}": 2048 for i in range(n)}
        skills_dir = self._make_skills_dir(tmp_path, skills)
        with patch("xftc.checks.skills_check._get_skills_dir", return_value=skills_dir):
            result = check_skills()
            assert result["count"] == n
            assert result["total_kb"] == (n * 2048) // 1024

    def test_skills_without_skill_md_counted_with_zero_size(self, tmp_path):
        from xftc.checks.skills_check import check_skills, SKILLS_COUNT_LIMIT
        # Skills with no SKILL.md still count toward the count limit
        skills_dir = tmp_path / "skills"
        skills_dir.mkdir()
        for i in range(SKILLS_COUNT_LIMIT + 1):
            (skills_dir / f"skill_{i}").mkdir()
        with patch("xftc.checks.skills_check._get_skills_dir", return_value=str(skills_dir)):
            result = check_skills()
            assert result is not None
            assert result["count"] == SKILLS_COUNT_LIMIT + 1
