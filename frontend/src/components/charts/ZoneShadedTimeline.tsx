import { useMemo, useState, useEffect, useCallback } from 'react';
import {
  ResponsiveContainer,
  LineChart,
  Line,
  XAxis,
  YAxis,
  Tooltip,
  ReferenceLine,
  ReferenceArea,
  Brush,
  CartesianGrid,
} from 'recharts';
import type { StreamSummaryResponse, ZoneBlock } from '../../api/types.ts';
import { getStreamZoneBlocks } from '../../api/streams.ts';
import { ZONE_COLORS } from '../../utils/powerZones.ts';
import { formatDuration } from '../../utils/format.ts';
import ZoneLegend from './ZoneLegend.tsx';
import './ZoneShadedTimeline.css';

interface Props {
  stream: StreamSummaryResponse;
  ftp?: number | null;
  activityId: number;
}

interface DataPoint {
  elapsed: number;
  power: number | null;
  hr: number | null;
}

export default function ZoneShadedTimeline({ stream, ftp, activityId }: Props) {
  const [zoneBlocks, setZoneBlocks] = useState<ZoneBlock[]>([]);

  const loadZones = useCallback(async () => {
    if (!ftp || ftp <= 0) return;
    try {
      const result = await getStreamZoneBlocks(activityId, ftp);
      setZoneBlocks(result.blocks);
    } catch {
      // Zone shading is optional -- degrade gracefully
    }
  }, [activityId, ftp]);

  useEffect(() => {
    loadZones();
  }, [loadZones]);

  const data = useMemo<DataPoint[]>(() => {
    const firstTs = new Date(stream.timestamps[0]).getTime();
    return stream.timestamps.map((ts, i) => ({
      elapsed: Math.round((new Date(ts).getTime() - firstTs) / 1000),
      power: stream.power[i],
      hr: stream.heart_rate[i],
    }));
  }, [stream]);

  const hasPower = stream.power.some((v) => v != null);
  const hasHR = stream.heart_rate.some((v) => v != null);

  if (!hasPower && !hasHR) {
    return <div className="chart-empty">No stream data available for this activity.</div>;
  }

  const maxPower = stream.stats.power_max ?? 500;
  const maxHR = stream.stats.hr_max ?? 200;
  const powerCeil = Math.ceil(maxPower / 50) * 50 + 50;
  const hrCeil = Math.ceil(maxHR / 10) * 10 + 10;
  const maxElapsed = data.length > 0 ? data[data.length - 1].elapsed : 0;

  return (
    <div className="zone-shaded-timeline card">
      <h3 className="chart-title">Power &amp; Heart Rate</h3>
      {ftp && ftp > 0 && <ZoneLegend ftp={ftp} />}
      <ResponsiveContainer width="100%" height={380}>
        <LineChart data={data} margin={{ top: 10, right: 10, left: 0, bottom: 0 }}>
          <CartesianGrid strokeDasharray="3 3" stroke="var(--color-border)" />

          {/* Zone shading as background reference areas */}
          {hasPower &&
            zoneBlocks.map((block, idx) => (
              <ReferenceArea
                key={idx}
                yAxisId="power"
                x1={block.start_seconds}
                x2={Math.min(block.end_seconds, maxElapsed)}
                fill={ZONE_COLORS[block.zone] ?? ZONE_COLORS[1]}
                fillOpacity={0.15}
                ifOverflow="hidden"
              />
            ))}

          <XAxis
            dataKey="elapsed"
            tickFormatter={(v: number) => formatDuration(v)}
            stroke="var(--color-text-secondary)"
            fontSize={11}
            interval="preserveStartEnd"
          />
          {hasPower && (
            <YAxis
              yAxisId="power"
              orientation="left"
              domain={[0, powerCeil]}
              stroke="var(--color-power)"
              fontSize={11}
              tickFormatter={(v: number) => `${v}W`}
              width={55}
            />
          )}
          {hasHR && (
            <YAxis
              yAxisId="hr"
              orientation="right"
              domain={[60, hrCeil]}
              stroke="var(--color-hr)"
              fontSize={11}
              tickFormatter={(v: number) => `${v}`}
              width={40}
            />
          )}
          <Tooltip
            content={({ payload, label }) => {
              if (!payload || payload.length === 0) return null;
              const elapsed = label as number;
              return (
                <div className="chart-tooltip">
                  <div className="chart-tooltip-time">{formatDuration(elapsed)}</div>
                  {payload.map((entry) => (
                    <div key={entry.dataKey as string} style={{ color: entry.color as string }}>
                      {entry.dataKey === 'power'
                        ? `Power: ${entry.value ?? '--'}W`
                        : `HR: ${entry.value ?? '--'} bpm`}
                    </div>
                  ))}
                </div>
              );
            }}
          />
          {hasPower && (
            <Line
              yAxisId="power"
              type="monotone"
              dataKey="power"
              stroke="var(--color-power)"
              strokeWidth={1.5}
              dot={false}
              connectNulls={false}
              isAnimationActive={false}
            />
          )}
          {hasHR && (
            <Line
              yAxisId="hr"
              type="monotone"
              dataKey="hr"
              stroke="var(--color-hr)"
              strokeWidth={1.5}
              dot={false}
              connectNulls={false}
              isAnimationActive={false}
            />
          )}
          {ftp && hasPower && (
            <ReferenceLine
              yAxisId="power"
              y={ftp}
              stroke="var(--color-ftp-line)"
              strokeDasharray="6 3"
              strokeWidth={1.5}
              label={{
                value: `FTP ${ftp}W`,
                position: 'insideTopRight',
                fill: 'var(--color-ftp-line)',
                fontSize: 11,
              }}
            />
          )}
          <Brush
            dataKey="elapsed"
            height={30}
            stroke="var(--color-border)"
            tickFormatter={(v: number) => formatDuration(v)}
          />
        </LineChart>
      </ResponsiveContainer>
    </div>
  );
}
