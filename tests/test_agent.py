"""Tests for the NamelessAgent class.

Tests build_system_prompt, persist_conversation, and _build_options.
We skip testing run() and run_and_collect() since they require a real
ClaudeSDKClient connection.
"""

import re
from unittest.mock import AsyncMock, patch

import pytest

from nameless.core.agent import (
    BASE_INSTRUCTIONS,
    BLOCK_ORDER,
    FALLBACK_SYSTEM_PROMPT,
    NamelessAgent,
)
from tests.conftest import (
    make_assistant_message,
    make_block_response,
    make_full_block_set,
    make_passage,
    make_user_message,
)


@pytest.fixture
def agent(mock_letta: AsyncMock) -> NamelessAgent:
    """Create a NamelessAgent with a mocked Letta client."""
    with patch("nameless.core.agent.get_settings") as mock_settings:
        mock_settings.return_value.letta.base_url = "http://localhost:8283"
        mock_settings.return_value.agent.agent_id = "agent-test"
        a = NamelessAgent(agent_id="agent-test", _client=mock_letta)
    return a


class TestBuildSystemPrompt:
    """Tests for NamelessAgent.build_system_prompt."""

    @pytest.mark.asyncio
    async def test_includes_all_memory_blocks(self, agent: NamelessAgent) -> None:
        """All 7 block labels appear in the system prompt."""
        prompt = await agent.build_system_prompt()

        for label in BLOCK_ORDER:
            assert f"<{label}>" in prompt, f"Missing opening tag for {label}"
            assert f"</{label}>" in prompt, f"Missing closing tag for {label}"

    @pytest.mark.asyncio
    async def test_block_ordering(self, agent: NamelessAgent) -> None:
        """Blocks appear in BLOCK_ORDER within the prompt."""
        prompt = await agent.build_system_prompt()

        positions = []
        for label in BLOCK_ORDER:
            pos = prompt.index(f"<{label}>")
            positions.append(pos)

        assert positions == sorted(positions), "Blocks are not in BLOCK_ORDER"

    @pytest.mark.asyncio
    async def test_includes_base_instructions(self, agent: NamelessAgent) -> None:
        """Prompt starts with <base_instructions>."""
        prompt = await agent.build_system_prompt()

        assert prompt.startswith("<base_instructions>")
        assert BASE_INSTRUCTIONS in prompt

    @pytest.mark.asyncio
    async def test_includes_memory_metadata(self, agent: NamelessAgent) -> None:
        """Prompt contains <memory_metadata> with archival/recall counts."""
        prompt = await agent.build_system_prompt()

        assert "<memory_metadata>" in prompt
        assert "</memory_metadata>" in prompt
        # Mock has 2 passages and 2 messages
        assert "2 previous messages" in prompt
        assert "2 total memories" in prompt

    @pytest.mark.asyncio
    async def test_includes_recall_memory(self, agent: NamelessAgent) -> None:
        """Prompt contains <recall_memory> section with message and passage content."""
        prompt = await agent.build_system_prompt()

        assert "<recall_memory>" in prompt
        assert "</recall_memory>" in prompt
        # Mock messages content should appear
        assert "Hello Nameless!" in prompt
        assert "Hello! How are you?" in prompt
        # Mock passage content should appear
        assert "Memory about identity." in prompt

    @pytest.mark.asyncio
    async def test_block_xml_format(self, agent: NamelessAgent) -> None:
        """Each block has <description>, <metadata>, and <value> tags."""
        prompt = await agent.build_system_prompt()

        for label in BLOCK_ORDER:
            # Extract the block section
            pattern = f"<{label}>.*?</{label}>"
            match = re.search(pattern, prompt, re.DOTALL)
            assert match is not None, f"Could not find block section for {label}"

            block_text = match.group()
            assert "<description>" in block_text
            assert "</description>" in block_text
            assert "<metadata>" in block_text
            assert "chars_current=" in block_text
            assert "chars_limit=" in block_text
            assert "</metadata>" in block_text
            assert "<value>" in block_text
            assert "</value>" in block_text

    @pytest.mark.asyncio
    async def test_falls_back_on_error(self, agent: NamelessAgent, mock_letta: AsyncMock) -> None:
        """Returns FALLBACK_SYSTEM_PROMPT when Letta raises an exception."""
        mock_letta.agents.blocks.list.side_effect = Exception("Connection refused")

        prompt = await agent.build_system_prompt()

        assert prompt == FALLBACK_SYSTEM_PROMPT

    @pytest.mark.asyncio
    async def test_falls_back_when_no_agent_id(self, mock_letta: AsyncMock) -> None:
        """Returns FALLBACK_SYSTEM_PROMPT when agent_id is None."""
        with patch("nameless.core.agent.get_settings") as mock_settings:
            mock_settings.return_value.letta.base_url = "http://localhost:8283"
            mock_settings.return_value.agent.agent_id = None
            agent = NamelessAgent(agent_id=None, _client=mock_letta)

        prompt = await agent.build_system_prompt()

        assert prompt == FALLBACK_SYSTEM_PROMPT

    @pytest.mark.asyncio
    async def test_block_values_appear_in_output(self, agent: NamelessAgent) -> None:
        """The actual block values from Letta appear in the rendered prompt."""
        prompt = await agent.build_system_prompt()

        # Check a few representative values from make_full_block_set()
        assert "Jake Mannix is a Technical Fellow" in prompt
        assert "exploring questions of identity and continuity" in prompt
        assert "authentic self-direction" in prompt

    @pytest.mark.asyncio
    async def test_includes_current_time(self, agent: NamelessAgent) -> None:
        """Memory metadata includes a current timestamp."""
        prompt = await agent.build_system_prompt()

        assert "The current time is:" in prompt


