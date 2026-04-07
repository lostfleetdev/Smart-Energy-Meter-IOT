"""
Improved Data Pipeline v2 - Selective cleaning for better ML results

Key improvements:
1. Select only high-quality houses per appliance
2. Filter out periods with excessive zeros/missing data
3. Focus on ACTIVE usage periods only (when appliance is actually used)
4. Better outlier handling
5. Separate models for usage prediction vs on/off classification
"""

import os
import pandas as pd
import numpy as np
from pathlib import Path
from datetime import datetime

BASE_DIR = Path(__file__).parent
RAW_DIR = BASE_DIR / "dataset" / "Clean_dataset"
PROCESSED_DIR = BASE_DIR / "dataset" / "processed_v2"
PROCESSED_DIR.mkdir(exist_ok=True)

# High-quality houses per appliance (based on data quality analysis)
QUALITY_HOUSES = {
    "ac_1": [1, 3, 7, 2, 11],        # Good continuous data, varied usage
    "ac_2": [3, 1, 7, 11],           # Best 4 houses
    "boiler": [1, 4, 7, 9, 2],       # Low missing, active usage
    "fridge": [1, 3, 7, 8, 6],       # Continuous appliance, need good data
    "washing_machine": [7, 12, 5, 3], # Intermittent but active
    "dishwasher": [12],              # Only 1 quality house
}

# Appliance thresholds for ON detection (Watts)
ON_THRESHOLDS = {
    "ac_1": 100,      # AC needs substantial power when running
    "ac_2": 100,
    "boiler": 200,    # Boilers draw significant power
    "fridge": 30,     # Fridges cycle on/off
    "washing_machine": 50,
    "dishwasher": 20,
}


def load_house_data(house_num: int):
    """Load and merge electric + environmental data for a house."""
    house_dir = RAW_DIR / f"House_{house_num:02d}"
    
    if not house_dir.exists():
        return None
    
    # Load electric data
    electric_dir = house_dir / "Electric_data"
    electric_files = sorted(electric_dir.glob("202*.csv"))
    
    if not electric_files:
        return None
    
    electric_dfs = []
    for f in electric_files:
        df = pd.read_csv(f, parse_dates=["timestamp"])
        electric_dfs.append(df)
    
    electric_df = pd.concat(electric_dfs, ignore_index=True)
    
    # Load environmental data
    env_dir = house_dir / "Environmental_data"
    env_files = sorted(env_dir.glob("202*.csv"))
    
    if env_files:
        env_dfs = []
        for f in env_files:
            df = pd.read_csv(f, parse_dates=["timestamp"])
            env_dfs.append(df)
        env_df = pd.concat(env_dfs, ignore_index=True)
        
        # Fix temperature column typo
        if "external_temparature" in env_df.columns:
            env_df["external_temperature"] = env_df["external_temparature"].combine_first(
                env_df.get("external_temperature", pd.Series())
            )
            env_df = env_df.drop(columns=["external_temparature"], errors="ignore")
        
        # Merge on timestamp (forward fill environmental data)
        env_df = env_df.sort_values("timestamp")
        electric_df = electric_df.sort_values("timestamp")
        
        electric_df = pd.merge_asof(
            electric_df, env_df,
            on="timestamp",
            direction="backward"
        )
    
    electric_df["house_id"] = house_num
    return electric_df


def clean_appliance_data(df: pd.DataFrame, appliance: str):
    """
    Clean data for specific appliance with aggressive filtering.
    """
    target_col = appliance
    
    if target_col not in df.columns:
        return None
    
    df = df.copy()
    
    # 1. Remove rows with issues flag
    if "issues" in df.columns:
        df = df[df["issues"] != 1]
    
    # 2. Remove rows where target is missing
    df = df.dropna(subset=[target_col])
    
    # 3. Remove obvious outliers (> 99.9th percentile or negative)
    upper_limit = df[target_col].quantile(0.999)
    df = df[(df[target_col] >= 0) & (df[target_col] <= upper_limit)]
    
    # 4. Forward fill small gaps (up to 1 minute = 6 readings at 10s)
    df[target_col] = df[target_col].ffill(limit=6)
    
    return df


