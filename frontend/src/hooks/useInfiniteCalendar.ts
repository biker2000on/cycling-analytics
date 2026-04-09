import { useState, useCallback, useRef, useEffect } from 'react';
import type { CalendarMonth } from '../api/types.ts';
import { getCalendarData } from '../api/metrics.ts';

interface MonthData {
  year: number;
  month: number;
  data: CalendarMonth | null;
  loading: boolean;
  error: string | null;
}

interface UseInfiniteCalendarReturn {
  months: MonthData[];
  loadOlder: () => void;
  scrollToToday: () => void;
  activeMonth: { year: number; month: number } | null;
  setActiveMonth: (year: number, month: number) => void;
}

const MAX_MONTHS = 120; // 10 years
const INITIAL_MONTHS = 3;

function getMonthKey(year: number, month: number): string {
  return `${year}-${String(month).padStart(2, '0')}`;
}

function incrementMonth(year: number, month: number): { year: number; month: number } {
  return month === 12 ? { year: year + 1, month: 1 } : { year, month: month + 1 };
}

function decrementMonth(year: number, month: number): { year: number; month: number } {
  return month === 1 ? { year: year - 1, month: 12 } : { year, month: month - 1 };
}

/** Build initial months list in reverse-chronological order (newest first). */
function buildInitialMonths(year: number, month: number, count: number): MonthData[] {
  const result: MonthData[] = [];
  let y = year;
  let m = month;

  for (let i = 0; i < count; i++) {
    result.push({ year: y, month: m, data: null, loading: true, error: null });
    const prev = decrementMonth(y, m);
    y = prev.year;
    m = prev.month;
  }

  return result; // [current, prev, prev-1, ...]
}

export function useInfiniteCalendar(): UseInfiniteCalendarReturn {
  const now = new Date();
  const currentYear = now.getFullYear();
  const currentMonth = now.getMonth() + 1;

  // Months stored newest-first: [current, last month, 2 months ago, ...]
  const [months, setMonths] = useState<MonthData[]>(() =>
    buildInitialMonths(currentYear, currentMonth, INITIAL_MONTHS)
  );

  const [activeMonth, setActiveMonthState] = useState<{ year: number; month: number } | null>({
    year: currentYear,
    month: currentMonth,
  });

  const setActiveMonth = useCallback((year: number, month: number) => {
    setActiveMonthState({ year, month });
  }, []);

  const fetchingRef = useRef(new Set<string>());

  const fetchMonth = useCallback(async (year: number, month: number) => {
    const key = getMonthKey(year, month);
    if (fetchingRef.current.has(key)) return;
    fetchingRef.current.add(key);

    try {
      const data = await getCalendarData(year, month);
      setMonths((prev) =>
        prev.map((m) =>
          m.year === year && m.month === month
            ? { ...m, data, loading: false, error: null }
            : m
        )
      );
    } catch (err: unknown) {
      const message =
        (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail ||
        'Failed to load calendar data';
      setMonths((prev) =>
        prev.map((m) =>
          m.year === year && m.month === month
            ? { ...m, loading: false, error: message }
            : m
        )
      );
    } finally {
      fetchingRef.current.delete(key);
    }
  }, []);

  // Auto-fetch when months are added
  useEffect(() => {
    months.forEach((m) => {
      if (m.loading && m.data === null && m.error === null) {
        fetchMonth(m.year, m.month);
      }
    });
  }, [months, fetchMonth]);

  // Scrolling down = loading older months (appended to end of array).
  // Only load one month at a time - wait until the last one finishes loading.
  const loadOlder = useCallback(() => {
    setMonths((prev) => {
      if (prev.length === 0) return prev;

      // Don't load more if the last month is still loading
      const last = prev[prev.length - 1];
      if (last.loading) return prev;

      const olderMonth = decrementMonth(last.year, last.month);

      // Don't add if already in the list
      if (prev.some((m) => m.year === olderMonth.year && m.month === olderMonth.month)) {
        return prev;
      }

      let updated = [
        ...prev,
        { year: olderMonth.year, month: olderMonth.month, data: null, loading: true, error: null },
      ];

      // Trim from beginning (newest) if exceeding max
      if (updated.length > MAX_MONTHS) {
        updated = updated.slice(updated.length - MAX_MONTHS);
      }

      return updated;
    });
  }, []);

  const scrollToToday = useCallback(() => {
    const todayKey = `month-${getMonthKey(currentYear, currentMonth)}`;
    const element = document.getElementById(todayKey);
    if (element) {
      element.scrollIntoView({ behavior: 'smooth', block: 'start' });
    }
  }, [currentYear, currentMonth]);

  return {
    months,
    loadOlder,
    scrollToToday,
    activeMonth,
    setActiveMonth,
  };
}
