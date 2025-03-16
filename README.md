# Raspberry Pi Pico W Wi-Fi Scanner

## Overview
This project uses a Raspberry Pi Pico W to scan for Wi-Fi networks and display the results both on the serial console and through LED indicators. The onboard LED (connected to the Wi-Fi module) lights up during each scan, while an LED connected to GP5 blinks once for each network found. Additionally, the project monitors and displays the internal temperature of the RP2040 chip.

## Features
- **Wi-Fi Network Scanning**: Detects all available Wi-Fi networks in range (test-1.py)
- **Detailed Network Information**: Displays SSID, signal strength (RSSI), channel, and security type (test-1.py)
- **Temperature Monitoring**: Reads and displays the internal temperature of the RP2040 chip
- **Google Sheets Integration**: Sends temperature data to Google Sheets for logging and analysis (test-2.py)
- **Visual Feedback**: Uses LEDs to indicate status and operation
- **Command-line Workflow**: Uses rshell and minicom instead of Thonny IDE

## Hardware Requirements
- Raspberry Pi Pico W
- LED connected to GP5 (with appropriate resistor to ground)
- USB cable for power and data connection

## Software Requirements
- MicroPython firmware for Raspberry Pi Pico W
- `rshell` for file management
- `minicom` (Linux/macOS) or PuTTY (Windows) for serial monitoring

## Hardware Setup
1. Connect an LED to GP5 of the Raspberry Pi Pico W with a suitable resistor (220-330Ω) to ground
2. The onboard LED (connected to the "LED" pin) will be used automatically
3. The internal temperature sensor is built into the RP2040 chip and requires no additional wiring

## Installation

