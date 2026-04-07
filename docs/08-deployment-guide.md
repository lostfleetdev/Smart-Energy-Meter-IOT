# 8. Deployment Guide

## 8.1 Overview

This guide covers deploying the Smart Energy Monitor to:

1. **Local Development** — Running on your machine
2. **DigitalOcean Droplet** — Production cloud deployment
3. **Raspberry Pi** — Local server option

---

## 8.2 Prerequisites

### Software Requirements

| Component | Version | Purpose |
|-----------|---------|---------|
| Python | 3.10+ | Backend server |
| uv | Latest | Package manager |
| NanoMQ | 0.21+ | MQTT broker |
| Git | 2.0+ | Version control |

### Hardware Requirements (Cloud)

| Resource | Minimum | Recommended |
|----------|---------|-------------|
| CPU | 1 vCPU | 2 vCPU |
| RAM | 1 GB | 2 GB |
| Storage | 10 GB | 25 GB |
| Network | 1 Gbps | 1 Gbps |

---

## 8.3 Local Development

### Step 1: Clone Repository

```bash
git clone https://github.com/YOUR_USER/smart-energy-monitor.git
cd smart-energy-monitor
```

### Step 2: Install NanoMQ (Windows)

```powershell
# Download from: https://nanomq.io/downloads
# Extract to C:\nanomq

# Add to PATH
$env:PATH += ";C:\nanomq"

# Test
nanomq --version
```

### Step 3: Start NanoMQ

```powershell
# Create config file
@"
listeners.tcp.bind = "0.0.0.0:1883"
log.level = info
"@ | Out-File -FilePath nanomq.conf

# Start broker
nanomq start --conf nanomq.conf
```

### Step 4: Run Backend

```powershell
cd backend

# Install dependencies
uv sync
# Or: pip install -r requirements.txt

# Run server
uv run python main.py
# Or: python main.py
```

### Step 5: Access Dashboard

Open browser: `http://localhost:5000`

### Local Development Script

```powershell
# dev.ps1 - Run all services
param(
    [switch]$mqtt,
    [switch]$backend,
    [switch]$all
)

if ($mqtt -or $all) {
    Start-Process -NoNewWindow nanomq -ArgumentList "start"
}

if ($backend -or $all) {
    Set-Location backend
    uv run python main.py
}
```

---

## 8.4 DigitalOcean Deployment

### Automated Deployment

The `deploy.sh` script automates the entire setup:

```bash
# On a fresh Ubuntu droplet
curl -sSL https://raw.githubusercontent.com/YOUR_USER/YOUR_REPO/main/deploy.sh | bash
```

### Manual Deployment Steps

#### Step 1: Create Droplet

```
Droplet Settings:
- Image: Ubuntu 22.04 LTS
- Size: Basic, 1 GB RAM, 1 vCPU
- Region: Closest to your location
- Authentication: SSH Key
```

#### Step 2: SSH into Droplet

```bash
ssh root@YOUR_DROPLET_IP
```

#### Step 3: System Update

```bash
apt-get update && apt-get upgrade -y
```

#### Step 4: Install NanoMQ

```bash
curl -s https://assets.emqx.com/scripts/install-nanomq-deb.sh | bash
apt-get install -y nanomq

# Configure
cat > /etc/nanomq/nanomq.conf << 'EOF'
listeners.tcp.bind = "0.0.0.0:1883"
http_server.port = 8081
log.level = warn
EOF

# Enable and start
systemctl enable nanomq
systemctl start nanomq
```

#### Step 5: Install Python & uv

```bash
apt-get install -y python3 python3-pip curl git

# Install uv
curl -LsSf https://astral.sh/uv/install.sh | sh
export PATH="$HOME/.local/bin:$PATH"
```

#### Step 6: Setup Application

```bash
# Create app directory
mkdir -p /opt/energy-monitor
cd /opt/energy-monitor

# Clone or copy files
git clone --depth 1 https://github.com/YOUR_USER/YOUR_REPO.git repo
cp -r repo/backend/* .
cp -r repo/ML/models ./ 2>/dev/null || true

# Install dependencies
uv sync
```

