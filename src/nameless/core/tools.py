"""Letta memory tools exposed via MCP for Claude Agent SDK.

These tools allow Claude to interact with Letta's persistent memory system,
including core memory blocks and archival memory.
"""

from typing import Any

from claude_agent_sdk import create_sdk_mcp_server, tool  # type: ignore[import-not-found]
from letta_client import Letta

from nameless.config import get_settings


def create_letta_mcp_server(letta_client: Letta | None = None, agent_id: str | None = None) -> Any:
    """Create an MCP server with Letta memory tools.

    Args:
        letta_client: Optional pre-configured Letta client. If not provided,
            creates one from settings.
        agent_id: The Letta agent ID. If not provided, reads from settings.

    Returns:
        An MCP server instance with Letta tools registered.
    """
    settings = get_settings()

    if letta_client is None:
        letta_client = Letta(base_url=settings.letta.base_url)

    if agent_id is None:
        agent_id = settings.agent.agent_id
        if agent_id is None:
            raise ValueError("No agent_id provided and NAMELESS_AGENT_ID not set")

    # Capture in closure for tools
    _letta = letta_client
    _agent_id = agent_id

    @tool("get_memory_block", "Get a core memory block by name (e.g. 'persona', 'human').", {"block_name": str})
    async def get_memory_block(args: dict[str, Any]) -> dict[str, Any]:
        """Retrieve a core memory block from Letta."""
        block_name = args["block_name"]
        block = _letta.agents.blocks.retrieve(block_name, agent_id=_agent_id)
        return {"content": [{"type": "text", "text": block.value or ""}]}

    @tool("update_memory_block", "Update a core memory block value.", {"block_name": str, "value": str})
    async def update_memory_block(args: dict[str, Any]) -> dict[str, Any]:
        """Update a core memory block in Letta."""
        block_name = args["block_name"]
        value = args["value"]
        _letta.agents.blocks.update(block_name, agent_id=_agent_id, value=value)
        return {"content": [{"type": "text", "text": f"Updated memory block '{block_name}'"}]}

    @tool("search_archival_memory", "Search archival memory for past experiences.", {"query": str, "count": int})
    async def search_archival_memory(args: dict[str, Any]) -> dict[str, Any]:
        """Search archival memory using semantic similarity."""
        query = args["query"]
        count = args.get("count", 10)
        results = _letta.agents.passages.search(_agent_id, query=query, top_k=count)
        entries = [{"text": r.passage.text, "score": r.score} for r in results]
        return {"content": [{"type": "text", "text": str(entries)}]}

    @tool("insert_archival_memory", "Store a new entry in archival memory.", {"text": str})
    async def insert_archival_memory(args: dict[str, Any]) -> dict[str, Any]:
        """Insert a new entry into archival memory."""
        text = args["text"]
        _letta.agents.passages.create(_agent_id, text=text)
        return {"content": [{"type": "text", "text": "Memory archived successfully"}]}

    @tool("list_memory_blocks", "List all available core memory blocks.", {})
    async def list_memory_blocks(args: dict[str, Any]) -> dict[str, Any]:
        """List all core memory blocks."""
        blocks_list = _letta.agents.blocks.list(_agent_id)
        blocks = [{"label": b.label, "value_length": len(b.value) if b.value else 0} for b in blocks_list]
        return {"content": [{"type": "text", "text": str(blocks)}]}

    @tool("get_recent_messages", "Get recent conversation messages.", {"count": int})
    async def get_recent_messages(args: dict[str, Any]) -> dict[str, Any]:
        """Get recent messages from recall memory."""
        count = args.get("count", 10)
        messages = _letta.agents.messages.list(_agent_id, limit=count)
        formatted = []
        for m in messages:
            entry = {"type": type(m).__name__}
            if hasattr(m, "content"):
                entry["content"] = str(m.content)[:500]
            if hasattr(m, "date"):
                entry["date"] = str(m.date)
            formatted.append(entry)
        return {"content": [{"type": "text", "text": str(formatted)}]}

    # Create the MCP server with all tools
    return create_sdk_mcp_server(
        name="letta",
        tools=[
            get_memory_block,
            update_memory_block,
            search_archival_memory,
            insert_archival_memory,
            list_memory_blocks,
            get_recent_messages,
        ],
    )
