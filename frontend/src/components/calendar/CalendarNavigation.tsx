import { format } from 'date-fns';
import './MonthView.css';

interface Props {
  year: number;
  month: number;
  onTodayClick: () => void;
}

export default function CalendarNavigation({ year, month, onTodayClick }: Props) {
  const dateObj = new Date(year, month - 1, 1);
  const label = format(dateObj, 'MMMM yyyy');

  return (
    <div className="calendar-navigation">
      <h2 className="calendar-month-title">{label}</h2>
      <button className="btn btn-primary btn-sm" onClick={onTodayClick}>
        Today
      </button>
    </div>
  );
}
