# Smart Energy Monitor — Backend

Flask + MQTT backend for the ML-IoT smart energy monitor.

## Quick Start

```bash
# Install dependencies
uv sync

# Run (requires nanomq broker on localhost:1883)
uv run python main.py
```

Open http://localhost:5000

## Architecture

```
┌─────────────┐     MQTT      ┌─────────────────────────────────┐
│   ESP32     │ ────────────► │         main.py                 │
│   Device    │               │  ┌───────────┐  ┌───────────┐  │
└─────────────┘               │  │MQTT Thread│  │Flask App  │  │
                              │  │  paho-mqtt│  │  /        │  │
                              │  │  subscribe│  │  /stream  │──┼──► Browser
                              │  │  ↓        │  │  /relay   │  │    (SSE)
                              │  │  deque ───┼──│  /history │  │
                              │  └───────────┘  └───────────┘  │
                              │                     ↓          │
                              │                 data.csv       │
                              └─────────────────────────────────┘
```

## API Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/` | GET | Dashboard UI |
| `/stream` | GET | SSE live telemetry (connect on-demand) |
| `/history?limit=N` | GET | Last N readings from CSV |
| `/relay` | GET | Current relay state |
| `/relay` | POST | Set relay (`{"on": true/false}`) |
| `/stats` | GET | Buffer statistics |

## MQTT Topics

| Topic | Direction | Payload |
|-------|-----------|---------|
| `energy/{device}/telemetry` | Device → Server | `{"voltage":V,"current":I,"power":W,"energy":kWh}` |
| `energy/{device}/relay/set` | Server → Device | `1` or `0` |
| `energy/{device}/relay/state` | Device → Server | `1` or `0` |

## Environment Variables

```bash
MQTT_BROKER=localhost   # MQTT broker host
MQTT_PORT=1883          # MQTT broker port
DEVICE_ID=device01      # Device identifier
```

## Files

- `main.py` — Flask app + MQTT client
- `static/index.html` — Material Design dashboard
- `data.csv` — Telemetry log (auto-created)
