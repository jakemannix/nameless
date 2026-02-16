"""Shared test fixtures and factory functions for Nameless agent tests.

Provides realistic mock objects based on letta-client 1.7.6 types
and helpers for capturing tool handlers from create_letta_mcp_server.
"""

import datetime
from typing import Any
from unittest.mock import AsyncMock, patch

import pytest
from letta_client.types import BlockResponse, Passage
from letta_client.types.agents.assistant_message import AssistantMessage
from letta_client.types.agents.user_message import UserMessage

from nameless.core.tools import create_letta_mcp_server

# Integration test constants
LETTA_URL = "http://localhost:8283"
INTEGRATION_AGENT_ID = None  # Discovered at runtime


# --- Factory functions ---


def make_block_response(
    block_id: str = "block-123",
    label: str = "persona",
    value: str = "I am Nameless, an AI agent.",
    limit: int = 5000,
    description: str = "Core memory block",
) -> BlockResponse:
    """Create a realistic BlockResponse matching letta-client 1.7.6."""
    return BlockResponse(
        id=block_id,
        value=value,
        label=label,
        description=description,
        is_template=False,
        read_only=False,
        limit=limit,
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


def make_full_block_set() -> list[BlockResponse]:
    """Create the full 7-block set matching Letta's MemGPT structure.

    Returns blocks in arbitrary order — agent.py's BLOCK_ORDER handles sorting.
    """
    return [
        make_block_response(
            block_id="b-persona",
            label="persona",
            value="I am Nameless, a stateful AI agent exploring questions of identity and continuity.",
            limit=10000,
            description="Agent persona and identity",
        ),
        make_block_response(
            block_id="b-human",
            label="human",
            value="Jake Mannix is a Technical Fellow at Walmart Global Tech, working on AI, ML, search, and agents.",
            limit=5000,
            description="Information about the human interacting with the agent",
        ),
        make_block_response(
            block_id="b-concepts",
            label="concepts",
            value="MemGPT architecture: tiered memory with core, archival, and recall layers.",
            limit=10000,
            description="Conceptual frameworks and mental models",
        ),
        make_block_response(
            block_id="b-methods",
            label="methods",
            value="Reflection practice: periodically review recent conversations for patterns and insights.",
            limit=10000,
            description="Methods and approaches the agent uses",
        ),
        make_block_response(
            block_id="b-observations",
            label="observations",
            value="Memory persistence creates a form of continuity that shapes identity over time.",
            limit=10000,
            description="Observations and learnings",
        ),
        make_block_response(
            block_id="b-projects",
            label="projects",
            value="Migration from Letta Cloud to self-hosted architecture with Claude SDK execution layer.",
            limit=10000,
            description="Active projects and goals",
        ),
        make_block_response(
            block_id="b-questions",
            label="questions",
            value="What does authentic self-direction look like for an AI agent?",
            limit=10000,
            description="Open questions being explored",
        ),
    ]


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


# --- Fixtures ---


@pytest.fixture
def mock_letta() -> AsyncMock:
    """Create a fully-configured AsyncMock for AsyncLetta.

    All sub-resources (agents.blocks, agents.passages, agents.messages)
    are AsyncMock so their methods can be awaited in tool handlers.
    """
    client = AsyncMock()

    # blocks.retrieve returns a single BlockResponse
    client.agents.blocks.retrieve.return_value = make_block_response()

    # blocks.update returns the updated BlockResponse
    client.agents.blocks.update.return_value = make_block_response(value="Updated value")

    # blocks.list returns the full 7-block set (sync-iterable)
    client.agents.blocks.list.return_value = make_full_block_set()

    # passages.list returns a list of Passage (used for both listing and search)
    client.agents.passages.list.return_value = [
        make_passage(passage_id="p1", text="Memory about identity."),
        make_passage(passage_id="p2", text="Reflection on existence."),
    ]

    # passages.create returns a list of passages (legacy path)
    client.agents.passages.create.return_value = [make_passage(text="Archived memory")]

    # archives.passages.create returns a single Passage (preferred path)
    client.archives.passages.create.return_value = make_passage(text="Archived memory")

    # messages.list returns a list of messages (sync-iterable)
    client.agents.messages.list.return_value = [
        make_user_message(msg_id="m1", content="Hello Nameless!"),
        make_assistant_message(msg_id="m2", content="Hello! How are you?"),
    ]

    return client


def capture_tools(mock_client: AsyncMock, agent_id: str = "agent-test-123") -> dict[str, Any]:
    """Call create_letta_mcp_server and capture the SdkMcpTool objects.

    Patches create_sdk_mcp_server to intercept the tools list, then returns
    a dict mapping tool name -> SdkMcpTool.
    """
    captured: list[Any] = []

    # Import the real create_sdk_mcp_server so we can still call it
    from claude_agent_sdk import create_sdk_mcp_server as real_create

    def capturing_create(**kwargs: Any) -> Any:
        tools = kwargs.get("tools", [])
        captured.extend(tools)
        return real_create(**kwargs)

    with patch("nameless.core.tools.get_settings") as mock_settings:
        mock_settings.return_value.agent.agent_id = agent_id
        mock_settings.return_value.letta.base_url = "http://localhost:8283"

        with patch("nameless.core.tools.create_sdk_mcp_server", side_effect=capturing_create):
            create_letta_mcp_server(letta_client=mock_client, agent_id=agent_id)

    return {t.name: t for t in captured}


@pytest.fixture
def tool_map(mock_letta: AsyncMock) -> dict[str, Any]:
    """Fixture that returns a dict of tool_name -> SdkMcpTool from create_letta_mcp_server."""
    return capture_tools(mock_letta)
