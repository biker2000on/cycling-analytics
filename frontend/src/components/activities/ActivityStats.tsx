import type { Activity } from '../../api/types.ts';
import {
  formatDuration,
  formatDecimal1,
  formatDecimal2,
  formatWatts,
  formatHR,
} from '../../utils/format.ts';
import { useUnits } from '../../hooks/useUnits.ts';
import './ActivityStats.css';

interface Props {
  activity: Activity;
  ftp?: number | null;
}

interface StatCard {
  label: string;
  value: string;
  unit?: string;
}

export default function ActivityStats({ activity, ftp }: Props) {
  const { formatDistance, formatElevation, distanceUnit, elevationUnit } = useUnits();

  const stats: StatCard[] = [
    { label: 'Duration', value: formatDuration(activity.duration_seconds) },
    { label: 'Distance', value: formatDistance(activity.distance_meters), unit: distanceUnit },
    { label: 'Elevation', value: formatElevation(activity.elevation_gain_meters), unit: elevationUnit },
    { label: 'TSS', value: formatDecimal1(activity.tss) },
    { label: 'NP', value: formatWatts(activity.np_watts), unit: 'W' },
    { label: 'IF', value: formatDecimal2(activity.intensity_factor) },
    { label: 'Avg Power', value: formatWatts(activity.avg_power_watts), unit: 'W' },
    { label: 'Max Power', value: formatWatts(activity.max_power_watts), unit: 'W' },
    { label: 'Avg HR', value: formatHR(activity.avg_hr), unit: 'bpm' },
    { label: 'Max HR', value: formatHR(activity.max_hr), unit: 'bpm' },
  ];

  if (ftp) {
    stats.push({ label: 'FTP', value: formatWatts(ftp), unit: 'W' });
  }

  return (
    <div className="stats-grid">
      {stats.map((s) => (
        <div key={s.label} className="stat-card card">
          <div className="stat-label">{s.label}</div>
          <div className="stat-value">
            {s.value}
            {s.unit && s.value !== '--' && <span className="stat-unit">{s.unit}</span>}
          </div>
        </div>
      ))}
    </div>
  );
}
