"""
ESP32-C6 Telemetry Client with BME680 Sensor
Sends sensor data via HTTP POST to Pi5 ingest endpoint.
"""

import network
import urequests
import machine
import time
import json
import random

# ============================================================================
# CONFIGURATION - Load from config.py if present, else use defaults
# ============================================================================
try:
    import config

    WIFI_SSID = config.WIFI_SSID
    WIFI_PASSWORD = config.WIFI_PASSWORD
    PI5_HOST = config.PI5_HOST
    PI5_PORT = config.PI5_PORT
    INGEST_ENDPOINT = getattr(config, "INGEST_ENDPOINT", "/ingest")
    DEVICE_ID = config.DEVICE_ID
    API_KEY = getattr(config, "API_KEY", "")
    SEND_INTERVAL_SEC = getattr(config, "SAMPLE_INTERVAL", 60)
    STATUS_LED_PIN = getattr(config, "STATUS_LED_PIN", 15)
    BME680_SDA_PIN = getattr(config, "BME680_SDA_PIN", 19)
    BME680_SCL_PIN = getattr(config, "BME680_SCL_PIN", 20)
except ImportError:
    WIFI_SSID = "YOUR_WIFI_SSID"
    WIFI_PASSWORD = "YOUR_WIFI_PASSWORD"
    PI5_HOST = "192.168.1.100"
    PI5_PORT = 8000
    INGEST_ENDPOINT = "/ingest"
    DEVICE_ID = "esp32_c6_01"
    API_KEY = ""
    SEND_INTERVAL_SEC = 60
    STATUS_LED_PIN = 15
    BME680_SDA_PIN = 19
    BME680_SCL_PIN = 20

FIRMWARE_VERSION = "1.0.0"

# ============================================================================
# BME680 Sensor (optional - graceful fallback)
# ============================================================================
_bme680 = None
_bme680_available = False
_bme680_retry_count = 0
_BME680_MAX_RETRIES = 3


def init_bme680():
    """Initialize BME680 sensor with graceful error handling.

    Uses configured I2C pins (BME680_SDA_PIN, BME680_SCL_PIN) from config.py
    if available, otherwise defaults to SDA=19, SCL=20.

    Tries configured pin order first, then swapped order if sensor not detected.
    """
    global _bme680, _bme680_available

    try:
        # Try importing BME680 library
        from bme680 import BME680_I2C
        from machine import Pin, SoftI2C

        # Try configured pin pair first
        print(f"[BME680] Trying I2C: SDA=GPIO{BME680_SDA_PIN}, SCL=GPIO{BME680_SCL_PIN}")
        i2c = SoftI2C(sda=Pin(BME680_SDA_PIN), scl=Pin(BME680_SCL_PIN), freq=100000)

        # Scan for BME680 (typically at 0x76 or 0x77)
        devices = i2c.scan()
        if 0x76 in devices or 0x77 in devices:
            _bme680 = BME680_I2C(i2c)
            _bme680_available = True
            print("[BME680] Sensor initialized successfully")
            return True

        # Sensor not found on configured pins, try swapped order
        print(
            f"[BME680] Not found, trying swapped: SDA=GPIO{BME680_SCL_PIN}, SCL=GPIO{BME680_SDA_PIN}"
        )
        i2c = SoftI2C(sda=Pin(BME680_SCL_PIN), scl=Pin(BME680_SDA_PIN), freq=100000)
        devices = i2c.scan()
        if 0x76 in devices or 0x77 in devices:
            _bme680 = BME680_I2C(i2c)
            _bme680_available = True
            print("[BME680] Sensor initialized successfully (swapped pins)")
            return True

        # Neither pin order found the sensor
        raise OSError("BME680 not found on I2C bus")

    except ImportError:
        print("[BME680] ERROR: bme680 library not found!")
        print("[BME680] Please upload bme680.py to the device")
        _bme680_available = False
        return False

    except OSError as e:
        print(f"[BME680] ERROR: Sensor not detected - {e}")
        print(f"[BME680] Check wiring: SDA to GPIO{BME680_SDA_PIN}, SCL to GPIO{BME680_SCL_PIN}")
        _bme680_available = False
        return False

    except Exception as e:
        print(f"[BME680] ERROR: Initialization failed - {e}")
        _bme680_available = False
        return False


