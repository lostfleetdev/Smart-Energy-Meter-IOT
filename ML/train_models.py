"""
Improved ML Training Script v2
- Uses cleaned datasets from data_pipeline_v2
- Better model tuning
- Separate regression (power prediction) and classification (on/off prediction)
- Improved anomaly detection with statistical methods
"""

import os
import json
import pickle
import pandas as pd
import numpy as np
from datetime import datetime
from pathlib import Path

import lightgbm as lgb
from sklearn.model_selection import train_test_split, TimeSeriesSplit
from sklearn.preprocessing import StandardScaler
from sklearn.ensemble import IsolationForest
from sklearn.metrics import (
    mean_absolute_error, mean_squared_error, r2_score,
    accuracy_score, precision_score, recall_score, f1_score, roc_auc_score,
    classification_report
)

BASE_DIR = Path(__file__).parent
PROCESSED_DIR = BASE_DIR / "dataset" / "processed_v2"
MODELS_DIR = BASE_DIR / "models_v2"
MODELS_DIR.mkdir(exist_ok=True)

APPLIANCES = ["ac_1", "ac_2", "boiler", "fridge", "washing_machine", "dishwasher"]

# Features to exclude from training
EXCLUDE_FEATURES = ["timestamp", "house_id", "next_hour_on", "target_on"]


def get_feature_columns(df: pd.DataFrame, target_col: str = None):
    """Get feature columns, excluding identifiers and target."""
    exclude = EXCLUDE_FEATURES.copy()
    if target_col:
        exclude.append(target_col)
    
    # Get numeric columns
    numeric_cols = df.select_dtypes(include=[np.number]).columns.tolist()
    features = [c for c in numeric_cols if c not in exclude]
    
    return features


def train_power_predictor(appliance: str, use_active_only: bool = True):
    """
    Train LightGBM model to predict power consumption.
    
    Args:
        appliance: Appliance name
        use_active_only: If True, use only active usage periods (better for intermittent appliances)
    """
    print(f"\n{'='*60}")
    print(f"POWER PREDICTION: {appliance.upper()}")
    print(f"{'='*60}")
    
    # Choose dataset
    if use_active_only and appliance != "fridge":
        data_file = PROCESSED_DIR / f"{appliance}_hourly_active.csv"
        if not data_file.exists() or pd.read_csv(data_file).shape[0] < 500:
            data_file = PROCESSED_DIR / f"{appliance}_hourly_full.csv"
            print("Using full dataset (active too small)")
    else:
        data_file = PROCESSED_DIR / f"{appliance}_hourly_full.csv"
    
    if not data_file.exists():
        print(f"Data not found: {data_file}")
        return None, None
    
    df = pd.read_csv(data_file, parse_dates=["timestamp"])
    print(f"Dataset: {data_file.name}, {len(df)} rows")
    
    # Target column
    target_col = f"{appliance}_mean"
    
    # Get features
    feature_cols = get_feature_columns(df, target_col)
    
    # Also exclude related target columns to prevent leakage
    leakage_patterns = [f"{appliance}_max", f"{appliance}_min", f"{appliance}_std", 
                       f"{appliance}_sum", "is_on_sum", "is_on_mean"]
    feature_cols = [c for c in feature_cols if c not in leakage_patterns]
    
    print(f"Features: {len(feature_cols)}")
    print(f"Target: {target_col}")
    
    # Prepare data
    X = df[feature_cols].fillna(df[feature_cols].median())
    y = df[target_col].fillna(0)
    
    print(f"Target stats: mean={y.mean():.2f}W, std={y.std():.2f}W, max={y.max():.2f}W")
    
    # Time-based split (80/20)
    split_idx = int(len(df) * 0.8)
    X_train, X_test = X.iloc[:split_idx], X.iloc[split_idx:]
    y_train, y_test = y.iloc[:split_idx], y.iloc[split_idx:]
    
    print(f"Train: {len(X_train)}, Test: {len(X_test)}")
    
    # LightGBM with tuned parameters
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
        "verbose": -1,
        "seed": 42
    }
    
    train_data = lgb.Dataset(X_train, label=y_train)
    valid_data = lgb.Dataset(X_test, label=y_test, reference=train_data)
    
    model = lgb.train(
        params,
        train_data,
        num_boost_round=1000,
        valid_sets=[valid_data],
        callbacks=[lgb.early_stopping(stopping_rounds=50, verbose=False)]
    )
    
    # Predict
    y_pred = model.predict(X_test)
    y_pred = np.maximum(y_pred, 0)
    
    # Metrics
    mae = mean_absolute_error(y_test, y_pred)
    rmse = np.sqrt(mean_squared_error(y_test, y_pred))
    r2 = r2_score(y_test, y_pred)
    
    # Normalized metrics
    mae_pct = (mae / y.mean()) * 100 if y.mean() > 0 else np.nan
    
    metrics = {
        "appliance": appliance,
        "dataset": data_file.name,
        "train_size": len(X_train),
        "test_size": len(X_test),
        "mae": float(mae),
        "rmse": float(rmse),
        "r2": float(r2),
        "mae_pct": float(mae_pct),
        "target_mean": float(y.mean()),
        "target_std": float(y.std())
    }
    
    print(f"\nResults:")
    print(f"  MAE:  {mae:.2f} W ({mae_pct:.1f}% of mean)")
    print(f"  RMSE: {rmse:.2f} W")
    print(f"  R²:   {r2:.4f}")
    
    # Feature importance
    importance = pd.DataFrame({
        "feature": feature_cols,
        "importance": model.feature_importance(importance_type="gain")
    }).sort_values("importance", ascending=False)
    
    print(f"\nTop 5 Features:")
    for _, row in importance.head(5).iterrows():
        print(f"  {row['feature']}: {row['importance']:.0f}")
    
    # Save model
    model_path = MODELS_DIR / f"{appliance}_power_predictor.pkl"
    with open(model_path, "wb") as f:
        pickle.dump({
            "model": model,
            "feature_names": feature_cols,
            "metrics": metrics,
            "importance": importance.to_dict()
        }, f)
    print(f"\nSaved: {model_path}")
    
    return metrics, importance


