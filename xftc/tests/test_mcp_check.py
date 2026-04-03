import json
import os
import tempfile
import pytest
from unittest.mock import patch


def make_mcp_json(servers: dict) -> str:
    """Write a .mcp.json to a temp dir and return dir path."""
    d = tempfile.mkdtemp()
    with open(os.path.join(d, ".mcp.json"), "w") as f:
        json.dump({"mcpServers": servers}, f)
    return d


class TestMcpCheck:
    def test_no_mcp_files_returns_none(self, tmp_path):
        from xftc.checks.mcp_check import check_mcp_overhead
        result = check_mcp_overhead(str(tmp_path))
        assert result is None

    def test_one_server_below_threshold_returns_none(self, tmp_path):
        mcp = {"mcpServers": {"server1": {}}}
        (tmp_path / ".mcp.json").write_text(json.dumps(mcp))
        from xftc.checks.mcp_check import check_mcp_overhead
        # 1 server × 18000 = 18000 < 30000 threshold
        result = check_mcp_overhead(str(tmp_path))
        assert result is None

    def test_two_servers_above_threshold_returns_tuple(self, tmp_path):
        mcp = {"mcpServers": {"s1": {}, "s2": {}}}
        (tmp_path / ".mcp.json").write_text(json.dumps(mcp))
        from xftc.checks.mcp_check import check_mcp_overhead
        # 2 × 18000 = 36000 >= 30000
        result = check_mcp_overhead(str(tmp_path))
        assert result == (2, 36000)

    def test_malformed_mcp_json_returns_none(self, tmp_path):
        (tmp_path / ".mcp.json").write_text("not json{{{")
        from xftc.checks.mcp_check import check_mcp_overhead
        result = check_mcp_overhead(str(tmp_path))
        assert result is None

    def test_count_mcp_servers_counts_correctly(self, tmp_path):
        mcp = {"mcpServers": {"a": {}, "b": {}, "c": {}}}
        (tmp_path / ".mcp.json").write_text(json.dumps(mcp))
        from xftc.checks.mcp_check import count_mcp_servers
        count = count_mcp_servers(str(tmp_path))
        assert count == 3

    def test_empty_mcp_servers_dict_returns_none(self, tmp_path):
        mcp = {"mcpServers": {}}
        (tmp_path / ".mcp.json").write_text(json.dumps(mcp))
        from xftc.checks.mcp_check import check_mcp_overhead
        result = check_mcp_overhead(str(tmp_path))
        assert result is None
