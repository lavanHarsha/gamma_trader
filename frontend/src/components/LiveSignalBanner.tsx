import React, { useEffect, useState } from 'react';
import { Volume2, VolumeX, AlertTriangle, CheckCircle, TrendingUp, TrendingDown, ShieldAlert, Sparkles } from 'lucide-react';
import { soundEngine } from '../utils/audio';

interface Signal {
  signal_id: string;
  symbol: string;
  direction: string;
  setup_type: string;
  entry_limit_price: number;
  quantity: number;
  p_win: number;
  expected_net_ev_rs: number;
  target_net_profit_rs: number;
  is_actionable: boolean;
}

interface ActiveTradeStatus {
  active: boolean;
  trade: {
    symbol: string;
    direction: string;
    entry_price: number;
    current_price: number;
    active_stop_price: number;
    target_price: number;
    unrealized_net_pnl: number;
    breakeven_armed: boolean;
    status: string;
    exit_instructions?: string;
    audio_alert_type?: string;
  } | null;
}

interface Props {
  signal: Signal | null;
  tradeStatus: ActiveTradeStatus | null;
}

export const LiveSignalBanner: React.FC<Props> = ({ signal, tradeStatus }) => {
  const [audioEnabled, setAudioEnabled] = useState<boolean>(true);
  const [lastAudioAlert, setLastAudioAlert] = useState<string>('');

  const toggleAudio = () => {
    const next = !audioEnabled;
    setAudioEnabled(next);
    soundEngine.setEnabled(next);
    if (next) soundEngine.playTone(880, 0.1);
  };

  // Play audio alerts based on trade state changes
  useEffect(() => {
    if (!audioEnabled || !tradeStatus?.trade) return;
    const alertType = tradeStatus.trade.audio_alert_type;
    if (alertType && alertType !== lastAudioAlert) {
      setLastAudioAlert(alertType);
      if (alertType === 'BREAKEVEN_CHIME') soundEngine.playBreakevenAlert();
      else if (alertType === 'TARGET_CHIME') soundEngine.playTargetHitAlert();
      else if (alertType === 'REVERSAL_CHIME') soundEngine.playReversalAlert();
      else if (alertType === 'STOP_CHIME') soundEngine.playStopLossAlert();
    }
  }, [tradeStatus, audioEnabled, lastAudioAlert]);

  // Play sound when fresh actionable signal appears
  useEffect(() => {
    if (!audioEnabled || !signal?.is_actionable) return;
    soundEngine.playSignalAlert();
  }, [signal?.signal_id, audioEnabled, signal?.is_actionable]);

  // 1. ACTIVE TRADE MONITORING BANNERS
  if (tradeStatus?.active && tradeStatus.trade) {
    const t = tradeStatus.trade;
    const isBe = t.status === 'BREAKEVEN_ARMED';
    const isProfitable = t.unrealized_net_pnl >= 0;

    if (t.exit_instructions && isBe) {
      return (
        <div className="bg-amber-950/80 border-2 border-amber-500 rounded-xl p-4 flex items-center justify-between shadow-lg shadow-amber-500/10 animate-pulse">
          <div className="flex items-center gap-3">
            <div className="p-3 bg-amber-500/20 rounded-lg text-amber-400">
              <ShieldAlert className="w-8 h-8" />
            </div>
            <div>
              <div className="flex items-center gap-2">
                <span className="text-xs font-bold uppercase tracking-widest px-2 py-0.5 bg-amber-500 text-dark-900 rounded">
                  COST BREAKEVEN TRIGGERED
                </span>
                <span className="text-sm font-mono text-amber-200">Zero Risk Mode Active</span>
              </div>
              <h3 className="text-lg font-bold text-amber-100 mt-1">
                Move Stop-Loss on Kite to ₹{t.active_stop_price.toFixed(2)}
              </h3>
              <p className="text-sm text-amber-300/90">{t.exit_instructions}</p>
            </div>
          </div>
          <button
            onClick={toggleAudio}
            className="p-2.5 rounded-lg bg-dark-800 hover:bg-dark-700 text-gray-300 border border-gray-700"
            title="Toggle Alert Sounds"
          >
            {audioEnabled ? <Volume2 className="w-5 h-5 text-amber-400" /> : <VolumeX className="w-5 h-5 text-gray-500" />}
          </button>
        </div>
      );
    }

    return (
      <div className="bg-dark-800/90 border border-gray-700 rounded-xl p-4 flex items-center justify-between shadow-md">
        <div className="flex items-center gap-3">
          <div className={`p-3 rounded-lg ${t.direction === 'LONG' ? 'bg-emerald-500/20 text-emerald-400' : 'bg-rose-500/20 text-rose-400'}`}>
            {t.direction === 'LONG' ? <TrendingUp className="w-7 h-7" /> : <TrendingDown className="w-7 h-7" />}
          </div>
          <div>
            <div className="flex items-center gap-2">
              <span className="text-xs font-bold px-2 py-0.5 bg-blue-500/20 text-blue-400 border border-blue-500/30 rounded">
                ACTIVE MIS POSITION ON KITE
              </span>
              <span className="text-sm font-bold text-white">{t.symbol}</span>
              <span className="text-xs text-gray-400">({t.direction})</span>
            </div>
            <div className="flex items-center gap-4 mt-1 text-sm font-mono">
              <span className="text-gray-300">Entry: ₹{t.entry_price.toFixed(2)}</span>
              <span className="text-gray-300">Live: ₹{t.current_price.toFixed(2)}</span>
              <span className="text-gray-300">SL: ₹{t.active_stop_price.toFixed(2)}</span>
              <span className="text-gray-300">Target: ₹{t.target_price.toFixed(2)}</span>
              <span className={`font-bold ${isProfitable ? 'text-emerald-400' : 'text-rose-400'}`}>
                Net PnL: {isProfitable ? '+' : ''}₹{t.unrealized_net_pnl.toFixed(2)}
              </span>
            </div>
          </div>
        </div>
        <button
          onClick={toggleAudio}
          className="p-2.5 rounded-lg bg-dark-900 hover:bg-dark-700 text-gray-300 border border-gray-700"
        >
          {audioEnabled ? <Volume2 className="w-5 h-5 text-emerald-400" /> : <VolumeX className="w-5 h-5 text-gray-500" />}
        </button>
      </div>
    );
  }

  // 2. FRESH ACTIONABLE HIGH-CONVICTION SIGNAL BANNER
  if (signal && signal.is_actionable) {
    const isLong = signal.direction.toUpperCase() === 'LONG' || signal.direction.toUpperCase() === 'BUY';
    return (
      <div className={`border-2 rounded-xl p-4 flex items-center justify-between shadow-xl ${
        isLong
          ? 'bg-emerald-950/80 border-emerald-500 shadow-emerald-500/20'
          : 'bg-rose-950/80 border-rose-500 shadow-rose-500/20'
      }`}>
        <div className="flex items-center gap-4">
          <div className={`p-3 rounded-lg ${isLong ? 'bg-emerald-500 text-dark-900' : 'bg-rose-500 text-white'}`}>
            {isLong ? <TrendingUp className="w-8 h-8 font-black" /> : <TrendingDown className="w-8 h-8 font-black" />}
          </div>
          <div>
            <div className="flex items-center gap-2">
              <span className={`text-xs font-black uppercase tracking-widest px-2.5 py-0.5 rounded ${
                isLong ? 'bg-emerald-400 text-dark-900' : 'bg-rose-400 text-dark-900'
              }`}>
                HIGH CONVICTION ACTIONABLE SIGNAL
              </span>
              <span className="text-xs bg-dark-800 text-gray-300 px-2 py-0.5 rounded border border-gray-700">
                Setup: {signal.setup_type}
              </span>
            </div>
            <h2 className="text-xl font-black text-white mt-1 flex items-center gap-3">
              <span>{isLong ? 'EXECUTE BUY ON KITE' : 'EXECUTE SHORT ON KITE'}: {signal.symbol}</span>
              <span className="text-gray-300 text-base font-normal font-mono">
                Qty: {signal.quantity} @ Limit ₹{signal.entry_limit_price.toFixed(2)}
              </span>
            </h2>
            <div className="flex items-center gap-4 mt-1 text-xs font-mono text-gray-300">
              <span className="text-emerald-300 font-bold">P(Win): {(signal.p_win * 100).toFixed(1)}%</span>
              <span className="text-cyan-300 font-bold">Net EV: +₹{signal.expected_net_ev_rs.toFixed(1)}</span>
              <span>Target: +₹{signal.target_net_profit_rs.toFixed(0)} net</span>
              <span className="text-gray-400">Max Risk: -₹185 hard-cap</span>
            </div>
          </div>
        </div>
        <div className="flex items-center gap-3">
          <button
            onClick={toggleAudio}
            className="p-2.5 rounded-lg bg-dark-900 hover:bg-dark-800 text-gray-300 border border-gray-700"
            title="Toggle Alert Sounds"
          >
            {audioEnabled ? <Volume2 className="w-5 h-5 text-emerald-400" /> : <VolumeX className="w-5 h-5 text-gray-500" />}
          </button>
        </div>
      </div>
    );
  }

  // 3. IDLE / SCANNING STATE BANNER
  return (
    <div className="bg-dark-800/60 border border-gray-800 rounded-xl p-3.5 flex items-center justify-between text-gray-400">
      <div className="flex items-center gap-3">
        <div className="w-2.5 h-2.5 rounded-full bg-emerald-500 animate-ping" />
        <span className="text-sm font-medium text-gray-300">
          Scanning 10 Liquid NSE Stocks for Stage-1 Setups (ORB, VWAP Pullback, Vol Squeeze)
        </span>
        <span className="text-xs bg-dark-900 text-gray-400 px-2 py-0.5 rounded border border-gray-700/60 font-mono">
          Strict Edge Gate: P(Win) ≥ 62% & Net EV ≥ +₹65
        </span>
      </div>
      <div className="flex items-center gap-3">
        <button
          onClick={toggleAudio}
          className="p-1.5 rounded-lg bg-dark-900 hover:bg-dark-800 text-gray-400 hover:text-gray-200 border border-gray-800"
          title="Toggle Alert Sounds"
        >
          {audioEnabled ? <Volume2 className="w-4 h-4 text-emerald-400" /> : <VolumeX className="w-4 h-4 text-gray-500" />}
        </button>
      </div>
    </div>
  );
};

