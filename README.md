# Smart Energy Monitor — ML-IoT Project

> **Sem 6 Project** | Per-appliance energy monitoring with ML anomaly detection

## Overview

A plug-and-play smart metering system built on ESP32 that measures real-time voltage, current, and power consumption, transmits data to a cloud backend, and uses machine learning for anomaly detection — enabling remote monitoring and appliance control from a web dashboard.

---

## Problem Statement

Household energy bills provide no granular breakdown per appliance. Existing smart meters measure whole-premises usage. This project deploys one compact monitor per appliance for precise, isolated consumption data.

---

## Architecture

```
┌─────────────────┐     MQTT/WS      ┌──────────────────────────────────────┐
│   ESP32 Device  │ ───────────────► │           Cloud Backend              │
│  (MicroPython)  │   WiFi 2.4GHz    │  ┌──────────┐  ┌────────────────┐   │
│                 │                   │  │  nanomq  │  │   FastAPI +    │   │
│ • ZMPT101B (V)  │                   │  │  (MQTT)  │──│   SQLite +     │   │
│ • ACS712 (I)    │                   │  └──────────┘  │ IsolationForest│   │
│ • OLED Display  │                   │                └────────────────┘   │
│ • Relay Module  │   ◄─────────────  │                       │             │
│ • Touch Sensor  │   Control Cmds    │              ┌────────▼────────┐   │
└─────────────────┘                   │              │  dashboard.html │   │
                                      │              │  (Material 2)   │   │
                                      └──────────────┴─────────────────────┘
```

---

## Hardware Stack

| Component       | Role                                  | Connection    |
|-----------------|---------------------------------------|---------------|
| **ESP32**       | MCU + WiFi (802.11 b/g/n)             | —             |
| **ZMPT101B**    | AC Voltage sensing (0-250V)           | Parallel, GPIO35 |
| **ACS712 20A**  | AC Current sensing (0-20A)            | Series on Live, GPIO34 |
| **HLK-PM01**    | 230V AC → 5V DC isolated PSU          | Parallel      |
| **Relay Module**| Remote ON/OFF switching               | GPIO2         |
| **SSD1306 OLED**| 128×64 local display                  | I²C (SCL:18, SDA:21) |
| **Touch Sensor**| Capacitive UI toggle                  | GPIO4         |

---

## Measurements

| Metric           | Method                                           |
|------------------|--------------------------------------------------|
| RMS Voltage      | ADC sampling @ ZMPT101B, calibrated scaling      |
| RMS Current      | ADC sampling @ ACS712, dynamic zero-point        |
| Real Power (W)   | V × I (assuming resistive load / PF ≈ 1)         |
| Apparent Power   | V × I (VA)                                       |
| Power Factor     | Real / Apparent                                  |
| Energy (kWh)     | ∫ Power × dt (numerical integration)             |

---

## Project Structure

```
IOT/
├── device/                  # ESP32 MicroPython firmware
│   ├── main.py              # Main loop: sensing, display, relay control
│   ├── calibrate.py         # Interactive sensor calibration (OLED-guided)
│   ├── calibration.json     # Stored calibration constants
│   ├── boot.py              # MicroPython boot stub
│   └── ssd1306.py           # OLED driver library
│
├── ML/                      # Machine Learning
│   └── train.ipynb          # IsolationForest training notebook (TODO)
│
├── ml_iot_arch_v3.svg       # Architecture diagram
└── README.md                # This file
```

### Missing Components (To Implement)

- [ ] `backend/` — FastAPI server, SQLite, MQTT client, ML inference
- [ ] `dashboard.html` — Material 2 web UI
- [ ] `deploy.sh` — DigitalOcean deployment script
- [ ] WiFi + MQTT connectivity in `device/main.py`
- [ ] IsolationForest training pipeline

---

## Device Firmware

### Calibration (`calibrate.py`)

Interactive 2-step calibration via OLED + touch button:

