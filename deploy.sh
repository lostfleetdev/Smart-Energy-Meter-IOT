#!/bin/bash
# ═══════════════════════════════════════════════════════════════════
# Smart Energy Monitor — DigitalOcean Deployment Script
# ═══════════════════════════════════════════════════════════════════
# Usage: curl -sSL <raw-url>/deploy.sh | bash
#    or: ./deploy.sh
# ═══════════════════════════════════════════════════════════════════

set -e

APP_DIR="/opt/energy-monitor"
ML_DIR="/opt/energy-monitor/ML"
REPO_URL="https://github.com/YOUR_USER/YOUR_REPO.git"  # Update this

echo "╔══════════════════════════════════════════════════╗"
echo "║   Smart Energy Monitor — Deployment Script       ║"
echo "║          with ML Predictions Support             ║"
echo "╚══════════════════════════════════════════════════╝"

# ─────────────────────────────────────────────────────────────
# 1. System Update
# ─────────────────────────────────────────────────────────────
echo "[1/6] Updating system..."
apt-get update -qq
apt-get upgrade -y -qq

# ─────────────────────────────────────────────────────────────
# 2. Install NanoMQ (MQTT Broker)
# ─────────────────────────────────────────────────────────────
echo "[2/6] Installing NanoMQ..."
if ! command -v nanomq &> /dev/null; then
    curl -s https://assets.emqx.com/scripts/install-nanomq-deb.sh | bash
    apt-get install -y -qq nanomq
fi

# Create nanomq config
cat > /etc/nanomq/nanomq.conf << 'EOF'
# NanoMQ Configuration
listeners.tcp.bind = "0.0.0.0:1883"
http_server.port = 8081
log.level = warn
EOF

# Enable and start nanomq
systemctl enable nanomq
systemctl restart nanomq
echo "    NanoMQ started on port 1883"

# ─────────────────────────────────────────────────────────────
# 3. Install Python + uv
# ─────────────────────────────────────────────────────────────
echo "[3/6] Installing Python & uv..."
apt-get install -y -qq python3 python3-pip curl git

if ! command -v uv &> /dev/null; then
    curl -LsSf https://astral.sh/uv/install.sh | sh
    export PATH="$HOME/.local/bin:$PATH"
fi

# ─────────────────────────────────────────────────────────────
# 4. Setup Application
# ─────────────────────────────────────────────────────────────
echo "[4/6] Setting up application..."
mkdir -p "$APP_DIR"
mkdir -p "$ML_DIR"

# If repo URL set, clone it; otherwise copy local files
if [[ "$REPO_URL" != *"YOUR_"* ]]; then
    if [ -d "$APP_DIR/repo" ]; then
        cd "$APP_DIR/repo" && git pull
    else
        git clone --depth 1 "$REPO_URL" "$APP_DIR/repo"
    fi
    cp -r "$APP_DIR/repo/backend/"* "$APP_DIR/"
    cp -r "$APP_DIR/repo/ML/models" "$ML_DIR/" 2>/dev/null || true
    cp -r "$APP_DIR/repo/ML/data_pipeline.py" "$ML_DIR/" 2>/dev/null || true
    cp -r "$APP_DIR/repo/ML/train_models.py" "$ML_DIR/" 2>/dev/null || true
else
    echo "    [!] Set REPO_URL in script or copy files manually to $APP_DIR"
fi

# ─────────────────────────────────────────────────────────────
# 5. Install Dependencies
# ─────────────────────────────────────────────────────────────
echo "[5/6] Installing Python dependencies..."
cd "$APP_DIR"
uv sync 2>/dev/null || uv pip install flask flask-cors paho-mqtt scikit-learn lightgbm joblib

# ─────────────────────────────────────────────────────────────
# 6. Create Systemd Service
# ─────────────────────────────────────────────────────────────
echo "[6/6] Creating systemd service..."
cat > /etc/systemd/system/energy-monitor.service << EOF
[Unit]
Description=Smart Energy Monitor Backend with ML
After=network.target nanomq.service
Wants=nanomq.service

[Service]
Type=simple
WorkingDirectory=$APP_DIR
ExecStart=/root/.local/bin/uv run python main.py
Restart=always
RestartSec=5
Environment=MQTT_BROKER=localhost
Environment=MQTT_PORT=1883
Environment=DEVICE_ID=device01

[Install]
WantedBy=multi-user.target
EOF

systemctl daemon-reload
systemctl enable energy-monitor
systemctl restart energy-monitor

# ─────────────────────────────────────────────────────────────
# Done
# ─────────────────────────────────────────────────────────────
IP=$(hostname -I | awk '{print $1}')
echo ""
echo "╔══════════════════════════════════════════════════╗"
echo "║              Deployment Complete!                ║"
echo "╠══════════════════════════════════════════════════╣"
echo "║  NanoMQ:      mqtt://$IP:1883              ║"
echo "║  Dashboard:   http://$IP:5000              ║"
echo "║  ML API:      http://$IP:5000/ml/info      ║"
echo "╠══════════════════════════════════════════════════╣"
echo "║  Commands:                                       ║"
echo "║    systemctl status energy-monitor               ║"
echo "║    journalctl -u energy-monitor -f               ║"
echo "║    systemctl restart energy-monitor              ║"
echo "╠══════════════════════════════════════════════════╣"
echo "║  ML Endpoints:                                   ║"
echo "║    GET  /ml/appliances   - List appliances       ║"
echo "║    GET  /ml/predict/:app - Power prediction      ║"
echo "║    POST /ml/anomaly/:app - Anomaly detection     ║"
echo "╚══════════════════════════════════════════════════╝"
