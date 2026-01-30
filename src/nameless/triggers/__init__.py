"""Trigger handlers for Nameless agent.

Triggers are the entry points that wake Nameless up:
- cron: Periodic "perch time" wakeups for self-reflection
- discord: Discord bot events and commands
- bluesky: Bluesky notifications and mentions
"""

from nameless.triggers.bluesky import BlueskyTrigger
from nameless.triggers.cron import CronTrigger
from nameless.triggers.discord import DiscordTrigger

__all__ = ["CronTrigger", "DiscordTrigger", "BlueskyTrigger"]
