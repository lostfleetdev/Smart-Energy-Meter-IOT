# core technical highlights for viva

## visual metaphor

Use a "measurement pipeline" graphic with three vertical lanes: **edge device**, **server intelligence**, **operator interface**.  
Color the telemetry path as solid arrows and relay command path as dashed arrows, matching your report sequence diagram.

## one-line pitch

Calibrated 200-sample AC sensing on ESP32, coupled with MQTT + SSE + LightGBM inference, gives appliance-level visibility and control in one closed loop.

## the technical surprise

When relay switches OFF, firmware waits 300 ms and re-estimates the ACS712 baseline before continuing measurements.  
This small auto-zero step reduces drift and makes low-current readings more stable after switching events.

## the core algorithm or feature to force examiner focus

Focus on the calibrated RMS + power computation and verified error bounds.  
This is the foundation that makes everything else valid, including ML outputs and relay decisions.

## the motivation

Users do not act on monthly aggregate kWh because it does not tell them which appliance is responsible.  
Device-level metering gives a direct answer and enables practical interventions such as targeted switching and fault investigation.

