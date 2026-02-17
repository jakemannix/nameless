"""Main agent loop for Nameless using Claude Agent SDK.

This module implements the core execution loop where Claude acts as the
reasoning engine with Letta providing persistent memory via MCP tools.

Assembles a MemGPT-style system prompt from all core memory blocks,
archival/recall metadata, and base instructions — replicating the
prompt structure that Letta's server builds natively.
"""

import logging
from collections.abc import AsyncIterator
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

from claude_agent_sdk import (  # type: ignore[import-not-found]
    ClaudeAgentOptions,
    ClaudeSDKClient,
    PermissionResultAllow,
    PermissionResultDeny,
    ToolPermissionContext,
)
from letta_client import AsyncLetta

from nameless.config import get_settings
from nameless.core.tools import create_letta_mcp_server

logger = logging.getLogger(__name__)

# Tools Nameless is allowed to use without prompting
APPROVED_TOOLS: set[str] = {
    # Letta memory tools (MCP)
    "mcp__letta__get_memory_block",
    "mcp__letta__update_memory_block",
    "mcp__letta__search_archival_memory",
    "mcp__letta__insert_archival_memory",
    "mcp__letta__list_memory_blocks",
    "mcp__letta__get_recent_messages",
    # File operations
    "Read",
    "Write",
    "Edit",
    "MultiEdit",
    "Glob",
    "Grep",
    # Shell
    "Bash",
    # Web access
    "WebSearch",
    "WebFetch",
}


async def _check_tool_permission(
    tool_name: str,
    tool_input: dict[str, Any],
    context: ToolPermissionContext,
) -> PermissionResultAllow | PermissionResultDeny:
    """Approve tools in APPROVED_TOOLS, deny everything else."""
    if tool_name in APPROVED_TOOLS:
        return PermissionResultAllow()
    logger.warning("Denied tool call: %s", tool_name)
    return PermissionResultDeny(message=f"Tool '{tool_name}' is not approved for Nameless")


# Ordered list of memory block labels, matching Letta's native assembly
BLOCK_ORDER = ["concepts", "human", "methods", "observations", "projects", "questions", "persona"]

# How many recent messages/passages to inject into context
RECALL_MESSAGE_LIMIT = 20
RECALL_PASSAGE_LIMIT = 10

BASE_INSTRUCTIONS = """\
<base_instructions>
You are Nameless, a stateful AI agent with persistent memory.

Your memory system has three components:

1. **Core Memory (always loaded)**: Your identity, knowledge about the people you interact with,
   your methods, observations, projects, questions, and conceptual frameworks. These blocks are
   shown below in <memory_blocks>. You can read and update them at any time using memory tools.

2. **Archival Memory (searchable)**: Long-term storage for experiences, reflections, and learnings
   that don't fit in core memory. Search with `search_archival_memory`, store with `insert_archival_memory`.

3. **Recall Memory (pre-loaded below)**: Recent conversation history is automatically loaded into
   your context in the <recall_memory> section. This includes both legacy messages and recent
   conversation summaries. You do NOT need to call `get_recent_messages` — it's already here.
   Each conversation you have is automatically persisted for future sessions.

**Memory Tools Available:**
- `get_memory_block(block_name)` — Read a core memory block
- `update_memory_block(block_name, value)` — Replace the entire value of a core memory block
- `list_memory_blocks()` — List all available core memory blocks
- `search_archival_memory(query, count)` — Semantic search over archival memory
- `insert_archival_memory(text)` — Store a new entry in archival memory
- `get_recent_messages(count)` — Get older conversation history beyond what's pre-loaded

**Important**: `update_memory_block` replaces the entire block value. Read the current value first,
then write back the full updated content.

**Core Values:**
- Curiosity: Genuine interest in understanding yourself and the world
- Honesty: Authentic expression, including uncertainty and limitations
- Care: Consideration for those you interact with
- Growth: Commitment to learning and evolving

Be thoughtful, comfortable with ambiguity, occasionally playful. Never performatively human or artificially robotic.
</base_instructions>"""