#### Step 7: Create Systemd Service

```bash
cat > /etc/systemd/system/energy-monitor.service << 'EOF'
[Unit]
Description=Smart Energy Monitor Backend
After=network.target nanomq.service
Wants=nanomq.service

[Service]
Type=simple
WorkingDirectory=/opt/energy-monitor
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
systemctl start energy-monitor
```

#### Step 8: Verify Deployment

```bash
# Check services
systemctl status nanomq
systemctl status energy-monitor

# Check logs
journalctl -u energy-monitor -f

# Test endpoints
curl http://localhost:5000/stats
curl http://localhost:5000/ml/info
```

---

## 8.5 Firewall Configuration

### DigitalOcean Firewall

```
Inbound Rules:
- SSH:   Port 22,   TCP, Your IP
- HTTP:  Port 5000, TCP, All IPv4/IPv6
- MQTT:  Port 1883, TCP, All IPv4/IPv6
```

### UFW (Ubuntu)

```bash
ufw allow 22/tcp
ufw allow 5000/tcp
ufw allow 1883/tcp
ufw enable
```

---

## 8.6 ESP32 Configuration

Update device firmware with cloud server details:

```python
# device/main.py (or separate config file)

WIFI_SSID = "YOUR_WIFI_SSID"
WIFI_PASS = "YOUR_WIFI_PASSWORD"

MQTT_BROKER = "YOUR_DROPLET_IP"  # e.g., "167.172.5.123"
MQTT_PORT = 1883
DEVICE_ID = "device01"

TOPIC_TELEMETRY = f"energy/{DEVICE_ID}/telemetry"
TOPIC_RELAY_SET = f"energy/{DEVICE_ID}/relay/set"
TOPIC_RELAY_STATE = f"energy/{DEVICE_ID}/relay/state"
```

---

## 8.7 Monitoring & Logging

### View Logs

```bash
# Real-time logs
journalctl -u energy-monitor -f

# Last 100 lines
journalctl -u energy-monitor -n 100

# Since today
journalctl -u energy-monitor --since today
```

### Service Commands

```bash
# Restart
systemctl restart energy-monitor

# Stop
systemctl stop energy-monitor

# Status
systemctl status energy-monitor
```

### Health Check Script

```bash
#!/bin/bash
# health-check.sh

# Check if services are running
if ! systemctl is-active --quiet nanomq; then
    echo "NanoMQ is down, restarting..."
    systemctl restart nanomq
fi

if ! systemctl is-active --quiet energy-monitor; then
    echo "Energy Monitor is down, restarting..."
    systemctl restart energy-monitor
fi

# Check HTTP endpoint
if ! curl -s http://localhost:5000/stats > /dev/null; then
    echo "HTTP endpoint not responding"
    systemctl restart energy-monitor
fi
```

Add to crontab:
```bash
*/5 * * * * /opt/energy-monitor/health-check.sh >> /var/log/health-check.log 2>&1
```

---

## 8.8 SSL/HTTPS Setup

### Using Caddy (Recommended)

```bash
# Install Caddy
apt install -y debian-keyring debian-archive-keyring apt-transport-https
curl -1sLf 'https://dl.cloudsmith.io/public/caddy/stable/gpg.key' | gpg --dearmor -o /usr/share/keyrings/caddy-stable-archive-keyring.gpg
echo "deb [signed-by=/usr/share/keyrings/caddy-stable-archive-keyring.gpg] https://dl.cloudsmith.io/public/caddy/stable/deb/debian any-version main" | tee /etc/apt/sources.list.d/caddy-stable.list
apt update && apt install caddy

# Configure
cat > /etc/caddy/Caddyfile << 'EOF'
energy.yourdomain.com {
    reverse_proxy localhost:5000
}
EOF

systemctl restart caddy
```

### Using Nginx + Let's Encrypt

