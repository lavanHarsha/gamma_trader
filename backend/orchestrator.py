import os
import yaml
import json
import logging
from datetime import datetime, timedelta, date
from typing import Dict, Any, List, Optional
import pandas as pd
import numpy as np
import pytz

from backend.data_providers.storage import DataStorageManager
from backend.data_providers.groww_feed import GrowwMarketDataProvider
from backend.data_providers.replay_feed import ReplayMarketDataProvider
from backend.costs.zerodha_nse import ZerodhaIntradayCostCalculator
from backend.features.stationary import StationaryFeatureEngine
from backend.features.candidate_rules import CandidateRuleScanner, CandidateSetup
from backend.labeling.triple_barrier import CostAdjustedTripleBarrierLabeler
from backend.ml.trainer import ModelTrainer
from backend.execution.risk_gate import RiskGatekeeper
from backend.execution.trade_monitor import TradeMonitor

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
logger = logging.getLogger("AlphaPulseOrchestrator")
IST = pytz.timezone("Asia/Kolkata")

class SystemOrchestrator:
    """
    Central Quantitative & Real-Time Orchestrator for Gamma_trader-Web.
    Coordinates Market Data Ingestion, Stationary Feature Engineering,
    Candidate Rule Scanning, Model Training/Inference, Risk Gatekeeping, and Trade Monitoring.
    """

    def __init__(self, root_dir: str = "."):
        self.root_dir = os.path.abspath(root_dir)
        self.config_dir = os.path.join(self.root_dir, "config")
        self.data_dir = os.path.join(self.root_dir, "data")
        
        # Load Universe & Risk configs
        self.universe_cfg = self._load_universe()
        self.storage = DataStorageManager(self.data_dir)
        self.groww_feed = GrowwMarketDataProvider(request_delay_sec=0.15)
        self.replay_feed = ReplayMarketDataProvider(self.storage)
        self.risk_gate = RiskGatekeeper(self.config_dir)
        self.trade_monitor = TradeMonitor()
        self.trainer = ModelTrainer(os.path.join(self.data_dir, "models"))
        
        self.active_mode: str = "LIVE"  # "LIVE" or "REPLAY"
        self.latest_signals: List[Dict[str, Any]] = []
        self.audit_report: Dict[str, Any] = {}

        # Try loading existing trained models & audit report
        self.trainer.load_artifacts()
        audit_file = os.path.join(self.data_dir, "models", "audit_report.json")
        if os.path.exists(audit_file):
            try:
                with open(audit_file, "r", encoding="utf-8") as f:
                    self.audit_report = json.load(f)
            except Exception as e:
                logger.warning(f"Failed to load audit_report.json: {e}")

    def _load_universe(self) -> Dict[str, Any]:
        u_path = os.path.join(self.config_dir, "universe.yaml")
        if os.path.exists(u_path):
            with open(u_path, "r", encoding="utf-8") as f:
                return yaml.safe_load(f)
        return {"stocks": [], "indices": []}

    def get_stocks_list(self) -> List[Dict[str, Any]]:
        return self.universe_cfg.get("stocks", [])

    def get_indices_list(self) -> List[Dict[str, Any]]:
        return self.universe_cfg.get("indices", [])

    def download_historical_data(self, days: int = 365, interval_min: int = 15) -> Dict[str, int]:
        """
        Download 1-year historical intraday bars for all 10 stocks and benchmark indices via Groww.
        Saves clean Parquet partitions into data/raw_parquet/.
        """
        now_dt = datetime.now(IST)
        start_dt = now_dt - timedelta(days=days)
        results = {}

        logger.info(f"Starting Groww historical download for {days} days ({interval_min}m bars)...")

        # 1. Stocks
        for item in self.get_stocks_list():
            sym = item["symbol"]
            groww_sym = item.get("groww_symbol", sym)
            logger.info(f"Downloading {sym} ({groww_sym})...")
            try:
                df = self.groww_feed.fetch_historical_bars(
                    symbol=groww_sym,
                    interval_minutes=interval_min,
                    start_dt=start_dt,
                    end_dt=now_dt
                )
                if not df.empty:
                    df['symbol'] = sym
                    self.storage.save_raw_bars(sym, interval_min, df)
                    results[sym] = len(df)
                    logger.info(f"Saved {len(df)} bars for {sym}")
                else:
                    results[sym] = 0
            except Exception as e:
                logger.error(f"Failed to fetch {sym}: {e}")
                results[sym] = 0

        # 2. Benchmark & Sector Indices
        for item in self.get_indices_list():
            sym = item["symbol"]
            groww_sym = item.get("groww_symbol", sym)
            logger.info(f"Downloading Index {sym} ({groww_sym})...")
            try:
                df = self.groww_feed.fetch_historical_bars(
                    symbol=groww_sym,
                    interval_minutes=interval_min,
                    start_dt=start_dt,
                    end_dt=now_dt
                )
                if not df.empty:
                    df['symbol'] = sym
                    self.storage.save_raw_bars(sym, interval_min, df)
                    results[sym] = len(df)
                    logger.info(f"Saved {len(df)} bars for index {sym}")
                else:
                    results[sym] = 0
            except Exception as e:
                logger.error(f"Failed to fetch index {sym}: {e}")
                results[sym] = 0

        return results

    def sync_live_market_bars(self) -> Dict[str, int]:
        """
        Pulls real-time intraday candles for the current day from Groww feed
        and updates local storage so the live scanner and trade monitor run on live prices.
        """
        now = datetime.now(IST)
        start_dt = now - timedelta(days=2)
        results = {}

        # 1. Update Benchmark & Sector Indices first
        for item in self.get_indices_list():
            sym = item["symbol"]
            groww_sym = item.get("groww_symbol", sym)
            try:
                df = self.groww_feed.fetch_historical_bars(
                    symbol=groww_sym,
                    interval_minutes=15,
                    start_dt=start_dt,
                    end_dt=now
                )
                if not df.empty:
                    df['symbol'] = sym
                    self.storage.save_raw_bars(sym, 15, df)
                    results[sym] = len(df)
            except Exception as e:
                logger.debug(f"Live sync index {sym} error: {e}")

        # 2. Update Stocks (15m and 5m)
        for item in self.get_stocks_list():
            sym = item["symbol"]
            groww_sym = item.get("groww_symbol", sym)
            try:
                for interval in [15, 5]:
                    df = self.groww_feed.fetch_historical_bars(
                        symbol=groww_sym,
                        interval_minutes=interval,
                        start_dt=start_dt,
                        end_dt=now
                    )
                    if not df.empty:
                        df['symbol'] = sym
                        self.storage.save_raw_bars(sym, interval, df)
                        results[f"{sym}_{interval}m"] = len(df)
            except Exception as e:
                logger.debug(f"Live sync stock {sym} error: {e}")

        # Re-evaluate live market signals after sync
        self.evaluate_live_market()
        return results

    def run_training_pipeline(self) -> Dict[str, Any]:
        """
        Full End-to-End Quantitative Pipeline:
        1. Load all stock and index bars from DuckDB/Parquet.
        2. Precompute 22 stationary indicators for each stock.
        3. Scan historical Stage-1 candidate setups.
        4. Apply Cost-Adjusted Triple-Barrier Labeler with Zerodha MIS fees.
        5. Pool all events into a unified training dataset.
        6. Run Purged & Embargoed Walk-Forward Cross-Validation.
        7. Fit final calibrated LightGBM model and SHAP TreeExplainer.
        """
        logger.info("Initiating quantitative training pipeline...")
        all_candidates_labeled = []
        nifty_df = self.storage.load_raw_bars("NIFTY", 15)
        vix_df = self.storage.load_raw_bars("INDIAVIX", 15)

        for item in self.get_stocks_list():
            sym = item["symbol"]
            sec_sym = item.get("sector_symbol", "NIFTY")
            sec_df = self.storage.load_raw_bars(sec_sym, 15)
            stock_df = self.storage.load_raw_bars(sym, 15)

            if len(stock_df) < 50:
                logger.warning(f"Insufficient bars for {sym} ({len(stock_df)} bars); skipping training fold.")
                continue

            # Precompute indicators
            df_ind = StationaryFeatureEngine.compute_indicators(stock_df)

            # Stage 1: Candidate rule scanning
            candidates = CandidateRuleScanner.scan_bars(sym, df_ind, sector_df=sec_df)
            logger.info(f"Found {len(candidates)} Stage-1 candidate setups for {sym}")

            if not candidates:
                continue

            # Stage 2: Cost-Adjusted Triple Barrier Labeling at Higher Difficulty
            labeled = CostAdjustedTripleBarrierLabeler.label_candidates(
                df=df_ind,
                candidates=candidates,
                tick_size=item.get("tick_size", 0.05),
                target_capital=25000.0,
                min_net_profit_threshold=250.0,
                slippage_ticks=2
            )

            if labeled.empty:
                continue

            # Extract stationary features for each candidate setup
            feature_rows = []
            for _, row in labeled.iterrows():
                idx = int(row['bar_index'])
                feats = StationaryFeatureEngine.extract_features_at_index(
                    df=df_ind,
                    idx=idx,
                    direction=row['direction'],
                    sector_df=sec_df,
                    nifty_df=nifty_df,
                    vix_df=vix_df
                )
                feats["timestamp"] = row["timestamp"]
                feats["symbol"] = row["symbol"]
                feats["direction"] = row["direction"]
                feats["setup_type"] = row["setup_type"]
                feats["entry_price"] = row["entry_price"]
                feats["exit_price"] = row["exit_price"]
                feats["net_pnl"] = row["net_pnl"]
                feats["label"] = int(row["label"])
                feature_rows.append(feats)

            all_candidates_labeled.extend(feature_rows)

        if not all_candidates_labeled:
            logger.warning("No candidate setups generated; unable to fit model.")
            return {"status": "NO_CANDIDATE_DATA"}

        pooled_df = pd.DataFrame(all_candidates_labeled)
        logger.info(f"Total pooled candidate setups: {len(pooled_df)} (Positive win labels: {pooled_df['label'].sum()})")

        # Save processed dataset
        proc_path = os.path.join(self.storage.processed_dir, "pooled_features_labeled.parquet")
        pooled_df.to_parquet(proc_path, index=False)

        # Walk-forward cross validation & final training
        report = self.trainer.train_walk_forward(pooled_df)
        self.audit_report = report
        logger.info(f"Walk-Forward cross validation finished: {report.get('overall_oos_metrics')}")
        return report

    def evaluate_live_market(self) -> List[Dict[str, Any]]:
        """
        Evaluates current market state (or active replay step) across the 10 stocks.
        Returns scanner status and any actionable signal that passes all 7 risk gates.
        Uses in-memory cache to maintain sub-millisecond response latency.
        """
        now_ts = datetime.now(IST).timestamp()
        if hasattr(self, "_last_eval_time") and (now_ts - self._last_eval_time < 5.0) and self.latest_signals:
            return self.latest_signals
        self._last_eval_time = now_ts

        active_signals = []
        nifty_raw = self._get_active_bars("NIFTY", 15)
        vix_raw = self._get_active_bars("INDIAVIX", 15)
        nifty_df = nifty_raw.tail(150) if not nifty_raw.empty else nifty_raw
        vix_df = vix_raw.tail(150) if not vix_raw.empty else vix_raw

        for item in self.get_stocks_list():
            sym = item["symbol"]
            sec_sym = item.get("sector_symbol", "NIFTY")
            sec_raw = self._get_active_bars(sec_sym, 15)
            sec_df = sec_raw.tail(150) if not sec_raw.empty else sec_raw

            raw_df = self._get_active_bars(sym, 15)
            if len(raw_df) < 25:
                continue

            df = raw_df.tail(150).copy()
            df_ind = StationaryFeatureEngine.compute_indicators(df)
            last_idx = len(df_ind) - 1
            last_row = df_ind.iloc[last_idx]
            curr_ts = last_row["timestamp"]
            curr_close = float(last_row["close"])
            atr_val = max(float(last_row.get("atr_14", 1.0)), 0.05)
            rvol = float(last_row.get("volume", 1.0)) / max(float(last_row.get("mean_vol_tod", 1.0)), 1.0)
            bar_range = max(float(last_row["high"]) - float(last_row["low"]), 0.05)
            exhaustion = float(last_row.get("day_range_exhaustion", 0.5))

            # Scan setups on df_ind
            all_setups = CandidateRuleScanner.scan_bars(sym, df_ind, sector_df=sec_df)
            if not all_setups:
                continue

            latest_setup = all_setups[-1]
            bars_since = last_idx - latest_setup.bar_index
            # Setup must be recent (within last 3 bars or same day)
            if bars_since > 3 and latest_setup.timestamp.date() != curr_ts.date():
                continue

            setup_idx = latest_setup.bar_index
            direction = latest_setup.direction
            tick_size = item.get("tick_size", 0.05)

            # Feature extraction at setup bar
            feats = StationaryFeatureEngine.extract_features_at_index(
                df=df_ind,
                idx=setup_idx,
                direction=direction,
                sector_df=sec_df,
                nifty_df=nifty_df,
                vix_df=vix_df
            )

            # Predict calibrated win probability
            p_win = self.trainer.predict_p_win(feats)

            # Price calculations for ₹25,000 exposure
            entry_price = curr_close
            qty = int(25000.0 // entry_price)
            if qty <= 0:
                continue

            atr_pct = atr_val / entry_price
            # Dynamic Target configured for ₹125+ net profit on ₹25,000 exposure
            gross_target_pct = float(np.clip(0.9 * atr_pct, 0.0055, 0.0075))
            gross_stop_pct = float(np.clip(0.85 * atr_pct, 0.0055, 0.0068))

            if direction == "LONG":
                target_p = entry_price * (1.0 + gross_target_pct)
                stop_p = entry_price * (1.0 - gross_stop_pct)
                be_p = entry_price * (1.0 + 0.0010)
            else:
                target_p = entry_price * (1.0 - gross_target_pct)
                stop_p = entry_price * (1.0 + gross_stop_pct)
                be_p = entry_price * (1.0 - 0.0010)

            # Calculate net profit and net loss using Zerodha fee calculator
            cost_target = ZerodhaIntradayCostCalculator.calculate(
                direction=direction,
                entry_price=entry_price,
                exit_price=target_p,
                qty=qty,
                tick_size=tick_size,
                slippage_ticks=1
            )
            cost_stop = ZerodhaIntradayCostCalculator.calculate(
                direction=direction,
                entry_price=entry_price,
                exit_price=stop_p,
                qty=qty,
                tick_size=tick_size,
                slippage_ticks=1
            )

            # Evaluate 7 Risk Gates
            trades_today = len(self.trade_monitor.completed_trades)
            daily_pnl = sum([t.get("net_pnl", 0.0) for t in self.trade_monitor.completed_trades])

            gate_eval = self.risk_gate.evaluate_gates(
                symbol=sym,
                current_ts=curr_ts,
                p_win=p_win,
                net_target_rs=cost_target.net_pnl,
                net_stop_rs=cost_stop.net_pnl,
                day_range_exhaustion=exhaustion,
                rvol_time_of_day=rvol,
                bar_range=bar_range,
                atr_14=atr_val,
                trades_taken_today=trades_today,
                daily_net_pnl=daily_pnl
            )

            # Generate SHAP explanations
            explanation = {}
            if self.trainer.active_explainer is not None:
                explanation = self.trainer.active_explainer.explain_instance(
                    features_dict=feats,
                    direction=direction,
                    symbol=sym,
                    sector_name=item.get("sector", "Sector")
                )

            signal_card = {
                "signal_id": f"SIG-{sym}-{curr_ts.strftime('%H%M')}",
                "timestamp": curr_ts.isoformat(),
                "symbol": sym,
                "display_name": item.get("name", sym),
                "sector": item.get("sector", "General"),
                "direction": direction,
                "setup_type": latest_setup.setup_type,
                "current_price": round(curr_close, 2),
                "entry_limit_price": round(entry_price, 2),
                "quantity": qty,
                "exposure_rs": round(qty * entry_price, 2),
                "target_price": round(target_p, 2),
                "stop_loss_price": round(stop_p, 2),
                "breakeven_price": round(be_p, 2),
                "p_win": p_win,
                "expected_net_ev_rs": gate_eval["expected_ev_rs"],
                "target_net_profit_rs": cost_target.net_pnl,
                "stop_net_loss_rs": cost_stop.net_pnl,
                "zerodha_fee_estimate": cost_target.total_charges,
                "is_actionable": gate_eval["all_passed"],
                "gate_breakdown": gate_eval["gate_results"],
                "rejection_reasons": gate_eval["rejection_reasons"],
                "positive_reasons": explanation.get("top_positive_reasons", []),
                "caution_points": explanation.get("caution_points", []),
                "shap_breakdown": explanation.get("shap_breakdown", [])
            }

            active_signals.append(signal_card)

        self.latest_signals = active_signals
        return active_signals

    def _get_active_bars(self, symbol: str, interval_min: int = 15) -> pd.DataFrame:
        if self.active_mode == "REPLAY":
            return self.replay_feed.fetch_historical_bars(symbol, interval_min, datetime.min, datetime.max)
        else:
            return self.storage.load_raw_bars(symbol, interval_min)
