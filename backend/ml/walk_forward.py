import numpy as np
import pandas as pd
from typing import Generator, Tuple, List
from datetime import timedelta

class PurgedWalkForwardCV:
    """
    Purged & Embargoed Walk-Forward Cross-Validator.
    Splits:
      - Train: 6 months
      - Purge / Embargo: 2 trading days
      - Validation (for Calibration): 1 month
      - Test (Strictly Out-of-Sample): 1 month
    Steps forward 1 month at a time.
    """

    def __init__(
        self,
        train_months: int = 6,
        val_months: int = 1,
        test_months: int = 1,
        embargo_days: int = 2
    ):
        self.train_months = train_months
        self.val_months = val_months
        self.test_months = test_months
        self.embargo_days = embargo_days

    def split(
        self,
        df: pd.DataFrame
    ) -> Generator[Tuple[np.ndarray, np.ndarray, np.ndarray], None, None]:
        """
        Yields (train_indices, val_indices, test_indices).
        """
        if df.empty or 'timestamp' not in df.columns:
            return

        df_sorted = df.sort_values('timestamp').reset_index(drop=True)
        timestamps = df_sorted['timestamp']
        min_ts = timestamps.min()
        max_ts = timestamps.max()

        # Step monthly
        step_days = 30
        train_span = timedelta(days=self.train_months * 30)
        val_span = timedelta(days=self.val_months * 30)
        test_span = timedelta(days=self.test_months * 30)
        embargo_span = timedelta(days=self.embargo_days)

        curr_train_start = min_ts

        while True:
            train_end = curr_train_start + train_span
            val_start = train_end + embargo_span
            val_end = val_start + val_span
            test_start = val_end + embargo_span
            test_end = test_start + test_span

            if test_start >= max_ts:
                break

            train_mask = (timestamps >= curr_train_start) & (timestamps < train_end)
            val_mask = (timestamps >= val_start) & (timestamps < val_end)
            test_mask = (timestamps >= test_start) & (timestamps <= test_end)

            train_idx = np.where(train_mask)[0]
            val_idx = np.where(val_mask)[0]
            test_idx = np.where(test_mask)[0]

            if len(train_idx) > 10 and len(val_idx) > 5 and len(test_idx) > 5:
                yield train_idx, val_idx, test_idx

            curr_train_start += timedelta(days=step_days)

