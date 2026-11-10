# Gamma_trader-Web (AlphaPulse)
### Explainable Low-Risk NSE Intraday Meta-Labeling & Live Signal Web Application

---

## 1. Executive Summary & Financial Guardrails
**Gamma_trader-Web** is a production-grade, explainable quantitative trading and signal-generation web system built specifically for the National Stock Exchange of India (NSE). It is engineered under real-world financial constraints to target **₹3,000+ net monthly profit** on **₹5,000 starting capital** using **Zerodha Kite MIS 5x leverage** (**₹25,000 maximum position exposure**).

### Financial Parameters Strictly Enforced:
- **Starting Capital:** ₹5,000
- **Intraday Leverage:** Zerodha MIS up to 5x (₹25,000 position exposure per trade)
- **Monthly Net Target:** ₹3,000+ net profit (~₹750/week across 20 trading sessions)
- **Max Net Loss per Trade:** Hard-capped at **-₹185 net** (inclusive of ~₹26.73 Zerodha statutory charges and 1-tick adverse slippage)
- **Target Net Profit per Trade:** **+₹250 to +₹320 net** (after all statutory charges and slippage)
- **Dynamic Cost Breakeven Protection:** Once an active trade moves **+0.55% gross** in favor, the system issues an instant audio and visual alert instructing the user to move their Stop-Loss on Zerodha Kite Mobile App to **Cost Breakeven (`Entry + 0.12%`)**, locking the trade to ₹0 net risk.
- **High-Conviction Selectivity:** Trades only fire when calibrated probability $P(\text{Win}) \ge 0.62$ and Expected Net EV $\ge +₹65.0$.
- **100% Manual Zerodha Kite Execution:** No automated order webhooks or unauthorized API order placements. The web app serves as the quant decision deck on desktop or mobile (`http://localhost:5173`), providing exact Zerodha Kite inputs (Quantity, Limit Price, SL, Target).

---

## 2. Tech Stack & Architecture
- **Backend Language:** Python 3.11+ / 3.14 (Miniconda)
- **Zero-Cost Data Engine:** **Groww Charting API** for free 1-year historical 15m/5m/1m intraday OHLCV backfills + fallback support for Angel One SmartAPI and Fyers v3.
- **Storage Engine:** `duckdb` + `pyarrow` partitioned Parquet files (`data/raw_parquet/`).
- **Quant & ML Engine:** `numpy`, `pandas`, `numba` (JIT-accelerated triple-barrier labeling), `scikit-learn`, `lightgbm`, `shap` (TreeExplainer for real-time per-signal feature attributions), `scipy`.
- **Backend API & Push:** `FastAPI`, `uvicorn`, `websockets`, `pydantic`.
- **Frontend Web Application:** React 18, Vite, TypeScript, Tailwind CSS, TradingView `lightweight-charts`, `lucide-react`, Web Audio API sound synthesizer.

---

## 3. Directory Layout
```text
Gamma_trader/
├── config/
│   ├── universe.yaml            # 10 liquid 5x-MIS NSE stocks + sector index mappings + tick sizes
│   ├── risk_config.yaml         # Capital: 5000, Max Exposure: 25000, EV gates, IST session bounds
│   └── blackout_events.json     # Quarterly earnings dates, RBI policy days, Budget days to block
├── data/
│   ├── raw_parquet/             # Partitioned 5m and 15m OHLCV Parquet files (Stocks + Indices)
│   ├── processed_features/      # Cached stationary feature matrices & triple-barrier labels
│   └── models/                  # Serialized Walk-Forward LightGBM models, Calibrators & SHAP explainers
├── backend/
│   ├── data_providers/
│   │   ├── base.py              # Abstract MarketDataProvider interface
│   │   ├── groww_feed.py        # Free Groww 1-year historical + intraday feed & rate limiter
│   │   ├── angel_fyers_feed.py  # Angel One SmartAPI / Fyers v3 adapter
│   │   ├── replay_feed.py       # Market replay simulator for testing after 3:30 PM
│   │   └── storage.py           # DuckDB + Parquet manager with strict IST session hygiene
│   ├── costs/
│   │   └── zerodha_nse.py       # Exact NSE MIS brokerage, STT, Stamp, Exchange, GST, & Slippage
│   ├── features/
│   │   ├── stationary.py        # 22 stationary candlestick, RVOL_tod, VWAP, & regime features
│   │   └── candidate_rules.py   # Stage-1 Rule Filter (15m ORB, VWAP Pullback, Vol Squeeze)
│   ├── labeling/
│   │   └── triple_barrier.py    # Numba-accelerated Cost-Adjusted Triple-Barrier + Breakeven Labeler
│   ├── ml/
│   │   ├── walk_forward.py      # Purged & Embargoed Walk-Forward Cross-Validator
│   │   ├── trainer.py           # Pooled LightGBM + Logistic Baseline + Isotonic/Sigmoid Calibration
│   │   ├── explainer.py         # Real-time SHAP TreeExplainer -> Plain-English Reason Generator
│   │   └── metrics.py           # Net Profit Factor, Expectancy (₹), Brier Score, Deflated Sharpe
│   ├── execution/
│   │   ├── risk_gate.py         # Multi-gate risk validator, News/Shock blocker, Daily Circuit Breaker
│   │   └── trade_monitor.py     # Tracks active trade state: ENTRY -> MOVE_TO_BREAKEVEN -> SELL_NOW
│   ├── orchestrator.py          # Central coordinator connecting data, features, labels, and training
│   └── api/
│       └── main.py              # FastAPI REST endpoints + Live WebSocket broadcaster
├── frontend/
│   ├── src/
│   │   ├── components/
│   │   │   ├── LiveSignalBanner.tsx    # Audio/Visual BUY/HOLD/BREAKEVEN/SELL action banner
│   │   │   ├── TradeExecutionCard.tsx  # Exact Zerodha Kite inputs (Qty, Limit Price, SL, Target, Fees)
│   │   │   ├── ExplainabilityPanel.tsx # Top Positive/Negative SHAP Reasons & Plain-English Narrative
│   │   │   ├── IntradayChart.tsx       # TradingView Lightweight Chart with VWAP, ORB, SL & Target lines
│   │   │   ├── WatchlistScanner.tsx    # Live 10-stock scanner table with Regime & RVOL meters
│   │   │   └── WalkForwardAudit.tsx    # Out-of-Sample backtest tear sheet & Paper Trade ledger
│   │   ├── utils/
│   │   │   └── audio.ts                # Web Audio API alert chimes synthesizer
│   │   ├── App.tsx
│   │   └── main.tsx
│   └── package.json
├── scripts/
│   └── download_and_train.py    # Full-year Groww ingestion and walk-forward training script
└── tests/
    ├── test_zero_leakage.py     # Mutation test proving features at bar t never read bar t+1
    └── test_zerodha_math.py     # Unit test verifying ₹25,000 buy -> ₹25,250 sell = ₹26.73 exact fee
```

