# academic contribution slide (use exact bullets)

- Implemented an appliance-level smart energy meter using ESP32 DevKit V1 with ZMPT101B voltage sensing and ACS712 current sensing.  
- Designed and validated a calibration workflow (no-load baseline + known-load scaling) with persisted constants in `calibration.json`.  
- Achieved practical measurement accuracy against a commercial reference meter: approximately ±2.5% power error at 600 W load, and documented ±5% at low-current 65 W load.  
- Built complete IoT data path: MQTT telemetry (`energy/{device_id}/telemetry`), relay control topics, Flask ingestion, CSV history storage, and SSE live streaming.  
- Implemented runtime APIs for monitoring and control (`/stream`, `/history`, `/relay`) and integrated them into a working browser dashboard.  
- Trained and integrated three ML components from PLEGMA-derived datasets: LightGBM regression (R² 0.87), LightGBM ON/OFF classifier (94% accuracy), and Isolation Forest anomaly detector (89% precision).  
- Added explicit runtime safeguards: model-load checks and "insufficient history" error responses to avoid unreliable predictions.  
- Delivered end-to-end prototype traceability across firmware, backend, ML pipeline, and UI with repository-linked implementation evidence.

Keep this slide on screen during viva Q&A. Do not switch to a blank "Thank You" or "Questions?" slide.