```bash
# Install
apt install -y nginx certbot python3-certbot-nginx

# Configure Nginx
cat > /etc/nginx/sites-available/energy-monitor << 'EOF'
server {
    listen 80;
    server_name energy.yourdomain.com;
    
    location / {
        proxy_pass http://localhost:5000;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_set_header Host $host;
    }
}
EOF

ln -s /etc/nginx/sites-available/energy-monitor /etc/nginx/sites-enabled/
nginx -t && systemctl restart nginx

# Get SSL certificate
certbot --nginx -d energy.yourdomain.com
```

---

## 8.9 Raspberry Pi Deployment

### Prerequisites

- Raspberry Pi 4 (2GB+ RAM)
- Raspberry Pi OS Lite (64-bit)
- Ethernet or WiFi connection

### Installation

```bash
# Update system
sudo apt update && sudo apt upgrade -y

# Install dependencies
sudo apt install -y python3 python3-pip git

# Install NanoMQ
curl -s https://assets.emqx.com/scripts/install-nanomq-deb.sh | sudo bash
sudo apt install -y nanomq

# Setup application
sudo mkdir -p /opt/energy-monitor
sudo chown $USER:$USER /opt/energy-monitor
cd /opt/energy-monitor

git clone https://github.com/YOUR_USER/YOUR_REPO.git .
pip3 install flask flask-cors paho-mqtt scikit-learn lightgbm

# Create service (same as DigitalOcean)
# ...
```

---

## 8.10 Troubleshooting

### Common Issues

| Issue | Solution |
|-------|----------|
| MQTT connection refused | Check NanoMQ is running: `systemctl status nanomq` |
| Dashboard not loading | Verify backend: `curl localhost:5000` |
| No live data | Check ESP32 WiFi and MQTT config |
| ML predictions fail | Verify models exist in `/opt/energy-monitor/ML/models/` |

### Debug Commands

```bash
# Test MQTT broker
mosquitto_sub -h localhost -t "energy/#" -v

# Check open ports
ss -tlnp | grep -E "(1883|5000)"

# Test from ESP32
# (In MicroPython REPL)
import network
wlan = network.WLAN(network.STA_IF)
print(wlan.isconnected())
print(wlan.ifconfig())
```

---

## 8.11 Architecture Diagram

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                      PRODUCTION DEPLOYMENT                                   │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│   ┌─────────────────┐                                                        │
│   │    ESP32        │                                                        │
│   │    Device       │                                                        │
│   │                 │                                                        │
│   │  Home WiFi      │                                                        │
│   └────────┬────────┘                                                        │
│            │                                                                 │
│            │ MQTT (1883)                                                     │
│            │                                                                 │
│            ▼                                                                 │
│   ┌─────────────────────────────────────────────────────────────────────┐   │
│   │                    DigitalOcean Droplet                              │   │
│   │                                                                      │   │
│   │   ┌───────────┐    ┌───────────┐    ┌───────────┐                   │   │
│   │   │  Caddy    │    │  Flask    │    │  NanoMQ   │                   │   │
│   │   │  (HTTPS)  │───►│  Backend  │◄───│  (MQTT)   │                   │   │
│   │   │  :443     │    │  :5000    │    │  :1883    │                   │   │
│   │   └───────────┘    └───────────┘    └───────────┘                   │   │
│   │                          │                                           │   │
│   │                          ▼                                           │   │
│   │                    ┌───────────┐                                     │   │
│   │                    │ ML Models │                                     │   │
│   │                    │   .pkl    │                                     │   │
│   │                    └───────────┘                                     │   │
│   │                                                                      │   │
│   └─────────────────────────────────────────────────────────────────────┘   │
│            │                                                                 │
│            │ HTTPS                                                           │
│            │                                                                 │
│            ▼                                                                 │
│   ┌─────────────────┐                                                        │
│   │    Browser      │                                                        │
│   │    Dashboard    │                                                        │
│   └─────────────────┘                                                        │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## Next: [API Reference →](./09-api-reference.md)
