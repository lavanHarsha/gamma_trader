import React, { useEffect, useRef, useState } from 'react';
import {
  createChart,
  CandlestickSeries,
  LineSeries,
  HistogramSeries,
  type IChartApi,
  type CandlestickData,
  type LineData,
  type HistogramData,
  type Time
} from 'lightweight-charts';
import { BarChart3, RefreshCw } from 'lucide-react';

interface BarData {
  time: number; // Unix timestamp in seconds
  open: number;
  high: number;
  low: number;
  close: number;
  volume: number;
  vwap?: number;
  orb_high?: number;
  orb_low?: number;
  ema_9?: number;
  ema_21?: number;
}

interface TradeLevels {
  entryPrice?: number;
  targetPrice?: number;
  stopPrice?: number;
  breakevenPrice?: number;
  direction?: string;
}

interface Props {
  symbol: string;
  tradeLevels?: TradeLevels | null;
}

export const IntradayChart: React.FC<Props> = ({ symbol, tradeLevels }) => {
  const chartContainerRef = useRef<HTMLDivElement>(null);
  const chartRef = useRef<IChartApi | null>(null);
  const [interval, setIntervalVal] = useState<number>(15);
  const [bars, setBars] = useState<BarData[]>([]);
  const [loading, setLoading] = useState<boolean>(true);
  const [currentBarInfo, setCurrentBarInfo] = useState<BarData | null>(null);

  const fetchBars = async (intVal: number = interval) => {
    setLoading(true);
    try {
      const res = await fetch(`http://localhost:8000/api/bars/${symbol}?interval=${intVal}`);
      if (res.ok) {
        const data: BarData[] = await res.json();
        setBars(data);
        if (data.length > 0) {
          setCurrentBarInfo(data[data.length - 1]);
        }
      }
    } catch (e) {
      console.error('Error fetching bars:', e);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchBars(interval);
  }, [symbol, interval]);

  useEffect(() => {
    if (!chartContainerRef.current || bars.length === 0) return;

    if (chartRef.current) {
      chartRef.current.remove();
      chartRef.current = null;
    }

    const container = chartContainerRef.current;
    const chart = createChart(container, {
      width: container.clientWidth,
      height: 440,
      layout: {
        background: { color: '#0b0f19' },
        textColor: '#9ca3af',
      },
      grid: {
        vertLines: { color: '#1f2937' },
        horzLines: { color: '#1f2937' },
      },
      crosshair: {
        mode: 1,
      },
      rightPriceScale: {
        borderColor: '#374151',
      },
      timeScale: {
        borderColor: '#374151',
        timeVisible: true,
        secondsVisible: false,
      },
    });

    chartRef.current = chart;

    // 1. Candlestick series
    const candleSeries = chart.addSeries(CandlestickSeries, {
      upColor: '#10b981',
      downColor: '#ef4444',
      borderVisible: false,
      wickUpColor: '#10b981',
      wickDownColor: '#ef4444',
    });

    const candleData: CandlestickData[] = bars.map(b => ({
      time: b.time as Time,
      open: b.open,
      high: b.high,
      low: b.low,
      close: b.close,
    }));
    candleSeries.setData(candleData);

    // 2. Volume Histogram (sub-pane at bottom)
    const volumeSeries = chart.addSeries(HistogramSeries, {
      priceFormat: {
        type: 'volume',
      },
      priceScaleId: 'volume',
    });
    chart.priceScale('volume').applyOptions({
      scaleMargins: {
        top: 0.8,
        bottom: 0,
      },
    });

    const volumeData: HistogramData[] = bars.map(b => ({
      time: b.time as Time,
      value: b.volume,
      color: b.close >= b.open ? 'rgba(16, 185, 129, 0.35)' : 'rgba(239, 68, 68, 0.35)',
    }));
    volumeSeries.setData(volumeData);

    // 3. Overlaid Intraday VWAP (Yellow)
    const vwapSeries = chart.addSeries(LineSeries, {
      color: '#eab308', // Yellow
      lineWidth: 2,
      title: 'VWAP',
    });
    const vwapData: LineData[] = bars
      .filter(b => b.vwap !== undefined)
      .map(b => ({ time: b.time as Time, value: b.vwap! }));
    vwapSeries.setData(vwapData);

    // 4. Overlaid EMA 9 (Blue)
    const ema9Series = chart.addSeries(LineSeries, {
      color: '#3b82f6', // Blue
      lineWidth: 1,
      title: 'EMA 9',
    });
    const ema9Data: LineData[] = bars
      .filter(b => b.ema_9 !== undefined)
      .map(b => ({ time: b.time as Time, value: b.ema_9! }));
    ema9Series.setData(ema9Data);

    // 5. Overlaid EMA 21 (Purple)
    const ema21Series = chart.addSeries(LineSeries, {
      color: '#a855f7', // Purple
      lineWidth: 1,
      title: 'EMA 21',
    });
    const ema21Data: LineData[] = bars
      .filter(b => b.ema_21 !== undefined)
      .map(b => ({ time: b.time as Time, value: b.ema_21! }));
    ema21Series.setData(ema21Data);

    // 6. ORB 15m Range Lines (Amber dashed)
    const lastBar = bars[bars.length - 1];
    if (lastBar.orb_high && lastBar.orb_low) {
      candleSeries.createPriceLine({
        price: lastBar.orb_high,
        color: '#f97316',
        lineWidth: 1,
        lineStyle: 2, // Dashed
        axisLabelVisible: true,
        title: `ORB-H (₹${lastBar.orb_high.toFixed(2)})`,
      });
      candleSeries.createPriceLine({
        price: lastBar.orb_low,
        color: '#f97316',
        lineWidth: 1,
        lineStyle: 2, // Dashed
        axisLabelVisible: true,
        title: `ORB-L (₹${lastBar.orb_low.toFixed(2)})`,
      });
    }

    // 7. Dynamic Signal Price Lines
    if (tradeLevels?.entryPrice) {
      candleSeries.createPriceLine({
        price: tradeLevels.entryPrice,
        color: '#38bdf8', // Blue
        lineWidth: 2,
        lineStyle: 0, // Solid
        axisLabelVisible: true,
        title: `ENTRY (₹${tradeLevels.entryPrice.toFixed(2)})`,
      });
    }

    if (tradeLevels?.targetPrice) {
      candleSeries.createPriceLine({
        price: tradeLevels.targetPrice,
        color: '#10b981', // Emerald Green
        lineWidth: 2,
        lineStyle: 2, // Dashed
        axisLabelVisible: true,
        title: `TARGET (₹${tradeLevels.targetPrice.toFixed(2)})`,
      });
    }

    if (tradeLevels?.stopPrice) {
      candleSeries.createPriceLine({
        price: tradeLevels.stopPrice,
        color: '#ef4444', // Red
        lineWidth: 2,
        lineStyle: 2, // Dashed
        axisLabelVisible: true,
        title: `INITIAL SL (₹${tradeLevels.stopPrice.toFixed(2)})`,
      });
    }

    if (tradeLevels?.breakevenPrice) {
      candleSeries.createPriceLine({
        price: tradeLevels.breakevenPrice,
        color: '#f59e0b', // Amber
        lineWidth: 1,
        lineStyle: 1, // Dotted
        axisLabelVisible: true,
        title: `BREAKEVEN (₹${tradeLevels.breakevenPrice.toFixed(2)})`,
      });
    }

    chart.timeScale().fitContent();

    // Crosshair tooltip
    chart.subscribeCrosshairMove(param => {
      if (param.time && param.seriesData.get(candleSeries)) {
        const c = param.seriesData.get(candleSeries) as { open: number; high: number; low: number; close: number };
        const matchingBar = bars.find(b => b.time === (param.time as number));
        if (c && matchingBar) {
          setCurrentBarInfo({
            ...matchingBar,
            open: c.open,
            high: c.high,
            low: c.low,
            close: c.close,
          });
        }
      }
    });

    const handleResize = () => {
      if (container && chartRef.current) {
        chartRef.current.applyOptions({ width: container.clientWidth });
      }
    };
    window.addEventListener('resize', handleResize);

    return () => {
      window.removeEventListener('resize', handleResize);
      if (chartRef.current) {
        chartRef.current.remove();
        chartRef.current = null;
      }
    };
  }, [bars, tradeLevels]);

  return (
    <div className="bg-dark-800 border border-gray-700/80 rounded-xl p-4 shadow-xl">
      {/* Header with Stock Info, Interval Toggle & Legend */}
      <div className="flex flex-wrap items-center justify-between pb-3 mb-2 border-b border-gray-700/60 gap-2">
        <div className="flex items-center gap-3">
          <span className="p-1.5 bg-dark-900 border border-gray-700 rounded-lg text-cyan-400">
            <BarChart3 className="w-5 h-5" />
          </span>
          <div>
            <div className="flex items-center gap-2">
              <h3 className="text-base font-bold text-white">{symbol}</h3>
              {/* 15m & 5m Interval Toggle */}
              <div className="flex bg-dark-900 rounded border border-gray-700 p-0.5 text-xs font-mono">
                <button
                  onClick={() => setIntervalVal(15)}
                  className={`px-2 py-0.5 rounded transition ${
                    interval === 15 ? 'bg-blue-600 text-white font-bold' : 'text-gray-400 hover:text-white'
                  }`}
                >
                  15m
                </button>
                <button
                  onClick={() => setIntervalVal(5)}
                  className={`px-2 py-0.5 rounded transition ${
                    interval === 5 ? 'bg-blue-600 text-white font-bold' : 'text-gray-400 hover:text-white'
                  }`}
                >
                  5m
                </button>
              </div>
            </div>
            {currentBarInfo && (
              <div className="flex items-center gap-3 text-xs font-mono text-gray-400 mt-0.5">
                <span>O: <strong className="text-white">₹{currentBarInfo.open.toFixed(2)}</strong></span>
                <span>H: <strong className="text-white">₹{currentBarInfo.high.toFixed(2)}</strong></span>
                <span>L: <strong className="text-white">₹{currentBarInfo.low.toFixed(2)}</strong></span>
                <span>C: <strong className="text-cyan-300">₹{currentBarInfo.close.toFixed(2)}</strong></span>
                <span>Vol: <strong className="text-gray-300">{currentBarInfo.volume.toLocaleString()}</strong></span>
              </div>
            )}
          </div>
        </div>

        {/* Indicator Color Legend */}
        <div className="flex items-center gap-3 text-xs font-mono">
          <div className="flex items-center gap-1.5 text-yellow-400">
            <span className="w-2.5 h-0.5 bg-yellow-400 inline-block" />
            <span>VWAP</span>
          </div>
          <div className="flex items-center gap-1.5 text-blue-400">
            <span className="w-2.5 h-0.5 bg-blue-400 inline-block" />
            <span>EMA 9</span>
          </div>
          <div className="flex items-center gap-1.5 text-purple-400">
            <span className="w-2.5 h-0.5 bg-purple-400 inline-block" />
            <span>EMA 21</span>
          </div>
          <div className="flex items-center gap-1.5 text-orange-400">
            <span className="w-2.5 h-0.5 bg-orange-400 inline-block border-dashed" />
            <span>ORB</span>
          </div>
          <button
            onClick={() => fetchBars(interval)}
            className="p-1 rounded-lg bg-dark-900 hover:bg-dark-700 text-gray-400 hover:text-white border border-gray-700 ml-1"
            title="Refresh"
          >
            <RefreshCw className={`w-3.5 h-3.5 ${loading ? 'animate-spin' : ''}`} />
          </button>
        </div>
      </div>

      {/* Chart Canvas */}
      <div className="relative">
        {loading && bars.length === 0 && (
          <div className="absolute inset-0 bg-dark-900/80 flex items-center justify-center text-sm text-gray-400 z-10 rounded-lg">
            Loading chart data...
          </div>
        )}
        <div ref={chartContainerRef} className="w-full rounded-lg overflow-hidden" />
      </div>
    </div>
  );
};
