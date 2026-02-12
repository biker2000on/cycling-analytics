import { useState, useEffect, useCallback, useMemo } from 'react';
import {
  ResponsiveContainer,
  AreaChart,
  Area,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
} from 'recharts';
import type { RouteGeoJSON, StreamSummaryResponse } from '../api/types.ts';
import { getActivityRoute } from '../api/routes.ts';
import RouteMap from '../components/maps/RouteMap.tsx';
import { formatDuration, formatElevation } from '../utils/format.ts';
import './ActivityMapPage.css';

interface Props {
  activityId: number;
  stream: StreamSummaryResponse | null;
}

interface ElevationPoint {
  elapsed: number;
  altitude: number | null;
}

export default function ActivityMapPage({ activityId, stream }: Props) {
  const [route, setRoute] = useState<RouteGeoJSON | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');

  const load = useCallback(async () => {
    setLoading(true);
    setError('');
    try {
      const result = await getActivityRoute(activityId);
      setRoute(result);
    } catch {
      setError('No GPS data available for this activity');
    } finally {
      setLoading(false);
    }
  }, [activityId]);

  useEffect(() => {
    load();
  }, [load]);

  const elevationData = useMemo<ElevationPoint[]>(() => {
    if (!stream) return [];
    const firstTs = new Date(stream.timestamps[0]).getTime();
    return stream.timestamps.map((ts, i) => ({
      elapsed: Math.round((new Date(ts).getTime() - firstTs) / 1000),
      altitude: stream.altitude_meters[i] != null ? Number(stream.altitude_meters[i]) : null,
    }));
  }, [stream]);

  const hasElevation = elevationData.some((p) => p.altitude != null);

  if (loading) {
    return (
      <div className="loading-state">
        <span className="spinner" /> Loading map...
      </div>
    );
  }

  if (error || !route) {
    return (
      <div className="card" style={{ padding: 'var(--space-xl)', textAlign: 'center' }}>
        <p style={{ color: 'var(--color-text-secondary)' }}>
          {error || 'No GPS data available for this activity.'}
        </p>
      </div>
    );
  }

  return (
    <div className="activity-map-page">
      <div className="card map-card">
        <RouteMap route={route} />
      </div>

      {hasElevation && (
        <div className="card elevation-card">
          <h4 className="chart-subtitle">Elevation Profile</h4>
          <ResponsiveContainer width="100%" height={160}>
            <AreaChart data={elevationData} margin={{ top: 5, right: 10, left: 0, bottom: 0 }}>
              <CartesianGrid strokeDasharray="3 3" stroke="var(--color-border)" />
              <XAxis
                dataKey="elapsed"
                tickFormatter={(v: number) => formatDuration(v)}
                stroke="var(--color-text-secondary)"
                fontSize={10}
                interval="preserveStartEnd"
              />
              <YAxis
                stroke="var(--color-text-secondary)"
                fontSize={10}
                tickFormatter={(v: number) => `${formatElevation(v)}m`}
                width={50}
              />
              <Tooltip
                content={({ payload, label }) => {
                  if (!payload || payload.length === 0) return null;
                  const elapsed = label as number;
                  const alt = payload[0].value as number | null;
                  return (
                    <div className="chart-tooltip">
                      <div className="chart-tooltip-time">{formatDuration(elapsed)}</div>
                      <div>Elevation: {alt != null ? `${formatElevation(alt)}m` : '--'}</div>
                    </div>
                  );
                }}
              />
              <Area
                type="monotone"
                dataKey="altitude"
                stroke="var(--color-cadence)"
                fill="var(--color-cadence)"
                fillOpacity={0.2}
                strokeWidth={1.5}
                dot={false}
                connectNulls={false}
                isAnimationActive={false}
              />
            </AreaChart>
          </ResponsiveContainer>
        </div>
      )}
    </div>
  );
}
