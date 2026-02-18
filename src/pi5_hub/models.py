"""Pydantic models for API validation and serialization."""

from datetime import datetime
import math
from typing import Any

from pydantic import BaseModel, Field, field_validator


class TelemetryIngest(BaseModel):
    """Incoming telemetry data from Pico W or ESP32-C6."""

    device_id: str = Field(..., min_length=1, max_length=100)
    device_ts: str | int | float | None = None
    request_id: str | None = Field(default=None, max_length=100)
    firmware: str | None = None
    sensor_error: str | None = None

    # ESP32-C6 environmental sensors
    temperature: float | None = None
    humidity: float | None = None
    pressure: float | None = None
    gas: float | None = None

    # Pico W specific
    raw_adc: int | None = None
    voltage: float | None = None

    # Tracking metrics
    stink_count: int = Field(default=0, ge=0)
    redirect_count: int = Field(default=0, ge=0)
    success_count: int = Field(default=0, ge=0)
    total_requests: int = Field(default=0, ge=0)
    uptime_cycles: int = Field(default=0, ge=0)
    reset_count: int = Field(default=0, ge=0)

    @field_validator("temperature", "humidity", "pressure", "gas", "voltage", mode="before")
    @classmethod
    def validate_numeric(cls, v: Any) -> float | None:
        if v is None or v == "":
            return None
        try:
            n = float(v)
            if not math.isfinite(n):
                return None
            return n
        except (ValueError, TypeError):
            return None

    @property
    def is_pico_w(self) -> bool:
        """Check if this is Pico W data based on device_id."""
        return "pico_w" in self.device_id.lower()


class TelemetryResponse(BaseModel):
    """Response for successful telemetry ingestion."""

    status: str = "success"
    timestamp: str
    device_id: str
    cached: bool = False


class HourlyReport(BaseModel):
    """Aggregated hourly report for a device."""

    device_id: str
    hour_start: datetime
    reading_count: int
    avg_temperature: float | None
    max_temperature: float | None
    min_temperature: float | None
    avg_humidity: float | None
    avg_pressure: float | None
    avg_gas: float | None
    total_stink_count: int
    total_success_count: int
    total_requests: int


class AlertState(BaseModel):
    """State for tracking alerts per device."""

    last_reading_at: datetime | None = None
    last_alert_at: datetime | None = None
    last_hvac_alert_at: datetime | None = None
    alert_active: bool = False
    stale_miss_count: int = 0
