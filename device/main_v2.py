"""
Smart Energy Monitor - ESP32 Firmware v2
=========================================
WiFi + MQTT enabled version with telemetry publishing and relay control.
Sends data to backend which handles ML predictions.
"""

from machine import Pin, SoftI2C, ADC
import ssd1306
import time
import math
import json

try:
    from umqtt.simple import MQTTClient
except ImportError:
    print("ERROR: umqtt not found. Install with: import upip; upip.install('micropython-umqtt.simple')")
    MQTTClient = None

# Import WiFi config from boot_v2
try:
    from boot_v2 import (
        MQTT_BROKER, MQTT_PORT, DEVICE_ID, APPLIANCE_TYPE,
        TELEMETRY_INTERVAL_MS, DISPLAY_UPDATE_MS, wlan
    )
except ImportError:
    MQTT_BROKER = "localhost"
    MQTT_PORT = 1883
    DEVICE_ID = "device01"
    APPLIANCE_TYPE = "fridge"
    TELEMETRY_INTERVAL_MS = 2000
    DISPLAY_UPDATE_MS = 1000
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
# MQTT Topics (matching backend)
# ══════════════════════════════════════════════════
TOPIC_TELEMETRY = f"energy/{DEVICE_ID}/telemetry"
TOPIC_RELAY_SET = f"energy/{DEVICE_ID}/relay/set"
TOPIC_RELAY_STATE = f"energy/{DEVICE_ID}/relay/state"

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
total_screens  = 4
energy_kwh     = 0.0
last_time      = 0
mqtt_client    = None
mqtt_connected = False
last_relay_state = 1
error_count = 0

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
        for i, line in enumerate(lines[:8]):
            oled.text(str(line), 0, i * 8)
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
# MQTT Functions
# ══════════════════════════════════════════════════
def mqtt_callback(topic, msg):
    """Handle incoming MQTT messages (relay control)."""
    global last_relay_state
    
    topic_str = topic.decode()
    payload = msg.decode()
    
    if topic_str == TOPIC_RELAY_SET:
        if payload == "1":
            relay.value(0)  # Active LOW: 0 = ON
            print("[MQTT] Relay ON")
        else:
            relay.value(1)  # Active LOW: 1 = OFF
            print("[MQTT] Relay OFF")
        
        # Publish state back
        publish_relay_state()

def connect_mqtt():
    global mqtt_client, mqtt_connected
    
    if not wlan or not wlan.isconnected():
        print("[MQTT] No WiFi connection")
        return False
    
    if MQTTClient is None:
        print("[MQTT] umqtt library not available")
        return False
    
    try:
        client_id = f"esp32_{DEVICE_ID}"
        mqtt_client = MQTTClient(client_id, MQTT_BROKER, port=MQTT_PORT)
        mqtt_client.set_callback(mqtt_callback)
        mqtt_client.connect()
        mqtt_client.subscribe(TOPIC_RELAY_SET)
        mqtt_connected = True
        print(f"[MQTT] Connected to {MQTT_BROKER}:{MQTT_PORT}")
        return True
    except Exception as e:
        print(f"[MQTT] Connection failed: {e}")
        mqtt_connected = False
        return False

def publish_telemetry(voltage, current, power, energy):
    """Publish sensor data to MQTT."""
    global mqtt_connected
    
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
        mqtt_client.publish(TOPIC_TELEMETRY, payload, qos=0)
        return True
    except Exception as e:
        print(f"[MQTT] Publish failed: {e}")
        mqtt_connected = False
        return False

def publish_relay_state():
    """Publish current relay state."""
    global mqtt_connected
    
    if not mqtt_connected or mqtt_client is None:
        return False
    
    try:
        state = "0" if relay.value() == 1 else "1"  # Invert (active LOW)
        mqtt_client.publish(TOPIC_RELAY_STATE, state, qos=0)
        return True
    except:
        mqtt_connected = False
        return False

