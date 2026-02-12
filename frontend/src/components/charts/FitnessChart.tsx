import { useMemo } from 'react';
import {
  ResponsiveContainer,
  ComposedChart,
  Line,
  Area,
  XAxis,
  YAxis,
  Tooltip,
  ReferenceLine,
  Brush,
  CartesianGrid,
  Legend,
} from 'recharts';
import type { FitnessDataPoint } from '../../api/types.ts';
import { format } from 'date-fns';
import './FitnessChart.css';

interface Props {
  data: FitnessDataPoint[];
}

interface ChartDataPoint {
  date: string;
  dateLabel: string;
  ctl: number;
  atl: number;
  tsbPositive: number | null;
  tsbNegative: number | null;
  tsb: number;
}

export default function FitnessChart({ data }: Props) {
  const chartData = useMemo<ChartDataPoint[]>(() => {
    return data.map((d) => {
      const tsb = Number(d.tsb);
      return {
        date: d.date,
        dateLabel: format(new Date(d.date), 'MMM d'),
        ctl: Number(d.ctl),
        atl: Number(d.atl),
        tsbPositive: tsb >= 0 ? tsb : null,
        tsbNegative: tsb < 0 ? tsb : null,
        tsb,
      };
    });
  }, [data]);

  if (chartData.length === 0) {
    return (
      <div className="chart-empty">
        No fitness data available for this date range.
      </div>
    );
  }

  // Compute domain for TSB axis
  const tsbValues = chartData.map((d) => d.tsb);
  const tsbMin = Math.min(...tsbValues);
  const tsbMax = Math.max(...tsbValues);
  const tsbPadding = Math.max(Math.abs(tsbMin), Math.abs(tsbMax), 20) * 0.1;
  const tsbDomain = [
    Math.floor(tsbMin - tsbPadding),
    Math.ceil(tsbMax + tsbPadding),
  ];

  // Compute domain for CTL/ATL axis
  const ctlValues = chartData.map((d) => d.ctl);
  const atlValues = chartData.map((d) => d.atl);
  const loadMax = Math.max(...ctlValues, ...atlValues, 10);
  const loadDomain = [0, Math.ceil(loadMax * 1.1)];

  return (
    <div className="fitness-chart">
      <ResponsiveContainer width="100%" height={400}>
        <ComposedChart data={chartData} margin={{ top: 10, right: 10, left: 0, bottom: 0 }}>
          <CartesianGrid strokeDasharray="3 3" stroke="var(--color-border)" />

          <XAxis
            dataKey="dateLabel"
            stroke="var(--color-text-secondary)"
            fontSize={11}
            interval="preserveStartEnd"
            tickCount={8}
          />

          {/* Left axis: CTL/ATL */}
          <YAxis
            yAxisId="load"
            orientation="left"
            domain={loadDomain}
            stroke="var(--color-text-secondary)"
            fontSize={11}
            width={45}
            tickFormatter={(v: number) => `${v}`}
          />

          {/* Right axis: TSB */}
          <YAxis
            yAxisId="tsb"
            orientation="right"
            domain={tsbDomain}
            stroke="var(--color-cadence)"
            fontSize={11}
            width={45}
            tickFormatter={(v: number) => `${v}`}
          />

          {/* TSB zero reference line */}
          <ReferenceLine
            yAxisId="tsb"
            y={0}
            stroke="var(--color-text-secondary)"
            strokeDasharray="4 2"
            strokeOpacity={0.5}
          />

          <Tooltip
            content={({ payload, label }) => {
              if (!payload || payload.length === 0) return null;
              const point = payload[0]?.payload as ChartDataPoint | undefined;
              if (!point) return null;
              return (
                <div className="chart-tooltip">
                  <div className="chart-tooltip-time">{label}</div>
                  <div style={{ color: 'var(--color-power)' }}>
                    CTL (Fitness): {point.ctl.toFixed(1)}
                  </div>
                  <div style={{ color: 'var(--color-hr)' }}>
                    ATL (Fatigue): {point.atl.toFixed(1)}
                  </div>
                  <div style={{ color: point.tsb >= 0 ? 'var(--color-cadence)' : 'var(--color-danger)' }}>
                    TSB (Form): {point.tsb.toFixed(1)}
                  </div>
                </div>
              );
            }}
          />

          <Legend
            verticalAlign="top"
            height={36}
            formatter={(value: string) => {
              const labels: Record<string, string> = {
                ctl: 'CTL (Fitness)',
                atl: 'ATL (Fatigue)',
                tsbPositive: 'TSB (Form +)',
                tsbNegative: 'TSB (Form -)',
              };
              return labels[value] ?? value;
            }}
          />

          {/* TSB positive area (green, above zero) */}
          <Area
            yAxisId="tsb"
            type="monotone"
            dataKey="tsbPositive"
            fill="var(--color-cadence)"
            fillOpacity={0.15}
            stroke="none"
            connectNulls={false}
            isAnimationActive={false}
          />

          {/* TSB negative area (red, below zero) */}
          <Area
            yAxisId="tsb"
            type="monotone"
            dataKey="tsbNegative"
            fill="var(--color-danger)"
            fillOpacity={0.15}
            stroke="none"
            connectNulls={false}
            isAnimationActive={false}
          />

          {/* CTL line (blue) */}
          <Line
            yAxisId="load"
            type="monotone"
            dataKey="ctl"
            stroke="var(--color-power)"
            strokeWidth={2}
            dot={false}
            isAnimationActive={false}
          />

          {/* ATL line (red) */}
          <Line
            yAxisId="load"
            type="monotone"
            dataKey="atl"
            stroke="var(--color-hr)"
            strokeWidth={2}
            dot={false}
            isAnimationActive={false}
          />

          <Brush
            dataKey="dateLabel"
            height={30}
            stroke="var(--color-border)"
          />
        </ComposedChart>
      </ResponsiveContainer>
    </div>
  );
}
