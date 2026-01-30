"""Tests for configuration module."""

import os
from unittest.mock import patch

from nameless.config import Settings, get_settings


def test_env_overrides_defaults():
    """Test that environment variables override any defaults or .env values."""
    env = {
        "LETTA_BASE_URL": "http://test-override:9999",
        "LETTA_API_KEY": "test-key",
    }

    with patch.dict(os.environ, env):
        settings = Settings()
        # Env vars should take precedence over .env file
        assert settings.letta.base_url == "http://test-override:9999"
        assert settings.letta.api_key == "test-key"


def test_settings_from_env():
    """Test that settings are loaded from environment variables."""
    env = {
        "LETTA_BASE_URL": "http://custom:9000",
        "LETTA_API_KEY": "secret",
        "NAMELESS_AGENT_ID": "agent-123",
        "BLUESKY_HANDLE": "test.bsky.social",
        "PERCH_INTERVAL_HOURS": "4",
    }

    with patch.dict(os.environ, env, clear=True):
        settings = Settings()

        assert settings.letta.base_url == "http://custom:9000"
        assert settings.letta.api_key == "secret"
        assert settings.agent.agent_id == "agent-123"
        assert settings.bluesky.handle == "test.bsky.social"
        assert settings.triggers.perch_interval_hours == 4


def test_get_settings_cached():
    """Test that get_settings returns cached instance."""
    get_settings.cache_clear()

    settings1 = get_settings()
    settings2 = get_settings()

    assert settings1 is settings2
