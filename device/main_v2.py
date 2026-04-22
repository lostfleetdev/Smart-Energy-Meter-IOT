"""
Smart Energy Monitor - ESP32 Firmware v2
=========================================
WiFi + MQTT enabled version with telemetry publishing and relay control.
"""

from machine import Pin, SoftI2C, ADC
import network
import ssd1306
import time
import math
import json
import gc

try:
    from umqtt.simple import MQTTClient
except ImportError:
    MQTTClient = None

# Import config from boot_v2
try:
    from boot_v2 import (
        WIFI_SSID, WIFI_PASSWORD, WIFI_MAX_RETRIES, WIFI_TIMEOUT_SEC,
        MQTT_BROKER, MQTT_PORT, DEVICE_ID, APPLIANCE_TYPE,
        TELEMETRY_INTERVAL_MS, DISPLAY_UPDATE_MS, MQTT_RECONNECT_MS
    )
except ImportError:
    WIFI_SSID = "nokia"
    WIFI_PASSWORD = "tetra123"
    WIFI_MAX_RETRIES = 3
    WIFI_TIMEOUT_SEC = 15
    MQTT_BROKER = "10.144.231.186"
    MQTT_PORT = 1883
    DEVICE_ID = "device01"
    APPLIANCE_TYPE = "fridge"
    TELEMETRY_INTERVAL_MS = 2000
    DISPLAY_UPDATE_MS = 1000
    MQTT_RECONNECT_MS = 10000

# WiFi global
wlan = None

# ══════════════════════════════════════════════════
# Pin Configuration
# ══════════════════════════════════════════════════
TOUCH_PIN    = 4
RELAY_PIN    = 2
OLED_SCL     = 18
OLED_SDA     = 21
VOLTAGE_PIN  = 35
CURRENT_PIN  = 34

# ══════════════════════════════════════════════════
# MQTT Topics
# ══════════════════════════════════════════════════
TOPIC_TELEMETRY = "energy/" + DEVICE_ID + "/telemetry"
TOPIC_RELAY_SET = "energy/" + DEVICE_ID + "/relay/set"
TOPIC_RELAY_STATE = "energy/" + DEVICE_ID + "/relay/state"

# ══════════════════════════════════════════════════
# Hardware Initialization
# ══════════════════════════════════════════════════
i2c = None
oled = None
relay = None
touch_btn = None
adc_v = None
adc_i = None

def init_hardware():
    global i2c, oled, relay, touch_btn, adc_v, adc_i
    
    i2c = SoftI2C(scl=Pin(OLED_SCL), sda=Pin(OLED_SDA), freq=100000)
    oled = ssd1306.SSD1306_I2C(128, 64, i2c)
    
    relay = Pin(RELAY_PIN, Pin.OUT)
    relay.value(1)  # Active LOW: 1 = OFF
    
    touch_btn = Pin(TOUCH_PIN, Pin.IN)
    
    adc_v = ADC(Pin(VOLTAGE_PIN))
    adc_v.atten(ADC.ATTN_11DB)
    
    adc_i = ADC(Pin(CURRENT_PIN))
    adc_i.atten(ADC.ATTN_11DB)

# ══════════════════════════════════════════════════
# Calibration Constants
# ══════════════════════════════════════════════════
V_MIDPOINT       = 2048
V_SCALE          = 0.1
ACS_MIDPOINT_V   = 1.65
ACS_LIVE_MID     = 1.65
ACS_SENSITIVITY  = 0.066
V_NOISE_THRESH   = 30.0
I_NOISE_THRESH   = 0.08

# ══════════════════════════════════════════════════
# Global State
# ══════════════════════════════════════════════════
current_screen = 0
total_screens  = 5
energy_kwh     = 0.0
last_time      = 0
mqtt_client    = None
mqtt_connected = False
last_relay_state = 1
error_count = 0
tx_count = 0

# Debug values
raw_v_rms = 0.0
raw_i_rms = 0.0
raw_i_avg = 0.0

# ══════════════════════════════════════════════════
# OLED Display Functions
# ══════════════════════════════════════════════════
def safe_oled_write(func):
    global error_count
    try:
        func()
    except OSError:
        error_count += 1
        time.sleep_ms(100)
        try:
            init_hardware()
            func()
        except:
            pass

def show_oled(lines):
    def _write():
        oled.fill(0)
        for idx, line in enumerate(lines[:8]):
            oled.text(str(line), 0, idx * 8)
        oled.show()
    safe_oled_write(_write)