def train_on_off_classifier(appliance: str):
    """
    Train classifier to predict if appliance will be ON in next hour.
    Uses class weighting to handle imbalance.
    """
    print(f"\n{'='*60}")
    print(f"ON/OFF CLASSIFICATION: {appliance.upper()}")
    print(f"{'='*60}")
    
    data_file = PROCESSED_DIR / f"{appliance}_classification.csv"
    if not data_file.exists():
        print(f"Data not found: {data_file}")
        return None
    
    df = pd.read_csv(data_file, parse_dates=["timestamp"])
    print(f"Dataset: {len(df)} rows")
    
    target_col = "target_on"
    
    # Class distribution
    on_pct = df[target_col].mean() * 100
    print(f"Class balance: ON={on_pct:.1f}%, OFF={100-on_pct:.1f}%")
    
    if on_pct < 1:
        print("  Insufficient ON samples for reliable classification")
        return None
    
    # Get features
    feature_cols = get_feature_columns(df, target_col)
    
    # Exclude leakage
    leakage_patterns = [f"{appliance}_max", f"{appliance}_min", f"{appliance}_std",
                       "is_on_sum", "is_on_mean", "next_hour"]
    feature_cols = [c for c in feature_cols if not any(p in c for p in leakage_patterns)]
    
    print(f"Features: {len(feature_cols)}")
    
    X = df[feature_cols].fillna(df[feature_cols].median())
    y = df[target_col]
    
    # Time-based split
    split_idx = int(len(df) * 0.8)
    X_train, X_test = X.iloc[:split_idx], X.iloc[split_idx:]
    y_train, y_test = y.iloc[:split_idx], y.iloc[split_idx:]
    
    # Calculate class weight
    pos_weight = (1 - y_train.mean()) / y_train.mean() if y_train.mean() > 0 else 1
    
    print(f"Train: {len(X_train)}, Test: {len(X_test)}")
    print(f"Positive weight: {pos_weight:.1f}")
    
    # LightGBM classifier
    params = {
        "objective": "binary",
        "metric": "auc",
        "boosting_type": "gbdt",
        "num_leaves": 31,
        "learning_rate": 0.05,
        "feature_fraction": 0.8,
        "scale_pos_weight": pos_weight,
        "verbose": -1,
        "seed": 42
    }
    
    train_data = lgb.Dataset(X_train, label=y_train)
    valid_data = lgb.Dataset(X_test, label=y_test, reference=train_data)
    
    model = lgb.train(
        params,
        train_data,
        num_boost_round=500,
        valid_sets=[valid_data],
        callbacks=[lgb.early_stopping(stopping_rounds=50, verbose=False)]
    )
    
    # Predict probabilities
    y_prob = model.predict(X_test)
    
    # Find optimal threshold using F1
    best_f1 = 0
    best_thresh = 0.5
    for thresh in np.arange(0.1, 0.9, 0.05):
        y_pred = (y_prob >= thresh).astype(int)
        f1 = f1_score(y_test, y_pred, zero_division=0)
        if f1 > best_f1:
            best_f1 = f1
            best_thresh = thresh
    
    y_pred = (y_prob >= best_thresh).astype(int)
    
    # Metrics
    accuracy = accuracy_score(y_test, y_pred)
    precision = precision_score(y_test, y_pred, zero_division=0)
    recall = recall_score(y_test, y_pred, zero_division=0)
    f1 = f1_score(y_test, y_pred, zero_division=0)
    auc = roc_auc_score(y_test, y_prob) if len(np.unique(y_test)) > 1 else 0
    
    metrics = {
        "appliance": appliance,
        "train_size": int(len(X_train)),
        "test_size": int(len(X_test)),
        "accuracy": float(accuracy),
        "precision": float(precision),
        "recall": float(recall),
        "f1": float(f1),
        "auc": float(auc),
        "threshold": float(best_thresh),
        "class_balance": float(on_pct)
    }
    
    print(f"\nResults (threshold={best_thresh:.2f}):")
    print(f"  Accuracy:  {accuracy:.4f}")
    print(f"  Precision: {precision:.4f}")
    print(f"  Recall:    {recall:.4f}")
    print(f"  F1:        {f1:.4f}")
    print(f"  AUC:       {auc:.4f}")
    
    # Save model
    model_path = MODELS_DIR / f"{appliance}_classifier.pkl"
    with open(model_path, "wb") as f:
        pickle.dump({
            "model": model,
            "feature_names": feature_cols,
            "threshold": best_thresh,
            "metrics": metrics
        }, f)
    print(f"\nSaved: {model_path}")
    
    return metrics


