import os
import json
import logging
from dataclasses import dataclass, field
from datetime import datetime, time
from typing import Optional, Dict, Any, List
import pytz
from backend.costs.zerodha_nse import ZerodhaIntradayCostCalculator, CostBreakdown

logger = logging.getLogger("TradeMonitor")
IST = pytz.timezone("Asia/Kolkata")

@dataclass
class ActiveTrade:
    trade_id: str
    symbol: str
    direction: str  # "LONG" or "SHORT"
    entry_price: float
    qty: int
    target_price: float
    initial_stop_price: float
    breakeven_trigger_price: float
    breakeven_stop_price: float
    tick_size: float = 0.05
    entry_time: datetime = field(default_factory=lambda: datetime.now(IST))
    status: str = "IN_PROGRESS"  # IN_PROGRESS, BREAKEVEN_ARMED, CLOSED
    current_price: float = 0.0
    highest_price: float = 0.0
    lowest_price: float = 999999.0
    active_stop_price: float = 0.0
    realized_net_pnl: float = 0.0
    exit_price: Optional[float] = None
    exit_time: Optional[datetime] = None
    exit_action: Optional[str] = None
    exit_instructions: Optional[str] = None
    audio_alert_type: Optional[str] = None # "BREAKEVEN_CHIME", "TARGET_CHIME", "REVERSAL_CHIME", "STOP_CHIME"

