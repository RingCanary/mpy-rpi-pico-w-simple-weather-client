"""Database repository for telemetry data operations."""

import json
from datetime import datetime, timedelta, timezone

from asyncpg import Pool

from .models import HourlyReport, TelemetryIngest


class TelemetryRepository:
    """Repository for telemetry database operations."""

    def __init__(self, pool: Pool):
        self.pool = pool

    async def insert_reading(self, data: TelemetryIngest) -> bool:
        """Insert a telemetry reading. Returns True if inserted, False if duplicate."""
        async with self.pool.acquire() as conn:
            result = await conn.execute(
                """
                INSERT INTO readings (
                    device_id, device_ts, request_id, firmware,
                    temperature, humidity, pressure, gas,
                    raw_adc, voltage,
                    sensor_error,
                    stink_count, redirect_count, success_count,
                    total_requests, uptime_cycles, reset_count,
                    payload,
                    ingested_at
                ) VALUES (
                    $1, $2, $3, $4,
                    $5, $6, $7, $8,
                    $9, $10,
                    $11,
                    $12, $13, $14,
                    $15, $16, $17,
                    $18,
                    $19
                )
                ON CONFLICT (device_id, request_id) WHERE request_id IS NOT NULL DO NOTHING
                """,
                data.device_id,
                self._parse_device_ts(data.device_ts),
                data.request_id,
                data.firmware,
                data.temperature,
                data.humidity,
                data.pressure,
                data.gas,
                data.raw_adc,
                data.voltage,
                data.sensor_error,
                data.stink_count,
                data.redirect_count,
                data.success_count,
                data.total_requests,
                data.uptime_cycles,
                data.reset_count,
                json.dumps(data.model_dump(mode="json")),
                datetime.now(timezone.utc),
            )
            # ON CONFLICT DO NOTHING returns "INSERT 0 0" for duplicates, "INSERT 0 1" for success
            return result == "INSERT 0 1"

    def _parse_device_ts(self, ts: str | int | float | None) -> datetime | None:
        """Parse device timestamp to datetime."""
        if ts is None:
            return None
        try:
            if isinstance(ts, (int, float)):
                if ts > 1e12:
                    ts = ts / 1000
                return datetime.fromtimestamp(ts, tz=timezone.utc)
            if isinstance(ts, str):
                cleaned = ts.strip()
                if cleaned.isdigit():
                    return datetime.fromtimestamp(int(cleaned), tz=timezone.utc)
                if cleaned.endswith("Z"):
                    cleaned = cleaned[:-1] + "+00:00"
                try:
                    parsed = datetime.fromisoformat(cleaned)
                    if parsed.tzinfo is None:
                        return parsed.replace(tzinfo=timezone.utc)
                    return parsed.astimezone(timezone.utc)
                except ValueError:
                    pass

                for fmt in ["%Y-%m-%dT%H:%M:%S.%fZ", "%Y-%m-%dT%H:%M:%SZ", "%Y-%m-%d %H:%M:%S"]:
                    try:
                        return datetime.strptime(ts, fmt).replace(tzinfo=timezone.utc)
                    except ValueError:
                        continue
        except (ValueError, TypeError):
            pass
        return None

    async def get_last_reading(self, device_id: str) -> datetime | None:
        """Get the timestamp of the last reading for a device."""
        async with self.pool.acquire() as conn:
            return await conn.fetchval(
                "SELECT MAX(ingested_at) FROM readings WHERE device_id = $1",
                device_id,
            )

    async def get_latest_temperature(self, device_id: str) -> tuple[datetime | None, float | None]:
        """Get the latest temperature reading for a device (for HVAC alerts)."""
        async with self.pool.acquire() as conn:
            row = await conn.fetchrow(
                """
                SELECT ingested_at, temperature
                FROM readings
                WHERE device_id = $1 AND temperature IS NOT NULL
                ORDER BY ingested_at DESC
                LIMIT 1
                """,
                device_id,
            )
            if row:
                return row["ingested_at"], row["temperature"]
            return None, None

    async def get_devices_with_readings_since(self, since: datetime) -> list[str]:
        """Get list of device IDs that have readings since the given time."""
        async with self.pool.acquire() as conn:
            rows = await conn.fetch(
                "SELECT DISTINCT device_id FROM readings WHERE ingested_at >= $1",
                since,
            )
            return [row["device_id"] for row in rows]

    async def aggregate_hour(self, hour_start: datetime) -> list[HourlyReport]:
        """Aggregate readings for the previous hour and return reports."""
        hour_end = hour_start + timedelta(hours=1)
        async with self.pool.acquire() as conn:
            rows = await conn.fetch(
                """
                SELECT
                    device_id,
                    COUNT(*) as reading_count,
                    AVG(temperature) as avg_temperature,
                    MAX(temperature) as max_temperature,
                    MIN(temperature) as min_temperature,
                    AVG(humidity) as avg_humidity,
                    AVG(pressure) as avg_pressure,
                    AVG(gas) as avg_gas,
                    SUM(stink_count) as total_stink_count,
                    SUM(success_count) as total_success_count,
                    SUM(total_requests) as total_requests
                FROM readings
                WHERE ingested_at >= $1 AND ingested_at < $2
                GROUP BY device_id
                """,
                hour_start,
                hour_end,
            )
            return [
                HourlyReport(
                    device_id=row["device_id"],
                    hour_start=hour_start,
                    reading_count=row["reading_count"],
                    avg_temperature=row["avg_temperature"],
                    max_temperature=row["max_temperature"],
                    min_temperature=row["min_temperature"],
                    avg_humidity=row["avg_humidity"],
                    avg_pressure=row["avg_pressure"],
                    avg_gas=row["avg_gas"],
                    total_stink_count=row["total_stink_count"] or 0,
                    total_success_count=row["total_success_count"] or 0,
                    total_requests=row["total_requests"] or 0,
                )
                for row in rows
            ]

    async def insert_hourly_report(self, report: HourlyReport) -> None:
        """Insert an hourly report into the database."""
        async with self.pool.acquire() as conn:
            await conn.execute(
                """
                INSERT INTO hourly_reports (
                    device_id, hour_start, reading_count,
                    avg_temperature, max_temperature, min_temperature,
                    avg_humidity, avg_pressure, avg_gas,
                    total_stink_count, total_success_count, total_requests,
                    created_at
                ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13)
                ON CONFLICT (device_id, hour_start) DO UPDATE SET
                    reading_count = EXCLUDED.reading_count,
                    avg_temperature = EXCLUDED.avg_temperature,
                    max_temperature = EXCLUDED.max_temperature,
                    min_temperature = EXCLUDED.min_temperature,
                    avg_humidity = EXCLUDED.avg_humidity,
                    avg_pressure = EXCLUDED.avg_pressure,
                    avg_gas = EXCLUDED.avg_gas,
                    total_stink_count = EXCLUDED.total_stink_count,
                    total_success_count = EXCLUDED.total_success_count,
                    total_requests = EXCLUDED.total_requests,
                    created_at = EXCLUDED.created_at
                """,
                report.device_id,
                report.hour_start,
                report.reading_count,
                report.avg_temperature,
                report.max_temperature,
                report.min_temperature,
                report.avg_humidity,
                report.avg_pressure,
                report.avg_gas,
                report.total_stink_count,
                report.total_success_count,
                report.total_requests,
                datetime.now(timezone.utc),
            )

    async def get_alert_state(self, device_id: str) -> dict:
        """Get alert state for a device."""
        async with self.pool.acquire() as conn:
            row = await conn.fetchrow(
                """
                SELECT last_reading_at, last_alert_at, last_hvac_alert_at, alert_active,
                       COALESCE(stale_miss_count, 0) as stale_miss_count
                FROM alert_state WHERE device_id = $1
                """,
                device_id,
            )
            if row:
                return dict(row)
            return {
                "last_reading_at": None,
                "last_alert_at": None,
                "last_hvac_alert_at": None,
                "alert_active": False,
                "stale_miss_count": 0,
            }

    async def update_alert_state(
        self,
        device_id: str,
        last_reading_at: datetime | None = None,
        last_alert_at: datetime | None = None,
        last_hvac_alert_at: datetime | None = None,
        alert_active: bool | None = None,
        stale_miss_count: int | None = None,
    ) -> None:
        """Update alert state for a device."""
        async with self.pool.acquire() as conn:
            await conn.execute(
                """
                INSERT INTO alert_state (device_id, last_reading_at, last_alert_at, last_hvac_alert_at, alert_active, stale_miss_count)
                VALUES ($1, $2, $3, $4, $5, $6)
                ON CONFLICT (device_id) DO UPDATE SET
                    last_reading_at = COALESCE($2, alert_state.last_reading_at),
                    last_alert_at = COALESCE($3, alert_state.last_alert_at),
                    last_hvac_alert_at = COALESCE($4, alert_state.last_hvac_alert_at),
                    alert_active = COALESCE($5, alert_state.alert_active),
                    stale_miss_count = COALESCE($6, alert_state.stale_miss_count)
                """,
                device_id,
                last_reading_at,
                last_alert_at,
                last_hvac_alert_at,
                alert_active,
                stale_miss_count,
            )
