"""Tests for configuration module."""

import os
from unittest.mock import patch

from nameless.config import Settings, get_settings


def test_default_settings():
    """Test that default settings are populated correctly."""
    with patch.dict(os.environ, {}, clear=True):
        settings = Settings()

        assert settings.letta.base_url == "http://localhost:8283"
        assert settings.letta.password is None
        assert settings.agent.agent_id is None
        assert settings.triggers.perch_interval_hours == 2


def test_settings_from_env():
    """Test that settings are loaded from environment variables."""
    env = {
        "LETTA_BASE_URL": "http://custom:9000",
        "LETTA_PASSWORD": "secret",
        "NAMELESS_AGENT_ID": "agent-123",
        "BLUESKY_HANDLE": "test.bsky.social",
        "PERCH_INTERVAL_HOURS": "4",
    }

    with patch.dict(os.environ, env, clear=True):
        settings = Settings()

        assert settings.letta.base_url == "http://custom:9000"
        assert settings.letta.password == "secret"
        assert settings.agent.agent_id == "agent-123"
        assert settings.bluesky.handle == "test.bsky.social"
        assert settings.triggers.perch_interval_hours == 4


def test_get_settings_cached():
    """Test that get_settings returns cached instance."""
    get_settings.cache_clear()

    settings1 = get_settings()
    settings2 = get_settings()

    assert settings1 is settings2