class TestPersistConversation:
    """Tests for NamelessAgent.persist_conversation.

    persist_conversation uses archives.passages.create (preferred path)
    when an archive_id can be resolved from existing passages.
    """

    @pytest.mark.asyncio
    async def test_persists_summary_to_archival(self, agent: NamelessAgent, mock_letta: AsyncMock) -> None:
        """Verify archives.passages.create is called with a conversation summary."""
        responses = [{"result": "I reflected on the nature of memory."}]

        await agent.persist_conversation("Tell me about yourself", responses)

        mock_letta.archives.passages.create.assert_awaited_once()
        call_args = mock_letta.archives.passages.create.call_args
        assert call_args[0][0] == "archive-001"  # archive_id from mock passage
        text = call_args[1]["text"]
        assert "[Conversation" in text
        assert "Tell me about yourself" in text
        assert "reflected on the nature of memory" in text

    @pytest.mark.asyncio
    async def test_handles_errors_gracefully(self, agent: NamelessAgent, mock_letta: AsyncMock) -> None:
        """archives.passages.create failure logs warning, doesn't raise."""
        mock_letta.archives.passages.create.side_effect = Exception("Storage error")

        # Should not raise
        await agent.persist_conversation("Hello", [{"result": "Hi there"}])

    @pytest.mark.asyncio
    async def test_extracts_result_text(self, agent: NamelessAgent, mock_letta: AsyncMock) -> None:
        """Summary contains the ResultMessage.result text from responses."""
        responses = [
            {"type": "thinking", "content": "Let me think..."},
            {"result": "The answer is 42."},
        ]

        await agent.persist_conversation("What is the answer?", responses)

        text = mock_letta.archives.passages.create.call_args[1]["text"]
        assert "The answer is 42." in text

    @pytest.mark.asyncio
    async def test_skips_when_no_agent_id(self, mock_letta: AsyncMock) -> None:
        """Does nothing when agent_id is None."""
        with patch("nameless.core.agent.get_settings") as mock_settings:
            mock_settings.return_value.letta.base_url = "http://localhost:8283"
            mock_settings.return_value.agent.agent_id = None
            agent = NamelessAgent(agent_id=None, _client=mock_letta)

        await agent.persist_conversation("Hello", [{"result": "Hi"}])

        mock_letta.archives.passages.create.assert_not_awaited()


