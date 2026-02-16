"""Tests for Letta MCP tools that invoke the actual tool handlers.

Each test captures the SdkMcpTool objects created by create_letta_mcp_server,
invokes their .handler() with test arguments, and verifies both:
1. The MCP response format ({"content": [{"type": "text", "text": ...}]})
2. That the underlying AsyncLetta mock was called with correct arguments
"""

from typing import Any
from unittest.mock import AsyncMock, patch

import pytest

from tests.conftest import capture_tools, make_block_response, make_passage


class TestCreateServer:
    """Tests for create_letta_mcp_server function."""

    def test_requires_agent_id(self) -> None:
        """Raises ValueError when no agent_id is provided or configured."""
        from nameless.core.tools import create_letta_mcp_server

        mock_client = AsyncMock()

        with patch("nameless.core.tools.get_settings") as mock_settings:
            mock_settings.return_value.agent.agent_id = None
            with pytest.raises(ValueError, match="No agent_id provided"):
                create_letta_mcp_server(letta_client=mock_client)

    def test_creates_six_tools(self, tool_map: dict[str, Any]) -> None:
        """Server should register exactly 6 tools."""
        expected_names = {
            "get_memory_block",
            "update_memory_block",
            "search_archival_memory",
            "insert_archival_memory",
            "list_memory_blocks",
            "get_recent_messages",
        }
        assert set(tool_map.keys()) == expected_names


class TestGetMemoryBlock:
    """Tests for the get_memory_block tool handler."""

    @pytest.mark.asyncio
    async def test_returns_block_value(self, mock_letta: AsyncMock) -> None:
        """Handler returns the block's value as text content."""
        mock_letta.agents.blocks.retrieve.return_value = make_block_response(
            label="persona", value="I am Nameless, exploring identity."
        )
        tools = capture_tools(mock_letta)

        result = await tools["get_memory_block"].handler({"block_name": "persona"})

        assert result == {"content": [{"type": "text", "text": "I am Nameless, exploring identity."}]}

    @pytest.mark.asyncio
    async def test_empty_value_returns_empty_string(self, mock_letta: AsyncMock) -> None:
        """Handler returns empty string when block value is empty."""
        mock_letta.agents.blocks.retrieve.return_value = make_block_response(
            label="persona", value=""
        )
        tools = capture_tools(mock_letta)

        result = await tools["get_memory_block"].handler({"block_name": "persona"})

        assert result["content"][0]["text"] == ""

    @pytest.mark.asyncio
    async def test_calls_retrieve_correctly(self, mock_letta: AsyncMock) -> None:
        """Handler passes block_name and agent_id to Letta retrieve."""
        tools = capture_tools(mock_letta, agent_id="agent-abc")

        await tools["get_memory_block"].handler({"block_name": "human"})

        mock_letta.agents.blocks.retrieve.assert_awaited_once_with("human", agent_id="agent-abc")


class TestUpdateMemoryBlock:
    """Tests for the update_memory_block tool handler."""

    @pytest.mark.asyncio
    async def test_returns_confirmation(self, mock_letta: AsyncMock) -> None:
        """Handler returns a confirmation message with the block name."""
        tools = capture_tools(mock_letta)

        result = await tools["update_memory_block"].handler({"block_name": "persona", "value": "New value"})

        assert result == {"content": [{"type": "text", "text": "Updated memory block 'persona'"}]}

    @pytest.mark.asyncio
    async def test_calls_update_correctly(self, mock_letta: AsyncMock) -> None:
        """Handler passes block_name, agent_id, and value to Letta update."""
        tools = capture_tools(mock_letta, agent_id="agent-xyz")

        await tools["update_memory_block"].handler({"block_name": "human", "value": "Jake likes coffee"})

        mock_letta.agents.blocks.update.assert_awaited_once_with(
            "human", agent_id="agent-xyz", value="Jake likes coffee"
        )


class TestSearchArchivalMemory:
    """Tests for the search_archival_memory tool handler.

    The tool tries semantic search first (agents.passages.search), then
    falls back to text-based search (agents.passages.list) on older servers.
    """

    @pytest.mark.asyncio
    async def test_uses_semantic_search_when_available(self, mock_letta: AsyncMock) -> None:
        """Handler uses passages.search (semantic) when the endpoint exists."""
        # Set up semantic search to succeed
        search_result = AsyncMock()
        search_result.results = [
            AsyncMock(content="Semantic result 1", id="s1"),
            AsyncMock(content="Semantic result 2", id="s2"),
        ]
        mock_letta.agents.passages.search.return_value = search_result
        tools = capture_tools(mock_letta, agent_id="agent-semantic")

        result = await tools["search_archival_memory"].handler({"query": "identity", "count": 3})

        text = result["content"][0]["text"]
        assert "Semantic result 1" in text
        assert "Semantic result 2" in text
        mock_letta.agents.passages.search.assert_awaited_once_with(
            "agent-semantic", query="identity", top_k=3,
        )
        # Text-based fallback should NOT have been called
        mock_letta.agents.passages.list.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_falls_back_to_text_search(self, mock_letta: AsyncMock) -> None:
        """Handler falls back to passages.list (text) when semantic search fails."""
        # Make semantic search fail (e.g. server doesn't support it)
        mock_letta.agents.passages.search.side_effect = Exception("405 Method Not Allowed")
        mock_letta.agents.passages.list.return_value = [
            make_passage(passage_id="p1", text="First memory"),
            make_passage(passage_id="p2", text="Second memory"),
        ]
        tools = capture_tools(mock_letta)

        result = await tools["search_archival_memory"].handler({"query": "memories", "count": 5})

        text = result["content"][0]["text"]
        assert "First memory" in text
        assert "Second memory" in text

    @pytest.mark.asyncio
    async def test_default_count_is_10(self, mock_letta: AsyncMock) -> None:
        """Handler defaults to top_k/limit=10 when count not provided."""
        mock_letta.agents.passages.search.side_effect = Exception("not available")
        tools = capture_tools(mock_letta, agent_id="agent-def")

        await tools["search_archival_memory"].handler({"query": "test"})

        mock_letta.agents.passages.list.assert_awaited_once_with("agent-def", search="test", limit=10)

    @pytest.mark.asyncio
    async def test_text_fallback_calls_list_correctly(self, mock_letta: AsyncMock) -> None:
        """Fallback passes agent_id, search query, and limit to passages.list."""
        mock_letta.agents.passages.search.side_effect = Exception("not available")
        tools = capture_tools(mock_letta, agent_id="agent-search")

        await tools["search_archival_memory"].handler({"query": "identity", "count": 3})

        mock_letta.agents.passages.list.assert_awaited_once_with("agent-search", search="identity", limit=3)


