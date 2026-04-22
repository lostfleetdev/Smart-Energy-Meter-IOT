# 4-person workload matrix (revised deep split)

## role map you asked for

This split follows your exact structure:
        
1. One person owns backend completely.
2. One person owns IoT device side.
3. One person owns ML integration.
4. One person owns simpler scope (UI + architecture + documentation-facing tasks), but still with clear defendable outputs.

| Member | Role title | Core knowledge area | Primary ownership |
|---|---|---|---|
| Member 1 | Backend systems lead | Flask APIs, MQTT server-side integration, SSE, storage, deployment | Full backend runtime and API behavior |
| Member 2 | IoT hardware and firmware lead | ESP32 MicroPython, sensing, calibration, relay control | Device electronics + edge logic |
| Member 3 | ML integration lead | Time-series features, model training/export, runtime inference design | Model pipeline + serving contracts |
| Member 4 | UI and architecture documentation lead | Frontend UX basics, architecture diagrams, integration proof presentation | Dashboard polish + architecture communication |

## deep responsibilities by member

### Member 1: Backend systems lead (full backend owner)

**Core knowledge required**
- Flask route lifecycle, request/response handling, error paths.
- MQTT broker/client flow from server side.
- SSE streaming pattern and client update behavior.
- CSV persistence strategy, schema stability, and history retrieval.
- Basic deployment/service startup on cloud VM.

**Exact tasks**
- Own `backend/main.py` end to end.
- Implement and maintain MQTT ingestion path from `energy/{device_id}/telemetry`.
- Own REST/SSE interfaces: `/stream`, `/history`, `/relay`, `/stats`.
- Manage relay command publishing to `energy/{device_id}/relay/set` and state sync handling.
- Maintain backend-side validation and explicit failure responses (including model unavailable and insufficient history surface behavior).
- Keep the server boot/deploy flow reproducible (`deploy.sh`, dependency setup, service startup notes).

**Deliverables examiner can verify**
- Running backend demo showing live SSE updates without polling.
- Relay command round-trip from dashboard to device and confirmation state.
- Backend logs showing payload parse, storage write, and event broadcast.
- API screenshots or terminal calls proving each endpoint response.

**Defense responsibility**
- Explain why backend uses MQTT + REST + SSE together instead of one protocol.
- Explain how backend isolates ingestion, control, and visualization concerns.
- Explain what happens when device disconnects or payload is malformed.

---

### Member 2: IoT hardware and firmware lead

**Core knowledge required**
- ESP32 GPIO/ADC behavior and MicroPython runtime constraints.
- AC sensing with ZMPT101B and ACS712, including offset/noise handling.
- Calibration logic and known-load scaling.
- Relay safety boundaries and touch-input handling.

**Exact tasks**
- Own hardware wiring and validation for ESP32, sensors, OLED, relay, HLK-PM01, touch module.
- Own firmware runtime loop in `device/main.py` and network path in `device/main_v2.py`.
- Maintain 200-point sampling loop and RMS/power/energy computation path.
- Implement calibration workflow in `device/calibrate.py` and maintain `calibration.json` field consistency.
- Own OLED screen logic, short/long touch actions, and local fallback behavior during network issues.

**Deliverables examiner can verify**
- Assembled device and stable boot behavior.
- Live OLED values under no-load and known-load tests.
- Calibration before/after comparison against reference meter.
- Demonstration of local touch relay control and cloud-triggered relay response.

**Defense responsibility**
- Justify sensor selection and resulting low-current limitation.
- Explain calibration math in simple terms (offset, scale, noise floor).
- Explain timing and why one AC cycle with 200 samples is used.

---

### Member 3: ML integration lead

**Core knowledge required**
- Time-series feature engineering and leakage-safe train/test strategy.
- LightGBM regression/classification behavior.
- Isolation Forest and thresholding logic for anomalies.
- Model artifact packaging and runtime feature parity guarantees.

**Exact tasks**
- Own `ML/data_pipeline.py` and `ML/train_models.py`.
- Build and maintain appliance-wise features: lag, rolling windows, calendar terms, diff terms.
- Keep time-ordered split and threshold tuning logic for classifier reproducible.
- Export model artifacts with metadata and feature ordering constraints.
- Own `backend/ml_service.py` model-loading and inference contract with backend owner.
- Define behavior for cold-start/insufficient-history cases and ensure backend surfaces these clearly.

**Deliverables examiner can verify**
- Reproducible training output with metric tables (R2, MAE, accuracy, precision).
- Model artifact files and documented feature list.
- Runtime prediction/anomaly responses tied to incoming telemetry.
- Explanation of why appliance-specific modeling performed better than one global model.

**Defense responsibility**
- Defend model choice vs simpler threshold-only rules.
- Explain why anomaly detection combines Isolation Forest + Z-score.
- Explain confidence limits and drift/retraining requirement.

---

### Member 4: UI and architecture documentation lead (lighter but valid scope)

**Core knowledge required**
- HTML/CSS/JS dashboard composition and usability basics.
- Diagram-first communication for system architecture.
- Technical documentation structure for external viva review.

**Exact tasks**
- Own dashboard structure in `backend/static/index.html` with clear card layout, readability, and control grouping.
- Improve chart labeling, units, alert text clarity, and relay state visibility for examiner-friendly demo flow.
- Own architecture storytelling artifacts: block diagram, layered architecture, sequence flow, and module traceability mapping.
- Prepare presentation visual assets linking report sections to actual repository files.
- Own viva coordination material: slide order, transition cues, and contribution slide formatting.

**Deliverables examiner can verify**
- Dashboard screens that clearly expose live, historical, anomaly, and control panels.
- Architecture visuals that match actual implementation flow.
- Traceability matrix connecting each project claim to concrete files.
- Final slide deck consistency (no mismatched terminology between report, code, and slides).

**Defense responsibility**
- Explain UI choices made for operational clarity, not aesthetics alone.
- Explain architecture diagrams as implementation maps, not conceptual art.
- Explain how presentation evidence supports equal contribution claims.

## boundary rules to avoid overlap confusion

1. Backend code decisions are finalized by Member 1.  
2. Device sensing/calibration decisions are finalized by Member 2.  
3. Model/feature/inference decisions are finalized by Member 3.  
4. Presentation architecture visuals and dashboard communication decisions are finalized by Member 4.

## viva execution format for equal visibility

1. Each member gets one live artifact demo (not only verbal explanation).  
2. Each member answers one deep technical question from their owned area.  
3. Each member cites at least two concrete files while answering.