def check_mqtt_messages():
    """Check for incoming MQTT messages (non-blocking)."""
    global mqtt_connected
    
    if not mqtt_connected or mqtt_client is None:
        return
    
    try:
        mqtt_client.check_msg()
    except:
        mqtt_connected = False

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
    """Return compact status string for header."""
    wifi_icon = "W" if (wlan and wlan.isconnected()) else "!"
    mqtt_icon = "M" if mqtt_connected else "!"
    relay_icon = "R" if relay.value() == 0 else "r"  # R=ON, r=OFF
    return f"{wifi_icon}{mqtt_icon}{relay_icon}"

def update_display(v, i, w):
    def _update():
        oled.fill(0)
        status = get_status_icons()

        if current_screen == 0:
            # ── Main Dashboard - All key info ──
            oled.text(f"LIVE [{status}]", 0, 0)
            oled.hline(0, 9, 128, 1)
            
            # Large power display
            oled.text(f"{v:.1f}V {i:.2f}A", 0, 12)
            oled.text(f"Power: {w:.1f}W", 0, 22)
            
            # Energy + Relay status
            oled.hline(0, 31, 128, 1)
            oled.text(f"E:{energy_kwh:.4f}kWh", 0, 34)
            
            relay_str = "ON " if relay.value() == 0 else "OFF"
            oled.text(f"Relay:{relay_str}", 0, 44)
            
            # Network status bar
            oled.hline(0, 53, 128, 1)
            wifi_str = "OK" if (wlan and wlan.isconnected()) else "X"
            mqtt_str = "OK" if mqtt_connected else "X"
            oled.text(f"WiFi:{wifi_str} MQTT:{mqtt_str}", 0, 56)

        elif current_screen == 1:
            # ── Energy & Stats ──
            oled.text(f"ENERGY [{status}]", 0, 0)
            oled.hline(0, 9, 128, 1)
            
            oled.text(f"Total:", 0, 12)
            oled.text(f" {energy_kwh:.6f} kWh", 0, 22)
            
            oled.hline(0, 31, 128, 1)
            oled.text(f"V:{v:.1f} I:{i:.2f}", 0, 34)
            oled.text(f"P:{w:.1f}W", 0, 44)
            
            relay_str = "ON" if relay.value() == 0 else "OFF"
            oled.text(f"Relay: {relay_str}", 0, 56)

        elif current_screen == 2:
            # ── Network Info ──
            oled.text(f"NETWORK [{status}]", 0, 0)
            oled.hline(0, 9, 128, 1)
            
            # WiFi section
            if wlan and wlan.isconnected():
                ip = wlan.ifconfig()[0]
                oled.text("WiFi: Connected", 0, 12)
                oled.text(f"IP:{ip}", 0, 22)
            else:
                oled.text("WiFi: OFFLINE", 0, 12)
                oled.text("No IP", 0, 22)
            
            oled.hline(0, 31, 128, 1)
            
            # MQTT section
            if mqtt_connected:
                oled.text("MQTT: Connected", 0, 34)
            else:
                oled.text("MQTT: OFFLINE", 0, 34)
            oled.text(f"Brkr:{MQTT_BROKER}", 0, 44)
            oled.text(f"ID:{DEVICE_ID}", 0, 54)

        elif current_screen == 3:
            # ── Debug/Raw Values ──
            oled.text(f"DEBUG [{status}]", 0, 0)
            oled.hline(0, 9, 128, 1)
            
            oled.text(f"Vraw:{raw_v_rms:.1f}", 0, 12)
            oled.text(f"Irms:{raw_i_rms:.4f}V", 0, 22)
            oled.text(f"Iavg:{raw_i_avg:.3f}V", 0, 32)
            oled.text(f"Imid:{ACS_LIVE_MID:.3f}V", 0, 42)
            oled.text(f"Sens:{ACS_SENSITIVITY:.4f}", 0, 52)
            oled.text(f"Err:{error_count}", 90, 52)

        oled.show()
    
    safe_oled_write(_update)

