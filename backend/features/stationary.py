import numpy as np
import pandas as pd
from typing import Dict, Any, Optional

EPS = 1e-6

class StationaryFeatureEngine:
    """
    Computes 22 strictly stationary, scale-invariant features for intraday meta-labeling.
    Never passes raw rupee prices, raw volume levels, or non-stationary moving averages.
    Ensures zero future leakage (features at bar t only depend on information <= t).
    """

    FEATURE_NAMES = [
        "body_to_atr",
        "favorable_wick_ratio",
        "adverse_wick_ratio",
        "close_location_value",
        "three_bar_momentum_atr",
        "rvol_time_of_day",
        "up_down_vol_ratio_5",
        "vol_price_corr_6",
        "cum_day_rvol",
        "vwap_z_score",
        "ema9_dist_atr",
        "ema9_ema21_spread_atr",
        "orb_range_to_daily_atr",
        "prev_day_va_position",
        "overnight_gap_to_atr",
        "kaufman_efficiency_10",
        "bb_width_pct_rank_60",
        "day_range_exhaustion",
        "atr_pct_current",
        "sector_rel_strength_30m",
        "sector_vs_nifty_30m",
        "india_vix_regime"
    ]

    @staticmethod
    def compute_indicators(df: pd.DataFrame) -> pd.DataFrame:
        """
        Precompute intraday running indicators (VWAP, EMA9, EMA21, ATR, Bollinger, ORB).
        Strictly resets intraday anchors (VWAP, Cumulative Volume, Day High/Low, ORB) at 09:15 each day.
        """
        df = df.copy()
        if 'date' not in df.columns:
            df['date'] = df['timestamp'].dt.date

        # True Range and ATR 14
        prev_close = df['close'].shift(1)
        tr1 = df['high'] - df['low']
        tr2 = (df['high'] - prev_close).abs()
        tr3 = (df['low'] - prev_close).abs()
        df['true_range'] = np.maximum(tr1, np.maximum(tr2, tr3))
        df['atr_14'] = df['true_range'].rolling(window=14, min_periods=1).mean()

        # EMAs
        df['ema_9'] = df['close'].ewm(span=9, adjust=False).mean()
        df['ema_21'] = df['close'].ewm(span=21, adjust=False).mean()

        # Bollinger Bands (20, 2)
        df['bb_mid'] = df['close'].rolling(window=20, min_periods=1).mean()
        df['bb_std'] = df['close'].rolling(window=20, min_periods=1).std().fillna(0)
        df['bb_upper'] = df['bb_mid'] + 2.0 * df['bb_std']
        df['bb_lower'] = df['bb_mid'] - 2.0 * df['bb_std']
        df['bb_width'] = (df['bb_upper'] - df['bb_lower']) / (df['bb_mid'] + EPS)

        # 60-bar percentile rank of bb_width
        def rolling_pct_rank(s):
            return s.rolling(window=60, min_periods=5).apply(
                lambda x: pd.Series(x).rank(pct=True).iloc[-1] if len(x) > 0 else 0.5,
                raw=False
            )
        df['bb_width_pct_rank_60'] = rolling_pct_rank(df['bb_width']).fillna(0.5)

        # Per-day running anchors
        df['time_str'] = df['timestamp'].dt.strftime('%H:%M')
        df['pv'] = df['close'] * df['volume']
        df['cum_vol'] = df.groupby('date')['volume'].cumsum()
        df['cum_pv'] = df.groupby('date')['pv'].cumsum()
        df['vwap'] = df['cum_pv'] / (df['cum_vol'] + EPS)

        # Intraday VWAP deviation std
        df['vwap_dev'] = df['close'] - df['vwap']
        df['vwap_std'] = df.groupby('date')['vwap_dev'].transform(lambda g: g.expanding().std()).fillna(1.0)
        df['vwap_std'] = np.maximum(df['vwap_std'], 0.1)

        # Day High / Day Low so far
        df['day_high_so_far'] = df.groupby('date')['high'].cummax()
        df['day_low_so_far'] = df.groupby('date')['low'].cummin()

        # ORB (09:15 to 09:30 candle)
        orb_mask = df['time_str'] == '09:15'
        df['orb_high'] = df[orb_mask].groupby('date')['high'].transform('max')
        df['orb_low'] = df[orb_mask].groupby('date')['low'].transform('min')
        df['orb_high'] = df.groupby('date')['orb_high'].ffill()
        df['orb_low'] = df.groupby('date')['orb_low'].ffill()

        # Prior Day High, Low, Close
        daily_stats = df.groupby('date').agg(
            d_high=('high', 'max'),
            d_low=('low', 'min'),
            d_close=('close', 'last')
        ).shift(1)
        
        df = df.merge(daily_stats, on='date', how='left')
        df['d_range_20d_mean'] = (df['d_high'] - df['d_low']).rolling(20, min_periods=1).mean().fillna(df['high'] - df['low'])
        df['daily_atr_14'] = (df['d_high'] - df['d_low']).rolling(14, min_periods=1).mean().fillna(df['atr_14'])

        # Time of day historical volume mean (20 days)
        time_slot_means = df.groupby('time_str')['volume'].transform(lambda s: s.rolling(20, min_periods=1).mean())
        df['mean_vol_tod'] = time_slot_means.fillna(df['volume'] + EPS)

        # Cumulative time of day volume mean
        cum_time_means = df.groupby('time_str')['cum_vol'].transform(lambda s: s.rolling(20, min_periods=1).mean())
        df['mean_cum_vol_tod'] = cum_time_means.fillna(df['cum_vol'] + EPS)

        return df

    @classmethod
    def extract_features_at_index(
        cls,
        df: pd.DataFrame,
        idx: int,
        direction: str,
        sector_df: Optional[pd.DataFrame] = None,
        nifty_df: Optional[pd.DataFrame] = None,
        vix_df: Optional[pd.DataFrame] = None
    ) -> Dict[str, float]:
        """
        Extract the 22 stationary features strictly at index `idx` for candidate setup.
        direction: "LONG" or "SHORT"
        """
        dir_mult = 1.0 if direction.upper() in ("LONG", "BUY") else -1.0
        row = df.iloc[idx]

        close_t = float(row['close'])
        open_t = float(row['open'])
        high_t = float(row['high'])
        low_t = float(row['low'])
        vol_t = float(row['volume'])
        atr_t = max(float(row.get('atr_14', 1.0)), EPS)
        bar_range = max(high_t - low_t, EPS)

        # 1. Candlestick Microstructure
        # body_to_atr: signed by trade direction so +1 always favors trade
        body_to_atr = dir_mult * (close_t - open_t) / atr_t

        upper_wick = high_t - max(open_t, close_t)
        lower_wick = min(open_t, close_t) - low_t

        if dir_mult > 0: # LONG
            favorable_wick = lower_wick
            adverse_wick = upper_wick
        else: # SHORT
            favorable_wick = upper_wick
            adverse_wick = lower_wick

        favorable_wick_ratio = favorable_wick / bar_range
        adverse_wick_ratio = adverse_wick / bar_range

        # close_location_value: direction * (2C - H - L)/(H - L)
        close_location_value = dir_mult * (2.0 * close_t - high_t - low_t) / bar_range

        # three_bar_momentum_atr: direction * (C_t - O_{t-2}) / ATR_14
        if idx >= 2:
            open_t2 = float(df.iloc[idx - 2]['open'])
            three_bar_momentum_atr = dir_mult * (close_t - open_t2) / atr_t
        else:
            three_bar_momentum_atr = body_to_atr

        # 2. Volume & Institutional Order Flow
        mean_vol_tod = max(float(row.get('mean_vol_tod', vol_t)), EPS)
        rvol_time_of_day = vol_t / mean_vol_tod

        # up_down_vol_ratio_5
        start_idx5 = max(0, idx - 4)
        sub5 = df.iloc[start_idx5:idx + 1]
        if dir_mult > 0:
            fav_vol = sub5[sub5['close'] >= sub5['open']]['volume'].sum()
            adv_vol = sub5[sub5['close'] < sub5['open']]['volume'].sum()
        else:
            fav_vol = sub5[sub5['close'] <= sub5['open']]['volume'].sum()
            adv_vol = sub5[sub5['close'] > sub5['open']]['volume'].sum()
        up_down_vol_ratio_5 = (fav_vol + 1.0) / (adv_vol + 1.0)

        # vol_price_corr_6
        start_idx6 = max(0, idx - 5)
        sub6 = df.iloc[start_idx6:idx + 1]
        if len(sub6) >= 4:
            price_diffs = dir_mult * sub6['close'].diff().dropna()
            vols = sub6['volume'].iloc[1:]
            if price_diffs.std() > EPS and vols.std() > EPS:
                vol_price_corr_6 = float(np.corrcoef(price_diffs, vols)[0, 1])
                if np.isnan(vol_price_corr_6):
                    vol_price_corr_6 = 0.0
            else:
                vol_price_corr_6 = 0.0
        else:
            vol_price_corr_6 = 0.0

        # cum_day_rvol
        cum_vol = float(row.get('cum_vol', vol_t))
        mean_cum_vol = max(float(row.get('mean_cum_vol_tod', cum_vol)), EPS)
        cum_day_rvol = cum_vol / mean_cum_vol

        # 3. Intraday Anchors & Trend Geometry
        vwap_val = float(row.get('vwap', close_t))
        vwap_std = max(float(row.get('vwap_std', 1.0)), EPS)
        vwap_z_score = dir_mult * (close_t - vwap_val) / vwap_std

        ema9 = float(row.get('ema_9', close_t))
        ema21 = float(row.get('ema_21', close_t))
        ema9_dist_atr = dir_mult * (close_t - ema9) / atr_t
        ema9_ema21_spread_atr = dir_mult * (ema9 - ema21) / atr_t

        daily_atr = max(float(row.get('daily_atr_14', atr_t * 3)), EPS)
        orb_h = float(row.get('orb_high', high_t))
        orb_l = float(row.get('orb_low', low_t))
        orb_range_to_daily_atr = (orb_h - orb_l) / daily_atr

        pd_h = row.get('d_high')
        pd_l = row.get('d_low')
        pd_c = row.get('d_close')
        if pd.isna(pd_h) or pd.isna(pd_l) or pd.isna(pd_c):
            prev_day_va_position = 0.0
            overnight_gap_to_atr = 0.0
        else:
            pd_h = float(pd_h)
            pd_l = float(pd_l)
            pd_c = float(pd_c)
            pd_range = max(pd_h - pd_l, EPS)
            if dir_mult > 0:
                prev_day_va_position = (close_t - pd_c) / pd_range
            else:
                prev_day_va_position = (pd_c - close_t) / pd_range

            day_open = float(df[df['date'] == row['date']].iloc[0]['open'])
            overnight_gap_to_atr = dir_mult * (day_open - pd_c) / daily_atr

        # 4. Choppiness, Regime & Fuel Exhaustion
        if idx >= 10:
            sub10 = df.iloc[idx - 10:idx + 1]
            net_change = abs(close_t - float(sub10.iloc[0]['close']))
            path_sum = sub10['close'].diff().abs().sum()
            kaufman_efficiency_10 = net_change / max(path_sum, EPS)
        else:
            kaufman_efficiency_10 = 0.5

        bb_width_pct_rank_60 = float(row.get('bb_width_pct_rank_60', 0.5))
        
        day_h = float(row.get('day_high_so_far', high_t))
        day_l = float(row.get('day_low_so_far', low_t))
        d_range_mean = max(float(row.get('d_range_20d_mean', daily_atr)), EPS)
        day_range_exhaustion = (day_h - day_l) / d_range_mean

        atr_pct_current = atr_t / max(close_t, EPS)

        # 5. Cross-Sectional Context
        # Sector relative strength 30m
        stock_ret_30m = (close_t - float(df.iloc[max(0, idx - 2)]['close'])) / (float(df.iloc[max(0, idx - 2)]['close']) + EPS)
        sector_ret_30m = 0.0
        nifty_ret_30m = 0.0

        curr_ts = row['timestamp']
        if sector_df is not None and not sector_df.empty:
            sec_sub = sector_df[sector_df['timestamp'] <= curr_ts]
            if len(sec_sub) >= 3:
                s_c = float(sec_sub.iloc[-1]['close'])
                s_prev = float(sec_sub.iloc[-3]['close'])
                sector_ret_30m = (s_c - s_prev) / (s_prev + EPS)

        if nifty_df is not None and not nifty_df.empty:
            nif_sub = nifty_df[nifty_df['timestamp'] <= curr_ts]
            if len(nif_sub) >= 3:
                n_c = float(nif_sub.iloc[-1]['close'])
                n_prev = float(nif_sub.iloc[-3]['close'])
                nifty_ret_30m = (n_c - n_prev) / (n_prev + EPS)

        sector_rel_strength_30m = dir_mult * (stock_ret_30m - sector_ret_30m)
        sector_vs_nifty_30m = dir_mult * (sector_ret_30m - nifty_ret_30m)

        # India VIX level and 30m change
        vix_level = 14.0
        vix_chg_30m = 0.0
        if vix_df is not None and not vix_df.empty:
            v_sub = vix_df[vix_df['timestamp'] <= curr_ts]
            if len(v_sub) >= 1:
                vix_level = float(v_sub.iloc[-1]['close'])
            if len(v_sub) >= 3:
                v_prev = float(v_sub.iloc[-3]['close'])
                vix_chg_30m = (vix_level - v_prev) / (v_prev + EPS)
        
        # Normalized vix regime: positive = lower vix (supportive for equities), negative = spiking vix
        india_vix_regime = (15.0 - vix_level) / 10.0 - (vix_chg_30m * 2.0)

        feats = {
            "body_to_atr": float(np.clip(np.nan_to_num(body_to_atr, nan=0.0), -3.0, 3.0)),
            "favorable_wick_ratio": float(np.clip(np.nan_to_num(favorable_wick_ratio, nan=0.0), 0.0, 1.0)),
            "adverse_wick_ratio": float(np.clip(np.nan_to_num(adverse_wick_ratio, nan=0.0), 0.0, 1.0)),
            "close_location_value": float(np.clip(np.nan_to_num(close_location_value, nan=0.0), -1.0, 1.0)),
            "three_bar_momentum_atr": float(np.clip(np.nan_to_num(three_bar_momentum_atr, nan=0.0), -4.0, 4.0)),
            "rvol_time_of_day": float(np.clip(np.nan_to_num(rvol_time_of_day, nan=1.0), 0.0, 10.0)),
            "up_down_vol_ratio_5": float(np.clip(np.nan_to_num(up_down_vol_ratio_5, nan=1.0), 0.0, 15.0)),
            "vol_price_corr_6": float(np.clip(np.nan_to_num(vol_price_corr_6, nan=0.0), -1.0, 1.0)),
            "cum_day_rvol": float(np.clip(np.nan_to_num(cum_day_rvol, nan=1.0), 0.0, 5.0)),
            "vwap_z_score": float(np.clip(np.nan_to_num(vwap_z_score, nan=0.0), -5.0, 5.0)),
            "ema9_dist_atr": float(np.clip(np.nan_to_num(ema9_dist_atr, nan=0.0), -4.0, 4.0)),
            "ema9_ema21_spread_atr": float(np.clip(np.nan_to_num(ema9_ema21_spread_atr, nan=0.0), -3.0, 3.0)),
            "orb_range_to_daily_atr": float(np.clip(np.nan_to_num(orb_range_to_daily_atr, nan=0.5), 0.0, 3.0)),
            "prev_day_va_position": float(np.clip(np.nan_to_num(prev_day_va_position, nan=0.0), -3.0, 3.0)),
            "overnight_gap_to_atr": float(np.clip(np.nan_to_num(overnight_gap_to_atr, nan=0.0), -3.0, 3.0)),
            "kaufman_efficiency_10": float(np.clip(np.nan_to_num(kaufman_efficiency_10, nan=0.5), 0.0, 1.0)),
            "bb_width_pct_rank_60": float(np.clip(np.nan_to_num(bb_width_pct_rank_60, nan=0.5), 0.0, 1.0)),
            "day_range_exhaustion": float(np.clip(np.nan_to_num(day_range_exhaustion, nan=0.5), 0.0, 2.0)),
            "atr_pct_current": float(np.clip(np.nan_to_num(atr_pct_current, nan=0.01), 0.0, 0.1)),
            "sector_rel_strength_30m": float(np.clip(np.nan_to_num(sector_rel_strength_30m, nan=0.0), -0.1, 0.1)),
            "sector_vs_nifty_30m": float(np.clip(np.nan_to_num(sector_vs_nifty_30m, nan=0.0), -0.1, 0.1)),
            "india_vix_regime": float(np.clip(np.nan_to_num(india_vix_regime, nan=0.0), -2.0, 2.0))
        }

        return feats
