import { useEffect, useLayoutEffect, useRef, useCallback } from 'react';
import { useNavigate } from 'react-router-dom';
import { format } from 'date-fns';
import { useInfiniteCalendar } from '../hooks/useInfiniteCalendar.ts';
import CalendarNavigation from '../components/calendar/CalendarNavigation.tsx';
import MonthView from '../components/calendar/MonthView.tsx';
import './CalendarPage.css';

export default function CalendarPage() {
  const navigate = useNavigate();
  const { months, loadOlder, loadNewer, scrollToToday, activeMonth, setActiveMonth } = useInfiniteCalendar();

  const scrollContainerRef = useRef<HTMLDivElement>(null);
  const topSentinelRef = useRef<HTMLDivElement>(null);
  const bottomSentinelRef = useRef<HTMLDivElement>(null);
  const prevScrollHeightRef = useRef<number>(0);

  // IntersectionObserver for loading older months (top sentinel)
  useEffect(() => {
    const topSentinel = topSentinelRef.current;
    const container = scrollContainerRef.current;
    if (!topSentinel || !container) return;

    const observer = new IntersectionObserver(
      (entries) => {
        if (entries[0].isIntersecting) {
          // Store scroll height BEFORE adding new content at the top
          prevScrollHeightRef.current = container.scrollHeight;
          loadOlder();
        }
      },
      { threshold: 0.1, root: container }
    );

    observer.observe(topSentinel);
    return () => observer.disconnect();
  }, [loadOlder]);

  // IntersectionObserver for loading newer months (bottom sentinel)
  useEffect(() => {
    const bottomSentinel = bottomSentinelRef.current;
    const container = scrollContainerRef.current;
    if (!bottomSentinel || !container) return;

    const observer = new IntersectionObserver(
      (entries) => {
        if (entries[0].isIntersecting) {
          loadNewer();
        }
      },
      { threshold: 0.1, root: container }
    );

    observer.observe(bottomSentinel);
    return () => observer.disconnect();
  }, [loadNewer]);

  // IntersectionObserver for tracking active month (sticky headers)
  useEffect(() => {
    const container = scrollContainerRef.current;
    if (!container) return;

    const headers = container.querySelectorAll('.calendar-month-sticky-header');
    if (headers.length === 0) return;

    const observer = new IntersectionObserver(
      (entries) => {
        entries.forEach((entry) => {
          if (entry.isIntersecting) {
            const header = entry.target as HTMLElement;
            const year = parseInt(header.dataset.year || '0', 10);
            const month = parseInt(header.dataset.month || '0', 10);
            if (year && month) {
              setActiveMonth(year, month);
            }
          }
        });
      },
      { threshold: [0.5], root: container }
    );

    headers.forEach((header) => observer.observe(header));
    return () => observer.disconnect();
  }, [months, setActiveMonth]);

  // Preserve scroll position when prepending older months
  useLayoutEffect(() => {
    const container = scrollContainerRef.current;
    if (!container || months.length === 0) return;

    const firstMonthKey = `${months[0].year}-${String(months[0].month).padStart(2, '0')}`;

    // When the first month changes (new month prepended), adjust scroll position
    if (prevScrollHeightRef.current > 0) {
      const newScrollHeight = container.scrollHeight;
      const delta = newScrollHeight - prevScrollHeightRef.current;
      if (delta > 0) {
        container.scrollTop += delta;
      }
      prevScrollHeightRef.current = 0;
    }
  }, [months.length > 0 ? `${months[0].year}-${months[0].month}` : '']);

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
          {/* Top sentinel for loading older months */}
          <div ref={topSentinelRef} className="calendar-sentinel" />

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
                  <div className="loading-state">
                    <span className="spinner" /> Loading...
                  </div>
                ) : monthData.data ? (
                  <MonthView calendarData={monthData.data} onDayClick={handleDayClick} />
                ) : null}
              </div>
            );
          })}

          {/* Bottom sentinel for loading newer months */}
          <div ref={bottomSentinelRef} className="calendar-sentinel" />
        </div>
      </div>
    </div>
  );
}
