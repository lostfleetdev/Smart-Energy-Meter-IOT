# Smart Energy Monitor - ESP32 MicroPython v2

WiFi + MQTT enabled firmware for ESP32-based smart energy monitoring.

## Files

| File | Description |
|------|-------------|
| `boot_v2.py` | WiFi configuration and connection (runs on boot) |
| `main_v2.py` | Main firmware with MQTT, display, sensors |
| `ssd1306.py` | OLED display driver (included) |
| `calibration.json` | Sensor calibration data |
| `calibrate.py` | Calibration utility |

---

## Installation

### 1. Install MicroPython on ESP32

Download firmware from: https://micropython.org/download/esp32/

```bash
# Erase flash
esptool.py --chip esp32 --port COM3 erase_flash

# Flash MicroPython
esptool.py --chip esp32 --port COM3 write_flash -z 0x1000 esp32-xxx.bin
```

### 2. Install Required Modules

Connect to ESP32 REPL (via Thonny, mpremote, or serial):

```python
# Method 1: Using mip (MicroPython 1.20+)
import mip
mip.install("umqtt.simple")

# Method 2: Using upip (older versions)
import upip
upip.install("micropython-umqtt.simple")

# Method 3: Manual - download and copy
# Get umqtt/simple.py from micropython-lib and copy to device
```

### 3. Configure WiFi and MQTT

Edit `boot_v2.py`:

```python
WIFI_SSID = "YourWiFiName"
WIFI_PASSWORD = "YourWiFiPassword"
MQTT_BROKER = "192.168.1.100"  # Backend server IP
MQTT_PORT = 1883
DEVICE_ID = "device01"
APPLIANCE_TYPE = "fridge"  # ac_1, ac_2, boiler, fridge, washing_machine, dishwasher
```

### 4. Upload Files to ESP32

Using mpremote:
```bash
mpremote cp boot_v2.py :boot.py
mpremote cp main_v2.py :main.py
mpremote cp ssd1306.py :ssd1306.py
mpremote cp calibration.json :calibration.json
```

Using Thonny:
- Open each file and Save As to device with the names above

### 5. Run Calibration (if needed)

```bash
mpremote cp calibrate.py :calibrate.py
mpremote run calibrate.py
```

---

## OLED Display Screens

**Short tap:** Toggle relay  
**Long press (>600ms):** Next screen

| Screen | Content |
|--------|---------|
| 0 - Live | V, I, P, Energy, Relay, Network status |
| 1 - Energy | Accumulated kWh, current readings |
| 2 - Network | WiFi IP, MQTT status, TX count |
| 3 - Config | Device ID, appliance type, broker |
| 4 - Debug | Raw sensor values, memory |

**Status Icons** (top right):
- `W` WiFi connected / `w` disconnected
- `M` MQTT connected / `m` disconnected  
- `R` Relay ON / `r` Relay OFF

---

## MQTT Topics

| Topic | Direction | Payload |
|-------|-----------|---------|
| `energy/{device_id}/telemetry` | Device → Server | JSON: voltage, current, power, energy, appliance |
| `energy/{device_id}/relay/set` | Server → Device | `1` = ON, `0` = OFF |
| `energy/{device_id}/relay/state` | Device → Server | `1` = ON, `0` = OFF |

### Telemetry JSON Example:
```json
{
  "voltage": 230.5,
  "current": 2.45,
  "power": 564.7,
  "energy": 0.001234,
  "appliance": "fridge",
  "device_id": "device01"
}
```

---

## Troubleshooting

### "No calibration file"
Run `calibrate.py` first to generate `calibration.json`

### WiFi won't connect
- Check SSID/password in `boot_v2.py`
- Ensure 2.4GHz network (ESP32 doesn't support 5GHz)
- Move closer to router during setup

### MQTT keeps disconnecting
- Verify broker IP is correct
- Check if MQTT broker (nanomq/mosquitto) is running
- Ensure port 1883 is not blocked

### Module import errors
```python
# Check if umqtt is installed
import umqtt.simple  # Should not error
```

---

## Hardware Connections

| Component | ESP32 Pin |
|-----------|-----------|
| OLED SCL | GPIO 18 |
| OLED SDA | GPIO 21 |
| Relay | GPIO 2 |
| Touch Button | GPIO 4 |
| ZMPT101B (Voltage) | GPIO 35 |
| ACS712 (Current) | GPIO 34 |
