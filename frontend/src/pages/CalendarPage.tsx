import { useEffect, useRef, useCallback } from 'react';
import { useNavigate } from 'react-router-dom';
import { format } from 'date-fns';
import { useInfiniteCalendar } from '../hooks/useInfiniteCalendar.ts';
import MonthView from '../components/calendar/MonthView.tsx';
import MonthSkeleton from '../components/calendar/MonthSkeleton.tsx';
import './CalendarPage.css';

export default function CalendarPage() {
  const navigate = useNavigate();
  const { months, loadOlder, scrollToToday } = useInfiniteCalendar();

  const scrollContainerRef = useRef<HTMLDivElement>(null);

  // Infinite scroll: load older months when near the bottom
  useEffect(() => {
    const container = scrollContainerRef.current;
    if (!container) return;

    let rafId: number | null = null;

    function checkScroll() {
      const { scrollTop, scrollHeight, clientHeight } = container!;
      if (scrollHeight - scrollTop - clientHeight < 400) {
        loadOlder();
      }
    }

    function onScroll() {
      if (rafId) return;
      rafId = requestAnimationFrame(() => {
        checkScroll();
        rafId = null;
      });
    }

    container.addEventListener('scroll', onScroll, { passive: true });
    return () => {
      container.removeEventListener('scroll', onScroll);
      if (rafId) cancelAnimationFrame(rafId);
    };
  }, [loadOlder]);

  // On initial load only: keep filling viewport until content is scrollable.
  // Cap at 12 months to prevent runaway in tiny viewports.
  const initialFillDone = useRef(false);
  useEffect(() => {
    if (initialFillDone.current) return;
    const container = scrollContainerRef.current;
    if (!container) return;
    if (months.length > 12) {
      initialFillDone.current = true;
      return;
    }
    // Check if the last month is still loading - wait for it
    const last = months[months.length - 1];
    if (last?.loading) return;

    const timer = setTimeout(() => {
      const { scrollHeight, clientHeight } = container;
      if (scrollHeight <= clientHeight + 100) {
        loadOlder();
      } else {
        initialFillDone.current = true;
      }
    }, 150);

    return () => clearTimeout(timer);
  }, [months, loadOlder]);

  const handleDayClick = useCallback((dateStr: string) => {
    navigate(`/activities?date=${dateStr}`);
  }, [navigate]);

  return (
    <div className="calendar-page">
      <div className="page-header">
        <h1 className="page-title">Training Calendar</h1>
      </div>

      <div className="card calendar-card">
        <button className="calendar-today-fab" onClick={scrollToToday} title="Scroll to today">
          Today
        </button>
        <div className="calendar-scroll-container" ref={scrollContainerRef}>
          {/* Months rendered newest-first: scroll down = older */}
          {months.map((monthData) => {
            const monthKey = `${monthData.year}-${String(monthData.month).padStart(2, '0')}`;
            const monthId = `month-${monthKey}`;
            const dateObj = new Date(monthData.year, monthData.month - 1, 1);
            const monthLabel = format(dateObj, 'MMMM yyyy');

            return (
              <div key={monthKey} id={monthId} className="calendar-month-section">
                <div
                  className="calendar-month-sticky-header"
                  data-year={monthData.year}
                  data-month={monthData.month}
                >
                  {monthLabel}
                </div>

                {monthData.error && (
                  <div className="alert alert-error">{monthData.error}</div>
                )}

                {monthData.loading ? (
                  <MonthSkeleton />
                ) : monthData.data ? (
                  <MonthView calendarData={monthData.data} onDayClick={handleDayClick} />
                ) : null}
              </div>
            );
          })}

        </div>
      </div>
    </div>
  );
}
