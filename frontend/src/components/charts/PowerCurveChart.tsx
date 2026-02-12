import { useMemo } from 'react';
import {
  ResponsiveContainer,
  LineChart,
  Line,
  XAxis,
  YAxis,
  Tooltip,
  CartesianGrid,
  ReferenceLine,
} from 'recharts';
import type { PowerCurvePoint } from '../../api/types.ts';
import './PowerCurveChart.css';

interface Props {
  data: PowerCurvePoint[];
  onPointClick?: (point: PowerCurvePoint) => void;
}

interface ChartPoint {
  duration: number;
  power: number;
  activityId: number;
  activityDate: string;
  label: string;
}

const REFERENCE_DURATIONS = [
  { seconds: 5, label: '5s' },
  { seconds: 60, label: '1min' },
  { seconds: 300, label: '5min' },
  { seconds: 1200, label: '20min' },
  { seconds: 3600, label: '60min' },
];

function formatDurationAxis(seconds: number): string {
  if (seconds < 60) return `${seconds}s`;
  if (seconds < 3600) return `${Math.round(seconds / 60)}m`;
  return `${(seconds / 3600).toFixed(1)}h`;
}

// Generate log-scale ticks
const LOG_TICKS = [1, 2, 5, 10, 30, 60, 120, 300, 600, 1200, 1800, 3600];

export default function PowerCurveChart({ data, onPointClick }: Props) {
  const chartData = useMemo<ChartPoint[]>(() => {
    return data.map((d) => ({
      duration: d.duration_seconds,
      power: Number(d.power_watts),
      activityId: d.activity_id,
      activityDate: d.activity_date,
      label: formatDurationAxis(d.duration_seconds),
    }));
  }, [data]);

  if (chartData.length === 0) {
    return (
      <div className="chart-empty">
        No power curve data available. Ride with a power meter to see your curve.
      </div>
    );
  }

  const maxPower = Math.max(...chartData.map((d) => d.power));
  const powerCeil = Math.ceil(maxPower / 50) * 50 + 50;

  return (
    <div className="power-curve-chart">
      <ResponsiveContainer width="100%" height={400}>
        <LineChart
          data={chartData}
          margin={{ top: 10, right: 10, left: 0, bottom: 0 }}
          onClick={(e: Record<string, unknown>) => {
            const payload = e?.activePayload as Array<{ payload: ChartPoint }> | undefined;
            if (payload && payload[0] && onPointClick) {
              const point = payload[0].payload;
              const original = data.find((d) => d.duration_seconds === point.duration);
              if (original) onPointClick(original);
            }
          }}
        >
          <CartesianGrid strokeDasharray="3 3" stroke="var(--color-border)" />

          <XAxis
            dataKey="duration"
            scale="log"
            domain={[1, 3600]}
            ticks={LOG_TICKS}
            tickFormatter={formatDurationAxis}
            stroke="var(--color-text-secondary)"
            fontSize={11}
            type="number"
          />

          <YAxis
            domain={[0, powerCeil]}
            stroke="var(--color-text-secondary)"
            fontSize={11}
            tickFormatter={(v: number) => `${v}W`}
            width={55}
          />

          {/* Reference lines at key durations */}
          {REFERENCE_DURATIONS.map((ref) => (
            <ReferenceLine
              key={ref.seconds}
              x={ref.seconds}
              stroke="var(--color-border)"
              strokeDasharray="4 2"
              strokeOpacity={0.6}
              label={{
                value: ref.label,
                position: 'top',
                fill: 'var(--color-text-secondary)',
                fontSize: 10,
              }}
            />
          ))}

          <Tooltip
            content={({ payload }) => {
              if (!payload || payload.length === 0) return null;
              const point = payload[0].payload as ChartPoint;
              return (
                <div className="chart-tooltip">
                  <div className="chart-tooltip-time">
                    {formatDurationAxis(point.duration)}
                  </div>
                  <div style={{ color: 'var(--color-power)' }}>
                    Power: {point.power}W
                  </div>
                  <div style={{ fontSize: '0.75rem', color: 'var(--color-text-secondary)' }}>
                    {point.activityDate}
                  </div>
                </div>
              );
            }}
          />

          <Line
            type="monotone"
            dataKey="power"
            stroke="var(--color-power)"
            strokeWidth={2.5}
            dot={{ r: 3, fill: 'var(--color-power)' }}
            activeDot={{ r: 5, fill: 'var(--color-power)', stroke: 'var(--color-bg-card)', strokeWidth: 2 }}
            isAnimationActive={false}
          />
        </LineChart>
      </ResponsiveContainer>
    </div>
  );
}
