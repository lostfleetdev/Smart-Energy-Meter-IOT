"""
Smart Meter Calibration Script (OLED-only, no terminal needed)
==============================================================
Run this script to calibrate voltage and current sensors.
All feedback shown on OLED display. Use touch button to proceed.
"""

from machine import Pin, SoftI2C, ADC
import ssd1306
import time
import math
import json

# --- Pin Configuration ---
TOUCH_PIN    = 4
RELAY_PIN    = 2
OLED_SCL     = 18
OLED_SDA     = 21
VOLTAGE_PIN  = 35
CURRENT_PIN  = 34

# --- Hardware Init ---
i2c  = SoftI2C(scl=Pin(OLED_SCL), sda=Pin(OLED_SDA), freq=400000)
oled = ssd1306.SSD1306_I2C(128, 64, i2c)

relay = Pin(RELAY_PIN, Pin.OUT)
relay.value(1)  # OFF initially

touch_btn = Pin(TOUCH_PIN, Pin.IN)

adc_v = ADC(Pin(VOLTAGE_PIN))
adc_v.atten(ADC.ATTN_11DB)

adc_i = ADC(Pin(CURRENT_PIN))
adc_i.atten(ADC.ATTN_11DB)

# Known load for calibration
KNOWN_VOLTAGE = 230.0  # Indian mains nominal voltage
KNOWN_POWER   = 600.0  # Your kettle's rated power in watts


def show_oled(lines):
    """Display up to 8 lines on OLED (8px per line)."""
    oled.fill(0)
    for i, line in enumerate(lines[:8]):
        oled.text(str(line), 0, i * 8)
    oled.show()


def wait_for_touch():
    """Wait for touch button press and release."""
    while touch_btn.value() == 0:
        time.sleep_ms(50)
    while touch_btn.value() == 1:
        time.sleep_ms(50)
    time.sleep_ms(200)


def show_progress(title, current, total):
    """Show progress bar on OLED."""
    oled.fill(0)
    oled.text(title, 0, 0)
    
    # Progress bar
    bar_width = 100
    filled = int((current / total) * bar_width)
    oled.rect(14, 28, bar_width + 4, 12, 1)
    oled.fill_rect(16, 30, filled, 8, 1)
    
    pct = int((current / total) * 100)
    oled.text(f"{pct}%", 52, 48)
    oled.show()


def sample_adc_with_progress(adc, samples, title):
    """Get raw ADC samples with progress display."""
    readings = []
    for i in range(samples):
        readings.append(adc.read())
        time.sleep_us(200)
        if i % 100 == 0:
            show_progress(title, i, samples)
    
    avg = sum(readings) / len(readings)
    return avg, readings


def measure_rms_voltage_raw(midpoint, samples=500):
    """Measure RMS voltage in raw ADC units."""
    sum_sq = 0
    for _ in range(samples):
        val = adc_v.read() - midpoint
        sum_sq += val * val
        time.sleep_us(200)
    return math.sqrt(sum_sq / samples)


def measure_rms_current_raw(midpoint_v, samples=500):
    """Measure RMS current in volts from ADC midpoint."""
    sum_sq = 0
    for _ in range(samples):
        v = (adc_i.read() / 4095.0) * 3.3
        diff = v - midpoint_v
        sum_sq += diff * diff
        time.sleep_us(200)
    return math.sqrt(sum_sq / samples)


def save_calibration(cal_data):
    """Save calibration data to JSON file."""
    with open('calibration.json', 'w') as f:
        json.dump(cal_data, f)


