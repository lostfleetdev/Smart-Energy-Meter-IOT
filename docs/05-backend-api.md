# 5. Backend API

## 5.1 Overview

The backend is a Flask application that:

1. **Subscribes to MQTT** — Receives telemetry from ESP32 devices
2. **Streams via SSE** — Pushes live data to web dashboard
3. **Serves REST API** — History, relay control, ML predictions
4. **Runs ML Models** — Power prediction and anomaly detection

---

## 5.2 Architecture

```
┌─────────────────────────────────────────────────────────────────────────┐
│                          BACKEND SERVER                                  │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                          │
│   ┌───────────────┐                                                      │
│   │  MQTT CLIENT  │                                                      │
│   │               │                                                      │
│   │  Topics:      │                                                      │
│   │  • telemetry  │──────┬──────────────────────────────────────────┐   │
│   │  • relay/set  │      │                                          │   │
│   │  • relay/state│      │                                          │   │
│   └───────────────┘      │                                          │   │
│                          ▼                                          │   │
│   ┌───────────────────────────────────────────────────────────────┐ │   │
│   │                    MESSAGE HANDLER                             │ │   │
│   │                                                                │ │   │
│   │   on_message() ──► Parse JSON ──► Anomaly Check ──► Buffer    │ │   │
│   │                                         │              │       │ │   │
│   │                                         ▼              ▼       │ │   │
│   │                                    ML Service      data_buffer │ │   │
│   │                                         │              │       │ │   │
│   │                                         ▼              ▼       │ │   │
│   │                                    Prediction      data.csv    │ │   │
│   │                                                                │ │   │
│   └───────────────────────────────────────────────────────────────┘ │   │
│                                                                      │   │
│   ┌───────────────────────────────────────────────────────────────┐ │   │
│   │                      FLASK APP (:5000)                         │ │   │
│   │                                                                │ │   │
│   │   Routes:                                                      │ │   │
│   │   ┌──────────────────────────────────────────────────────────┐ │ │   │
│   │   │  GET  /           → Dashboard (index.html)               │ │ │   │
│   │   │  GET  /stream     → SSE live telemetry                   │ │ │   │
│   │   │  GET  /history    → Historical readings (CSV)            │ │ │   │
│   │   │  GET  /stats      → Aggregated statistics                │ │ │   │
│   │   │  GET  /relay      → Current relay state                  │ │ │   │
│   │   │  POST /relay      → Set relay state                      │ │ │   │
│   │   └──────────────────────────────────────────────────────────┘ │ │   │
│   │                                                                │ │   │
│   │   ML Routes:                                                   │ │   │
│   │   ┌──────────────────────────────────────────────────────────┐ │ │   │
│   │   │  GET  /ml/info           → Model information             │ │ │   │
│   │   │  GET  /ml/appliances     → Available appliances          │ │ │   │
│   │   │  GET  /ml/predict/:app   → Power prediction              │ │ │   │
│   │   │  POST /ml/anomaly/:app   → Anomaly detection             │ │ │   │
│   │   │  GET  /ml/predictions    → All predictions               │ │ │   │
│   │   │  GET  /ml/history/:app   → Power history                 │ │ │   │
│   │   │  POST /ml/reading/:app   → Add power reading             │ │ │   │
│   │   │  POST /ml/simulate       → Simulate readings             │ │ │   │
│   │   └──────────────────────────────────────────────────────────┘ │ │   │
│   │                                                                │ │   │
│   └───────────────────────────────────────────────────────────────┘ │   │
│                                                                      │   │
│   ┌───────────────┐                                                  │   │
│   │  ML SERVICE   │                                                  │   │
│   │               │                                                  │   │
│   │  Models:      │                                                  │   │
│   │  • LightGBM   │  ← Power prediction                              │   │
│   │  • IsoForest  │  ← Anomaly detection                             │   │
│   │  • Classifier │  ← On/Off prediction                             │   │
│   │               │                                                  │   │
│   └───────────────┘                                                  │   │
│                                                                          │
└─────────────────────────────────────────────────────────────────────────┘
```

---

## 5.3 Configuration

### Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `MQTT_BROKER` | `localhost` | MQTT broker hostname |
| `MQTT_PORT` | `1883` | MQTT broker port |
| `DEVICE_ID` | `device01` | Device identifier |

### MQTT Topics

| Topic | Direction | QoS | Purpose |
|-------|-----------|-----|---------|
| `energy/{device_id}/telemetry` | Subscribe | 1 | Receive sensor data |
| `energy/{device_id}/relay/set` | Publish | 1 | Send relay command |
| `energy/{device_id}/relay/state` | Subscribe | 1 | Receive relay state |

---

## 5.4 Quick Start

### Local Development

```bash
cd backend

# Install dependencies (using uv)
uv sync

# Or with pip
pip install flask flask-cors paho-mqtt

# Start NanoMQ broker (in another terminal)
nanomq start

# Run backend
uv run python main.py
# Or: python main.py
```

### Output

```
╔══════════════════════════════════════════════════╗
║     Smart Energy Monitor — Backend Server        ║
╠══════════════════════════════════════════════════╣
║  MQTT Broker: localhost:1883                     ║
║  Device ID:   device01                           ║
║  Data File:   data.csv                           ║
╚══════════════════════════════════════════════════╝
[ML] Loaded predictor: ac_1
[ML] Loaded anomaly detector: ac_1
[ML] Loaded classifier: ac_1
...
[MQTT] Connected: Success
 * Running on http://0.0.0.0:5000
```

---

## 5.5 MQTT Message Format

### Telemetry (Device → Server)

