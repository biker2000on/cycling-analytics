import type { CalendarDay } from '../../api/types.ts';
import { formatDuration } from '../../utils/format.ts';
import { useUnits } from '../../hooks/useUnits.ts';
import './MonthView.css';

interface Props {
  days: CalendarDay[];
  weekLabel: string;
}

export default function WeeklySummary({ days, weekLabel }: Props) {
  const { formatDistance, distanceUnit, formatElevation, elevationUnit } = useUnits();
  const totalTss = days.reduce((sum, d) => sum + Number(d.total_tss), 0);
  const totalDuration = days.reduce((sum, d) => sum + d.total_duration_seconds, 0);
  const totalDistance = days.reduce((sum, d) => sum + Number(d.total_distance_meters), 0);
  const totalCount = days.reduce((sum, d) => sum + d.activity_count, 0);
  const totalElevation = days.reduce((sum, d) => {
    const dayElev = d.activities?.reduce((s, a) => s + Number(a.elevation_gain_meters || 0), 0) || 0;
    return sum + dayElev;
  }, 0);

  if (totalCount === 0) {
    return (
      <div className="weekly-summary weekly-summary-empty">
        <span className="weekly-label">{weekLabel}</span>
        <span className="weekly-stat">--</span>
      </div>
    );
  }

  return (
    <div className="weekly-summary">
      <span className="weekly-label">{weekLabel}</span>
      <div className="weekly-stats-grid">
        <div className="weekly-stat-row">
          <span className="weekly-stat-value">{formatDistance(totalDistance)}</span>
          <span className="weekly-stat-unit">{distanceUnit}</span>
        </div>
        <div className="weekly-stat-row">
          <span className="weekly-stat-value">{formatDuration(totalDuration)}</span>
        </div>
        {totalElevation > 0 && (
          <div className="weekly-stat-row">
            <span className="weekly-stat-value">{formatElevation(totalElevation)}</span>
            <span className="weekly-stat-unit">{elevationUnit}</span>
          </div>
        )}
        {totalTss > 0 && (
          <div className="weekly-stat-row">
            <span className="weekly-stat-value weekly-stat-tss">{Math.round(totalTss)}</span>
            <span className="weekly-stat-unit">TSS</span>
          </div>
        )}
      </div>
    </div>
  );
}
