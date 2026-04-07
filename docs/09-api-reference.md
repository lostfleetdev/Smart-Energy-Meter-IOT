# 9. API Reference

## 9.1 Base URL

```
Development:  http://localhost:5000
Production:   https://your-server.com
```

---

## 9.2 Core Endpoints

### GET /

Serves the dashboard HTML page.

**Response:** HTML page

---

### GET /stream

Server-Sent Events stream for real-time telemetry.

**Response:** SSE stream

```
Content-Type: text/event-stream

data: {"voltage": 228.5, "current": 2.34, "power": 534.7, "energy": 1.234, "timestamp": "2026-04-07T10:30:00", "anomaly": false}

data: {"voltage": 229.1, "current": 2.35, "power": 538.4, "energy": 1.235, "timestamp": "2026-04-07T10:30:01", "anomaly": false}
```

**JavaScript Usage:**
```javascript
const eventSource = new EventSource('/stream');
eventSource.onmessage = (event) => {
    const data = JSON.parse(event.data);
    console.log(data);
};
```

---

### GET /history

Get historical telemetry readings.

**Query Parameters:**

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `limit` | int | 100 | Number of readings to return |

**Response:**
```json
[
    {
        "timestamp": "2026-04-07T10:30:00",
        "voltage": "228.5",
        "current": "2.34",
        "power": "534.7",
        "energy": "1.234",
        "anomaly": "False"
    },
    ...
]
```

**Example:**
```bash
curl "http://localhost:5000/history?limit=50"
```

---

### GET /stats

Get aggregated statistics from the current buffer.

**Response:**
```json
{
    "count": 87,
    "avg_power": 456.23,
    "max_power": 1250.00,
    "min_power": 0.00,
    "relay": true,
    "sse_clients": 2
}
```

**Error Response:**
```json
{
    "error": "No data"
}
```

---

### GET /relay

Get current relay state.

**Response:**
```json
{
    "on": true
}
```

---

### POST /relay

Set relay state.

**Request Body:**
```json
{
    "on": true
}
```

If `on` is omitted, toggles current state.

**Response:**
```json
{
    "requested": true
}
```

**Example:**
```bash
# Turn ON
curl -X POST http://localhost:5000/relay \
     -H "Content-Type: application/json" \
     -d '{"on": true}'

# Toggle
curl -X POST http://localhost:5000/relay
```

---

## 9.3 ML Endpoints

### GET /ml/info

Get information about loaded ML models.

**Response:**
```json
{
    "models_dir": "/opt/energy-monitor/ML/models",
    "power_predictors": ["ac_1", "ac_2", "boiler", "fridge", "washing_machine", "dishwasher"],
    "anomaly_detectors": ["ac_1", "ac_2", "boiler", "fridge", "washing_machine", "dishwasher"],
    "classifiers": ["ac_1", "ac_2", "boiler", "fridge", "washing_machine"],
    "history_sizes": {
        "ac_1": 0,
        "ac_2": 0,
        "boiler": 0,
        "fridge": 12,
        "washing_machine": 0,
        "dishwasher": 0
    },
    "training_summary": {
        "trained_at": "2026-04-01T15:30:00",
        "power_metrics": [...],
        "classifier_metrics": [...],
        "anomaly_stats": [...]
    }
}
```

---

### GET /ml/appliances

List available appliances and their capabilities.

**Response:**
```json
{
    "appliances": ["ac_1", "ac_2", "boiler", "fridge", "washing_machine", "dishwasher"],
    "with_predictors": ["ac_1", "ac_2", "boiler", "fridge", "washing_machine", "dishwasher"],
    "with_anomaly_detection": ["ac_1", "ac_2", "boiler", "fridge", "washing_machine", "dishwasher"],
    "with_classifiers": ["ac_1", "ac_2", "boiler", "fridge", "washing_machine"]
}
```

---

### GET /ml/predict/{appliance}

Predict power consumption for the next hour.

**Path Parameters:**

| Parameter | Type | Description |
|-----------|------|-------------|
| `appliance` | string | Appliance name (e.g., `fridge`) |

**Response (Success):**
```json
{
    "appliance": "fridge",
    "predicted_power": 85.32,
    "unit": "watts",
    "features_used": {
        "hour": 14,
        "day_of_week": 1,
        "is_weekend": 0,
        "lag_1h": 82.5,
        "lag_24h": 88.2,
        "diff_1h": 2.8,
        "diff_24h": -2.9,
        "rolling_mean_6h": 84.1,
        "rolling_std_6h": 5.2
    },
    "timestamp": "2026-04-07T14:30:00"
}
```

