"""Configuration management using pydantic-settings."""

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    model_config = SettingsConfigDict(
        env_prefix="XERT_",
        env_file=".env",
        env_file_encoding="utf-8",
    )

    # Xert credentials
    username: str = Field(description="Xert account username/email")
    password: str = Field(description="Xert account password")

    # Home Assistant webhook
    ha_url: str = Field(
        default="http://homeassistant:8123",
        description="Home Assistant base URL",
    )
    ha_webhook_id: str = Field(description="Webhook ID configured in Home Assistant")
    ha_token: str = Field(
        default="",
        description="Home Assistant long-lived access token (optional)",
    )

    # Polling intervals (seconds)
    training_info_interval: int = Field(
        default=900,
        description="Training info poll interval (seconds), default 15 min",
    )
    activities_interval: int = Field(
        default=900,
        description="Activities poll interval (seconds), default 15 min",
    )

    # Activity lookback period
    lookback_days: int = Field(
        default=90,
        description="Number of days of activities to fetch",
    )

    # Token refresh margin (seconds before expiry to refresh)
    token_refresh_margin: int = Field(
        default=300,
        description="Refresh tokens this many seconds before expiry",
    )

    # Token storage path
    token_file: str = Field(
        default="/data/tokens.json",
        description="Path to store OAuth tokens",
    )

    # Logging
    log_level: str = Field(
        default="INFO",
        description="Logging level",
    )


def get_settings() -> Settings:
    """Get application settings."""
    return Settings()
