"""Configuration management for Nameless agent.

Loads settings from environment variables with sensible defaults for local development.
"""

from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class LettaConfig(BaseSettings):
    """Letta server connection settings."""

    model_config = SettingsConfigDict(env_prefix="LETTA_", env_file=".env", extra="ignore")

    base_url: str = Field(default="http://localhost:8283", description="Letta server URL")
    api_key: str | None = Field(default=None, description="Letta API key for authentication")


class AgentConfig(BaseSettings):
    """Nameless agent-specific settings."""

    model_config = SettingsConfigDict(env_prefix="NAMELESS_", env_file=".env", extra="ignore")

    agent_id: str | None = Field(default=None, description="Letta agent ID (set after import)")


class BlueskyConfig(BaseSettings):
    """Bluesky/AT Protocol settings."""

    model_config = SettingsConfigDict(env_prefix="BLUESKY_", env_file=".env", extra="ignore")

    handle: str | None = Field(default=None, description="Bluesky handle (e.g., user.bsky.social)")
    app_password: str | None = Field(default=None, description="Bluesky app password")


class DiscordConfig(BaseSettings):
    """Discord bot settings."""

    model_config = SettingsConfigDict(env_prefix="DISCORD_", env_file=".env", extra="ignore")

    bot_token: str | None = Field(default=None, description="Discord bot token")
    guild_id: str | None = Field(default=None, description="Primary Discord guild/server ID")


class TriggerConfig(BaseSettings):
    """Trigger/scheduler settings."""

    model_config = SettingsConfigDict(env_prefix="", env_file=".env", extra="ignore")

    perch_interval_hours: int = Field(default=2, description="Hours between perch time wakeups")


class Settings(BaseSettings):
    """Aggregated settings for Nameless agent."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    letta: LettaConfig = Field(default_factory=LettaConfig)
    agent: AgentConfig = Field(default_factory=AgentConfig)
    bluesky: BlueskyConfig = Field(default_factory=BlueskyConfig)
    discord: DiscordConfig = Field(default_factory=DiscordConfig)
    triggers: TriggerConfig = Field(default_factory=TriggerConfig)

    # API Keys
    anthropic_api_key: str | None = Field(default=None, alias="ANTHROPIC_API_KEY")
    openai_api_key: str | None = Field(default=None, alias="OPENAI_API_KEY")


@lru_cache
def get_settings() -> Settings:
    """Get cached settings instance."""
    return Settings()
