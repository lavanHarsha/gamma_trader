import numpy as np
import pandas as pd
from typing import Dict, Any, List
from scipy.stats import norm, skew, kurtosis

def compute_trading_metrics(
    net_pnls: List[float],
    y_true: np.ndarray,
    y_prob: np.ndarray,
    initial_capital: float = 5000.0
) -> Dict[str, Any]:
    """
    Computes professional quantitative performance metrics:
    Net Profit Factor, Rupee Expectancy, Brier Score, Win Rate, Max Drawdown, Deflated Sharpe.
    """
    if len(net_pnls) == 0:
        return {
            "total_trades": 0,
            "win_rate": 0.0,
            "profit_factor": 0.0,
            "expectancy_rs": 0.0,
            "total_net_pnl": 0.0,
            "brier_score": 0.0,
            "max_drawdown_rs": 0.0,
            "sharpe_ratio": 0.0,
            "deflated_sharpe": 0.0
        }

    pnls = np.array(net_pnls, dtype=np.float64)
    wins = pnls[pnls > 0]
    losses = pnls[pnls < 0]

    win_count = len(wins)
    loss_count = len(losses)
    total_trades = len(pnls)
    win_rate = win_count / max(1, total_trades)

    gross_win = float(wins.sum()) if len(wins) > 0 else 0.0
    gross_loss = float(abs(losses.sum())) if len(losses) > 0 else 0.0
    profit_factor = (gross_win / gross_loss) if gross_loss > 0 else (99.0 if gross_win > 0 else 0.0)

    expectancy_rs = float(pnls.mean())
    total_net_pnl = float(pnls.sum())

    # Brier Score: Mean squared error of probabilities vs binary outcomes
    if len(y_true) > 0 and len(y_prob) > 0:
        brier_score = float(np.mean((y_prob - y_true) ** 2))
    else:
        brier_score = 0.0

    # Max Drawdown
    equity_curve = initial_capital + np.cumsum(pnls)
    peak = np.maximum.accumulate(equity_curve)
    drawdowns = peak - equity_curve
    max_dd = float(np.max(drawdowns)) if len(drawdowns) > 0 else 0.0

    # Sharpe Ratio (annualized intraday ~252 trading sessions)
    mean_pnl = np.mean(pnls)
    std_pnl = np.std(pnls)
    if std_pnl > 1e-6:
        sr = float((mean_pnl / std_pnl) * np.sqrt(252))
        # Deflated Sharpe adjustment for skewness and kurtosis (Bailey & López de Prado)
        sk = float(skew(pnls))
        kt = float(kurtosis(pnls))
        var_sr = (1.0 - sk * sr + ((kt - 1.0) / 4.0) * (sr ** 2)) / max(1, total_trades)
        std_sr = np.sqrt(max(1e-6, var_sr))
        psr = float(norm.cdf((sr) / std_sr))
        deflated_sharpe = round(psr, 3)
    else:
        sr = 0.0
        deflated_sharpe = 0.0

    return {
        "total_trades": total_trades,
        "win_rate": round(win_rate * 100, 1),
        "profit_factor": round(profit_factor, 2),
        "expectancy_rs": round(expectancy_rs, 2),
        "total_net_pnl": round(total_net_pnl, 2),
        "brier_score": round(brier_score, 4),
        "max_drawdown_rs": round(max_dd, 2),
        "sharpe_ratio": round(sr, 2),
        "deflated_sharpe": deflated_sharpe
    }

