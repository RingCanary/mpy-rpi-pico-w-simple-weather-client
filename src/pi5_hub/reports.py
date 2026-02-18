"""Hourly report generation and distribution."""

import asyncio
import logging
from datetime import datetime, timedelta, timezone

from .apps_script_client import AppsScriptClient, get_apps_script_client
from .models import HourlyReport
from .repository import TelemetryRepository
from .sheets_client import SheetsClient, get_sheets_client
from .slack_client import SlackClient

logger = logging.getLogger(__name__)


class ReportGenerator:
    """Generator for hourly telemetry reports."""

    def __init__(
        self,
        repo: TelemetryRepository,
        slack: SlackClient,
        sheets: SheetsClient | None = None,
        apps_script: AppsScriptClient | None = None,
    ):
        self.repo = repo
        self.slack = slack
        self.sheets = sheets or get_sheets_client()
        self.apps_script = apps_script or get_apps_script_client()

    async def generate_hourly_report(
        self, hour_start: datetime | None = None
    ) -> list[HourlyReport]:
        """Generate and distribute hourly reports."""
        if hour_start is None:
            now = datetime.now(timezone.utc)
            hour_start = now.replace(minute=0, second=0, microsecond=0) - timedelta(hours=1)

        reports = await self.repo.aggregate_hour(hour_start)

        for report in reports:
            try:
                await self._distribute_report(report)
            except Exception as e:
                logger.error(f"Failed to distribute report for {report.device_id}: {e}")

        return reports

    async def _distribute_report(self, report: HourlyReport) -> None:
        """Distribute a report to Slack and Sheets/Apps Script."""
        await self.repo.insert_hourly_report(report)

        report_data = {
            "hour_start": report.hour_start.isoformat(),
            "device_id": report.device_id,
            "reading_count": report.reading_count,
            "avg_temperature": report.avg_temperature,
            "max_temperature": report.max_temperature,
            "min_temperature": report.min_temperature,
            "avg_humidity": report.avg_humidity,
            "avg_pressure": report.avg_pressure,
            "avg_gas": report.avg_gas,
            "total_stink_count": report.total_stink_count,
            "total_success_count": report.total_success_count,
            "total_requests": report.total_requests,
        }

        # Always send to Slack
        await self.slack.send_hourly_report(report.device_id, report_data)

        # Prefer Apps Script webapp if configured, fallback to direct Sheets API
        if self.apps_script:
            try:
                success = await self.apps_script.send_hourly_report(report)
                if success:
                    logger.info(f"Hourly report sent via Apps Script for {report.device_id}")
                # Fail-soft: log error already in client
            except Exception as e:
                logger.error(f"Apps Script delivery failed for {report.device_id}: {e}")
        elif self.sheets:
            try:
                await asyncio.to_thread(self.sheets.ensure_headers, "Hourly Reports")
                await asyncio.to_thread(self.sheets.append_hourly_report, report_data)
                logger.info(f"Hourly report appended to Sheets for {report.device_id}")
            except Exception as e:
                logger.error(f"Sheets delivery failed for {report.device_id}: {e}")
        else:
            logger.debug(f"No Sheets/Apps Script configured for {report.device_id}")

        logger.info(f"Hourly report distributed for {report.device_id}")

    async def send_latest_summary(self, device_id: str) -> dict | None:
        """Send a quick summary of the latest reading for a device."""
        ts, temp = await self.repo.get_latest_temperature(device_id)
        if temp is None:
            return None

        report_data = {
            "device_id": device_id,
            "avg_temperature": temp,
            "reading_count": 1,
        }
        await self.slack.send_hourly_report(device_id, report_data)
        return {"device_id": device_id, "temperature": temp, "timestamp": ts}