# ══════════════════════════════════════════════════
# Main Loop
# ══════════════════════════════════════════════════
def main():
    global current_screen, energy_kwh, last_time, error_count, last_relay_state
    global mqtt_connected
    
    init_hardware()
    last_time = time.ticks_ms()
    
    # Startup splash with boot progress
    def boot_screen(step, status, detail=""):
        oled.fill(0)
        oled.text("SMART METER v2", 8, 0)
        oled.hline(0, 10, 128, 1)
        oled.text(f"Step {step}/5", 0, 14)
        oled.text(status, 0, 26)
        if detail:
            oled.text(detail[:16], 0, 38)
        # Progress bar
        progress = int((step / 5) * 120)
        oled.rect(4, 52, 120, 10, 1)
        oled.fill_rect(5, 53, progress, 8, 1)
        oled.show()
    
    safe_oled_write(lambda: boot_screen(1, "Booting..."))
    time.sleep(0.5)
    
    # Show WiFi status
    if wlan and wlan.isconnected():
        ip = wlan.ifconfig()[0]
        safe_oled_write(lambda: boot_screen(2, "WiFi: OK", ip))
    else:
        safe_oled_write(lambda: boot_screen(2, "WiFi: OFFLINE", "No connection"))
    time.sleep(0.8)
    
    # Load calibration
    safe_oled_write(lambda: boot_screen(3, "Loading calib..."))
    time.sleep(0.3)
    if not load_calibration():
        show_oled([
            "!! ERROR !!",
            "",
            "No calibration",
            "file found.",
            "",
            "Run calibrate.py",
            "then reboot"
        ])
        while True:
            time.sleep(1)
    
    safe_oled_write(lambda: boot_screen(3, "Calibration: OK"))
    time.sleep(0.5)
    
    # Connect to MQTT
    safe_oled_write(lambda: boot_screen(4, "MQTT connecting", MQTT_BROKER))
    mqtt_retry_count = 0
    while not mqtt_connected and mqtt_retry_count < 3:
        if connect_mqtt():
            safe_oled_write(lambda: boot_screen(4, "MQTT: OK", MQTT_BROKER))
            time.sleep(0.5)
            break
        mqtt_retry_count += 1
        time.sleep(0.5)
    
    if not mqtt_connected:
        safe_oled_write(lambda: boot_screen(4, "MQTT: OFFLINE", "Will retry..."))
        time.sleep(0.8)
    
    # Initial sensor zero
    safe_oled_write(lambda: boot_screen(5, "Zeroing sensors"))
    relay.value(1)
    time.sleep_ms(500)
    update_current_baseline()
    
    # Publish initial relay state
    publish_relay_state()
    
    btn_pressed = False
    press_start = 0
    last_update = 0
    last_mqtt_publish = 0
    mqtt_reconnect_time = 0
    
    MQTT_RECONNECT_INTERVAL_MS = 10000  # Retry MQTT every 10 seconds
    
    # Main loop
    while True:
        try:
            now = time.ticks_ms()
            
            # ── Check MQTT messages ──────────────────
            check_mqtt_messages()
            
            # ── MQTT Reconnection ──────────────────
            if not mqtt_connected and time.ticks_diff(now, mqtt_reconnect_time) > MQTT_RECONNECT_INTERVAL_MS:
                connect_mqtt()
                mqtt_reconnect_time = now
            
            # ── Touch Button Handler ──────────────────
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

            # ── Auto re-zero when relay turns OFF ──────────────────
            current_relay = relay.value()
            if current_relay == 1 and last_relay_state == 0:
                time.sleep_ms(300)
                update_current_baseline()
            last_relay_state = current_relay

            # ── Sensor Read + Display ───────────────
            if time.ticks_diff(now, last_update) >= DISPLAY_UPDATE_MS:
                volts = get_rms_voltage()
                amps = get_rms_current()
                watts = round(volts * amps, 1)

                hours_passed = time.ticks_diff(now, last_time) / 3_600_000.0
                energy_kwh += (watts / 1000.0) * hours_passed
                last_time = now

                update_display(volts, amps, watts)
                last_update = now
                
                # ── Publish Telemetry to MQTT ──────────────────
                if time.ticks_diff(now, last_mqtt_publish) >= TELEMETRY_INTERVAL_MS:
                    publish_telemetry(volts, amps, watts, energy_kwh)
                    last_mqtt_publish = now

            time.sleep_ms(20)
            
        except Exception as e:
            error_count += 1
            print(f"[ERROR] {e}")
            time.sleep_ms(500)
            try:
                init_hardware()
            except:
                pass


if __name__ == "__main__":
    main()