def main():
    # ══════════════════════════════════════════════════
    # WELCOME SCREEN
    # ══════════════════════════════════════════════════
    show_oled([
        "================",
        " SMART METER",
        " CALIBRATION",
        "================",
        "",
        f"Load: {int(KNOWN_POWER)}W",
        "",
        "Touch to start"
    ])
    wait_for_touch()
    
    # ══════════════════════════════════════════════════
    # STEP 1: NO LOAD - Measure Zero Points
    # ══════════════════════════════════════════════════
    show_oled([
        "== STEP 1 of 2 ==",
        "",
        "Remove ALL loads",
        "from socket",
        "",
        "Unplug kettle!",
        "",
        "Touch when ready"
    ])
    wait_for_touch()
    
    # Turn relay ON to measure circuit
    relay.value(0)
    time.sleep(1)
    
    # Sample voltage ADC with progress
    show_progress("Reading V...", 0, 2000)
    V_MIDPOINT, _ = sample_adc_with_progress(adc_v, 2000, "Reading V...")
    V_MIDPOINT = int(V_MIDPOINT)
    
    # Sample current ADC
    show_progress("Reading I...", 0, 2000)
    i_samples = []
    for i in range(2000):
        i_samples.append((adc_i.read() / 4095.0) * 3.3)
        time.sleep_us(200)
        if i % 100 == 0:
            show_progress("Reading I...", i, 2000)
    ACS_MIDPOINT_V = sum(i_samples) / len(i_samples)
    
    # Get no-load RMS readings
    show_oled(["Calculating", "RMS values..."])
    v_rms_noload = measure_rms_voltage_raw(V_MIDPOINT, 1000)
    i_rms_noload = measure_rms_current_raw(ACS_MIDPOINT_V, 1000)
    
    # Show no-load results
    show_oled([
        "NO-LOAD DONE",
        "============",
        f"V mid: {V_MIDPOINT}",
        f"I mid: {ACS_MIDPOINT_V:.3f}V",
        f"V rms: {v_rms_noload:.1f}",
        f"I rms: {i_rms_noload:.4f}",
        "",
        "Touch continue"
    ])
    wait_for_touch()
    
    # ══════════════════════════════════════════════════
    # STEP 2: WITH LOAD - Measure with known appliance
    # ══════════════════════════════════════════════════
    show_oled([
        "== STEP 2 of 2 ==",
        "",
        "Connect kettle",
        f"({int(KNOWN_POWER)}W) to socket",
        "",
        "Turn kettle ON!",
        "",
        "Touch when ready"
    ])
    wait_for_touch()
    
    show_oled([
        "Measuring load...",
        "",
        "Keep kettle ON",
        "Please wait..."
    ])
    time.sleep(3)  # Let kettle stabilize
    
    # Multiple measurements for accuracy
    v_readings = []
    i_readings = []
    
    for sample in range(5):
        show_oled([
            "Measuring load...",
            "",
            f"Sample {sample+1} of 5",
            "",
            "Keep kettle ON!"
        ])
        
        v_rms = measure_rms_voltage_raw(V_MIDPOINT, 500)
        i_rms = measure_rms_current_raw(ACS_MIDPOINT_V, 500)
        v_readings.append(v_rms)
        i_readings.append(i_rms)
        time.sleep_ms(300)
    
    v_rms_load = sum(v_readings) / len(v_readings)
    i_rms_load = sum(i_readings) / len(i_readings)
    
    # Show raw readings
    show_oled([
        "WITH-LOAD DONE",
        "==============",
        f"V rms: {v_rms_load:.1f}",
        f"I rms: {i_rms_load:.4f}V",
        "",
        "",
        "",
        "Touch continue"
    ])
    wait_for_touch()
    
    # ══════════════════════════════════════════════════
    # STEP 3: Calculate Calibration Factors
    # ══════════════════════════════════════════════════
    show_oled(["Calculating", "calibration..."])
    
    # Voltage scaling: raw ADC RMS -> actual voltage
    V_SCALE = KNOWN_VOLTAGE / v_rms_load
    
    # Current: using known power and voltage
    expected_current = KNOWN_POWER / KNOWN_VOLTAGE
    
    # ACS sensitivity: volts per amp
    ACS_SENSITIVITY = i_rms_load / expected_current
    
    # Verify calculation
    calc_voltage = v_rms_load * V_SCALE
    calc_current = i_rms_load / ACS_SENSITIVITY
    calc_power = calc_voltage * calc_current
    
    # Noise thresholds
    V_NOISE_THRESHOLD = v_rms_noload * V_SCALE * 1.5
    I_NOISE_THRESHOLD = (i_rms_noload / ACS_SENSITIVITY) * 1.5 if ACS_SENSITIVITY > 0 else 0.1
    
    # Show calculated values
    show_oled([
        "CALCULATED:",
        f"V scale:{V_SCALE:.4f}",
        f"I sens:{ACS_SENSITIVITY:.4f}",
        "",
        "VERIFY:",
        f"V:{calc_voltage:.0f} I:{calc_current:.2f}",
        f"P:{calc_power:.0f}W",
        "Touch to save"
    ])
    wait_for_touch()
    
    # ══════════════════════════════════════════════════
    # STEP 4: Save Calibration
    # ══════════════════════════════════════════════════
    calibration = {
        'v_midpoint': V_MIDPOINT,
        'v_scale': V_SCALE,
        'acs_midpoint_v': ACS_MIDPOINT_V,
        'acs_sensitivity': ACS_SENSITIVITY,
        'v_noise_threshold': V_NOISE_THRESHOLD,
        'i_noise_threshold': I_NOISE_THRESHOLD,
        'calibration_voltage': KNOWN_VOLTAGE,
        'calibration_power': KNOWN_POWER,
        'raw_v_rms_noload': v_rms_noload,
        'raw_i_rms_noload': i_rms_noload,
        'raw_v_rms_load': v_rms_load,
        'raw_i_rms_load': i_rms_load,
    }
    
    show_oled(["Saving to", "flash memory..."])
    save_calibration(calibration)
    time.sleep(1)
    
    # Turn relay OFF
    relay.value(1)
    
    # Final success screen
    show_oled([
        "================",
        " CALIBRATION",
        " COMPLETE!",
        "================",
        "",
        "Remove kettle",
        "Restart device",
        "to use main.py"
    ])
    
    # Keep showing success
    while True:
        time.sleep(1)


if __name__ == "__main__":
    main()
