import React, { useState } from 'react';
import { Smartphone, CheckCircle, ShieldCheck, DollarSign, AlertCircle, Clock } from 'lucide-react';

interface SignalCardProps {
  signal: {
    symbol: string;
    display_name: string;
    direction: string;
    setup_type: string;
    entry_limit_price: number;
    quantity: number;
    exposure_rs: number;
    target_price: number;
    stop_loss_price: number;
    breakeven_price: number;
    p_win: number;
    expected_net_ev_rs: number;
    target_net_profit_rs: number;
    stop_net_loss_rs: number;
    zerodha_fee_estimate: number;
    is_actionable: boolean;
    rejection_reasons?: string[];
  } | null;
  activeTrade: {
    active: boolean;
    trade: {
      symbol: string;
      direction: string;
      entry_price: number;
      current_price: number;
      qty: number;
      target_price: number;
      active_stop_price: number;
      breakeven_armed: boolean;
      unrealized_net_pnl: number;
      total_charges: number;
      exit_instructions?: string;
    } | null;
  } | null;
  onEnterTrade: (params: {
    symbol: string;
    direction: string;
    entry_price: number;
    qty: number;
    target_price: number;
    stop_price: number;
  }) => void;
  onExitTrade: () => void;
}

export const TradeExecutionCard: React.FC<SignalCardProps> = ({
  signal,
  activeTrade,
  onEnterTrade,
  onExitTrade
}) => {
  const [copiedField, setCopiedField] = useState<string | null>(null);

  const copyToClipboard = (text: string, field: string) => {
    navigator.clipboard.writeText(text);
    setCopiedField(field);
    setTimeout(() => setCopiedField(null), 1500);
  };

  // 1. ACTIVE POSITION VIEW (Already marked active)
  if (activeTrade?.active && activeTrade.trade) {
    const t = activeTrade.trade;
    const isLong = t.direction === 'LONG' || t.direction === 'BUY';
    const isNetPositive = t.unrealized_net_pnl >= 0;

    return (
      <div className="bg-dark-800 border border-blue-500/50 rounded-xl p-5 shadow-2xl relative overflow-hidden">
        <div className="absolute top-0 left-0 right-0 h-1 bg-gradient-to-r from-blue-500 via-emerald-400 to-amber-400 animate-pulse" />
        
        <div className="flex items-center justify-between mb-4">
          <div className="flex items-center gap-2.5">
            <span className="p-2 bg-blue-500/20 text-blue-400 rounded-lg">
              <Smartphone className="w-5 h-5" />
            </span>
            <div>
              <h3 className="text-base font-black text-white flex items-center gap-2">
                <span>ACTIVE POSITION: {t.symbol}</span>
                <span className={`text-xs px-2 py-0.5 rounded font-black ${
                  isLong ? 'bg-emerald-500/20 text-emerald-400 border border-emerald-500/30' : 'bg-rose-500/20 text-rose-400 border border-rose-500/30'
                }`}>
                  {t.direction} (MIS 5x)
                </span>
              </h3>
              <p className="text-xs text-gray-400">Live Kite exit tracking in progress</p>
            </div>
          </div>
          <div className="text-right">
            <span className="text-[11px] text-gray-400 block uppercase">Net PnL (After Fees)</span>
            <div className={`text-xl font-mono font-black ${isNetPositive ? 'text-emerald-400' : 'text-rose-400'}`}>
              {isNetPositive ? '+' : ''}₹{t.unrealized_net_pnl.toFixed(2)}
            </div>
          </div>
        </div>

        {/* Live Metrics Grid */}
        <div className="grid grid-cols-2 md:grid-cols-4 gap-2.5 bg-dark-900/90 p-3 rounded-lg border border-gray-700/60 mb-4 font-mono text-sm">
          <div>
            <span className="text-[10px] text-gray-500 block uppercase">Qty</span>
            <span className="font-bold text-white">{t.qty} sh</span>
          </div>
          <div>
            <span className="text-[10px] text-gray-500 block uppercase">Fill Price</span>
            <span className="font-bold text-white">₹{t.entry_price.toFixed(2)}</span>
          </div>
          <div>
            <span className="text-[10px] text-gray-500 block uppercase">Live LTP</span>
            <span className="font-bold text-cyan-400">₹{t.current_price.toFixed(2)}</span>
          </div>
          <div>
            <span className="text-[10px] text-gray-500 block uppercase">Stop-Loss</span>
            <span className={`font-bold ${t.breakeven_armed ? 'text-amber-400' : 'text-rose-400'}`}>
              ₹{t.active_stop_price.toFixed(2)} {t.breakeven_armed ? '(BE)' : ''}
            </span>
          </div>
        </div>

        {/* Live Exit Reason Log */}
        <div className="bg-dark-900 border border-gray-700/80 p-3 rounded-lg text-xs space-y-1.5 mb-4">
          <div className="flex items-center gap-1.5 text-gray-400 font-bold uppercase text-[10px]">
            <Clock className="w-3.5 h-3.5 text-cyan-400" />
            <span>Live Exit Reason Log (Updated Every Minute)</span>
          </div>
          <p className="text-gray-300 leading-relaxed">
            {t.exit_instructions ||
              (t.breakeven_armed
                ? `🟡 Stop-loss moved to Cost Breakeven at ₹${t.active_stop_price.toFixed(2)}. Capital is 100% protected at ₹0 net risk. Monitoring for Target at ₹${t.target_price.toFixed(2)}.`
                : `Active trade monitoring: Waiting for +0.55% excursion to arm Cost Breakeven SL at ₹${(t.entry_price * 1.0012).toFixed(2)}. Target barrier set at ₹${t.target_price.toFixed(2)}.`
              )}
          </p>
        </div>

        <button
          onClick={onExitTrade}
          className="w-full py-2.5 px-4 rounded-lg bg-rose-600 hover:bg-rose-500 text-white font-bold text-xs uppercase tracking-wider transition shadow-lg shadow-rose-600/20"
        >
          Position Closed on Kite (Mark Inactive)
        </button>
      </div>
    );
  }

  // 2. FRESH SIGNAL CARD (Exact Kite Inputs)
  if (!signal) {
    return (
      <div className="bg-dark-800 border border-gray-800 rounded-xl p-6 text-center text-gray-400">
        <Smartphone className="w-10 h-10 text-gray-600 mx-auto mb-2 opacity-50" />
        <h4 className="text-sm font-semibold text-gray-300">No Actionable Trade Card</h4>
        <p className="text-xs text-gray-500 mt-1 max-w-sm mx-auto">
          Scanning 10 liquid stocks. Only high-conviction setups meeting all 7 risk gates appear here.
        </p>
      </div>
    );
  }

  const isLong = signal.direction.toUpperCase() === 'LONG' || signal.direction.toUpperCase() === 'BUY';
  const confidencePct = Math.round(signal.p_win * 100);

  return (
    <div className={`border rounded-xl p-5 shadow-2xl relative ${
      signal.is_actionable
        ? isLong ? 'bg-dark-800 border-emerald-500/70 shadow-emerald-500/10' : 'bg-dark-800 border-rose-500/70 shadow-rose-500/10'
        : 'bg-dark-800 border-gray-700/60 opacity-85'
    }`}>
      {/* Header */}
      <div className="flex items-center justify-between pb-3 mb-3 border-b border-gray-700/60">
        <div className="flex items-center gap-2.5">
          <span className="p-2 bg-dark-900 border border-gray-700 rounded-lg text-emerald-400">
            <Smartphone className="w-5 h-5" />
          </span>
          <div>
            <div className="flex items-center gap-2">
              <span className={`text-xs px-2.5 py-0.5 rounded font-black tracking-wide ${
                isLong ? 'bg-emerald-500 text-dark-900' : 'bg-rose-500 text-white'
              }`}>
                {isLong ? 'BUY (LONG)' : 'SELL (SHORT)'}
              </span>
              <span className="text-base font-black text-white">{signal.symbol}</span>
              <span className="text-xs text-purple-300 font-mono bg-purple-900/30 px-2 py-0.5 rounded border border-purple-800/40">
                {signal.setup_type}
              </span>
            </div>
            <p className="text-xs text-gray-400 mt-0.5">{signal.display_name} • MIS Intraday (5x)</p>
          </div>
        </div>

        {/* Win Probability & Confidence Bar */}
        <div className="text-right">
          <span className="text-[10px] text-gray-400 block uppercase font-mono">Calibrated Win Prob</span>
          <span className="text-base font-mono font-bold text-emerald-400">{confidencePct}% P(Win)</span>
          <div className="w-24 h-1.5 bg-dark-900 rounded-full overflow-hidden border border-gray-700 mt-0.5">
            <div className="h-full bg-emerald-400" style={{ width: `${confidencePct}%` }} />
          </div>
        </div>
      </div>

      {/* Exact Kite Mobile Inputs Title */}
      <div className="text-[11px] font-bold uppercase tracking-wider text-gray-400 mb-2 flex items-center justify-between">
        <span>Exact Kite Mobile Order Inputs (₹25,000 Exposure)</span>
        <span className="text-[10px] text-gray-500 lowercase">click value to copy</span>
      </div>

      {/* Parameter Cards Grid */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-2 mb-3">
        {/* Quantity */}
        <div
          onClick={() => copyToClipboard(signal.quantity.toString(), 'qty')}
          className="bg-dark-900/90 border border-gray-700 p-2 rounded-lg cursor-pointer hover:border-gray-500 transition relative"
        >
          <span className="text-[10px] text-gray-400 block uppercase">Quantity</span>
          <span className="text-base font-mono font-bold text-white">{signal.quantity} shares</span>
          <span className="text-[9px] text-gray-500 block">floor(25k / entry)</span>
          {copiedField === 'qty' && <span className="absolute top-1 right-1 text-[9px] text-emerald-400 font-bold">Copied!</span>}
        </div>

        {/* Limit Price */}
        <div
          onClick={() => copyToClipboard(signal.entry_limit_price.toFixed(2), 'price')}
          className="bg-dark-900/90 border border-gray-700 p-2 rounded-lg cursor-pointer hover:border-gray-500 transition relative"
        >
          <span className="text-[10px] text-gray-400 block uppercase">Limit Price</span>
          <span className="text-base font-mono font-bold text-cyan-400">₹{signal.entry_limit_price.toFixed(2)}</span>
          <span className="text-[9px] text-gray-500 block">Order: MIS Limit</span>
          {copiedField === 'price' && <span className="absolute top-1 right-1 text-[9px] text-emerald-400 font-bold">Copied!</span>}
        </div>

        {/* Initial Stop-Loss */}
        <div
          onClick={() => copyToClipboard(signal.stop_loss_price.toFixed(2), 'sl')}
          className="bg-dark-900/90 border border-rose-900/60 p-2 rounded-lg cursor-pointer hover:border-rose-600 transition relative"
        >
          <span className="text-[10px] text-rose-300 block uppercase">Initial SL (SL-M)</span>
          <span className="text-base font-mono font-bold text-rose-400">₹{signal.stop_loss_price.toFixed(2)}</span>
          <span className="text-[9px] text-rose-300/80 block">-₹{Math.abs(signal.stop_net_loss_rs).toFixed(2)} max loss</span>
          {copiedField === 'sl' && <span className="absolute top-1 right-1 text-[9px] text-emerald-400 font-bold">Copied!</span>}
        </div>

        {/* Target Price */}
        <div
          onClick={() => copyToClipboard(signal.target_price.toFixed(2), 'tgt')}
          className="bg-dark-900/90 border border-emerald-900/60 p-2 rounded-lg cursor-pointer hover:border-emerald-600 transition relative"
        >
          <span className="text-[10px] text-emerald-300 block uppercase">Target (Limit)</span>
          <span className="text-base font-mono font-bold text-emerald-400">₹{signal.target_price.toFixed(2)}</span>
          <span className="text-[9px] text-emerald-300/80 block">+₹{signal.target_net_profit_rs.toFixed(2)} net</span>
          {copiedField === 'tgt' && <span className="absolute top-1 right-1 text-[9px] text-emerald-400 font-bold">Copied!</span>}
        </div>
      </div>

      {/* Dynamic Breakeven Rule Callout */}
      <div className="bg-amber-950/30 border border-amber-600/40 rounded-lg p-2.5 text-xs text-amber-200 mb-3 flex items-center justify-between font-mono">
        <div className="flex items-center gap-1.5">
          <ShieldCheck className="w-4 h-4 text-amber-400 shrink-0" />
          <span>Move SL to Breakeven At: <strong>₹{(signal.entry_limit_price * (isLong ? 1.0055 : 0.9945)).toFixed(2)}</strong></span>
        </div>
        <span className="text-amber-300 font-bold">New SL: ₹{signal.breakeven_price.toFixed(2)} (Entry + 0.12%)</span>
      </div>

      {/* Fee & Tax Breakdown Strip */}
      <div className="flex items-center justify-between text-xs text-gray-400 font-mono px-1 mb-3">
        <span>Zerodha Tax & Brokerage: <strong className="text-gray-300">₹{signal.zerodha_fee_estimate.toFixed(2)}</strong></span>
        <span>Expected Net EV: <strong className="text-emerald-400">+{signal.expected_net_ev_rs.toFixed(1)} ₹</strong></span>
      </div>

      {/* Rejections */}
      {!signal.is_actionable && signal.rejection_reasons && signal.rejection_reasons.length > 0 && (
        <div className="p-2.5 bg-rose-950/40 border border-rose-800/60 rounded-lg text-xs text-rose-300 mb-3 flex items-start gap-2">
          <AlertCircle className="w-4 h-4 text-rose-400 shrink-0 mt-0.5" />
          <div>
            <strong className="block font-semibold">Pre-Trade Risk Gatekeeper Blocked This Setup:</strong>
            <ul className="list-disc list-inside mt-0.5 space-y-0.5 text-[11px]">
              {signal.rejection_reasons.map((r, i) => (
                <li key={i}>{r}</li>
              ))}
            </ul>
          </div>
        </div>
      )}

      {/* Action Button: "Mark Trade Active" or "Test Paper Trade" */}
      {signal.is_actionable ? (
        <button
          onClick={() => onEnterTrade({
            symbol: signal.symbol,
            direction: signal.direction,
            entry_price: signal.entry_limit_price,
            qty: signal.quantity,
            target_price: signal.target_price,
            stop_price: signal.stop_loss_price
          })}
          className={`w-full py-2.5 px-4 rounded-xl font-black text-xs uppercase tracking-wider flex items-center justify-center gap-2 shadow-xl transition active:scale-[0.99] ${
            isLong
              ? 'bg-emerald-500 hover:bg-emerald-400 text-dark-900 shadow-emerald-500/25'
              : 'bg-rose-500 hover:bg-rose-400 text-white shadow-rose-500/25'
          }`}
        >
          <CheckCircle className="w-4 h-4" />
          <span>Mark Trade Active (Start Live Exit Tracking)</span>
        </button>
      ) : (
        <button
          onClick={() => onEnterTrade({
            symbol: signal.symbol,
            direction: signal.direction,
            entry_price: signal.entry_limit_price,
            qty: signal.quantity,
            target_price: signal.target_price,
            stop_price: signal.stop_loss_price
          })}
          className="w-full py-2.5 px-4 rounded-xl font-bold text-xs uppercase tracking-wider flex items-center justify-center gap-2 bg-amber-600/20 hover:bg-amber-600/30 text-amber-300 border border-amber-500/40 shadow-lg transition active:scale-[0.99]"
          title="Manually trigger paper trade simulation for this setup"
        >
          <CheckCircle className="w-4 h-4" />
          <span>Simulate Paper Trade (Test Live Exit Engine)</span>
        </button>
      )}
    </div>
  );
};