**Response (Error - No Model):**
```json
{
    "error": "No model for fridge"
}
```

**Response (Error - Insufficient Data):**
```json
{
    "error": "Insufficient history (need 3+ readings)"
}
```

**Example:**
```bash
curl http://localhost:5000/ml/predict/fridge
```

---

### GET /ml/predict-onoff/{appliance}

Predict if appliance will be ON in the next hour.

**Path Parameters:**

| Parameter | Type | Description |
|-----------|------|-------------|
| `appliance` | string | Appliance name |

**Response:**
```json
{
    "appliance": "fridge",
    "will_be_on": true,
    "confidence": 92.3,
    "timestamp": "2026-04-07T14:30:00"
}
```

---

### POST /ml/anomaly/{appliance}

Detect if a power reading is anomalous.

**Path Parameters:**

| Parameter | Type | Description |
|-----------|------|-------------|
| `appliance` | string | Appliance name |

**Request Body:**
```json
{
    "power": 534.7
}
```

**Response (Normal):**
```json
{
    "appliance": "fridge",
    "power": 85.5,
    "is_anomaly": false,
    "z_score": 0.82,
    "reason": null,
    "stats": {
        "mean": 82.3,
        "std": 12.5,
        "threshold_high": 119.8
    },
    "timestamp": "2026-04-07T14:30:00"
}
```

**Response (Anomaly):**
```json
{
    "appliance": "fridge",
    "power": 250.0,
    "is_anomaly": true,
    "z_score": 4.21,
    "reason": ["Z-score 4.2 > 3", "ML model flagged"],
    "stats": {
        "mean": 82.3,
        "std": 12.5,
        "threshold_high": 119.8
    },
    "timestamp": "2026-04-07T14:30:00"
}
```

**Example:**
```bash
curl -X POST http://localhost:5000/ml/anomaly/fridge \
     -H "Content-Type: application/json" \
     -d '{"power": 250}'
```

---

### POST /ml/reading/{appliance}

Add a power reading for an appliance and check for anomaly.

**Path Parameters:**

| Parameter | Type | Description |
|-----------|------|-------------|
| `appliance` | string | Appliance name |

**Request Body:**
```json
{
    "power": 85.5
}
```

**Response:**
```json
{
    "status": "added",
    "appliance": "fridge",
    "power": 85.5,
    "history_size": 13,
    "anomaly_check": {
        "is_anomaly": false,
        "z_score": 0.25,
        ...
    }
}
```

---

### GET /ml/predictions

Get predictions for all appliances with sufficient data.

**Response:**
```json
{
    "fridge": {
        "power_prediction": {
            "appliance": "fridge",
            "predicted_power": 85.32,
            "unit": "watts",
            "timestamp": "2026-04-07T14:30:00"
        },
        "on_off_prediction": {
            "appliance": "fridge",
            "will_be_on": true,
            "confidence": 92.3,
            "timestamp": "2026-04-07T14:30:00"
        }
    },
    "ac_1": null
}
```

---

### GET /ml/history/{appliance}

Get power reading history for an appliance.

**Path Parameters:**

| Parameter | Type | Description |
|-----------|------|-------------|
| `appliance` | string | Appliance name |

**Response:**
```json
{
    "appliance": "fridge",
    "count": 24,
    "readings": [
        {
            "timestamp": "2026-04-07T10:00:00",
            "hour": 10,
            "day_of_week": 1,
            "is_weekend": 0,
            "power": 82.5,
            "is_on": 1
        },
        ...
    ]
}
```

---

### POST /ml/simulate

Simulate adding multiple readings for testing.

**Request Body:**
```json
{
    "appliance": "fridge",
    "readings": [80.5, 82.3, 85.1, 83.7, 84.2, 81.9]
}
```

**Response:**
```json
{
    "status": "simulated",
    "appliance": "fridge",
    "readings_added": 6,
    "history_size": 6
}
```

**Example:**
```bash
curl -X POST http://localhost:5000/ml/simulate \
     -H "Content-Type: application/json" \
     -d '{"appliance": "fridge", "readings": [80, 82, 85, 83, 84, 82]}'
```

---

