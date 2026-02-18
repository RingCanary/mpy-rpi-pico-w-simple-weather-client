-- Pi5 Telemetry Hub Database Schema
-- Run with: psql -d telemetry -f sql/init.sql

-- Raw telemetry readings
CREATE TABLE IF NOT EXISTS readings (
    id BIGSERIAL PRIMARY KEY,
    device_id VARCHAR(100) NOT NULL,
    device_ts TIMESTAMPTZ,
    request_id VARCHAR(100),
    firmware VARCHAR(50),
    
    -- Environmental sensor data (ESP32-C6)
    temperature REAL,
    humidity REAL,
    pressure REAL,
    gas REAL,
    
    -- Pico W specific
    raw_adc INTEGER,
    voltage REAL,

    -- Sensor status and full payload
    sensor_error TEXT,
    payload JSONB NOT NULL DEFAULT '{}'::jsonb,
    
    -- Tracking metrics
    stink_count INTEGER DEFAULT 0,
    redirect_count INTEGER DEFAULT 0,
    success_count INTEGER DEFAULT 0,
    total_requests INTEGER DEFAULT 0,
    uptime_cycles INTEGER DEFAULT 0,
    reset_count INTEGER DEFAULT 0,
    
    -- Metadata
    ingested_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Unique index for race-safe deduplication
CREATE UNIQUE INDEX IF NOT EXISTS uq_readings_device_request
    ON readings(device_id, request_id) 
    WHERE request_id IS NOT NULL;

-- Index for querying by device and time
CREATE INDEX IF NOT EXISTS idx_readings_device_time 
    ON readings(device_id, ingested_at DESC);

-- Index for hourly aggregation queries
CREATE INDEX IF NOT EXISTS idx_readings_time 
    ON readings(ingested_at);

-- Hourly aggregated reports
CREATE TABLE IF NOT EXISTS hourly_reports (
    id BIGSERIAL PRIMARY KEY,
    device_id VARCHAR(100) NOT NULL,
    hour_start TIMESTAMPTZ NOT NULL,
    reading_count INTEGER NOT NULL,
    
    -- Aggregated metrics
    avg_temperature REAL,
    max_temperature REAL,
    min_temperature REAL,
    avg_humidity REAL,
    avg_pressure REAL,
    avg_gas REAL,
    
    -- Totals
    total_stink_count INTEGER DEFAULT 0,
    total_success_count INTEGER DEFAULT 0,
    total_requests INTEGER DEFAULT 0,
    
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    
    CONSTRAINT uq_hourly_report_device_hour UNIQUE (device_id, hour_start)
);

-- Index for querying reports by device
CREATE INDEX IF NOT EXISTS idx_hourly_reports_device 
    ON hourly_reports(device_id, hour_start DESC);

-- Alert state tracking (per device)
CREATE TABLE IF NOT EXISTS alert_state (
    device_id VARCHAR(100) PRIMARY KEY,
    last_reading_at TIMESTAMPTZ,
    last_alert_at TIMESTAMPTZ,
    last_hvac_alert_at TIMESTAMPTZ,
    alert_active BOOLEAN DEFAULT FALSE,
    stale_miss_count INTEGER DEFAULT 0,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Add stale_miss_count column to existing tables (idempotent)
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_name = 'alert_state' AND column_name = 'stale_miss_count'
    ) THEN
        ALTER TABLE alert_state ADD COLUMN stale_miss_count INTEGER DEFAULT 0;
    END IF;
END $$;

-- Function to update updated_at timestamp
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Trigger for alert_state
DROP TRIGGER IF EXISTS update_alert_state_updated_at ON alert_state;
CREATE TRIGGER update_alert_state_updated_at
    BEFORE UPDATE ON alert_state
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();
