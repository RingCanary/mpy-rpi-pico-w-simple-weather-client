"""Google Sheets client for appending report rows."""

import logging
from pathlib import Path

from google.oauth2 import service_account
from googleapiclient.discovery import Resource, build

from .config import get_settings

logger = logging.getLogger(__name__)


class SheetsClient:
    """Client for writing to Google Sheets."""

    SCOPES = ["https://www.googleapis.com/auth/spreadsheets"]

    def __init__(
        self,
        spreadsheet_id: str | None = None,
        service_account_path: str | None = None,
    ):
        settings = get_settings()
        self.spreadsheet_id = spreadsheet_id or settings.google_sheets_spreadsheet_id
        self.service_account_path = service_account_path or settings.google_service_account_json
        self._service: Resource | None = None

    def _get_credentials(self):
        """Get Google service account credentials."""
        if not self.service_account_path:
            raise ValueError("Service account JSON path not configured")

        path = Path(self.service_account_path)
        if not path.exists():
            raise FileNotFoundError(f"Service account file not found: {path}")

        return service_account.Credentials.from_service_account_file(
            str(path),
            scopes=self.SCOPES,
        )

    @property
    def service(self) -> Resource:
        """Get or create the Google Sheets service."""
        if self._service is None:
            if not self.spreadsheet_id:
                raise ValueError("Spreadsheet ID not configured")
            creds = self._get_credentials()
            self._service = build("sheets", "v4", credentials=creds)
        return self._service

    def append_row(self, sheet_name: str, values: list) -> bool:
        """Append a row to a sheet. Returns True if successful."""
        if not self.spreadsheet_id:
            logger.warning("Google Sheets spreadsheet ID not configured, skipping append")
            return False

        try:
            body = {"values": [values]}
            result = (
                self.service.spreadsheets()
                .values()
                .append(
                    spreadsheetId=self.spreadsheet_id,
                    range=f"{sheet_name}!A1",
                    valueInputOption="USER_ENTERED",
                    insertDataOption="INSERT_ROWS",
                    body=body,
                )
                .execute()
            )
            logger.info(
                f"Appended row to {sheet_name}: {result.get('updates', {}).get('updatedRows', 0)} rows"
            )
            return True
        except Exception as e:
            logger.error(f"Failed to append row to Google Sheets: {e}")
            return False

    def append_hourly_report(self, report: dict) -> bool:
        """Append hourly report to the Hourly Reports sheet."""
        values = [
            report.get("hour_start", ""),
            report.get("device_id", ""),
            report.get("reading_count", 0),
            report.get("avg_temperature", ""),
            report.get("max_temperature", ""),
            report.get("min_temperature", ""),
            report.get("avg_humidity", ""),
            report.get("avg_pressure", ""),
            report.get("avg_gas", ""),
            report.get("total_stink_count", 0),
            report.get("total_success_count", 0),
            report.get("total_requests", 0),
        ]
        return self.append_row("Hourly Reports", values)

    def _sheet_exists(self, sheet_name: str) -> bool:
        metadata = self.service.spreadsheets().get(spreadsheetId=self.spreadsheet_id).execute()
        sheets = metadata.get("sheets", [])
        return any(s.get("properties", {}).get("title") == sheet_name for s in sheets)

    def _create_sheet(self, sheet_name: str) -> bool:
        try:
            self.service.spreadsheets().batchUpdate(
                spreadsheetId=self.spreadsheet_id,
                body={"requests": [{"addSheet": {"properties": {"title": sheet_name}}}]},
            ).execute()
            return True
        except Exception as e:
            if "already exists" in str(e).lower():
                return True
            logger.error(f"Failed to create sheet {sheet_name}: {e}")
            return False

    def ensure_headers(self, sheet_name: str) -> bool:
        """Ensure sheet has headers (creates sheet if needed)."""
        headers = [
            "Hour Start",
            "Device ID",
            "Reading Count",
            "Avg Temp (C)",
            "Max Temp (C)",
            "Min Temp (C)",
            "Avg Humidity (%)",
            "Avg Pressure (hPa)",
            "Avg Gas (kOhms)",
            "Total Stink Count",
            "Total Success Count",
            "Total Requests",
        ]
        try:
            if not self._sheet_exists(sheet_name):
                created = self._create_sheet(sheet_name)
                if not created:
                    return False

            result = (
                self.service.spreadsheets()
                .values()
                .get(spreadsheetId=self.spreadsheet_id, range=f"{sheet_name}!A1:L1")
                .execute()
            )
            if not result.get("values"):
                return self.append_row(sheet_name, headers)
            return True
        except Exception as e:
            logger.error(f"Failed to ensure headers: {e}")
            return False


def get_sheets_client() -> SheetsClient | None:
    """Get a Google Sheets client instance if configured."""
    settings = get_settings()
    if settings.google_sheets_spreadsheet_id and settings.google_service_account_json:
        return SheetsClient()
    return None
