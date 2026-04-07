"""
ML Prediction Service
=====================
Provides ML-powered predictions and anomaly detection for appliances.
Loads trained models and exposes prediction functions.
"""

import os
import pickle
import json
from pathlib import Path
from datetime import datetime
from collections import deque
from typing import Optional

# Path to ML models (relative to project root)
PROJECT_ROOT = Path(__file__).parent.parent
MODELS_DIR = PROJECT_ROOT / "ML" / "models"

# Appliances supported
APPLIANCES = ["ac_1", "ac_2", "boiler", "fridge", "washing_machine", "dishwasher"]

# Power thresholds for ON detection (in Watts)
ON_THRESHOLDS = {
    "ac_1": 100,
    "ac_2": 100,
    "boiler": 200,
    "fridge": 30,
    "washing_machine": 50,
    "dishwasher": 20,
}


class MLService:
    """ML Service for power prediction and anomaly detection."""

    def __init__(self):
        self.models = {}
        self.anomaly_models = {}
        self.classifiers = {}
        self.history = {app: deque(maxlen=48) for app in APPLIANCES}  # 48 hours
        self.load_models()

    def load_models(self):
        """Load all trained models."""
        if not MODELS_DIR.exists():
            print(f"[ML] Models directory not found: {MODELS_DIR}")
            return

        for appliance in APPLIANCES:
            # Load power predictor
            predictor_path = MODELS_DIR / f"{appliance}_power_predictor.pkl"
            if predictor_path.exists():
                with open(predictor_path, "rb") as f:
                    self.models[appliance] = pickle.load(f)
                print(f"[ML] Loaded predictor: {appliance}")

            # Load anomaly detector
            anomaly_path = MODELS_DIR / f"{appliance}_anomaly_v2.pkl"
            if anomaly_path.exists():
                with open(anomaly_path, "rb") as f:
                    self.anomaly_models[appliance] = pickle.load(f)
                print(f"[ML] Loaded anomaly detector: {appliance}")

            # Load classifier (on/off prediction)
            classifier_path = MODELS_DIR / f"{appliance}_classifier.pkl"
            if classifier_path.exists():
                with open(classifier_path, "rb") as f:
                    self.classifiers[appliance] = pickle.load(f)
                print(f"[ML] Loaded classifier: {appliance}")

        # Load training summary
        summary_path = MODELS_DIR / "training_summary_v2.json"
        if summary_path.exists():
            with open(summary_path, "r") as f:
                self.training_summary = json.load(f)
        else:
            self.training_summary = {}

    def add_reading(self, appliance: str, power: float, timestamp: Optional[datetime] = None):
        """Add a power reading to history for an appliance."""
        if appliance not in APPLIANCES:
            return False

        ts = timestamp or datetime.now()
        reading = {
            "timestamp": ts.isoformat(),
            "hour": ts.hour,
            "day_of_week": ts.weekday(),
            "is_weekend": 1 if ts.weekday() >= 5 else 0,
            "power": power,
            "is_on": 1 if power > ON_THRESHOLDS.get(appliance, 50) else 0,
        }
        self.history[appliance].append(reading)
        return True

    def get_features(self, appliance: str) -> Optional[dict]:
        """Extract features from history for prediction."""
        history = self.history[appliance]
        if len(history) < 3:
            return None

        current = history[-1]
        prev_1h = history[-2] if len(history) >= 2 else current
        prev_24h = history[-24] if len(history) >= 24 else current

        # Calculate rolling statistics
        powers = [r["power"] for r in history]
        recent_powers = powers[-6:] if len(powers) >= 6 else powers  # Last 6 hours

        features = {
            "hour": current["hour"],
            "day_of_week": current["day_of_week"],
            "is_weekend": current["is_weekend"],
            "lag_1h": prev_1h["power"],
            "lag_24h": prev_24h["power"],
            "diff_1h": current["power"] - prev_1h["power"],
            "diff_24h": current["power"] - prev_24h["power"],
            "rolling_mean_6h": sum(recent_powers) / len(recent_powers),
            "rolling_std_6h": (
                (sum((p - sum(recent_powers) / len(recent_powers)) ** 2 for p in recent_powers) / len(recent_powers)) ** 0.5
                if len(recent_powers) > 1 else 0
            ),
        }
        return features

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

        try:
            prediction = model.predict(X)[0]
            return {
                "appliance": appliance,
                "predicted_power": round(max(0, prediction), 2),
                "unit": "watts",
                "features_used": features,
                "timestamp": datetime.now().isoformat(),
            }
        except Exception as e:
            return {"error": str(e)}

    def predict_on_off(self, appliance: str) -> Optional[dict]:
        """Predict if appliance will be ON in next hour."""
        if appliance not in self.classifiers:
            return {"error": f"No classifier for {appliance}"}

        features = self.get_features(appliance)
        if not features:
            return {"error": "Insufficient history"}

        classifier = self.classifiers[appliance]
        feature_order = [
            "hour", "day_of_week", "is_weekend", "lag_1h", "lag_24h",
            "diff_1h", "diff_24h", "rolling_mean_6h", "rolling_std_6h"
        ]

        X = [[features[f] for f in feature_order]]

        try:
            prediction = classifier.predict(X)[0]
            proba = classifier.predict_proba(X)[0]
            return {
                "appliance": appliance,
                "will_be_on": bool(prediction),
                "confidence": round(max(proba) * 100, 1),
                "timestamp": datetime.now().isoformat(),
            }
        except Exception as e:
            return {"error": str(e)}

    def detect_anomaly(self, appliance: str, power: float) -> Optional[dict]:
        """Detect if current power reading is anomalous."""
        if appliance not in self.anomaly_models:
            return {"error": f"No anomaly model for {appliance}"}

        model_data = self.anomaly_models[appliance]
        iso_forest = model_data["model"]
        stats = model_data["stats"]

        # Simple Z-score check
        z_score = abs(power - stats["mean"]) / max(stats["std"], 1)
        is_statistical_anomaly = z_score > 3

        # Isolation Forest check
        features = self.get_features(appliance)
        is_ml_anomaly = False

        if features:
            feature_order = [
                "hour", "day_of_week", "is_weekend", "lag_1h", "lag_24h",
                "diff_1h", "diff_24h", "rolling_mean_6h", "rolling_std_6h"
            ]
            X = [[features[f] for f in feature_order]]
            try:
                prediction = iso_forest.predict(X)[0]
                is_ml_anomaly = prediction == -1
            except:
                pass

        is_anomaly = is_statistical_anomaly or is_ml_anomaly
        reason = []
        if is_statistical_anomaly:
            reason.append(f"Z-score {z_score:.1f} > 3")
        if is_ml_anomaly:
            reason.append("ML model flagged")

        return {
            "appliance": appliance,
            "power": power,
            "is_anomaly": is_anomaly,
            "z_score": round(z_score, 2),
            "reason": reason if is_anomaly else None,
            "stats": {
                "mean": round(stats["mean"], 2),
                "std": round(stats["std"], 2),
                "threshold_high": round(stats["mean"] + 3 * stats["std"], 2),
            },
            "timestamp": datetime.now().isoformat(),
        }

    def get_all_predictions(self) -> dict:
        """Get predictions for all appliances with sufficient data."""
        results = {}
        for appliance in APPLIANCES:
            if len(self.history[appliance]) >= 3:
                results[appliance] = {
                    "power_prediction": self.predict_power(appliance),
                    "on_off_prediction": self.predict_on_off(appliance) if appliance in self.classifiers else None,
                }
        return results

    def get_model_info(self) -> dict:
        """Get information about loaded models."""
        return {
            "models_dir": str(MODELS_DIR),
            "power_predictors": list(self.models.keys()),
            "anomaly_detectors": list(self.anomaly_models.keys()),
            "classifiers": list(self.classifiers.keys()),
            "history_sizes": {app: len(hist) for app, hist in self.history.items()},
            "training_summary": self.training_summary,
        }


# Singleton instance
ml_service = MLService()