# ══════════════════════════════════════════════════
# Calibration Loading
# ══════════════════════════════════════════════════
def load_calibration():
    global V_MIDPOINT, V_SCALE, ACS_MIDPOINT_V, ACS_LIVE_MID, ACS_SENSITIVITY
    global V_NOISE_THRESH, I_NOISE_THRESH
    
    try:
        with open('calibration.json', 'r') as f:
            cal = json.load(f)
        
        V_MIDPOINT      = cal['v_midpoint']
        V_SCALE         = cal['v_scale']
        ACS_MIDPOINT_V  = cal['acs_midpoint_v']
        ACS_LIVE_MID    = ACS_MIDPOINT_V
        ACS_SENSITIVITY = cal['acs_sensitivity']
        V_NOISE_THRESH  = cal.get('v_noise_threshold', 30.0)
        I_NOISE_THRESH  = cal.get('i_noise_threshold', 0.08)
        
        return True
    except:
        return False

# ══════════════════════════════════════════════════
# WiFi Functions
# ══════════════════════════════════════════════════
def connect_wifi():
    global wlan
    wlan = network.WLAN(network.STA_IF)
    wlan.active(True)
    
    if wlan.isconnected():
        return True
    
    for attempt in range(WIFI_MAX_RETRIES):
        gc.collect()
        try:
            wlan.connect(WIFI_SSID, WIFI_PASSWORD)
        except OSError:
            time.sleep(2)
            continue
        
        wait_count = 0
        while wait_count < WIFI_TIMEOUT_SEC:
            if wlan.isconnected():
                return True
            status = wlan.status()
            if status in (network.STAT_WRONG_PASSWORD, network.STAT_NO_AP_FOUND):
                break
            time.sleep(1)
            wait_count += 1
        
        wlan.disconnect()
        time.sleep(2)
    
    return False

def check_wifi():
    """Check WiFi and reconnect if disconnected."""
    global wlan
    if wlan is None:
        return False
    if wlan.isconnected():
        return True
    # WiFi disconnected - try to reconnect
    try:
        wlan.connect(WIFI_SSID, WIFI_PASSWORD)
        wait = 0
        while wait < 10 and not wlan.isconnected():
            time.sleep(1)
            wait += 1
        return wlan.isconnected()
    except:
        return False

def get_wifi_info():
    if wlan is None or not wlan.isconnected():
        return {"connected": False, "ip": None, "ssid": WIFI_SSID}
    cfg = wlan.ifconfig()
    return {"connected": True, "ip": cfg[0], "ssid": WIFI_SSID}

# ══════════════════════════════════════════════════
# MQTT Functions
# ══════════════════════════════════════════════════
relay_changed = False  # Flag to publish state outside callback

def mqtt_callback(topic, msg):
    global relay_changed
    
    topic_str = topic.decode()
    payload = msg.decode()
    
    if topic_str == TOPIC_RELAY_SET:
        if payload == "1":
            relay.value(0)  # Active LOW: 0 = ON
        else:
            relay.value(1)  # Active LOW: 1 = OFF
        relay_changed = True  # Mark to publish state in main loop

def connect_mqtt():
    global mqtt_client, mqtt_connected
    
    if not wlan or not wlan.isconnected():
        mqtt_connected = False
        return False
    
    if MQTTClient is None:
        mqtt_connected = False
        return False
    
    # Close existing client if any
    if mqtt_client is not None:
        try:
            mqtt_client.disconnect()
        except:
            pass
        mqtt_client = None
    
    try:
        client_id = "esp32_" + DEVICE_ID
        mqtt_client = MQTTClient(client_id, MQTT_BROKER, port=MQTT_PORT, keepalive=60)
        mqtt_client.set_callback(mqtt_callback)
        mqtt_client.connect()
        mqtt_client.subscribe(TOPIC_RELAY_SET)
        mqtt_connected = True
        return True
    except Exception as e:
        mqtt_connected = False
        mqtt_client = None
        return False

def publish_telemetry(voltage, current, power, energy):
    global mqtt_connected, tx_count, mqtt_client
    
    if not mqtt_connected or mqtt_client is None:
        return False
    
    try:
        payload = json.dumps({
            "voltage": voltage,
            "current": current,
            "power": power,
            "energy": round(energy, 6),
            "appliance": APPLIANCE_TYPE,
            "device_id": DEVICE_ID
        })
        mqtt_client.publish(TOPIC_TELEMETRY, payload)
        tx_count += 1
        return True
    except OSError:
        mqtt_connected = False
        try:
            mqtt_client.disconnect()
        except:
            pass
        mqtt_client = None
        return False

