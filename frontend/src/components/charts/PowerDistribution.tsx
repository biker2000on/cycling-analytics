import {
  ResponsiveContainer,
  BarChart,
  Bar,
  XAxis,
  YAxis,
  Tooltip,
  Cell,
  CartesianGrid,
} from 'recharts';
import type { PowerDistributionBin } from '../../api/types.ts';
import { ZONE_COLORS } from '../../utils/powerZones.ts';
import './PowerDistribution.css';

interface Props {
  distribution: PowerDistributionBin[];
}

export default function PowerDistribution({ distribution }: Props) {
  if (distribution.length === 0) {
    return <div className="chart-empty">No power distribution data available.</div>;
  }

  const chartData = distribution.map((bin) => ({
    label: `${bin.bin_start}`,
    count: bin.count,
    zone: bin.zone,
    range: `${bin.bin_start}-${bin.bin_end}W`,
  }));

  return (
    <div className="power-distribution">
      <h4 className="chart-subtitle">Power Distribution</h4>
      <ResponsiveContainer width="100%" height={280}>
        <BarChart data={chartData} margin={{ top: 5, right: 10, left: 0, bottom: 5 }}>
          <CartesianGrid strokeDasharray="3 3" stroke="var(--color-border)" vertical={false} />
          <XAxis
            dataKey="label"
            stroke="var(--color-text-secondary)"
            fontSize={10}
            interval="preserveStartEnd"
            tickFormatter={(v: string) => `${v}W`}
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
          <Bar dataKey="count" isAnimationActive={false} radius={[2, 2, 0, 0]}>
            {chartData.map((entry, idx) => (
              <Cell key={idx} fill={ZONE_COLORS[entry.zone] ?? ZONE_COLORS[1]} />
            ))}
          </Bar>
        </BarChart>
      </ResponsiveContainer>
    </div>
  );
}
