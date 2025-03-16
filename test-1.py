import network
import time
from machine import Pin, ADC
import math

# Initialize LEDs
led_onboard = Pin("LED", Pin.OUT)  # Onboard LED tied to Wi-Fi module
led_gp5 = Pin(5, Pin.OUT)          # LED soldered to GP5

# Initialize temperature sensor (ADC4 is connected to the internal temperature sensor)
temp_sensor = ADC(4)
# Conversion factor for temperature calculation
conversion_factor = 3.3 / (65535)

def read_temperature():
    # Read the raw temperature value
    raw_temp = temp_sensor.read_u16()
    
    # Convert the raw value to voltage
    voltage = raw_temp * conversion_factor
    
    # Convert voltage to temperature (Celsius)
    # The formula is from the RP2040 datasheet
    temperature = 27 - (voltage - 0.706) / 0.001721
    
    return temperature

def wifi_scan_blink():
    # Turn on onboard LED to indicate scan start
    led_onboard.on()
    print("Scanning for Wi-Fi networks...")
    
    # Create and activate WLAN interface
    wlan = network.WLAN(network.STA_IF)
    wlan.active(True)
    
    # Wait a moment for interface to initialize
    time.sleep(1)
    
    # Perform scan
    try:
        networks = wlan.scan()
        num_networks = len(networks)
        print("Found {} networks!".format(num_networks))
        
        # List all discovered networks
        print("\nNetwork List:")
        print("-" * 60)
        print("| {:<32} | {:<8} | {:<6} | {:<8} |".format("SSID", "RSSI", "Ch", "Security"))
        print("-" * 60)
        
        for net in networks:
            ssid = net[0].decode('utf-8') if net[0] else "(Hidden)"
            bssid = ':'.join('{:02x}'.format(b) for b in net[1])
            channel = net[2]
            rssi = net[3]
            authmode = net[4]
            
            # Convert authmode to readable format
            security = "Unknown"
            if authmode == 0:
                security = "Open"
            elif authmode == 1:
                security = "WEP"
            elif authmode == 2:
                security = "WPA-PSK"
            elif authmode == 3:
                security = "WPA2-PSK"
            elif authmode == 4:
                security = "WPA/WPA2"
            
            print("| {:<32} | {:<8} | {:<6} | {:<8} |".format(ssid, rssi, channel, security))
        
        print("-" * 60)
        
        # Blink LED based on number of networks
        for _ in range(num_networks):
            led_gp5.on()
            time.sleep(0.2)
            led_gp5.off()
            time.sleep(0.2)
    
    except Exception as e:
        print("Error during scan:", e)
    
    # Turn off onboard LED when done
    led_onboard.off()

# Main loop
print("Starting Wi-Fi scanner...")
while True:
    # Read and display temperature
    temp = read_temperature()
    print("\nCurrent temperature: {:.2f}°C".format(temp))
    
    # Run Wi-Fi scan
    wifi_scan_blink()
    time.sleep(5)