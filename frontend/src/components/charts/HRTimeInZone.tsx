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
import type { HRZoneTime } from '../../api/types.ts';
import { HR_ZONE_COLORS } from '../../utils/hrZones.ts';
import { formatDuration } from '../../utils/format.ts';
import './HRTimeInZone.css';

interface Props {
  zones: HRZoneTime[];
}

export default function HRTimeInZone({ zones }: Props) {
  if (zones.length === 0 || zones.every((z) => z.seconds === 0)) {
    return <div className="chart-empty">No HR zone data available.</div>;
  }

  const chartData = zones.map((z) => ({
    name: `Z${z.zone} ${z.name}`,
    seconds: z.seconds,
    zone: z.zone,
    label: formatDuration(z.seconds),
    hrRange: `${z.min_hr}-${z.max_hr} bpm`,
  }));

  return (
    <div className="hr-time-in-zone">
      <h4 className="chart-subtitle">Time in HR Zones</h4>
      <ResponsiveContainer width="100%" height={220}>
        <BarChart
          data={chartData}
          layout="vertical"
          margin={{ top: 5, right: 10, left: 10, bottom: 5 }}
        >
          <CartesianGrid strokeDasharray="3 3" stroke="var(--color-border)" horizontal={false} />
          <XAxis
            type="number"
            stroke="var(--color-text-secondary)"
            fontSize={10}
            tickFormatter={(v: number) => formatDuration(v)}
          />
          <YAxis
            type="category"
            dataKey="name"
            stroke="var(--color-text-secondary)"
            fontSize={11}
            width={120}
          />
          <Tooltip
            content={({ payload }) => {
              if (!payload || payload.length === 0) return null;
              const item = payload[0].payload as (typeof chartData)[number];
              return (
                <div className="chart-tooltip">
                  <div className="chart-tooltip-time">{item.name}</div>
                  <div>Time: {item.label}</div>
                  <div>HR: {item.hrRange}</div>
                </div>
              );
            }}
          />
          <Bar dataKey="seconds" isAnimationActive={false} radius={[0, 4, 4, 0]}>
            {chartData.map((entry, idx) => (
              <Cell key={idx} fill={HR_ZONE_COLORS[entry.zone] ?? HR_ZONE_COLORS[1]} />
            ))}
          </Bar>
        </BarChart>
      </ResponsiveContainer>
    </div>
  );
}
