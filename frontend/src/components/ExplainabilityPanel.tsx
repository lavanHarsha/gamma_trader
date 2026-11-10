import React, { useState } from 'react';
import { Cpu, Check, AlertTriangle, ChevronDown, ChevronUp, BarChart2 } from 'lucide-react';

interface SHAPReason {
  title: string;
  feature: string;
  raw_value: number;
  shap_contribution: number;
  description: string;
  impact: 'POSITIVE' | 'CAUTION';
}

interface SHAPItem {
  feature: string;
  shap_contribution: number;
  raw_value: number;
}

interface Props {
  positiveReasons: SHAPReason[];
  cautionPoints: SHAPReason[];
  shapBreakdown: SHAPItem[];
  pWin: number;
  symbol: string;
}

export const ExplainabilityPanel: React.FC<Props> = ({
  positiveReasons,
  cautionPoints,
  shapBreakdown,
  pWin,
  symbol
}) => {
  const [showFullBreakdown, setShowFullBreakdown] = useState<boolean>(false);

  // Key institutional metrics to highlight
  const getKeyMetric = (name: string): { raw: number; shap: number } => {
    const item = shapBreakdown.find(x => x.feature.includes(name));
    return item ? { raw: item.raw_value, shap: item.shap_contribution } : { raw: 0, shap: 0 };
  };

  const rvolMetric = getKeyMetric('rvol');
  const sectorMetric = getKeyMetric('sector_rel_strength');
  const vwapMetric = getKeyMetric('vwap_z');
  const efficiencyMetric = getKeyMetric('kaufman_efficiency');
  const fuelMetric = getKeyMetric('day_range_exhaustion');

  return (
    <div className="bg-dark-800 border border-gray-700/80 rounded-xl p-5 shadow-xl space-y-4">
      {/* Header */}
      <div className="flex items-center justify-between pb-3 border-b border-gray-700/60">
        <div className="flex items-center gap-2">
          <span className="p-1.5 bg-purple-500/20 text-purple-400 rounded-lg">
            <Cpu className="w-5 h-5" />
          </span>
          <div>
            <h3 className="text-sm font-black text-white">
              Why Buy / Why Sell: Explainability Box
            </h3>
            <p className="text-[11px] text-gray-400">
              SHAP TreeExplainer decomposing mathematical conviction for {symbol}
            </p>
          </div>
        </div>
        <div className="text-right">
          <span className="text-[10px] text-gray-400 block uppercase font-mono">Calibrated Win Prob</span>
          <span className="text-sm font-mono font-bold text-emerald-400">
            {(pWin * 100).toFixed(1)}% P(Win)
          </span>
        </div>
      </div>

      {/* Horizontal Green/Red SHAP Contribution Bars (5 Core Microstructure Pillars) */}
      <div className="bg-dark-900/90 border border-gray-700/70 rounded-lg p-3.5 space-y-2.5">
        <div className="flex items-center justify-between text-xs font-bold text-gray-300 uppercase tracking-wider mb-1">
          <span className="flex items-center gap-1.5">
            <BarChart2 className="w-3.5 h-3.5 text-purple-400" />
            <span>Key Institutional Pillars (SHAP Impact)</span>
          </span>
          <span className="text-[10px] text-gray-500">Green = Bullish, Red = Drag</span>
        </div>

        {/* 1. Volume RVOL */}
        <div className="space-y-0.5">
          <div className="flex justify-between text-xs font-mono">
            <span className="text-gray-400">Volume RVOL (ToD): <strong>{rvolMetric.raw.toFixed(1)}x</strong></span>
            <span className={rvolMetric.shap >= 0 ? 'text-emerald-400 font-bold' : 'text-rose-400 font-bold'}>
              {rvolMetric.shap >= 0 ? '+' : ''}{rvolMetric.shap.toFixed(3)}
            </span>
          </div>
          <div className="h-1.5 bg-dark-800 rounded-full overflow-hidden flex">
            <div
              className={`h-full ${rvolMetric.shap >= 0 ? 'bg-emerald-400' : 'bg-rose-500'}`}
              style={{ width: `${Math.min(100, Math.max(15, Math.abs(rvolMetric.shap) * 500))}%` }}
            />
          </div>
        </div>

        {/* 2. Sector Relative Strength */}
        <div className="space-y-0.5">
          <div className="flex justify-between text-xs font-mono">
            <span className="text-gray-400">Sector Rel Strength: <strong>{(sectorMetric.raw * 100).toFixed(2)}%</strong></span>
            <span className={sectorMetric.shap >= 0 ? 'text-emerald-400 font-bold' : 'text-rose-400 font-bold'}>
              {sectorMetric.shap >= 0 ? '+' : ''}{sectorMetric.shap.toFixed(3)}
            </span>
          </div>
          <div className="h-1.5 bg-dark-800 rounded-full overflow-hidden flex">
            <div
              className={`h-full ${sectorMetric.shap >= 0 ? 'bg-emerald-400' : 'bg-rose-500'}`}
              style={{ width: `${Math.min(100, Math.max(15, Math.abs(sectorMetric.shap) * 500))}%` }}
            />
          </div>
        </div>

        {/* 3. VWAP Z-Score */}
        <div className="space-y-0.5">
          <div className="flex justify-between text-xs font-mono">
            <span className="text-gray-400">VWAP Z-Score: <strong>{vwapMetric.raw.toFixed(2)}σ</strong></span>
            <span className={vwapMetric.shap >= 0 ? 'text-emerald-400 font-bold' : 'text-rose-400 font-bold'}>
              {vwapMetric.shap >= 0 ? '+' : ''}{vwapMetric.shap.toFixed(3)}
            </span>
          </div>
          <div className="h-1.5 bg-dark-800 rounded-full overflow-hidden flex">
            <div
              className={`h-full ${vwapMetric.shap >= 0 ? 'bg-emerald-400' : 'bg-rose-500'}`}
              style={{ width: `${Math.min(100, Math.max(15, Math.abs(vwapMetric.shap) * 500))}%` }}
            />
          </div>
        </div>

        {/* 4. Kaufman Efficiency Ratio */}
        <div className="space-y-0.5">
          <div className="flex justify-between text-xs font-mono">
            <span className="text-gray-400">Trend Efficiency: <strong>{(efficiencyMetric.raw * 100).toFixed(0)}%</strong></span>
            <span className={efficiencyMetric.shap >= 0 ? 'text-emerald-400 font-bold' : 'text-rose-400 font-bold'}>
              {efficiencyMetric.shap >= 0 ? '+' : ''}{efficiencyMetric.shap.toFixed(3)}
            </span>
          </div>
          <div className="h-1.5 bg-dark-800 rounded-full overflow-hidden flex">
            <div
              className={`h-full ${efficiencyMetric.shap >= 0 ? 'bg-emerald-400' : 'bg-rose-500'}`}
              style={{ width: `${Math.min(100, Math.max(15, Math.abs(efficiencyMetric.shap) * 500))}%` }}
            />
          </div>
        </div>

        {/* 5. Remaining Daily ATR Fuel */}
        <div className="space-y-0.5">
          <div className="flex justify-between text-xs font-mono">
            <span className="text-gray-400">Daily Fuel Used: <strong>{(fuelMetric.raw * 100).toFixed(0)}%</strong></span>
            <span className={fuelMetric.shap >= 0 ? 'text-emerald-400 font-bold' : 'text-rose-400 font-bold'}>
              {fuelMetric.shap >= 0 ? '+' : ''}{fuelMetric.shap.toFixed(3)}
            </span>
          </div>
          <div className="h-1.5 bg-dark-800 rounded-full overflow-hidden flex">
            <div
              className={`h-full ${fuelMetric.shap >= 0 ? 'bg-emerald-400' : 'bg-amber-400'}`}
              style={{ width: `${Math.min(100, Math.max(15, (1.0 - fuelMetric.raw) * 100))}%` }}
            />
          </div>
        </div>
      </div>

      {/* Plain-English Explanations Generated by explainer.py */}
      <div>
        <h4 className="text-xs font-bold text-emerald-400 uppercase tracking-wider mb-2 flex items-center gap-1.5">
          <Check className="w-3.5 h-3.5" />
          <span>Top Institutional Reasons (Plain-English)</span>
        </h4>
        <div className="space-y-2">
          {positiveReasons.length > 0 ? (
            positiveReasons.map((item, idx) => (
              <div
                key={idx}
                className="bg-dark-900 border border-emerald-950/80 p-2.5 rounded-lg text-xs"
              >
                <div className="flex items-center justify-between font-bold text-emerald-300">
                  <span>{item.title}</span>
                  <span className="font-mono text-emerald-400 bg-emerald-500/10 px-1.5 py-0.2 rounded text-[10px]">
                    +{item.shap_contribution.toFixed(3)}
                  </span>
                </div>
                <p className="text-gray-300 mt-0.5 leading-relaxed text-[11px]">{item.description}</p>
              </div>
            ))
          ) : (
            <p className="text-xs text-gray-500 italic">Institutional factors within normal baseline parameters.</p>
          )}
        </div>
      </div>

      {/* Caution & Nuance Points */}
      {cautionPoints && cautionPoints.length > 0 && (
        <div>
          <h4 className="text-xs font-bold text-amber-400 uppercase tracking-wider mb-2 flex items-center gap-1.5">
            <AlertTriangle className="w-3.5 h-3.5" />
            <span>Risk Factors & Nuances To Watch</span>
          </h4>
          <div className="space-y-2">
            {cautionPoints.map((item, idx) => (
              <div
                key={idx}
                className="bg-dark-900 border border-amber-950/80 p-2.5 rounded-lg text-xs"
              >
                <div className="flex items-center justify-between font-bold text-amber-300">
                  <span>{item.title}</span>
                  <span className="font-mono text-amber-400 bg-amber-500/10 px-1.5 py-0.2 rounded text-[10px]">
                    {item.shap_contribution.toFixed(3)}
                  </span>
                </div>
                <p className="text-gray-300 mt-0.5 leading-relaxed text-[11px]">{item.description}</p>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Expandable Table for All 22 Features */}
      <div>
        <button
          onClick={() => setShowFullBreakdown(!showFullBreakdown)}
          className="w-full py-1.5 px-3 rounded-lg bg-dark-900 hover:bg-dark-700 text-xs font-semibold text-gray-400 hover:text-gray-200 flex items-center justify-between border border-gray-700/60 transition"
        >
          <span>All 22 Stationary Features</span>
          {showFullBreakdown ? <ChevronUp className="w-3.5 h-3.5" /> : <ChevronDown className="w-3.5 h-3.5" />}
        </button>

        {showFullBreakdown && (
          <div className="mt-2 bg-dark-900 rounded-lg p-2.5 border border-gray-700 max-h-56 overflow-y-auto">
            <table className="w-full text-left text-[11px] font-mono">
              <thead>
                <tr className="border-b border-gray-800 text-gray-500 text-[10px] uppercase">
                  <th className="py-1">Feature</th>
                  <th className="py-1 text-right">Raw</th>
                  <th className="py-1 text-right">SHAP</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-800/60">
                {shapBreakdown.map((item, i) => {
                  const isPos = item.shap_contribution >= 0;
                  return (
                    <tr key={i}>
                      <td className="py-1 text-gray-300">{item.feature}</td>
                      <td className="py-1 text-right text-gray-400">{item.raw_value.toFixed(3)}</td>
                      <td className={`py-1 text-right font-bold ${isPos ? 'text-emerald-400' : 'text-rose-400'}`}>
                        {isPos ? '+' : ''}{item.shap_contribution.toFixed(3)}
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  );
};
