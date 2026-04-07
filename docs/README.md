# Smart Energy Monitor — Project Documentation

> **Semester 6 Mini Project** | Per-appliance energy monitoring with ML anomaly detection

---

## 📚 Documentation Index

| Document | Description |
|----------|-------------|
| [**1. Project Overview**](./01-project-overview.md) | Introduction, problem statement, and solution |
| [**2. System Architecture**](./02-system-architecture.md) | High-level architecture and data flow |
| [**3. Hardware Design**](./03-hardware-design.md) | ESP32, sensors, circuit diagram, and pin mapping |
| [**4. Firmware Guide**](./04-firmware-guide.md) | MicroPython code, calibration, and main loop |
| [**5. Backend API**](./05-backend-api.md) | Flask server, MQTT, SSE streaming, and endpoints |
| [**6. ML Pipeline**](./06-ml-pipeline.md) | Data processing, model training, and anomaly detection |
| [**7. Dashboard UI**](./07-dashboard-ui.md) | Material Design 2 web interface |
| [**8. Deployment Guide**](./08-deployment-guide.md) | DigitalOcean setup and systemd services |
| [**9. API Reference**](./09-api-reference.md) | Complete REST API documentation |

---

## 🎯 Quick Links

### For Hardware Setup
- [Pin Configuration](./03-hardware-design.md#pin-configuration)
- [Sensor Calibration](./04-firmware-guide.md#calibration-process)
- [Circuit Diagram](./03-hardware-design.md#circuit-diagram)

### For Software Development
- [Backend Setup](./05-backend-api.md#quick-start)
- [ML Training](./06-ml-pipeline.md#training-models)
- [API Endpoints](./09-api-reference.md)

### For Deployment
- [Cloud Deployment](./08-deployment-guide.md#digitalocean-deployment)
- [Local Testing](./08-deployment-guide.md#local-development)

---

## 📐 Architecture Diagram

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                         SMART ENERGY MONITOR                                 │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  ┌────────────────┐     MQTT/WiFi      ┌──────────────────────────────────┐ │
│  │   ESP32 DEVICE │ ─────────────────► │        CLOUD BACKEND             │ │
│  │                │                     │                                  │ │
│  │  • ZMPT101B    │                     │  ┌──────────┐  ┌──────────────┐ │ │
│  │    (Voltage)   │                     │  │  NanoMQ  │  │   Flask +    │ │ │
│  │  • ACS712      │                     │  │  (MQTT   │──│   ML Service │ │ │
│  │    (Current)   │                     │  │  Broker) │  │              │ │ │
│  │  • SSD1306     │                     │  └──────────┘  └──────────────┘ │ │
│  │    (OLED)      │     Control Cmds    │                      │          │ │
│  │  • Relay       │ ◄───────────────────│                      ▼          │ │
│  │  • Touch       │                     │              ┌──────────────┐   │ │
│  └────────────────┘                     │              │  Dashboard   │   │ │
│                                          │              │  (Material)  │   │ │
│                                          │              └──────────────┘   │ │
│                                          └──────────────────────────────────┘ │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## 🗂️ Project Structure

```
IOT/
├── docs/                      # 📚 Documentation (you are here)
│   ├── README.md
│   ├── 01-project-overview.md
│   ├── 02-system-architecture.md
│   ├── 03-hardware-design.md
│   ├── 04-firmware-guide.md
│   ├── 05-backend-api.md
│   ├── 06-ml-pipeline.md
│   ├── 07-dashboard-ui.md
│   ├── 08-deployment-guide.md
│   ├── 09-api-reference.md
│   ├── images/                # Screenshots and photos
│   └── diagrams/              # Mermaid/PlantUML source files
│
├── device/                    # 🔌 ESP32 MicroPython firmware
│   ├── main.py
│   ├── calibrate.py
│   ├── calibration.json
│   ├── boot.py
│   └── ssd1306.py
│
├── backend/                   # 🖥️ Flask server + ML service
│   ├── main.py
│   ├── ml_service.py
│   ├── static/index.html
│   └── data.csv
│
├── ML/                        # 🧠 Machine Learning
│   ├── data_pipeline.py
│   ├── train_models.py
│   ├── train.ipynb
│   ├── dataset/
│   └── models/
│
├── Review-Report/             # 📝 Academic report (LaTeX)
│
├── deploy.sh                  # 🚀 Deployment script
└── README.md                  # Project README
```

---

## 👥 Team

| Name | Roll No |
|------|---------|
| Raman Bhise | B52 |
| Panchakshari Chakor | B53 |
| Rutika Parekar | B60 |
| Omkar Jagtap | B65 |

**Guide:** Prof. Dasganu Hake  
**Institution:** G H Raisoni College of Engineering and Management, Pune  
**Course:** Machine Learning & IoT (23UITELP3602)  
**Academic Year:** 2025-26

---

## 📄 License

Academic project — Semester 6, T.Y. B.Tech Information Technology