class TestInsertArchivalMemory:
    """Tests for the insert_archival_memory tool handler."""

    @pytest.mark.asyncio
    async def test_returns_success_message(self, mock_letta: AsyncMock) -> None:
        """Handler returns a success confirmation."""
        tools = capture_tools(mock_letta)

        result = await tools["insert_archival_memory"].handler({"text": "A new insight"})

        assert result == {"content": [{"type": "text", "text": "Memory archived successfully"}]}

    @pytest.mark.asyncio
    async def test_calls_archive_create_correctly(self, mock_letta: AsyncMock) -> None:
        """Handler uses archives.passages.create when archive_id is resolvable."""
        tools = capture_tools(mock_letta, agent_id="agent-ins")

        await tools["insert_archival_memory"].handler({"text": "Something to remember"})

        # Should use archives path (archive_id resolved from mock passage)
        mock_letta.archives.passages.create.assert_awaited_once_with(
            "archive-001", text="Something to remember"
        )


class TestListMemoryBlocks:
    """Tests for the list_memory_blocks tool handler."""

    @pytest.mark.asyncio
    async def test_returns_block_summaries(self, mock_letta: AsyncMock) -> None:
        """Handler returns label and value_length for each block."""
        mock_letta.agents.blocks.list.return_value = [
            make_block_response(label="persona", value="Short"),
            make_block_response(label="human", value="A longer description here"),
        ]
        tools = capture_tools(mock_letta)

        result = await tools["list_memory_blocks"].handler({})

        text = result["content"][0]["text"]
        assert "persona" in text
        assert "human" in text

    @pytest.mark.asyncio
    async def test_includes_value_lengths(self, mock_letta: AsyncMock) -> None:
        """Handler includes the character count of each block's value."""
        mock_letta.agents.blocks.list.return_value = [
            make_block_response(label="test", value="12345"),
        ]
        tools = capture_tools(mock_letta)

        result = await tools["list_memory_blocks"].handler({})

        text = result["content"][0]["text"]
        assert "'value_length': 5" in text or '"value_length": 5' in text

    @pytest.mark.asyncio
    async def test_calls_list_correctly(self, mock_letta: AsyncMock) -> None:
        """Handler passes agent_id to Letta blocks.list."""
        tools = capture_tools(mock_letta, agent_id="agent-list")

        await tools["list_memory_blocks"].handler({})

        mock_letta.agents.blocks.list.assert_awaited_once_with("agent-list")


class TestGetRecentMessages:
    """Tests for the get_recent_messages tool handler."""

    @pytest.mark.asyncio
    async def test_returns_formatted_messages(self, mock_letta: AsyncMock) -> None:
        """Handler returns messages with type, content, and date fields."""
        tools = capture_tools(mock_letta)

        result = await tools["get_recent_messages"].handler({"count": 5})

        text = result["content"][0]["text"]
        assert "UserMessage" in text
        assert "AssistantMessage" in text
        assert "Hello Nameless!" in text

    @pytest.mark.asyncio
    async def test_truncates_long_content(self, mock_letta: AsyncMock) -> None:
        """Handler truncates message content to 500 characters."""
        from tests.conftest import make_assistant_message

        long_content = "x" * 1000
        mock_letta.agents.messages.list.return_value = [
            make_assistant_message(content=long_content),
        ]
        tools = capture_tools(mock_letta)

        result = await tools["get_recent_messages"].handler({"count": 1})

        text = result["content"][0]["text"]
        # The content field within the formatted dict should be truncated to 500 chars
        # str(m.content)[:500] means the content string is at most 500 chars
        assert len(long_content[:500]) == 500
        assert ("x" * 501) not in text

    @pytest.mark.asyncio
    async def test_default_count_is_10(self, mock_letta: AsyncMock) -> None:
        """Handler defaults to limit=10 when count not provided."""
        tools = capture_tools(mock_letta, agent_id="agent-msg")

        await tools["get_recent_messages"].handler({})

        mock_letta.agents.messages.list.assert_awaited_once_with("agent-msg", limit=10)
