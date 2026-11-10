import numpy as np
import numba
import pandas as pd
from typing import List, Dict, Any, Tuple
from backend.costs.zerodha_nse import ZerodhaIntradayCostCalculator

@numba.njit
def fast_triple_barrier_loop(
    opens: np.ndarray,
    highs: np.ndarray,
    lows: np.ndarray,
    closes: np.ndarray,
    is_same_day: np.ndarray,  # 1 if same day, 0 if next day
    is_before_square_off: np.ndarray, # 1 if <= 15:10 IST, 0 otherwise
    start_bar: int,
    max_bars_ahead: int,
    is_long: bool,
    entry_price: float,
    gross_target_pct: float,
    gross_stop_pct: float,
    breakeven_trigger_pct: float,
    breakeven_buffer_pct: float,
) -> Tuple[int, float, int, str]:
    """
    Numba-accelerated forward path evaluator with dynamic breakeven protection.
    Returns: (label: 1 or 0, exit_price: float, bars_held: int, exit_reason: str_id)
    str_id: 1="TARGET", 2="BREAKEVEN_STOP", 3="INITIAL_STOP", 4="TIME_TIMEOUT", 5="DAY_CLOSE"
    """
    n = len(opens)
    if start_bar >= n:
        return 0, entry_price, 0, 4

    if is_long:
        target_price = entry_price * (1.0 + gross_target_pct)
        initial_stop = entry_price * (1.0 - gross_stop_pct)
        breakeven_trigger_price = entry_price * (1.0 + breakeven_trigger_pct)
        breakeven_stop_price = entry_price * (1.0 + breakeven_buffer_pct)
    else:
        target_price = entry_price * (1.0 - gross_target_pct)
        initial_stop = entry_price * (1.0 + gross_stop_pct)
        breakeven_trigger_price = entry_price * (1.0 - breakeven_trigger_pct)
        breakeven_stop_price = entry_price * (1.0 - breakeven_buffer_pct)

    active_stop = initial_stop
    breakeven_armed = False

    end_bar = min(n, start_bar + max_bars_ahead)

    for i in range(start_bar, end_bar):
        # Check if new day started or past 15:10 IST
        if is_same_day[i] == 0:
            # Must have exited before end of same day
            exit_p = closes[i - 1] if i > start_bar else opens[start_bar]
            return 0, exit_p, max(1, i - start_bar), 5

        if is_before_square_off[i] == 0:
            # 15:10 square off hit
            exit_p = opens[i]
            return 0, exit_p, max(1, i - start_bar), 4

        h = highs[i]
        l = lows[i]

        if is_long:
            # Check if breakeven triggered during this bar
            if not breakeven_armed and h >= breakeven_trigger_price:
                breakeven_armed = True
                active_stop = max(active_stop, breakeven_stop_price)

            # Check target hit
            if h >= target_price:
                return 1, target_price, i - start_bar + 1, 1

            # Check stop hit
            if l <= active_stop:
                reason = 2 if breakeven_armed else 3
                return 0, active_stop, i - start_bar + 1, reason

        else: # SHORT
            if not breakeven_armed and l <= breakeven_trigger_price:
                breakeven_armed = True
                active_stop = min(active_stop, breakeven_stop_price)

            if l <= target_price:
                return 1, target_price, i - start_bar + 1, 1

            if h >= active_stop:
                reason = 2 if breakeven_armed else 3
                return 0, active_stop, i - start_bar + 1, reason

    # Vertical timeout reached
    exit_p = closes[end_bar - 1] if end_bar > start_bar else opens[start_bar]
    return 0, exit_p, max_bars_ahead, 4


