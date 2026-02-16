"""Integration tests against a real Letta server at localhost:8283.

These tests require:
1. A running Letta server at localhost:8283
2. At least one agent with memory blocks and archival passages

Run with: uv run pytest tests/test_integration.py -v
Skip in CI: uv run pytest -m "not integration" -v
"""

import httpx
import pytest
from letta_client import AsyncLetta
from unittest.mock import patch

from nameless.core.agent import BLOCK_ORDER, NamelessAgent
from nameless.core.tools import create_letta_mcp_server

LETTA_URL = "http://localhost:8283"


def letta_server_available() -> bool:
    """Check if the Letta server is reachable."""
    try:
        r = httpx.get(f"{LETTA_URL}/v1/health", timeout=2.0, follow_redirects=True)
        return r.status_code == 200
    except (httpx.ConnectError, httpx.TimeoutException):
        return False


pytestmark = [
    pytest.mark.integration,
    pytest.mark.skipif(not letta_server_available(), reason="Letta server not available at localhost:8283"),
]


@pytest.fixture
async def letta_client() -> AsyncLetta:
    """Create a real AsyncLetta client."""
    return AsyncLetta(base_url=LETTA_URL)


@pytest.fixture
async def agent_id(letta_client: AsyncLetta) -> str:
    """Discover the first available agent ID from the Letta server."""
    page = await letta_client.agents.list()
    assert len(page.items) > 0, "No agents found on Letta server"
    return page.items[0].id


class TestBlocksIntegration:
    """Integration tests for Letta blocks API."""

    @pytest.mark.asyncio
    async def test_list_blocks(self, letta_client: AsyncLetta, agent_id: str) -> None:
        """Can list all memory blocks for an agent."""
        page = await letta_client.agents.blocks.list(agent_id)
        assert len(page.items) > 0
        labels = [b.label for b in page.items]
        assert "persona" in labels

    @pytest.mark.asyncio
    async def test_retrieve_persona(self, letta_client: AsyncLetta, agent_id: str) -> None:
        """Can retrieve the persona block by label."""
        block = await letta_client.agents.blocks.retrieve("persona", agent_id=agent_id)
        assert block.label == "persona"
        assert block.value is not None
        assert len(block.value) > 0

    @pytest.mark.asyncio
    async def test_update_and_restore(self, letta_client: AsyncLetta, agent_id: str) -> None:
        """Can update a block's value and restore the original."""
        # Read original
        original = await letta_client.agents.blocks.retrieve("persona", agent_id=agent_id)
        original_value = original.value

        # Update
        test_value = f"{original_value}\n[integration test marker]"
        updated = await letta_client.agents.blocks.update("persona", agent_id=agent_id, value=test_value)
        assert "[integration test marker]" in updated.value

        # Restore
        restored = await letta_client.agents.blocks.update("persona", agent_id=agent_id, value=original_value)
        assert restored.value == original_value


class TestPassagesIntegration:
    """Integration tests for Letta passages/archival memory API."""

    @pytest.mark.asyncio
    async def test_list_passages(self, letta_client: AsyncLetta, agent_id: str) -> None:
        """Can list archival memory passages for an agent."""
        passages = await letta_client.agents.passages.list(agent_id)
        assert isinstance(passages, list)
        assert len(passages) > 0
        assert hasattr(passages[0], "text")

    @pytest.mark.asyncio
    async def test_insert_passage(self, letta_client: AsyncLetta, agent_id: str) -> None:
        """Can insert a new archival memory passage via archives API."""
        marker = "[integration-test-insert]"
        # Get archive_id from existing passage
        passages = await letta_client.agents.passages.list(agent_id, limit=1)
        assert len(passages) > 0
        archive_id = passages[0].archive_id

        result = await letta_client.archives.passages.create(archive_id, text=marker)
        assert hasattr(result, "text")
        assert result.text == marker

        # Verify it appears in the listing (use high limit to include newest)
        all_passages = await letta_client.agents.passages.list(agent_id, limit=1000)
        texts = [p.text for p in all_passages]
        assert marker in texts

        # Cleanup
        await letta_client.archives.passages.delete(result.id, archive_id=archive_id)


