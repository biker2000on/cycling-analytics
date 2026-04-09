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
  loadNewer: () => void;
  scrollToToday: () => void;
  activeMonth: { year: number; month: number } | null;
  setActiveMonth: (year: number, month: number) => void;
}

const MAX_MONTHS = 24;
const INITIAL_PAST_MONTHS = 3;

function getMonthKey(year: number, month: number): string {
  return `${year}-${String(month).padStart(2, '0')}`;
}

function incrementMonth(year: number, month: number): { year: number; month: number } {
  return month === 12 ? { year: year + 1, month: 1 } : { year, month: month + 1 };
}

function decrementMonth(year: number, month: number): { year: number; month: number } {
  return month === 1 ? { year: year - 1, month: 12 } : { year, month: month - 1 };
}

function buildMonthRange(centerYear: number, centerMonth: number, pastCount: number): MonthData[] {
  const result: MonthData[] = [];
  let y = centerYear;
  let m = centerMonth;

  // Go back pastCount months
  for (let i = 0; i < pastCount; i++) {
    const prev = decrementMonth(y, m);
    y = prev.year;
    m = prev.month;
  }

  // Build pastCount + current + 1 future
  for (let i = 0; i < pastCount + 2; i++) {
    result.push({ year: y, month: m, data: null, loading: true, error: null });
    const next = incrementMonth(y, m);
    y = next.year;
    m = next.month;
  }

  return result;
}

export function useInfiniteCalendar(): UseInfiniteCalendarReturn {
  const now = new Date();
  const currentYear = now.getFullYear();
  const currentMonth = now.getMonth() + 1;

  const [months, setMonths] = useState<MonthData[]>(() =>
    buildMonthRange(currentYear, currentMonth, INITIAL_PAST_MONTHS)
  );

  const [activeMonth, setActiveMonthState] = useState<{ year: number; month: number } | null>({
    year: currentYear,
    month: currentMonth,
  });

  const setActiveMonth = useCallback((year: number, month: number) => {
    setActiveMonthState({ year, month });
  }, []);

  const loadingRef = useRef(new Set<string>());
  const pendingMonths = useRef(new Set<string>());

  const fetchMonth = useCallback(async (year: number, month: number) => {
    const key = getMonthKey(year, month);
    if (loadingRef.current.has(key)) return;
    loadingRef.current.add(key);

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
      loadingRef.current.delete(key);
    }
  }, []);

  // Auto-fetch when months are added
  useEffect(() => {
    months.forEach((m) => {
      if (m.loading && m.data === null && m.error === null) {
        fetchMonth(m.year, m.month);
        pendingMonths.current.delete(getMonthKey(m.year, m.month));
      }
    });
  }, [months, fetchMonth]);

  const loadOlder = useCallback(() => {
    setMonths((prev) => {
      if (prev.length === 0) return prev;

      const oldest = prev[0];
      const olderMonth = decrementMonth(oldest.year, oldest.month);
      const key = getMonthKey(olderMonth.year, olderMonth.month);

      if (pendingMonths.current.has(key)) return prev;
      pendingMonths.current.add(key);

      let updated = [
        { year: olderMonth.year, month: olderMonth.month, data: null, loading: true, error: null },
        ...prev,
      ];

      if (updated.length > MAX_MONTHS) {
        updated = updated.slice(0, MAX_MONTHS);
      }

      return updated;
    });
  }, []);

  const loadNewer = useCallback(() => {
    setMonths((prev) => {
      if (prev.length === 0) return prev;

      const newest = prev[prev.length - 1];
      const newerMonth = incrementMonth(newest.year, newest.month);

      // Allow up to 1 month into the future
      const limit = incrementMonth(currentYear, currentMonth);
      if (
        newerMonth.year > limit.year ||
        (newerMonth.year === limit.year && newerMonth.month > limit.month)
      ) {
        return prev;
      }

      const key = getMonthKey(newerMonth.year, newerMonth.month);
      if (pendingMonths.current.has(key)) return prev;
      pendingMonths.current.add(key);

      let updated = [
        ...prev,
        { year: newerMonth.year, month: newerMonth.month, data: null, loading: true, error: null },
      ];

      if (updated.length > MAX_MONTHS) {
        updated = updated.slice(updated.length - MAX_MONTHS);
      }

      return updated;
    });
  }, [currentYear, currentMonth]);

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
    loadNewer,
    scrollToToday,
    activeMonth,
    setActiveMonth,
  };
}
