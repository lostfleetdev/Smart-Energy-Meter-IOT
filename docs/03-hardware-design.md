# 3. Hardware Design

## 3.1 Component List

### Bill of Materials

| # | Component | Model | Quantity | Purpose |
|---|-----------|-------|----------|---------|
| 1 | Microcontroller | ESP32-WROOM-32D | 1 | MCU + WiFi |
| 2 | Voltage Sensor | ZMPT101B | 1 | AC voltage sensing (0-250V) |
| 3 | Current Sensor | ACS712-20A | 1 | AC current sensing (0-20A) |
| 4 | OLED Display | SSD1306 128×64 | 1 | Local display |
| 5 | Relay Module | 5V Single-Channel | 1 | Load switching |
| 6 | Touch Sensor | TTP223 Capacitive | 1 | User input |
| 7 | Power Supply | HLK-PM01 | 1 | 230VAC → 5VDC |
| 8 | Voltage Regulator | AMS1117-3.3V | 1 | 5V → 3.3V for ESP32 |
| 9 | Enclosure | IP65 Junction Box | 1 | Housing |
| 10 | Terminals | Screw Terminal Blocks | 4 | Wire connections |

### Component Cost (Approximate)

| Component | Cost (INR) |
|-----------|------------|
| ESP32 DevKit | ₹450 |
| ZMPT101B | ₹180 |
| ACS712-20A | ₹120 |
| SSD1306 OLED | ₹200 |
| Relay Module | ₹80 |
| HLK-PM01 | ₹250 |
| Misc (wires, box, terminals) | ₹300 |
| **Total** | **~₹1,580** |

---

## 3.2 Pin Configuration

### ESP32 GPIO Mapping

```
                         ┌─────────────────────────────────────┐
                         │           ESP32-WROOM-32D          │
                         │                                     │
                         │  ┌───────────────────────────────┐  │
                         │  │                               │  │
                  3.3V ──┼──│ 3V3                     VIN   │──┼── 5V
                   GND ──┼──│ GND                     GND   │──┼── GND
                         │  │                               │  │
       [VOLTAGE_ADC] ────┼──│ GPIO35 (ADC1_CH7)    GPIO21  │──┼──── [I2C_SDA] OLED
       [CURRENT_ADC] ────┼──│ GPIO34 (ADC1_CH6)    GPIO18  │──┼──── [I2C_SCL] OLED
                         │  │                               │  │
        [TOUCH_BTN] ─────┼──│ GPIO4                 GPIO2   │──┼──── [RELAY_CTRL]
                         │  │                               │  │
                         │  │                               │  │
                         │  └───────────────────────────────┘  │
                         │                                     │
                         │          [ESP32 DevKit V1]          │
                         └─────────────────────────────────────┘
```

### Pin Reference Table

| GPIO | Function | Direction | Notes |
|------|----------|-----------|-------|
| 35 | Voltage ADC | Input | ZMPT101B signal (ADC1_CH7) |
| 34 | Current ADC | Input | ACS712 signal (ADC1_CH6) |
| 18 | I²C SCL | Output | OLED clock line |
| 21 | I²C SDA | Bidirectional | OLED data line |
| 2 | Relay Control | Output | Active LOW (0=ON, 1=OFF) |
| 4 | Touch Sensor | Input | HIGH when touched |

---

## 3.3 Circuit Diagram

### System Block Diagram

