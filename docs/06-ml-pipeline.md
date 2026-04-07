# 6. ML Pipeline

## 6.1 Overview

The machine learning pipeline processes historical energy data to:

1. **Predict power consumption** — LightGBM regression
2. **Classify ON/OFF state** — LightGBM binary classifier
3. **Detect anomalies** — Isolation Forest + Z-score

---

## 6.2 Data Pipeline

### Dataset Structure

```
ML/
├── dataset/
│   ├── Clean_dataset/           # Raw data per house
│   │   ├── House_01/
│   │   │   ├── Electric_data/
│   │   │   │   ├── 202301.csv
│   │   │   │   ├── 202302.csv
│   │   │   │   └── ...
│   │   │   └── Environmental_data/
│   │   │       ├── 202301.csv
│   │   │       └── ...
│   │   ├── House_02/
│   │   └── ...
│   │
│   └── processed_v2/            # Processed hourly data
│       ├── ac_1_hourly_full.csv
│       ├── ac_1_hourly_active.csv
│       ├── ac_1_classification.csv
│       └── ...
│
├── models/                      # Trained models
│   ├── ac_1_power_predictor.pkl
│   ├── ac_1_anomaly_v2.pkl
│   ├── ac_1_classifier.pkl
│   └── training_summary_v2.json
│
├── data_pipeline.py             # Data processing script
├── train_models.py              # Model training script
└── train.ipynb                  # Jupyter notebook
```

### Pipeline Flow

```
┌─────────────────────────────────────────────────────────────────────────┐
│                         DATA PIPELINE FLOW                               │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                          │
│   STAGE 1: RAW DATA LOADING                                              │
│   ─────────────────────────                                              │
│                                                                          │
│   House_01/Electric_data/*.csv                                           │
│         │                                                                │
│         ▼                                                                │
│   ┌─────────────────────────────────────────────────────────────────┐   │
│   │  load_house_data(house_num)                                      │   │
│   │                                                                  │   │
│   │  • Concat all monthly CSV files                                  │   │
│   │  • Merge with environmental data                                 │   │
│   │  • Fix column typos (external_temparature)                       │   │
│   │  • Add house_id column                                           │   │
│   └─────────────────────────────────────────────────────────────────┘   │
│                                                                          │
│   STAGE 2: DATA CLEANING                                                 │
│   ──────────────────────                                                 │
│                                                                          │
│   ┌─────────────────────────────────────────────────────────────────┐   │
│   │  clean_appliance_data(df, appliance)                             │   │
│   │                                                                  │   │
│   │  • Remove rows with issues flag                                  │   │
│   │  • Drop missing target values                                    │   │
│   │  • Remove outliers (> 99.9th percentile)                         │   │
│   │  • Forward-fill small gaps (up to 6 readings)                    │   │
│   └─────────────────────────────────────────────────────────────────┘   │
│                                                                          │
│   STAGE 3: HOURLY AGGREGATION                                            │
│   ───────────────────────────                                            │
│                                                                          │
│   ┌─────────────────────────────────────────────────────────────────┐   │
│   │  create_hourly_aggregates(df, appliance)                         │   │
│   │                                                                  │   │
│   │  Aggregations:                                                   │   │
│   │  • {appliance}_mean, _max, _min, _std                            │   │
│   │  • is_on_sum, is_on_mean                                         │   │
│   │  • P_agg_mean, P_agg_max                                         │   │
│   │  • Environmental: temp, humidity                                 │   │
│   │                                                                  │   │
│   │  Quality filter: min 300 readings/hour (83% coverage)            │   │
│   └─────────────────────────────────────────────────────────────────┘   │
│                                                                          │
│   STAGE 4: FEATURE ENGINEERING                                           │
│   ────────────────────────────                                           │
│                                                                          │
│   ┌─────────────────────────────────────────────────────────────────┐   │
│   │  add_features(df, appliance)                                     │   │
│   │                                                                  │   │
│   │  Time features:                                                  │   │
│   │  • hour (0-23)                                                   │   │
│   │  • day_of_week (0-6)                                             │   │
│   │  • is_weekend (0/1)                                              │   │
│   │  • month, season, time_period                                    │   │
│   │                                                                  │   │
│   │  Lag features:                                                   │   │
│   │  • lag_1, lag_2, lag_3, lag_6, lag_12, lag_24                    │   │
│   │  • diff_1h, diff_24h                                             │   │
│   │                                                                  │   │
│   │  Rolling statistics:                                             │   │
│   │  • rolling_mean_6h, rolling_std_6h, rolling_mean_24h             │   │
│   └─────────────────────────────────────────────────────────────────┘   │
│                                                                          │
│   STAGE 5: OUTPUT DATASETS                                               │
│   ────────────────────────                                               │
│                                                                          │
│   ┌─────────────────────────────────────────────────────────────────┐   │
│   │  Output files per appliance:                                     │   │
│   │                                                                  │   │
│   │  • {appliance}_hourly_full.csv     → All hours                   │   │
│   │  • {appliance}_hourly_active.csv   → Active usage only           │   │
│   │  • {appliance}_classification.csv  → On/Off prediction target    │   │
│   └─────────────────────────────────────────────────────────────────┘   │
│                                                                          │
└─────────────────────────────────────────────────────────────────────────┘
```

