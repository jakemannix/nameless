"""Periodic "perch time" trigger for Nameless.

Inspired by Strix's 2-hour tick cycles - moments for self-reflection,
memory consolidation, and autonomous thought.
"""

import logging
import time
from datetime import datetime

import schedule

from nameless.config import get_settings

logger = logging.getLogger(__name__)


class CronTrigger:
    """Handles periodic wakeup events for Nameless."""

    def __init__(self) -> None:
        self.settings = get_settings()
        self._running = False

    def perch_time(self) -> None:
        """Execute a perch time cycle.

        This is Nameless's moment for:
        - Reviewing recent memories
        - Consolidating learnings
        - Autonomous reflection
        - Deciding whether to reach out
        """
        timestamp = datetime.now().isoformat()
        logger.info(f"Perch time triggered at {timestamp}")

        # TODO: Integrate with Letta MCP to:
        # 1. Load core memory blocks
        # 2. Review recent archival memories
        # 3. Generate reflection
        # 4. Optionally trigger outreach (Discord, Bluesky)

        logger.info("Perch time cycle complete")

    def start(self) -> None:
        """Start the periodic scheduler."""
        interval = self.settings.triggers.perch_interval_hours
        logger.info(f"Starting perch time scheduler (every {interval} hours)")

        schedule.every(interval).hours.do(self.perch_time)

        # Run immediately on start
        self.perch_time()

        self._running = True
        while self._running:
            schedule.run_pending()
            time.sleep(60)  # Check every minute

    def stop(self) -> None:
        """Stop the scheduler."""
        self._running = False
        logger.info("Perch time scheduler stopped")


def main() -> None:
    """Entry point for the cron trigger."""
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )

    trigger = CronTrigger()
    try:
        trigger.start()
    except KeyboardInterrupt:
        trigger.stop()


if __name__ == "__main__":
    main()
