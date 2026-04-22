"""
Smart Energy Monitor — Flask Backend
=====================================
Single-file backend: MQTT subscriber, SSE streaming, ML predictions.
"""

import csv
import json
import os
import threading
import time
from collections import deque
from datetime import datetime
from pathlib import Path

import paho.mqtt.client as mqtt
from flask import Flask, Response, jsonify, request, send_from_directory
from flask_cors import CORS

from ml_service import ml_service, APPLIANCES

# ══════════════════════════════════════════════════
# Configuration
# ══════════════════════════════════════════════════
MQTT_BROKER = os.getenv("MQTT_BROKER", "localhost")
MQTT_PORT = int(os.getenv("MQTT_PORT", 1883))
DEVICE_ID = os.getenv("DEVICE_ID", "device01")
DATA_FILE = Path(__file__).parent / "data.csv"

# MQTT topics
TOPIC_TELEMETRY = f"energy/{DEVICE_ID}/telemetry"
TOPIC_RELAY_SET = f"energy/{DEVICE_ID}/relay/set"
TOPIC_RELAY_STATE = f"energy/{DEVICE_ID}/relay/state"

# ══════════════════════════════════════════════════
# Shared State
# ══════════════════════════════════════════════════
data_buffer = deque(maxlen=100)  # Last 100 readings for SSE
relay_state = {"on": False}
sse_clients = set()  # Track active SSE clients
lock = threading.Lock()

# ══════════════════════════════════════════════════
# Flask App
# ══════════════════════════════════════════════════
app = Flask(__name__, static_folder="static")
CORS(app)  # Enable CORS for frontend access


@app.route("/")
def index():
    """Serve dashboard."""
    return send_from_directory(app.static_folder, "index.html")


@app.route("/stream")
def stream():
    """SSE endpoint — streams live telemetry while client connected."""
    def generate():
        client_id = id(threading.current_thread())
        sse_clients.add(client_id)
        last_seen_timestamp = None
        
        try:
            while True:
                with lock:
                    if data_buffer:
                        # Find new data since last seen
                        new_data = []
                        for item in data_buffer:
                            ts = item.get("timestamp")
                            if last_seen_timestamp is None or ts > last_seen_timestamp:
                                new_data.append(item)
                        
                        if new_data:
                            last_seen_timestamp = new_data[-1].get("timestamp")
                            for item in new_data:
                                yield f"data: {json.dumps(item)}\n\n"
                
                time.sleep(0.5)
        finally:
            sse_clients.discard(client_id)
    
    return Response(generate(), mimetype="text/event-stream")


@app.route("/history")
def history():
    """Return last N readings from CSV."""
    limit = request.args.get("limit", 100, type=int)
    
    if not DATA_FILE.exists():
        return jsonify([])
    
    rows = []
    with open(DATA_FILE, "r", newline="") as f:
        reader = csv.DictReader(f)
        for row in reader:
            rows.append(row)
    
    # Return last 'limit' rows
    return jsonify(rows[-limit:])


@app.route("/relay", methods=["GET", "POST"])
def relay():
    """Get or set relay state."""
    if request.method == "GET":
        return jsonify(relay_state)
    
    # POST — toggle or set relay
    data = request.get_json() or {}
    new_state = data.get("on", not relay_state["on"])
    
    # Publish to MQTT
    payload = "1" if new_state else "0"
    mqtt_client.publish(TOPIC_RELAY_SET, payload, qos=1)
    
    return jsonify({"requested": new_state})


@app.route("/stats")
def stats():
    """Basic statistics from buffer."""
    with lock:
        if not data_buffer:
            return jsonify({"error": "No data", "buffer_size": 0})
        
        powers = [d["power"] for d in data_buffer if "power" in d]
        
    if not powers:
        return jsonify({"error": "No power data", "buffer_size": len(data_buffer)})
    
    return jsonify({
        "count": len(powers),
        "avg_power": round(sum(powers) / len(powers), 2),
        "max_power": round(max(powers), 2),
        "min_power": round(min(powers), 2),
        "relay": relay_state["on"],
        "sse_clients": len(sse_clients),
        "last_reading": data_buffer[-1] if data_buffer else None,
    })


@app.route("/debug")
def debug():
    """Debug endpoint to check system status."""
    with lock:
        buffer_data = list(data_buffer)[-5:]  # Last 5
    return jsonify({
        "mqtt_topics": {
            "telemetry": TOPIC_TELEMETRY,
            "relay_set": TOPIC_RELAY_SET, 
            "relay_state": TOPIC_RELAY_STATE,
        },
        "buffer_size": len(data_buffer),
        "last_readings": buffer_data,
        "relay_state": relay_state,
        "sse_clients": len(sse_clients),
    })


