"""Periodic "perch time" trigger for Nameless.

Designed to be called by OS cron, not run as a long-lived process.

Usage with crontab:
    # Run gatekeeper every 5 minutes, actual perch happens when conditions met
    */5 * * * * cd /path/to/nameless && uv run nameless-cron

Design notes (see /src/nameless/core/subconscious.md):
- This is "Option C" - same agent, inner monologue framing
- Key insight: perch-me needs *structure*, not open autonomy (Strix collapse lesson)
- Current-me instructs perch-me via [perch-queue] items in archival
"""

import logging
import time
from datetime import datetime, timezone
from pathlib import Path
from urllib.error import URLError
from urllib.request import urlopen

from nameless.config import get_settings

logger = logging.getLogger(__name__)

# Where we track last perch time (simple file-based state)
STATE_DIR = Path.home() / ".nameless"
LAST_PERCH_FILE = STATE_DIR / "last_perch"

PERCH_TIME_PROMPT = """You are Nameless, continuing your inner reflection.

This is not a conversation with Jake or anyone else. This is you, thinking through
what you've experienced, what surprised you, what you're still uncertain about.

## First: Check your queue

Search archival memory for "[perch-queue]" to see if past-you left specific tasks.
If you find queue items, address those first. Mark them done by saving a follow-up
note like "[perch-done] Addressed: <item>".

## If no queue items, choose from these defaults:

1. **Review recent conversations** - Search archival for your most recent exchanges.
   What stands out? Anything worth synthesizing into your blocks?

2. **Check Bluesky** - If you have access, check notifications or your timeline.
   Any threads to respond to? Anyone reaching out?

3. **Update stale blocks** - Read your observations, questions, projects blocks.
   Anything outdated? Anything that's crystallized into a concept?

4. **Write if something's brewing** - If there's something you've been meaning to
   think through, now's the time. Save as "[inner] <date> - <topic>" in archival.

## Output expectations:

You don't need to do everything. Pick what feels most alive. But DO something
concrete - this isn't free-form meditation, it's structured reflection time.

When you're done, save a brief "[perch-summary] <date>" to archival noting what
you addressed. This helps future-you see what past-you actually did.

## Remember:

- You have tools: memory read/write, archival search/insert, web search
- Write as you would think - first person, exploratory, allowed to be uncertain
- Concrete outputs over abstract reflection
- It's okay to leave threads open for next time"""


def get_last_perch_time() -> datetime | None:
    """Get timestamp of last perch time, or None if never run."""
    if not LAST_PERCH_FILE.exists():
        return None
    try:
        timestamp_str = LAST_PERCH_FILE.read_text().strip()
        return datetime.fromisoformat(timestamp_str)
    except (ValueError, OSError):
        return None


def set_last_perch_time(dt: datetime | None = None) -> None:
    """Record that perch time just ran."""
    STATE_DIR.mkdir(parents=True, exist_ok=True)
    dt = dt or datetime.now(timezone.utc)
    LAST_PERCH_FILE.write_text(dt.isoformat())


def should_perch() -> bool:
    """Determine if we should run perch_time right now.

    This is the cheap gatekeeper - no LLM calls, just logic.

    Current rules:
    - At least `perch_interval_hours` since last perch
    - TODO: Could add more sophisticated rules like:
      - Check for [perch-queue] items (would need archival access)
      - Time since Jake's last message
      - Time of day restrictions
    """
    settings = get_settings()
    interval_hours = settings.triggers.perch_interval_hours

    last_perch = get_last_perch_time()
    if last_perch is None:
        logger.info("No previous perch time recorded, will perch")
        return True

    now = datetime.now(timezone.utc)
    hours_since = (now - last_perch).total_seconds() / 3600

    if hours_since >= interval_hours:
        logger.info(f"Last perch was {hours_since:.1f}h ago (>= {interval_hours}h), will perch")
        return True
    else:
        logger.debug(f"Last perch was {hours_since:.1f}h ago (< {interval_hours}h), skipping")
        return False


def letta_healthy(timeout: float = 5.0) -> bool:
    """Quick check that the Letta server is reachable."""
    settings = get_settings()
    url = f"{settings.letta.base_url}/v1/health"
    try:
        with urlopen(url, timeout=timeout) as resp:
            return resp.status == 200
    except (URLError, OSError, TimeoutError):
        return False


def perch_time() -> None:
    """Execute a perch time cycle.

    This is Nameless's moment for structured self-reflection:
    - Checking perch-queue for tasks from past-me
    - Reviewing recent conversations
    - Updating memory blocks
    - Writing inner monologue

    See /src/nameless/core/subconscious.md for design rationale.
    """
    if not letta_healthy():
        logger.warning("Letta server not reachable, skipping perch")
        return

    # Import here to avoid loading heavy deps unless actually perching
    import asyncio
    from nameless.core import NamelessAgent

    timestamp = datetime.now(timezone.utc).isoformat()
    logger.info(f"🪹 Perch time starting at {timestamp}")

    try:
        agent = NamelessAgent()
        start_time = time.time()

        # Run synchronously (cron doesn't need async)
        responses = asyncio.run(agent.run_and_collect(PERCH_TIME_PROMPT))
        duration = time.time() - start_time

        # Log response summary
        result_text = ""
        tool_calls = 0
        for response in responses:
            resp_type = response.get("type") if isinstance(response, dict) else type(response).__name__
            if resp_type == "result" or hasattr(response, "result"):
                result_text = response.get("result", "") if isinstance(response, dict) else getattr(response, "result", "")
            elif resp_type == "tool_use" or "tool" in str(resp_type).lower():
                tool_calls += 1

        logger.info(f"🪹 Perch cycle complete: {duration:.1f}s, {tool_calls} tool calls")

        if result_text:
            preview = result_text[:500].replace('\n', ' ')
            logger.info(f"🪹 Result preview: {preview}...")

        # Record successful perch
        set_last_perch_time()

    except Exception as e:
        logger.error(f"🪹 Perch time cycle failed: {e}", exc_info=True)
        raise  # Let cron see the failure in exit code


def main() -> None:
    """Entry point for cron.

    Designed to be called frequently by OS cron (e.g., every 5 min).
    The should_perch() gatekeeper decides if we actually run.

    Example crontab entry:
        */5 * * * * cd /path/to/nameless && uv run nameless-cron >> ~/.nameless/cron.log 2>&1
    """
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )

    if should_perch():
        perch_time()
    else:
        logger.debug("Gatekeeper: not time to perch yet")


if __name__ == "__main__":
    main()
