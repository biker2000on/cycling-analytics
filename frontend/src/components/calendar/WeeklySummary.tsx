import type { CalendarDay } from '../../api/types.ts';
import { formatDuration } from '../../utils/format.ts';
import { useUnits } from '../../hooks/useUnits.ts';
import './MonthView.css';

interface Props {
  days: CalendarDay[];
  weekLabel: string;
}

export default function WeeklySummary({ days, weekLabel }: Props) {
  const { formatDistance, distanceUnit } = useUnits();
  const totalTss = days.reduce((sum, d) => sum + Number(d.total_tss), 0);
  const totalDuration = days.reduce((sum, d) => sum + d.total_duration_seconds, 0);
  const totalDistance = days.reduce((sum, d) => sum + Number(d.total_distance_meters), 0);
  const totalCount = days.reduce((sum, d) => sum + d.activity_count, 0);

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
      <span className="weekly-stat">{totalCount} ride{totalCount > 1 ? 's' : ''}</span>
      <span className="weekly-stat">{Math.round(totalTss)} TSS</span>
      <span className="weekly-stat">{formatDuration(totalDuration)}</span>
      <span className="weekly-stat">{formatDistance(totalDistance)} {distanceUnit}</span>
    </div>
  );
}
