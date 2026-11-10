from dataclasses import dataclass
from typing import List, Optional, Dict, Any
import pandas as pd
import numpy as np
from datetime import time

@dataclass
class CandidateSetup:
    timestamp: pd.Timestamp
    symbol: str
    direction: str  # "LONG" or "SHORT"
    setup_type: str # "ORB_BREAKOUT", "VWAP_TREND_PULLBACK", "VOL_SQUEEZE_EXPANSION"
    entry_ref_price: float
    bar_index: int
    rvol: float
    clv: float
    atr: float

class CandidateRuleScanner:
    """
    Stage 1: Deterministic Institutional Setup Scanner.
    Filters candidate trade setups strictly between 09:30 IST and 14:15 IST.
    Identifies ORB Breakouts, VWAP Trend Pullbacks, and Volatility Squeeze Expansions.
    """

    START_TIME = time(9, 30)
    END_TIME = time(14, 15)

    @classmethod
    def scan_bars(
        cls,
        symbol: str,
        df: pd.DataFrame,
        sector_df: Optional[pd.DataFrame] = None
    ) -> List[CandidateSetup]:
        """
        Scan a precomputed indicators DataFrame and return all candidate setups.
        """
        setups: List[CandidateSetup] = []
        if len(df) < 25:
            return setups

        for i in range(15, len(df)):
            row = df.iloc[i]
            bar_time = row['timestamp'].time()
            if bar_time < cls.START_TIME or bar_time > cls.END_TIME:
                continue

            close_t = float(row['close'])
            open_t = float(row['open'])
            high_t = float(row['high'])
            low_t = float(row['low'])
            vol_t = float(row['volume'])
            atr_t = max(float(row.get('atr_14', 1.0)), 0.05)
            rvol = float(row.get('volume', 1.0)) / max(float(row.get('mean_vol_tod', 1.0)), 1.0)
            bar_range = max(high_t - low_t, 0.01)
            raw_clv = (2.0 * close_t - high_t - low_t) / bar_range

            orb_h = float(row.get('orb_high', high_t))
            orb_l = float(row.get('orb_low', low_t))
            vwap_val = float(row.get('vwap', close_t))
            ema9 = float(row.get('ema_9', close_t))
            ema21 = float(row.get('ema_21', close_t))
            bb_upper = float(row.get('bb_upper', high_t))
            bb_lower = float(row.get('bb_lower', low_t))
            bb_rank = float(row.get('bb_width_pct_rank_60', 0.5))

            # Pattern 1: ORB_BREAKOUT (Morning momentum window: 09:30 to 11:30 IST)
            if bar_time <= time(11, 30):
                # Long: Bar closes above ORB_High, rvol >= 1.20, clv >= 0.35
                if close_t > orb_h and rvol >= 1.20 and raw_clv >= 0.35:
                    prev_c = float(df.iloc[i - 1]['close'])
                    if prev_c <= orb_h * 1.004:
                        setups.append(CandidateSetup(
                            timestamp=row['timestamp'],
                            symbol=symbol.upper(),
                            direction="LONG",
                            setup_type="ORB_BREAKOUT",
                            entry_ref_price=close_t,
                            bar_index=i,
                            rvol=round(rvol, 2),
                            clv=round(raw_clv, 2),
                            atr=round(atr_t, 2)
                        ))
                        continue

                # Short: Bar closes below ORB_Low, rvol >= 1.20, clv <= -0.35
                if close_t < orb_l and rvol >= 1.20 and raw_clv <= -0.35:
                    prev_c = float(df.iloc[i - 1]['close'])
                    if prev_c >= orb_l * 0.996:
                        setups.append(CandidateSetup(
                            timestamp=row['timestamp'],
                            symbol=symbol.upper(),
                            direction="SHORT",
                            setup_type="ORB_BREAKOUT",
                            entry_ref_price=close_t,
                            bar_index=i,
                            rvol=round(rvol, 2),
                            clv=round(raw_clv, 2),
                            atr=round(atr_t, 2)
                        ))
                        continue

            # Pattern 2: VWAP_TREND_PULLBACK (09:45 to 14:15 IST)
            # Established trend check
            sec_ret_30m = 0.0
            if sector_df is not None and not sector_df.empty:
                s_sub = sector_df[sector_df['timestamp'] <= row['timestamp']]
                if len(s_sub) >= 3:
                    s_c = float(s_sub.iloc[-1]['close'])
                    s_p = float(s_sub.iloc[-3]['close'])
                    sec_ret_30m = (s_c - s_p) / (s_p + 1e-6)

            body_to_atr_val = (close_t - open_t) / atr_t

            # Long pullback
            if close_t > vwap_val and close_t > ema9 and sec_ret_30m >= -0.002:
                prior_bar = df.iloc[i - 1]
                dist_to_pullback = min(abs(float(prior_bar['low']) - vwap_val), abs(float(prior_bar['low']) - ema9))
                if dist_to_pullback <= 0.45 * atr_t and body_to_atr_val >= 0.30:
                    setups.append(CandidateSetup(
                        timestamp=row['timestamp'],
                        symbol=symbol.upper(),
                        direction="LONG",
                        setup_type="VWAP_TREND_PULLBACK",
                        entry_ref_price=close_t,
                        bar_index=i,
                        rvol=round(rvol, 2),
                        clv=round(raw_clv, 2),
                        atr=round(atr_t, 2)
                    ))
                    continue

            # Short pullback
            if close_t < vwap_val and close_t < ema9 and sec_ret_30m <= 0.002:
                prior_bar = df.iloc[i - 1]
                dist_to_pullback = min(abs(float(prior_bar['high']) - vwap_val), abs(float(prior_bar['high']) - ema9))
                if dist_to_pullback <= 0.45 * atr_t and body_to_atr_val <= -0.30:
                    setups.append(CandidateSetup(
                        timestamp=row['timestamp'],
                        symbol=symbol.upper(),
                        direction="SHORT",
                        setup_type="VWAP_TREND_PULLBACK",
                        entry_ref_price=close_t,
                        bar_index=i,
                        rvol=round(rvol, 2),
                        clv=round(raw_clv, 2),
                        atr=round(atr_t, 2)
                    ))
                    continue

            # Pattern 3: VOL_SQUEEZE_EXPANSION
            recent_bb_ranks = [float(df.iloc[k].get('bb_width_pct_rank_60', 0.5)) for k in range(max(0, i - 3), i)]
            was_squeezed = any(r <= 0.35 for r in recent_bb_ranks)

            if was_squeezed and abs(close_t - open_t) >= 0.70 * atr_t and rvol >= 1.15:
                if close_t > open_t and close_t >= bb_upper:
                    setups.append(CandidateSetup(
                        timestamp=row['timestamp'],
                        symbol=symbol.upper(),
                        direction="LONG",
                        setup_type="VOL_SQUEEZE_EXPANSION",
                        entry_ref_price=close_t,
                        bar_index=i,
                        rvol=round(rvol, 2),
                        clv=round(raw_clv, 2),
                        atr=round(atr_t, 2)
                    ))
                    continue
                elif close_t < open_t and close_t <= bb_lower:
                    setups.append(CandidateSetup(
                        timestamp=row['timestamp'],
                        symbol=symbol.upper(),
                        direction="SHORT",
                        setup_type="VOL_SQUEEZE_EXPANSION",
                        entry_ref_price=close_t,
                        bar_index=i,
                        rvol=round(rvol, 2),
                        clv=round(raw_clv, 2),
                        atr=round(atr_t, 2)
                    ))
                    continue

            # Pattern 4: VWAP_MOMENTUM_THRUST (Institutional Intraday Trend Driver)
            if rvol >= 1.15:
                if close_t > vwap_val and close_t > ema9 and raw_clv >= 0.40:
                    prev_c = float(df.iloc[i - 1]['close'])
                    if prev_c <= vwap_val * 1.002: # Clean fresh cross
                        setups.append(CandidateSetup(
                            timestamp=row['timestamp'],
                            symbol=symbol.upper(),
                            direction="LONG",
                            setup_type="VWAP_MOMENTUM_THRUST",
                            entry_ref_price=close_t,
                            bar_index=i,
                            rvol=round(rvol, 2),
                            clv=round(raw_clv, 2),
                            atr=round(atr_t, 2)
                        ))
                        continue
                elif close_t < vwap_val and close_t < ema9 and raw_clv <= -0.40:
                    prev_c = float(df.iloc[i - 1]['close'])
                    if prev_c >= vwap_val * 0.998:
                        setups.append(CandidateSetup(
                            timestamp=row['timestamp'],
                            symbol=symbol.upper(),
                            direction="SHORT",
                            setup_type="VWAP_MOMENTUM_THRUST",
                            entry_ref_price=close_t,
                            bar_index=i,
                            rvol=round(rvol, 2),
                            clv=round(raw_clv, 2),
                            atr=round(atr_t, 2)
                        ))
                        continue

        return setups