## 9.4 Error Responses

### Standard Error Format

```json
{
    "error": "Error message description"
}
```

### HTTP Status Codes

| Code | Meaning |
|------|---------|
| 200 | Success |
| 400 | Bad Request (invalid parameters) |
| 404 | Not Found |
| 500 | Internal Server Error |

---

## 9.5 MQTT Topics

### Telemetry (Device → Server)

**Topic:** `energy/{device_id}/telemetry`

**Payload:**
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

### Relay Set (Server → Device)

**Topic:** `energy/{device_id}/relay/set`

**Payload:**
```
"1"   →  Turn relay ON
"0"   →  Turn relay OFF
```

### Relay State (Device → Server)

**Topic:** `energy/{device_id}/relay/state`

**Payload:**
```
"1"   →  Relay is ON
"0"   →  Relay is OFF
```

---

## 9.6 Data Types

### Telemetry Reading

| Field | Type | Unit | Description |
|-------|------|------|-------------|
| `timestamp` | string | ISO 8601 | Reading timestamp |
| `voltage` | float | V | RMS voltage |
| `current` | float | A | RMS current |
| `power` | float | W | Real power |
| `energy` | float | kWh | Cumulative energy |
| `anomaly` | boolean | - | Anomaly flag |

### ML Prediction

| Field | Type | Description |
|-------|------|-------------|
| `appliance` | string | Appliance identifier |
| `predicted_power` | float | Predicted watts |
| `unit` | string | Always "watts" |
| `features_used` | object | Input features |
| `timestamp` | string | Prediction time |

### Anomaly Result

| Field | Type | Description |
|-------|------|-------------|
| `is_anomaly` | boolean | Anomaly detected |
| `z_score` | float | Statistical z-score |
| `reason` | array/null | Explanation if anomaly |
| `stats` | object | Mean, std, threshold |

---

## 9.7 Rate Limits

| Endpoint | Limit |
|----------|-------|
| All | None (local deployment) |

For production, consider adding rate limiting with Flask-Limiter:

```python
from flask_limiter import Limiter

limiter = Limiter(
    app,
    default_limits=["100 per minute"]
)

@app.route("/ml/predict/<appliance>")
@limiter.limit("30 per minute")
def ml_predict(appliance):
    ...
```

---

## 9.8 Example Client

### Python

```python
import requests

BASE_URL = "http://localhost:5000"

# Get stats
stats = requests.get(f"{BASE_URL}/stats").json()
print(f"Average power: {stats['avg_power']} W")

# Get prediction
prediction = requests.get(f"{BASE_URL}/ml/predict/fridge").json()
print(f"Predicted: {prediction['predicted_power']} W")

# Check anomaly
result = requests.post(
    f"{BASE_URL}/ml/anomaly/fridge",
    json={"power": 150.0}
).json()
print(f"Anomaly: {result['is_anomaly']}")

# Toggle relay
requests.post(f"{BASE_URL}/relay")
```

### JavaScript

```javascript
// Fetch stats
const stats = await fetch('/stats').then(r => r.json());
console.log(`Average power: ${stats.avg_power} W`);

// Get prediction
const pred = await fetch('/ml/predict/fridge').then(r => r.json());
console.log(`Predicted: ${pred.predicted_power} W`);

// SSE stream
const sse = new EventSource('/stream');
sse.onmessage = (e) => {
    const data = JSON.parse(e.data);
    updateDashboard(data);
};
```

### cURL

```bash
# Get history
curl "http://localhost:5000/history?limit=10" | jq

# Add reading
curl -X POST http://localhost:5000/ml/reading/fridge \
     -H "Content-Type: application/json" \
     -d '{"power": 85}' | jq

# Toggle relay
curl -X POST http://localhost:5000/relay | jq
```

---

## 9.9 OpenAPI Specification

For tools like Swagger/Postman, an OpenAPI spec can be generated:

```yaml
openapi: 3.0.0
info:
  title: Smart Energy Monitor API
  version: 1.0.0
servers:
  - url: http://localhost:5000
paths:
  /stats:
    get:
      summary: Get aggregated statistics
      responses:
        '200':
          description: Success
          content:
            application/json:
              schema:
                type: object
                properties:
                  count: { type: integer }
                  avg_power: { type: number }
                  max_power: { type: number }
                  min_power: { type: number }
                  relay: { type: boolean }
  # ... additional paths
```
