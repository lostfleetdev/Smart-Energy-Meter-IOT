# 4. Firmware Guide

## 4.1 Overview

The device firmware runs on ESP32 using MicroPython. It handles:

1. **Sensor Reading** — ADC sampling of voltage and current
2. **RMS Calculation** — True RMS from 200 samples per measurement
3. **Display Management** — 4-screen OLED UI
4. **Touch Input** — Button handling for control and navigation
5. **Relay Control** — Load switching with auto-zero compensation
6. **Error Recovery** — Automatic reinitialization on I²C failures

---

## 4.2 File Structure

```
device/
├── main.py           # Main application loop
├── calibrate.py      # Interactive calibration wizard
├── calibration.json  # Stored calibration constants
├── boot.py           # MicroPython boot stub
└── ssd1306.py        # OLED driver library
```

---

## 4.3 Calibration Process

### Why Calibration?

Each sensor has manufacturing variations. Calibration determines:

| Parameter | Purpose |
|-----------|---------|
| `v_midpoint` | ZMPT101B DC offset (ADC value at 0V) |
| `v_scale` | Volts per ADC unit |
| `acs_midpoint_v` | ACS712 zero-current voltage |
| `acs_sensitivity` | Volts per Amp |
| `v_noise_threshold` | Minimum voltage to consider valid |
| `i_noise_threshold` | Minimum current to consider valid |

### Calibration Steps

```
┌────────────────────────────────────────────────────────────────┐
│                  CALIBRATION WIZARD FLOW                       │
├────────────────────────────────────────────────────────────────┤
│                                                                │
│   STEP 1: NO-LOAD MEASUREMENT                                  │
│   ───────────────────────────                                  │
│   • Remove all appliances from socket                          │
│   • Relay turned ON (circuit closed)                           │
│   • Measure ADC values for 2000 samples                        │
│   • Calculate V_MIDPOINT and ACS_MIDPOINT_V                    │
│   • Record noise floor (RMS at no load)                        │
│                                                                │
│                         ▼                                      │
│                                                                │
│   STEP 2: WITH-LOAD MEASUREMENT                                │
│   ─────────────────────────────                                │
│   • Connect known load (e.g., 600W kettle)                     │
│   • Turn kettle ON                                             │
│   • Measure RMS voltage and current (5 samples)                │
│   • Calculate V_SCALE and ACS_SENSITIVITY                      │
│                                                                │
│                         ▼                                      │
│                                                                │
│   STEP 3: SAVE TO FLASH                                        │
│   ──────────────────────                                       │
│   • Write calibration.json                                     │
│   • Display verification values                                │
│   • Turn relay OFF                                             │
│                                                                │
└────────────────────────────────────────────────────────────────┘
```

### Calibration Constants

```python
# Example calibration.json
{
    "v_midpoint": 2965,           # ADC midpoint for ZMPT101B
    "v_scale": 0.2103,            # Volts per raw RMS unit
    "acs_midpoint_v": 2.373,      # Zero-current voltage
    "acs_sensitivity": 0.1075,    # Volts per Amp
    "v_noise_threshold": 5.78,    # Voltage noise floor (V)
    "i_noise_threshold": 0.107,   # Current noise floor (A)
    "calibration_voltage": 230.0, # Reference voltage used
    "calibration_power": 600.0    # Reference load used (W)
}
```

### Running Calibration

```bash
# Upload and run calibration script
ampy -p COM3 run device/calibrate.py

# Follow OLED prompts:
# 1. Remove all loads → Touch to continue
# 2. Connect kettle, turn ON → Touch when ready
# 3. Wait for measurements
# 4. Calibration saved!
```

---

## 4.4 Main Loop

### State Machine

```
┌─────────────────────────────────────────────────────────────────┐
│                       MAIN LOOP STATE                           │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│   ┌───────────────┐                                             │
│   │   STARTUP     │                                             │
│   │               │                                             │
│   │ • Init I²C    │                                             │
│   │ • Init ADC    │                                             │
│   │ • Load calib  │                                             │
│   │ • Zero sensors│                                             │
│   └───────┬───────┘                                             │
│           │                                                     │
│           ▼                                                     │
│   ┌───────────────────────────────────────────────────────┐     │
│   │                    MAIN LOOP (20ms tick)               │     │
│   │                                                        │     │
│   │   ┌─────────────┐    ┌─────────────┐    ┌───────────┐ │     │
│   │   │   TOUCH     │    │   SENSOR    │    │  DISPLAY  │ │     │
│   │   │  HANDLING   │    │   READING   │    │  UPDATE   │ │     │
│   │   │             │    │             │    │           │ │     │
│   │   │ • Debounce  │    │ • Every 1s  │    │ • Every 1s│ │     │
│   │   │ • Short tap │    │ • V/I RMS   │    │ • 4 screens│ │     │
│   │   │   → Toggle  │    │ • Power calc│    │           │ │     │
│   │   │ • Long press│    │ • Energy ∫  │    │           │ │     │
│   │   │   → Next pg │    │             │    │           │ │     │
│   │   └─────────────┘    └─────────────┘    └───────────┘ │     │
│   │                                                        │     │
│   │   ┌─────────────────────────────────────────────────┐ │     │
│   │   │              AUTO-ZERO COMPENSATION              │ │     │
│   │   │                                                  │ │     │
│   │   │  When relay turns OFF:                           │ │     │
│   │   │  • Wait 300ms for settling                       │ │     │
│   │   │  • Re-measure ACS712 zero-current baseline       │ │     │
│   │   │  • Update ACS_LIVE_MID                           │ │     │
│   │   │                                                  │ │     │
│   │   └─────────────────────────────────────────────────┘ │     │
│   │                                                        │     │
│   └────────────────────────────────────────────────────────┘     │
│                                                                 │
│   ┌───────────────┐                                             │
│   │ ERROR HANDLER │                                             │
│   │               │                                             │
│   │ • Catch OSError│                                             │
│   │ • Reinit I²C   │                                             │
│   │ • Increment    │                                             │
│   │   error_count  │                                             │
│   └───────────────┘                                             │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

### RMS Calculation

```python
def get_rms_voltage():
    """RMS voltage from ZMPT101B using calibrated values."""
    sum_sq = 0
    samples = 200

    for _ in range(samples):
        val = adc_v.read() - V_MIDPOINT  # Remove DC offset
        sum_sq += val * val
        time.sleep_us(100)  # ~20ms total sampling

    rms_raw = math.sqrt(sum_sq / samples)
    voltage = rms_raw * V_SCALE

    if voltage < V_NOISE_THRESH:
        return 0.0
    return round(voltage, 1)
