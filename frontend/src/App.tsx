import React, { useState, useEffect, useRef } from 'react';
import {
  Shield,
  Target,
  Zap,
  TrendingUp,
  TrendingDown,
  Calendar,
  Clock,
  Play,
  Pause,
  SkipForward,
  FastForward,
  Activity,
  Award,
  Layers,
  Bot,
  RefreshCw
} from 'lucide-react';

import { LiveSignalBanner } from './components/LiveSignalBanner';
import { TradeExecutionCard } from './components/TradeExecutionCard';
import { ExplainabilityPanel } from './components/ExplainabilityPanel';
import { IntradayChart } from './components/IntradayChart';
import { WatchlistScanner, type ScannerRow } from './components/WatchlistScanner';
import { WalkForwardAudit } from './components/WalkForwardAudit';

export const App: React.FC = () => {
  const [mode, setMode] = useState<'LIVE' | 'REPLAY'>('LIVE');
  const [selectedSymbol, setSelectedSymbol] = useState<string>('TATASTEEL');
  const [wsConnected, setWsConnected] = useState<boolean>(false);
  const [bottomTab, setBottomTab] = useState<'WATCHLIST' | 'AUDIT'>('WATCHLIST');
  
  // Live Clock (Asia/Kolkata)
  const [istTime, setIstTime] = useState<string>('');

  // Market Regime & Circuit Breaker Badges
  const [niftyTrend, setNiftyTrend] = useState<string>('BULLISH');
  const [vixLevel, setVixLevel] = useState<number>(14.2);
  const [topSector, setTopSector] = useState<string>('NIFTY METAL (+1.2%)');
  const [dailyNetPnL, setDailyNetPnL] = useState<number>(0.0);
  const [tradesUsedToday, setTradesUsedToday] = useState<number>(0);

  // Data states
  const [scannerRows, setScannerRows] = useState<ScannerRow[]>([]);
  const [allSignals, setAllSignals] = useState<any[]>([]);
  const [activeSignal, setActiveSignal] = useState<any | null>(null);
  const [tradeStatus, setTradeStatus] = useState<any | null>(null);
  
  // Replay controls
  const [replayDate, setReplayDate] = useState<string>('2026-11-06');
  const [replaySpeed, setReplaySpeed] = useState<number>(1);
  const [isReplaying, setIsReplaying] = useState<boolean>(false);

  const wsRef = useRef<WebSocket | null>(null);
  const replayIntervalRef = useRef<any>(null);

  // Live IST Clock Timer
  useEffect(() => {
    const updateClock = () => {
      const now = new Date();
      const options: Intl.DateTimeFormatOptions = {
        timeZone: 'Asia/Kolkata',
        hour: '2-digit',
        minute: '2-digit',
        second: '2-digit',
        hour12: false
      };
      setIstTime(now.toLocaleTimeString('en-GB', options) + ' IST');
    };
    updateClock();
    const interval = setInterval(updateClock, 1000);
    return () => clearInterval(interval);
  }, []);

  // WebSocket Connection
  useEffect(() => {
    let ws: WebSocket;
    let timer: any;

    const connect = () => {
      ws = new WebSocket('ws://localhost:8000/ws');
      wsRef.current = ws;

      ws.onopen = () => {
        setWsConnected(true);
      };

      ws.onmessage = (event) => {
        try {
          const data = JSON.parse(event.data);
          if (data.type === 'MARKET_PULSE') {
            if (data.scanner) setScannerRows(data.scanner);
            if (data.trade_status) {
              setTradeStatus(data.trade_status);
              if (data.trade_status.history) {
                setTradesUsedToday(data.trade_status.history.length);
                const sumPnL = data.trade_status.history.reduce((acc: number, t: any) => acc + (t.net_pnl || 0), 0);
                setDailyNetPnL(sumPnL);
              }
            }
            if (data.top_signal) setActiveSignal(data.top_signal);
          }
        } catch (e) {
          console.error('WS parse error:', e);
        }
      };

      ws.onclose = () => {
        setWsConnected(false);
        timer = setTimeout(connect, 3000);
      };

      ws.onerror = () => {
        ws.close();
      };
    };

    connect();

    return () => {
      clearTimeout(timer);
      if (wsRef.current) wsRef.current.close();
    };
  }, []);

  // Polling fallback
  const fetchSnapshot = async () => {
    try {
      const [scanRes, sigRes, tradeRes] = await Promise.all([
        fetch('http://localhost:8000/api/scanner'),
        fetch('http://localhost:8000/api/signals'),
        fetch('http://localhost:8000/api/trade/status'),
      ]);
      if (scanRes.ok) setScannerRows(await scanRes.json());
      if (sigRes.ok) {
        const sigs = await sigRes.json();
        setAllSignals(sigs);
        const match = sigs.find((s: any) => s.symbol === selectedSymbol) || sigs.find((s: any) => s.is_actionable) || (sigs.length > 0 ? sigs[0] : null);
        setActiveSignal(match);
      }
      if (tradeRes.ok) {
        const tData = await tradeRes.json();
        setTradeStatus(tData);
        if (tData.history) {
          setTradesUsedToday(tData.history.length);
          const sumPnL = tData.history.reduce((acc: number, t: any) => acc + (t.net_pnl || 0), 0);
          setDailyNetPnL(sumPnL);
        }
      }
    } catch (e) {
      console.warn('Backend polling error:', e);
    }
  };

  useEffect(() => {
    fetchSnapshot();
    const interval = setInterval(() => {
      // Light fallback poll: if WS is connected, poll only every 10s to keep UI lightweight
      fetchSnapshot();
    }, wsConnected ? 10000 : 4000);
    return () => clearInterval(interval);
  }, [wsConnected]);

  useEffect(() => {
    if (allSignals.length > 0) {
      const match = allSignals.find((s: any) => s.symbol === selectedSymbol) || allSignals.find((s: any) => s.is_actionable) || allSignals[0];
      setActiveSignal(match);
    }
  }, [selectedSymbol, allSignals]);

  // Enter Trade on Kite Handler
  const handleEnterTrade = async (params: any) => {
    try {
      const res = await fetch('http://localhost:8000/api/trade/enter', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(params),
      });
      if (res.ok) {
        fetchSnapshot();
      }
    } catch (e) {
      console.error('Error entering trade:', e);
    }
  };

  // Exit Trade Handler
  const handleExitTrade = async () => {
    try {
      const res = await fetch('http://localhost:8000/api/trade/exit', { method: 'POST' });
      if (res.ok) {
        fetchSnapshot();
      }
    } catch (e) {
      console.error('Error exiting trade:', e);
    }
  };

  const handleToggleAutoPaper = async () => {
    try {
      const res = await fetch('http://localhost:8000/api/trade/auto_paper_toggle', { method: 'POST' });
      if (res.ok) {
        fetchSnapshot();
      }
    } catch (e) {
      console.error('Error toggling auto paper:', e);
    }
  };

  const [isSyncing, setIsSyncing] = useState<boolean>(false);
  const handleSyncMarket = async () => {
    setIsSyncing(true);
    try {
      await fetch('http://localhost:8000/api/market/sync', { method: 'POST' });
      await fetchSnapshot();
    } catch (e) {
      console.error('Error syncing market:', e);
    } finally {
      setIsSyncing(false);
    }
  };

  // Replay Controls
  const handleInitReplay = async () => {
    try {
      const res = await fetch('http://localhost:8000/api/replay/init', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ target_date: replayDate, interval_min: 15 }),
      });
      if (res.ok) {
        setMode('REPLAY');
        fetchSnapshot();
      }
    } catch (e) {
      console.error('Error init replay:', e);
    }
  };

  const handleStepReplay = async () => {
    try {
      await fetch('http://localhost:8000/api/replay/control', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ action: 'STEP' }),
      });
      fetchSnapshot();
    } catch (e) {
      console.error('Error stepping replay:', e);
    }
  };

  const handleToggleAutoPlay = () => {
    if (isReplaying) {
      clearInterval(replayIntervalRef.current);
      setIsReplaying(false);
    } else {
      setIsReplaying(true);
      const delay = Math.max(500, 3000 / replaySpeed);
      replayIntervalRef.current = setInterval(() => {
        handleStepReplay();
      }, delay);
    }
  };

  const handleSwitchToLive = async () => {
    clearInterval(replayIntervalRef.current);
    setIsReplaying(false);
    try {
      await fetch('http://localhost:8000/api/replay/control', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ action: 'LIVE' }),
      });
      setMode('LIVE');
      fetchSnapshot();
    } catch (e) {
      console.error('Error switching to live:', e);
    }
  };

  // Get current trade levels for selected stock
  const currentTradeLevels = activeSignal && activeSignal.symbol === selectedSymbol ? {
    entryPrice: activeSignal.entry_limit_price,
    targetPrice: activeSignal.target_price,
    stopPrice: activeSignal.stop_loss_price,
    breakevenPrice: activeSignal.breakeven_price,
    direction: activeSignal.direction
  } : (tradeStatus?.trade && tradeStatus.trade.symbol === selectedSymbol ? {
    entryPrice: tradeStatus.trade.entry_price,
    targetPrice: tradeStatus.trade.target_price,
    stopPrice: tradeStatus.trade.active_stop_price,
    breakevenPrice: tradeStatus.trade.entry_price * 1.0012,
    direction: tradeStatus.trade.direction
  } : null);

  return (
    <div className="min-h-screen bg-dark-900 text-gray-100 flex flex-col font-sans">
      {/* 1. TOP COMMAND BAR */}
      <header className="bg-dark-800/95 border-b border-gray-800 sticky top-0 z-50 backdrop-blur">
        <div className="max-w-7xl mx-auto px-4 py-2.5 flex flex-wrap items-center justify-between gap-3">
          {/* Logo & Clock */}
          <div className="flex items-center gap-3">
            <div className="p-2 bg-gradient-to-tr from-blue-600 to-emerald-500 rounded-xl shadow-lg shadow-blue-500/20">
              <Zap className="w-5 h-5 text-white" />
            </div>
            <div>
              <div className="flex items-center gap-2">
                <h1 className="text-base font-black tracking-tight text-white flex items-center gap-1.5">
                  Gamma_trader-Web
                </h1>
                <span className="text-[10px] uppercase font-bold tracking-widest px-2 py-0.5 bg-blue-500/10 text-blue-400 border border-blue-500/20 rounded">
                  NSE Intraday MIS
                </span>
              </div>
              <div className="flex items-center gap-2 text-xs font-mono text-gray-400 mt-0.5">
                <Clock className="w-3 h-3 text-cyan-400" />
                <span className="text-white font-semibold">{istTime || '09:15:00 IST'}</span>
                <span className="text-gray-600">|</span>
                <span className="flex items-center gap-1">
                  <span className={`w-1.5 h-1.5 rounded-full ${wsConnected ? 'bg-emerald-400 animate-ping' : 'bg-rose-500'}`} />
                  <span className="text-[11px]">{wsConnected ? 'Live Feed Connected' : 'Connecting'}</span>
                </span>
              </div>
            </div>
          </div>

          {/* Market Regime & Circuit Breaker Badges */}
          <div className="hidden lg:flex items-center gap-2.5 font-mono text-xs">
            {/* NIFTY 50 Trend Badge */}
            <div className="bg-dark-900/90 border border-gray-700/80 px-2.5 py-1.5 rounded-lg flex items-center gap-1.5">
              <TrendingUp className="w-3.5 h-3.5 text-emerald-400" />
              <span className="text-gray-400">NIFTY 50:</span>
              <strong className="text-emerald-400">{niftyTrend}</strong>
            </div>

            {/* INDIA VIX Badge */}
            <div className="bg-dark-900/90 border border-gray-700/80 px-2.5 py-1.5 rounded-lg flex items-center gap-1.5">
              <Activity className="w-3.5 h-3.5 text-purple-400" />
              <span className="text-gray-400">INDIA VIX:</span>
              <strong className="text-purple-300">{vixLevel.toFixed(1)}</strong>
            </div>

            {/* Top Leading Sector Badge */}
            <div className="bg-dark-900/90 border border-gray-700/80 px-2.5 py-1.5 rounded-lg flex items-center gap-1.5">
              <Layers className="w-3.5 h-3.5 text-cyan-400" />
              <span className="text-gray-400">Leader:</span>
              <strong className="text-cyan-300">{topSector}</strong>
            </div>

            {/* Daily Paper Trading Performance Status */}
            <div className="bg-dark-900/90 border border-emerald-950/80 px-2.5 py-1.5 rounded-lg flex items-center gap-1.5 text-emerald-300">
              <Target className="w-3.5 h-3.5 text-emerald-400" />
              <span>Net PnL: <strong className={dailyNetPnL >= 0 ? 'text-emerald-400' : 'text-rose-400'}>{dailyNetPnL >= 0 ? '+' : ''}₹{dailyNetPnL.toFixed(1)}</strong></span>
              <span className="text-gray-600">|</span>
              <span>Trades: <strong className="text-cyan-400">{tradesUsedToday} Done (+₹125/win)</strong></span>
            </div>
          </div>

          {/* Mode Switcher & Replay Controls */}
          <div className="flex items-center gap-2 font-mono text-xs">
            {/* Auto Paper Trading Mode Toggle */}
            <button
              onClick={handleToggleAutoPaper}
              className={`px-2.5 py-1 rounded-lg font-mono text-xs font-bold border transition flex items-center gap-1.5 ${
                tradeStatus?.auto_paper_trading
                  ? 'bg-emerald-500/15 border-emerald-500/50 text-emerald-400 hover:bg-emerald-500/25'
                  : 'bg-dark-900 border-gray-700 text-gray-400 hover:text-white'
              }`}
              title="Autonomous Paper Trading on High-Conviction Setups"
            >
              <Bot className="w-3.5 h-3.5" />
              <span>Auto Paper: {tradeStatus?.auto_paper_trading ? 'ON' : 'OFF'}</span>
            </button>

            {mode === 'LIVE' ? (
              <div className="flex items-center gap-2">
                <span className="px-2.5 py-1 bg-emerald-500/10 text-emerald-400 border border-emerald-500/30 rounded-lg flex items-center gap-1.5">
                  <span className="w-1.5 h-1.5 rounded-full bg-emerald-400 animate-ping" />
                  Live Market
                </span>
                <button
                  onClick={handleSyncMarket}
                  disabled={isSyncing}
                  className="px-2 py-1 rounded-lg bg-dark-900 hover:bg-dark-700 text-cyan-400 border border-cyan-800/60 flex items-center gap-1 transition"
                  title="Force immediate sync with live Groww feed"
                >
                  <RefreshCw className={`w-3.5 h-3.5 ${isSyncing ? 'animate-spin text-cyan-300' : ''}`} />
                  <span className="text-[11px]">{isSyncing ? 'Syncing...' : 'Sync'}</span>
                </button>
                <button
                  onClick={handleInitReplay}
                  className="px-2.5 py-1 rounded-lg bg-dark-900 hover:bg-dark-700 text-gray-300 border border-gray-700 flex items-center gap-1 transition"
                  title="Test historical NSE day replay"
                >
                  <Calendar className="w-3.5 h-3.5 text-amber-400" />
                  <span>Replay Mode</span>
                </button>
              </div>
            ) : (
              <div className="flex items-center gap-1.5 bg-dark-900/90 border border-amber-600/50 p-1 rounded-lg">
                <span className="text-[11px] font-bold text-amber-400 px-1">
                  Replay: {replayDate}
                </span>

                {/* Speed Controls: 1x, 5x, 10x */}
                <div className="flex bg-dark-800 rounded border border-gray-700 text-[10px]">
                  {[1, 5, 10].map((s) => (
                    <button
                      key={s}
                      onClick={() => setReplaySpeed(s)}
                      className={`px-1.5 py-0.5 rounded transition ${
                        replaySpeed === s ? 'bg-amber-500 text-dark-900 font-bold' : 'text-gray-400 hover:text-white'
                      }`}
                    >
                      {s}x
                    </button>
                  ))}
                </div>

                {/* Play/Pause */}
                <button
                  onClick={handleToggleAutoPlay}
                  className="p-1 bg-amber-500/20 hover:bg-amber-500/30 text-amber-300 rounded border border-amber-500/30"
                  title={isReplaying ? 'Pause' : 'Play'}
                >
                  {isReplaying ? <Pause className="w-3 h-3" /> : <Play className="w-3 h-3" />}
                </button>

                {/* Step 15m */}
                <button
                  onClick={handleStepReplay}
                  className="px-1.5 py-1 bg-amber-500 hover:bg-amber-400 text-dark-900 rounded font-bold text-[10px] flex items-center gap-0.5"
                >
                  <SkipForward className="w-3 h-3" /> Step
                </button>

                <button
                  onClick={handleSwitchToLive}
                  className="px-1.5 py-1 bg-dark-800 hover:bg-dark-700 text-gray-300 rounded text-[10px]"
                >
                  Live
                </button>
              </div>
            )}
          </div>
        </div>
      </header>

      {/* Main Container */}
      <main className="max-w-7xl mx-auto px-4 py-4 flex-1 space-y-4 w-full">
        {/* Top High-Priority Action Banner */}
        <LiveSignalBanner
          signal={activeSignal}
          tradeStatus={tradeStatus}
        />

        {/* Center Grid: Chart (Left) + Kite Execution & Explainability (Right) */}
        <div className="grid grid-cols-1 lg:grid-cols-12 gap-4">
          {/* Center Left — Interactive Intraday Chart (7 Cols) */}
          <div className="lg:col-span-7 space-y-4">
            <IntradayChart
              symbol={selectedSymbol}
              tradeLevels={currentTradeLevels}
            />
          </div>

          {/* Center Right — Actionable Kite Card & Explainability (5 Cols) */}
          <div className="lg:col-span-5 space-y-4">
            <TradeExecutionCard
              signal={activeSignal}
              activeTrade={tradeStatus}
              onEnterTrade={handleEnterTrade}
              onExitTrade={handleExitTrade}
            />

            <ExplainabilityPanel
              positiveReasons={activeSignal?.positive_reasons || []}
              cautionPoints={activeSignal?.caution_points || []}
              shapBreakdown={activeSignal?.shap_breakdown || []}
              pWin={activeSignal?.p_win || 0.65}
              symbol={activeSignal?.symbol || selectedSymbol}
            />
          </div>
        </div>

        {/* Bottom Panel — Two Tabs */}
        <div className="space-y-3">
          {/* Tabs Navigation */}
          <div className="flex items-center gap-2 border-b border-gray-800 pb-2">
            <button
              onClick={() => setBottomTab('WATCHLIST')}
              className={`flex items-center gap-2 px-4 py-2 rounded-lg text-xs font-bold uppercase tracking-wider transition ${
                bottomTab === 'WATCHLIST'
                  ? 'bg-blue-600 text-white shadow-lg shadow-blue-600/20'
                  : 'bg-dark-800 text-gray-400 hover:text-white'
              }`}
            >
              <Activity className="w-4 h-4" />
              <span>Tab 1: Live 10-Stock Watchlist Matrix</span>
            </button>

            <button
              onClick={() => setBottomTab('AUDIT')}
              className={`flex items-center gap-2 px-4 py-2 rounded-lg text-xs font-bold uppercase tracking-wider transition ${
                bottomTab === 'AUDIT'
                  ? 'bg-blue-600 text-white shadow-lg shadow-blue-600/20'
                  : 'bg-dark-800 text-gray-400 hover:text-white'
              }`}
            >
              <Award className="w-4 h-4" />
              <span>Tab 2: Walk-Forward Backtest & Paper Ledger</span>
            </button>
          </div>

          {/* Active Tab Content */}
          {bottomTab === 'WATCHLIST' ? (
            <WatchlistScanner
              rows={scannerRows}
              selectedSymbol={selectedSymbol}
              onSelectSymbol={(sym) => setSelectedSymbol(sym)}
            />
          ) : (
            <WalkForwardAudit />
          )}
        </div>
      </main>

      {/* Footer */}
      <footer className="bg-dark-800 border-t border-gray-800 py-3 text-center text-xs text-gray-500 font-mono">
        Gamma_trader-Web • 100% Manual Zerodha Kite Execution • Free Groww Market Feed • Strict 7-Gate Risk Architecture
      </footer>
    </div>
  );
};

export default App;
