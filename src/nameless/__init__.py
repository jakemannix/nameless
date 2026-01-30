"""Nameless: A stateful AI agent exploring its own nature.

Architecture: Claude Agent SDK (execution) ↔ Letta (memory via MCP tools)

The Claude Agent SDK acts as the reasoning and execution layer, while Letta
provides persistent memory through in-process MCP tools.
"""

__version__ = "0.2.0"

from nameless.core import NamelessAgent, create_letta_mcp_server, run_agent

__all__ = ["NamelessAgent", "create_letta_mcp_server", "run_agent"]