def publish_relay_state():
    global mqtt_connected, mqtt_client
    
    if not mqtt_connected or mqtt_client is None:
        return False
    
    try:
        state = "0" if relay.value() == 1 else "1"
        mqtt_client.publish(TOPIC_RELAY_STATE, state)
        return True
    except OSError:
        mqtt_connected = False
        try:
            mqtt_client.disconnect()
        except:
            pass
        mqtt_client = None
        return False

def check_mqtt_messages():
    global mqtt_connected, mqtt_client
    
    if not mqtt_connected or mqtt_client is None:
        return
    
    try:
        mqtt_client.check_msg()
    except OSError:
        mqtt_connected = False
        try:
            mqtt_client.disconnect()
        except:
            pass
        mqtt_client = None

# ══════════════════════════════════════════════════
# Sensor Functions
# ══════════════════════════════════════════════════
def update_current_baseline():
    global ACS_LIVE_MID
    total_v = 0
    samples = 300
    
    for _ in range(samples):
        raw = adc_i.read()
        v = (raw / 4095.0) * 3.3
        total_v += v
        time.sleep_us(100)
    
    ACS_LIVE_MID = total_v / samples

def get_rms_voltage():
    global raw_v_rms
    try:
        sum_sq = 0
        samples = 200

        for _ in range(samples):
            val = adc_v.read() - V_MIDPOINT
            sum_sq += val * val
            time.sleep_us(100)

        rms_raw = math.sqrt(sum_sq / samples)
        raw_v_rms = rms_raw
        voltage = rms_raw * V_SCALE

        if V_NOISE_THRESH < 50 and voltage < V_NOISE_THRESH:
            return 0.0
        return round(voltage, 1)
    except:
        return 0.0

def get_rms_current():
    global raw_i_rms, raw_i_avg
    try:
        sum_sq = 0
        total_v = 0
        samples = 200

        for _ in range(samples):
            raw = adc_i.read()
            v = (raw / 4095.0) * 3.3
            total_v += v
            diff = v - ACS_LIVE_MID
            sum_sq += diff * diff
            time.sleep_us(100)

        raw_i_avg = total_v / samples
        rms_volts = math.sqrt(sum_sq / samples)
        raw_i_rms = rms_volts
        
        if ACS_SENSITIVITY <= 0:
            return 0.0
        
        irms = rms_volts / ACS_SENSITIVITY

        if irms < 0.1:
            return 0.0
        return round(irms, 2)
    except:
        return 0.0

# ══════════════════════════════════════════════════
# Display Functions
# ══════════════════════════════════════════════════
def get_status_icons():
    wifi_icon = "W" if (wlan and wlan.isconnected()) else "w"
    mqtt_icon = "M" if mqtt_connected else "m"
    relay_icon = "R" if relay.value() == 0 else "r"
    return wifi_icon + mqtt_icon + relay_icon