---

## 6.3 Quality Houses

Selected houses with best data quality per appliance:

| Appliance | Houses | Reason |
|-----------|--------|--------|
| `ac_1` | 1, 3, 7, 2, 11 | Good continuous data, varied usage |
| `ac_2` | 3, 1, 7, 11 | Best 4 houses |
| `boiler` | 1, 4, 7, 9, 2 | Low missing, active usage |
| `fridge` | 1, 3, 7, 8, 6 | Continuous, need good data |
| `washing_machine` | 7, 12, 5, 3 | Intermittent but active |
| `dishwasher` | 12 | Only 1 quality house |

---

## 6.4 Feature Engineering

### Time Features

| Feature | Type | Values | Purpose |
|---------|------|--------|---------|
| `hour` | int | 0-23 | Hour of day |
| `day_of_week` | int | 0-6 | Day (Mon=0) |
| `is_weekend` | binary | 0/1 | Weekend flag |
| `month` | int | 1-12 | Month |
| `season` | int | 0-3 | Winter/Spring/Summer/Fall |
| `time_period` | int | 0-3 | Night/Morning/Afternoon/Evening |

### Lag Features

| Feature | Formula | Purpose |
|---------|---------|---------|
| `lag_1` | `power[t-1]` | Previous hour |
| `lag_24` | `power[t-24]` | Same hour yesterday |
| `diff_1h` | `power[t] - power[t-1]` | Hourly change |
| `diff_24h` | `power[t] - power[t-24]` | Daily change |

### Rolling Statistics

| Feature | Window | Purpose |
|---------|--------|---------|
| `rolling_mean_6h` | 6 hours | Short-term average |
| `rolling_std_6h` | 6 hours | Short-term variability |
| `rolling_mean_24h` | 24 hours | Daily average |

---

## 6.5 Model Training

### Power Predictor (LightGBM Regression)

```python
params = {
    "objective": "regression",
    "metric": "mae",
    "boosting_type": "gbdt",
    "num_leaves": 63,
    "learning_rate": 0.03,
    "feature_fraction": 0.8,
    "bagging_fraction": 0.8,
    "bagging_freq": 5,
    "min_child_samples": 20,
    "reg_alpha": 0.1,
    "reg_lambda": 0.1,
}

model = lgb.train(
    params,
    train_data,
    num_boost_round=1000,
    valid_sets=[valid_data],
    callbacks=[lgb.early_stopping(stopping_rounds=50)]
)
```

### On/Off Classifier

```python
params = {
    "objective": "binary",
    "metric": "auc",
    "boosting_type": "gbdt",
    "num_leaves": 31,
    "learning_rate": 0.05,
    "feature_fraction": 0.8,
    "scale_pos_weight": pos_weight,  # Handle class imbalance
}
```

### Anomaly Detector (Isolation Forest)

```python
model = IsolationForest(
    n_estimators=200,
    contamination=0.02,  # Expect 2% anomalies
    random_state=42,
    n_jobs=-1
)
```

---

## 6.6 Model Performance

### Power Prediction Results

| Appliance | MAE (W) | MAE % | R² | Dataset |
|-----------|---------|-------|-----|---------|
| ac_1 | 85.2 | 12.3% | 0.876 | hourly_active.csv |
| ac_2 | 92.1 | 14.1% | 0.842 | hourly_active.csv |
| boiler | 156.3 | 18.7% | 0.723 | hourly_active.csv |
| fridge | 8.4 | 9.2% | 0.912 | hourly_full.csv |
| washing_machine | 45.6 | 22.1% | 0.654 | hourly_active.csv |
| dishwasher | 12.3 | 15.4% | 0.789 | hourly_full.csv |

### On/Off Classification Results

| Appliance | Accuracy | Precision | Recall | F1 | AUC |
|-----------|----------|-----------|--------|-----|-----|
| ac_1 | 0.923 | 0.856 | 0.812 | 0.834 | 0.945 |
| ac_2 | 0.908 | 0.823 | 0.789 | 0.806 | 0.932 |
| boiler | 0.956 | 0.912 | 0.878 | 0.895 | 0.967 |
| fridge | 0.978 | 0.945 | 0.934 | 0.940 | 0.989 |
| washing_machine | 0.887 | 0.756 | 0.698 | 0.726 | 0.891 |

### Anomaly Detection Results

| Appliance | Anomaly % | Normal Mean (W) | Threshold High (W) |
|-----------|-----------|-----------------|-------------------|
| ac_1 | 2.1% | 450.2 | 1250 |
| fridge | 1.8% | 85.4 | 220 |
| boiler | 2.3% | 1200.5 | 3500 |

