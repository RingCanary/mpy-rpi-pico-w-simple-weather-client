"""
Pico W Telemetry Client
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
except ImportError:
    WIFI_SSID = "YOUR_WIFI_SSID"
    WIFI_PASSWORD = "YOUR_WIFI_PASSWORD"
    PI5_HOST = "192.168.1.100"
    PI5_PORT = 8000
    INGEST_ENDPOINT = "/ingest"
    DEVICE_ID = "pico_w_01"
    API_KEY = ""
    SEND_INTERVAL_SEC = 60

FIRMWARE_VERSION = "1.0.0"

# ============================================================================
# LED Indicators
# ============================================================================
_green_led = None
_red_led = None


def init_leds():
    """Initialize onboard green LED and external red LED on GP5."""
    global _green_led, _red_led
    try:
        _green_led = machine.Pin("LED", machine.Pin.OUT)
    except Exception:
        _green_led = machine.Pin(25, machine.Pin.OUT)
    _red_led = machine.Pin(5, machine.Pin.OUT)
    _green_led.off()
    _red_led.off()


def _set_led(led, state):
    if led:
        if state:
            led.on()
        else:
            led.off()


def _blink(led, times=1, on_sec=0.08, off_sec=0.08):
    if not led:
        return
    for _ in range(times):
        led.on()
        time.sleep(on_sec)
        led.off()
        time.sleep(off_sec)


def refresh_led_state():
    """Green tracks Wi-Fi link, red is only for error blinks."""
    wifi_ok = _wifi_connected and _wlan is not None and _wlan.isconnected()
    _set_led(_green_led, wifi_ok)
    _set_led(_red_led, False)


def indicate_send_success():
    _blink(_green_led, times=1, on_sec=0.06, off_sec=0.04)
    refresh_led_state()


def indicate_send_failure():
    _blink(_red_led, times=2, on_sec=0.08, off_sec=0.08)
    refresh_led_state()


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

    retry_delay = base_delay
    for attempt in range(max_retries):
        try:
            print(f"[WiFi] Connecting (attempt {attempt + 1}/{max_retries})...")
            _wlan.connect(WIFI_SSID, WIFI_PASSWORD)

            # Wait for connection with timeout
            timeout = 10
            while not _wlan.isconnected() and timeout > 0:
                time.sleep(1)
                timeout -= 1

            if _wlan.isconnected():
                _wifi_connected = True
                print(f"[WiFi] Connected! IP: {_wlan.ifconfig()[0]}")
                refresh_led_state()
                return True
            else:
                print(f"[WiFi] Connection failed, retrying in {retry_delay}s...")
        except Exception as e:
            print(f"[WiFi] Error: {e}")

        time.sleep(retry_delay)
        retry_delay = min(retry_delay * 2, 30)  # Exponential backoff, max 30s

    _wifi_connected = False
    refresh_led_state()
    return False


def ensure_wifi():
    """Ensure Wi-Fi is connected, reconnect if needed."""
    global _wifi_connected

    if _wifi_connected and _wlan.isconnected():
        return True

    print("[WiFi] Connection lost, reconnecting...")
    _wifi_connected = False
    refresh_led_state()
    return connect_wifi()


# ============================================================================
# Sensor Reading
# ============================================================================
_adc = None
_temp_sensor = None


def init_sensors():
    """Initialize sensors."""
    global _adc, _temp_sensor
    _adc = machine.ADC(26)  # GP26 / ADC0
    _temp_sensor = machine.ADC(4)  # Internal temperature sensor


def read_internal_temp():
    """Read internal temperature sensor (approximate)."""
    # Pico internal temperature sensor is on ADC4
    # Convert ADC value to voltage, then to temperature
    reading = _temp_sensor.read_u16()
    voltage = reading * 3.3 / 65535
    # Formula from RP2040 datasheet (approximate)
    temp_c = 27 - (voltage - 0.706) / 0.001721
    return round(temp_c, 2)


def read_sensors():
    """Read all sensor values."""
    raw_adc = _adc.read_u16()
    voltage = round(raw_adc * 3.3 / 65535, 4)
    temperature = read_internal_temp()

    return {"raw_adc": raw_adc, "voltage": voltage, "temperature": temperature}


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
        indicate_send_failure()
        return False

    # Build telemetry payload
    sensor_data = read_sensors()
    payload = {
        "device_id": DEVICE_ID,
        "device_ts": int(time.time()),
        "firmware": FIRMWARE_VERSION,
        "request_id": generate_request_id(),
    }
    payload.update(sensor_data)

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
                indicate_send_success()
                return True
            else:
                print(f"[HTTP] Server error: {response.status_code}")
                response.close()

                # Don't retry on 4xx client errors
                if 400 <= response.status_code < 500:
                    indicate_send_failure()
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

    indicate_send_failure()
    return False


# ============================================================================
# Main Loop
# ============================================================================
def main():
    """Main telemetry loop."""
    print("=" * 50)
    print(f"Pico W Telemetry Client v{FIRMWARE_VERSION}")
    print(f"Device ID: {DEVICE_ID}")
    print("=" * 50)

    # Initialize
    init_leds()
    init_wifi()
    init_sensors()

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
            else:
                consecutive_failures += 1
                if consecutive_failures >= max_consecutive_failures:
                    print(f"[Main] Too many failures ({consecutive_failures}), resetting WiFi...")
                    global _wifi_connected
                    _wifi_connected = False
                    consecutive_failures = 0

            # Wait for next interval
            print(f"[Main] Sleeping {SEND_INTERVAL_SEC}s until next reading...")
            time.sleep(SEND_INTERVAL_SEC)

        except Exception as e:
            print(f"[Main] Unexpected error: {e}")
            time.sleep(10)  # Brief pause before retry


if __name__ == "__main__":
    main()