# ══════════════════════════════════════════════════
# ML Prediction Endpoints
# ══════════════════════════════════════════════════
@app.route("/ml/info")
def ml_info():
    """Get ML model information."""
    return jsonify(ml_service.get_model_info())


@app.route("/ml/appliances")
def ml_appliances():
    """List available appliances."""
    return jsonify({
        "appliances": APPLIANCES,
        "with_predictors": list(ml_service.models.keys()),
        "with_anomaly_detection": list(ml_service.anomaly_models.keys()),
        "with_classifiers": list(ml_service.classifiers.keys()),
    })


@app.route("/ml/predict/<appliance>")
def ml_predict(appliance):
    """Predict power consumption for an appliance."""
    if appliance not in APPLIANCES:
        return jsonify({"error": f"Unknown appliance: {appliance}"}), 400
    
    result = ml_service.predict_power(appliance)
    if "error" in result:
        return jsonify(result), 400
    return jsonify(result)


@app.route("/ml/predict-onoff/<appliance>")
def ml_predict_onoff(appliance):
    """Predict if appliance will be ON next hour."""
    if appliance not in APPLIANCES:
        return jsonify({"error": f"Unknown appliance: {appliance}"}), 400
    
    result = ml_service.predict_on_off(appliance)
    if "error" in result:
        return jsonify(result), 400
    return jsonify(result)


@app.route("/ml/anomaly/<appliance>", methods=["POST"])
def ml_anomaly(appliance):
    """Detect anomaly for a power reading."""
    if appliance not in APPLIANCES:
        return jsonify({"error": f"Unknown appliance: {appliance}"}), 400
    
    data = request.get_json() or {}
    power = data.get("power")
    if power is None:
        return jsonify({"error": "Missing 'power' in request body"}), 400
    
    result = ml_service.detect_anomaly(appliance, float(power))
    if "error" in result:
        return jsonify(result), 400
    return jsonify(result)


@app.route("/ml/reading/<appliance>", methods=["POST"])
def ml_add_reading(appliance):
    """Add a power reading for an appliance."""
    if appliance not in APPLIANCES:
        return jsonify({"error": f"Unknown appliance: {appliance}"}), 400
    
    data = request.get_json() or {}
    power = data.get("power")
    if power is None:
        return jsonify({"error": "Missing 'power' in request body"}), 400
    
    ml_service.add_reading(appliance, float(power))
    
    # Also check for anomaly
    anomaly_result = ml_service.detect_anomaly(appliance, float(power))
    
    return jsonify({
        "status": "added",
        "appliance": appliance,
        "power": power,
        "history_size": len(ml_service.history[appliance]),
        "anomaly_check": anomaly_result,
    })


@app.route("/ml/predictions")
def ml_all_predictions():
    """Get predictions for all appliances."""
    return jsonify(ml_service.get_all_predictions())


@app.route("/ml/history/<appliance>")
def ml_history(appliance):
    """Get power history for an appliance."""
    if appliance not in APPLIANCES:
        return jsonify({"error": f"Unknown appliance: {appliance}"}), 400
    
    history = list(ml_service.history[appliance])
    return jsonify({
        "appliance": appliance,
        "count": len(history),
        "readings": history,
    })


@app.route("/ml/simulate", methods=["POST"])
def ml_simulate():
    """Simulate adding readings for testing."""
    data = request.get_json() or {}
    appliance = data.get("appliance", "fridge")
    readings = data.get("readings", [])
    
    if appliance not in APPLIANCES:
        return jsonify({"error": f"Unknown appliance: {appliance}"}), 400
    
    for power in readings:
        ml_service.add_reading(appliance, float(power))
    
    return jsonify({
        "status": "simulated",
        "appliance": appliance,
        "readings_added": len(readings),
        "history_size": len(ml_service.history[appliance]),
    })


# ══════════════════════════════════════════════════
# Anomaly Detection (uses ML service)
# ══════════════════════════════════════════════════
def check_anomaly(reading):
    """Check for anomaly using ML service or fallback to Z-score."""
    try:
        power = reading.get("power", 0)
        appliance = reading.get("appliance", "fridge")
        
        # Try ML-based detection for the specific appliance
        if appliance in ml_service.anomaly_models:
            result = ml_service.detect_anomaly(appliance, power)
            if result and not result.get("error"):
                return result.get("is_anomaly", False)
        
        # Fallback: Simple Z-score anomaly check
        with lock:
            if len(data_buffer) < 20:
                return False
            
            powers = [d["power"] for d in data_buffer if "power" in d]
        
        if len(powers) < 20:
            return False
        
        mean = sum(powers) / len(powers)
        variance = sum((p - mean) ** 2 for p in powers) / len(powers)
        std = variance ** 0.5
        
        if std < 1:  # Avoid division by tiny std
            return False
        
        z_score = abs(power - mean) / std
        return z_score > 3  # Flag if > 3 standard deviations
    except Exception as e:
        print(f"[ANOMALY] Error checking: {e}")
        return False


