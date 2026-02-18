"""Alert logic for stale data and HVAC monitoring."""

import logging
from datetime import datetime, timedelta, timezone

from .config import get_settings
from .repository import TelemetryRepository
from .slack_client import SlackClient

logger = logging.getLogger(__name__)


class AlertManager:
    """Manager for telemetry alerts."""

    def __init__(self, repo: TelemetryRepository, slack: SlackClient):
        self.repo = repo
        self.slack = slack
        self.settings = get_settings()

    async def check_stale_alerts(self) -> list[dict]:
        """Check for stale data on required devices and send alerts if needed."""
        alerts_sent = []
        now = datetime.now(timezone.utc)
        cooldown = timedelta(minutes=self.settings.alert_cooldown_minutes)

        for device_id in self.settings.required_device_ids:
            try:
                state = await self.repo.get_alert_state(device_id)
                last_reading_at = state.get("last_reading_at")
                last_alert_at = state.get("last_alert_at")
                alert_active = state.get("alert_active", False)
                stale_miss_count = state.get("stale_miss_count", 0)

                current_reading_at = await self.repo.get_last_reading(device_id)

                if current_reading_at:
                    # Use current_reading_at for minutes_stalled calculation
                    minutes_stalled = (now - current_reading_at).total_seconds() / 60

                    if last_reading_at and current_reading_at > last_reading_at:
                        # New reading arrived - reset state and possibly send recovery
                        if alert_active:
                            await self.slack.send_recovery_alert(device_id)
                            await self.repo.update_alert_state(
                                device_id,
                                last_reading_at=current_reading_at,
                                last_alert_at=None,
                                alert_active=False,
                                stale_miss_count=0,
                            )
                            logger.info(f"Recovery detected for {device_id}")
                        else:
                            await self.repo.update_alert_state(
                                device_id, last_reading_at=current_reading_at, stale_miss_count=0
                            )
                        continue

                    if not last_reading_at:
                        await self.repo.update_alert_state(
                            device_id, last_reading_at=current_reading_at, stale_miss_count=0
                        )
                        continue

                    # Check if stalled < inactivity threshold - reset counter
                    if minutes_stalled < self.settings.inactivity_minutes:
                        if stale_miss_count > 0:
                            await self.repo.update_alert_state(device_id, stale_miss_count=0)
                        continue

                    # Device is stalled >= inactivity threshold - increment miss count
                    stale_miss_count += 1
                    await self.repo.update_alert_state(device_id, stale_miss_count=stale_miss_count)
                    logger.debug(f"Stale miss count for {device_id}: {stale_miss_count}")

                    # Send alert only if consecutive misses threshold met and cooldown permits
                    if stale_miss_count >= self.settings.stale_consecutive_misses:
                        can_alert = last_alert_at is None or (now - last_alert_at) >= cooldown

                        if can_alert:
                            await self.slack.send_stale_alert(device_id, int(minutes_stalled))
                            await self.repo.update_alert_state(
                                device_id,
                                last_alert_at=now,
                                alert_active=True,
                            )
                            alerts_sent.append(
                                {"device_id": device_id, "minutes_stalled": int(minutes_stalled)}
                            )
                            logger.warning(
                                f"Stale alert sent for {device_id}: {int(minutes_stalled)} min (misses={stale_miss_count})"
                            )
                        else:
                            logger.debug(f"Cooldown active for {device_id}")
                else:
                    # No reading at all for this device
                    if not last_reading_at:
                        continue

                    minutes_stalled = (now - last_reading_at).total_seconds() / 60

                    if minutes_stalled >= self.settings.inactivity_minutes:
                        stale_miss_count += 1
                        await self.repo.update_alert_state(
                            device_id, stale_miss_count=stale_miss_count
                        )
                        logger.debug(f"Stale miss count for {device_id}: {stale_miss_count}")

                        if stale_miss_count >= self.settings.stale_consecutive_misses:
                            can_alert = last_alert_at is None or (now - last_alert_at) >= cooldown

                            if can_alert:
                                await self.slack.send_stale_alert(device_id, int(minutes_stalled))
                                await self.repo.update_alert_state(
                                    device_id,
                                    last_alert_at=now,
                                    alert_active=True,
                                )
                                alerts_sent.append(
                                    {
                                        "device_id": device_id,
                                        "minutes_stalled": int(minutes_stalled),
                                    }
                                )
                                logger.warning(
                                    f"Stale alert sent for {device_id}: {int(minutes_stalled)} min (misses={stale_miss_count})"
                                )
                            else:
                                logger.debug(f"Cooldown active for {device_id}")

            except Exception as e:
                logger.error(f"Error checking stale alert for {device_id}: {e}")

        return alerts_sent

    async def check_hvac_alert(self, device_id: str) -> dict | None:
        """Check HVAC temperature alert for a specific device (ESP32)."""
        now = datetime.now(timezone.utc)
        cooldown = timedelta(minutes=self.settings.hvac_alert_cooldown_minutes)

        try:
            state = await self.repo.get_alert_state(device_id)
            last_hvac_alert_at = state.get("last_hvac_alert_at")

            ts, temp = await self.repo.get_latest_temperature(device_id)

            if temp is None or ts is None:
                return None

            if temp > self.settings.hvac_temp_threshold:
                can_alert = last_hvac_alert_at is None or (now - last_hvac_alert_at) >= cooldown

                if can_alert:
                    await self.slack.send_hvac_alert(
                        device_id,
                        temp,
                        self.settings.hvac_temp_threshold,
                    )
                    await self.repo.update_alert_state(device_id, last_hvac_alert_at=now)
                    logger.warning(f"HVAC alert sent for {device_id}: {temp:.2f}C")
                    return {"device_id": device_id, "temperature": temp}
                else:
                    logger.debug(f"HVAC alert cooldown active for {device_id}")

        except Exception as e:
            logger.error(f"Error checking HVAC alert for {device_id}: {e}")

        return None

    async def run_monitor_cycle(self) -> dict:
        """Run a full monitoring cycle (stale + HVAC checks)."""
        stale_alerts = await self.check_stale_alerts()

        hvac_alerts = []
        for device_id in self.settings.required_device_ids:
            if "pico" not in device_id.lower():
                hvac_alert = await self.check_hvac_alert(device_id)
                if hvac_alert:
                    hvac_alerts.append(hvac_alert)

        return {
            "stale_alerts": stale_alerts,
            "hvac_alerts": hvac_alerts,
            "checked_devices": self.settings.required_device_ids,
        }
