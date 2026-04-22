#!/usr/bin/env bash
# ═══════════════════════════════════════════════════════════════════
# Smart Energy Monitor — Linux/WSL2 Development Script
# ═══════════════════════════════════════════════════════════════════
# Usage: ./deploy.sh [start|stop|status|test|ml-test|install]
# ═══════════════════════════════════════════════════════════════════

set -Eeuo pipefail

ACTION="${1:-start}"
SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
REPO_URL="https://github.com/lostfleetdev/Smart-Energy-Meter-IOT.git"
DEFAULT_CLONE_DIR="${HOME}/Smart-Energy-Meter-IOT"
PROJECT_ROOT="${SCRIPT_DIR}"
BACKEND_DIR=""
ML_DIR=""

set_project_paths() {
  PROJECT_ROOT="$1"
  BACKEND_DIR="${PROJECT_ROOT}/backend"
  ML_DIR="${PROJECT_ROOT}/ML"
}

set_project_paths "${PROJECT_ROOT}"

if [[ "${EUID}" -eq 0 ]]; then
  SUDO_CMD=""
else
  SUDO_CMD="sudo"
fi

banner() {
  echo
  echo "╔══════════════════════════════════════════════════╗"
  echo "║   Smart Energy Monitor — Dev Environment         ║"
  echo "║          with ML Predictions Support             ║"
  echo "╚══════════════════════════════════════════════════╝"
  echo
}

info() { echo "[→] $*"; }
ok() { echo "[✓] $*"; }
warn() { echo "[!] $*"; }
fail() { echo "[✗] $*" >&2; }

run_as_root() {
  if [[ -n "${SUDO_CMD}" ]]; then
    "${SUDO_CMD}" "$@"
  else
    "$@"
  fi
}

require_cmd() {
  if ! command -v "$1" >/dev/null 2>&1; then
    fail "Required command not found: $1"
    exit 1
  fi
}

ensure_apt() {
  if ! command -v apt-get >/dev/null 2>&1; then
    fail "This script currently supports Debian/Ubuntu/WSL2 (apt-get)."
    exit 1
  fi
}

ensure_base_packages() {
  ensure_apt
  info "Installing required system packages..."
  run_as_root apt-get update -qq
  run_as_root apt-get install -y -qq \
    ca-certificates \
    curl \
    git \
    python3 \
    python3-pip \
    python3-venv \
    libgomp1
  ok "System packages ready"
}

is_project_root() {
  local root="$1"
  [[ -f "${root}/backend/pyproject.toml" && -f "${root}/backend/main.py" && -d "${root}/ML" ]]
}

ensure_repo_available() {
  if is_project_root "${PROJECT_ROOT}"; then
    ok "Using project source: ${PROJECT_ROOT}"
    return
  fi

  local target="${PROJECT_DIR:-${DEFAULT_CLONE_DIR}}"
  require_cmd git

  info "Project files not found beside script. Cloning repository..."

  if [[ -d "${target}/.git" ]]; then
    info "Updating existing clone in ${target}..."
    git -C "${target}" fetch --all --prune
    git -C "${target}" pull --ff-only
  elif [[ -d "${target}" && -n "$(ls -A "${target}" 2>/dev/null)" ]]; then
    fail "Clone target exists and is not empty: ${target}"
    fail "Set PROJECT_DIR to an empty directory or remove ${target}."
    exit 1
  else
    mkdir -p "$(dirname "${target}")"
    git clone --depth 1 "${REPO_URL}" "${target}"
  fi

  set_project_paths "${target}"
  if ! is_project_root "${PROJECT_ROOT}"; then
    fail "Cloned repository is missing expected backend/ML directories."
    exit 1
  fi

  ok "Using project source: ${PROJECT_ROOT}"
}

ensure_uv() {
  if command -v uv >/dev/null 2>&1; then
    return
  fi

  info "Installing uv..."
  curl -LsSf https://astral.sh/uv/install.sh | sh

  export PATH="${HOME}/.local/bin:${PATH}"
  if ! command -v uv >/dev/null 2>&1; then
    fail "uv installation completed but not found on PATH."
    fail "Run: export PATH=\"\$HOME/.local/bin:\$PATH\""
    exit 1
  fi
  ok "uv installed"
}

ensure_latest_nanomq() {
  if command -v nanomq >/dev/null 2>&1; then
    local installed_version
    installed_version="$(nanomq --version 2>/dev/null | awk '{print $NF}' | head -n1 || true)"
    [[ -n "${installed_version}" ]] && ok "NanoMQ already installed (${installed_version})"
  fi

  info "Checking latest NanoMQ release..."
  local arch
  arch="$(uname -m)"
  case "${arch}" in
    x86_64) arch="amd64" ;;
    aarch64|arm64) arch="arm64" ;;
    *)
      fail "Unsupported architecture for automatic NanoMQ install: ${arch}"
      exit 1
      ;;
  esac

  local release_json
  release_json="$(mktemp)"
  curl -fsSL "https://api.github.com/repos/nanomq/nanomq/releases/latest" -o "${release_json}"

  local tag
  tag="$(python3 - "${release_json}" <<'PY'
