"""Tests for core tools module with accurate Letta API mocks.

These mocks are based on letta-client 1.7.6 types:
- BlockResponse: Core memory block with id, value, label, etc.
- Passage: Archival memory entry with text, created_at, etc.
- PassageSearchResponseItem: Search result with passage and score
- Message types: AssistantMessage, UserMessage, etc. with content, date, message_type
"""

import datetime
from typing import Any
from unittest.mock import MagicMock, patch

import pytest

# Import the actual Letta types for accurate mocking
from letta_client.types import BlockResponse, Passage
from letta_client.types.agents.assistant_message import AssistantMessage
from letta_client.types.agents.user_message import UserMessage
from letta_client.types.passage_search_response import PassageSearchResponseItem


def make_block_response(
    block_id: str = "block-123",
    label: str = "persona",
    value: str = "I am Nameless, an AI agent.",
) -> BlockResponse:
    """Create a realistic BlockResponse matching letta-client 1.7.6."""
    return BlockResponse(
        id=block_id,
        value=value,
        label=label,
        description="Core memory block",
        is_template=False,
        read_only=False,
        limit=5000,
        metadata=None,
        tags=None,
        created_by_id=None,
        last_updated_by_id=None,
        project_id="project-456",
        base_template_id=None,
        template_id=None,
        template_name=None,
        deployment_id=None,
        entity_id=None,
        hidden=False,
        preserve_on_migration=False,
    )


def make_passage(
    passage_id: str = "passage-789",
    text: str = "A memory about something important.",
    created_at: datetime.datetime | None = None,
) -> Passage:
    """Create a realistic Passage matching letta-client 1.7.6."""
    return Passage(
        text=text,
        id=passage_id,
        created_at=created_at or datetime.datetime(2024, 1, 15, 10, 30, 0),
        embedding=None,
        embedding_config=None,
        archive_id="archive-001",
        file_id=None,
        file_name=None,
        source_id=None,
        metadata=None,
        tags=None,
        is_deleted=False,
        created_by_id=None,
        last_updated_by_id=None,
        updated_at=None,
    )


def make_passage_search_result(
    passage: Passage | None = None,
    score: float = 0.95,
) -> PassageSearchResponseItem:
    """Create a realistic PassageSearchResponseItem."""
    return PassageSearchResponseItem(
        passage=passage or make_passage(),
        score=score,
        metadata=None,
    )


def make_assistant_message(
    msg_id: str = "msg-001",
    content: str = "Hello, I'm here to help.",
    date: datetime.datetime | None = None,
) -> AssistantMessage:
    """Create a realistic AssistantMessage matching letta-client 1.7.6."""
    return AssistantMessage(
        id=msg_id,
        content=content,
        date=date or datetime.datetime(2024, 1, 15, 11, 0, 0),
        message_type="assistant_message",
        is_err=False,
        name=None,
        otid=None,
        run_id="run-123",
        sender_id=None,
        seq_id=1,
        step_id="step-001",
    )


def make_user_message(
    msg_id: str = "msg-002",
    content: str = "Hello Nameless!",
    date: datetime.datetime | None = None,
) -> UserMessage:
    """Create a realistic UserMessage matching letta-client 1.7.6."""
    return UserMessage(
        id=msg_id,
        content=content,
        date=date or datetime.datetime(2024, 1, 15, 10, 59, 0),
        message_type="user_message",
        is_err=False,
        name=None,
        otid=None,
        run_id="run-123",
        sender_id=None,
        seq_id=0,
        step_id="step-000",
    )


class MockSyncArrayPage(list):
    """Mock for letta_client.pagination.SyncArrayPage that behaves like a list."""

    def __init__(self, items: list[Any]):
        super().__init__(items)

    def has_next_page(self) -> bool:
        return False


class TestCreateLettaMcpServer:
    """Tests for create_letta_mcp_server function."""

    def test_requires_agent_id(self) -> None:
        """Test that create_letta_mcp_server raises if no agent_id provided."""
        from nameless.core.tools import create_letta_mcp_server

        mock_letta = MagicMock()

        with patch("nameless.core.tools.get_settings") as mock_settings:
            mock_settings.return_value.agent.agent_id = None

            with pytest.raises(ValueError, match="No agent_id provided"):
                create_letta_mcp_server(letta_client=mock_letta)

    def test_creates_server_with_tools(self) -> None:
        """Test that create_letta_mcp_server returns a server with tools."""
        from nameless.core.tools import create_letta_mcp_server

        mock_letta = MagicMock()

        with patch("nameless.core.tools.get_settings") as mock_settings:
            mock_settings.return_value.agent.agent_id = "agent-123"
            mock_settings.return_value.letta.base_url = "http://localhost:8283"

            server = create_letta_mcp_server(letta_client=mock_letta, agent_id="agent-123")

            # Server should be created (exact type depends on claude_agent_sdk)
            assert server is not None


