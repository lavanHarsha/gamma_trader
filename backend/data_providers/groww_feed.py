import requests
import time
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import pytz
from typing import Dict, Any, Optional, List
import logging

from backend.data_providers.base import MarketDataProvider

logger = logging.getLogger("GrowwMarketDataProvider")
IST = pytz.timezone("Asia/Kolkata")

class GrowwMarketDataProvider(MarketDataProvider):
    """
    Production-grade Groww Market Data Provider.
    Extracts 1m, 5m, 15m historical intraday OHLCV bars for NSE stocks and indices
    over 1+ year without any API keys or subscriptions.
    Handles chunking, rate limiting, and timestamp normalization to Asia/Kolkata.
    """

    BASE_URL = "https://groww.in/v1/api/charting_service/v2/chart/exchange"
    HEADERS = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
        "Accept": "application/json, text/plain, */*",
        "Referer": "https://groww.in/stocks",
    }

    # Symbol mappings for Groww
    SYMBOL_MAP = {
        "ZOMATO": "ETERNAL",
        "TATAMOTORS": "TMPV",
        "NIFTY 50": "NIFTY",
        "NIFTY50": "NIFTY",
        "INDIA VIX": "INDIAVIX",
        "NIFTY FIN SERVICE": "FINNIFTY",
    }

    def __init__(self, request_delay_sec: float = 0.2):
        self.request_delay_sec = request_delay_sec
        self.session = requests.Session()
        self.session.headers.update(self.HEADERS)

    def _resolve_symbol(self, symbol: str) -> str:
        s = symbol.upper().strip()
        return self.SYMBOL_MAP.get(s, s)

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
        Fetch historical bars between start_dt and end_dt.
        Automatically chunks into smaller date ranges for granular intervals (1m, 5m).
        """
        clean_sym = self._resolve_symbol(symbol)
        
        # Determine chunk size in days
        if interval_minutes <= 1:
            chunk_days = 5  # 1m bars ~375 per day -> 5 days ~1875 bars
        elif interval_minutes <= 5:
            chunk_days = 25 # 5m bars ~75 per day -> 25 days ~1875 bars
        else:
            chunk_days = 120 # 15m bars ~25 per day -> 120 days ~3000 bars

        if start_dt.tzinfo is None:
            start_dt = IST.localize(start_dt)
        if end_dt.tzinfo is None:
            end_dt = IST.localize(end_dt)

        all_records = []
        curr_start = start_dt

        while curr_start < end_dt:
            curr_end = min(curr_start + timedelta(days=chunk_days), end_dt)
            start_ms = int(curr_start.timestamp() * 1000)
            end_ms = int(curr_end.timestamp() * 1000)

            url = f"{self.BASE_URL}/{exchange}/segment/{segment}/{clean_sym}"
            params = {
                "startTimeInMillis": start_ms,
                "endTimeInMillis": end_ms,
                "intervalInMinutes": interval_minutes
            }

            try:
                resp = self.session.get(url, params=params, timeout=12)
                if resp.status_code == 200:
                    data = resp.json()
                    candles = data.get("candles", [])
                    for c in candles:
                        # c: [epoch_seconds, open, high, low, close, volume]
                        if len(c) >= 5:
                            vol = float(c[5]) if len(c) >= 6 and c[5] is not None else 0.0
                            all_records.append({
                                "timestamp": datetime.fromtimestamp(c[0], tz=IST),
                                "open": float(c[1]),
                                "high": float(c[2]),
                                "low": float(c[3]),
                                "close": float(c[4]),
                                "volume": vol,
                                "symbol": symbol.upper()
                            })
                else:
                    logger.warning(f"Groww API non-200 [{resp.status_code}] for {clean_sym} ({curr_start} to {curr_end})")
            except Exception as e:
                logger.error(f"Error fetching Groww bars for {clean_sym}: {e}")

            curr_start = curr_end + timedelta(minutes=1)
            if self.request_delay_sec > 0:
                time.sleep(self.request_delay_sec)

        if not all_records:
            return pd.DataFrame(columns=["timestamp", "open", "high", "low", "close", "volume", "symbol"])

        df = pd.DataFrame(all_records)
        df = df.drop_duplicates(subset=["timestamp"]).sort_values("timestamp").reset_index(drop=True)
        return df

    def get_latest_quote(self, symbol: str) -> Dict[str, Any]:
        """Fetch latest quote / tick from Groww."""
        clean_sym = self._resolve_symbol(symbol)
        now_dt = datetime.now(IST)
        start_dt = now_dt - timedelta(days=2)
        start_ms = int(start_dt.timestamp() * 1000)
        end_ms = int(now_dt.timestamp() * 1000)

        url = f"{self.BASE_URL}/NSE/segment/CASH/{clean_sym}"
        params = {
            "startTimeInMillis": start_ms,
            "endTimeInMillis": end_ms,
            "intervalInMinutes": 1
        }

        try:
            resp = self.session.get(url, params=params, timeout=6)
            if resp.status_code == 200:
                candles = resp.json().get("candles", [])
                if candles:
                    last = candles[-1]
                    vol = float(last[5]) if len(last) >= 6 and last[5] is not None else 0.0
                    return {
                        "symbol": symbol.upper(),
                        "timestamp": datetime.fromtimestamp(last[0], tz=IST).isoformat(),
                        "open": float(last[1]),
                        "high": float(last[2]),
                        "low": float(last[3]),
                        "close": float(last[4]),
                        "volume": vol,
                        "status": "LIVE"
                    }
        except Exception as e:
            logger.warning(f"Error fetching latest quote for {symbol}: {e}")

        return {
            "symbol": symbol.upper(),
            "timestamp": now_dt.isoformat(),
            "status": "UNAVAILABLE"
        }