---

## 4. The 10-Stock Liquid MIS Universe
Selected for 5x MIS margin eligibility, tight ₹0.01–₹0.05 bid-ask spreads, and institutional volume:
1. **TATASTEEL** (Sector: NIFTY METAL)
2. **HINDALCO** (Sector: NIFTY METAL)
3. **VEDL** (Sector: NIFTY METAL)
4. **ETERNAL** / Zomato (Sector: NIFTY 50)
5. **BEL** / Bharat Electronics (Sector: NIFTY 50)
6. **DLF** (Sector: NIFTY REALTY)
7. **RECLTD** (Sector: NIFTY FIN SERVICE)
8. **MOTHERSON** (Sector: NIFTY AUTO)
9. **TMPV** / Tata Motors PV (Sector: NIFTY AUTO)
10. **CANBK** (Sector: NIFTY PSU BANK)

**Benchmark & Regime Indices:**
- `NIFTY` (NIFTY 50), `INDIAVIX` (India VIX), `NIFTYMETAL`, `NIFTYAUTO`, `NIFTYREALTY`, `NIFTYPSUBANK`, `FINNIFTY`.

---

## 5. Exact Zerodha NSE Intraday Cost Formulas
Every backtest barrier and live trade calculates exact statutory fees down to the paisa:
- `buy_brokerage = min(20.0, 0.0003 * buy_turnover)`
- `sell_brokerage = min(20.0, 0.0003 * sell_turnover)`
- `stt = 0.00025 * sell_turnover` (0.025% on Sell side only)
- `nse_txn_charge = 0.0000297 * total_turnover` (0.00297%)
- `sebi_ipft_charge = 0.000002 * total_turnover` (₹10/Cr SEBI + ₹10/Cr IPFT)
- `stamp_duty = 0.00003 * buy_turnover` (0.003% on Buy side only)
- `gst = 0.18 * (brokerage + nse_txn_charge + sebi_ipft_charge)`
- **Adverse Slippage:** 1 tick per side deducted from fill price.
- **Verification:** Buying ₹25,000 and Selling ₹25,250 with 0 slippage equals **₹26.73 total charges** and **₹223.27 net PnL**.

---

## 6. How to Run the Application

### Step 1: Start Backend API & WebSocket Server
```bash
uvicorn backend.api.main:app --host 0.0.0.0 --port 8000
```

### Step 2: Start Frontend Web Application
```bash
cd frontend
npm run dev -- --host
```
Open **`http://localhost:5173`** on your browser or phone on the local Wi-Fi.

### Step 3: Run Zero-Leakage & Statutory Math Tests
```bash
python tests/test_zerodha_math.py
python tests/test_zero_leakage.py
```

### Step 4: Full-Year Groww Historical Ingestion & Training (Optional/On-Demand)
```bash
python scripts/download_and_train.py
```
This fetches 1 year of 15m/5m bars from Groww for all 10 stocks and 7 indices, saves them to DuckDB/Parquet, and trains the walk-forward calibrated LightGBM model.