import json, sys
with open(sys.argv[1], "r", encoding="utf-8") as f:
    data = json.load(f)
print(data.get("tag_name", ""))
PY
)"
  if [[ -z "${tag}" ]]; then
    rm -f "${release_json}"
    fail "Could not read latest NanoMQ release tag."
    exit 1
  fi

  local deb_url
  deb_url="$(python3 - "${release_json}" "${arch}" <<'PY'
import json, re, sys
with open(sys.argv[1], "r", encoding="utf-8") as f:
    data = json.load(f)
arch = sys.argv[2]
assets = data.get("assets", [])

# Preference: standard package, then sqlite/full/msquic variants.
patterns = [
    rf"nanomq-.*-linux-{arch}\.deb$",
    rf"nanomq-.*-linux-{arch}-sqlite\.deb$",
    rf"nanomq-.*-linux-{arch}-full\.deb$",
    rf"nanomq-.*-linux-{arch}-msquic\.deb$",
]

for p in patterns:
    rx = re.compile(p)
    for asset in assets:
        name = asset.get("name", "")
        if rx.search(name):
            print(asset.get("browser_download_url", ""))
            sys.exit(0)
print("")
PY
)"
  rm -f "${release_json}"

  if [[ -z "${deb_url}" ]]; then
    fail "No compatible NanoMQ .deb asset found for ${arch} in latest release."
    exit 1
  fi

  local deb_file="/tmp/nanomq-${tag}-${arch}.deb"
  info "Downloading NanoMQ ${tag} (${arch})..."
  curl -fL "${deb_url}" -o "${deb_file}"

  info "Installing NanoMQ package..."
  run_as_root dpkg -i "${deb_file}" || run_as_root apt-get install -f -y -qq
  rm -f "${deb_file}"

  require_cmd nanomq
  ok "NanoMQ installed/updated to latest release (${tag})"
}

sync_backend_deps() {
  ensure_uv
  if [[ ! -f "${BACKEND_DIR}/pyproject.toml" ]]; then
    fail "backend/pyproject.toml not found."
    exit 1
  fi

  info "Installing backend Python dependencies..."
  (
    cd "${BACKEND_DIR}"
    if [[ -f "uv.lock" ]]; then
      uv sync --frozen
    else
      uv sync
    fi
  )
  ok "Backend dependencies ready"
}

start_nanomq() {
  require_cmd nanomq
  if pgrep -x nanomq >/dev/null 2>&1; then
    local pid
    pid="$(pgrep -x nanomq | head -n1)"
    warn "NanoMQ already running (PID: ${pid})"
    return
  fi

  info "Starting NanoMQ broker..."
  nanomq start >/dev/null 2>&1 || true
  sleep 2

  if pgrep -x nanomq >/dev/null 2>&1; then
    local pid
    pid="$(pgrep -x nanomq | head -n1)"
    ok "NanoMQ started (PID: ${pid})"
  else
    fail "NanoMQ failed to start."
    exit 1
  fi
}

show_model_status() {
  local models_path="${ML_DIR}/models"
  if [[ -d "${models_path}" ]]; then
    local count
    count="$(find "${models_path}" -maxdepth 1 -type f -name '*.pkl' | wc -l | tr -d ' ')"
    ok "ML models found: ${count}"
  else
    warn "ML models directory not found: ${models_path}"
  fi
}

install_all() {
  ensure_base_packages
  ensure_repo_available
  ensure_uv
  ensure_latest_nanomq
  sync_backend_deps
  show_model_status
  ok "Install/setup complete"
}

start_services() {
  banner
  install_all
  start_nanomq

  info "Starting Flask backend..."
  echo
  echo "    Dashboard:    http://localhost:5000"
  echo "    ML API:       http://localhost:5000/ml/info"
  echo "    MQTT:         localhost:1883"
  echo
  echo "    Press Ctrl+C to stop Flask"
  echo

  cd "${BACKEND_DIR}"
  uv run python main.py
}

stop_services() {
  banner
  if pgrep -x nanomq >/dev/null 2>&1; then
    local pid
    pid="$(pgrep -x nanomq | head -n1)"
    info "Stopping NanoMQ (PID: ${pid})..."
    nanomq stop >/dev/null 2>&1 || true
    sleep 1
    if pgrep -x nanomq >/dev/null 2>&1; then
      pkill -x nanomq || true
      sleep 1
    fi
    if pgrep -x nanomq >/dev/null 2>&1; then
      fail "NanoMQ is still running."
      exit 1
    fi
    ok "NanoMQ stopped"
  else
    warn "NanoMQ not running"
  fi
}