def update_display(v, i, w):
    def _update():
        oled.fill(0)
        status = get_status_icons()

        if current_screen == 0:
            # Main Dashboard
            hdr = "[%s] %s" % (status, APPLIANCE_TYPE[:6])
            oled.text(hdr, 0, 0)
            oled.hline(0, 9, 128, 1)
            
            oled.text("V:%.1f I:%.2f" % (v, i), 0, 12)
            oled.text("Power: %.1f W" % w, 0, 23)
            
            oled.hline(0, 32, 128, 1)
            oled.text("E: %.5f kWh" % energy_kwh, 0, 35)
            
            relay_str = "ON " if relay.value() == 0 else "OFF"
            oled.text("Relay:%s Tx:%d" % (relay_str, tx_count), 0, 46)
            
            oled.hline(0, 55, 128, 1)
            wifi_str = "OK" if (wlan and wlan.isconnected()) else "X"
            mqtt_str = "OK" if mqtt_connected else "X"
            oled.text("Net:%s Srv:%s" % (wifi_str, mqtt_str), 0, 57)

        elif current_screen == 1:
            # Energy
            oled.text("ENERGY [%s]" % status, 0, 0)
            oled.hline(0, 9, 128, 1)
            
            oled.text("Accumulated:", 0, 12)
            oled.text(" %.6f kWh" % energy_kwh, 0, 22)
            
            oled.hline(0, 31, 128, 1)
            oled.text("Current Readings:", 0, 34)
            oled.text("V:%.1f I:%.2f P:%.0f" % (v, i, w), 0, 44)
            
            relay_str = "ON" if relay.value() == 0 else "OFF"
            oled.text("Relay:%s Err:%d" % (relay_str, error_count), 0, 56)

        elif current_screen == 2:
            # Network
            oled.text("NETWORK [%s]" % status, 0, 0)
            oled.hline(0, 9, 128, 1)
            
            wifi_info = get_wifi_info()
            if wifi_info["connected"]:
                oled.text("WiFi: Connected", 0, 12)
                oled.text("IP: %s" % wifi_info["ip"], 0, 22)
            else:
                oled.text("WiFi: OFFLINE", 0, 12)
                ssid = wifi_info["ssid"]
                if ssid:
                    oled.text("SSID: %s" % ssid[:14], 0, 22)
            
            oled.hline(0, 31, 128, 1)
            
            if mqtt_connected:
                oled.text("MQTT: Connected", 0, 34)
                oled.text("Tx: %d msgs" % tx_count, 0, 44)
            else:
                oled.text("MQTT: OFFLINE", 0, 34)
                oled.text("Reconnecting...", 0, 44)
            
            oled.text("Srv:%s" % MQTT_BROKER[:15], 0, 56)

        elif current_screen == 3:
            # Config
            oled.text("CONFIG [%s]" % status, 0, 0)
            oled.hline(0, 9, 128, 1)
            
            oled.text("ID: %s" % DEVICE_ID, 0, 12)
            oled.text("Type: %s" % APPLIANCE_TYPE, 0, 22)
            
            oled.hline(0, 31, 128, 1)
            oled.text("Broker: %s" % MQTT_BROKER[:14], 0, 34)
            oled.text("Port: %d" % MQTT_PORT, 0, 44)
            
            oled.text("TX int: %dms" % TELEMETRY_INTERVAL_MS, 0, 56)

        elif current_screen == 4:
            # Debug
            oled.text("DEBUG [%s]" % status, 0, 0)
            oled.hline(0, 9, 128, 1)
            
            oled.text("Vraw: %.2f" % raw_v_rms, 0, 12)
            oled.text("Irms: %.5f V" % raw_i_rms, 0, 22)
            oled.text("Iavg: %.4f V" % raw_i_avg, 0, 32)
            oled.text("Imid: %.4f V" % ACS_LIVE_MID, 0, 42)
            
            gc.collect()
            mem_free = gc.mem_free() // 1024
            oled.text("Mem:%dK Err:%d" % (mem_free, error_count), 0, 56)

        oled.show()
    
    safe_oled_write(_update)

# ══════════════════════════════════════════════════
# Boot Screen
# ══════════════════════════════════════════════════
def boot_screen(step, total, title, detail=""):
    oled.fill(0)
    oled.text("SMART METER v2", 8, 0)
    oled.hline(0, 10, 128, 1)
    oled.text("[%d/%d] %s" % (step, total, title), 0, 14)
    if detail:
        oled.text(detail[:21], 0, 26)
    # Progress bar
    progress_pct = int((step / total) * 100)
    bar_width = int(progress_pct * 1.16)
    oled.rect(4, 52, 120, 10, 1)
    oled.fill_rect(5, 53, min(bar_width, 118), 8, 1)
    oled.text("%d%%" % progress_pct, 52, 40)
    oled.show()