def check_bme680():
    """Check and reinitialize BME680 if needed."""
    global _bme680_retry_count

    if _bme680_available:
        return True

    if _bme680_retry_count < _BME680_MAX_RETRIES:
        print(
            f"[BME680] Retrying initialization ({_bme680_retry_count + 1}/{_BME680_MAX_RETRIES})..."
        )
        if init_bme680():
            _bme680_retry_count = 0
            return True
        _bme680_retry_count += 1

    return False


def read_bme680():
    """Read BME680 sensor values with error handling."""
    global _bme680_retry_count, _bme680_available

    if not _bme680_available:
        # Periodically retry sensor initialization
        check_bme680()
        return None

    try:
        # Trigger a reading for drivers that require it
        if hasattr(_bme680, "trigger_measurement"):
            _bme680.trigger_measurement()
            time.sleep_ms(100)

        # Read values
        data = {
            "temperature": round(_bme680.temperature, 2),
            "humidity": round(_bme680.humidity, 2),
            "pressure": round(_bme680.pressure, 2),
            "gas": round(_bme680.gas, 0),
        }
        return data

    except Exception as e:
        print(f"[BME680] Read error: {e}")
        _bme680_available = False
        return None


# ============================================================================
# Wi-Fi Management
# ============================================================================
_wlan = None
_wifi_connected = False


def init_wifi():
    """Initialize Wi-Fi and connect."""
    global _wlan, _wifi_connected
    _wlan = network.WLAN(network.STA_IF)
    _wlan.active(True)
    _wifi_connected = False


def connect_wifi(max_retries=5, base_delay=2):
    """Connect to Wi-Fi with retry and backoff."""
    global _wifi_connected

    if _wifi_connected and _wlan.isconnected():
        return True

    # LED OFF while connecting/disconnected
    set_led_state(False)

    retry_delay = base_delay
    for attempt in range(max_retries):
        try:
            print(f"[WiFi] Connecting (attempt {attempt + 1}/{max_retries})...")
            _wlan.connect(WIFI_SSID, WIFI_PASSWORD)

            # Wait for connection with timeout
            timeout = 15
            while not _wlan.isconnected() and timeout > 0:
                time.sleep(1)
                timeout -= 1

            if _wlan.isconnected():
                _wifi_connected = True
                print(f"[WiFi] Connected! IP: {_wlan.ifconfig()[0]}")
                # LED ON steady when connected
                set_led_state(True)
                return True
            else:
                print(f"[WiFi] Connection failed, retrying in {retry_delay}s...")
        except Exception as e:
            print(f"[WiFi] Error: {e}")

        time.sleep(retry_delay)
        retry_delay = min(retry_delay * 2, 30)  # Exponential backoff, max 30s

    _wifi_connected = False
    # LED OFF on connection failure
    set_led_state(False)
    return False


def ensure_wifi():
    """Ensure Wi-Fi is connected, reconnect if needed."""
    global _wifi_connected

    if _wifi_connected and _wlan.isconnected():
        return True

    print("[WiFi] Connection lost, reconnecting...")
    _wifi_connected = False
    # LED OFF on connection loss
    set_led_state(False)
    return connect_wifi()


# ============================================================================
# HTTP Communication
# ============================================================================
_request_counter = 0


def generate_request_id():
    """Generate a unique request ID."""
    global _request_counter
    _request_counter += 1
    timestamp = int(time.time())
    rand = random.randint(1000, 9999)
    return f"{DEVICE_ID}-{timestamp}-{_request_counter}-{rand}"


