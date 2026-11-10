from dataclasses import dataclass
from typing import Literal

@dataclass
class CostBreakdown:
    gross_pnl: float
    net_pnl: float
    total_charges: float
    brokerage: float
    stt: float
    nse_txn_charge: float
    sebi_ipft_charge: float
    stamp_duty: float
    gst: float
    eff_buy: float
    eff_sell: float
    buy_turnover: float
    sell_turnover: float
    total_turnover: float
    slippage_cost: float

class ZerodhaIntradayCostCalculator:
    """
    Statutory-precise Zerodha Equity Intraday (MIS) Cost & Friction Calculator for NSE.
    Includes exact STT, Exchange transaction charges, SEBI+IPFT, Stamp duty, GST, and 1-tick adverse slippage.
    """
    
    @staticmethod
    def calculate(
        direction: Literal["LONG", "SHORT"],
        entry_price: float,
        exit_price: float,
        qty: int,
        tick_size: float = 0.05,
        slippage_ticks: int = 1
    ) -> CostBreakdown:
        if qty <= 0:
            raise ValueError(f"Quantity must be strictly positive, got {qty}")

        slip = slippage_ticks * tick_size
        
        if direction.upper() in ("LONG", "BUY"):
            eff_buy = entry_price + slip
            eff_sell = exit_price - slip
            raw_gross = (exit_price - entry_price) * qty
            gross_pnl = (eff_sell - eff_buy) * qty
        elif direction.upper() in ("SHORT", "SELL"):
            eff_sell = entry_price - slip
            eff_buy = exit_price + slip
            raw_gross = (entry_price - exit_price) * qty
            gross_pnl = (eff_sell - eff_buy) * qty
        else:
            raise ValueError(f"Invalid direction: {direction}. Must be 'LONG' or 'SHORT'")

        slippage_cost = raw_gross - gross_pnl

        buy_turnover = eff_buy * qty
        sell_turnover = eff_sell * qty
        total_turnover = buy_turnover + sell_turnover

        # Brokerage: 0.03% or Rs. 20 per executed order, whichever is lower
        buy_brokerage = min(20.0, 0.0003 * buy_turnover)
        sell_brokerage = min(20.0, 0.0003 * sell_turnover)
        brokerage = buy_brokerage + sell_brokerage

        # STT: 0.025% on Sell turnover for intraday equity
        stt = 0.00025 * sell_turnover

        # NSE Transaction charge: 0.00297% of total turnover
        nse_txn_charge = 0.0000297 * total_turnover

        # SEBI Turnover fee (Rs. 10 per crore) + Investor Protection Fund Trust (IPFT, Rs. 10 per crore) = 0.000002
        sebi_ipft_charge = 0.000002 * total_turnover

        # Stamp Duty: 0.003% on Buy side turnover for intraday
        stamp_duty = 0.00003 * buy_turnover

        # GST: 18% on (Brokerage + NSE Txn Charge + SEBI/IPFT)
        gst = 0.18 * (brokerage + nse_txn_charge + sebi_ipft_charge)

        total_charges = brokerage + stt + nse_txn_charge + sebi_ipft_charge + stamp_duty + gst
        net_pnl = gross_pnl - total_charges

        return CostBreakdown(
            gross_pnl=round(gross_pnl, 2),
            net_pnl=round(net_pnl, 2),
            total_charges=round(total_charges, 2),
            brokerage=round(brokerage, 2),
            stt=round(stt, 2),
            nse_txn_charge=round(nse_txn_charge, 2),
            sebi_ipft_charge=round(sebi_ipft_charge, 2),
            stamp_duty=round(stamp_duty, 2),
            gst=round(gst, 2),
            eff_buy=round(eff_buy, 4),
            eff_sell=round(eff_sell, 4),
            buy_turnover=round(buy_turnover, 2),
            sell_turnover=round(sell_turnover, 2),
            total_turnover=round(total_turnover, 2),
            slippage_cost=round(slippage_cost, 2),
        )

    @staticmethod
    def calculate_from_turnover(
        buy_turnover: float,
        sell_turnover: float
    ) -> float:
        """Helper to quickly calculate total charges given buy and sell turnovers (0 slippage)."""
        total_turnover = buy_turnover + sell_turnover
        buy_brokerage = min(20.0, 0.0003 * buy_turnover)
        sell_brokerage = min(20.0, 0.0003 * sell_turnover)
        brokerage = buy_brokerage + sell_brokerage
        stt = 0.00025 * sell_turnover
        nse_txn_charge = 0.0000297 * total_turnover
        sebi_ipft_charge = 0.000002 * total_turnover
        stamp_duty = 0.00003 * buy_turnover
        gst = 0.18 * (brokerage + nse_txn_charge + sebi_ipft_charge)
        return round(brokerage + stt + nse_txn_charge + sebi_ipft_charge + stamp_duty + gst, 2)

