import { useEffect, useState, useCallback } from 'react';
import { useNavigate } from 'react-router-dom';
import type { CalendarMonth } from '../api/types.ts';
import { getCalendarData } from '../api/metrics.ts';
import CalendarNavigation from '../components/calendar/CalendarNavigation.tsx';
import MonthView from '../components/calendar/MonthView.tsx';
import './CalendarPage.css';

export default function CalendarPage() {
  const now = new Date();
  const [year, setYear] = useState(now.getFullYear());
  const [month, setMonth] = useState(now.getMonth() + 1);
  const [data, setData] = useState<CalendarMonth | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const navigate = useNavigate();

  const fetchData = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const result = await getCalendarData(year, month);
      setData(result);
    } catch (err: unknown) {
      const message =
        (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail ||
        'Failed to load calendar data';
      setError(message);
    } finally {
      setLoading(false);
    }
  }, [year, month]);

  useEffect(() => {
    fetchData();
  }, [fetchData]);

  function handlePrev() {
    if (month === 1) {
      setYear((y) => y - 1);
      setMonth(12);
    } else {
      setMonth((m) => m - 1);
    }
  }

  function handleNext() {
    if (month === 12) {
      setYear((y) => y + 1);
      setMonth(1);
    } else {
      setMonth((m) => m + 1);
    }
  }

  function handleDayClick(dateStr: string) {
    // Navigate to activities filtered by date (or expand inline)
    navigate(`/activities?date=${dateStr}`);
  }

  return (
    <div className="calendar-page">
      <div className="page-header">
        <h1 className="page-title">Training Calendar</h1>
      </div>

      <div className="card calendar-card">
        <CalendarNavigation
          year={year}
          month={month}
          onPrev={handlePrev}
          onNext={handleNext}
        />

        {error && <div className="alert alert-error">{error}</div>}

        {loading ? (
          <div className="loading-state">
            <span className="spinner" /> Loading calendar...
          </div>
        ) : data ? (
          <MonthView calendarData={data} onDayClick={handleDayClick} />
        ) : null}
      </div>
    </div>
  );
}
