"""Slack client for sending alerts and reports."""

import logging

import httpx

from .config import get_settings

logger = logging.getLogger(__name__)


class SlackClient:
    """Client for posting messages to Slack via webhook."""

    def __init__(self, webhook_url: str | None = None):
        self.webhook_url = webhook_url or get_settings().slack_webhook_url

    async def post_message(self, text: str) -> bool:
        """Post a message to Slack. Returns True if successful."""
        if not self.webhook_url:
            logger.warning("Slack webhook URL not configured, skipping message")
            return False

        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    self.webhook_url,
                    json={"text": text},
                    timeout=10.0,
                )
                if response.status_code < 200 or response.status_code >= 300:
                    logger.error(f"Slack webhook returned {response.status_code}: {response.text}")
                    return False
                logger.info("Slack message sent successfully")
                return True
        except httpx.HTTPError as e:
            logger.error(f"Failed to send Slack message: {e}")
            return False

    async def send_stale_alert(
        self, device_id: str, minutes_stalled: int, sheet_url: str | None = None
    ) -> bool:
        """Send stale data alert."""
        msg = (
            f":warning: Data stream stalled\n"
            f"* {device_id}: no new rows for {minutes_stalled} min\n"
            f"Possible causes: Wi-Fi drop, device loop issue, or power interruption"
        )
        if sheet_url:
            msg += f"\nSheet: {sheet_url}"
        return await self.post_message(msg)

    async def send_recovery_alert(self, device_id: str) -> bool:
        """Send recovery notification."""
        return await self.post_message(f":white_check_mark: Data resumed for {device_id}")

    async def send_hvac_alert(
        self, device_id: str, temperature: float, threshold: float, sheet_url: str | None = None
    ) -> bool:
        """Send HVAC temperature alert."""
        msg = f":thermometer: HVAC failure alert: Temperature {temperature:.2f}C (threshold: {threshold}C) on {device_id}"
        if sheet_url:
            msg += f"\nSheet: {sheet_url}"
        return await self.post_message(msg)

    async def send_hourly_report(self, device_id: str, report_data: dict) -> bool:
        """Send hourly weather report."""
        lines = [f":sun_small_cloud: Hourly report for {device_id}"]
        if report_data.get("avg_temperature") is not None:
            lines.append(
                f"* Temp: {report_data['avg_temperature']:.1f}C (max: {report_data.get('max_temperature', 'N/A')}, min: {report_data.get('min_temperature', 'N/A')})"
            )
        if report_data.get("avg_humidity") is not None:
            lines.append(f"* Humidity: {report_data['avg_humidity']:.1f}%")
        if report_data.get("avg_pressure") is not None:
            lines.append(f"* Pressure: {report_data['avg_pressure']:.1f} hPa")
        if report_data.get("avg_gas") is not None:
            lines.append(f"* Gas: {report_data['avg_gas']:.1f} kOhms")
        lines.append(f"* Readings: {report_data.get('reading_count', 0)}")
        return await self.post_message("\n".join(lines))


def get_slack_client() -> SlackClient:
    """Get a Slack client instance."""
    return SlackClient()
