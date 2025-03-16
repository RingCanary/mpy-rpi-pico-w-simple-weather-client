import network
import time
import urequests
from machine import Pin, ADC
import json

# Initialize LEDs
led_onboard = Pin("LED", Pin.OUT)  # Onboard LED tied to Wi-Fi module
led_gp5 = Pin(5, Pin.OUT)          # LED soldered to GP5

# Initialize temperature sensor (internal, connected to ADC4)
temp_sensor = ADC(4)

# Wi-Fi credentials
SSID = "your_wifi_ssid"  # Replace with your Wi-Fi SSID
PASSWORD = "your_wifi_password"  # Replace with your Wi-Fi password

# Google Sheets Web App URL (from Google Apps Script)
GOOGLE_SHEETS_URL = "your_google_script_web_app_url"  # Replace with your deployed web app URL

# Connect to Wi-Fi
def connect_wifi():
    led_onboard.on()  # Turn on LED to indicate connection attempt
    
    wlan = network.WLAN(network.STA_IF)
    wlan.active(True)
    if not wlan.isconnected():
        print("Connecting to Wi-Fi...")
        wlan.connect(SSID, PASSWORD)
        
        # Wait for connection with timeout
        max_wait = 10
        while max_wait > 0:
            if wlan.isconnected():
                break
            max_wait -= 1
            print("Waiting for connection...")
            time.sleep(1)
        
        if wlan.isconnected():
            print("Connected to Wi-Fi!")
            print("Network config:", wlan.ifconfig())
            led_onboard.off()  # Turn off LED after successful connection
            return True
        else:
            print("Failed to connect to Wi-Fi")
            # Blink LED to indicate failure
            for _ in range(5):
                led_onboard.off()
                time.sleep(0.1)
                led_onboard.on()
                time.sleep(0.1)
            led_onboard.off()
            return False
    else:
        print("Already connected to Wi-Fi")
        print("Network config:", wlan.ifconfig())
        led_onboard.off()
        return True

# Read raw temperature ADC value
def read_raw_temp():
    return temp_sensor.read_u16()  # Read raw ADC value (0-65535)

# Send temperature to Google Sheets
def send_to_google_sheets(raw_adc):
    # Check if URL is still the placeholder
    if GOOGLE_SHEETS_URL == "your_google_script_web_app_url":
        print("ERROR: You need to replace the placeholder URL with your actual Google Apps Script Web App URL")
        return False
        
    # Prepare data to send
    data = {
        "raw_adc": raw_adc,
        "device_id": "pico_w_1"  # Identifier for your device
    }
    
    # Convert to JSON
    json_data = json.dumps(data)
    
    # Set headers
    headers = {
        "Content-Type": "application/json"
    }
    
    # LED feedback - turn on while sending
    led_gp5.on()
    
    try:
        # Send POST request to Google Apps Script Web App
        print("Sending data to Google Sheets...")
        print(f"URL: {GOOGLE_SHEETS_URL}")
        print(f"Data: {json_data}")
        
        response = urequests.post(GOOGLE_SHEETS_URL, data=json_data, headers=headers)
        
        # Check response
        if response.status_code == 200:
            print("Data sent successfully!")
            response_text = response.text
            print("Response:", response_text)
            
            # Parse response to get temperature
            try:
                response_json = json.loads(response_text)
                if "temperature" in response_json:
                    print(f"Processed temperature: {response_json['temperature']}°C")
            except Exception as parse_error:
                print(f"Error parsing response: {parse_error}")
        else:
            print("Failed to send data. Status code:", response.status_code)
            print("Response:", response.text)
        
        # Close the response to free memory
        response.close()
        return response.status_code == 200
        
    except Exception as e:
        print("Error sending data:", e)
        return False
    finally:
        # Turn off LED after sending
        led_gp5.off()

# Main program
print("Starting Pico W Temperature Logger...")

# Try to connect to Wi-Fi
if connect_wifi():
    print("Wi-Fi connected, starting temperature logging")
    
    # Main loop
    while True:
        try:
            # Read raw temperature ADC value
            raw_adc = read_raw_temp()
            print("\nRaw temperature ADC value:", raw_adc)
            
            # Send temperature data to Google Sheets
            success = send_to_google_sheets(raw_adc)
            
            # Blink LED to indicate successful reading cycle
            if success:
                # Fast blink 3 times for success
                for _ in range(3):
                    led_gp5.on()
                    time.sleep(0.1)
                    led_gp5.off()
                    time.sleep(0.1)
            else:
                # Slow blink 2 times for failure
                for _ in range(2):
                    led_gp5.on()
                    time.sleep(0.5)
                    led_gp5.off()
                    time.sleep(0.5)
            
            # Wait before next reading
            print("Waiting for next reading cycle...")
            time.sleep(60)  # Take readings every minute
            
        except Exception as e:
            print("Error in main loop:", e)
            # Blink LED rapidly to indicate error
            for _ in range(5):
                led_gp5.on()
                time.sleep(0.1)
                led_gp5.off()
                time.sleep(0.1)
            time.sleep(10)  # Wait before retrying
else:
    print("Failed to connect to Wi-Fi, cannot proceed")
    # Blink LED rapidly to indicate error
    for _ in range(10):
        led_gp5.on()
        time.sleep(0.1)
        led_gp5.off()
        time.sleep(0.1)