class TradeMonitor:
    """
    Real-time Live Trade State and Exit Monitor.
    Tracks active user positions entered on Zerodha Kite and issues instant
    audio/visual management instructions (MOVE_TO_BREAKEVEN, TAKE_PROFIT, EARLY_REVERSAL, STOP_LOSS).
    """

    def __init__(self, persistence_file: str = "data/paper_trades.json"):
        self.persistence_file = os.path.abspath(persistence_file)
        self.active_trade: Optional[ActiveTrade] = None
        self.completed_trades: List[Dict[str, Any]] = []
        self.auto_paper_trading: bool = True
        self._load_completed_trades()

    def _load_completed_trades(self):
        """Loads persistent paper trading history from disk."""
        if os.path.exists(self.persistence_file):
            try:
                with open(self.persistence_file, "r", encoding="utf-8") as f:
                    self.completed_trades = json.load(f)
                logger.info(f"Loaded {len(self.completed_trades)} historical paper trades from {self.persistence_file}")
            except Exception as e:
                logger.warning(f"Could not load paper trades: {e}")

    def _save_completed_trades(self):
        """Persists paper trading history to disk."""
        try:
            os.makedirs(os.path.dirname(self.persistence_file), exist_ok=True)
            with open(self.persistence_file, "w", encoding="utf-8") as f:
                json.dump(self.completed_trades, f, indent=2)
        except Exception as e:
            logger.error(f"Failed to persist paper trades: {e}")

    def maybe_auto_enter_trade(self, signal: Dict[str, Any]) -> Optional[ActiveTrade]:
        """
        If auto paper trading is enabled and no trade is currently open,
        automatically enters paper trade on high-conviction actionable signals.
        """
        if not self.auto_paper_trading:
            return None
        if self.active_trade is not None and self.active_trade.status != "CLOSED":
            return None
        if not signal.get("is_actionable", False):
            return None

        # Check today's trade count (allows high-velocity testing up to 25 trades/day)
        today_str = datetime.now(IST).strftime("%Y-%m-%d")
        trades_today = sum(1 for t in self.completed_trades if t.get("entry_time", "").startswith(today_str))
        if trades_today >= 25:
            logger.info("Max daily trades limit (25) reached; auto paper trade paused.")
            return None

        sym = signal["symbol"]
        direction = signal["direction"]
        entry_p = float(signal["entry_limit_price"])
        qty = int(signal["quantity"])
        target_p = float(signal["target_price"])
        stop_p = float(signal["stop_loss_price"])

        logger.info(f"[AUTO-PAPER-TRADING] Automatically entering trade: {direction} {sym} {qty} shares @ ₹{entry_p}")
        trade = self.start_trade(
            symbol=sym,
            direction=direction,
            entry_price=entry_p,
            qty=qty,
            target_price=target_p,
            stop_price=stop_p,
            tick_size=signal.get("tick_size", 0.05)
        )
        return trade

    def start_trade(
        self,
        symbol: str,
        direction: str,
        entry_price: float,
        qty: int,
        target_price: float,
        stop_price: float,
        tick_size: float = 0.05
    ) -> ActiveTrade:
        is_long = direction.upper() in ("LONG", "BUY")
        if is_long:
            be_trigger = entry_price * (1.0 + 0.0035)
            be_stop = entry_price * (1.0 + 0.0010)
        else:
            be_trigger = entry_price * (1.0 - 0.0035)
            be_stop = entry_price * (1.0 - 0.0010)

        now_dt = datetime.now(IST)
        trade = ActiveTrade(
            trade_id=f"TRD-{now_dt.strftime('%H%M%S')}",
            symbol=symbol.upper(),
            direction=direction.upper(),
            entry_price=round(entry_price, 2),
            qty=qty,
            target_price=round(target_price, 2),
            initial_stop_price=round(stop_price, 2),
            breakeven_trigger_price=round(be_trigger, 2),
            breakeven_stop_price=round(be_stop, 2),
            tick_size=tick_size,
            entry_time=now_dt,
            current_price=round(entry_price, 2),
            highest_price=round(entry_price, 2),
            lowest_price=round(entry_price, 2),
            active_stop_price=round(stop_price, 2)
        )
        self.active_trade = trade
        return trade

    def update_tick(
        self,
        current_price: float,
        bar_high: Optional[float] = None,
        bar_low: Optional[float] = None,
        vwap_val: Optional[float] = None,
        volume_bias_reversal: bool = False,
        current_time: Optional[datetime] = None
    ) -> Optional[Dict[str, Any]]:
        """
        Evaluate live market tick against active trade boundaries.
        Returns alert payload if state changes or exit triggers.
        """
        trade = self.active_trade
        if trade is None or trade.status == "CLOSED":
            return None

        if current_time is None:
            current_time = datetime.now(IST)

        high_val = bar_high if bar_high is not None else current_price
        low_val = bar_low if bar_low is not None else current_price

        trade.current_price = round(current_price, 2)
        trade.highest_price = max(trade.highest_price, high_val)
        trade.lowest_price = min(trade.lowest_price, low_val)

        is_long = trade.direction in ("LONG", "BUY")

        # Check Event 1: MOVE STOP-LOSS TO BREAKEVEN (+0.55% reached)
        if trade.status == "IN_PROGRESS":
            if (is_long and high_val >= trade.breakeven_trigger_price) or \
               ((not is_long) and low_val <= trade.breakeven_trigger_price):
                trade.status = "BREAKEVEN_ARMED"
                trade.active_stop_price = trade.breakeven_stop_price
                trade.audio_alert_type = "BREAKEVEN_CHIME"
                trade.exit_instructions = (
                    f"🟡 BREAKEVEN ALERT! Price reached +0.35% excursion. "
                    f"Stop-loss automatically moved to Cost Breakeven at ₹{trade.breakeven_stop_price:.2f}. "
                    f"Capital is 100% protected at ₹0 net risk."
                )
                return {
                    "event": "MOVE_TO_BREAKEVEN",
                    "trade_id": trade.trade_id,
                    "new_stop_price": trade.breakeven_stop_price,
                    "instructions": trade.exit_instructions,
                    "audio": "BREAKEVEN_CHIME"
                }

        # Check Event 2: TAKE PROFIT — SELL NOW (Target Hit)
        if (is_long and high_val >= trade.target_price) or \
           ((not is_long) and low_val <= trade.target_price):
            return self._close_trade(
                exit_price=trade.target_price,
                action="TAKE_PROFIT",
                instructions=f"🟢 TARGET REACHED! Sell {trade.qty} shares on Zerodha Kite at ₹{trade.target_price:.2f}.",
                audio="TARGET_CHIME",
                exit_time=current_time
            )

        # Check Event 3: STOP-LOSS / BREAKEVEN STOP HIT
        if (is_long and low_val <= trade.active_stop_price) or \
           ((not is_long) and high_val >= trade.active_stop_price):
            is_be = (trade.status == "BREAKEVEN_ARMED")
            action = "BREAKEVEN_EXIT" if is_be else "STOP_LOSS_EXIT"
            audio = "BREAKEVEN_CHIME" if is_be else "STOP_CHIME"
            msg = f"Stop-Loss hit at ₹{trade.active_stop_price:.2f}. Capital preserved." if not is_be else f"Cost breakeven stop filled at ₹{trade.active_stop_price:.2f}. Zero net loss."
            return self._close_trade(
                exit_price=trade.active_stop_price,
                action=action,
                instructions=f"🔴 {msg} Confirm exit on Zerodha Kite.",
                audio=audio,
                exit_time=current_time
            )

        # Check Event 4: 15:10 IST MANDATORY SQUARE-OFF
        if current_time.time() >= time(15, 10):
            return self._close_trade(
                exit_price=trade.current_price,
                action="TIME_SQUARE_OFF",
                instructions=f"🔴 3:10 PM IST reached! Close position immediately at market price ₹{trade.current_price:.2f} on Kite before Zerodha ₹59 auto-square-off penalty.",
                audio="STOP_CHIME",
                exit_time=current_time
            )

        # Check Event 5: EARLY MOMENTUM REVERSAL EXIT
        # In profit (> +0.40%), but 5m bar breaks adverse side of VWAP with volume spike
        if vwap_val is not None:
            if is_long:
                unrealized_gain = (current_price - trade.entry_price) / trade.entry_price
                if unrealized_gain >= 0.0040 and current_price < vwap_val and volume_bias_reversal:
                    return self._close_trade(
                        exit_price=trade.current_price,
                        action="EARLY_MOMENTUM_REVERSAL",
                        instructions=f"🟠 Institutional momentum fading below VWAP! Close position at limit/market ₹{trade.current_price:.2f} to lock in partial profit.",
                        audio="REVERSAL_CHIME",
                        exit_time=current_time
                    )
            else:
                unrealized_gain = (trade.entry_price - current_price) / trade.entry_price
                if unrealized_gain >= 0.0040 and current_price > vwap_val and volume_bias_reversal:
                    return self._close_trade(
                        exit_price=trade.current_price,
                        action="EARLY_MOMENTUM_REVERSAL",
                        instructions=f"🟠 Institutional short momentum stalling above VWAP! Close position at ₹{trade.current_price:.2f} to bank profit.",
                        audio="REVERSAL_CHIME",
                        exit_time=current_time
                    )

        return None

    def _close_trade(
        self,
        exit_price: float,
        action: str,
        instructions: str,
        audio: str,
        exit_time: datetime
    ) -> Dict[str, Any]:
        trade = self.active_trade
        cost = ZerodhaIntradayCostCalculator.calculate(
            direction=trade.direction,
            entry_price=trade.entry_price,
            exit_price=exit_price,
            qty=trade.qty,
            tick_size=trade.tick_size,
            slippage_ticks=1
        )
        trade.status = "CLOSED"
        trade.exit_price = round(exit_price, 2)
        trade.exit_time = exit_time
        trade.exit_action = action
        trade.exit_instructions = instructions
        trade.audio_alert_type = audio
        trade.realized_net_pnl = cost.net_pnl

        record = {
            "trade_id": trade.trade_id,
            "symbol": trade.symbol,
            "direction": trade.direction,
            "entry_price": trade.entry_price,
            "exit_price": trade.exit_price,
            "qty": trade.qty,
            "gross_pnl": cost.gross_pnl,
            "net_pnl": cost.net_pnl,
            "total_charges": cost.total_charges,
            "brokerage": cost.brokerage,
            "stt": cost.stt,
            "action": action,
            "instructions": instructions,
            "entry_time": trade.entry_time.isoformat(),
            "exit_time": trade.exit_time.isoformat()
        }
        self.completed_trades.append(record)
        self._save_completed_trades()
        return {
            "event": action,
            "trade_id": trade.trade_id,
            "exit_price": trade.exit_price,
            "net_pnl": cost.net_pnl,
            "instructions": instructions,
            "audio": audio
        }

    def get_status_payload(self) -> Dict[str, Any]:
        trade = self.active_trade
        if trade is None:
            return {
                "active": False,
                "trade": None,
                "history": self.completed_trades,
                "auto_paper_trading": self.auto_paper_trading
            }

        # Calculate live unrealized PnL
        cost = ZerodhaIntradayCostCalculator.calculate(
            direction=trade.direction,
            entry_price=trade.entry_price,
            exit_price=trade.current_price,
            qty=trade.qty,
            tick_size=trade.tick_size,
            slippage_ticks=1
        )

        return {
            "active": trade.status != "CLOSED",
            "auto_paper_trading": self.auto_paper_trading,
            "trade": {
                "trade_id": trade.trade_id,
                "symbol": trade.symbol,
                "direction": trade.direction,
                "entry_price": trade.entry_price,
                "current_price": trade.current_price,
                "qty": trade.qty,
                "target_price": trade.target_price,
                "active_stop_price": trade.active_stop_price,
                "breakeven_armed": trade.status == "BREAKEVEN_ARMED",
                "status": trade.status,
                "unrealized_net_pnl": cost.net_pnl,
                "unrealized_gross_pnl": cost.gross_pnl,
                "total_charges": cost.total_charges,
                "exit_instructions": trade.exit_instructions,
                "audio_alert_type": trade.audio_alert_type
            },
            "history": self.completed_trades
        }