```json
{
    "voltage": 228.5,
    "current": 2.34,
    "power": 534.7,
    "energy": 1.234,
    "relay": true,
    "appliance": "fridge"
}
```

### Relay Command (Server → Device)

```
"1"  →  Turn relay ON
"0"  →  Turn relay OFF
```

### Relay State (Device → Server)

```
"1"  →  Relay is ON
"0"  →  Relay is OFF
```

---

## 5.6 SSE Streaming

### Endpoint: `GET /stream`

Server-Sent Events for real-time telemetry updates.

```javascript
// Client-side JavaScript
const eventSource = new EventSource('/stream');

eventSource.onmessage = (event) => {
    const data = JSON.parse(event.data);
    console.log('Telemetry:', data);
    // {voltage: 228.5, current: 2.34, power: 534.7, ...}
};
```

### Stream Format

```
data: {"voltage": 228.5, "current": 2.34, "power": 534.7, "timestamp": "2026-04-07T10:30:00", "anomaly": false}

data: {"voltage": 229.1, "current": 2.35, "power": 538.4, "timestamp": "2026-04-07T10:30:01", "anomaly": false}
```

---

## 5.7 Data Storage

### CSV Format (data.csv)

| Column | Type | Description |
|--------|------|-------------|
| timestamp | ISO 8601 | Reading timestamp |
| voltage | float | RMS voltage (V) |
| current | float | RMS current (A) |
| power | float | Power (W) |
| energy | float | Cumulative energy (kWh) |
| anomaly | boolean | ML anomaly flag |

### Sample Data

```csv
timestamp,voltage,current,power,energy,anomaly
2026-04-07T10:30:00,228.5,2.34,534.7,1.234,False
2026-04-07T10:30:01,229.1,2.35,538.4,1.235,False
2026-04-07T10:30:02,227.8,4.56,1038.8,1.238,True
```

---

## 5.8 ML Service

### Supported Appliances

| Appliance | Predictor | Classifier | Anomaly |
|-----------|-----------|------------|---------|
| `ac_1` | ✓ | ✓ | ✓ |
| `ac_2` | ✓ | ✓ | ✓ |
| `boiler` | ✓ | ✓ | ✓ |
| `fridge` | ✓ | ✓ | ✓ |
| `washing_machine` | ✓ | ✓ | ✓ |
| `dishwasher` | ✓ | - | ✓ |

### Power Prediction

Uses LightGBM with features:
- Hour of day, day of week, weekend flag
- Lag features (1h, 24h)
- Rolling statistics (6h mean, std)
- Difference features

### Anomaly Detection

Two-stage detection:
1. **Z-score** — Flag if |z| > 3
2. **Isolation Forest** — ML-based pattern detection

### ON Thresholds

| Appliance | Threshold (W) |
|-----------|---------------|
| AC | 100 |
| Boiler | 200 |
| Fridge | 30 |
| Washing Machine | 50 |
| Dishwasher | 20 |

---

## 5.9 Anomaly Check Logic

```python
def check_anomaly(reading):
    """Check for anomaly using ML service or fallback to Z-score."""
    power = reading.get("power", 0)
    
    # Try ML-based detection
    if "fridge" in ml_service.anomaly_models:
        result = ml_service.detect_anomaly("fridge", power)
        if result and not result.get("error"):
            return result.get("is_anomaly", False)
    
    # Fallback: Simple Z-score
    with lock:
        if len(data_buffer) < 20:
            return False
        
        powers = [d["power"] for d in data_buffer]
    
    mean = sum(powers) / len(powers)
    variance = sum((p - mean) ** 2 for p in powers) / len(powers)
    std = variance ** 0.5
    
    if std < 1:
        return False
    
    z_score = abs(reading["power"] - mean) / std
    return z_score > 3
```

---

## 5.10 Thread Model

```
┌─────────────────────────────────────────────────────────────────┐
│                       THREAD ARCHITECTURE                        │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│   Main Thread                                                    │
│   ┌───────────────────────────────────────────────────────────┐ │
│   │                                                           │ │
│   │   Flask.run(threaded=True)                                │ │
│   │                                                           │ │
│   │   • HTTP request handling                                 │ │
│   │   • SSE streaming (per client)                            │ │
│   │   • ML predictions                                        │ │
│   │                                                           │ │
│   └───────────────────────────────────────────────────────────┘ │
│                                                                  │
│   MQTT Thread (daemon)                                           │
│   ┌───────────────────────────────────────────────────────────┐ │
│   │                                                           │ │
│   │   mqtt_loop()                                             │ │
│   │                                                           │ │
│   │   • Connection management                                 │ │
│   │   • Message callbacks                                     │ │
│   │   • Auto-reconnect                                        │ │
│   │                                                           │ │
│   └───────────────────────────────────────────────────────────┘ │
│                                                                  │
│   Shared State (with threading.Lock)                             │
│   ┌───────────────────────────────────────────────────────────┐ │
│   │                                                           │ │
│   │   data_buffer = deque(maxlen=100)                         │ │
│   │   relay_state = {"on": False}                             │ │
│   │   sse_clients = set()                                     │ │
│   │                                                           │ │
│   └───────────────────────────────────────────────────────────┘ │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

---

## 5.11 Dependencies

### pyproject.toml

```toml
[project]
name = "smart-energy-backend"
version = "1.0.0"
requires-python = ">=3.10"
dependencies = [
    "flask>=3.0",
    "flask-cors>=4.0",
    "paho-mqtt>=2.0",
    "scikit-learn>=1.4",
    "lightgbm>=4.0",
]
```

---

## Next: [ML Pipeline →](./06-ml-pipeline.md)
