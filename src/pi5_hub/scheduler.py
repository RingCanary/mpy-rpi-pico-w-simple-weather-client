"""APScheduler setup for background jobs."""

import logging

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger

from .alerts import AlertManager
from .apps_script_client import get_apps_script_client
from .config import get_settings
from .db import get_pool
from .reports import ReportGenerator
from .repository import TelemetryRepository
from .sheets_client import get_sheets_client
from .slack_client import SlackClient

logger = logging.getLogger(__name__)

scheduler: AsyncIOScheduler | None = None


async def monitor_job() -> None:
    """Run monitoring cycle for stale data and HVAC alerts."""
    try:
        pool = await get_pool()
        repo = TelemetryRepository(pool)
        slack = SlackClient()
        manager = AlertManager(repo, slack)
        result = await manager.run_monitor_cycle()
        logger.info(f"Monitor cycle completed: {result}")
    except Exception as e:
        logger.error(f"Monitor job failed: {e}")


async def hourly_report_job() -> None:
    """Generate and distribute hourly reports."""
    try:
        pool = await get_pool()
        repo = TelemetryRepository(pool)
        slack = SlackClient()
        sheets = get_sheets_client()
        apps_script = get_apps_script_client()
        generator = ReportGenerator(repo, slack, sheets, apps_script)
        reports = await generator.generate_hourly_report()
        logger.info(f"Hourly report job completed: {len(reports)} reports generated")
    except Exception as e:
        logger.error(f"Hourly report job failed: {e}")


def setup_scheduler() -> AsyncIOScheduler:
    """Set up and return the scheduler with configured jobs."""
    global scheduler
    settings = get_settings()

    sched = AsyncIOScheduler(timezone="UTC")
    scheduler = sched

    sched.add_job(
        monitor_job,
        trigger=IntervalTrigger(minutes=settings.monitor_interval_minutes),
        id="monitor_job",
        name="Stale data and HVAC monitor",
        replace_existing=True,
        max_instances=1,
        coalesce=True,
    )

    if settings.report_interval_hours <= 1:
        sched.add_job(
            hourly_report_job,
            trigger=CronTrigger(minute=0, timezone="UTC"),
            id="hourly_report_job",
            name="Hourly report generator",
            replace_existing=True,
            max_instances=1,
            coalesce=True,
        )
    else:
        sched.add_job(
            hourly_report_job,
            trigger=IntervalTrigger(hours=settings.report_interval_hours),
            id="hourly_report_job",
            name="Periodic report generator",
            replace_existing=True,
            max_instances=1,
            coalesce=True,
        )

    logger.info(
        f"Scheduler configured: monitor every {settings.monitor_interval_minutes} min, "
        f"reports at :00 each hour"
    )
    return scheduler


def start_scheduler() -> None:
    """Start the scheduler."""
    global scheduler
    if scheduler is None:
        scheduler = setup_scheduler()
    assert scheduler is not None
    if not scheduler.running:
        scheduler.start()
        logger.info("Scheduler started")


def shutdown_scheduler() -> None:
    """Shutdown the scheduler."""
    global scheduler
    if scheduler is not None:
        scheduler.shutdown(wait=False)
        scheduler = None
        logger.info("Scheduler shutdown")


async def run_standalone() -> None:
    """Run scheduler standalone (without FastAPI)."""
    import asyncio

    from .db import get_pool

    # Initialize database pool
    await get_pool()
    logger.info("Database pool initialized")

    # Start scheduler
    start_scheduler()

    try:
        # Run forever
        while True:
            await asyncio.sleep(3600)
    except KeyboardInterrupt:
        logger.info("Keyboard interrupt received")
    finally:
        shutdown_scheduler()
        from .db import close_pool

        await close_pool()


def main() -> None:
    """Entry point for running scheduler standalone."""
    import asyncio

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )

    asyncio.run(run_standalone())


if __name__ == "__main__":
    main()
