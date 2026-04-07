# boot_v2.py - WiFi and MQTT Configuration for Smart Energy Monitor
# This file runs on every boot before main_v2.py

import network
import time

# ══════════════════════════════════════════════════
# Configuration - Edit these values
# ══════════════════════════════════════════════════
WIFI_SSID = "Yashraj15"
WIFI_PASSWORD = "Apppa9959"

# Backend server configuration
MQTT_BROKER = "192.168.0.61"  # Your backend server IP
MQTT_PORT = 1883
DEVICE_ID = "device01"

# Appliance type (for ML predictions)
# Options: ac_1, ac_2, boiler, fridge, washing_machine, dishwasher
APPLIANCE_TYPE = "fridge"

# Telemetry settings
TELEMETRY_INTERVAL_MS = 2000  # Send data every 2 seconds
DISPLAY_UPDATE_MS = 1000      # Update display every 1 second

# ══════════════════════════════════════════════════
# WiFi Connection
# ══════════════════════════════════════════════════
def connect_wifi(max_retries=3):
    """Connect to WiFi with retry logic."""
    wlan = network.WLAN(network.STA_IF)
    wlan.active(True)
    
    if wlan.isconnected():
        print(f"[WiFi] Already connected: {wlan.ifconfig()[0]}")
        return wlan
    
    for attempt in range(max_retries):
        print(f"[WiFi] Connecting to {WIFI_SSID} (attempt {attempt + 1}/{max_retries})...")
        wlan.connect(WIFI_SSID, WIFI_PASSWORD)
        
        # Wait for connection with timeout
        max_wait = 15
        while max_wait > 0:
            if wlan.isconnected():
                break
            time.sleep(1)
            max_wait -= 1
            print(".", end="")
        
        if wlan.isconnected():
            ip = wlan.ifconfig()[0]
            print(f"\n[WiFi] Connected! IP: {ip}")
            return wlan
        
        print(f"\n[WiFi] Attempt {attempt + 1} failed")
        time.sleep(2)
    
    print("[WiFi] All connection attempts failed!")
    return None

# Connect on boot
wlan = connect_wifi()
