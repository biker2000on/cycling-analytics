import { useState } from 'react';
import {
  ResponsiveContainer,
  BarChart,
  Bar,
  XAxis,
  YAxis,
  Tooltip,
  CartesianGrid,
} from 'recharts';
import type { TotalsPeriod } from '../../api/types.ts';
import './TotalsBarChart.css';

interface Props {
  periods: TotalsPeriod[];
}

type MetricKey = 'tss' | 'duration' | 'distance';

interface ChartData {
  label: string;
  tss: number;
  duration: number;
  distance: number;
  rides: number;
}

const METRICS: { key: MetricKey; label: string; color: string }[] = [
  { key: 'tss', label: 'TSS', color: 'var(--color-primary)' },
  { key: 'duration', label: 'Duration (h)', color: 'var(--color-cadence)' },
  { key: 'distance', label: 'Distance (km)', color: 'var(--color-warning)' },
];

export default function TotalsBarChart({ periods }: Props) {
  const [metric, setMetric] = useState<MetricKey>('tss');

  const chartData: ChartData[] = periods.map((p) => ({
    label: p.period_label,
    tss: Number(p.total_tss),
    duration: p.total_duration_seconds / 3600,
    distance: Number(p.total_distance_meters) / 1000,
    rides: p.ride_count,
  }));

  if (chartData.length === 0) {
    return <div className="chart-empty">No totals data available.</div>;
  }

  const currentMetric = METRICS.find((m) => m.key === metric)!;

  function formatYAxis(value: number): string {
    switch (metric) {
      case 'tss':
        return `${Math.round(value)}`;
      case 'duration':
        return `${value.toFixed(1)}h`;
      case 'distance':
        return `${Math.round(value)}km`;
    }
  }

  return (
    <div className="totals-bar-chart">
      <div className="totals-metric-toggle">
        {METRICS.map((m) => (
          <button
            key={m.key}
            className={`totals-metric-btn${metric === m.key ? ' totals-metric-btn-active' : ''}`}
            onClick={() => setMetric(m.key)}
          >
            {m.label}
          </button>
        ))}
      </div>

      <ResponsiveContainer width="100%" height={350}>
        <BarChart data={chartData} margin={{ top: 10, right: 10, left: 0, bottom: 5 }}>
          <CartesianGrid strokeDasharray="3 3" stroke="var(--color-border)" vertical={false} />
          <XAxis
            dataKey="label"
            stroke="var(--color-text-secondary)"
            fontSize={10}
            interval="preserveStartEnd"
            angle={-30}
            textAnchor="end"
            height={50}
          />
          <YAxis
            stroke="var(--color-text-secondary)"
            fontSize={10}
            tickFormatter={formatYAxis}
            width={50}
          />
          <Tooltip
            content={({ payload, label }) => {
              if (!payload || payload.length === 0) return null;
              const item = payload[0].payload as ChartData;
              return (
                <div className="chart-tooltip">
                  <div className="chart-tooltip-time">{label}</div>
                  <div>{item.rides} ride{item.rides !== 1 ? 's' : ''}</div>
                  <div>TSS: {Math.round(item.tss)}</div>
                  <div>Duration: {item.duration.toFixed(1)}h</div>
                  <div>Distance: {item.distance.toFixed(1)} km</div>
                </div>
              );
            }}
          />
          <Bar
            dataKey={metric}
            fill={currentMetric.color}
            isAnimationActive={false}
            radius={[3, 3, 0, 0]}
          />
        </BarChart>
      </ResponsiveContainer>
    </div>
  );
}
