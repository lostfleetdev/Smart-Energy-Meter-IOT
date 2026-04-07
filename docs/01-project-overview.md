# 1. Project Overview

## 1.1 Introduction

The **Smart Energy Monitor** is a per-appliance energy monitoring system designed to provide granular, real-time power consumption data at the device level. Unlike traditional whole-house smart meters that only show aggregate consumption, this system deploys individual monitoring units for each appliance, enabling precise tracking of energy usage patterns.

### Key Capabilities

| Feature | Description |
|---------|-------------|
| **Real-time Monitoring** | Voltage, current, and power measurements every second |
| **Remote Control** | Relay-based ON/OFF switching via web dashboard |
| **ML Anomaly Detection** | Isolation Forest model detects unusual consumption patterns |
| **Cloud Connectivity** | MQTT/WebSocket for live data streaming |
| **Local Display** | OLED screen shows readings even without network |
| **Historical Analytics** | Power usage trends and cost estimation |

---

## 1.2 Problem Statement

### The Challenge

Household electricity bills provide no granular breakdown per appliance. Existing smart meters measure whole-premises usage, leaving consumers unable to:

1. **Identify energy hogs** — Which appliance is consuming the most?
2. **Detect faults early** — Is the AC drawing 30% more power than usual?
3. **Control remotely** — Can I switch off the geyser from work?
4. **Track patterns** — When does peak consumption occur?

### Current Limitations

| Approach | Limitation |
|----------|------------|
| **Standard Meters** | Only total kWh, no device breakdown |
| **NILM Systems** | Complex algorithms, probabilistic results, expensive |
| **Smart Plugs** | Limited to power monitoring, no ML insights |

---

## 1.3 Proposed Solution

### Four-Layer Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                    SMART ENERGY MONITOR                         │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  Layer 4: VISUALIZATION & CONTROL                               │
│  ┌───────────────────────────────────────────────────────────┐  │
│  │  • Web Dashboard (Material Design 2)                       │  │
│  │  • Real-time charts (Chart.js)                             │  │
│  │  • Relay control toggle                                    │  │
│  │  • Historical data viewer                                  │  │
│  └───────────────────────────────────────────────────────────┘  │
│                              ▲                                   │
│                              │ SSE / REST API                    │
│  Layer 3: INTELLIGENCE (ML)                                      │
│  ┌───────────────────────────────────────────────────────────┐  │
│  │  • LightGBM power predictor                                │  │
│  │  • Isolation Forest anomaly detector                       │  │
│  │  • On/Off classifier                                       │  │
│  │  • Feature engineering pipeline                            │  │
│  └───────────────────────────────────────────────────────────┘  │
│                              ▲                                   │
│                              │ JSON telemetry                    │
│  Layer 2: CONNECTIVITY                                           │
│  ┌───────────────────────────────────────────────────────────┐  │
│  │  • WiFi 802.11 b/g/n (2.4 GHz)                             │  │
│  │  • MQTT protocol (QoS 1)                                   │  │
│  │  • NanoMQ broker                                           │  │
│  │  • WebSocket for push events                               │  │
│  └───────────────────────────────────────────────────────────┘  │
│                              ▲                                   │
│                              │ Raw sensor data                   │
│  Layer 1: SENSING & MEASUREMENT                                  │
│  ┌───────────────────────────────────────────────────────────┐  │
│  │  • ZMPT101B voltage transformer (0-250V AC)                │  │
│  │  • ACS712 20A Hall-effect current sensor                   │  │
│  │  • ESP32 12-bit ADC @ 200 samples/measurement              │  │
│  │  • RMS calculation, power factor computation               │  │
│  └───────────────────────────────────────────────────────────┘  │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

---

## 1.4 Measured Parameters

| Metric | Formula | Description |
|--------|---------|-------------|
| **RMS Voltage** | `√(Σv²/n)` | True voltage accounting for AC waveform |
| **RMS Current** | `√(Σi²/n)` | True current with dynamic zero compensation |
| **Real Power (W)** | `V × I × PF` | Actual power consumed |
| **Apparent Power (VA)** | `V × I` | Total power drawn from supply |
| **Power Factor** | `Real / Apparent` | Efficiency metric (0-1) |
| **Energy (kWh)** | `∫ P dt` | Cumulative consumption over time |

---

## 1.5 Use Cases

### Residential
- Track appliance-wise electricity costs
- Identify inefficient devices
- Schedule high-consumption tasks during off-peak hours

### Commercial
- Monitor server room power consumption
- Detect equipment failures before they escalate
- Generate energy audit reports

### Industrial
- Per-machine energy accounting
- Predictive maintenance via anomaly detection
- Compliance with energy regulations

---

## 1.6 Technical Specifications

| Parameter | Specification |
|-----------|---------------|
| **Input Voltage** | 100-250V AC, 50/60 Hz |
| **Max Current** | 20A |
| **Measurement Accuracy** | ±2% (after calibration) |
| **Sampling Rate** | 200 samples per measurement |
| **Telemetry Interval** | 1-60 seconds (configurable) |
| **Communication** | WiFi 2.4 GHz, MQTT over TCP |
| **Display** | 128×64 OLED, 4 screens |
| **Control** | Single-pole relay (10A/250VAC) |
| **Power Supply** | HLK-PM01 (230VAC → 5VDC) |

---

## 1.7 Novelty & Contributions

1. **Per-appliance granularity** — Each device gets its own monitor
2. **Dynamic zero compensation** — Auto-calibrates current sensor when relay is OFF
3. **ML-based anomaly detection** — Not just threshold alerts, but pattern-based
4. **Offline-capable** — OLED shows readings even without network
5. **Single-command deployment** — `deploy.sh` sets up entire cloud stack

---

## Next: [System Architecture →](./02-system-architecture.md)
