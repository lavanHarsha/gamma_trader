import sys
import os
import pytest
import numpy as np
import pandas as pd
from datetime import datetime, time
import pytz

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from backend.data_providers.storage import DataStorageManager
from backend.features.stationary import StationaryFeatureEngine
from backend.ml.trainer import ModelTrainer

IST = pytz.timezone("Asia/Kolkata")

def test_tatasteel_zero_future_leakage():
    """
    Mandatory Anti-Leakage Mutation Test:
    1. Load historical trading day for TATASTEEL from storage.
    2. Compute the 22 features and ML probability p_win at 10:30 IST.
    3. Overwrite all OHLCV rows from 10:35 IST to 15:30 IST with extreme random numbers (price * 100).
    4. Recompute features and p_win at 10:30 IST.
    5. Assert that np.isclose(features_before, features_after, atol=1e-12) is True.
    """
    storage = DataStorageManager("data")
    trainer = ModelTrainer("data/models")
    trainer.load_artifacts()

    # Load TATASTEEL 15m bars
    df_raw = storage.load_raw_bars("TATASTEEL", 15)
    assert not df_raw.empty, "TATASTEEL raw parquet data must exist"

    # Select the most recent complete trading day with normal morning hours
    available_dates = sorted(df_raw['date'].unique())
    target_date = None
    for d in reversed(available_dates[:-1]):
        day_df = df_raw[df_raw['date'] == d]
        if any(day_df['timestamp'].dt.time <= time(10, 30)) and len(day_df) >= 15:
            target_date = d
            break

    if target_date is None:
        target_date = available_dates[-2] if len(available_dates) >= 2 else available_dates[-1]

    # Include prior day for prior-day anchor calculations
    prior_dates = [d for d in available_dates if d < target_date]
    if prior_dates:
        prev_date = prior_dates[-1]
        test_df = df_raw[df_raw['date'].isin([prev_date, target_date])].copy().reset_index(drop=True)
    else:
        test_df = df_raw[df_raw['date'] == target_date].copy().reset_index(drop=True)

    # Locate the 10:30 IST bar (or closest bar <= 10:30 IST on target_date)
    day_mask = (test_df['date'] == target_date)
    day_indices = test_df[day_mask].index.tolist()
    
    target_idx = None
    target_time = time(10, 30)
    for idx in day_indices:
        b_time = test_df.iloc[idx]['timestamp'].time()
        if b_time <= target_time:
            target_idx = idx

    assert target_idx is not None, "Must find bar at or before 10:30 IST on target date"

    # 1. Compute features before mutation
    df_calc1 = StationaryFeatureEngine.compute_indicators(test_df.copy())
    feats_before = StationaryFeatureEngine.extract_features_at_index(
        df=df_calc1,
        idx=target_idx,
        direction="LONG"
    )
    p_win_before = trainer.predict_p_win(feats_before)

    # 2. Mutate all rows after 10:30 IST up to 15:30 IST with extreme numbers (price * 100)
    df_mutated = test_df.copy()
    np.random.seed(42)
    for future_idx in range(target_idx + 1, len(df_mutated)):
        orig_c = df_mutated.at[future_idx, "close"]
        extreme_mult = 100.0 + np.random.uniform(5.0, 50.0)
        df_mutated.at[future_idx, "open"] = orig_c * extreme_mult
        df_mutated.at[future_idx, "high"] = orig_c * extreme_mult * 1.5
        df_mutated.at[future_idx, "low"] = orig_c * 0.1
        df_mutated.at[future_idx, "close"] = orig_c * extreme_mult * 1.2
        df_mutated.at[future_idx, "volume"] = 99999999.0

    # 3. Recompute indicators and features after mutation
    df_calc2 = StationaryFeatureEngine.compute_indicators(df_mutated)
    feats_after = StationaryFeatureEngine.extract_features_at_index(
        df=df_calc2,
        idx=target_idx,
        direction="LONG"
    )
    p_win_after = trainer.predict_p_win(feats_after)

    # 4. Strict assertion: All 22 features identical with atol=1e-12
    for feat_name in StationaryFeatureEngine.FEATURE_NAMES:
        val_b = feats_before[feat_name]
        val_a = feats_after[feat_name]
        assert np.isclose(val_b, val_a, atol=1e-12), (
            f"LEAKAGE DETECTED on feature '{feat_name}'! Before: {val_b}, After: {val_a}, Diff: {abs(val_b - val_a)}"
        )

    # 5. Probability p_win must also be identical
    assert np.isclose(p_win_before, p_win_after, atol=1e-6), (
        f"Probability changed from {p_win_before} to {p_win_after}"
    )

if __name__ == "__main__":
    test_tatasteel_zero_future_leakage()
    print("ALL MANDATORY ZERO-LEAKAGE TESTS PASSED! atol=1e-12 verified on historical TATASTEEL.")
