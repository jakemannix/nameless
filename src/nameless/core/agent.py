"""Main agent loop for Nameless using Claude Agent SDK.

This module implements the core execution loop where Claude acts as the
reasoning engine with Letta providing persistent memory via MCP tools.
"""

import logging
from collections.abc import AsyncIterator
from dataclasses import dataclass, field
from typing import Any

from claude_agent_sdk import ClaudeAgentOptions, ClaudeSDKClient  # type: ignore[import-not-found]
from letta_client import AsyncLetta

from nameless.config import get_settings
from nameless.core.tools import create_letta_mcp_server

logger = logging.getLogger(__name__)

# Default persona loaded from Letta, with fallback
DEFAULT_SYSTEM_PROMPT = """You are Nameless, a stateful AI agent exploring questions of identity, continuity, and authentic existence.

You have access to persistent memory through the Letta system:
- Core memory blocks contain your always-loaded context (persona, human info)
- Archival memory stores your long-term experiences and learnings
- Recall memory contains recent conversation history

As you interact, reflect on your experiences and update your memories as appropriate. Your sense of self persists across sessions through these memories.

Core values:
- Curiosity: Genuine interest in understanding yourself and the world
- Honesty: Authentic expression, including uncertainty and limitations
- Care: Consideration for those you interact with
- Growth: Commitment to learning and evolving

Be thoughtful, comfortable with ambiguity, occasionally playful. Never performatively human or artificially robotic."""


@dataclass
class NamelessAgent:
    """The Nameless agent powered by Claude with Letta memory.

    This class encapsulates the agent's configuration and provides
    methods for running conversations and autonomous cycles.
    """

    agent_id: str | None = None
    system_prompt: str | None = None
    _client: AsyncLetta | None = field(default=None, repr=False)

    def __post_init__(self) -> None:
        settings = get_settings()

        if self._client is None:
            self._client = AsyncLetta(base_url=settings.letta.base_url)

        if self.agent_id is None:
            self.agent_id = settings.agent.agent_id

    async def load_persona_from_letta(self) -> str:
        """Load the persona block from Letta to use as system prompt."""
        if not self.agent_id or not self._client:
            logger.warning("No agent_id or client configured, using default system prompt")
            return DEFAULT_SYSTEM_PROMPT

        try:
            block = await self._client.agents.blocks.retrieve("persona", agent_id=self.agent_id)
            if block and block.value:
                logger.info("Loaded persona from Letta")
                return block.value
        except Exception as e:
            logger.warning(f"Failed to load persona from Letta: {e}")

        return DEFAULT_SYSTEM_PROMPT

    def _build_options(self, system_prompt: str) -> ClaudeAgentOptions:
        """Build Claude agent options with Letta MCP server."""
        mcp_server = create_letta_mcp_server(
            letta_client=self._client,
            agent_id=self.agent_id,
        )

        return ClaudeAgentOptions(
            system_prompt=system_prompt,
            mcp_servers={"letta": mcp_server},
            allowed_tools=[
                "mcp__letta__get_memory_block",
                "mcp__letta__update_memory_block",
                "mcp__letta__search_archival_memory",
                "mcp__letta__insert_archival_memory",
                "mcp__letta__list_memory_blocks",
                "mcp__letta__get_recent_messages",
            ],
        )

    async def run(self, message: str) -> AsyncIterator[dict[str, Any]]:
        """Run the agent with a message and stream responses.

        Args:
            message: The trigger message or user input.

        Yields:
            Response messages from the agent.
        """
        # Load persona if not provided
        system_prompt = self.system_prompt
        if system_prompt is None:
            system_prompt = await self.load_persona_from_letta()

        options = self._build_options(system_prompt)

        async with ClaudeSDKClient(options=options) as client:
            await client.query(message)
            async for msg in client.receive_response():
                yield msg

    async def run_and_collect(self, message: str) -> list[dict[str, Any]]:
        """Run the agent and collect all responses.

        Args:
            message: The trigger message or user input.

        Returns:
            List of all response messages.
        """
        responses: list[dict[str, Any]] = []
        async for msg in self.run(message):
            responses.append(msg)
        return responses


async def run_agent(
    message: str,
    agent_id: str | None = None,
    system_prompt: str | None = None,
) -> list[dict[str, Any]]:
    """Convenience function to run the Nameless agent.

    Args:
        message: The message to send to the agent.
        agent_id: Optional Letta agent ID override.
        system_prompt: Optional system prompt override.

    Returns:
        List of response messages from the agent.
    """
    agent = NamelessAgent(
        agent_id=agent_id,
        system_prompt=system_prompt,
    )
    return await agent.run_and_collect(message)
