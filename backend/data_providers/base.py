from abc import ABC, abstractmethod
from typing import List, Dict, Any, Optional
import pandas as pd
from datetime import datetime

class MarketDataProvider(ABC):
    """
    Abstract Interface for Market Data Providers.
    Supports historical backfills (1m, 5m, 15m), live streaming / polling,
    and market replay simulation.
    """

    @abstractmethod
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
        Fetch historical OHLCV bars.
        Must return a DataFrame with columns:
        ['timestamp', 'open', 'high', 'low', 'close', 'volume', 'symbol']
        where 'timestamp' is a tz-aware datetime localized to Asia/Kolkata.
        """
        pass

    @abstractmethod
    def get_latest_quote(self, symbol: str) -> Dict[str, Any]:
        """
        Fetch latest tick / quote:
        returns {'symbol': ..., 'price': ..., 'volume': ..., 'timestamp': ..., 'day_high': ..., 'day_low': ...}
        """
        pass