```
                                         ┌─────────────────────────────────────────┐
                                         │              POWER SUPPLY               │
                                         │                                         │
   ┌───────────────┐                     │   ┌───────────┐    ┌───────────┐        │
   │   AC MAINS    │──── L ──────────────┼──►│  HLK-PM01 │───►│  AMS1117  │──────────────► 3.3V (ESP32)
   │   230V AC     │──── N ──────────────┼──►│ 230V→5V   │    │  5V→3.3V  │        │
   │               │                     │   └───────────┘    └───────────┘        │
   └───────────────┘                     │         │                               │
          │                              │         ▼                               │
          │                              │        5V ──────────────────────────────────► 5V (Relay, OLED)
          │                              └─────────────────────────────────────────┘
          │
          │      ┌──────────────────────────────────────────────────────────────────────┐
          │      │                        MEASUREMENT CIRCUIT                           │
          │      │                                                                      │
          ├──────┼────────────────────────────────────────────────────────┐             │
          │      │                                                        │             │
          │      │   ┌─────────────┐                                      │             │
          │      │   │  ZMPT101B   │                                      │             │
          │      │   │  (Parallel) │────────────────────────► GPIO35      │             │
          │      │   │   V sensor  │                          (ADC)       │             │
          │      │   └─────────────┘                                      │             │
          │      │                                                        │             │
          │      │                      ┌─────────────────────────────────┼─────────────┼─────┐
          │      │                      │                                 │             │     │
          │      │   ┌─────────────┐    │                                 │             │     │
          └──────┼──►│  ACS712     │────┼───────────────────► GPIO34      │             │     │
                 │   │  (Series)   │    │                     (ADC)       │             │     │
                 │   │   I sensor  │    │                                 │             │     │
                 │   └─────────────┘    │                                 │             │     │
                 │                      │                                 │             │     │
                 │                      ▼                                 │             │     │
                 │              ┌───────────────┐                         │             │     │
                 │              │    RELAY      │◄──────────── GPIO2      │             │     │
                 │              │   (Series     │              (OUT)      │             │     │
                 │              │   on LIVE)    │                         │             │     │
                 │              └───────────────┘                         │             │     │
                 │                      │                                 │             │     │
                 │                      ▼                                 │             │     │
                 │              ┌───────────────┐                         │             │     │
                 │              │     LOAD      │                         │             │     │
                 │              │  (Appliance)  │                         │             │     │
                 │              └───────────────┘                         │             │     │
                 │                      │                                 │             │     │
                 └──────────────────────┴─────────────────────────────────┴─────────────┴─────┘
                                        │
                                        ▼
                                    NEUTRAL
```

### Detailed Connections

```
                    VOLTAGE SENSING                           CURRENT SENSING
                    ═══════════════                           ═══════════════
                                                              
    LIVE ──────────────┬────────────────► RELAY ──► LOAD      
                       │                                      
              ┌────────┴────────┐                            LIVE ──► ACS712 ──► LOAD
              │                 │                                       │
              │   ZMPT101B      │                                       │
              │                 │                            ┌──────────┴──────────┐
              │   +────┐        │                            │                     │
              │   │ AC │        │                            │    ACS712-20A       │
              │   │ IN │        │                            │                     │
              │   └────┘        │                            │   VCC ────► 5V      │
              │                 │                            │   GND ────► GND     │
              │   VCC ──► 5V    │                            │   OUT ────► GPIO34  │
              │   GND ──► GND   │                            │                     │
              │   OUT ──► GPIO35│                            └─────────────────────┘
              │                 │
              └─────────────────┘


                    OLED DISPLAY                             TOUCH SENSOR
                    ════════════                             ════════════
                                                             
              ┌─────────────────┐                            ┌─────────────────┐
              │                 │                            │                 │
              │   SSD1306       │                            │    TTP223       │
              │   128×64        │                            │    Module       │
              │                 │                            │                 │
              │   VCC ──► 3.3V  │                            │   VCC ──► 3.3V  │
              │   GND ──► GND   │                            │   GND ──► GND   │
              │   SCL ──► GPIO18│                            │   SIG ──► GPIO4 │
              │   SDA ──► GPIO21│                            │                 │
              │                 │                            └─────────────────┘
              └─────────────────┘


                    RELAY MODULE
                    ════════════
                    
              ┌─────────────────┐
              │                 │
              │   5V RELAY      │
              │   Module        │           COM ──► AC LIVE IN
              │                 │           NC  ──► (not used)
              │   VCC ──► 5V    │           NO  ──► LOAD LIVE
              │   GND ──► GND   │
              │   IN  ──► GPIO2 │   (Active LOW: 0=ON, 1=OFF)
              │                 │
              └─────────────────┘
```

---

## 3.4 Sensor Details

### ZMPT101B Voltage Sensor

| Parameter | Value |
|-----------|-------|
| Input Voltage | 0-250V AC |
| Output | 0-3.3V analog |
| Accuracy | ±1% |
| Isolation | 4kV |
| Connection | Parallel to mains |

