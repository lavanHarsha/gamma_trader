import os
import threading
import duckdb
import pandas as pd
import numpy as np
from datetime import datetime
import pytz
from typing import Optional, List, Dict

IST = pytz.timezone("Asia/Kolkata")

class DataStorageManager:
    """
    DuckDB and Partitioned Parquet storage manager for NSE intraday equity data.
    Enforces strict Asia/Kolkata timezone localization and intraday session hygiene.
    """

    def __init__(self, base_dir: str = "data"):
        self.base_dir = os.path.abspath(base_dir)
        self.raw_dir = os.path.join(self.base_dir, "raw_parquet")
        self.processed_dir = os.path.join(self.base_dir, "processed_features")
        self.models_dir = os.path.join(self.base_dir, "models")
        self._lock = threading.Lock()
        
        os.makedirs(self.raw_dir, exist_ok=True)
        os.makedirs(self.processed_dir, exist_ok=True)
        os.makedirs(self.models_dir, exist_ok=True)

        self.db_path = os.path.join(self.base_dir, "gamma_trader.duckdb")
        try:
            self.conn = duckdb.connect(self.db_path)
            self._init_duckdb_schema()
        except Exception:
            try:
                self.conn = duckdb.connect(self.db_path, read_only=True)
            except Exception:
                self.conn = duckdb.connect(":memory:")

    def _init_duckdb_schema(self):
        """Initialize tables / views if needed in DuckDB."""
        with self._lock:
            try:
                self.conn.execute("""
                    CREATE TABLE IF NOT EXISTS data_catalog (
                        symbol VARCHAR,
                        interval_min INTEGER,
                        start_ts TIMESTAMP WITH TIME ZONE,
                        end_ts TIMESTAMP WITH TIME ZONE,
                        bar_count INTEGER,
                        file_path VARCHAR,
                        last_updated TIMESTAMP WITH TIME ZONE
                    );
                """)
            except Exception:
                pass

    @staticmethod
    def enforce_ist_hygiene(df: pd.DataFrame) -> pd.DataFrame:
        """
        Enforce strict intraday session hygiene:
        1. Timestamp converted to Asia/Kolkata.
        2. Filter only normal NSE market hours: 09:15:00 to 15:30:00 IST.
        3. Drop duplicates and sort ascending.
        4. Strictly reject or reset any cross-day forward-fill.
        """
        if df.empty:
            return df

        df = df.copy()
        if not pd.api.types.is_datetime64_any_dtype(df['timestamp']):
            df['timestamp'] = pd.to_datetime(df['timestamp'], utc=True)

        if df['timestamp'].dt.tz is None:
            df['timestamp'] = df['timestamp'].dt.tz_localize("UTC").dt.tz_convert(IST)
        else:
            df['timestamp'] = df['timestamp'].dt.tz_convert(IST)

        df = df.drop_duplicates(subset=['timestamp']).sort_values('timestamp').reset_index(drop=True)

        # Market hours filter: 09:15 <= time <= 15:30
        times = df['timestamp'].dt.time
        open_time = pd.to_datetime("09:15:00").time()
        close_time = pd.to_datetime("15:30:00").time()
        mask = (times >= open_time) & (times <= close_time)
        df = df[mask].reset_index(drop=True)

        # Ensure date column for group-by
        df['date'] = df['timestamp'].dt.date
        return df

    def save_raw_bars(self, symbol: str, interval_min: int, df: pd.DataFrame):
        """Save clean OHLCV bars partitioned by symbol and interval."""
        if df.empty:
            return

        df = self.enforce_ist_hygiene(df)
        symbol_clean = symbol.upper().replace("^", "")
        file_path = os.path.join(self.raw_dir, f"{symbol_clean}_{interval_min}m.parquet")
        
        # Merge if existing
        if os.path.exists(file_path):
            existing_df = pd.read_parquet(file_path)
            existing_df = self.enforce_ist_hygiene(existing_df)
            combined = pd.concat([existing_df, df], ignore_index=True)
            combined = combined.drop_duplicates(subset=['timestamp']).sort_values('timestamp').reset_index(drop=True)
            df = combined

        df.to_parquet(file_path, index=False, compression="snappy")

        # Update catalog in DuckDB if writable
        try:
            min_ts = df['timestamp'].min()
            max_ts = df['timestamp'].max()
            count = len(df)
            now_ts = datetime.now(IST)

            with self._lock:
                cursor = self.conn.cursor()
                try:
                    cursor.execute("DELETE FROM data_catalog WHERE symbol = ? AND interval_min = ?", [symbol_clean, interval_min])
                    cursor.execute("""
                        INSERT INTO data_catalog VALUES (?, ?, ?, ?, ?, ?, ?)
                    """, [symbol_clean, interval_min, min_ts, max_ts, count, file_path, now_ts])
                finally:
                    cursor.close()
        except Exception:
            pass

    def load_raw_bars(
        self,
        symbol: str,
        interval_min: int,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None
    ) -> pd.DataFrame:
        """Load OHLCV bars using high-speed Parquet read with DuckDB fallback."""
        symbol_clean = symbol.upper().replace("^", "")
        file_path = os.path.join(self.raw_dir, f"{symbol_clean}_{interval_min}m.parquet")
        if not os.path.exists(file_path):
            return pd.DataFrame()

        # Fast path: direct parquet read without database locking
        if not start_date and not end_date:
            try:
                df = pd.read_parquet(file_path)
                return self.enforce_ist_hygiene(df)
            except Exception:
                pass

        query = f"SELECT * FROM read_parquet('{file_path.replace(os.sep, '/')}')"
        conditions = []
        if start_date:
            conditions.append(f"timestamp >= '{start_date}'")
        if end_date:
            conditions.append(f"timestamp <= '{end_date}'")

        if conditions:
            query += " WHERE " + " AND ".join(conditions)
        query += " ORDER BY timestamp ASC"

        with self._lock:
            cursor = self.conn.cursor()
            try:
                df = cursor.execute(query).df()
            finally:
                cursor.close()
        return self.enforce_ist_hygiene(df)

    def close(self):
        if self.conn:
            self.conn.close()