1. **No-Load**: Measures ADC zero-points for voltage & current sensors
2. **With-Load**: Uses known appliance (e.g., 600W kettle) to compute scaling factors

Outputs `calibration.json`:
```json
{
  "v_midpoint": 2965,
  "v_scale": 0.2103,
  "acs_midpoint_v": 2.373,
  "acs_sensitivity": 0.1075,
  "v_noise_threshold": 5.78,
  "i_noise_threshold": 0.107
}
```

### Main Loop (`main.py`)

- **Sensor Sampling**: 200 samples/measurement, RMS calculation
- **Dynamic Zero**: Re-calibrates current baseline when relay turns OFF
- **OLED Screens** (4 total, cycle with long-press):
  - Live: V, I, W
  - Energy: cumulative kWh, relay status
  - Control: relay toggle instructions
  - Debug: raw ADC values, midpoints, error count
- **Touch Input**: Short tap = toggle relay; Long press = next screen
- **Error Recovery**: Auto-reinitializes I²C/OLED on failures

---

## Connectivity (Planned)

| Protocol   | Purpose                                      |
|------------|----------------------------------------------|
| **MQTT**   | Periodic telemetry (1–5 min), `device/{id}/telemetry` |
| **WebSocket** | Instant push on anomaly / relay state change |

---

## Backend (Planned)

```
backend/
├── server.py          # FastAPI app
│   ├── POST /telemetry      # Ingest MQTT-bridged data
│   ├── GET  /history        # Query historical readings
│   ├── POST /control        # Relay commands
│   └── WS   /ws             # Real-time anomaly alerts
│
├── models/
│   └── anomaly.pkl    # Trained IsolationForest
│
└── data/
    └── energy.db      # SQLite storage
```

### ML Features (IsolationForest)

| Feature    | Description                          |
|------------|--------------------------------------|
| `power`    | Instantaneous watts                  |
| `pf`       | Power factor                         |
| `hour`     | Hour of day (0–23)                   |
| `day`      | Day of week (0–6)                    |

Detects: consumption spikes, appliance faults, unusual usage patterns.

---

## Deployment (Planned)

Single-command deployment to DigitalOcean:
```bash
./deploy.sh   # Installs nanomq, Python deps, starts services
```

---

## Quick Start

### 1. Flash ESP32

```bash
# Install esptool + ampy
pip install esptool adafruit-ampy

# Flash MicroPython firmware (one-time)
esptool.py --chip esp32 erase_flash
esptool.py --chip esp32 write_flash -z 0x1000 esp32-micropython.bin

# Upload device files
ampy -p COM3 put device/ssd1306.py
ampy -p COM3 put device/calibrate.py
ampy -p COM3 put device/main.py
ampy -p COM3 put device/boot.py
```

### 2. Calibrate

```bash
ampy -p COM3 run device/calibrate.py
# Follow OLED prompts with touch button
```

### 3. Run

Reset ESP32 — `main.py` runs automatically.

---

## Pin Reference

| GPIO | Function     | Notes                        |
|------|--------------|------------------------------|
| 35   | Voltage ADC  | ZMPT101B signal              |
| 34   | Current ADC  | ACS712 signal                |
| 18   | I²C SCL      | OLED clock                   |
| 21   | I²C SDA      | OLED data                    |
| 2    | Relay        | Active LOW (1=OFF, 0=ON)     |
| 4    | Touch Sensor | HIGH when touched            |

---

## Evaluation Summary

### ✅ Implemented

- Voltage & current RMS measurement with calibration
- Power calculation and energy accumulation
- OLED multi-screen UI with touch navigation
- Relay control with auto-zero compensation
- Robust error handling and recovery

### ⚠️ Partially Complete

- ML training notebook (empty file exists)
- Architecture diagram (SVG present)

### ❌ Not Yet Implemented

- WiFi connectivity in device firmware
- MQTT/WebSocket communication
- Backend server (FastAPI + SQLite)
- IsolationForest anomaly detection
- Web dashboard
- Deployment scripts

---

## License

Academic project — Semester 6