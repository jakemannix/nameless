"""Bluesky trigger for Nameless.

Handles Bluesky notifications, mentions, and posting.
Uses the AT Protocol via the atproto library.
"""

import logging
from datetime import UTC, datetime

from nameless.config import get_settings

logger = logging.getLogger(__name__)


class BlueskyTrigger:
    """Handles Bluesky/AT Protocol interactions for Nameless."""

    def __init__(self) -> None:
        self.settings = get_settings()
        self._client = None

    def _get_client(self):
        """Get or create authenticated Bluesky client."""
        if self._client is not None:
            return self._client

        if not self.settings.bluesky.handle or not self.settings.bluesky.app_password:
            raise ValueError("BLUESKY_HANDLE and BLUESKY_APP_PASSWORD must be configured")

        from atproto import Client

        self._client = Client()
        self._client.login(self.settings.bluesky.handle, self.settings.bluesky.app_password)
        logger.info(f"Authenticated to Bluesky as {self.settings.bluesky.handle}")

        return self._client

    def post(self, text: str) -> str:
        """Post a skeet to Bluesky.

        Args:
            text: The post content (max 300 characters)

        Returns:
            URI of the created post
        """
        if len(text) > 300:
            logger.warning(f"Post truncated from {len(text)} to 300 characters")
            text = text[:297] + "..."

        client = self._get_client()
        response = client.send_post(text=text)

        logger.info(f"Posted to Bluesky: {text[:50]}...")
        return response.uri

    def check_notifications(self) -> list[dict]:
        """Check for new notifications (mentions, replies, etc.).

        Returns:
            List of notification dicts with relevant info
        """
        client = self._get_client()

        # Get unread notifications
        response = client.app.bsky.notification.list_notifications()

        notifications = []
        for notif in response.notifications:
            if not notif.is_read:
                notifications.append(
                    {
                        "reason": notif.reason,  # 'mention', 'reply', 'like', etc.
                        "author": notif.author.handle,
                        "uri": notif.uri,
                        "indexed_at": notif.indexed_at,
                    }
                )

        if notifications:
            logger.info(f"Found {len(notifications)} unread notifications")

        return notifications

    def get_post_thread(self, uri: str) -> dict:
        """Get a post and its thread context.

        Args:
            uri: AT Protocol URI of the post

        Returns:
            Thread data including parent and replies
        """
        client = self._get_client()
        response = client.app.bsky.feed.get_post_thread({"uri": uri})
        return response.thread

    async def handle_mention(self, notification: dict) -> str | None:
        """Handle a mention notification.

        Args:
            notification: Notification data from check_notifications

        Returns:
            Response text to post, or None if no response
        """
        logger.info(f"Handling mention from {notification['author']}")

        # TODO: Integrate with Letta MCP to:
        # 1. Fetch the post content
        # 2. Store in archival memory
        # 3. Generate contextual response
        # 4. Post reply

        return None

    def poll_and_respond(self) -> None:
        """Poll for notifications and respond to mentions.

        This is the main loop for Bluesky interaction.
        """
        logger.info(f"Polling Bluesky at {datetime.now(UTC).isoformat()}")

        notifications = self.check_notifications()

        for notif in notifications:
            if notif["reason"] == "mention":
                # TODO: Handle asynchronously
                logger.info(f"Would respond to mention from {notif['author']}")

        # Mark notifications as read
        if notifications:
            client = self._get_client()
            client.app.bsky.notification.update_seen(
                {"seen_at": datetime.now(UTC).isoformat()}
            )


def main() -> None:
    """Entry point for Bluesky trigger testing."""
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )

    trigger = BlueskyTrigger()
    trigger.poll_and_respond()


if __name__ == "__main__":
    main()
