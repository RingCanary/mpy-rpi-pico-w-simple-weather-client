"""Environment-driven configuration using pydantic-settings."""

from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    # Database
    database_url: str = Field(
        default="postgresql://postgres:postgres@localhost:5432/telemetry",
        description="PostgreSQL connection URL",
    )

    # Server
    host: str = Field(default="0.0.0.0")
    port: int = Field(default=8000)
    api_key: str | None = Field(
        default=None, description="Optional API key for device authentication"
    )

    # Slack
    slack_webhook_url: str | None = Field(default=None, description="Slack incoming webhook URL")

    # Google Sheets
    google_sheets_spreadsheet_id: str | None = Field(
        default=None, description="Google Sheets spreadsheet ID"
    )
    google_service_account_json: str | None = Field(
        default=None, description="Path to service account JSON file"
    )

    # Google Apps Script webapp delivery (alternative to direct Sheets API)
    apps_script_webapp_url: str | None = Field(
        default=None, description="Google Apps Script webapp URL for hourly reports"
    )

    # Alert configuration
    inactivity_minutes: int = Field(
        default=5, description="Minutes without data before stale alert"
    )
    alert_cooldown_minutes: int = Field(default=30, description="Cooldown between repeated alerts")
    hvac_temp_threshold: float = Field(
        default=25.0, description="Temperature threshold for HVAC alert (C)"
    )
    hvac_alert_cooldown_minutes: int = Field(default=30, description="Cooldown between HVAC alerts")
    stale_consecutive_misses: int = Field(
        default=4, description="Consecutive stale checks required before alert"
    )

    # Required devices for stale alerts (comma-separated device IDs)
    required_devices: str = Field(
        default="", description="Comma-separated list of required device IDs"
    )

    # Scheduler
    monitor_interval_minutes: int = Field(
        default=1, description="Interval for monitor job in minutes"
    )
    report_interval_hours: int = Field(default=1, description="Interval for report job in hours")

    @property
    def required_device_ids(self) -> list[str]:
        """Parse required devices from comma-separated string."""
        if not self.required_devices:
            return []
        return [d.strip() for d in self.required_devices.split(",") if d.strip()]


@lru_cache
def get_settings() -> Settings:
    """Get cached settings instance."""
    return Settings()
