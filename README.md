# Raspberry Pi Pico W Wi-Fi Scanner

## Overview
This project uses a Raspberry Pi Pico W to scan for Wi-Fi networks and display the results both on the serial console and through LED indicators. The onboard LED (connected to the Wi-Fi module) lights up during each scan, while an LED connected to GP5 blinks once for each network found.

## Features
- **Wi-Fi Network Scanning**: Detects all available Wi-Fi networks in range
- **Detailed Network Information**: Displays SSID, signal strength (RSSI), channel, and security type
- **Visual Feedback**: Uses LEDs to indicate scanning status and network count
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

### Stopping the Script
Press `Ctrl+C` to interrupt the running script.

## Understanding the Output

The script produces output like this:
```
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

- **SSID**: Network name (or "Hidden" for networks not broadcasting their SSID)
- **RSSI**: Signal strength in dBm (lower negative numbers indicate stronger signals)
- **Ch**: Wi-Fi channel
- **Security**: Security type (Open, WEP, WPA-PSK, WPA2-PSK, WPA/WPA2, or Unknown)

## LED Behavior
- **Onboard LED**: Lights up during each Wi-Fi scan
- **GP5 LED**: Blinks once for each network found (0.2s on, 0.2s off per blink)

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

## Next Steps
- Connect to a specific Wi-Fi network
- Fetch weather data from an online API
- Display weather information using additional LEDs or sensors

## Resources
- [Raspberry Pi Pico W Documentation](https://www.raspberrypi.com/documentation/microcontrollers/raspberry-pi-pico.html)
- [MicroPython Documentation](https://docs.micropython.org/)
- [MicroPython Network Libraries](https://docs.micropython.org/en/latest/library/network.html)
