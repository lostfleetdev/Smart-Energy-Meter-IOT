from machine import Pin, SoftI2C, ADC, WDT
import ssd1306
import time
import math
import json

# --- Pin Configuration ---
TOUCH_PIN    = 4    # Capacitive touch module (SIG)
RELAY_PIN    = 2    # Relay module
OLED_SCL     = 18
OLED_SDA     = 21
VOLTAGE_PIN  = 35   # ZMPT101B
CURRENT_PIN  = 34   # ACS712

# --- Hardware Initialization ---
def init_hardware():
    global i2c, oled, relay, touch_btn, adc_v, adc_i
    
    i2c  = SoftI2C(scl=Pin(OLED_SCL), sda=Pin(OLED_SDA), freq=100000)  # Slower I2C for stability
    oled = ssd1306.SSD1306_I2C(128, 64, i2c)
    
    relay = Pin(RELAY_PIN, Pin.OUT)
    relay.value(1)  # Active LOW: 1 = OFF
    
    touch_btn = Pin(TOUCH_PIN, Pin.IN)
    
    adc_v = ADC(Pin(VOLTAGE_PIN))
    adc_v.atten(ADC.ATTN_11DB)
    
    adc_i = ADC(Pin(CURRENT_PIN))
    adc_i.atten(ADC.ATTN_11DB)

init_hardware()

# --- Calibration Constants (loaded from calibration.json) ---
V_MIDPOINT       = 2048     # ZMPT101B ADC DC offset
V_SCALE          = 0.1      # Volts per ADC unit
ACS_MIDPOINT_V   = 1.65     # ACS712 zero-current voltage (static from file)
ACS_LIVE_MID     = 1.65     # Dynamic midpoint (updated when relay OFF)
ACS_SENSITIVITY  = 0.066    # Volts per Amp
V_NOISE_THRESH   = 30.0     # Voltage noise floor
I_NOISE_THRESH   = 0.08     # Current noise floor

# --- Global State ---
current_screen = 0
total_screens  = 4  # Added debug screen
energy_kwh     = 0.0
last_time      = time.ticks_ms()

# Debug: store raw values for troubleshooting
raw_v_rms = 0.0
raw_i_rms = 0.0
raw_i_avg = 0.0  # Average current ADC voltage (to see baseline)
error_count = 0  # Track errors
last_relay_state = 1  # Track relay changes for auto-zero


def safe_oled_write(func):
    """Wrapper to handle I2C errors on OLED."""
    global error_count
    try:
        func()
    except OSError:
        error_count += 1
        time.sleep_ms(100)
        try:
            init_hardware()  # Reinitialize on error
            func()
        except:
            pass


def show_oled(lines):
    """Display up to 8 lines on OLED (8px per line)."""
    def _write():
        oled.fill(0)
        for i, line in enumerate(lines[:8]):
            oled.text(str(line), 0, i * 8)
        oled.show()
    safe_oled_write(_write)


# ══════════════════════════════════════════════════
# LOAD CALIBRATION FROM FILE
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
        ACS_LIVE_MID    = ACS_MIDPOINT_V  # Start with calibrated value
        ACS_SENSITIVITY = cal['acs_sensitivity']
        V_NOISE_THRESH  = cal.get('v_noise_threshold', 30.0)
        I_NOISE_THRESH  = cal.get('i_noise_threshold', 0.08)
        
        show_oled([
            "Calibration",
            "Loaded!",
            "",
            f"Vmid: {V_MIDPOINT}",
            f"Vscl: {V_SCALE:.4f}",
            f"Imid: {ACS_MIDPOINT_V:.3f}",
            f"Isen: {ACS_SENSITIVITY:.4f}"
        ])
        time.sleep(2)
        return True
        
    except OSError:
        show_oled([
            "ERROR!",
            "",
            "No calibration",
            "file found.",
            "",
            "Run calibrate.py",
            "first!"
        ])
        return False
    
    except Exception as e:
        show_oled([
            "ERROR!",
            "",
            "Bad calibration",
            "file.",
            "",
            "Re-run",
            "calibrate.py"
        ])
        return False


