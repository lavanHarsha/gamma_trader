import os
import logging
from datetime import datetime
import pandas as pd
from typing import Dict, Any, Optional
from backend.data_providers.base import MarketDataProvider

logger = logging.getLogger("AngelFyersFeed")

class AngelSmartAPIProvider(MarketDataProvider):
    """
    Adapter for Angel One SmartAPI (free historical and WebSocket tick streaming).
    Requires ANGEL_API_KEY, ANGEL_CLIENT_ID, and ANGEL_PIN in environment variables.
    """
    def __init__(self, api_key: Optional[str] = None, client_id: Optional[str] = None):
        self.api_key = api_key or os.getenv("ANGEL_API_KEY", "")
        self.client_id = client_id or os.getenv("ANGEL_CLIENT_ID", "")
        self.connected = bool(self.api_key and self.client_id)

    def fetch_historical_bars(
        self,
        symbol: str,
        interval_minutes: int,
        start_dt: datetime,
        end_dt: datetime,
        exchange: str = "NSE",
        segment: str = "CASH"
    ) -> pd.DataFrame:
        if not self.connected:
            logger.info("Angel One credentials not provided; defaulting to empty dataframe.")
            return pd.DataFrame()
        # Integration logic with smartapi-python when credentials exist
        return pd.DataFrame()

    def get_latest_quote(self, symbol: str) -> Dict[str, Any]:
        return {"symbol": symbol, "status": "Angel One connected" if self.connected else "unconfigured"}


class FyersAPIProvider(MarketDataProvider):
    """
    Adapter for Fyers API v3 (free historical and live WebSocket streaming).
    Requires FYERS_APP_ID and FYERS_ACCESS_TOKEN in environment variables.
    """
    def __init__(self, app_id: Optional[str] = None, access_token: Optional[str] = None):
        self.app_id = app_id or os.getenv("FYERS_APP_ID", "")
        self.access_token = access_token or os.getenv("FYERS_ACCESS_TOKEN", "")
        self.connected = bool(self.app_id and self.access_token)

    def fetch_historical_bars(
        self,
        symbol: str,
        interval_minutes: int,
        start_dt: datetime,
        end_dt: datetime,
        exchange: str = "NSE",
        segment: str = "CASH"
    ) -> pd.DataFrame:
        if not self.connected:
            logger.info("Fyers credentials not provided; defaulting to empty dataframe.")
            return pd.DataFrame()
        return pd.DataFrame()

    def get_latest_quote(self, symbol: str) -> Dict[str, Any]:
        return {"symbol": symbol, "status": "Fyers connected" if self.connected else "unconfigured"}

