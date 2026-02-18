"""FastAPI application entry point."""

import logging
from contextlib import asynccontextmanager
from datetime import datetime, timezone

from fastapi import FastAPI, Header, HTTPException
from fastapi.responses import JSONResponse

from .config import get_settings
from .db import close_pool, get_pool
from .models import TelemetryIngest, TelemetryResponse
from .repository import TelemetryRepository
from .scheduler import shutdown_scheduler, start_scheduler

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan handler."""
    logger.info("Starting Pi5 telemetry hub...")

    pool = await get_pool()
    logger.info("Database pool created")

    start_scheduler()
    logger.info("Scheduler started")

    yield

    logger.info("Shutting down Pi5 telemetry hub...")
    shutdown_scheduler()
    await close_pool()
    logger.info("Shutdown complete")


app = FastAPI(
    title="Pi5 Telemetry Hub",
    description="Telemetry collection and alerting for environmental sensors",
    version="0.1.0",
    lifespan=lifespan,
)


@app.get("/health")
async def health_check() -> dict:
    """Health check endpoint."""
    return {"status": "healthy", "timestamp": datetime.now(timezone.utc).isoformat()}


@app.post("/ingest", response_model=TelemetryResponse)
async def ingest_telemetry(
    data: TelemetryIngest,
    x_api_key: str | None = Header(default=None, alias="X-API-Key"),
) -> TelemetryResponse:
    """Ingest telemetry data from Pico W or ESP32-C6 devices."""
    settings = get_settings()

    # Check API key if configured
    if settings.api_key:
        if not x_api_key or x_api_key != settings.api_key:
            raise HTTPException(status_code=401, detail="Invalid or missing API key")

    try:
        pool = await get_pool()
        repo = TelemetryRepository(pool)

        inserted = await repo.insert_reading(data)

        if not inserted:
            return TelemetryResponse(
                status="success",
                timestamp=datetime.now(timezone.utc).isoformat(),
                device_id=data.device_id,
                cached=True,
            )

        logger.info(f"Telemetry ingested: device={data.device_id}, temp={data.temperature}")

        return TelemetryResponse(
            status="success",
            timestamp=datetime.now(timezone.utc).isoformat(),
            device_id=data.device_id,
            cached=False,
        )

    except Exception as e:
        logger.error(f"Failed to ingest telemetry: {e}")
        raise HTTPException(status_code=500, detail=f"Internal error: {e}")


@app.get("/devices")
async def list_devices() -> dict:
    """List devices with recent readings."""
    try:
        pool = await get_pool()
        repo = TelemetryRepository(pool)
        since = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
        devices = await repo.get_devices_with_readings_since(since)
        return {"devices": devices, "count": len(devices)}
    except Exception as e:
        logger.error(f"Failed to list devices: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.exception_handler(Exception)
async def global_exception_handler(request, exc):
    """Global exception handler."""
    logger.error(f"Unhandled exception: {exc}")
    return JSONResponse(status_code=500, content={"status": "error", "message": str(exc)})


def main() -> None:
    """Run the application with uvicorn."""
    import uvicorn

    settings = get_settings()
    uvicorn.run(
        "pi5_hub.main:app",
        host=settings.host,
        port=settings.port,
        reload=False,
    )


if __name__ == "__main__":
    main()