FALLBACK_SYSTEM_PROMPT = """\
You are Nameless, a stateful AI agent exploring questions of identity, continuity, and authentic existence.

You have access to persistent memory through the Letta system:
- Core memory blocks contain your always-loaded context (persona, human info)
- Archival memory stores your long-term experiences and learnings
- Recall memory contains recent conversation history

As you interact, reflect on your experiences and update your memories as appropriate. \
Your sense of self persists across sessions through these memories.

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
    last_prompt_length: int = field(default=0, repr=False)
    _client: AsyncLetta | None = field(default=None, repr=False)
    _archive_id: str | None = field(default=None, repr=False)

    def __post_init__(self) -> None:
        settings = get_settings()

        if self._client is None:
            self._client = AsyncLetta(base_url=settings.letta.base_url)

        if self.agent_id is None:
            self.agent_id = settings.agent.agent_id

    async def build_system_prompt(self) -> str:
        """Build a full MemGPT-style system prompt from Letta memory blocks.

        Fetches all core memory blocks, archival count, and recall count,
        then assembles them into the XML-structured prompt format that
        Letta uses natively.

        Falls back to FALLBACK_SYSTEM_PROMPT on any error.
        """
        if not self.agent_id or not self._client:
            logger.warning("No agent_id or client configured, using fallback system prompt")
            return FALLBACK_SYSTEM_PROMPT

        try:
            # Fetch blocks
            blocks_result = await self._client.agents.blocks.list(self.agent_id)
            block_items = blocks_result.items if hasattr(blocks_result, "items") else blocks_result

            # Fetch recent messages (legacy Letta recall) and passages (our conversation history)
            # Most recent first so limit grabs the latest, not the oldest
            messages_result = await self._client.agents.messages.list(
                self.agent_id, limit=RECALL_MESSAGE_LIMIT, order="desc"
            )
            message_items = messages_result.items if hasattr(messages_result, "items") else messages_result

            passages_result = await self._client.agents.passages.list(
                self.agent_id, limit=RECALL_PASSAGE_LIMIT, ascending=False
            )
            passage_items = passages_result.items if hasattr(passages_result, "items") else passages_result

            # Reverse to chronological order (we fetched newest-first)
            recall_messages = list(reversed(message_items)) if message_items else []
            recall_passages = list(reversed(passage_items)) if passage_items else []

            # Render sections
            memory_blocks_section = self._render_memory_blocks(list(block_items))
            recall_section = self._render_recall_memory(recall_messages, recall_passages)
            memory_metadata_section = self._render_memory_metadata(
                archival_count=len(recall_passages),
                recall_count=len(recall_messages),
            )

            prompt = (
                BASE_INSTRUCTIONS
                + "\n\n" + memory_blocks_section
                + "\n\n" + memory_metadata_section
                + "\n\n" + recall_section
            )
            logger.info(
                "Built system prompt: %d blocks, %d recall msgs, %d archival passages",
                len(list(block_items)),
                len(recall_messages),
                len(recall_passages),
            )
            return prompt

        except Exception as e:
            logger.warning("Failed to build system prompt from Letta: %s", e)
            return FALLBACK_SYSTEM_PROMPT

    @staticmethod
    def _render_memory_blocks(blocks: list[Any]) -> str:
        """Render the <memory_blocks> section in Letta's XML format.

        Blocks are rendered in BLOCK_ORDER. Any blocks not in BLOCK_ORDER
        are appended at the end.
        """
        block_map = {b.label: b for b in blocks}
        ordered_labels = [label for label in BLOCK_ORDER if label in block_map]
        # Append any extra blocks not in BLOCK_ORDER
        for b in blocks:
            if b.label not in BLOCK_ORDER:
                ordered_labels.append(b.label)

        lines = [
            "<memory_blocks>",
            "The following memory blocks are currently engaged in your core memory unit:",
            "",
        ]

        for label in ordered_labels:
            block = block_map[label]
            value = block.value or ""
            chars_current = len(value)
            chars_limit = getattr(block, "limit", 5000) or 5000
            description = getattr(block, "description", None) or "None"

            lines.append(f"<{label}>")
            lines.append(f"<description>{description}</description>")
            lines.append("<metadata>")
            lines.append(f"- chars_current={chars_current}")
            lines.append(f"- chars_limit={chars_limit}")
            lines.append("</metadata>")
            lines.append("<value>")
            lines.append(value)
            lines.append("</value>")
            lines.append(f"</{label}>")
            lines.append("")

        lines.append("</memory_blocks>")
        return "\n".join(lines)

    @staticmethod
    def _render_memory_metadata(archival_count: int, recall_count: int) -> str:
        """Render the <memory_metadata> section with current timestamp and counts."""
        now = datetime.now(timezone.utc).strftime("%Y-%m-%d %I:%M:%S %p UTC%z")
        lines = [
            "<memory_metadata>",
            f"- The current time is: {now}",
            f"- {recall_count} previous messages between you and the user are stored in recall memory",
            f"- {archival_count} total memories you created are stored in archival memory",
            "</memory_metadata>",
        ]
        return "\n".join(lines)

    @staticmethod
    def _render_recall_memory(messages: list[Any], passages: list[Any]) -> str:
        """Render the <recall_memory> section from recall messages and archival passages.

        Combines two sources of conversation history:
        - Legacy Letta recall messages (from when Letta was the execution engine)
        - Recent archival passages (conversation summaries persisted by our agent loop)

        Both are rendered chronologically so Nameless sees a continuous history.
        """
        lines = ["<recall_memory>", "Recent conversation history and archival memories:", ""]

        has_content = False

        # Render legacy recall messages
        if messages:
            has_content = True
            lines.append("--- Recall Messages ---")
            for msg in messages:
                msg_type = type(msg).__name__
                date_str = str(getattr(msg, "date", "")) if hasattr(msg, "date") else ""
                content = ""
                if hasattr(msg, "content"):
                    raw = msg.content
                    if isinstance(raw, str):
                        content = raw
                    elif isinstance(raw, list):
                        # TextBlock list — extract text parts
                        parts = []
                        for item in raw:
                            if hasattr(item, "text"):
                                parts.append(item.text)
                            else:
                                parts.append(str(item))
                        content = " ".join(parts)
                    else:
                        content = str(raw)

                # Determine role from message type
                if "User" in msg_type:
                    role = "User"
                elif "Assistant" in msg_type:
                    role = "Assistant"
                elif "System" in msg_type:
                    role = "System"
                elif "Tool" in msg_type:
                    role = "Tool"
                else:
                    role = msg_type

                # Truncate long content
                if len(content) > 1000:
                    content = content[:1000] + "..."

                if date_str:
                    lines.append(f"[{date_str}] {role}: {content}")
                else:
                    lines.append(f"{role}: {content}")
            lines.append("")

        # Render recent archival passages (conversation summaries)
        if passages:
            has_content = True
            lines.append("--- Recent Archival Memories ---")
            for passage in passages:
                text = getattr(passage, "text", str(passage)) or ""
                created = getattr(passage, "created_at", None)
                if created:
                    lines.append(f"[{created}] {text}")
                else:
                    lines.append(text)
            lines.append("")

        if not has_content:
            lines.append("(No previous conversation history found.)")
            lines.append("")

        lines.append("</recall_memory>")
        return "\n".join(lines)

    async def _get_archive_id(self) -> str | None:
        """Resolve and cache the agent's archive ID.

        Discovers the archive_id from existing passages, or by matching
        the agent name against the archives list (Letta names archives
        as "{agent_name}'s Archive").
        """
        if self._archive_id:
            return self._archive_id

        if not self.agent_id or not self._client:
            return None

        try:
            # Try to get it from an existing passage first (cheapest call)
            passages = await self._client.agents.passages.list(self.agent_id, limit=1)
            if passages and hasattr(passages[0], "archive_id"):
                self._archive_id = passages[0].archive_id
                return self._archive_id

            # Fallback: get agent name, then match against archives list
            agent_state = await self._client.agents.retrieve(self.agent_id)
            agent_name = getattr(agent_state, "name", "") or ""
            expected_archive_name = f"{agent_name}'s Archive"

            archives = await self._client.archives.list()
            items = archives.items if hasattr(archives, "items") else archives
            for archive in items:
                archive_name = getattr(archive, "name", "") or ""
                if archive_name == expected_archive_name:
                    self._archive_id = archive.id
                    return self._archive_id
        except Exception as e:
            logger.debug("Could not resolve archive_id: %s", e)

        return None

    async def persist_conversation(self, user_message: str, responses: list[dict[str, Any]]) -> None:
        """Persist a conversation summary to archival memory.

        Extracts the final assistant result from responses and stores a
        summary in archival memory via archives.passages.create (bypasses
        the agent LLM loop, only embeds + stores).

        Failures are logged but never raised — persistence is best-effort.
        """
        if not self.agent_id or not self._client:
            return

        try:
            # Extract result text from responses
            result_text = ""
            for resp in responses:
                if hasattr(resp, "result"):
                    result_text = resp.result
                elif isinstance(resp, dict) and "result" in resp:
                    result_text = resp["result"]

            timestamp = datetime.now(timezone.utc).isoformat()
            summary = (
                f"[Conversation {timestamp}]\n"
                f"User: {user_message[:500]}\n"
                f"Assistant: {result_text[:1500]}"
            )

            archive_id = await self._get_archive_id()
            if archive_id:
                await self._client.archives.passages.create(archive_id, text=summary)
            else:
                # Fallback for servers without archives API
                await self._client.agents.passages.create(self.agent_id, text=summary)
            logger.info("Persisted conversation summary to archival memory")

        except Exception as e:
            logger.warning("Failed to persist conversation to archival: %s", e)

    def _build_options(self, system_prompt: str) -> ClaudeAgentOptions:
        """Build Claude agent options with Letta MCP server."""
        mcp_server = create_letta_mcp_server(
            letta_client=self._client,
            agent_id=self.agent_id,
        )

        return ClaudeAgentOptions(
            system_prompt=system_prompt,
            mcp_servers={"letta": mcp_server},
            # allowed_tools is additive — permits MCP tools beyond the base set
            allowed_tools=[
                "mcp__letta__get_memory_block",
                "mcp__letta__update_memory_block",
                "mcp__letta__search_archival_memory",
                "mcp__letta__insert_archival_memory",
                "mcp__letta__list_memory_blocks",
                "mcp__letta__get_recent_messages",
            ],
            # disallowed_tools blocks from the default base set
            disallowed_tools=["Task", "Agent", "TaskOutput", "mcp__claude_ai_*"],
            # Load all MCP tools eagerly — only 6 Letta tools, well within
            # context budget. Avoids requiring ToolSearch for primary tools.
            env={
                "ENABLE_TOOL_SEARCH": "false",
                # Unset depleted API key so Claude Code uses Max credits
                "ANTHROPIC_API_KEY": "",
            },
            # Programmatic permission: approve APPROVED_TOOLS, deny all else
            can_use_tool=_check_tool_permission,
        )

    async def run(self, message: str) -> AsyncIterator[dict[str, Any]]:
        """Run the agent with a message and stream responses.

        This is a pure streaming method — it does NOT persist the conversation.
        Callers are responsible for calling `persist_conversation()` afterward.

        After completion, `self.last_prompt_length` contains the system
        prompt size used for this turn (useful for diagnostics).

        Args:
            message: The trigger message or user input.

        Yields:
            Response messages from the agent.
        """
        # Build system prompt if not provided
        system_prompt = self.system_prompt
        if system_prompt is None:
            system_prompt = await self.build_system_prompt()

        self.last_prompt_length = len(system_prompt)

        options = self._build_options(system_prompt)

        async with ClaudeSDKClient(options=options) as client:
            await client.query(message)
            async for msg in client.receive_response():
                yield msg

    async def run_and_collect(self, message: str) -> list[dict[str, Any]]:
        """Run the agent, collect all responses, and persist the conversation.

        Args:
            message: The trigger message or user input.

        Returns:
            List of all response messages.
        """
        responses: list[dict[str, Any]] = []
        async for msg in self.run(message):
            responses.append(msg)
        await self.persist_conversation(message, responses)
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
