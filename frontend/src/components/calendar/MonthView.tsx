import { useMemo } from 'react';
import type { CalendarDay, CalendarMonth } from '../../api/types.ts';
import DayCell from './DayCell.tsx';
import WeeklySummary from './WeeklySummary.tsx';
import { getDay, getDaysInMonth, getISOWeek } from 'date-fns';
import './MonthView.css';

interface Props {
  calendarData: CalendarMonth;
  onDayClick?: (date: string) => void;
}

const DAY_HEADERS = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun'];

export default function MonthView({ calendarData, onDayClick }: Props) {
  const { year, month, days } = calendarData;

  // Build lookup from day-of-month to calendar data
  const dayMap = useMemo(() => {
    const map: Record<number, CalendarDay> = {};
    for (const d of days) {
      const dayNum = new Date(d.date).getDate();
      map[dayNum] = d;
    }
    return map;
  }, [days]);

  const daysInMonth = getDaysInMonth(new Date(year, month - 1));
  const firstDayOfWeek = getDay(new Date(year, month - 1, 1));
  // Convert Sunday=0 to Monday-first (Mon=0, ..., Sun=6)
  const startOffset = firstDayOfWeek === 0 ? 6 : firstDayOfWeek - 1;

  // Build weeks array
  const weeks: { days: number[]; weekLabel: string }[] = [];
  let currentWeek: number[] = [];

  // Fill leading empty cells
  for (let i = 0; i < startOffset; i++) {
    currentWeek.push(0);
  }

  for (let day = 1; day <= daysInMonth; day++) {
    currentWeek.push(day);
    if (currentWeek.length === 7) {
      const weekNum = getISOWeek(new Date(year, month - 1, day));
      weeks.push({ days: [...currentWeek], weekLabel: `W${weekNum}` });
      currentWeek = [];
    }
  }

  // Fill trailing empty cells
  if (currentWeek.length > 0) {
    const lastDay = currentWeek[currentWeek.length - 1];
    const weekNum = getISOWeek(new Date(year, month - 1, lastDay));
    while (currentWeek.length < 7) {
      currentWeek.push(0);
    }
    weeks.push({ days: [...currentWeek], weekLabel: `W${weekNum}` });
  }

  const today = new Date();

  return (
    <div className="month-view">
      {/* Day headers */}
      <div className="month-header-row">
        {DAY_HEADERS.map((h) => (
          <div key={h} className="month-header-cell">{h}</div>
        ))}
        <div className="month-header-cell month-header-summary">Week</div>
      </div>

      {/* Week rows */}
      {weeks.map((week, wi) => {
        const weekDayData = week.days
          .filter((d) => d > 0)
          .map((d) => dayMap[d])
          .filter(Boolean) as CalendarDay[];

        return (
          <div key={wi} className="month-week-row">
            <div className="month-day-cells">
              {week.days.map((day, di) => {
                if (day === 0) {
                  return <div key={di} className="day-cell day-cell-empty" />;
                }
                const isTodayFlag =
                  today.getFullYear() === year &&
                  today.getMonth() === month - 1 &&
                  today.getDate() === day;
                const dateStr = `${year}-${String(month).padStart(2, '0')}-${String(day).padStart(2, '0')}`;

                return (
                  <DayCell
                    key={di}
                    day={day}
                    data={dayMap[day]}
                    isToday={isTodayFlag}
                    onClick={() => onDayClick?.(dateStr)}
                  />
                );
              })}
            </div>
            <WeeklySummary days={weekDayData} weekLabel={week.weekLabel} />
          </div>
        );
      })}
    </div>
  );
}
