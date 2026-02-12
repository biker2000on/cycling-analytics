import type { CalendarDay } from '../../api/types.ts';
import './MonthView.css';

interface Props {
  day: number;
  data?: CalendarDay;
  isToday: boolean;
  onClick?: () => void;
}

function getTssIntensity(tss: number): string {
  if (tss === 0) return '';
  if (tss < 50) return 'tss-light';
  if (tss < 100) return 'tss-moderate';
  if (tss < 150) return 'tss-hard';
  return 'tss-very-hard';
}

export default function DayCell({ day, data, isToday, onClick }: Props) {
  const tss = data ? Number(data.total_tss) : 0;
  const hasActivity = data && data.activity_count > 0;

  return (
    <div
      className={`day-cell${isToday ? ' day-cell-today' : ''}${hasActivity ? ' day-cell-has-activity' : ''} ${getTssIntensity(tss)}`}
      onClick={onClick}
    >
      <span className="day-number">{day}</span>
      {hasActivity && (
        <div className="day-details">
          <span className="day-activity-count">
            {data.activity_count} ride{data.activity_count > 1 ? 's' : ''}
          </span>
          {tss > 0 && <span className="day-tss">{Math.round(tss)} TSS</span>}
        </div>
      )}
    </div>
  );
}
