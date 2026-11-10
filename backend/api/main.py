import os
import asyncio
import logging
from datetime import datetime, date, timedelta
from typing import Dict, Any, List, Optional
import pandas as pd
import pytz

from fastapi import FastAPI, WebSocket, WebSocketDisconnect, BackgroundTasks, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from backend.orchestrator import SystemOrchestrator
from backend.features.stationary import StationaryFeatureEngine

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
logger = logging.getLogger("GammaTraderAPI")
IST = pytz.timezone("Asia/Kolkata")

app = FastAPI(title="Gamma_trader-Web API", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

orchestrator = SystemOrchestrator()

# Connected WebSocket clients
active_websockets: List[WebSocket] = []

class TradeEnterRequest(BaseModel):
    symbol: str
    direction: str
    entry_price: float
    qty: int
    target_price: float
    stop_price: float
    tick_size: float = 0.05

class ReplayInitRequest(BaseModel):
    target_date: str # YYYY-MM-DD
    interval_min: int = 15

class ReplayControlRequest(BaseModel):
    action: str # "STEP", "PLAY", "PAUSE", "SEEK"
    index: Optional[int] = None
    speed: Optional[float] = 1.0


@app.on_event("startup")
async def startup_event():
    logger.info("Gamma_trader-Web Backend starting up...")
    # Launch background tick/replay broadcaster task
    asyncio.create_task(broadcast_loop())
    asyncio.create_task(live_market_updater_task())

async def live_market_updater_task():
    """Periodically updates market data during trading hours (09:15 to 15:30 IST on weekdays)."""
    # Initial immediate sync on startup in background
    try:
        logger.info("Performing initial live market data sync from Groww...")
        loop = asyncio.get_event_loop()
        await loop.run_in_executor(None, orchestrator.sync_live_market_bars)
        logger.info("Initial live market data sync complete.")
    except Exception as e:
        logger.error(f"Initial live sync error: {e}")

    while True:
        try:
            now = datetime.now(IST)
            if now.weekday() < 5 and (now.hour > 9 or (now.hour == 9 and now.minute >= 15)) and (now.hour < 15 or (now.hour == 15 and now.minute <= 30)):
                if orchestrator.active_mode == "LIVE":
                    loop = asyncio.get_event_loop()
                    await loop.run_in_executor(None, orchestrator.sync_live_market_bars)
        except Exception as e:
            logger.error(f"Error in live market updater: {e}")
        await asyncio.sleep(30.0)

async def broadcast_loop():
    """Periodically streams updates to WebSocket clients."""
    while True:
        try:
            # 1. Update Trade Monitor tick
            trade_payload = orchestrator.trade_monitor.get_status_payload()
            if trade_payload["active"] and trade_payload["trade"]:
                sym = trade_payload["trade"]["symbol"]
                if orchestrator.active_mode == "REPLAY":
                    curr_bar = orchestrator.replay_feed.get_current_bar(sym, 15)
                    if curr_bar is not None and not curr_bar.empty:
                        c_p = float(curr_bar["close"].iloc[0])
                        h_p = float(curr_bar["high"].iloc[0])
                        l_p = float(curr_bar["low"].iloc[0])
                        alert = orchestrator.trade_monitor.update_tick(
                            current_price=c_p,
                            bar_high=h_p,
                            bar_low=l_p
                        )
                        trade_payload = orchestrator.trade_monitor.get_status_payload()
                else:
                    quote = orchestrator.groww_feed.get_latest_quote(sym)
                    if quote.get("close"):
                        alert = orchestrator.trade_monitor.update_tick(
                            current_price=quote["close"],
                            bar_high=quote.get("high"),
                            bar_low=quote.get("low")
                        )
                        trade_payload = orchestrator.trade_monitor.get_status_payload()
            
            # 2. Auto Paper Trading Entry Check
            elif orchestrator.trade_monitor.auto_paper_trading and not trade_payload["active"]:
                for sig in orchestrator.latest_signals:
                    if sig.get("is_actionable", False):
                        entered = orchestrator.trade_monitor.maybe_auto_enter_trade(sig)
                        if entered:
                            trade_payload = orchestrator.trade_monitor.get_status_payload()
                            break

            if active_websockets:
                # 3. Scanner state
                scanner_rows = get_scanner_state()
                
                # 4. Active signal
                signals = orchestrator.latest_signals
                top_signal = signals[0] if signals else None

                msg = {
                    "type": "MARKET_PULSE",
                    "timestamp": datetime.now(IST).isoformat(),
                    "scanner": scanner_rows,
                    "trade_status": trade_payload,
                    "top_signal": top_signal,
                    "replay_mode": orchestrator.active_mode == "REPLAY"
                }

                disconnected = []
                for ws in active_websockets:
                    try:
                        await ws.send_json(msg)
                    except Exception:
                        disconnected.append(ws)
                for ws in disconnected:
                    if ws in active_websockets:
                        active_websockets.remove(ws)
        except Exception as e:
            logger.error(f"Error in broadcast loop: {e}")

        await asyncio.sleep(2.0)


_cached_scanner_rows: List[Dict[str, Any]] = []
_last_scanner_time: float = 0.0

def get_scanner_state() -> List[Dict[str, Any]]:
    global _cached_scanner_rows, _last_scanner_time
    now_ts = datetime.now(IST).timestamp()
    if _cached_scanner_rows and (now_ts - _last_scanner_time < 3.5):
        return _cached_scanner_rows

    rows = []
    for item in orchestrator.get_stocks_list():
        sym = item["symbol"]
        df = orchestrator._get_active_bars(sym, 15)
        if df.empty or len(df) < 15:
            rows.append({
                "symbol": sym,
                "name": item.get("name", sym),
                "sector": item.get("sector", "General"),
                "price": 0.0,
                "change_pct": 0.0,
                "rvol": 1.0,
                "regime": "NEUTRAL",
                "setup": "IDLE"
            })
            continue

        # Use recent 150 bars for instantaneous calculation
        df_sub = df.tail(150).copy()
        df_ind = StationaryFeatureEngine.compute_indicators(df_sub)
        last = df_ind.iloc[-1]
        c = float(last['close'])
        same_day_bars = df_sub[df_sub['date'] == last['date']]
        o_day = float(same_day_bars.iloc[0]['open']) if len(same_day_bars) > 0 else c
        chg_pct = (c - o_day) / o_day * 100.0 if o_day > 0 else 0.0
        rvol = float(last.get('volume', 1.0)) / max(float(last.get('mean_vol_tod', 1.0)), 1.0)
        vwap_val = float(last.get('vwap', c))
        ema9 = float(last.get('ema_9', c))

        regime = "BULLISH" if c > vwap_val and c > ema9 else ("BEARISH" if c < vwap_val and c < ema9 else "CHOPPY")

        vwap_std = max(float(last.get('vwap_std', 1.0)), 0.1)
        vwap_z = (c - vwap_val) / vwap_std
        day_range_used = float(last.get('day_range_exhaustion', 0.5)) * 100.0

        # Find matching signal if any
        matching_sig = next((s for s in orchestrator.latest_signals if s["symbol"] == sym), None)
        setup_desc = matching_sig["setup_type"] if matching_sig else ("WATCH" if rvol > 1.2 else "IDLE")
        win_prob = (matching_sig.get("p_win", 0.50) * 100.0) if matching_sig else 50.0

        rows.append({
            "symbol": sym,
            "name": item.get("name", sym),
            "sector": item.get("sector", "General"),
            "price": round(c, 2),
            "change_pct": round(chg_pct, 2),
            "rvol": round(rvol, 2),
            "vwap_z": round(vwap_z, 2),
            "sector_rel_strength_pct": round(chg_pct * 0.15, 2),
            "day_range_used_pct": round(day_range_used, 1),
            "regime": regime,
            "setup": setup_desc,
            "win_prob_pct": round(win_prob, 1),
            "is_actionable": matching_sig.get("is_actionable", False) if matching_sig else False
        })
    _cached_scanner_rows = rows
    _last_scanner_time = now_ts
    return rows


@app.get("/api/universe")
def get_universe():
    return orchestrator.universe_cfg

@app.get("/api/risk_config")
def get_risk_config():
    return orchestrator.risk_gate.risk_config

@app.get("/api/bars/{symbol}")
def get_bars(symbol: str, interval: int = 15):
    """
    Returns OHLCV bars formatted for TradingView Lightweight-Charts:
    [{time: epoch_seconds, open, high, low, close, volume, vwap, orb_h, orb_l, ema9, ema21}]
    """
    df = orchestrator._get_active_bars(symbol.upper(), interval)
    if df.empty:
        return []

    # Take recent 350 bars for ultra-fast lightweight-charts rendering
    df_sub = df.tail(350).copy()
    df_ind = StationaryFeatureEngine.compute_indicators(df_sub)
    results = []
    for _, row in df_ind.iterrows():
        ts_sec = int(row['timestamp'].timestamp())
        c_val = round(float(row['close']), 2)
        h_val = round(float(row['high']), 2)
        l_val = round(float(row['low']), 2)
        o_val = round(float(row['open']), 2)
        vol_val = round(float(row['volume']), 0)

        # NaN-safe indicator values
        raw_vwap = row.get('vwap')
        vwap_val = round(float(raw_vwap), 2) if (raw_vwap is not None and not pd.isna(raw_vwap)) else c_val

        raw_orb_h = row.get('orb_high')
        orb_h_val = round(float(raw_orb_h), 2) if (raw_orb_h is not None and not pd.isna(raw_orb_h)) else h_val

        raw_orb_l = row.get('orb_low')
        orb_l_val = round(float(raw_orb_l), 2) if (raw_orb_l is not None and not pd.isna(raw_orb_l)) else l_val

        raw_e9 = row.get('ema_9')
        e9_val = round(float(raw_e9), 2) if (raw_e9 is not None and not pd.isna(raw_e9)) else c_val

        raw_e21 = row.get('ema_21')
        e21_val = round(float(raw_e21), 2) if (raw_e21 is not None and not pd.isna(raw_e21)) else c_val

        results.append({
            "time": ts_sec,
            "open": o_val,
            "high": h_val,
            "low": l_val,
            "close": c_val,
            "volume": vol_val,
            "vwap": vwap_val,
            "orb_high": orb_h_val,
            "orb_low": orb_l_val,
            "ema_9": e9_val,
            "ema_21": e21_val
        })
    return results

@app.get("/api/scanner")
def get_scanner():
    return get_scanner_state()

@app.get("/api/signals")
def get_signals():
    orchestrator.evaluate_live_market()
    return orchestrator.latest_signals

@app.post("/api/market/sync")
async def trigger_live_sync():
    """Manually triggers an immediate pull of live market bars from Groww."""
    loop = asyncio.get_event_loop()
    res = await loop.run_in_executor(None, orchestrator.sync_live_market_bars)
    return {"status": "SUCCESS", "synced": res}

@app.get("/api/audit")
def get_audit():
    # Always ensure freshest audit report is loaded from disk
    audit_file = os.path.join(orchestrator.data_dir, "models", "audit_report.json")
    if os.path.exists(audit_file):
        try:
            with open(audit_file, "r", encoding="utf-8") as f:
                orchestrator.audit_report = json.load(f)
        except Exception:
            pass
    return {
        "audit_report": orchestrator.audit_report,
        "completed_trades": orchestrator.trade_monitor.completed_trades
    }

@app.post("/api/trade/enter")
def enter_trade(req: TradeEnterRequest):
    trade = orchestrator.trade_monitor.start_trade(
        symbol=req.symbol,
        direction=req.direction,
        entry_price=req.entry_price,
        qty=req.qty,
        target_price=req.target_price,
        stop_price=req.stop_price,
        tick_size=req.tick_size
    )
    return {"status": "SUCCESS", "trade_id": trade.trade_id}

@app.post("/api/trade/exit")
def exit_trade():
    status = orchestrator.trade_monitor.get_status_payload()
    if not status["active"] or not status["trade"]:
        return {"status": "NO_ACTIVE_TRADE"}

    trade = orchestrator.trade_monitor.active_trade
    res = orchestrator.trade_monitor._close_trade(
        exit_price=trade.current_price,
        action="MANUAL_USER_EXIT",
        instructions="Position closed manually by user.",
        audio="STOP_CHIME",
        exit_time=datetime.now(IST)
    )
    return {"status": "CLOSED", "result": res}

@app.get("/api/trade/status")
def trade_status():
    return orchestrator.trade_monitor.get_status_payload()

@app.post("/api/trade/auto_paper_toggle")
def toggle_auto_paper():
    orchestrator.trade_monitor.auto_paper_trading = not orchestrator.trade_monitor.auto_paper_trading
    return {
        "status": "SUCCESS",
        "auto_paper_trading": orchestrator.trade_monitor.auto_paper_trading
    }

@app.post("/api/trade/clear_paper_history")
def clear_paper_history():
    orchestrator.trade_monitor.completed_trades = []
    orchestrator.trade_monitor._save_completed_trades()
    return {"status": "SUCCESS", "message": "Paper trade history cleared"}

@app.post("/api/replay/init")
def init_replay(req: ReplayInitRequest):
    orchestrator.active_mode = "REPLAY"
    try:
        t_date = datetime.strptime(req.target_date, "%Y-%m-%d").date()
    except Exception:
        t_date = date.today()

    stocks = [s["symbol"] for s in orchestrator.get_stocks_list()]
    indices = [i["symbol"] for i in orchestrator.get_indices_list()]
    orchestrator.replay_feed.set_session(t_date, stocks + indices, req.interval_min)
    return {
        "status": "REPLAY_INITIALIZED",
        "date": str(t_date),
        "total_bars": len(orchestrator.replay_feed.all_timestamps)
    }

@app.post("/api/replay/control")
def control_replay(req: ReplayControlRequest):
    if req.action == "STEP":
        ts = orchestrator.replay_feed.step()
        orchestrator.evaluate_live_market()
        return {"status": "STEPPED", "timestamp": str(ts), "index": orchestrator.replay_feed.current_index}
    elif req.action == "SEEK" and req.index is not None:
        orchestrator.replay_feed.seek(req.index)
        orchestrator.evaluate_live_market()
        return {"status": "SEEKED", "index": orchestrator.replay_feed.current_index}
    elif req.action == "LIVE":
        orchestrator.active_mode = "LIVE"
        return {"status": "SWITCHED_TO_LIVE"}
    return {"status": "OK"}

@app.post("/api/data/download_and_train")
def download_and_train(background_tasks: BackgroundTasks, days: int = 365):
    def task():
        orchestrator.download_historical_data(days=days, interval_min=15)
        orchestrator.run_training_pipeline()
    background_tasks.add_task(task)
    return {"status": "IN_PROGRESS", "message": f"Historical {days}-day download & model training initiated."}

@app.post("/api/train")
def trigger_training(background_tasks: BackgroundTasks):
    def task():
        orchestrator.run_training_pipeline()
    background_tasks.add_task(task)
    return {"status": "IN_PROGRESS", "message": "High-difficulty model training pipeline initiated in background."}

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    active_websockets.append(websocket)
    try:
        while True:
            # Receive client ping or messages
            data = await websocket.receive_text()
            if data == "EVALUATE":
                orchestrator.evaluate_live_market()
    except WebSocketDisconnect:
        if websocket in active_websockets:
            active_websockets.remove(websocket)
