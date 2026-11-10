import json
import os
from datetime import datetime, time, date
from typing import Dict, Any, Tuple, Optional, List
import pytz
import yaml

IST = pytz.timezone("Asia/Kolkata")

class RiskGatekeeper:
    """
    Multi-Gate Pre-Trade Risk Validator & Shock Blocker.
    Strictly verifies all 7 gates before any candidate setup can trigger an active BUY/SHORT signal.
    """

    def __init__(self, config_dir: str = "config"):
        self.config_dir = os.path.abspath(config_dir)
        self.risk_config = self._load_risk_config()
        self.blackout_events = self._load_blackout_events()

    def _load_risk_config(self) -> Dict[str, Any]:
        cfg_path = os.path.join(self.config_dir, "risk_config.yaml")
        if os.path.exists(cfg_path):
            with open(cfg_path, "r", encoding="utf-8") as f:
                return yaml.safe_load(f)
        return {}

    def _load_blackout_events(self) -> Dict[str, Any]:
        bl_path = os.path.join(self.config_dir, "blackout_events.json")
        if os.path.exists(bl_path):
            with open(bl_path, "r", encoding="utf-8") as f:
                return json.load(f)
        return {"macro_events": [], "stock_earnings_blackouts": {}}

    def evaluate_gates(
        self,
        symbol: str,
        current_ts: datetime,
        p_win: float,
        net_target_rs: float,
        net_stop_rs: float,
        day_range_exhaustion: float,
        rvol_time_of_day: float,
        bar_range: float,
        atr_14: float,
        trades_taken_today: int,
        daily_net_pnl: float
    ) -> Dict[str, Any]:
        """
        Evaluate candidate setup against all 7 gates.
        Returns:
          passed: bool
          gate_results: Dict[str, bool]
          rejection_reasons: List[str]
          ev_rs: float
        """
        rejection_reasons = []
        gate_results = {}

        # Gate 1: Calibrated Edge (P(Win) >= threshold)
        min_p = self.risk_config.get("trade_guardrails", {}).get("min_p_win", 0.48)
        g1_pass = p_win >= min_p
        gate_results[f"Gate 1 - Calibrated Edge (P >= {int(min_p*100)}%)"] = g1_pass
        if not g1_pass:
            rejection_reasons.append(f"Calibrated win probability {p_win*100:.1f}% is below required {min_p*100:.0f}% threshold.")

        # Gate 2: Net Rupee Expectancy
        # Incorporates the dynamic breakeven protection factor (~35% of non-target exits at cost)
        effective_stop = 0.70 * abs(net_stop_rs)
        expected_ev = p_win * net_target_rs - (1.0 - p_win) * effective_stop
        min_ev = self.risk_config.get("trade_guardrails", {}).get("min_expected_net_ev", 10.0)
        g2_pass = expected_ev >= min_ev
        gate_results[f"Gate 2 - Net Rupee Expectancy (>= +₹{min_ev:.0f})"] = g2_pass
        if not g2_pass:
            rejection_reasons.append(f"Net Rupee Expectancy +₹{expected_ev:.1f} is below minimum threshold +₹{min_ev:.1f}.")

        # Gate 3: Fuel Remaining (day_range_exhaustion <= 0.78)
        max_exhaustion = self.risk_config.get("shock_filters", {}).get("max_day_range_exhaustion", 0.78)
        g3_pass = day_range_exhaustion <= max_exhaustion
        gate_results["Gate 3 - Intraday Fuel Remaining (<= 78%)"] = g3_pass
        if not g3_pass:
            rejection_reasons.append(f"Daily range exhaustion {day_range_exhaustion*100:.1f}% exceeds 78% limit (stock already spent its daily move).")

        # Gate 4: Anti-News Shock Filter (RVOL <= 5.0, bar_range <= 2.5*ATR)
        max_rvol = self.risk_config.get("shock_filters", {}).get("max_rvol_time_of_day", 5.0)
        max_bar_atr = self.risk_config.get("shock_filters", {}).get("max_bar_range_atr_multiple", 2.5)

        date_str = current_ts.strftime("%Y-%m-%d")
        earnings_blackouts = self.blackout_events.get("stock_earnings_blackouts", {}).get(symbol.upper(), [])
        macro_blackouts = [m["date"] for m in self.blackout_events.get("macro_events", [])]
        is_blackout = (date_str in earnings_blackouts) or (date_str in macro_blackouts)

        is_freak_bar = (rvol_time_of_day > max_rvol) or (bar_range > max_bar_atr * max(atr_14, 0.05))
        g4_pass = not is_freak_bar
        gate_results["Gate 4 - Anti-News & Shock Filter"] = g4_pass
        if is_blackout:
            rejection_reasons.append(f"Caution: Date {date_str} is flagged as earnings/macro date for {symbol}.")
        if is_freak_bar:
            rejection_reasons.append(f"Freak bar anomaly detected (RVOL: {rvol_time_of_day:.1f}x or bar range > {max_bar_atr}x ATR).")

        # Gate 5: Time Window (09:30 to 14:15 IST, lunch lull 12:00-13:15 requires P >= 0.68)
        c_time = current_ts.time()
        start_t = time(9, 30)
        end_t = time(14, 15)
        lunch_s = time(12, 0)
        lunch_e = time(13, 15)

        in_session = start_t <= c_time <= end_t
        in_lunch = lunch_s <= c_time <= lunch_e
        if in_session:
            if in_lunch:
                g5_pass = p_win >= 0.68
                if not g5_pass:
                    rejection_reasons.append(f"Lunch hour lull (12:00-13:15 IST) requires elevated conviction P(Win) >= 68%.")
            else:
                g5_pass = True
        else:
            g5_pass = False
            rejection_reasons.append(f"Current time {c_time.strftime('%H:%M')} is outside active signal window (09:30-14:15 IST).")
        gate_results["Gate 5 - Session & Lunch Window"] = g5_pass

        # Gate 6: Max Daily Trade Cap (trades_taken_today < 2)
        max_trades = self.risk_config.get("trade_guardrails", {}).get("max_daily_trades", 2)
        g6_pass = trades_taken_today < max_trades
        gate_results["Gate 6 - Max Daily Trades (< 2)"] = g6_pass
        if not g6_pass:
            rejection_reasons.append(f"Daily limit of {max_trades} trades has been reached for today.")

        # Gate 7: Daily Profit Lock / Loss Circuit Breaker (-₹190 to +₹280)
        min_daily = self.risk_config.get("trade_guardrails", {}).get("daily_stop_loss_limit", -190.0)
        max_daily = self.risk_config.get("trade_guardrails", {}).get("daily_profit_lock_limit", 280.0)
        g7_pass = (daily_net_pnl > min_daily) and (daily_net_pnl < max_daily)
        gate_results["Gate 7 - Daily Profit Lock / Circuit Breaker"] = g7_pass
        if daily_net_pnl <= min_daily:
            rejection_reasons.append(f"Daily stop loss circuit breaker hit (Net PnL ₹{daily_net_pnl:.1f} <= -₹190). App locked for today.")
        elif daily_net_pnl >= max_daily:
            rejection_reasons.append(f"Daily profit lock triggered (Net PnL +₹{daily_net_pnl:.1f} >= +₹280). Profits protected for the session!")

        all_passed = all([g1_pass, g2_pass, g3_pass, g4_pass, g5_pass, g6_pass, g7_pass])

        return {
            "all_passed": all_passed,
            "gate_results": gate_results,
            "rejection_reasons": rejection_reasons,
            "expected_ev_rs": round(expected_ev, 2)
        }