def create_hourly_aggregates(df: pd.DataFrame, appliance: str):
    """Create hourly aggregates with quality metrics."""
    target_col = appliance
    on_threshold = ON_THRESHOLDS.get(appliance, 50)
    
    df = df.copy()
    df["hour"] = df["timestamp"].dt.floor("h")
    
    # Mark ON periods
    df["is_on"] = (df[target_col] > on_threshold).astype(int)
    
    # Aggregate
    agg_dict = {
        target_col: ["mean", "max", "min", "std", "count"],
        "is_on": ["sum", "mean"],  # on_count and on_ratio
        "P_agg": ["mean", "max"] if "P_agg" in df.columns else [],
    }
    
    # Add environmental features if present
    for col in ["external_temperature", "internal_temperature", "external_humidity", "internal_humidity"]:
        if col in df.columns:
            agg_dict[col] = ["mean"]
    
    # Add voltage/current if present
    for col in ["V", "A"]:
        if col in df.columns:
            agg_dict[col] = ["mean"]
    
    # Remove empty aggregations
    agg_dict = {k: v for k, v in agg_dict.items() if v}
    
    hourly = df.groupby(["house_id", "hour"]).agg(agg_dict).reset_index()
    
    # Flatten column names
    new_cols = []
    for col in hourly.columns:
        if isinstance(col, tuple):
            if col[1]:
                new_cols.append(f"{col[0]}_{col[1]}")
            else:
                new_cols.append(col[0])
        else:
            new_cols.append(col)
    hourly.columns = new_cols
    
    # Rename index columns
    hourly = hourly.rename(columns={"hour": "timestamp"})
    
    # Quality filter: require at least 300 readings per hour (83% coverage)
    count_col = f"{target_col}_count"
    if count_col in hourly.columns:
        hourly = hourly[hourly[count_col] >= 300]
        hourly = hourly.drop(columns=[count_col])
    
    return hourly


def add_features(df: pd.DataFrame, appliance: str):
    """Add time features and lag features."""
    df = df.copy()
    
    # Time features
    df["hour"] = df["timestamp"].dt.hour
    df["day_of_week"] = df["timestamp"].dt.dayofweek
    df["is_weekend"] = (df["day_of_week"] >= 5).astype(int)
    df["month"] = df["timestamp"].dt.month
    
    # Season (Northern hemisphere)
    df["season"] = df["month"].map({
        12: 0, 1: 0, 2: 0,    # Winter
        3: 1, 4: 1, 5: 1,     # Spring
        6: 2, 7: 2, 8: 2,     # Summer
        9: 3, 10: 3, 11: 3    # Fall
    })
    
    # Time period
    df["time_period"] = pd.cut(
        df["hour"],
        bins=[-1, 6, 12, 18, 24],
        labels=[0, 1, 2, 3]  # Night, Morning, Afternoon, Evening
    ).astype(int)
    
    target_mean = f"{appliance}_mean"
    
    # Lag features (per house)
    for house_id in df["house_id"].unique():
        mask = df["house_id"] == house_id
        house_df = df.loc[mask, target_mean]
        
        for lag in [1, 2, 3, 6, 12, 24]:
            df.loc[mask, f"lag_{lag}"] = house_df.shift(lag)
        
        # Rolling features
        df.loc[mask, "rolling_mean_6h"] = house_df.rolling(6, min_periods=1).mean()
        df.loc[mask, "rolling_std_6h"] = house_df.rolling(6, min_periods=1).std()
        df.loc[mask, "rolling_mean_24h"] = house_df.rolling(24, min_periods=1).mean()
        
        # Difference features
        df.loc[mask, "diff_1h"] = house_df.diff(1)
        df.loc[mask, "diff_24h"] = house_df.diff(24)
    
    return df


def create_active_usage_dataset(df: pd.DataFrame, appliance: str):
    """
    Create dataset focused on ACTIVE usage periods only.
    For intermittent appliances, this filters to periods when device is on.
    """
    target_mean = f"{appliance}_mean"
    on_threshold = ON_THRESHOLDS.get(appliance, 50)
    
    # For fridge (always cycling), keep all data
    if appliance == "fridge":
        return df
    
    # For intermittent appliances, focus on active periods
    # Include: when device is ON, or 3 hours before/after ON periods
    df = df.copy()
    df = df.sort_values(["house_id", "timestamp"])
    
    is_on = df[target_mean] > on_threshold
    
    # Expand to include context around ON periods
    for house_id in df["house_id"].unique():
        mask = df["house_id"] == house_id
        house_on = is_on[mask]
        
        # Rolling window: mark as active if ON within ±3 hours
        expanded = house_on.rolling(7, center=True, min_periods=1).max()
        is_on.loc[mask] = expanded > 0
    
    # Keep rows that are in active periods
    active_df = df[is_on].copy()
    
    print(f"  Active usage: {len(active_df)}/{len(df)} rows ({len(active_df)/len(df)*100:.1f}%)")
    
    return active_df