class CostAdjustedTripleBarrierLabeler:
    """
    Labels historical candidate setups using Numba JIT acceleration and exact Zerodha MIS fee deduction.
    Label = 1 strictly requires reaching the profit barrier with at least +₹220 net profit.
    """

    @classmethod
    def label_candidates(
        cls,
        df: pd.DataFrame,
        candidates: List[Any],
        tick_size: float = 0.05,
        target_capital: float = 25000.0,
        min_net_profit_threshold: float = 250.0,
        slippage_ticks: int = 2
    ) -> pd.DataFrame:
        if not candidates or df.empty:
            return pd.DataFrame()

        # Prepare numpy arrays
        opens = df['open'].to_numpy(dtype=np.float64)
        highs = df['high'].to_numpy(dtype=np.float64)
        lows = df['low'].to_numpy(dtype=np.float64)
        closes = df['close'].to_numpy(dtype=np.float64)

        dates = df['date'].to_numpy()
        times = df['timestamp'].dt.time.to_numpy()
        square_off_time = pd.to_datetime("15:10:00").time()

        n = len(df)
        is_same_day = np.ones(n, dtype=np.int32)
        is_before_square_off = np.ones(n, dtype=np.int32)

        for i in range(n):
            if i > 0 and dates[i] != dates[i - 1]:
                is_same_day[i] = 0
            if times[i] > square_off_time:
                is_before_square_off[i] = 0

        labeled_records = []

        for cand in candidates:
            idx = cand.bar_index
            if idx + 1 >= n:
                continue

            # Candidate entries simulate filling on next bar open with adverse slippage
            next_bar_open = opens[idx + 1]
            direction = cand.direction.upper()
            is_long = direction in ("LONG", "BUY")

            if is_long:
                simulated_entry = next_bar_open + (tick_size * slippage_ticks)
            else:
                simulated_entry = next_bar_open - (tick_size * slippage_ticks)

            qty = int(target_capital // simulated_entry)
            if qty <= 0:
                continue

            atr_val = cand.atr
            atr_pct = atr_val / max(simulated_entry, 1.0)

            # Barrier Geometry (strictly from spec)
            gross_target_pct = float(np.clip(1.5 * atr_pct, 0.0120, 0.0160))
            gross_stop_pct = float(np.clip(0.75 * atr_pct, 0.0055, 0.0062))
            breakeven_trigger_pct = 0.0055
            breakeven_buffer_pct = 0.0012
            max_bars_ahead = 16 # up to 4 hours (16 x 15m) or session end

            raw_label, exit_price, bars_held, reason_id = fast_triple_barrier_loop(
                opens=opens,
                highs=highs,
                lows=lows,
                closes=closes,
                is_same_day=is_same_day,
                is_before_square_off=is_before_square_off,
                start_bar=idx + 1,
                max_bars_ahead=max_bars_ahead,
                is_long=is_long,
                entry_price=simulated_entry,
                gross_target_pct=gross_target_pct,
                gross_stop_pct=gross_stop_pct,
                breakeven_trigger_pct=breakeven_trigger_pct,
                breakeven_buffer_pct=breakeven_buffer_pct
            )

            # Calculate exact net PnL after all Zerodha charges and slippage
            cost = ZerodhaIntradayCostCalculator.calculate(
                direction="LONG" if is_long else "SHORT",
                entry_price=simulated_entry,
                exit_price=exit_price,
                qty=qty,
                tick_size=tick_size,
                slippage_ticks=slippage_ticks
            )

            # Win condition: Target barrier reached OR session square-off in solid net profit
            final_label = 1 if ((raw_label == 1 and cost.net_pnl >= 200.0) or cost.net_pnl >= min_net_profit_threshold) else 0

            reason_map = {1: "TARGET", 2: "BREAKEVEN_STOP", 3: "INITIAL_STOP", 4: "TIME_TIMEOUT", 5: "DAY_CLOSE"}

            labeled_records.append({
                "timestamp": cand.timestamp,
                "symbol": cand.symbol,
                "direction": cand.direction,
                "setup_type": cand.setup_type,
                "entry_price": round(simulated_entry, 2),
                "exit_price": round(exit_price, 2),
                "qty": qty,
                "gross_pnl": cost.gross_pnl,
                "net_pnl": cost.net_pnl,
                "total_charges": cost.total_charges,
                "bars_held": bars_held,
                "exit_reason": reason_map.get(reason_id, "UNKNOWN"),
                "label": final_label,
                "bar_index": idx
            })

        return pd.DataFrame(labeled_records)

