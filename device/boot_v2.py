"""
boot_v2.py - WiFi and Configuration for Smart Energy Monitor ESP32
===================================================================
This file runs on every boot before main_v2.py
"""

import network
import time
import gc

# ══════════════════════════════════════════════════
# USER CONFIGURATION - Edit these values
# ══════════════════════════════════════════════════

# WiFi Settings
WIFI_SSID = "nokia"
WIFI_PASSWORD = "tetra123"

# Backend Server Configuration
MQTT_BROKER = "192.168.1.100"  # Your backend server IP address
MQTT_PORT = 1883               # Default MQTT port

# Device Identification
DEVICE_ID = "device01"         # Unique device identifier

# Appliance Type for ML Predictions
# Valid options: ac_1, ac_2, boiler, fridge, washing_machine, dishwasher
APPLIANCE_TYPE = "fridge"

# Timing Settings (milliseconds)
TELEMETRY_INTERVAL_MS = 2000   # Send data to backend every 2 seconds
DISPLAY_UPDATE_MS = 1000       # Update OLED display every 1 second
MQTT_RECONNECT_MS = 10000      # Retry MQTT connection every 10 seconds

# WiFi connection settings
WIFI_MAX_RETRIES = 3
WIFI_TIMEOUT_SEC = 15

# ══════════════════════════════════════════════════
# WiFi Connection Handler
# ══════════════════════════════════════════════════
def connect_wifi(max_retries=WIFI_MAX_RETRIES, timeout=WIFI_TIMEOUT_SEC):
    """Connect to WiFi with retry logic. Returns WLAN object or None."""
    wlan = network.WLAN(network.STA_IF)
    wlan.active(True)
    
    if wlan.isconnected():
        return wlan
    
    for attempt in range(max_retries):
        gc.collect()
        try:
            wlan.connect(WIFI_SSID, WIFI_PASSWORD)
        except OSError:
            time.sleep(2)
            continue
        
        wait_count = 0
        while wait_count < timeout:
            if wlan.isconnected():
                return wlan
            status = wlan.status()
            if status in (network.STAT_WRONG_PASSWORD, network.STAT_NO_AP_FOUND):
                break
            time.sleep(1)
            wait_count += 1
        
        wlan.disconnect()
        time.sleep(2)
    
    return None


def get_wifi_info():
    """Return WiFi info dict for display."""
    if wlan is None or not wlan.isconnected():
        return {"connected": False, "ip": None, "ssid": WIFI_SSID}
    
    cfg = wlan.ifconfig()
    return {
        "connected": True,
        "ip": cfg[0],
        "gateway": cfg[2],
        "ssid": WIFI_SSID
    }


# Connect on boot
wlan = connect_wifi()
gc.collect()
