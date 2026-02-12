import {
  ResponsiveContainer,
  BarChart,
  Bar,
  XAxis,
  YAxis,
  Tooltip,
  CartesianGrid,
} from 'recharts';
import type { HRDistributionBin } from '../../api/types.ts';
import './HRDistribution.css';

interface Props {
  distribution: HRDistributionBin[];
}

export default function HRDistribution({ distribution }: Props) {
  if (distribution.length === 0) {
    return <div className="chart-empty">No HR distribution data available.</div>;
  }

  const chartData = distribution.map((bin) => ({
    label: `${bin.bin_start}`,
    count: bin.count,
    range: `${bin.bin_start}-${bin.bin_end} bpm`,
  }));

  return (
    <div className="hr-distribution">
      <h4 className="chart-subtitle">HR Distribution</h4>
      <ResponsiveContainer width="100%" height={280}>
        <BarChart data={chartData} margin={{ top: 5, right: 10, left: 0, bottom: 5 }}>
          <CartesianGrid strokeDasharray="3 3" stroke="var(--color-border)" vertical={false} />
          <XAxis
            dataKey="label"
            stroke="var(--color-text-secondary)"
            fontSize={10}
            interval="preserveStartEnd"
            tickFormatter={(v: string) => `${v}`}
          />
          <YAxis
            stroke="var(--color-text-secondary)"
            fontSize={10}
            tickFormatter={(v: number) => `${v}s`}
            width={45}
          />
          <Tooltip
            content={({ payload }) => {
              if (!payload || payload.length === 0) return null;
              const item = payload[0].payload as (typeof chartData)[number];
              return (
                <div className="chart-tooltip">
                  <div className="chart-tooltip-time">{item.range}</div>
                  <div>Time: {item.count}s</div>
                </div>
              );
            }}
          />
          <Bar
            dataKey="count"
            fill="var(--color-hr)"
            isAnimationActive={false}
            radius={[2, 2, 0, 0]}
          />
        </BarChart>
      </ResponsiveContainer>
    </div>
  );
}
