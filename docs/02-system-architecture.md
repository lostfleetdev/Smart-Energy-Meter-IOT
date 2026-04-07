# 2. System Architecture

## 2.1 High-Level Architecture

The Smart Energy Monitor follows a three-tier IoT architecture with local processing at the edge, cloud-based storage and intelligence, and web-based visualization.

```
┌─────────────────────────────────────────────────────────────────────────────────┐
│                              SYSTEM ARCHITECTURE                                 │
├─────────────────────────────────────────────────────────────────────────────────┤
│                                                                                  │
│   ┌─────────────────┐                                                            │
│   │   EDGE DEVICE   │                                                            │
│   │    (ESP32)      │                                                            │
│   │                 │                                                            │
│   │ ┌─────────────┐ │                                                            │
│   │ │  Sensors    │ │         WiFi 2.4 GHz                                       │
│   │ │ ZMPT + ACS  │ │             │                                              │
│   │ └─────────────┘ │             │                                              │
│   │       ▼         │             │                                              │
│   │ ┌─────────────┐ │             │                                              │
│   │ │  ADC + RMS  │ │             │                                              │
│   │ │ Calculation │ │             │                                              │
│   │ └─────────────┘ │             │                                              │
│   │       ▼         │             ▼                                              │
│   │ ┌─────────────┐ │    ┌───────────────┐    ┌─────────────────────────────┐   │
│   │ │  MicroPy    │─┼────│   MQTT Broker │────│      BACKEND SERVER          │   │
│   │ │  Firmware   │ │    │   (NanoMQ)    │    │                              │   │
│   │ └─────────────┘ │    │   Port 1883   │    │  ┌─────────┐  ┌───────────┐  │   │
│   │       │         │    └───────────────┘    │  │  Flask  │  │    ML     │  │   │
│   │       ▼         │             │           │  │   API   │──│  Service  │  │   │
│   │ ┌─────────────┐ │             │           │  │  :5000  │  │           │  │   │
│   │ │ OLED + Relay│ │             │           │  └─────────┘  └───────────┘  │   │
│   │ │   Display   │ │             │           │       │              │       │   │
│   │ └─────────────┘ │             │           │       ▼              ▼       │   │
│   └─────────────────┘             │           │  ┌─────────┐  ┌───────────┐  │   │
│                                    │           │  │  SSE    │  │  Models   │  │   │
│                                    │           │  │ Stream  │  │  .pkl     │  │   │
│                                    │           │  └─────────┘  └───────────┘  │   │
│                                    │           └─────────────────────────────┘   │
│                                    │                       │                     │
│                                    │                       ▼                     │
│                                    │           ┌─────────────────────────────┐   │
│                                    │           │      WEB DASHBOARD           │   │
│                                    │           │   (Material Design 2)        │   │
│                                    │           │                              │   │
│                                    │           │  • Live power gauges         │   │
│                                    │           │  • Historical charts         │   │
│                                    │           │  • ML predictions            │   │
│                                    │           │  • Relay control             │   │
│                                    │           │  • Anomaly alerts            │   │
│                                    │           └─────────────────────────────┘   │
│                                                                                  │
└─────────────────────────────────────────────────────────────────────────────────┘
```

---

## 2.2 Data Flow Diagram

```
┌─────────────────────────────────────────────────────────────────────────────────┐
│                              DATA FLOW                                           │
├─────────────────────────────────────────────────────────────────────────────────┤
│                                                                                  │
│  ┌──────────────────────────────────────────────────────────────────────────┐   │
│  │                           SENSING PHASE                                   │   │
│  │                                                                           │   │
│  │   AC Mains 230V ──┬──► ZMPT101B ──► ADC(GPIO35) ──► RMS Voltage          │   │
│  │                   │                                                       │   │
│  │   Load Current ───┴──► ACS712 ───► ADC(GPIO34) ──► RMS Current           │   │
│  │                                                                           │   │
│  │   [200 samples @ 100µs intervals → ~20ms per measurement]                 │   │
│  │                                                                           │   │
│  └──────────────────────────────────────────────────────────────────────────┘   │
│                                    │                                             │
│                                    ▼                                             │
│  ┌──────────────────────────────────────────────────────────────────────────┐   │
│  │                           PROCESSING PHASE                                │   │
│  │                                                                           │   │
│  │   V_rms, I_rms ──► P = V × I ──► Energy += P × dt ──► Display on OLED    │   │
│  │                                                                           │   │
│  │   [Local display updates every 1 second]                                  │   │
│  │                                                                           │   │
│  └──────────────────────────────────────────────────────────────────────────┘   │
│                                    │                                             │
│                                    ▼                                             │
│  ┌──────────────────────────────────────────────────────────────────────────┐   │
│  │                         TRANSMISSION PHASE                                │   │
│  │                                                                           │   │
│  │   JSON Payload ──► MQTT Publish ──► Topic: energy/{device_id}/telemetry  │   │
│  │                                                                           │   │
│  │   {                                                                       │   │
│  │     "voltage": 228.5,                                                     │   │
│  │     "current": 2.34,                                                      │   │
│  │     "power": 534.7,                                                       │   │
│  │     "energy": 1.23,                                                       │   │
│  │     "relay": true                                                         │   │
│  │   }                                                                       │   │
│  │                                                                           │   │
│  │   [Telemetry every 1-60 seconds depending on config]                      │   │
│  │                                                                           │   │
│  └──────────────────────────────────────────────────────────────────────────┘   │
│                                    │                                             │
│                                    ▼                                             │
│  ┌──────────────────────────────────────────────────────────────────────────┐   │
│  │                        BACKEND PROCESSING                                 │   │
│  │                                                                           │   │
│  │   MQTT Subscribe ──► Parse JSON ──► Append to CSV ──► Anomaly Check      │   │
│  │                                           │               │               │   │
│  │                                           ▼               ▼               │   │
│  │                                      data.csv      ML Prediction          │   │
│  │                                                         │                 │   │
│  │                                                         ▼                 │   │
│  │                                               ┌─────────────────┐         │   │
│  │                                               │ is_anomaly: T/F │         │   │
│  │                                               │ z_score: 2.4    │         │   │
│  │                                               │ prediction: 420W│         │   │
│  │                                               └─────────────────┘         │   │
│  │                                                                           │   │
│  └──────────────────────────────────────────────────────────────────────────┘   │
│                                    │                                             │
│                                    ▼                                             │
│  ┌──────────────────────────────────────────────────────────────────────────┐   │
│  │                         VISUALIZATION PHASE                               │   │
│  │                                                                           │   │
│  │   SSE Stream (/stream) ──► Dashboard ──► Charts + Gauges + Alerts        │   │
│  │                                                                           │   │
│  │   REST API:                                                               │   │
│  │   • GET /history → Historical readings                                    │   │
│  │   • GET /stats → Current statistics                                       │   │
│  │   • GET /ml/predict/{appliance} → ML predictions                          │   │
│  │   • POST /relay → Control relay state                                     │   │
│  │                                                                           │   │
│  └──────────────────────────────────────────────────────────────────────────┘   │
│                                                                                  │
└─────────────────────────────────────────────────────────────────────────────────┘
```