def send_telemetry(max_retries=3, base_delay=1):
    """Send telemetry data to Pi5 with retry logic."""
    if not ensure_wifi():
        print("[HTTP] Cannot send - no WiFi connection")
        return False

    # Read BME680 sensor
    sensor_data = read_bme680()

    # Build telemetry payload
    payload = {
        "device_id": DEVICE_ID,
        "device_ts": int(time.time()),
        "firmware": FIRMWARE_VERSION,
        "request_id": generate_request_id(),
    }

    # Add sensor data if available
    if sensor_data:
        payload.update(sensor_data)
    else:
        payload["sensor_error"] = "BME680 unavailable"

    url = f"http://{PI5_HOST}:{PI5_PORT}{INGEST_ENDPOINT}"
    headers = {"Content-Type": "application/json"}
    if API_KEY:
        headers["X-API-Key"] = API_KEY

    retry_delay = base_delay
    for attempt in range(max_retries):
        try:
            print(f"[HTTP] Sending telemetry (attempt {attempt + 1}/{max_retries})...")
            response = urequests.post(url, data=json.dumps(payload), headers=headers)

            if 200 <= response.status_code < 300:
                print(f"[HTTP] Success! Status: {response.status_code}")
                response.close()
                return True
            else:
                print(f"[HTTP] Server error: {response.status_code}")
                response.close()

                # Don't retry on 4xx client errors
                if 400 <= response.status_code < 500:
                    return False

        except OSError as e:
            # Network errors - likely need to reconnect WiFi
            print(f"[HTTP] Network error: {e}")
            ensure_wifi()
        except Exception as e:
            print(f"[HTTP] Error: {e}")

        if attempt < max_retries - 1:
            print(f"[HTTP] Retrying in {retry_delay}s...")
            time.sleep(retry_delay)
            retry_delay = min(retry_delay * 2, 10)

    return False


# ============================================================================
# Status LED (ESP32-C6 built-in - single LED)
# ============================================================================
_status_led = None


def init_led():
    """Initialize status LED."""
    global _status_led
    _status_led = machine.Pin(STATUS_LED_PIN, machine.Pin.OUT)
    # Start with LED OFF
    _status_led.off()


def set_led_state(on):
    """Set LED steady state (ON=True, OFF=False)."""
    if _status_led:
        if on:
            _status_led.on()
        else:
            _status_led.off()


def led_blink_pattern(times, delay_ms=100):
    """Blink LED a specific number of times, then restore to previous steady state.

    Patterns:
    - 1 blink: telemetry send success
    - 2 blinks: send failure / retry exhausted
    - 3 blinks: unexpected main loop exception
    """
    if not _status_led:
        return

    # Remember current state to restore after blinking
    was_on = _status_led.value() == 1

    for _ in range(times):
        _status_led.on()
        time.sleep_ms(delay_ms)
        _status_led.off()
        time.sleep_ms(delay_ms)

    # Restore steady state
    if was_on:
        _status_led.on()
    else:
        _status_led.off()


# ============================================================================
# Main Loop
# ============================================================================
def main():
    """Main telemetry loop."""
    print("=" * 50)
    print(f"ESP32-C6 Telemetry Client v{FIRMWARE_VERSION}")
    print(f"Device ID: {DEVICE_ID}")
    print("=" * 50)

    # Initialize
    init_wifi()
    init_led()
    init_bme680()

    # Initial connection
    if not connect_wifi():
        print("[Main] Warning: Initial WiFi connection failed, will retry in loop")

    consecutive_failures = 0
    max_consecutive_failures = 10

    while True:
        try:
            success = send_telemetry()

            if success:
                consecutive_failures = 0
                # Single short blink on success, returns to steady ON
                led_blink_pattern(1, 100)
            else:
                consecutive_failures += 1
                # Double blink on failure, returns to steady state
                led_blink_pattern(2, 100)

                if consecutive_failures >= max_consecutive_failures:
                    print(f"[Main] Too many failures ({consecutive_failures}), resetting WiFi...")
                    global _wifi_connected
                    _wifi_connected = False
                    # LED OFF when WiFi disconnected
                    set_led_state(False)
                    consecutive_failures = 0

            # Wait for next interval
            print(f"[Main] Sleeping {SEND_INTERVAL_SEC}s until next reading...")
            time.sleep(SEND_INTERVAL_SEC)

        except Exception as e:
            print(f"[Main] Unexpected error: {e}")
            # Triple quick blink on exception, returns to steady state
            led_blink_pattern(3, 80)
            time.sleep(10)  # Brief pause before retry


if __name__ == "__main__":
    main()