```

### Dynamic Zero Compensation

The ACS712 zero-point drifts with temperature. To compensate:

```python
def update_current_baseline():
    """Re-zero current sensor when relay is OFF (no load)."""
    global ACS_LIVE_MID
    total_v = 0
    samples = 300

    for _ in range(samples):
        raw = adc_i.read()
        v = (raw / 4095.0) * 3.3
        total_v += v
        time.sleep_us(100)

    ACS_LIVE_MID = total_v / samples

# Called when relay transitions from ON → OFF
if current_relay == 1 and last_relay_state == 0:
    time.sleep_ms(300)  # Wait for current to settle
    update_current_baseline()
```

---

## 4.5 OLED Display Screens

### Screen 0: Live Readings

```
┌────────────────────────┐
│     == LIVE ==         │
│                        │
│  Volt: 228.5 V         │
│  Curr: 2.34 A          │
│  Powr: 534.7 W         │
│                        │
└────────────────────────┘
```

### Screen 1: Energy & Relay

```
┌────────────────────────┐
│    == ENERGY ==        │
│                        │
│  Total used:           │
│  0.2345 kWh            │
│                        │
│  Relay: ON             │
└────────────────────────┘
```

### Screen 2: Control Instructions

```
┌────────────────────────┐
│    == CONTROL ==       │
│                        │
│  Relay: OFF            │
│                        │
│  Short tap:            │
│    Toggle relay        │
│  Long press: Menu      │
└────────────────────────┘
```

### Screen 3: Debug Info

```
┌────────────────────────┐
│    == DEBUG ==     E:0 │
│  Vrms:156.2            │
│  Irms:0.2341V          │
│  Iavg:2.374V           │
│  Iliv:2.373V           │
│  Isen:0.1075           │
└────────────────────────┘
```

---

## 4.6 Touch Input Handling

### Input Types

| Gesture | Duration | Action |
|---------|----------|--------|
| Short Tap | 50-600ms | Toggle relay |
| Long Press | >600ms | Next screen |

### Implementation

```python
# Touch button handling in main loop
is_touched = touch_btn.value() == 1

if is_touched and not btn_pressed:
    btn_pressed = True
    press_start = time.ticks_ms()

elif not is_touched and btn_pressed:
    btn_pressed = False
    duration = time.ticks_diff(time.ticks_ms(), press_start)

    if duration > 600:
        # Long press → next screen
        current_screen = (current_screen + 1) % total_screens
        last_update = 0
    elif duration > 50:
        # Short tap → toggle relay
        relay.value(not relay.value())
        last_update = 0
```

---

## 4.7 Error Handling

### I²C Recovery

```python
def safe_oled_write(func):
    """Wrapper to handle I2C errors on OLED."""
    global error_count
    try:
        func()
    except OSError:
        error_count += 1
        time.sleep_ms(100)
        try:
            init_hardware()  # Reinitialize on error
            func()
        except:
            pass
```

### Main Loop Protection

```python
while True:
    try:
        # ... main loop code ...
        time.sleep_ms(20)
        
    except Exception as e:
        error_count += 1
        time.sleep_ms(500)
        try:
            init_hardware()
        except:
            pass
```

---

## 4.8 Uploading Firmware

### Prerequisites

```bash
# Install tools
pip install esptool adafruit-ampy

# Flash MicroPython firmware (one-time)
esptool.py --chip esp32 erase_flash
esptool.py --chip esp32 write_flash -z 0x1000 esp32-micropython.bin
```

### Upload Files

```bash
# Upload OLED driver
ampy -p COM3 put device/ssd1306.py

# Upload calibration script
ampy -p COM3 put device/calibrate.py

# Run calibration
ampy -p COM3 run device/calibrate.py

# After calibration, upload main app
ampy -p COM3 put device/main.py
ampy -p COM3 put device/boot.py

# Reset ESP32 to start
```

### File Sizes

| File | Size | Purpose |
|------|------|---------|
| ssd1306.py | ~3 KB | OLED driver |
| calibrate.py | ~6 KB | Calibration wizard |
| main.py | ~7 KB | Main application |
| boot.py | ~100 B | Boot stub |
| calibration.json | ~400 B | Calibration data |

---

## 4.9 Memory Usage

| Resource | Used | Available |
|----------|------|-----------|
| Flash | ~520 KB | 4 MB |
| RAM | ~45 KB | 520 KB |
| Heap (after boot) | ~120 KB free | - |

---

## Next: [Backend API →](./05-backend-api.md)
