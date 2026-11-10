import React from 'react';
import { Activity, Eye, Zap } from 'lucide-react';

export interface ScannerRow {
  symbol: string;
  name: string;
  sector: string;
  price: number;
  change_pct: number;
  rvol: number;
  vwap_z: number;
  sector_rel_strength_pct: number;
  day_range_used_pct: number;
  regime: 'BULLISH' | 'BEARISH' | 'CHOPPY' | 'NEUTRAL';
  setup: string;
  win_prob_pct: number;
  is_actionable: boolean;
}

interface Props {
  rows: ScannerRow[];
  selectedSymbol: string;
  onSelectSymbol: (symbol: string) => void;
}

export const WatchlistScanner: React.FC<Props> = ({
  rows,
  selectedSymbol,
  onSelectSymbol
}) => {
  return (
    <div className="bg-dark-800 border border-gray-700/80 rounded-xl overflow-hidden shadow-xl">
      {/* Table Header */}
      <div className="p-3.5 border-b border-gray-700/60 flex items-center justify-between">
        <div className="flex items-center gap-2">
          <Activity className="w-4 h-4 text-cyan-400" />
          <h3 className="text-sm font-bold text-white uppercase tracking-wider">
            Live 10-Stock Watchlist Matrix (NSE MIS 5x)
          </h3>
        </div>
        <span className="text-[11px] text-gray-400 font-mono">
          Tight ₹0.01–₹0.05 Spreads • 09:15–15:30 IST
        </span>
      </div>

      <div className="overflow-x-auto">
        <table className="w-full text-left text-xs font-mono">
          <thead className="bg-dark-900/90 text-gray-400 uppercase text-[10px] tracking-wider border-b border-gray-800">
            <tr>
              <th className="py-2.5 px-3">Stock / Sector</th>
              <th className="py-2.5 px-2.5 text-right">LTP (₹)</th>
              <th className="py-2.5 px-2.5 text-right">% Chg</th>
              <th className="py-2.5 px-2.5 text-center">RVOL (ToD)</th>
              <th className="py-2.5 px-2.5 text-right">VWAP Z</th>
              <th className="py-2.5 px-2.5 text-right">Sector RS</th>
              <th className="py-2.5 px-2.5 text-center">Range Used %</th>
              <th className="py-2.5 px-2.5 text-center">Setup Status</th>
              <th className="py-2.5 px-2.5 text-right">ML P(Win)</th>
              <th className="py-2.5 px-3 text-center">Chart</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-gray-800/80">
            {rows.map((row) => {
              const isSelected = row.symbol === selectedSymbol;
              const isPositive = row.change_pct >= 0;
              const hasEdge = row.win_prob_pct >= 62;

              return (
                <tr
                  key={row.symbol}
                  onClick={() => onSelectSymbol(row.symbol)}
                  className={`cursor-pointer transition ${
                    isSelected
                      ? 'bg-blue-950/40 border-l-4 border-blue-500'
                      : 'hover:bg-dark-700/40'
                  }`}
                >
                  <td className="py-2.5 px-3">
                    <div className="flex items-center gap-1.5">
                      <span className="font-bold text-white text-xs">{row.symbol}</span>
                      {row.is_actionable && (
                        <span className="px-1 py-0.2 bg-emerald-500 text-dark-900 font-black text-[9px] rounded uppercase animate-bounce">
                          SIGNAL
                        </span>
                      )}
                    </div>
                    <span className="text-[10px] text-gray-500 block truncate max-w-[110px]">{row.sector}</span>
                  </td>

                  {/* LTP */}
                  <td className="py-2.5 px-2.5 text-right font-bold text-white">
                    ₹{row.price.toFixed(2)}
                  </td>

                  {/* % Change */}
                  <td className={`py-2.5 px-2.5 text-right font-bold ${isPositive ? 'text-emerald-400' : 'text-rose-400'}`}>
                    {isPositive ? '+' : ''}{row.change_pct.toFixed(2)}%
                  </td>

                  {/* RVOL_tod */}
                  <td className="py-2.5 px-2.5 text-center">
                    <span className={`font-bold ${row.rvol >= 1.35 ? 'text-amber-400' : 'text-gray-300'}`}>
                      {row.rvol.toFixed(1)}x
                    </span>
                  </td>

                  {/* VWAP Z-Score */}
                  <td className="py-2.5 px-2.5 text-right">
                    <span className={`font-bold ${(row.vwap_z || 0) >= 0 ? 'text-cyan-400' : 'text-purple-400'}`}>
                      {(row.vwap_z || 0) > 0 ? '+' : ''}{(row.vwap_z || 0).toFixed(1)}σ
                    </span>
                  </td>

                  {/* Sector RelStrength */}
                  <td className="py-2.5 px-2.5 text-right">
                    <span className={(row.sector_rel_strength_pct || 0) >= 0 ? 'text-emerald-400' : 'text-rose-400'}>
                      {(row.sector_rel_strength_pct || 0) >= 0 ? '+' : ''}{(row.sector_rel_strength_pct || 0).toFixed(2)}%
                    </span>
                  </td>

                  {/* Day Range Used % */}
                  <td className="py-2.5 px-2.5 text-center">
                    <div className="flex items-center justify-center gap-1">
                      <span className={`text-[11px] ${(row.day_range_used_pct || 50) > 78 ? 'text-rose-400 font-bold' : 'text-gray-300'}`}>
                        {(row.day_range_used_pct || 50).toFixed(0)}%
                      </span>
                      <div className="w-8 h-1.5 bg-dark-900 rounded-full overflow-hidden border border-gray-700">
                        <div
                          className={`h-full ${(row.day_range_used_pct || 50) > 78 ? 'bg-rose-500' : 'bg-cyan-500'}`}
                          style={{ width: `${Math.min(100, row.day_range_used_pct || 50)}%` }}
                        />
                      </div>
                    </div>
                  </td>

                  {/* Stage-1 Setup Status */}
                  <td className="py-2.5 px-2.5 text-center">
                    <span className={`px-1.5 py-0.5 rounded text-[10px] font-semibold ${
                      row.setup !== 'IDLE' && row.setup !== 'WATCH'
                        ? 'bg-purple-500/20 text-purple-300 border border-purple-500/30'
                        : 'text-gray-500'
                    }`}>
                      {row.setup}
                    </span>
                  </td>

                  {/* Live ML Win Prob % */}
                  <td className="py-2.5 px-2.5 text-right">
                    <span className={`font-bold ${hasEdge ? 'text-emerald-400' : 'text-gray-400'}`}>
                      {(row.win_prob_pct || 50).toFixed(1)}%
                    </span>
                  </td>

                  <td className="py-2.5 px-3 text-center">
                    <button
                      onClick={(e) => {
                        e.stopPropagation();
                        onSelectSymbol(row.symbol);
                      }}
                      className="p-1 rounded bg-dark-900 hover:bg-dark-700 text-gray-400 hover:text-white border border-gray-700"
                      title="Load Chart"
                    >
                      <Eye className="w-3.5 h-3.5" />
                    </button>
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    </div>
  );
};
