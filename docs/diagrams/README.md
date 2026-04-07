# Diagrams

This folder contains Mermaid diagram source files that can be rendered in GitHub, VS Code, or any Mermaid-compatible viewer.

## Files

| File | Description |
|------|-------------|
| `system-architecture.mmd` | High-level system architecture |
| `data-flow.mmd` | Data flow through the system |
| `ml-pipeline.mmd` | Machine learning pipeline |
| `device-state-machine.mmd` | ESP32 firmware state machine |
| `sequence-diagram.mmd` | Component interaction sequence |

## Viewing Diagrams

### GitHub
Mermaid diagrams render automatically in `.md` files on GitHub.

### VS Code
Install the "Markdown Preview Mermaid Support" extension.

### Online
Use https://mermaid.live to paste and render diagrams.

---

## Quick Preview

### System Architecture

```mermaid
flowchart TB
    subgraph Device["ESP32 Device"]
        ZMPT[ZMPT101B<br>Voltage]
        ACS[ACS712<br>Current]
        ADC[12-bit ADC]
        MCU[ESP32 MCU]
        OLED[SSD1306<br>OLED]
        RELAY[Relay<br>Module]
        ZMPT --> ADC
        ACS --> ADC
        ADC --> MCU
        MCU --> OLED
        MCU --> RELAY
    end

    subgraph Cloud["Cloud Backend"]
        MQTT[NanoMQ<br>MQTT Broker]
        API[Flask<br>API Server]
        ML[ML Service<br>LightGBM]
        MQTT --> API
        API --> ML
    end

    subgraph Client["Web Client"]
        DASH[Dashboard<br>Material Design]
    end

    MCU -->|WiFi/MQTT| MQTT
    API -->|SSE| DASH
    DASH -->|REST| API
```

### Data Flow

```mermaid
flowchart LR
    A[AC Mains] --> B[ZMPT101B]
    A --> C[ACS712]
    B --> D[ADC GPIO35]
    C --> E[ADC GPIO34]
    D --> F[RMS Calc]
    E --> F
    F --> G[Power: V×I]
    G --> H[MQTT Publish]
    H --> I[Backend]
    I --> J[Anomaly Check]
    J --> K[SSE Stream]
    K --> L[Dashboard]
```

### ML Pipeline

```mermaid
flowchart TD
    A[Raw CSV Data] --> B[Data Cleaning]
    B --> C[Hourly Aggregation]
    C --> D[Feature Engineering]
    D --> E[Train/Test Split]
    
    E --> F[LightGBM<br>Regressor]
    E --> G[LightGBM<br>Classifier]
    E --> H[Isolation<br>Forest]
    
    F --> I[power_predictor.pkl]
    G --> J[classifier.pkl]
    H --> K[anomaly_v2.pkl]
```
