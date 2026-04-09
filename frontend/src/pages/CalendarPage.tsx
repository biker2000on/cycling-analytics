import { useEffect, useRef, useCallback } from 'react';
import { useNavigate } from 'react-router-dom';
import { format } from 'date-fns';
import { useInfiniteCalendar } from '../hooks/useInfiniteCalendar.ts';
import CalendarNavigation from '../components/calendar/CalendarNavigation.tsx';
import MonthView from '../components/calendar/MonthView.tsx';
import MonthSkeleton from '../components/calendar/MonthSkeleton.tsx';
import './CalendarPage.css';

export default function CalendarPage() {
  const navigate = useNavigate();
  const { months, loadOlder, scrollToToday, activeMonth, setActiveMonth } = useInfiniteCalendar();

  const scrollContainerRef = useRef<HTMLDivElement>(null);
  const bottomSentinelRef = useRef<HTMLDivElement>(null);

  // Infinite scroll: when bottom sentinel is visible, load older months
  useEffect(() => {
    const sentinel = bottomSentinelRef.current;
    const container = scrollContainerRef.current;
    if (!sentinel || !container) return;

    const observer = new IntersectionObserver(
      (entries) => {
        if (entries[0].isIntersecting) {
          loadOlder();
        }
      },
      { threshold: 0.1, root: container, rootMargin: '200px' }
    );

    observer.observe(sentinel);
    return () => observer.disconnect();
  }, [loadOlder]);

  // Track which month header is in view for the navigation title
  useEffect(() => {
    const container = scrollContainerRef.current;
    if (!container) return;

    const headers = container.querySelectorAll('.calendar-month-sticky-header');
    if (headers.length === 0) return;

    const observer = new IntersectionObserver(
      (entries) => {
        for (const entry of entries) {
          if (entry.isIntersecting) {
            const header = entry.target as HTMLElement;
            const year = parseInt(header.dataset.year || '0', 10);
            const month = parseInt(header.dataset.month || '0', 10);
            if (year && month) {
              setActiveMonth(year, month);
            }
          }
        }
      },
      { threshold: [0.5], root: container }
    );

    headers.forEach((header) => observer.observe(header));
    return () => observer.disconnect();
  }, [months, setActiveMonth]);

  const handleDayClick = useCallback((dateStr: string) => {
    navigate(`/activities?date=${dateStr}`);
  }, [navigate]);

  return (
    <div className="calendar-page">
      <div className="page-header">
        <h1 className="page-title">Training Calendar</h1>
      </div>

      <div className="card calendar-card">
        <CalendarNavigation
          year={activeMonth?.year || new Date().getFullYear()}
          month={activeMonth?.month || new Date().getMonth() + 1}
          onTodayClick={scrollToToday}
        />

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

          {/* Bottom sentinel: triggers loading older months */}
          <div ref={bottomSentinelRef} className="calendar-sentinel" />
        </div>
      </div>
    </div>
  );
}
