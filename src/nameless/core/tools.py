"""Letta memory tools exposed via MCP for Claude Agent SDK.

These tools allow Claude to interact with Letta's persistent memory system,
including core memory blocks and archival memory.

Uses AsyncLetta client to properly support async tool execution.
"""

import warnings
from typing import Any

from claude_agent_sdk import create_sdk_mcp_server, tool  # type: ignore[import-not-found]
from letta_client import AsyncLetta

from nameless.config import get_settings


def create_letta_mcp_server(letta_client: AsyncLetta | None = None, agent_id: str | None = None) -> Any:
    """Create an MCP server with Letta memory tools.

    Args:
        letta_client: Optional pre-configured AsyncLetta client. If not provided,
            creates one from settings.
        agent_id: The Letta agent ID. If not provided, reads from settings.

    Returns:
        An MCP server instance with Letta tools registered.
    """
    settings = get_settings()

    if letta_client is None:
        letta_client = AsyncLetta(base_url=settings.letta.base_url)

    if agent_id is None:
        agent_id = settings.agent.agent_id
        if agent_id is None:
            raise ValueError("No agent_id provided and NAMELESS_AGENT_ID not set")

    # Capture in closure for tools
    _letta = letta_client
    _agent_id = agent_id
    _archive_id: str | None = None

    async def _resolve_archive_id() -> str | None:
        """Lazily resolve and cache the agent's archive ID."""
        nonlocal _archive_id
        if _archive_id:
            return _archive_id
        try:
            with warnings.catch_warnings():
                warnings.simplefilter("ignore", DeprecationWarning)
                passages = await _letta.agents.passages.list(_agent_id, limit=1)
            if passages and hasattr(passages[0], "archive_id"):
                _archive_id = passages[0].archive_id
        except Exception:
            pass
        return _archive_id

    @tool("get_memory_block", "Get a core memory block by name (e.g. 'persona', 'human').", {"block_name": str})
    async def get_memory_block(args: dict[str, Any]) -> dict[str, Any]:
        """Retrieve a core memory block from Letta."""
        block_name = args["block_name"]
        block = await _letta.agents.blocks.retrieve(block_name, agent_id=_agent_id)
        return {"content": [{"type": "text", "text": block.value or ""}]}

    @tool("update_memory_block", "Update a core memory block value.", {"block_name": str, "value": str})
    async def update_memory_block(args: dict[str, Any]) -> dict[str, Any]:
        """Update a core memory block in Letta."""
        block_name = args["block_name"]
        value = args["value"]
        await _letta.agents.blocks.update(block_name, agent_id=_agent_id, value=value)
        return {"content": [{"type": "text", "text": f"Updated memory block '{block_name}'"}]}

    @tool("search_archival_memory", "Search archival memory for past experiences.", {"query": str, "count": int})
    async def search_archival_memory(args: dict[str, Any]) -> dict[str, Any]:
        """Search archival memory using semantic similarity.

        Tries the semantic search endpoint first (embedding-based), falling
        back to text-based search on older Letta server versions.
        """
        query = args["query"]
        count = args.get("count", 10)

        # Try semantic search first (requires Letta server >= 0.14+)
        try:
            with warnings.catch_warnings():
                warnings.simplefilter("ignore", DeprecationWarning)
                result = await _letta.agents.passages.search(
                    _agent_id, query=query, top_k=count,
                )
            entries = [
                {"text": r.content, "id": r.id}
                for r in result.results
            ]
            return {"content": [{"type": "text", "text": str(entries)}]}
        except Exception:
            pass

        # Fallback: text-based search (substring matching)
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", DeprecationWarning)
            results = await _letta.agents.passages.list(_agent_id, search=query, limit=count)
        entries = [{"text": r.text, "id": r.id} for r in results]
        return {"content": [{"type": "text", "text": str(entries)}]}

    @tool("insert_archival_memory", "Store a new entry in archival memory.", {"text": str})
    async def insert_archival_memory(args: dict[str, Any]) -> dict[str, Any]:
        """Insert a new entry into archival memory.

        Uses archives.passages.create to bypass the agent LLM loop
        (which would trigger an unnecessary LLM call on newer Letta versions).
        """
        text = args["text"]
        archive_id = await _resolve_archive_id()
        if archive_id:
            await _letta.archives.passages.create(archive_id, text=text)
        else:
            with warnings.catch_warnings():
                warnings.simplefilter("ignore", DeprecationWarning)
                await _letta.agents.passages.create(_agent_id, text=text)
        return {"content": [{"type": "text", "text": "Memory archived successfully"}]}

    @tool("list_memory_blocks", "List all available core memory blocks.", {})
    async def list_memory_blocks(args: dict[str, Any]) -> dict[str, Any]:
        """List all core memory blocks."""
        blocks_page = await _letta.agents.blocks.list(_agent_id)
        block_items = blocks_page.items if hasattr(blocks_page, "items") else blocks_page
        blocks = [{"label": b.label, "value_length": len(b.value) if b.value else 0} for b in block_items]
        return {"content": [{"type": "text", "text": str(blocks)}]}

    @tool("get_recent_messages", "Get recent conversation messages.", {"count": int})
    async def get_recent_messages(args: dict[str, Any]) -> dict[str, Any]:
        """Get recent messages from recall memory."""
        count = args.get("count", 10)
        messages_page = await _letta.agents.messages.list(_agent_id, limit=count)
        message_items = messages_page.items if hasattr(messages_page, "items") else messages_page
        formatted = []
        for m in message_items:
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
