import { format } from 'date-fns';
import './MonthView.css';

interface Props {
  year: number;
  month: number;
  onPrev: () => void;
  onNext: () => void;
}

export default function CalendarNavigation({ year, month, onPrev, onNext }: Props) {
  const dateObj = new Date(year, month - 1, 1);
  const label = format(dateObj, 'MMMM yyyy');

  return (
    <div className="calendar-navigation">
      <button className="btn btn-secondary btn-sm" onClick={onPrev}>
        &larr; Prev
      </button>
      <h2 className="calendar-month-title">{label}</h2>
      <button className="btn btn-secondary btn-sm" onClick={onNext}>
        Next &rarr;
      </button>
    </div>
  );
}