class TestMessagesIntegration:
    """Integration tests for Letta messages API."""

    @pytest.mark.asyncio
    async def test_list_messages(self, letta_client: AsyncLetta, agent_id: str) -> None:
        """Can list recent messages for an agent."""
        page = await letta_client.agents.messages.list(agent_id, limit=5)
        # Agent may or may not have messages, but the call should succeed
        assert isinstance(page.items, list)


class TestToolsIntegration:
    """Integration tests running actual tool handlers against real Letta."""

    @pytest.fixture
    def integration_tools(self, letta_client: AsyncLetta, agent_id: str) -> dict:
        """Create tool handlers connected to the real Letta server."""
        from unittest.mock import patch as mock_patch

        from claude_agent_sdk import create_sdk_mcp_server as real_create

        captured: list = []

        def capturing_create(**kwargs):
            captured.extend(kwargs.get("tools", []))
            return real_create(**kwargs)

        with mock_patch("nameless.core.tools.get_settings") as mock_settings:
            mock_settings.return_value.agent.agent_id = agent_id
            mock_settings.return_value.letta.base_url = LETTA_URL

            with mock_patch("nameless.core.tools.create_sdk_mcp_server", side_effect=capturing_create):
                create_letta_mcp_server(letta_client=letta_client, agent_id=agent_id)

        return {t.name: t for t in captured}

    @pytest.mark.asyncio
    async def test_get_memory_block_via_handler(self, integration_tools: dict) -> None:
        """Tool handler retrieves persona block from real Letta."""
        result = await integration_tools["get_memory_block"].handler({"block_name": "persona"})

        assert "content" in result
        assert len(result["content"]) == 1
        assert result["content"][0]["type"] == "text"
        assert len(result["content"][0]["text"]) > 0

    @pytest.mark.asyncio
    async def test_list_blocks_via_handler(self, integration_tools: dict) -> None:
        """Tool handler lists all blocks from real Letta."""
        result = await integration_tools["list_memory_blocks"].handler({})

        text = result["content"][0]["text"]
        assert "persona" in text

    @pytest.mark.asyncio
    async def test_search_archival_via_handler(self, integration_tools: dict) -> None:
        """Tool handler searches archival memory via real Letta."""
        result = await integration_tools["search_archival_memory"].handler({"query": "identity", "count": 3})

        assert "content" in result
        assert result["content"][0]["type"] == "text"