show_status() {
  banner
  ensure_repo_available

  if pgrep -x nanomq >/dev/null 2>&1; then
    local pid
    pid="$(pgrep -x nanomq | head -n1)"
    ok "NanoMQ: Running (PID: ${pid})"
  else
    fail "NanoMQ: Not running"
  fi

  local flask_running="false"
  if command -v ss >/dev/null 2>&1; then
    if ss -ltn 2>/dev/null | grep -q ':5000 '; then
      flask_running="true"
    fi
  elif command -v netstat >/dev/null 2>&1; then
    if netstat -ltn 2>/dev/null | grep -q ':5000 '; then
      flask_running="true"
    fi
  fi

  if [[ "${flask_running}" == "true" ]]; then
    ok "Flask: Running on port 5000"
  else
    fail "Flask: Not running"
  fi

  show_model_status
}

send_test_data() {
  banner
  ensure_repo_available
  info "Sending test MQTT data..."
  (
    cd "${BACKEND_DIR}"
    uv run python - <<'PY'
import json
import random
import time
import paho.mqtt.client as mqtt

client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2)
client.connect("localhost", 1883, 60)

for i in range(5):
    data = {
        "voltage": round(220 + random.uniform(-10, 10), 1),
        "current": round(random.uniform(0.5, 3), 2),
        "power": round(random.uniform(100, 700), 1),
        "energy": round(random.uniform(0.1, 2), 4),
        "appliance": "fridge",
        "device_id": "device01",
    }
    client.publish("energy/device01/telemetry", json.dumps(data), qos=1)
    print(f'[{i+1}/5] Sent: V={data["voltage"]}V, I={data["current"]}A, P={data["power"]}W')
    time.sleep(1)

client.disconnect()
print("[✓] Test data sent!")
PY
  )
}

test_ml_service() {
  banner
  ensure_repo_available
  info "Testing ML service..."
  (
    cd "${BACKEND_DIR}"
    uv run python - <<'PY'
import requests

BASE_URL = "http://localhost:5000"

print("\n[1] Testing /ml/info...")
try:
    r = requests.get(f"{BASE_URL}/ml/info", timeout=8)
    data = r.json()
    print(f'    Models loaded: {len(data.get("power_predictors", []))} predictors')
    print(f'    Anomaly detectors: {len(data.get("anomaly_detectors", []))}')
except Exception as e:
    print(f"    Error: {e}")

print("\n[2] Testing /ml/appliances...")
try:
    r = requests.get(f"{BASE_URL}/ml/appliances", timeout=8)
    data = r.json()
    print(f'    Available: {", ".join(data.get("appliances", []))}')
except Exception as e:
    print(f"    Error: {e}")

print("\n[3] Simulating readings for fridge...")
try:
    readings = [35 + i * 2 for i in range(10)]
    r = requests.post(f"{BASE_URL}/ml/simulate", json={"appliance": "fridge", "readings": readings}, timeout=8)
    data = r.json()
    print(f'    Added {data.get("readings_added")} readings, total: {data.get("history_size")}')
except Exception as e:
    print(f"    Error: {e}")

print("\n[4] Testing prediction for fridge...")
try:
    r = requests.get(f"{BASE_URL}/ml/predict/fridge", timeout=8)
    data = r.json()
    if "error" in data:
        print(f'    Note: {data["error"]}')
    else:
        print(f'    Predicted power: {data.get("predicted_power")} W')
except Exception as e:
    print(f"    Error: {e}")

print("\n[5] Testing anomaly detection...")
try:
    r = requests.post(f"{BASE_URL}/ml/anomaly/fridge", json={"power": 500}, timeout=8)
    data = r.json()
    status = "ANOMALY" if data.get("is_anomaly") else "Normal"
    print(f'    500W reading: {status} (z-score: {data.get("z_score")})')
except Exception as e:
    print(f"    Error: {e}")

print("\n[✓] ML service test complete!")
PY
  )
}

clone_repo() {
  banner
  ensure_base_packages
  ensure_repo_available
  ok "Repository ready at: ${PROJECT_ROOT}"
}

usage() {
  echo "Usage: ./deploy.sh [start|stop|status|test|ml-test|install|clone]"
}

case "${ACTION}" in
  start) start_services ;;
  stop) stop_services ;;
  status) show_status ;;
  test) send_test_data ;;
  ml-test) test_ml_service ;;
  clone) clone_repo ;;
  install)
    banner
    install_all
    ;;
  *)
    usage
    exit 1
    ;;
esac
