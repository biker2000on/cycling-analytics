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

  // Infinite scroll: load older months when near the bottom
  useEffect(() => {
    const container = scrollContainerRef.current;
    if (!container) return;

    function onScroll() {
      const { scrollTop, scrollHeight, clientHeight } = container!;
      // Load more when within 400px of the bottom
      if (scrollHeight - scrollTop - clientHeight < 400) {
        loadOlder();
      }
    }

    container.addEventListener('scroll', onScroll, { passive: true });
    // Also check after each render (new month loaded may still not fill viewport)
    onScroll();
    return () => container.removeEventListener('scroll', onScroll);
  }, [loadOlder, months]);

  // Track which month header is in view for the navigation title.
  // Use a scroll listener to find the topmost visible month section.
  useEffect(() => {
    const container = scrollContainerRef.current;
    if (!container) return;

    function updateActiveMonth() {
      const sections = container!.querySelectorAll('.calendar-month-section');
      const containerTop = container!.getBoundingClientRect().top;

      for (const section of sections) {
        const rect = section.getBoundingClientRect();
        // The first section whose bottom is below the container top
        if (rect.bottom > containerTop + 50) {
          const header = section.querySelector('.calendar-month-sticky-header') as HTMLElement;
          if (header) {
            const year = parseInt(header.dataset.year || '0', 10);
            const month = parseInt(header.dataset.month || '0', 10);
            if (year && month) {
              setActiveMonth(year, month);
            }
          }
          break;
        }
      }
    }

    updateActiveMonth();
    container.addEventListener('scroll', updateActiveMonth, { passive: true });
    return () => container.removeEventListener('scroll', updateActiveMonth);
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

        </div>
      </div>
    </div>
  );
}