def process_appliance_v2(appliance: str):
    """Process data for one appliance with quality filtering."""
    print(f"\n{'='*60}")
    print(f"Processing: {appliance.upper()}")
    print(f"{'='*60}")
    
    houses = QUALITY_HOUSES.get(appliance, [])
    if not houses:
        print(f"No quality houses defined for {appliance}")
        return None
    
    print(f"Using houses: {houses}")
    
    all_data = []
    
    for house_num in houses:
        print(f"\n  House {house_num}...")
        
        # Load raw data
        df = load_house_data(house_num)
        if df is None:
            print(f"    No data found")
            continue
        
        # Clean appliance data
        df = clean_appliance_data(df, appliance)
        if df is None or len(df) == 0:
            print(f"    No valid data after cleaning")
            continue
        
        print(f"    Raw rows: {len(df)}")
        
        # Create hourly aggregates
        hourly = create_hourly_aggregates(df, appliance)
        print(f"    Hourly rows: {len(hourly)}")
        
        all_data.append(hourly)
    
    if not all_data:
        print("No data collected!")
        return None
    
    # Combine all houses
    combined = pd.concat(all_data, ignore_index=True)
    combined = combined.sort_values(["house_id", "timestamp"])
    
    # Add features
    combined = add_features(combined, appliance)
    
    # Drop rows with missing lag features
    combined = combined.dropna(subset=["lag_1"])
    
    print(f"\nTotal rows: {len(combined)}")
    print(f"Houses: {combined['house_id'].nunique()}")
    
    # Save full dataset
    full_path = PROCESSED_DIR / f"{appliance}_hourly_full.csv"
    combined.to_csv(full_path, index=False)
    print(f"Saved: {full_path}")
    
    # Create active-only dataset for intermittent appliances
    if appliance != "fridge":
        active = create_active_usage_dataset(combined, appliance)
        active_path = PROCESSED_DIR / f"{appliance}_hourly_active.csv"
        active.to_csv(active_path, index=False)
        print(f"Saved: {active_path}")
    
    return combined


def create_classification_dataset(appliance: str):
    """
    Create binary classification dataset: predict if appliance will be ON in next hour.
    """
    print(f"\nCreating classification dataset for {appliance}...")
    
    full_path = PROCESSED_DIR / f"{appliance}_hourly_full.csv"
    if not full_path.exists():
        print("Full dataset not found, run process_appliance_v2 first")
        return None
    
    df = pd.read_csv(full_path, parse_dates=["timestamp"])
    
    on_ratio_col = "is_on_mean"
    
    # Target: will appliance be ON in next hour? (>50% of readings above threshold)
    df["next_hour_on"] = np.nan  # Use float to allow NaN
    
    for house_id in df["house_id"].unique():
        mask = df["house_id"] == house_id
        df.loc[mask, "next_hour_on"] = df.loc[mask, on_ratio_col].shift(-1).values
    
    # Binary target
    df["target_on"] = (df["next_hour_on"] > 0.3).astype(int)
    
    # Remove last row per house (no next hour)
    df = df.dropna(subset=["next_hour_on"])
    
    # Balance check
    on_pct = df["target_on"].mean() * 100
    print(f"  ON class: {on_pct:.1f}%")
    print(f"  OFF class: {100-on_pct:.1f}%")
    
    # Save
    clf_path = PROCESSED_DIR / f"{appliance}_classification.csv"
    df.to_csv(clf_path, index=False)
    print(f"Saved: {clf_path}")
    
    return df


def process_all_v2():
    """Process all appliances with improved pipeline."""
    
    for appliance in QUALITY_HOUSES.keys():
        process_appliance_v2(appliance)
        create_classification_dataset(appliance)
    
    print(f"\n{'='*60}")
    print("PIPELINE COMPLETE")
    print(f"{'='*60}")
    print(f"Output directory: {PROCESSED_DIR}")
    
    # Summary
    print("\nGenerated datasets:")
    for f in sorted(PROCESSED_DIR.glob("*.csv")):
        df = pd.read_csv(f)
        print(f"  {f.name}: {len(df)} rows")


if __name__ == "__main__":
    process_all_v2()
