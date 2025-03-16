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

# Security type mapping for Wi-Fi scan
security_types = {
    0: "Open",
    1: "WEP",
    2: "WPA-PSK",
    3: "WPA2-PSK",
    4: "WPA/WPA2",
}

# Connect to Wi-Fi
def connect_wifi():
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
            return True
        else:
            print("Failed to connect to Wi-Fi")
            return False
    else:
        print("Already connected to Wi-Fi")
        print("Network config:", wlan.ifconfig())
        return True

# Read raw temperature ADC value
def read_raw_temp():
    return temp_sensor.read_u16()  # Read raw ADC value (0-65535)

# Send temperature to Google Sheets
def send_to_google_sheets(raw_adc):
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
        response = urequests.post(GOOGLE_SHEETS_URL, data=json_data, headers=headers)
        
        # Check response
        if response.status_code == 200:
            print("Data sent successfully!")
            response_text = response.text
            print("Response:", response_text)
        else:
            print("Failed to send data. Status code:", response.status_code)
            print("Response:", response.text)
        
        # Close the response to free memory
        response.close()
        
    except Exception as e:
        print("Error sending data:", e)
    
    # Turn off LED after sending
    led_gp5.off()

# Wi-Fi scan and LED control
def wifi_scan_blink():
    led_onboard.on()  # Turn on onboard LED to indicate scan start
    print("\nScanning for Wi-Fi networks...")
    
    # Perform Wi-Fi scan
    wlan = network.WLAN(network.STA_IF)
    wlan.active(True)
    networks = wlan.scan()
    
    # Print network count and detailed list
    num_networks = len(networks)
    print("Found {} networks!".format(num_networks))
    
    print("\nNetwork List:")
    print("-" * 60)
    print("| {:<32} | {:<8} | {:<6} | {:<8} |".format("SSID", "RSSI", "Ch", "Security"))
    print("-" * 60)
    
    for network in networks:
        ssid = network[0].decode('utf-8') if network[0] else "(Hidden)"
        rssi = network[3]
        channel = network[2]
        security = security_types.get(network[4], "Unknown")
        print("| {:<32} | {:<8} | {:<6} | {:<8} |".format(ssid, rssi, channel, security))
    
    print("-" * 60)
    
    # Read raw temperature ADC value
    raw_adc = read_raw_temp()
    print("Raw temperature ADC value: {}".format(raw_adc))
    
    # Blink GP5 LED based on number of networks found
    for _ in range(min(num_networks, 10)):  # Limit to 10 blinks max
        led_gp5.on()
        time.sleep(0.2)  # Short blink
        led_gp5.off()
        time.sleep(0.2)
    
    led_onboard.off()  # Turn off onboard LED when done
    
    return raw_adc

# Main program
print("Starting Pico W Temperature and Wi-Fi Scanner...")

# Try to connect to Wi-Fi
if connect_wifi():
    print("Wi-Fi connected, starting main loop")
    
    # Main loop
    while True:
        try:
            # Scan Wi-Fi networks and get temperature
            raw_adc = wifi_scan_blink()
            
            # Send temperature data to Google Sheets
            send_to_google_sheets(raw_adc)
            
            # Wait before next scan
            print("Waiting 5 seconds before next scan...")
            time.sleep(5)
            
        except Exception as e:
            print("Error in main loop:", e)
            time.sleep(5)  # Wait before retrying
else:
    print("Failed to connect to Wi-Fi, cannot proceed")
    # Blink LED rapidly to indicate error
    for _ in range(10):
        led_gp5.on()
        time.sleep(0.1)
        led_gp5.off()
        time.sleep(0.1)
