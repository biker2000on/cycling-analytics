import type { TotalsPeriod } from '../../api/types.ts';
import { formatDuration, formatDistance } from '../../utils/format.ts';
import './TotalsSummaryCards.css';

interface Props {
  periods: TotalsPeriod[];
}

export default function TotalsSummaryCards({ periods }: Props) {
  const totalRides = periods.reduce((sum, p) => sum + p.ride_count, 0);
  const totalTss = periods.reduce((sum, p) => sum + Number(p.total_tss), 0);
  const totalDuration = periods.reduce((sum, p) => sum + p.total_duration_seconds, 0);
  const totalDistance = periods.reduce((sum, p) => sum + Number(p.total_distance_meters), 0);

  return (
    <div className="totals-summary-cards">
      <div className="totals-card">
        <span className="totals-card-value">{totalRides}</span>
        <span className="totals-card-label">Total Rides</span>
      </div>
      <div className="totals-card">
        <span className="totals-card-value">{Math.round(totalTss)}</span>
        <span className="totals-card-label">Total TSS</span>
      </div>
      <div className="totals-card">
        <span className="totals-card-value">{formatDuration(totalDuration)}</span>
        <span className="totals-card-label">Total Time</span>
      </div>
      <div className="totals-card">
        <span className="totals-card-value">{formatDistance(totalDistance)} km</span>
        <span className="totals-card-label">Total Distance</span>
      </div>
    </div>
  );
}
