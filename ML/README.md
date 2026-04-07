# ML Module - Smart Energy Monitor

Power consumption prediction and anomaly detection for household appliances.

## Structure

```
ML/
├── data_pipeline.py       # Data cleaning and preprocessing
├── train_models.py        # Model training script
├── dataset/
│   ├── Clean_Dataset/     # Raw data (13 houses)
│   └── processed/         # Cleaned hourly/daily CSVs
└── models/                # Trained models (.pkl files)
```

## Supported Appliances

| Appliance | Power Predictor | Anomaly Detector | On/Off Classifier |
|-----------|-----------------|------------------|-------------------|
| ac_1 | ✅ R²=0.98 | ✅ | ✅ |
| ac_2 | ✅ R²=0.90 | ✅ | ✅ |
| boiler | ✅ R²=0.99 | ✅ | ✅ |
| fridge | ✅ R²=0.99 | ✅ | ✅ |
| washing_machine | ✅ R²=0.98 | ✅ | ✅ |
| dishwasher | ✅ R²=0.93 | ✅ | ❌ |

## Usage

### 1. Process Data
```bash
cd ML
uv run python data_pipeline.py
```

### 2. Train Models
```bash
uv run python train_models.py
```

### 3. Use in Backend
Models are automatically loaded by `backend/ml_service.py`.

## API Endpoints

The backend exposes these ML endpoints:

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/ml/info` | GET | Model info |
| `/ml/appliances` | GET | List appliances |
| `/ml/predict/<appliance>` | GET | Predict power |
| `/ml/predict-onoff/<appliance>` | GET | Predict ON/OFF |
| `/ml/anomaly/<appliance>` | POST | Detect anomaly |
| `/ml/reading/<appliance>` | POST | Add reading |
| `/ml/history/<appliance>` | GET | Get history |
| `/ml/simulate` | POST | Simulate readings |

## Model Details

- **Power Prediction**: LightGBM regression with temporal features
- **On/Off Classification**: LightGBM with class weighting for imbalance
- **Anomaly Detection**: Isolation Forest + statistical Z-score