# ══════════════════════════════════════════════════
# SENSOR FUNCTIONS
# ══════════════════════════════════════════════════
def update_current_baseline():
    """Re-zero current sensor when relay is OFF (no load)."""
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
    """RMS voltage from ZMPT101B using calibrated values."""
    global raw_v_rms
    try:
        sum_sq  = 0
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
    """RMS current from ACS712 using dynamic midpoint."""
    global raw_i_rms, raw_i_avg
    try:
        sum_sq  = 0
        total_v = 0
        samples = 200

        for _ in range(samples):
            raw = adc_i.read()
            v = (raw / 4095.0) * 3.3
            total_v += v
            diff = v - ACS_LIVE_MID  # Use dynamic midpoint
            sum_sq += diff * diff
            time.sleep_us(100)

        raw_i_avg = total_v / samples
        rms_volts = math.sqrt(sum_sq / samples)
        raw_i_rms = rms_volts
        
        if ACS_SENSITIVITY <= 0:
            return 0.0
        
        irms = rms_volts / ACS_SENSITIVITY

        if irms < 0.1:  # Fixed small threshold
            return 0.0
        return round(irms, 2)
    except:
        return 0.0


# ══════════════════════════════════════════════════
# DISPLAY FUNCTIONS
# ══════════════════════════════════════════════════
def update_display(v, i, w):
    def _update():
        oled.fill(0)

        if current_screen == 0:
            oled.text("== LIVE ==", 24, 0)
            oled.text(f"Volt: {v:.1f} V", 0, 18)
            oled.text(f"Curr: {i:.2f} A", 0, 32)
            oled.text(f"Powr: {w:.1f} W", 0, 46)

        elif current_screen == 1:
            oled.text("== ENERGY ==", 16, 0)
            oled.text("Total used:", 0, 20)
            oled.text(f"{energy_kwh:.4f} kWh", 0, 36)
            status = "ON" if relay.value() == 0 else "OFF"
            oled.text(f"Relay: {status}", 0, 52)

        elif current_screen == 2:
            oled.text("== CONTROL ==", 12, 0)
            status = "ON" if relay.value() == 0 else "OFF"
            oled.text(f"Relay: {status}", 0, 20)
            oled.text("Short tap:", 0, 36)
            oled.text("  Toggle relay", 0, 46)
            oled.text("Long press: Menu", 0, 56)

        elif current_screen == 3:
            # Debug screen - show raw values
            oled.text("== DEBUG ==", 20, 0)
            oled.text(f"Vrms:{raw_v_rms:.1f}", 0, 10)
            oled.text(f"Irms:{raw_i_rms:.4f}V", 0, 20)
            oled.text(f"Iavg:{raw_i_avg:.3f}V", 0, 30)
            oled.text(f"Iliv:{ACS_LIVE_MID:.3f}V", 0, 40)
            oled.text(f"Isen:{ACS_SENSITIVITY:.4f}", 0, 50)
            oled.text(f"E:{error_count}", 100, 0)

        oled.show()
    
    safe_oled_write(_update)


# ══════════════════════════════════════════════════
# MAIN LOOP
# ══════════════════════════════════════════════════
def main():
    global current_screen, energy_kwh, last_time, error_count, last_relay_state

    # Startup splash
    show_oled([
        "",
        "  SMART METER",
        "",
        "  Starting..."
    ])
    time.sleep(1)

    # Load calibration from file
    if not load_calibration():
        while True:
            time.sleep(1)

    # Initial zero with relay OFF
    show_oled(["Zeroing", "sensors..."])
    relay.value(1)  # Ensure OFF
    time.sleep_ms(500)
    update_current_baseline()
    
    btn_pressed  = False
    press_start  = 0
    last_update  = 0
    
    # Main loop with error recovery
    while True:
        try:
            # ── Touch Button Handler ──────────────────
            is_touched = touch_btn.value() == 1

            if is_touched and not btn_pressed:
                btn_pressed = True
                press_start = time.ticks_ms()

            elif not is_touched and btn_pressed:
                btn_pressed = False
                duration = time.ticks_diff(time.ticks_ms(), press_start)

                if duration > 600:
                    current_screen = (current_screen + 1) % total_screens
                    last_update = 0
                elif duration > 50:
                    relay.value(not relay.value())
                    last_update = 0

            # ── Auto re-zero when relay turns OFF ──────────────────
            current_relay = relay.value()
            if current_relay == 1 and last_relay_state == 0:
                # Relay just turned OFF - re-zero baseline after settling
                time.sleep_ms(300)
                update_current_baseline()
            last_relay_state = current_relay

            # ── Sensor Read + Display (every 1 second) ───────────────
            now = time.ticks_ms()
            if time.ticks_diff(now, last_update) >= 1000:
                volts = get_rms_voltage()
                amps  = get_rms_current()
                watts = round(volts * amps, 1)

                hours_passed = time.ticks_diff(now, last_time) / 3_600_000.0
                energy_kwh  += (watts / 1000.0) * hours_passed
                last_time    = now

                update_display(volts, amps, watts)
                last_update = now

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
