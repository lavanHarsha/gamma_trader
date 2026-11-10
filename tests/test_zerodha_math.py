import pytest
import sys
import os

# Ensure backend can be imported
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from backend.costs.zerodha_nse import ZerodhaIntradayCostCalculator

def test_zerodha_exact_charges_and_net_pnl():
    """
    Spec Verification:
    Buying ₹25,000 and Selling ₹25,250 with 0 slippage equals ₹26.73 in total_charges and ₹223.27 in net_pnl.
    """
    entry_price = 250.0
    exit_price = 252.50
    qty = 100  # 250 * 100 = 25,000; 252.5 * 100 = 25,250

    breakdown = ZerodhaIntradayCostCalculator.calculate(
        direction="LONG",
        entry_price=entry_price,
        exit_price=exit_price,
        qty=qty,
        tick_size=0.05,
        slippage_ticks=0 # zero slippage test
    )

    # Detailed asserts
    assert breakdown.buy_turnover == 25000.00
    assert breakdown.sell_turnover == 25250.00
    assert breakdown.total_turnover == 50250.00
    assert breakdown.brokerage == round(7.50 + 7.575, 2) # 15.08
    assert breakdown.total_charges == 26.73
    assert breakdown.gross_pnl == 250.00
    assert breakdown.net_pnl == 223.27

def test_zerodha_short_direction_with_slippage():
    """Verify short trade with 1-tick adverse slippage."""
    entry_price = 500.0
    exit_price = 495.0
    qty = 50  # 25,000 position
    tick_size = 0.05

    breakdown = ZerodhaIntradayCostCalculator.calculate(
        direction="SHORT",
        entry_price=entry_price,
        exit_price=exit_price,
        qty=qty,
        tick_size=tick_size,
        slippage_ticks=1
    )

    # In short: eff_sell = 500 - 0.05 = 499.95, eff_buy = 495 + 0.05 = 495.05
    assert breakdown.eff_sell == 499.95
    assert breakdown.eff_buy == 495.05
    # Gross with slippage = (499.95 - 495.05) * 50 = 4.90 * 50 = 245.00
    assert breakdown.gross_pnl == 245.00
    assert breakdown.slippage_cost == 5.00
    assert breakdown.net_pnl > 200.0

if __name__ == "__main__":
    test_zerodha_exact_charges_and_net_pnl()
    test_zerodha_short_direction_with_slippage()
    print("ALL ZERODHA MATH TESTS PASSED!")