# ══════════════════════════════════════════════════
# Main Loop
# ══════════════════════════════════════════════════
def main():
    global current_screen, energy_kwh, last_time, error_count, last_relay_state
    global mqtt_connected
    
    init_hardware()
    last_time = time.ticks_ms()
    
    # Step 1: Boot
    safe_oled_write(lambda: boot_screen(1, 6, "Booting", "ID: " + DEVICE_ID))
    time.sleep(0.5)
    
    # Step 2: Connect WiFi
    safe_oled_write(lambda: boot_screen(2, 6, "WiFi", WIFI_SSID[:16]))
    wifi_ok = connect_wifi()
    if wifi_ok:
        ip = wlan.ifconfig()[0]
        safe_oled_write(lambda: boot_screen(2, 6, "WiFi OK", ip))
    else:
        safe_oled_write(lambda: boot_screen(2, 6, "WiFi FAIL", "Offline mode"))
    time.sleep(0.6)
    
    # Step 3: Load calibration
    safe_oled_write(lambda: boot_screen(3, 6, "Calibration", "Loading..."))
    time.sleep(0.2)
    if not load_calibration():
        oled.fill(0)
        oled.text("!! ERROR !!", 20, 0)
        oled.hline(0, 10, 128, 1)
        oled.text("No calibration", 0, 16)
        oled.text("file found!", 0, 26)
        oled.text("Run calibrate.py", 0, 40)
        oled.text("then reboot", 0, 50)
        oled.show()
        while True:
            time.sleep(1)
    
    safe_oled_write(lambda: boot_screen(3, 6, "Calibration", "OK"))
    time.sleep(0.4)
    
    # Step 4: MQTT connection
    safe_oled_write(lambda: boot_screen(4, 6, "MQTT", MQTT_BROKER[:16]))
    mqtt_retry = 0
    while not mqtt_connected and mqtt_retry < 3:
        if connect_mqtt():
            safe_oled_write(lambda: boot_screen(4, 6, "MQTT OK", MQTT_BROKER[:16]))
            time.sleep(0.4)
            break
        mqtt_retry += 1
        time.sleep(0.5)
    
    if not mqtt_connected:
        safe_oled_write(lambda: boot_screen(4, 6, "MQTT FAIL", "Will retry..."))
        time.sleep(0.6)
    
    # Step 5: Zero sensors
    safe_oled_write(lambda: boot_screen(5, 6, "Sensors", "Zeroing..."))
    relay.value(1)
    time.sleep_ms(500)
    update_current_baseline()
    safe_oled_write(lambda: boot_screen(5, 6, "Sensors", "Ready"))
    time.sleep(0.3)
    
    # Step 6: Start
    safe_oled_write(lambda: boot_screen(6, 6, "Starting", APPLIANCE_TYPE))
    publish_relay_state()
    time.sleep(0.5)
    gc.collect()
    
    # Main loop variables
    btn_pressed = False
    press_start = 0
    last_update = 0
    last_mqtt_publish = 0
    mqtt_reconnect_time = 0
    wifi_check_time = 0
    
    # Main loop
    while True:
        try:
            now = time.ticks_ms()
            
            # Check MQTT messages
            check_mqtt_messages()
            
            # WiFi/MQTT Reconnection (check every 10s if disconnected)
            if not mqtt_connected and time.ticks_diff(now, mqtt_reconnect_time) > MQTT_RECONNECT_MS:
                # First ensure WiFi is connected
                if not (wlan and wlan.isconnected()):
                    if time.ticks_diff(now, wifi_check_time) > 30000:  # Check WiFi every 30s
                        check_wifi()
                        wifi_check_time = now
                # Then try MQTT if WiFi is up
                if wlan and wlan.isconnected():
                    connect_mqtt()
                mqtt_reconnect_time = now
            
            # Publish relay state if changed via MQTT command
            global relay_changed
            if relay_changed:
                publish_relay_state()
                relay_changed = False
            
            # Touch Button Handler
            is_touched = touch_btn.value() == 1

            if is_touched and not btn_pressed:
                btn_pressed = True
                press_start = now

            elif not is_touched and btn_pressed:
                btn_pressed = False
                duration = time.ticks_diff(now, press_start)

                if duration > 600:
                    current_screen = (current_screen + 1) % total_screens
                    last_update = 0
                elif duration > 50:
                    relay.value(not relay.value())
                    publish_relay_state()
                    last_update = 0

            # Auto re-zero when relay turns OFF
            current_relay = relay.value()
            if current_relay == 1 and last_relay_state == 0:
                time.sleep_ms(300)
                update_current_baseline()
            last_relay_state = current_relay

            # Sensor Read + Display
            if time.ticks_diff(now, last_update) >= DISPLAY_UPDATE_MS:
                volts = get_rms_voltage()
                amps = get_rms_current()
                watts = round(volts * amps, 1)

                hours_passed = time.ticks_diff(now, last_time) / 3600000.0
                energy_kwh += (watts / 1000.0) * hours_passed
                last_time = now

                update_display(volts, amps, watts)
                last_update = now
                
                # Publish Telemetry to MQTT
                if time.ticks_diff(now, last_mqtt_publish) >= TELEMETRY_INTERVAL_MS:
                    publish_telemetry(volts, amps, watts, energy_kwh)
                    last_mqtt_publish = now

            time.sleep_ms(20)
            
        except Exception as e:
            error_count += 1
            time.sleep_ms(500)
            try:
                init_hardware()
            except:
                pass


if __name__ == "__main__":
    main()

