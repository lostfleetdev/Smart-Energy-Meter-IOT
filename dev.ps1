# ═══════════════════════════════════════════════════════════════════
# Smart Energy Monitor — Windows Development Script
# ═══════════════════════════════════════════════════════════════════
# Usage: .\dev.ps1 [start|stop|status|test|ml-test]
# ═══════════════════════════════════════════════════════════════════

param(
    [Parameter(Position=0)]
    [ValidateSet("start", "stop", "status", "test", "ml-test")]
    [string]$Action = "start"
)

$ErrorActionPreference = "Stop"
$NANOMQ_EXE = "$PSScriptRoot\nanomq-windows-for_testing\bin\nanomq.exe"
$BACKEND_DIR = "$PSScriptRoot\backend"
$ML_DIR = "$PSScriptRoot\ML"

function Write-Banner {
    Write-Host ""
    Write-Host "╔══════════════════════════════════════════════════╗" -ForegroundColor Cyan
    Write-Host "║   Smart Energy Monitor — Dev Environment         ║" -ForegroundColor Cyan
    Write-Host "║          with ML Predictions Support             ║" -ForegroundColor Cyan
    Write-Host "╚══════════════════════════════════════════════════╝" -ForegroundColor Cyan
    Write-Host ""
}

function Start-Services {
    Write-Banner
    
    # Check nanomq exists
    if (-not (Test-Path $NANOMQ_EXE)) {
        Write-Host "[✗] NanoMQ not found at: $NANOMQ_EXE" -ForegroundColor Red
        Write-Host "    Download from: https://github.com/nanomq/nanomq/releases" -ForegroundColor DarkGray
        return
    }
    
    # Check if already running
    $mqProcess = Get-Process -Name "nanomq" -ErrorAction SilentlyContinue
    if ($mqProcess) {
        Write-Host "[!] NanoMQ already running (PID: $($mqProcess.Id))" -ForegroundColor Yellow
    } else {
        Write-Host "[→] Starting NanoMQ broker..." -ForegroundColor Cyan
        Start-Process -FilePath $NANOMQ_EXE -ArgumentList "start" -WindowStyle Hidden
        Start-Sleep -Seconds 2
        
        $mqProcess = Get-Process -Name "nanomq" -ErrorAction SilentlyContinue
        if ($mqProcess) {
            Write-Host "[✓] NanoMQ started (PID: $($mqProcess.Id))" -ForegroundColor Green
        } else {
            Write-Host "[✗] NanoMQ failed to start" -ForegroundColor Red
            return
        }
    }
    
    # Check ML models
    $mlModelsPath = "$ML_DIR\models"
    if (Test-Path $mlModelsPath) {
        $modelCount = (Get-ChildItem -Path $mlModelsPath -Filter "*.pkl").Count
        Write-Host "[✓] ML Models found: $modelCount models" -ForegroundColor Green
    } else {
        Write-Host "[!] ML Models not found at: $mlModelsPath" -ForegroundColor Yellow
        Write-Host "    Run training first: cd ML && uv run python train_models.py" -ForegroundColor DarkGray
    }
    
    Write-Host "[→] Starting Flask backend..." -ForegroundColor Cyan
    Write-Host ""
    Write-Host "    Dashboard:    http://localhost:5000" -ForegroundColor White
    Write-Host "    ML API:       http://localhost:5000/ml/info" -ForegroundColor White
    Write-Host "    MQTT:         localhost:1883" -ForegroundColor White
    Write-Host ""
    Write-Host "    Press Ctrl+C to stop" -ForegroundColor DarkGray
    Write-Host ""
    
    # Run Flask in foreground
    Push-Location $BACKEND_DIR
    try {
        & uv run python main.py
    } finally {
        Pop-Location
    }
}

function Stop-Services {
    Write-Banner
    
    # Stop NanoMQ
    $mqProcess = Get-Process -Name "nanomq" -ErrorAction SilentlyContinue
    if ($mqProcess) {
        Write-Host "[→] Stopping NanoMQ (PID: $($mqProcess.Id))..." -ForegroundColor Yellow
        Stop-Process -Id $mqProcess.Id -Force
        Write-Host "[✓] NanoMQ stopped" -ForegroundColor Green
    } else {
        Write-Host "[!] NanoMQ not running" -ForegroundColor DarkGray
    }
}