**Working Principle:**
The ZMPT101B uses a miniature voltage transformer to step down mains voltage. The output is a proportional AC signal centered around VCC/2 (1.65V), which swings ±1.5V based on input voltage.

```
Output = VCC/2 + (Vin × Scaling_Factor × sin(ωt))
```

### ACS712-20A Current Sensor

| Parameter | Value |
|-----------|-------|
| Sensing Range | -20A to +20A |
| Sensitivity | 100mV/A (typ.) |
| Zero Current Output | VCC/2 (2.5V @ 5V supply) |
| Bandwidth | 80kHz |
| Isolation | 2.1kV RMS |

**Working Principle:**
Hall-effect sensor that produces a voltage proportional to current flowing through the IP+ and IP- terminals. At zero current, output is VCC/2. Current flow shifts output up/down from this midpoint.

```
Vout = VCC/2 + (I × Sensitivity)
     = 2.5V + (I × 0.1V/A)
```

---

## 3.5 Safety Considerations

### Electrical Safety

| Hazard | Mitigation |
|--------|------------|
| **High Voltage** | All mains connections in enclosed junction box |
| **Isolation** | HLK-PM01 provides 3kV isolation |
| **Grounding** | Enclosure bonded to earth |
| **Overload** | Relay rated for 10A max, fuse protection |
| **Short Circuit** | MCB on main supply |

### PCB Guidelines

1. **Creepage Distance**: Maintain 6mm between mains traces and low-voltage circuits
2. **Isolation Slots**: Route slots between HV and LV areas
3. **Grounding**: Single-point ground to avoid loops
4. **Bypass Caps**: 100nF ceramic at each IC VCC pin

---

## 3.6 Assembly Guide

### Step-by-Step

1. **Mount HLK-PM01** in corner of enclosure (max distance from sensor wires)
2. **Connect ZMPT101B** in parallel to mains (L-N terminals)
3. **Wire ACS712** in series with LIVE going to load
4. **Connect relay** NO terminal to load LIVE
5. **Mount ESP32** on standoffs, away from HV
6. **Connect sensors** to ADC pins (GPIO34, GPIO35)
7. **Connect I²C** to OLED (GPIO18-SCL, GPIO21-SDA)
8. **Mount touch sensor** near enclosure lid
9. **Verify all connections** before powering on
10. **Initial power-on** with multimeter monitoring 3.3V rail

### Connection Checklist

- [ ] HLK-PM01 L-N connected to mains
- [ ] 5V rail measures 5.0V ±0.2V
- [ ] 3.3V rail measures 3.3V ±0.1V
- [ ] ZMPT101B output ~1.65V at no load
- [ ] ACS712 output ~2.5V at no current
- [ ] OLED lights up on power-on
- [ ] Relay clicks when GPIO2 goes LOW

---

## 3.7 Physical Layout

```
┌──────────────────────────────────────────────────────────────┐
│                        ENCLOSURE TOP VIEW                    │
│                                                              │
│   ┌─────────┐                            ┌─────────────┐     │
│   │ HLK-PM01│                            │    OLED     │     │
│   │  SMPS   │                            │   Display   │     │
│   └─────────┘                            └─────────────┘     │
│                                                              │
│   ┌─────────┐    ┌─────────┐    ┌─────────────────────────┐ │
│   │ ZMPT101B│    │ ACS712  │    │         ESP32           │ │
│   │ Voltage │    │ Current │    │        DevKit           │ │
│   └─────────┘    └─────────┘    └─────────────────────────┘ │
│                                                              │
│   ┌─────────┐    ┌─────────┐                                │
│   │  RELAY  │    │  TOUCH  │                                │
│   │ Module  │    │  Sensor │                                │
│   └─────────┘    └─────────┘                                │
│                                                              │
│   ══════════════════════════════════════════════════════    │
│   │  L  │  N  │  E  │  L-OUT │  N-OUT │  E-OUT │            │
│   ══════════════════════════════════════════════════════    │
│          INPUT TERMINALS              OUTPUT TERMINALS       │
│                                                              │
└──────────────────────────────────────────────────────────────┘
```

---

## Next: [Firmware Guide →](./04-firmware-guide.md)
