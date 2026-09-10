"""
Unit tests for data preprocessing pipeline.

Verifies no data leakage, correct feature engineering,
and proper chronological splitting.
"""

import numpy as np
import pandas as pd
import pytest
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from ml.preprocessing.clean import clean_dataset, clip_outliers
from ml.preprocessing.features import build_features, add_lag_features, get_feature_columns
from ml.preprocessing.split import chronological_split


class TestDataLeakage:
    """Ensure no future information leaks into features."""

    def test_lag_features_no_future(self):
        """Lag features must only use past values."""
        n = 200
        df = pd.DataFrame({
            "timestamp": pd.date_range("2026-01-01", periods=n, freq="15min", tz="UTC"),
            "load_power_w": np.arange(n, dtype=float),  # 0, 1, 2, ...
            "pv_power_w": np.zeros(n),
            "grid_power_w": np.zeros(n),
            "soc_pct": np.full(n, 50.0),
            "temperature_c": np.full(n, 25.0),
            "irradiance_wm2": np.zeros(n),
            "battery_power_w": np.zeros(n),
        })

        df = add_lag_features(df)

        # lag1 at index 5 should equal value at index 4
        assert df["load_power_w_lag1"].iloc[5] == 4.0, \
            "Lag1 does not point to previous step"

        # lag1 at index 0 should be NaN (no previous value)
        assert pd.isna(df["load_power_w_lag1"].iloc[0]), \
            "Lag1 at index 0 should be NaN"

    def test_rolling_features_shifted(self):
        """Rolling features must use shift(1) to exclude current value."""
        n = 100
        df = pd.DataFrame({
            "timestamp": pd.date_range("2026-01-01", periods=n, freq="15min", tz="UTC"),
            "load_power_w": np.arange(n, dtype=float),
            "pv_power_w": np.zeros(n),
            "grid_power_w": np.zeros(n),
            "soc_pct": np.full(n, 50.0),
            "temperature_c": np.full(n, 25.0),
            "irradiance_wm2": np.zeros(n),
            "battery_power_w": np.zeros(n),
        })

        df = build_features(df)

        # At index 10, rolling mean of 4 steps should use indices 6-9 (shifted)
        # Values 6, 7, 8, 9 → mean = 7.5
        if "load_power_w_rmean4" in df.columns:
            rmean_val = df["load_power_w_rmean4"].iloc[10]
            expected = np.mean([6, 7, 8, 9])
            assert abs(rmean_val - expected) < 0.01, \
                f"Rolling mean at step 10 = {rmean_val}, expected {expected}"


class TestChronologicalSplit:
    """Verify train/val/test splits maintain temporal order."""

    def _make_df(self, n=1000):
        return pd.DataFrame({
            "timestamp": pd.date_range("2026-01-01", periods=n, freq="15min", tz="UTC"),
            "load_power_w": np.random.default_rng(42).uniform(200, 3000, n),
        })

    def test_split_sizes(self):
        """Split sizes match requested fractions."""
        df = self._make_df(1000)
        train, val, test = chronological_split(df, 0.70, 0.15, 0.15, drop_na_features=False)

        assert len(train) == 700
        assert len(val) == 150
        assert len(test) == 150

    def test_no_overlap(self):
        """No timestamp appears in more than one split."""
        df = self._make_df(1000)
        train, val, test = chronological_split(df, 0.70, 0.15, 0.15, drop_na_features=False)

        train_ts = set(train["timestamp"])
        val_ts = set(val["timestamp"])
        test_ts = set(test["timestamp"])

        assert len(train_ts & val_ts) == 0, "Train/val overlap"
        assert len(val_ts & test_ts) == 0, "Val/test overlap"
        assert len(train_ts & test_ts) == 0, "Train/test overlap"

    def test_temporal_order(self):
        """Train ends before val starts, val ends before test starts."""
        df = self._make_df(1000)
        train, val, test = chronological_split(df, 0.70, 0.15, 0.15, drop_na_features=False)

        assert train["timestamp"].max() < val["timestamp"].min(), \
            "Train data overlaps with validation"
        assert val["timestamp"].max() < test["timestamp"].min(), \
            "Validation data overlaps with test"

    def test_fractions_sum_to_one(self):
        """Fractions must sum to 1.0."""
        df = self._make_df(100)
        with pytest.raises(AssertionError):
            chronological_split(df, 0.5, 0.3, 0.3, drop_na_features=False)


class TestOutlierClipping:
    """Verify outlier clipping uses engineering limits."""

    def test_pv_clipped_to_zero(self):
        """Negative PV values should be clipped to 0."""
        df = pd.DataFrame({"pv_power_w": [-100, 0, 3000, 7000]})
        result = clip_outliers(df)
        assert result["pv_power_w"].min() >= 0
        assert result["pv_power_w"].max() <= 6000

    def test_soc_clipped_to_range(self):
        """SOC must be between 0 and 100."""
        df = pd.DataFrame({"soc_pct": [-5, 50, 105]})
        result = clip_outliers(df)
        assert result["soc_pct"].min() >= 0
        assert result["soc_pct"].max() <= 100


class TestFeatureColumns:
    """Verify feature column definitions are consistent."""

    def test_consumption_features_defined(self):
        config = get_feature_columns("consumption")
        assert config["target"] == "load_power_w"
        assert len(config["features"]) > 10

    def test_pv_features_defined(self):
        config = get_feature_columns("pv")
        assert config["target"] == "pv_power_w"
        assert len(config["features"]) > 10

    def test_invalid_target_raises(self):
        with pytest.raises(ValueError):
            get_feature_columns("invalid")
