# 5-minute architecture overview

## concise pitch

We designed a three-tier IoT system to replace appliance-level guesswork with direct measurement.  
The ESP32 node samples AC voltage and current, computes calibrated RMS and power metrics locally, publishes telemetry through MQTT, and keeps local visibility through OLED.  
A Flask backend receives each packet, runs ML inference, stores history, and pushes live updates through SSE.  
The web dashboard displays live and historical behavior and sends relay commands back to the same device path.

## sequential build steps to prove execution

1. Defined the problem boundary: single-appliance, single-phase meter with remote visibility and control.  
2. Built sensing hardware using ZMPT101B, ACS712, HLK-PM01, ESP32, relay, OLED, and touch module.  
3. Implemented firmware loop: 200 samples per 20 ms cycle, RMS and power calculation, JSON telemetry packaging.  
4. Added calibration pipeline (`calibrate.py`) with no-load baseline and known-load scaling using a 600 W kettle.  
5. Integrated MQTT topics for telemetry, relay set, and relay state synchronization.  
6. Built backend interfaces (`/stream`, `/history`, `/relay`, ML routes) with Flask, paho-mqtt, and SSE.  
7. Trained ML models from PLEGMA data (LightGBM regressor, LightGBM classifier, Isolation Forest + Z-score).  
8. Connected frontend dashboard with live gauges, history chart, anomaly panel, and relay controls.  
9. Validated on kettle and charger loads against a commercial reference meter and documented error bounds.

## speaking points (short script)

- "We did not stop at simulation. We implemented full sensing, transport, inference, and control as one loop."  
- "The architecture is not theoretical. Every block maps to a concrete file and runtime endpoint."  
- "Our key engineering decision was appliance-level direct sensing, then analytics, instead of aggregate disaggregation."

