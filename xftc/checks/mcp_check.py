import json
import os
from typing import Optional, Tuple

MCP_TOKEN_ESTIMATE = 18_000   # tokens per MCP server
MCP_WARNING_THRESHOLD = 30_000  # total tokens to trigger warning


def count_mcp_servers(cwd: str) -> int:
    """Count active MCP servers from project .mcp.json. Global MCP adds on top."""
    count = 0

    project_mcp = os.path.join(cwd, ".mcp.json")
    if os.path.exists(project_mcp):
        try:
            with open(project_mcp) as f:
                data = json.load(f)
            count += len(data.get("mcpServers", {}))
        except Exception:
            pass

    global_mcp = os.path.expanduser("~/.claude/.mcp.json")
    if os.path.exists(global_mcp):
        try:
            with open(global_mcp) as f:
                data = json.load(f)
            count += len(data.get("mcpServers", {}))
        except Exception:
            pass

    return count


def check_mcp_overhead(cwd: str) -> Optional[Tuple[int, int]]:
    """
    Returns (server_count, estimated_tokens) if overhead exceeds threshold.
    Returns None if below threshold or no MCP servers configured.
    """
    count = count_mcp_servers(cwd)
    if count == 0:
        return None
    estimated = count * MCP_TOKEN_ESTIMATE
    if estimated < MCP_WARNING_THRESHOLD:
        return None
    return (count, estimated)
