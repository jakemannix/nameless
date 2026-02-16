"""Trigger handlers for Nameless agent.

Triggers are the entry points that wake Nameless up:
- cron: Periodic "perch time" wakeups for self-reflection
- discord: Discord bot events and commands
- bluesky: Bluesky notifications and mentions

Imports are lazy to avoid pulling in optional dependencies
(discord.py, atproto) when only one trigger is needed.
"""

__all__ = ["DiscordTrigger", "BlueskyTrigger"]


def __getattr__(name: str):
    if name == "BlueskyTrigger":
        from nameless.triggers.bluesky import BlueskyTrigger
        return BlueskyTrigger
    if name == "DiscordTrigger":
        from nameless.triggers.discord import DiscordTrigger
        return DiscordTrigger
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