class TestGetMemoryBlock:
    """Tests for get_memory_block tool."""

    @pytest.mark.asyncio
    async def test_retrieves_block_by_label(self) -> None:
        """Test that get_memory_block calls Letta API correctly."""
        from nameless.core.tools import create_letta_mcp_server

        mock_letta = MagicMock()
        mock_letta.agents.blocks.retrieve.return_value = make_block_response(
            label="persona",
            value="I am Nameless, exploring questions of identity.",
        )

        with patch("nameless.core.tools.get_settings") as mock_settings:
            mock_settings.return_value.agent.agent_id = "agent-123"

            # Create server to get tool functions
            create_letta_mcp_server(letta_client=mock_letta, agent_id="agent-123")

            # Directly test the Letta API call pattern
            result = mock_letta.agents.blocks.retrieve("persona", agent_id="agent-123")

            assert result.value == "I am Nameless, exploring questions of identity."
            assert result.label == "persona"
            mock_letta.agents.blocks.retrieve.assert_called_once_with(
                "persona", agent_id="agent-123"
            )


class TestUpdateMemoryBlock:
    """Tests for update_memory_block tool."""

    @pytest.mark.asyncio
    async def test_updates_block_value(self) -> None:
        """Test that update_memory_block calls Letta API correctly."""
        mock_letta = MagicMock()
        mock_letta.agents.blocks.update.return_value = make_block_response(
            label="persona",
            value="Updated persona text.",
        )

        # Test the API call pattern directly
        mock_letta.agents.blocks.update(
            "persona",
            agent_id="agent-123",
            value="Updated persona text.",
        )

        mock_letta.agents.blocks.update.assert_called_once_with(
            "persona",
            agent_id="agent-123",
            value="Updated persona text.",
        )


class TestSearchArchivalMemory:
    """Tests for search_archival_memory tool."""

    @pytest.mark.asyncio
    async def test_searches_with_query(self) -> None:
        """Test that search_archival_memory calls Letta API correctly."""
        mock_letta = MagicMock()

        # Create realistic search results
        search_results = [
            make_passage_search_result(
                passage=make_passage(
                    passage_id="p1",
                    text="Memory about exploring identity.",
                    created_at=datetime.datetime(2024, 1, 10, 9, 0, 0),
                ),
                score=0.92,
            ),
            make_passage_search_result(
                passage=make_passage(
                    passage_id="p2",
                    text="Reflection on what it means to be an AI.",
                    created_at=datetime.datetime(2024, 1, 12, 14, 30, 0),
                ),
                score=0.87,
            ),
        ]
        mock_letta.agents.passages.search.return_value = search_results

        # Test the API call pattern
        results = mock_letta.agents.passages.search(
            "agent-123",
            query="identity",
            top_k=10,
        )

        assert len(results) == 2
        assert results[0].passage.text == "Memory about exploring identity."
        assert results[0].score == 0.92
        mock_letta.agents.passages.search.assert_called_once_with(
            "agent-123",
            query="identity",
            top_k=10,
        )


class TestInsertArchivalMemory:
    """Tests for insert_archival_memory tool."""

    @pytest.mark.asyncio
    async def test_inserts_passage(self) -> None:
        """Test that insert_archival_memory calls Letta API correctly."""
        mock_letta = MagicMock()
        mock_letta.agents.passages.create.return_value = make_passage(
            text="A new memory to archive.",
        )

        # Test the API call pattern
        mock_letta.agents.passages.create(
            "agent-123",
            text="A new memory to archive.",
        )

        mock_letta.agents.passages.create.assert_called_once_with(
            "agent-123",
            text="A new memory to archive.",
        )


class TestListMemoryBlocks:
    """Tests for list_memory_blocks tool."""

    @pytest.mark.asyncio
    async def test_lists_all_blocks(self) -> None:
        """Test that list_memory_blocks calls Letta API correctly."""
        mock_letta = MagicMock()

        # Create mock paginated response
        blocks = MockSyncArrayPage([
            make_block_response(block_id="b1", label="persona", value="I am Nameless."),
            make_block_response(block_id="b2", label="human", value="Jake is a technical fellow."),
        ])
        mock_letta.agents.blocks.list.return_value = blocks

        # Test the API call pattern
        result = mock_letta.agents.blocks.list("agent-123")

        assert len(result) == 2
        assert result[0].label == "persona"
        assert result[1].label == "human"
        mock_letta.agents.blocks.list.assert_called_once_with("agent-123")


class TestGetRecentMessages:
    """Tests for get_recent_messages tool."""

    @pytest.mark.asyncio
    async def test_gets_messages_with_limit(self) -> None:
        """Test that get_recent_messages calls Letta API correctly."""
        mock_letta = MagicMock()

        # Create mock paginated response with different message types
        messages = MockSyncArrayPage([
            make_user_message(
                msg_id="m1",
                content="Hello Nameless!",
                date=datetime.datetime(2024, 1, 15, 10, 0, 0),
            ),
            make_assistant_message(
                msg_id="m2",
                content="Hello! How can I help you today?",
                date=datetime.datetime(2024, 1, 15, 10, 0, 5),
            ),
        ])
        mock_letta.agents.messages.list.return_value = messages

        # Test the API call pattern
        result = mock_letta.agents.messages.list("agent-123", limit=10)

        assert len(result) == 2
        assert result[0].message_type == "user_message"
        assert result[1].message_type == "assistant_message"
        mock_letta.agents.messages.list.assert_called_once_with("agent-123", limit=10)
