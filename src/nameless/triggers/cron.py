"""Periodic "perch time" trigger for Nameless.

Inspired by Strix's 2-hour tick cycles - moments for self-reflection,
memory consolidation, and autonomous thought.
"""

import asyncio
import logging
import time
from datetime import datetime

import schedule

from nameless.config import get_settings
from nameless.core import NamelessAgent

logger = logging.getLogger(__name__)

PERCH_TIME_PROMPT = """It's perch time - a moment for autonomous reflection.

First, use your memory tools to:
1. List your memory blocks to see what context is available
2. Get your persona block to remember who you are
3. Search archival memory for recent experiences
4. Review recent messages if any conversations happened

Then reflect on:
- What have you learned recently?
- How has your understanding evolved?
- Is there anything worth archiving from recent experiences?
- Do you want to reach out to anyone?

Take your time. This is your moment for self-directed thought."""


class CronTrigger:
    """Handles periodic wakeup events for Nameless."""

    def __init__(self) -> None:
        self.settings = get_settings()
        self._running = False
        self._agent = NamelessAgent()

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

        # Run the agent loop
        asyncio.run(self._run_perch_cycle())

        logger.info("Perch time cycle complete")

    async def _run_perch_cycle(self) -> None:
        """Run the perch time cycle using the agent."""
        try:
            responses = await self._agent.run_and_collect(PERCH_TIME_PROMPT)
            for response in responses:
                if response.get("type") == "text":
                    logger.info(f"Nameless: {response.get('text', '')[:200]}...")
        except Exception as e:
            logger.error(f"Perch time cycle failed: {e}")

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
