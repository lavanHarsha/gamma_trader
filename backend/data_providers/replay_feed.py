import os
import time
import asyncio
from datetime import datetime, date
from typing import Dict, Any, List, Optional, Callable
import pandas as pd
import pytz

from backend.data_providers.base import MarketDataProvider
from backend.data_providers.storage import DataStorageManager

IST = pytz.timezone("Asia/Kolkata")

class ReplayMarketDataProvider(MarketDataProvider):
    """
    Market Replay Simulator for testing the Web UI, Stage-1 Candlestick scanner,
    and Meta-labeling model outside market hours (after 3:30 PM IST or weekends).
    Simulates live bar progression at 1x, 5x, 10x, or max speed.
    """

    def __init__(self, storage: DataStorageManager):
        self.storage = storage
        self.active_date: Optional[date] = None
        self.interval_min: int = 15
        self.symbols: List[str] = []
        self.data_cache: Dict[str, pd.DataFrame] = {}
        self.all_timestamps: List[pd.Timestamp] = []
        self.current_index: int = 0
        self.is_running: bool = False
        self.speed: float = 1.0  # multiplier: 1x, 5x, 10x
        self.on_tick_callbacks: List[Callable[[Dict[str, Any]], None]] = []

    def set_session(self, target_date: date, symbols: List[str], interval_min: int = 15):
        """Prepare replay cache for a specific date and universe."""
        self.active_date = target_date
        self.interval_min = interval_min
        self.symbols = symbols
        self.data_cache = {}
        ts_set = set()

        for sym in symbols:
            df = self.storage.load_raw_bars(
                symbol=sym,
                interval_min=interval_min,
                start_date=f"{target_date} 09:15:00",
                end_date=f"{target_date} 15:30:00"
            )
            if not df.empty:
                self.data_cache[sym] = df
                for ts in df['timestamp']:
                    ts_set.add(ts)

        self.all_timestamps = sorted(list(ts_set))
        self.current_index = 0
        self.is_running = False

    def get_current_timestamp(self) -> Optional[pd.Timestamp]:
        if 0 <= self.current_index < len(self.all_timestamps):
            return self.all_timestamps[self.current_index]
        return None

    def get_current_bar(self, symbol: str, interval_min: int = 15) -> Optional[pd.DataFrame]:
        curr_ts = self.get_current_timestamp()
        df = self.data_cache.get(symbol.upper(), pd.DataFrame())
        if df.empty or curr_ts is None:
            return None
        sub = df[df['timestamp'] == curr_ts]
        return sub if not sub.empty else None

    def step(self) -> Optional[pd.Timestamp]:
        """Advance replay by 1 bar."""
        if self.current_index < len(self.all_timestamps) - 1:
            self.current_index += 1
            curr_ts = self.all_timestamps[self.current_index]
            self._notify_tick(curr_ts)
            return curr_ts
        return None

    def seek(self, index: int):
        if 0 <= index < len(self.all_timestamps):
            self.current_index = index
            self._notify_tick(self.all_timestamps[self.current_index])

    def fetch_historical_bars(
        self,
        symbol: str,
        interval_minutes: int,
        start_dt: datetime,
        end_dt: datetime,
        exchange: str = "NSE",
        segment: str = "CASH"
    ) -> pd.DataFrame:
        """
        Returns only bars up to current_index timestamp to ensure ZERO future leakage!
        """
        curr_ts = self.get_current_timestamp()
        df = self.data_cache.get(symbol.upper(), pd.DataFrame())
        if df.empty or curr_ts is None:
            return pd.DataFrame()

        # Slice strictly <= curr_ts
        visible_df = df[df['timestamp'] <= curr_ts].copy()
        return visible_df

    def get_latest_quote(self, symbol: str) -> Dict[str, Any]:
        curr_ts = self.get_current_timestamp()
        df = self.data_cache.get(symbol.upper(), pd.DataFrame())
        if df.empty or curr_ts is None:
            return {"symbol": symbol, "status": "NO_REPLAY_DATA"}

        visible = df[df['timestamp'] <= curr_ts]
        if visible.empty:
            return {"symbol": symbol, "status": "PENDING_OPEN"}

        last = visible.iloc[-1]
        return {
            "symbol": symbol.upper(),
            "timestamp": last['timestamp'].isoformat(),
            "open": float(last['open']),
            "high": float(last['high']),
            "low": float(last['low']),
            "close": float(last['close']),
            "volume": float(last['volume']),
            "replay_index": self.current_index,
            "total_bars": len(self.all_timestamps),
            "status": "REPLAY"
        }

    def _notify_tick(self, ts: pd.Timestamp):
        snapshot = {
            "timestamp": ts.isoformat(),
            "replay_index": self.current_index,
            "total_bars": len(self.all_timestamps),
            "progress_pct": round((self.current_index + 1) / max(1, len(self.all_timestamps)) * 100, 1),
            "quotes": {sym: self.get_latest_quote(sym) for sym in self.symbols}
        }
        for cb in self.on_tick_callbacks:
            try:
                cb(snapshot)
            except Exception:
                pass