function Show-Status {
    Write-Banner
    
    $mqProcess = Get-Process -Name "nanomq" -ErrorAction SilentlyContinue
    if ($mqProcess) {
        Write-Host "[✓] NanoMQ:  Running (PID: $($mqProcess.Id))" -ForegroundColor Green
    } else {
        Write-Host "[✗] NanoMQ:  Not running" -ForegroundColor Red
    }
    
    # Check if port 5000 is listening
    $flask = Get-NetTCPConnection -LocalPort 5000 -ErrorAction SilentlyContinue
    if ($flask) {
        Write-Host "[✓] Flask:   Running on port 5000" -ForegroundColor Green
    } else {
        Write-Host "[✗] Flask:   Not running" -ForegroundColor Red
    }
    
    # Check ML models
    $mlModelsPath = "$ML_DIR\models"
    if (Test-Path $mlModelsPath) {
        $modelCount = (Get-ChildItem -Path $mlModelsPath -Filter "*.pkl").Count
        Write-Host "[✓] ML:      $modelCount models loaded" -ForegroundColor Green
    } else {
        Write-Host "[✗] ML:      Models not found" -ForegroundColor Red
    }
}

function Send-TestData {
    Write-Banner
    Write-Host "[→] Sending test MQTT data..." -ForegroundColor Cyan
    
    # Use Python to send test MQTT message
    $testScript = @"
import paho.mqtt.client as mqtt
import json
import random
import time

client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2)
client.connect('localhost', 1883, 60)

for i in range(5):
    data = {
        'voltage': round(220 + random.uniform(-10, 10), 1),
        'current': round(random.uniform(0.5, 3), 2),
        'power': round(random.uniform(100, 700), 1),
        'energy': round(random.uniform(0.1, 2), 4),
        'appliance': 'fridge',
        'device_id': 'device01'
    }
    client.publish('energy/device01/telemetry', json.dumps(data), qos=1)
    print(f'[{i+1}/5] Sent: V={data["voltage"]}V, I={data["current"]}A, P={data["power"]}W')
    time.sleep(1)

client.disconnect()
print('[✓] Test data sent!')
"@
    
    Push-Location $BACKEND_DIR
    try {
        $testScript | & uv run python -
    } finally {
        Pop-Location
    }
}

function Test-MLService {
    Write-Banner
    Write-Host "[→] Testing ML Service..." -ForegroundColor Cyan
    
    $mlTestScript = @"
import requests
import json

BASE_URL = 'http://localhost:5000'

print('\n[1] Testing /ml/info...')
try:
    r = requests.get(f'{BASE_URL}/ml/info')
    data = r.json()
    print(f'    Models loaded: {len(data.get("power_predictors", []))} predictors')
    print(f'    Anomaly detectors: {len(data.get("anomaly_detectors", []))}')
except Exception as e:
    print(f'    Error: {e}')

print('\n[2] Testing /ml/appliances...')
try:
    r = requests.get(f'{BASE_URL}/ml/appliances')
    data = r.json()
    print(f'    Available: {", ".join(data.get("appliances", []))}')
except Exception as e:
    print(f'    Error: {e}')

print('\n[3] Simulating readings for fridge...')
try:
    readings = [35 + i*2 for i in range(10)]
    r = requests.post(f'{BASE_URL}/ml/simulate', json={'appliance': 'fridge', 'readings': readings})
    data = r.json()
    print(f'    Added {data.get("readings_added")} readings, total: {data.get("history_size")}')
except Exception as e:
    print(f'    Error: {e}')

print('\n[4] Testing prediction for fridge...')
try:
    r = requests.get(f'{BASE_URL}/ml/predict/fridge')
    data = r.json()
    if 'error' in data:
        print(f'    Note: {data["error"]}')
    else:
        print(f'    Predicted power: {data.get("predicted_power")} W')
except Exception as e:
    print(f'    Error: {e}')

print('\n[5] Testing anomaly detection...')
try:
    r = requests.post(f'{BASE_URL}/ml/anomaly/fridge', json={'power': 500})
    data = r.json()
    status = 'ANOMALY' if data.get('is_anomaly') else 'Normal'
    print(f'    500W reading: {status} (z-score: {data.get("z_score")})')
except Exception as e:
    print(f'    Error: {e}')

print('\n[✓] ML Service test complete!')
"@
    
    Push-Location $BACKEND_DIR
    try {
        $mlTestScript | & uv run python -
    } finally {
        Pop-Location
    }
}

# ─────────────────────────────────────────────────────────────
# Main
# ─────────────────────────────────────────────────────────────
switch ($Action) {
    "start"   { Start-Services }
    "stop"    { Stop-Services }
    "status"  { Show-Status }
    "test"    { Send-TestData }
    "ml-test" { Test-MLService }
}
