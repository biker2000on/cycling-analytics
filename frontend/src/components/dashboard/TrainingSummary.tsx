import { useEffect, useState } from 'react';
import type { PeriodSummary } from '../../api/types.ts';
import { getMetricsSummary } from '../../api/metrics.ts';
import { formatDuration } from '../../utils/format.ts';
import { useUnits } from '../../hooks/useUnits.ts';
import { format, startOfWeek, endOfWeek } from 'date-fns';
import './TrainingSummary.css';

export default function TrainingSummary() {
  const [summary, setSummary] = useState<PeriodSummary | null>(null);
  const [loading, setLoading] = useState(true);
  const { formatDistance, distanceUnit } = useUnits();

  useEffect(() => {
    let cancelled = false;
    async function load() {
      try {
        const now = new Date();
        const weekStart = startOfWeek(now, { weekStartsOn: 1 });
        const weekEnd = endOfWeek(now, { weekStartsOn: 1 });
        const data = await getMetricsSummary(
          format(weekStart, 'yyyy-MM-dd'),
          format(weekEnd, 'yyyy-MM-dd'),
        );
        if (!cancelled) setSummary(data);
      } catch {
        // Graceful degradation
      } finally {
        if (!cancelled) setLoading(false);
      }
    }
    load();
    return () => { cancelled = true; };
  }, []);

  return (
    <div className="training-summary card">
      <h3 className="widget-title">This Week</h3>
      {loading ? (
        <div className="loading-state">
          <span className="spinner" /> Loading...
        </div>
      ) : !summary ? (
        <div className="widget-empty">No summary data</div>
      ) : (
        <div className="summary-grid">
          <div className="summary-stat">
            <span className="summary-stat-value">{summary.ride_count}</span>
            <span className="summary-stat-label">Rides</span>
          </div>
          <div className="summary-stat">
            <span className="summary-stat-value">{Math.round(summary.total_tss)}</span>
            <span className="summary-stat-label">TSS</span>
          </div>
          <div className="summary-stat">
            <span className="summary-stat-value">
              {formatDuration(summary.total_duration_seconds)}
            </span>
            <span className="summary-stat-label">Time</span>
          </div>
          <div className="summary-stat">
            <span className="summary-stat-value">
              {formatDistance(summary.total_distance_meters)} {distanceUnit}
            </span>
            <span className="summary-stat-label">Distance</span>
          </div>
        </div>
      )}
    </div>
  );
}