### 1. Install MicroPython on the Pico W
- Download the latest MicroPython firmware for the Pico W from [micropython.org](https://micropython.org/download/rp2-pico-w/)
- Hold the BOOTSEL button on the Pico W and connect it to your computer via USB
- The Pico W should appear as a USB drive (named `RPI-RP2`)
- Drag the `.uf2` firmware file to the `RPI-RP2` drive
- The Pico W will automatically reboot with MicroPython installed

### 2. Install Required Tools

#### For Linux/macOS:
```bash
# Install rshell for file management
pip install rshell

# Install minicom for serial monitoring
sudo apt install minicom    # For Debian/Ubuntu
# or
sudo brew install minicom   # For macOS with Homebrew
```

#### For Windows:
```bash
# Install rshell for file management
pip install rshell

# For serial monitoring, download and install PuTTY from:
# https://www.putty.org/
```

## Google Sheets Integration
This project now includes integration with Google Sheets to log temperature data. To set up Google Sheets integration, follow these steps:

### 1. Create a Google Sheet
1. Go to [Google Sheets](https://sheets.google.com/) and create a new spreadsheet
2. Rename the spreadsheet to something meaningful (e.g., "Pico W Temperature Data")
3. Note the spreadsheet ID from the URL (the long string between `/d/` and `/edit` in the URL)

### 2. Set Up Google Apps Script
1. In your Google Sheet, click on `Extensions` > `Apps Script`
2. Delete any code in the editor and paste the contents of the `google_apps_script.js` file
3. Replace `your_spreadsheet_id` with your actual spreadsheet ID
4. Save the project with a name (e.g., "Pico W Temperature Logger")
5. Run the `setupWebApp` function once to initialize the web app:
   - Click on `Run` > `Run function` > `setupWebApp`
   - Grant the necessary permissions when prompted

### 3. Deploy the Web App
1. Click on `Deploy` > `New deployment`
2. For deployment type, select `Web app`
3. Fill in the following:
   - Description: "Pico W Temperature Logger"
   - Execute as: "Me"
   - Who has access: "Anyone" (for simplicity) or "Anyone with Google account" (more secure)
4. Click `Deploy`
5. Copy the Web app URL that appears - you'll need this for your Pico W code

### 4. Configure the Pico W Code
1. Open `test-2.py` in your preferred editor
2. Replace the placeholder values:
   - `your_wifi_ssid`: Your Wi-Fi network name
   - `your_wifi_password`: Your Wi-Fi password
   - `your_google_script_web_app_url`: The Web app URL from step 3.5
3. Upload the modified script to your Pico W using rshell

## Usage

### Uploading the Script

#### Using rshell:
```bash
# Connect to the Pico W (replace /dev/ttyACM0 with your device's port)
rshell -p /dev/ttyACM0

# Inside rshell, copy the script to the Pico W
cp test-1.py /pyboard/

# Optionally, rename to main.py to run automatically on boot
cp test-1.py /pyboard/main.py

# List files to confirm upload
ls /pyboard

# Exit rshell
exit
```

#### Finding your device port:
- **Linux/macOS**: Run `ls /dev/tty*` and look for something like `/dev/ttyACM0` or `/dev/ttyUSB0`
- **Windows**: Check Device Manager under "Ports (COM & LPT)" for a COM port (e.g., COM3)

### Running the Script

#### Method 1: Using minicom (Linux/macOS):
```bash
# Connect to the Pico W's serial console
minicom -D /dev/ttyACM0 -b 115200

# In the REPL (>>>), run:
exec(open('test-1.py').read())

# To exit minicom: Ctrl+A, then X, then Enter
```

#### Method 2: Using PuTTY (Windows):
1. Open PuTTY
2. Select "Serial" connection type
3. Enter your COM port (e.g., COM3)
4. Set Speed to 115200
5. Click "Open"
6. In the REPL (>>>), run: `exec(open('test-1.py').read())`

#### Method 3: Using rshell's REPL:
```bash
# Connect with rshell
rshell -p /dev/ttyACM0

# Enter the REPL
repl

# Execute the script
exec(open('test-1.py').read())

# Exit the REPL: Ctrl+X
# Exit rshell: exit
```

#### Method 4: Auto-run on boot:
If you copied the script as `main.py`, it will run automatically every time the Pico W boots up.

### Temperature Logging to Google Sheets (test-2.py)

#### Using rshell:
```bash
# Connect to the Pico W
rshell -p /dev/ttyACM0

# Copy the script to the Pico W
cp test-2.py /pyboard/

# To make it run automatically on boot
cp test-2.py /pyboard/main.py

# Exit rshell
exit
```

### Google Sheets Integration (test-2.py)
```
Starting Pico W Temperature Logger...
Connecting to Wi-Fi...
Connected to Wi-Fi!
Network config: ('192.168.1.100', '255.255.255.0', '192.168.1.1', '8.8.8.8')

Raw temperature ADC value: 28756
Sending data to Google Sheets...
Data sent successfully!
Response: {"status":"success","timestamp":"2025-03-16T16:15:45.123Z","temperature":27.3}
Processed temperature: 27.3°C
Waiting for next reading cycle...
```

### Stopping the Script
Press `Ctrl+C` to interrupt the running script.

## Understanding the Output

The script produces output like this:
```
Starting Wi-Fi scanner...

Current temperature: 27.35°C
Scanning for Wi-Fi networks...
Found 18 networks!

Network List:
------------------------------------------------------------
| SSID                             | RSSI     | Ch     | Security |
------------------------------------------------------------
| SSID_2_4                         | -68      | 1      | Unknown  |
| SSID_2_416281                    | -75      | 1      | Unknown  |
| SSID_2_4-G                       | -60      | 1      | Unknown  |
...
------------------------------------------------------------
```

- **Temperature**: Internal temperature of the RP2040 chip in Celsius
- **SSID**: Network name (or "Hidden" for networks not broadcasting their SSID)
- **RSSI**: Signal strength in dBm (lower negative numbers indicate stronger signals)
- **Ch**: Wi-Fi channel
- **Security**: Security type (Open, WEP, WPA-PSK, WPA2-PSK, WPA/WPA2, or Unknown)

## LED Behavior
- **Onboard LED**: 
  - In test-1.py: Lights up during each Wi-Fi scan
  - In test-2.py: Lights up during Wi-Fi connection, turns off when connected
- **GP5 LED**: 
  - In test-1.py: Blinks once for each network found (0.2s on, 0.2s off per blink)
  - In test-2.py: Turns on while sending data to Google Sheets, blinks 3 times after successful reading

## Troubleshooting

### No Serial Output
- Verify you're using the correct serial port
- Ensure the baud rate is set to 115200
- Check USB connections

### LEDs Not Working
- Verify the GP5 LED is connected correctly with a resistor to ground
- Ensure you're using the Pico W (not the regular Pico) as the code uses the Wi-Fi module

### Script Not Found
- Use `rshell ls /pyboard` to confirm the file was uploaded correctly
- Check for typos in the filename when using `exec(open())`

### Wi-Fi Not Scanning
- Ensure you're using the Pico W (not the regular Pico)
- Verify the MicroPython firmware is specifically for the Pico W

### Incorrect Temperature Readings
- The internal temperature sensor is not calibrated for high precision
- Readings may vary by a few degrees from actual temperature
- The chip temperature will be higher than ambient temperature

## Next Steps
- Add external sensors for more accurate environmental monitoring
- Create data visualizations in Google Sheets
- Set up alerts for temperature thresholds
- Display information on an LCD or OLED screen
- Implement power-saving modes for longer battery life

## Resources
- [Raspberry Pi Pico W Documentation](https://www.raspberrypi.com/documentation/microcontrollers/raspberry-pi-pico.html)
- [MicroPython Documentation](https://docs.micropython.org/)
- [MicroPython Network Libraries](https://docs.micropython.org/en/latest/library/network.html)
- [RP2040 Datasheet](https://datasheets.raspberrypi.com/rp2040/rp2040-datasheet.pdf)