---

## 2.3 Component Interaction

### MQTT Topics

| Topic | Direction | Purpose |
|-------|-----------|---------|
| `energy/{device_id}/telemetry` | Device → Server | Periodic sensor readings |
| `energy/{device_id}/relay/set` | Server → Device | Relay control command |
| `energy/{device_id}/relay/state` | Device → Server | Relay state confirmation |

### API Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/` | GET | Dashboard HTML |
| `/stream` | GET | SSE live telemetry |
| `/history` | GET | Historical readings |
| `/relay` | GET/POST | Relay state |
| `/stats` | GET | Aggregated statistics |
| `/ml/predict/{app}` | GET | Power prediction |
| `/ml/anomaly/{app}` | POST | Anomaly detection |

---

## 2.4 Sequence Diagram

```
┌──────────┐     ┌──────────┐     ┌──────────┐     ┌──────────┐     ┌──────────┐
│  Sensor  │     │  ESP32   │     │  NanoMQ  │     │  Backend │     │Dashboard │
└────┬─────┘     └────┬─────┘     └────┬─────┘     └────┬─────┘     └────┬─────┘
     │                │                │                │                │
     │  ADC Read      │                │                │                │
     │───────────────►│                │                │                │
     │                │                │                │                │
     │  Raw Values    │                │                │                │
     │◄───────────────│                │                │                │
     │                │                │                │                │
     │                │  RMS Calc      │                │                │
     │                │───────────────►│                │                │
     │                │                │                │                │
     │                │  MQTT Publish  │                │                │
     │                │───────────────►│                │                │
     │                │                │                │                │
     │                │                │  Subscribe     │                │
     │                │                │◄───────────────│                │
     │                │                │                │                │
     │                │                │  Forward Msg   │                │
     │                │                │───────────────►│                │
     │                │                │                │                │
     │                │                │                │  Anomaly Check │
     │                │                │                │───────────────►│
     │                │                │                │                │
     │                │                │                │  SSE Push      │
     │                │                │                │───────────────►│
     │                │                │                │                │
     │                │                │                │  Display       │
     │                │                │                │◄───────────────│
     │                │                │                │                │
```

---

## 2.5 Technology Stack

### Hardware
| Component | Technology |
|-----------|------------|
| Microcontroller | ESP32-WROOM-32D |
| Voltage Sensor | ZMPT101B |
| Current Sensor | ACS712-20A |
| Display | SSD1306 128×64 OLED |
| Control | 5V Relay Module |
| Power | HLK-PM01 AC-DC |

### Firmware
| Component | Technology |
|-----------|------------|
| Language | MicroPython 1.23 |
| ADC | 12-bit, 0-3.3V |
| I²C | SoftI2C @ 100kHz |
| WiFi | ESP32 native |

### Backend
| Component | Technology |
|-----------|------------|
| Web Framework | Flask 3.0 |
| MQTT Client | paho-mqtt |
| ML Framework | scikit-learn, LightGBM |
| MQTT Broker | NanoMQ |

### Frontend
| Component | Technology |
|-----------|------------|
| Design | Material Design 2 |
| Charts | Chart.js 4.4 |
| Icons | Material Icons |
| Data | Server-Sent Events |

---

## Next: [Hardware Design →](./03-hardware-design.md)