---

## 6.7 Feature Importance

### Top Features for Power Prediction

| Rank | Feature | Importance |
|------|---------|------------|
| 1 | lag_1 | 45,234 |
| 2 | rolling_mean_6h | 32,156 |
| 3 | lag_24 | 28,912 |
| 4 | hour | 18,456 |
| 5 | rolling_std_6h | 12,345 |

---

## 6.8 Running the Pipeline

### Data Processing

```bash
cd ML

# Process all appliances
uv run python data_pipeline.py
# Or: python data_pipeline.py

# Output:
# Processing: AC_1
#   House 1...
#     Raw rows: 345600
#     Hourly rows: 8520
# ...
# PIPELINE COMPLETE
# Output directory: dataset/processed_v2
```

### Model Training

```bash
# Train all models
uv run python train_models.py
# Or: python train_models.py

# Output:
# ══════════════════════════════════════════════════════════════
# POWER PREDICTION: AC_1
# ══════════════════════════════════════════════════════════════
# Dataset: ac_1_hourly_active.csv, 5234 rows
# Features: 15
# Target: ac_1_mean
# ...
# Results:
#   MAE:  85.2 W (12.3% of mean)
#   RMSE: 112.4 W
#   R²:   0.876
# 
# Saved: models/ac_1_power_predictor.pkl
```

---

## 6.9 Model Files

### Structure

```python
# Power predictor (.pkl)
{
    "model": lightgbm.Booster,
    "feature_names": ["hour", "day_of_week", ...],
    "metrics": {...},
    "importance": {...}
}

# Anomaly detector (.pkl)
{
    "model": IsolationForest,
    "scaler": StandardScaler,
    "feature_names": [...],
    "stats": {
        "mean": 450.2,
        "std": 120.5,
        "threshold_high": 811.7
    }
}

# Classifier (.pkl)
{
    "model": lightgbm.Booster,
    "feature_names": [...],
    "threshold": 0.45,
    "metrics": {...}
}
```

---

## 6.10 Inference in Backend

```python
def predict_power(self, appliance: str) -> Optional[dict]:
    """Predict power consumption for next hour."""
    if appliance not in self.models:
        return {"error": f"No model for {appliance}"}

    features = self.get_features(appliance)
    if not features:
        return {"error": "Insufficient history (need 3+ readings)"}

    model = self.models[appliance]
    feature_order = [
        "hour", "day_of_week", "is_weekend", "lag_1h", "lag_24h",
        "diff_1h", "diff_24h", "rolling_mean_6h", "rolling_std_6h"
    ]

    X = [[features[f] for f in feature_order]]

    prediction = model.predict(X)[0]
    return {
        "appliance": appliance,
        "predicted_power": round(max(0, prediction), 2),
        "unit": "watts",
        "timestamp": datetime.now().isoformat(),
    }
```

---

## 6.11 Model Diagram

```
┌─────────────────────────────────────────────────────────────────────────┐
│                         ML MODEL ARCHITECTURE                            │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                          │
│                         INPUT FEATURES                                   │
│   ┌─────────────────────────────────────────────────────────────────┐   │
│   │  Time: hour, day_of_week, is_weekend                             │   │
│   │  Lag:  lag_1h, lag_24h                                           │   │
│   │  Diff: diff_1h, diff_24h                                         │   │
│   │  Roll: rolling_mean_6h, rolling_std_6h                           │   │
│   └───────────────────────────┬─────────────────────────────────────┘   │
│                               │                                          │
│                               ▼                                          │
│   ┌─────────────────────────────────────────────────────────────────┐   │
│   │                        MODELS                                    │   │
│   │                                                                  │   │
│   │   ┌───────────────┐  ┌───────────────┐  ┌───────────────┐       │   │
│   │   │   LightGBM    │  │   LightGBM    │  │  IsoForest +  │       │   │
│   │   │  Regressor    │  │  Classifier   │  │   Z-Score     │       │   │
│   │   │               │  │               │  │               │       │   │
│   │   │ Power (W)     │  │ On/Off (0/1)  │  │ Anomaly Flag  │       │   │
│   │   └───────┬───────┘  └───────┬───────┘  └───────┬───────┘       │   │
│   │           │                  │                  │               │   │
│   │           ▼                  ▼                  ▼               │   │
│   │      ┌─────────┐        ┌─────────┐        ┌─────────┐          │   │
│   │      │ 534.7 W │        │ ON 85%  │        │ Normal  │          │   │
│   │      └─────────┘        └─────────┘        └─────────┘          │   │
│   │                                                                  │   │
│   └─────────────────────────────────────────────────────────────────┘   │
│                                                                          │
└─────────────────────────────────────────────────────────────────────────┘
```

---

## Next: [Dashboard UI →](./07-dashboard-ui.md)
