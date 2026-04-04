import os
import tempfile
import pytest

from xftc.checks.memory_audit_check import check_memory_audit, _memory_dir


# ── _memory_dir ──────────────────────────────────────────────────────────────

def test_memory_dir_encodes_path():
    result = _memory_dir('/home/user/MyProject')
    assert result.endswith('/.claude/projects/-home-user-MyProject/memory')


def test_memory_dir_root():
    result = _memory_dir('/foo')
    assert result.endswith('/.claude/projects/-foo/memory')


# ── check_memory_audit — no MEMORY.md ────────────────────────────────────────

def test_returns_none_when_no_memory_dir():
    result = check_memory_audit('/nonexistent/path/that/does/not/exist/ever')
    assert result is None


def test_returns_none_when_memory_md_missing(tmp_path):
    # Simulate the encoded memory dir existing but with no MEMORY.md
    cwd = str(tmp_path / 'project')
    encoded = cwd.replace('/', '-')
    memory_dir = tmp_path / '.claude' / 'projects' / encoded / 'memory'
    memory_dir.mkdir(parents=True)
    # No MEMORY.md written
    result = check_memory_audit(cwd)
    assert result is None


# ── check_memory_audit — clean MEMORY.md ─────────────────────────────────────

def _make_memory(tmp_path, cwd_name, content):
    """Create a MEMORY.md at the expected path for cwd."""
    cwd = str(tmp_path / cwd_name)
    encoded = cwd.replace('/', '-')
    home = str(tmp_path)
    memory_dir = tmp_path / '.claude' / 'projects' / encoded / 'memory'
    memory_dir.mkdir(parents=True)
    (memory_dir / 'MEMORY.md').write_text(content, encoding='utf-8')
    return cwd, memory_dir


def _patch_home(monkeypatch, tmp_path):
    monkeypatch.setenv('HOME', str(tmp_path))


def test_returns_none_when_all_links_valid(tmp_path, monkeypatch):
    _patch_home(monkeypatch, tmp_path)
    cwd, memory_dir = _make_memory(tmp_path, 'proj', '# Memory\n\n- [User](user.md) — details\n')
    (memory_dir / 'user.md').write_text('exists', encoding='utf-8')
    result = check_memory_audit(cwd)
    assert result is None


def test_returns_none_when_no_links(tmp_path, monkeypatch):
    _patch_home(monkeypatch, tmp_path)
    cwd, _ = _make_memory(tmp_path, 'proj', '# Memory\n\nNo links here, just text.\n')
    result = check_memory_audit(cwd)
    assert result is None


def test_returns_none_for_external_links(tmp_path, monkeypatch):
    _patch_home(monkeypatch, tmp_path)
    content = '- [Dispatch](https://dispatch.visionairy.biz)\n- [Anchor](#section)\n'
    cwd, _ = _make_memory(tmp_path, 'proj', content)
    result = check_memory_audit(cwd)
    assert result is None


# ── check_memory_audit — broken links ────────────────────────────────────────

def test_detects_single_broken_link(tmp_path, monkeypatch):
    _patch_home(monkeypatch, tmp_path)
    cwd, memory_dir = _make_memory(tmp_path, 'proj', '- [Missing](missing.md)\n')
    result = check_memory_audit(cwd)
    assert result is not None
    assert result['count'] == 1
    assert result['broken'][0]['title'] == 'Missing'
    assert result['broken'][0]['path'] == 'missing.md'


def test_detects_multiple_broken_links(tmp_path, monkeypatch):
    _patch_home(monkeypatch, tmp_path)
    content = '- [A](a.md)\n- [B](b.md)\n- [C](c.md)\n'
    cwd, _ = _make_memory(tmp_path, 'proj', content)
    result = check_memory_audit(cwd)
    assert result is not None
    assert result['count'] == 3
    paths = [b['path'] for b in result['broken']]
    assert set(paths) == {'a.md', 'b.md', 'c.md'}


def test_mixed_valid_and_broken(tmp_path, monkeypatch):
    _patch_home(monkeypatch, tmp_path)
    content = '- [Good](good.md)\n- [Bad](bad.md)\n'
    cwd, memory_dir = _make_memory(tmp_path, 'proj', content)
    (memory_dir / 'good.md').write_text('exists', encoding='utf-8')
    result = check_memory_audit(cwd)
    assert result is not None
    assert result['count'] == 1
    assert result['broken'][0]['path'] == 'bad.md'


def test_returns_memory_md_path(tmp_path, monkeypatch):
    _patch_home(monkeypatch, tmp_path)
    cwd, memory_dir = _make_memory(tmp_path, 'proj', '- [X](x.md)\n')
    result = check_memory_audit(cwd)
    assert result['memory_md'] == str(memory_dir / 'MEMORY.md')
    assert result['memory_dir'] == str(memory_dir)


def test_external_links_not_flagged_alongside_broken(tmp_path, monkeypatch):
    _patch_home(monkeypatch, tmp_path)
    content = '- [OK](https://example.com)\n- [Broken](gone.md)\n'
    cwd, _ = _make_memory(tmp_path, 'proj', content)
    result = check_memory_audit(cwd)
    assert result is not None
    assert result['count'] == 1
    assert result['broken'][0]['path'] == 'gone.md'


# ── line count / bloat checks ─────────────────────────────────────────────────

def test_returns_none_when_under_limit(tmp_path, monkeypatch):
    _patch_home(monkeypatch, tmp_path)
    content = '\n'.join([f'- line {i}' for i in range(50)])
    cwd, _ = _make_memory(tmp_path, 'proj', content)
    result = check_memory_audit(cwd)
    assert result is None


def test_flags_bloat_when_over_limit(tmp_path, monkeypatch):
    _patch_home(monkeypatch, tmp_path)
    content = '\n'.join([f'- line {i}' for i in range(200)])
    cwd, _ = _make_memory(tmp_path, 'proj', content)
    result = check_memory_audit(cwd)
    assert result is not None
    assert result['bloated'] is True
    assert result['line_count'] > 180


def test_bloat_result_has_no_broken_links(tmp_path, monkeypatch):
    _patch_home(monkeypatch, tmp_path)
    content = '\n'.join([f'- line {i}' for i in range(200)])
    cwd, _ = _make_memory(tmp_path, 'proj', content)
    result = check_memory_audit(cwd)
    assert result['count'] == 0
    assert result['broken'] == []


def test_broken_link_below_limit_still_reported(tmp_path, monkeypatch):
    _patch_home(monkeypatch, tmp_path)
    cwd, _ = _make_memory(tmp_path, 'proj', '- [Missing](gone.md)\n')
    result = check_memory_audit(cwd)
    assert result is not None
    assert result['bloated'] is False
    assert result['count'] == 1


def test_returns_none_when_all_links_present(tmp_path, monkeypatch):
    _patch_home(monkeypatch, tmp_path)
    content = '- [One](one.md)\n- [Two](two.md)\n'
    cwd, memory_dir = _make_memory(tmp_path, 'proj', content)
    (memory_dir / 'one.md').write_text('x', encoding='utf-8')
    (memory_dir / 'two.md').write_text('x', encoding='utf-8')
    result = check_memory_audit(cwd)
    assert result is None
