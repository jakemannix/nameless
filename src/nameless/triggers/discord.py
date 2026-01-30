"""Discord bot trigger for Nameless.

Handles Discord events like messages, mentions, and commands.
"""

import logging

from nameless.config import get_settings

logger = logging.getLogger(__name__)


class DiscordTrigger:
    """Handles Discord bot events for Nameless.

    Placeholder implementation - requires discord.py optional dependency.
    """

    def __init__(self) -> None:
        self.settings = get_settings()

    async def on_message(self, message_content: str, author: str, channel: str) -> str | None:
        """Handle incoming Discord messages.

        Args:
            message_content: The message text
            author: Message author's username
            channel: Channel name or ID

        Returns:
            Response to send, or None if no response
        """
        logger.info(f"Discord message from {author} in {channel}: {message_content[:50]}...")

        # TODO: Integrate with Letta MCP to:
        # 1. Store message in archival memory
        # 2. Generate response using core memory context
        # 3. Return response

        return None

    async def on_mention(self, message_content: str, author: str, channel: str) -> str:
        """Handle direct mentions of Nameless.

        Args:
            message_content: The message text
            author: Message author's username
            channel: Channel name or ID

        Returns:
            Response to the mention
        """
        logger.info(f"Discord mention from {author} in {channel}")

        # TODO: Always respond to direct mentions
        return "I'm still waking up... my memory system is being configured."

    def start(self) -> None:
        """Start the Discord bot.

        Raises:
            ImportError: If discord.py is not installed
        """
        if not self.settings.discord.bot_token:
            raise ValueError("DISCORD_BOT_TOKEN not configured")

        try:
            import discord  # noqa: F401
        except ImportError as e:
            raise ImportError("Install discord.py: pip install 'nameless[discord]'") from e

        # TODO: Implement full Discord bot with intents
        logger.info("Discord trigger not yet implemented")


def main() -> None:
    """Entry point for the Discord trigger."""
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )

    trigger = DiscordTrigger()
    trigger.start()


if __name__ == "__main__":
    main()
