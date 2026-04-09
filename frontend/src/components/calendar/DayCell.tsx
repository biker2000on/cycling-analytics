import { useNavigate } from 'react-router-dom';
import type { CalendarDay, CalendarActivity } from '../../api/types.ts';
import { formatDuration } from '../../utils/format.ts';
import { useUnits } from '../../hooks/useUnits.ts';
import './MonthView.css';

interface Props {
  day: number;
  data?: CalendarDay;
  isToday: boolean;
  onClick?: () => void;
}

const SPORT_COLORS: Record<string, string> = {
  cycling: '#4a90d9',
  running: '#e67e22',
  swimming: '#1abc9c',
  walking: '#95a5a6',
  hiking: '#27ae60',
  strength_training: '#8e44ad',
  yoga: '#f39c12',
  default: '#4a90d9',
};

const SPORT_ICONS: Record<string, string> = {
  cycling: '\u{1F6B4}',
  running: '\u{1F3C3}',
  swimming: '\u{1F3CA}',
  walking: '\u{1F6B6}',
  hiking: '\u26F0\uFE0F',
  strength_training: '\u{1F4AA}',
  yoga: '\u{1F9D8}',
  default: '\u{1F3CB}\uFE0F',
};

function getSportKey(sportType: string | null): string {
  if (!sportType) return 'default';
  const lower = sportType.toLowerCase();
  if (lower.includes('ride') || lower.includes('cycling') || lower.includes('bike')) return 'cycling';
  if (lower.includes('run')) return 'running';
  if (lower.includes('swim')) return 'swimming';
  if (lower.includes('walk')) return 'walking';
  if (lower.includes('hik')) return 'hiking';
  if (lower.includes('strength') || lower.includes('weight')) return 'strength_training';
  if (lower.includes('yoga')) return 'yoga';
  return 'default';
}

function ActivityCard({ activity }: { activity: CalendarActivity }) {
  const navigate = useNavigate();
  const { formatDistance, distanceUnit } = useUnits();
  const sportKey = getSportKey(activity.sport_type);
  const color = SPORT_COLORS[sportKey];
  const icon = SPORT_ICONS[sportKey];

  return (
    <div
      className="cal-activity-card"
      style={{ borderLeftColor: color }}
      onClick={(e) => {
        e.stopPropagation();
        navigate(`/activities/${activity.id}`);
      }}
    >
      <div className="cal-activity-header">
        <span className="cal-activity-icon">{icon}</span>
        <span className="cal-activity-name" title={activity.name}>
          {activity.name}
        </span>
      </div>
      <div className="cal-activity-stats">
        {activity.duration_seconds != null && activity.duration_seconds > 0 && (
          <span className="cal-stat">{formatDuration(activity.duration_seconds)}</span>
        )}
        {activity.distance_meters != null && Number(activity.distance_meters) > 0 && (
          <span className="cal-stat">{formatDistance(Number(activity.distance_meters))}{distanceUnit}</span>
        )}
        {activity.tss != null && Number(activity.tss) > 0 && (
          <span className="cal-stat cal-stat-tss">{Math.round(Number(activity.tss))}</span>
        )}
        {activity.avg_power_watts != null && Number(activity.avg_power_watts) > 0 && (
          <span className="cal-stat">{Math.round(Number(activity.avg_power_watts))}w</span>
        )}
      </div>
    </div>
  );
}

export default function DayCell({ day, data, isToday, onClick }: Props) {
  const hasActivity = data && data.activity_count > 0;

  return (
    <div
      className={`day-cell${isToday ? ' day-cell-today' : ''}${hasActivity ? ' day-cell-has-activity' : ''}`}
      onClick={onClick}
    >
      <span className="day-number">{day}</span>
      {hasActivity && data.activities && (
        <div className="day-activities">
          {data.activities.map((act) => (
            <ActivityCard key={act.id} activity={act} />
          ))}
        </div>
      )}
    </div>
  );
}