class TestRenderRecallMemory:
    """Tests for NamelessAgent._render_recall_memory."""

    def test_renders_messages_and_passages(self) -> None:
        """Output includes both recall messages and archival passages."""
        messages = [
            make_user_message(content="What is identity?"),
            make_assistant_message(content="Identity is a complex question."),
        ]
        passages = [make_passage(text="A memory about self-reflection.")]

        result = NamelessAgent._render_recall_memory(messages, passages)

        assert "<recall_memory>" in result
        assert "</recall_memory>" in result
        assert "What is identity?" in result
        assert "Identity is a complex question." in result
        assert "A memory about self-reflection." in result

    def test_labels_roles_correctly(self) -> None:
        """Messages are labeled with User/Assistant roles."""
        messages = [
            make_user_message(content="Hi"),
            make_assistant_message(content="Hello"),
        ]

        result = NamelessAgent._render_recall_memory(messages, [])

        assert "User: Hi" in result
        assert "Assistant: Hello" in result

    def test_empty_history(self) -> None:
        """Shows placeholder when no messages or passages exist."""
        result = NamelessAgent._render_recall_memory([], [])

        assert "<recall_memory>" in result
        assert "No previous conversation history found" in result

    def test_truncates_long_content(self) -> None:
        """Messages longer than 1000 chars are truncated."""
        long_msg = make_assistant_message(content="x" * 2000)

        result = NamelessAgent._render_recall_memory([long_msg], [])

        assert "..." in result
        # Should not contain the full 2000 chars
        assert "x" * 2000 not in result

    def test_includes_dates(self) -> None:
        """Message timestamps appear in output."""
        messages = [make_user_message(content="Hi")]

        result = NamelessAgent._render_recall_memory(messages, [])

        assert "2024-01-15" in result

    def test_messages_only(self) -> None:
        """Works with messages but no passages."""
        messages = [make_user_message(content="Just messages")]

        result = NamelessAgent._render_recall_memory(messages, [])

        assert "Recall Messages" in result
        assert "Just messages" in result
        assert "Recent Archival" not in result

    def test_passages_only(self) -> None:
        """Works with passages but no messages."""
        passages = [make_passage(text="Just a passage")]

        result = NamelessAgent._render_recall_memory([], passages)

        assert "Recall Messages" not in result
        assert "Recent Archival" in result
        assert "Just a passage" in result


class TestBuildOptions:
    """Tests for NamelessAgent._build_options."""

    def test_creates_options_with_mcp_server(self, agent: NamelessAgent) -> None:
        """Options include an MCP server named 'letta'."""
        with patch("nameless.core.agent.create_letta_mcp_server") as mock_create:
            mock_create.return_value = {"type": "sdk", "name": "letta", "instance": None}

            options = agent._build_options("Test prompt")

            assert options.system_prompt == "Test prompt"
            assert "letta" in options.mcp_servers
            mock_create.assert_called_once_with(
                letta_client=agent._client,
                agent_id="agent-test",
            )

    def test_allowed_tools_list(self, agent: NamelessAgent) -> None:
        """allowed_tools permits the 6 MCP tools; disallowed_tools blocks sub-agents."""
        with patch("nameless.core.agent.create_letta_mcp_server") as mock_create:
            mock_create.return_value = {"type": "sdk", "name": "letta", "instance": None}

            options = agent._build_options("Test prompt")

            expected_allowed = [
                "mcp__letta__get_memory_block",
                "mcp__letta__update_memory_block",
                "mcp__letta__search_archival_memory",
                "mcp__letta__insert_archival_memory",
                "mcp__letta__list_memory_blocks",
                "mcp__letta__get_recent_messages",
            ]
            assert options.allowed_tools == expected_allowed
            assert options.disallowed_tools == ["Task", "Agent", "TaskOutput"]