# ══════════════════════════════════════════════════
# MQTT Callbacks
# ══════════════════════════════════════════════════
def on_connect(client, userdata, flags, reason_code, properties):
    """Subscribe to topics on connect."""
    print(f"[MQTT] Connected: {reason_code}")
    client.subscribe(TOPIC_TELEMETRY, qos=1)
    client.subscribe(TOPIC_RELAY_STATE, qos=1)


def on_message(client, userdata, msg):
    """Handle incoming MQTT messages."""
    topic = msg.topic
    payload = msg.payload.decode()
    
    if topic == TOPIC_TELEMETRY:
        try:
            data = json.loads(payload)
            data["timestamp"] = datetime.now().isoformat()
            data["anomaly"] = check_anomaly(data)
            
            with lock:
                data_buffer.append(data)
            
            # Log receipt
            print(f"[MQTT] Telemetry: V={data.get('voltage')}, I={data.get('current')}, P={data.get('power')}")
            
            # Append to CSV
            append_csv(data)
            
            # Feed to ML service for predictions
            appliance = data.get("appliance", "fridge")
            power = data.get("power", 0)
            if appliance in APPLIANCES and power is not None:
                ml_service.add_reading(appliance, float(power))
            
            if data["anomaly"]:
                print(f"[ANOMALY] {data}")
                
        except json.JSONDecodeError:
            print(f"[MQTT] Invalid JSON: {payload}")
        except Exception as e:
            print(f"[MQTT] Error processing telemetry: {e}")
    
    elif topic == TOPIC_RELAY_STATE:
        relay_state["on"] = payload == "1"
        print(f"[MQTT] Relay state: {relay_state['on']}")


def append_csv(data):
    """Append reading to CSV file."""
    file_exists = DATA_FILE.exists()
    
    fieldnames = ["timestamp", "voltage", "current", "power", "energy", "anomaly"]
    
    with open(DATA_FILE, "a", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames, extrasaction="ignore")
        if not file_exists:
            writer.writeheader()
        writer.writerow(data)


# ══════════════════════════════════════════════════
# MQTT Client Setup
# ══════════════════════════════════════════════════
mqtt_client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2)
mqtt_client.on_connect = on_connect
mqtt_client.on_message = on_message
mqtt_client.reconnect_delay_set(min_delay=1, max_delay=30)


def on_disconnect(client, userdata, disconnect_flags, reason_code, properties):
    """Handle MQTT disconnection."""
    print(f"[MQTT] Disconnected (rc={reason_code}), will auto-reconnect...")


mqtt_client.on_disconnect = on_disconnect


def mqtt_loop():
    """MQTT network loop in background thread with robust reconnection."""
    while True:
        try:
            print(f"[MQTT] Connecting to {MQTT_BROKER}:{MQTT_PORT}...")
            mqtt_client.connect(MQTT_BROKER, MQTT_PORT, keepalive=60)
            mqtt_client.loop_forever(retry_first_connection=True)
        except OSError as e:
            print(f"[MQTT] Connection error: {e}, retrying in 5s...")
            time.sleep(5)
        except Exception as e:
            print(f"[MQTT] Unexpected error: {e}, retrying in 5s...")
            time.sleep(5)
            time.sleep(5)


# ══════════════════════════════════════════════════
# Main
# ══════════════════════════════════════════════════
def main():
    print(f"""
╔══════════════════════════════════════════════════╗
║     Smart Energy Monitor — Backend Server        ║
╠══════════════════════════════════════════════════╣
║  MQTT Broker: {MQTT_BROKER}:{MQTT_PORT:<24}║
║  Device ID:   {DEVICE_ID:<33}║
║  Data File:   {DATA_FILE.name:<33}║
╚══════════════════════════════════════════════════╝
    """)
    
    # Start MQTT in background
    mqtt_thread = threading.Thread(target=mqtt_loop, daemon=True)
    mqtt_thread.start()
    
    # Run Flask
    app.run(host="0.0.0.0", port=5000, debug=False, threaded=True)


if __name__ == "__main__":
    main()