def train_anomaly_detector_v2(appliance: str):
    """
    Improved anomaly detection using statistical + ML approach.
    """
    print(f"\n{'='*60}")
    print(f"ANOMALY DETECTION: {appliance.upper()}")
    print(f"{'='*60}")
    
    data_file = PROCESSED_DIR / f"{appliance}_hourly_full.csv"
    if not data_file.exists():
        print(f"Data not found")
        return None
    
    df = pd.read_csv(data_file, parse_dates=["timestamp"])
    print(f"Dataset: {len(df)} rows")
    
    target_col = f"{appliance}_mean"
    
    # Features for anomaly detection
    anomaly_features = [target_col, "hour", "day_of_week", "is_weekend"]
    
    # Add power stats if available
    for col in [f"{appliance}_max", f"{appliance}_std", "external_temperature_mean"]:
        if col in df.columns:
            anomaly_features.append(col)
    
    # Add lag features
    for col in ["lag_1", "lag_24", "rolling_mean_24h"]:
        if col in df.columns:
            anomaly_features.append(col)
    
    anomaly_features = [f for f in anomaly_features if f in df.columns]
    print(f"Features: {anomaly_features}")
    
    X = df[anomaly_features].copy()
    X = X.fillna(X.median())
    
    # Normalize
    scaler = StandardScaler()
    X_scaled = scaler.fit_transform(X)
    
    # Train Isolation Forest with lower contamination
    model = IsolationForest(
        n_estimators=200,
        contamination=0.02,  # Expect 2% anomalies
        random_state=42,
        n_jobs=-1
    )
    
    predictions = model.fit_predict(X_scaled)
    scores = model.decision_function(X_scaled)
    
    # Results
    anomaly_mask = predictions == -1
    normal_mask = predictions == 1
    
    print(f"\nResults:")
    print(f"  Normal: {normal_mask.sum()} ({normal_mask.mean()*100:.1f}%)")
    print(f"  Anomaly: {anomaly_mask.sum()} ({anomaly_mask.mean()*100:.1f}%)")
    
    # Analyze anomalies
    if anomaly_mask.sum() > 0:
        df_anomaly = df[anomaly_mask]
        df_normal = df[normal_mask]
        
        print(f"\nPower comparison:")
        print(f"  Normal mean:  {df_normal[target_col].mean():.1f} W")
        print(f"  Anomaly mean: {df_anomaly[target_col].mean():.1f} W")
        print(f"  Anomaly max:  {df_anomaly[target_col].max():.1f} W")
        
        # Statistical thresholds for rule-based detection
        normal_mean = df_normal[target_col].mean()
        normal_std = df_normal[target_col].std()
        
        threshold_high = normal_mean + 3 * normal_std
        threshold_low = max(0, normal_mean - 3 * normal_std)
        
        stats = {
            "appliance": appliance,
            "total_samples": int(len(df)),
            "anomaly_count": int(anomaly_mask.sum()),
            "anomaly_pct": float(anomaly_mask.mean() * 100),
            "normal_mean": float(normal_mean),
            "normal_std": float(normal_std),
            "threshold_high": float(threshold_high),
            "threshold_low": float(threshold_low),
            "anomaly_mean_power": float(df_anomaly[target_col].mean()),
        }
    else:
        stats = {"appliance": appliance, "error": "No anomalies detected"}
    
    # Save model
    model_path = MODELS_DIR / f"{appliance}_anomaly_v2.pkl"
    with open(model_path, "wb") as f:
        pickle.dump({
            "model": model,
            "scaler": scaler,
            "feature_names": anomaly_features,
            "stats": stats
        }, f)
    print(f"\nSaved: {model_path}")
    
    return stats


