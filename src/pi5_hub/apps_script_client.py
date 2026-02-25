"""Google Apps Script webapp client for hourly report delivery."""

import hashlib
import logging
from datetime import datetime, timezone

import httpx

from .config import get_settings
from .models import HourlyReport

logger = logging.getLogger(__name__)


class AppsScriptClient:
    """Async client for posting hourly reports to Apps Script webapp."""

    def __init__(self, webapp_url: str | None = None):
        settings = get_settings()
        self.webapp_url = webapp_url or settings.apps_script_webapp_url
        self._client: httpx.AsyncClient | None = None

    async def _get_client(self) -> httpx.AsyncClient:
        """Get or create the HTTP client."""
        if self._client is None:
            self._client = httpx.AsyncClient(timeout=30.0, follow_redirects=True)
        return self._client

    async def close(self) -> None:
        """Close the HTTP client."""
        if self._client is not None:
            await self._client.aclose()
            self._client = None

    def _generate_request_id(self, device_id: str, hour_start: datetime) -> str:
        """Generate deterministic request_id per device+hour."""
        key = f"{device_id}:{hour_start.isoformat()}"
        return hashlib.sha256(key.encode()).hexdigest()[:16]

    def _build_payload(self, report: HourlyReport) -> dict:
        """Build payload compatible with Apps Script doPost behavior."""
        request_id = self._generate_request_id(report.device_id, report.hour_start)

        # Base payload fields always included
        payload = {
            "device_id": report.device_id,
            "device_ts": report.hour_start.isoformat(),
            "firmware": "pi5_hub_hourly",
            "request_id": request_id,
        }

        # Device-type specific fields
        if "pico" in report.device_id.lower():
            # Pico-like device: include raw_adc=None, voltage=None, temperature only
            payload["raw_adc"] = None
            payload["voltage"] = None
            payload["temperature"] = report.avg_temperature
        else:
            # Other devices: include environmental sensors
            payload["temperature"] = report.avg_temperature
            payload["humidity"] = report.avg_humidity
            payload["pressure"] = report.avg_pressure
            payload["gas"] = report.avg_gas / 1000.0 if report.avg_gas is not None else None

        # Counter fields
        payload["stink_count"] = report.total_stink_count
        payload["total_stink_count"] = report.total_stink_count
        payload["success_count"] = report.total_success_count
        payload["total_success_count"] = report.total_success_count
        payload["total_requests"] = report.total_requests
        payload["uptime_cycles"] = report.reading_count
        payload["reset_count"] = 0

        return payload

    async def send_hourly_report(self, report: HourlyReport) -> bool:
        """Send hourly report to Apps Script webapp. Returns True if successful."""
        if not self.webapp_url:
            logger.warning("Apps Script webapp URL not configured, skipping")
            return False

        payload = self._build_payload(report)

        try:
            client = await self._get_client()
            response = await client.post(self.webapp_url, json=payload)

            if response.status_code >= 200 and response.status_code < 300:
                logger.info(
                    f"Apps Script report sent for {report.device_id}: status={response.status_code}"
                )
                return True
            else:
                logger.error(
                    f"Apps Script report failed for {report.device_id}: "
                    f"status={response.status_code}, body={response.text[:200]}"
                )
                return False
        except httpx.TimeoutException:
            logger.error(f"Apps Script timeout for {report.device_id}")
            return False
        except httpx.RequestError as e:
            logger.error(f"Apps Script request error for {report.device_id}: {e}")
            return False
        except Exception as e:
            logger.error(f"Apps Script unexpected error for {report.device_id}: {e}")
            return False


def get_apps_script_client() -> AppsScriptClient | None:
    """Get an Apps Script client instance if configured."""
    settings = get_settings()
    if settings.apps_script_webapp_url:
        return AppsScriptClient()
    return None
