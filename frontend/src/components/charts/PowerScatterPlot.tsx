import {
  ResponsiveContainer,
  ScatterChart,
  Scatter,
  XAxis,
  YAxis,
  Tooltip,
  CartesianGrid,
} from 'recharts';
import type { StreamResponse } from '../../api/types.ts';
import './PowerScatterPlot.css';

interface Props {
  stream: StreamResponse;
}

interface ScatterPoint {
  power: number;
  hr: number;
}

export default function PowerScatterPlot({ stream }: Props) {
  const points: ScatterPoint[] = [];

  for (let i = 0; i < stream.power.length; i++) {
    const p = stream.power[i];
    const h = stream.heart_rate[i];
    if (p != null && h != null && p > 0 && h > 0) {
      points.push({ power: p, hr: h });
    }
  }

  // Downsample if too many points for scatter rendering
  const maxPoints = 500;
  const sampled =
    points.length <= maxPoints
      ? points
      : points.filter((_, i) => i % Math.ceil(points.length / maxPoints) === 0);

  if (sampled.length === 0) {
    return <div className="chart-empty">No power/HR data available for scatter plot.</div>;
  }

  return (
    <div className="power-scatter-plot">
      <h4 className="chart-subtitle">Power vs Heart Rate</h4>
      <ResponsiveContainer width="100%" height={280}>
        <ScatterChart margin={{ top: 5, right: 10, left: 0, bottom: 5 }}>
          <CartesianGrid strokeDasharray="3 3" stroke="var(--color-border)" />
          <XAxis
            type="number"
            dataKey="power"
            name="Power"
            stroke="var(--color-text-secondary)"
            fontSize={10}
            tickFormatter={(v: number) => `${v}W`}
          />
          <YAxis
            type="number"
            dataKey="hr"
            name="HR"
            stroke="var(--color-text-secondary)"
            fontSize={10}
            tickFormatter={(v: number) => `${v}`}
            width={40}
          />
          <Tooltip
            content={({ payload }) => {
              if (!payload || payload.length === 0) return null;
              const point = payload[0].payload as ScatterPoint;
              return (
                <div className="chart-tooltip">
                  <div>Power: {point.power}W</div>
                  <div>HR: {point.hr} bpm</div>
                </div>
              );
            }}
          />
          <Scatter data={sampled} fill="var(--color-power)" fillOpacity={0.4} isAnimationActive={false} />
        </ScatterChart>
      </ResponsiveContainer>
    </div>
  );
}