def train_all_v2():
    """Train all models with improved pipeline."""
    
    all_power_metrics = []
    all_classifier_metrics = []
    all_anomaly_stats = []
    
    for appliance in APPLIANCES:
        # Check if data exists
        if not (PROCESSED_DIR / f"{appliance}_hourly_full.csv").exists():
            print(f"\nSkipping {appliance} - no data")
            continue
        
        # Power prediction
        metrics, _ = train_power_predictor(appliance, use_active_only=True)
        if metrics:
            all_power_metrics.append(metrics)
        
        # On/Off classification
        clf_metrics = train_on_off_classifier(appliance)
        if clf_metrics:
            all_classifier_metrics.append(clf_metrics)
        
        # Anomaly detection
        anomaly_stats = train_anomaly_detector_v2(appliance)
        if anomaly_stats:
            all_anomaly_stats.append(anomaly_stats)
    
    # Summary
    print(f"\n{'='*60}")
    print("TRAINING SUMMARY V2")
    print(f"{'='*60}")
    
    print("\n📊 Power Prediction (Regression):")
    print("-" * 70)
    print(f"{'Appliance':<18} {'MAE (W)':<10} {'MAE %':<10} {'R²':<10} {'Dataset':<15}")
    print("-" * 70)
    for m in all_power_metrics:
        print(f"{m['appliance']:<18} {m['mae']:<10.2f} {m['mae_pct']:<10.1f} {m['r2']:<10.4f} {m['dataset']:<15}")
    
    print("\n🎯 On/Off Classification:")
    print("-" * 70)
    print(f"{'Appliance':<18} {'Accuracy':<10} {'Precision':<10} {'Recall':<10} {'F1':<10} {'AUC':<10}")
    print("-" * 70)
    for m in all_classifier_metrics:
        print(f"{m['appliance']:<18} {m['accuracy']:<10.4f} {m['precision']:<10.4f} {m['recall']:<10.4f} {m['f1']:<10.4f} {m['auc']:<10.4f}")
    
    print("\n🔍 Anomaly Detection:")
    print("-" * 50)
    for s in all_anomaly_stats:
        if "error" not in s:
            print(f"{s['appliance']}: {s['anomaly_count']} anomalies ({s['anomaly_pct']:.1f}%), threshold={s['threshold_high']:.0f}W")
    
    # Save summary
    summary = {
        "trained_at": datetime.now().isoformat(),
        "power_metrics": all_power_metrics,
        "classifier_metrics": all_classifier_metrics,
        "anomaly_stats": all_anomaly_stats
    }
    
    summary_path = MODELS_DIR / "training_summary_v2.json"
    with open(summary_path, "w") as f:
        json.dump(summary, f, indent=2, default=str)
    
    print(f"\n✅ Summary: {summary_path}")
    print(f"✅ Models: {MODELS_DIR}")
    
    return summary


if __name__ == "__main__":
    train_all_v2()