class TestPersistenceRoundTrip:
    """Integration tests for persist → fetch round-trip using a disposable agent.

    Creates a temporary agent, verifies conversation summaries persist to
    archival and appear in the next build_system_prompt() call.
    """

    @pytest.fixture
    async def disposable_agent(self, letta_client: AsyncLetta):
        """Create a temporary agent with an attached archive.

        Uses the same LLM/embedding config as the existing agent so Letta
        server accepts the request. Creates and attaches an archive so
        passages can be created via archives.passages.create (which
        bypasses the agent LLM loop).
        """
        # Copy config from the existing agent
        page = await letta_client.agents.list()
        existing = page.items[0]

        agent_state = await letta_client.agents.create(
            name="test-persistence-roundtrip",
            memory_blocks=[
                {"label": "persona", "value": "I am a test agent."},
                {"label": "human", "value": "Test user."},
            ],
            llm_config=existing.llm_config,
            embedding_config=existing.embedding_config,
            include_base_tools=False,
        )

        # Create and attach an archive so persist_conversation can use it
        archive = await letta_client.archives.create(
            name=f"{agent_state.name}'s Archive",
            embedding_config=existing.embedding_config,
        )
        await letta_client.agents.archives.attach(archive.id, agent_id=agent_state.id)

        yield agent_state

        await letta_client.agents.delete(agent_state.id)
        await letta_client.archives.delete(archive.id)

    @pytest.mark.asyncio
    async def test_persist_then_fetch(self, letta_client: AsyncLetta, disposable_agent) -> None:
        """persist_conversation() writes a summary that build_system_prompt() picks up."""
        agent_id = disposable_agent.id

        with patch("nameless.core.agent.get_settings") as mock_settings:
            mock_settings.return_value.letta.base_url = LETTA_URL
            mock_settings.return_value.agent.agent_id = agent_id
            agent = NamelessAgent(agent_id=agent_id, _client=letta_client)

        # Simulate a conversation turn
        fake_responses = [{"result": "I remember everything about our chat."}]
        await agent.persist_conversation("Hello, do you remember me?", fake_responses)

        # Now build the system prompt — the summary should appear
        prompt = await agent.build_system_prompt()

        assert "Hello, do you remember me?" in prompt
        assert "I remember everything about our chat." in prompt
        assert "[Conversation" in prompt

    @pytest.mark.asyncio
    async def test_multiple_turns_accumulate(self, letta_client: AsyncLetta, disposable_agent) -> None:
        """Multiple persist calls all appear in the next system prompt."""
        agent_id = disposable_agent.id

        with patch("nameless.core.agent.get_settings") as mock_settings:
            mock_settings.return_value.letta.base_url = LETTA_URL
            mock_settings.return_value.agent.agent_id = agent_id
            agent = NamelessAgent(agent_id=agent_id, _client=letta_client)

        # Simulate two conversation turns
        await agent.persist_conversation("Turn one", [{"result": "Response one"}])
        await agent.persist_conversation("Turn two", [{"result": "Response two"}])

        prompt = await agent.build_system_prompt()

        assert "Turn one" in prompt
        assert "Response one" in prompt
        assert "Turn two" in prompt
        assert "Response two" in prompt

    @pytest.mark.asyncio
    async def test_prompt_grows_after_persist(self, letta_client: AsyncLetta, disposable_agent) -> None:
        """System prompt length increases after persisting a conversation."""
        agent_id = disposable_agent.id

        with patch("nameless.core.agent.get_settings") as mock_settings:
            mock_settings.return_value.letta.base_url = LETTA_URL
            mock_settings.return_value.agent.agent_id = agent_id
            agent = NamelessAgent(agent_id=agent_id, _client=letta_client)

        prompt_before = await agent.build_system_prompt()

        await agent.persist_conversation(
            "A meaningful conversation starter",
            [{"result": "A thoughtful and detailed response about identity."}],
        )

        prompt_after = await agent.build_system_prompt()

        assert len(prompt_after) > len(prompt_before)


class TestContextAssemblyIntegration:
    """Integration tests for full MemGPT-style system prompt assembly."""

    @pytest.mark.asyncio
    async def test_build_system_prompt_against_real_letta(
        self, letta_client: AsyncLetta, agent_id: str
    ) -> None:
        """build_system_prompt() assembles all 7 blocks in correct XML format."""
        with patch("nameless.core.agent.get_settings") as mock_settings:
            mock_settings.return_value.letta.base_url = LETTA_URL
            mock_settings.return_value.agent.agent_id = agent_id
            agent = NamelessAgent(agent_id=agent_id, _client=letta_client)

        prompt = await agent.build_system_prompt()

        # Should contain base instructions
        assert "<base_instructions>" in prompt
        assert "</base_instructions>" in prompt

        # Should contain memory_blocks wrapper
        assert "<memory_blocks>" in prompt
        assert "</memory_blocks>" in prompt

        # Should contain all 7 block labels
        for label in BLOCK_ORDER:
            assert f"<{label}>" in prompt, f"Missing block: {label}"
            assert f"</{label}>" in prompt

        # Each block should have proper XML structure
        assert "<description>" in prompt
        assert "<metadata>" in prompt
        assert "<value>" in prompt

        # Should contain recall memory section
        assert "<recall_memory>" in prompt
        assert "</recall_memory>" in prompt

        # Should contain memory metadata
        assert "<memory_metadata>" in prompt
        assert "The current time is:" in prompt
        assert "recall memory" in prompt
        assert "archival memory" in prompt
