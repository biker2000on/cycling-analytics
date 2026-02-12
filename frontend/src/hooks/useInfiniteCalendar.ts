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

function getMonthKey(year: number, month: number): string {
  return `${year}-${String(month).padStart(2, '0')}`;
}

function incrementMonth(year: number, month: number): { year: number; month: number } {
  if (month === 12) {
    return { year: year + 1, month: 1 };
  }
  return { year, month: month + 1 };
}

function decrementMonth(year: number, month: number): { year: number; month: number } {
  if (month === 1) {
    return { year: year - 1, month: 12 };
  }
  return { year, month: month - 1 };
}

export function useInfiniteCalendar(): UseInfiniteCalendarReturn {
  const now = new Date();
  const currentYear = now.getFullYear();
  const currentMonth = now.getMonth() + 1;

  const [months, setMonths] = useState<MonthData[]>(() => {
    // Start with 3 months: previous, current, next
    const prev = decrementMonth(currentYear, currentMonth);
    const next = incrementMonth(currentYear, currentMonth);

    return [
      { year: prev.year, month: prev.month, data: null, loading: true, error: null },
      { year: currentYear, month: currentMonth, data: null, loading: true, error: null },
      { year: next.year, month: next.month, data: null, loading: true, error: null },
    ];
  });

  const [activeMonth, setActiveMonthState] = useState<{ year: number; month: number } | null>({
    year: currentYear,
    month: currentMonth,
  });

  const setActiveMonth = useCallback((year: number, month: number) => {
    setActiveMonthState({ year, month });
  }, []);

  const loadingRef = useRef(new Set<string>());

  // Fetch data for a specific month
  const fetchMonth = useCallback(async (year: number, month: number) => {
    const key = getMonthKey(year, month);
    if (loadingRef.current.has(key)) {
      return; // Already loading
    }

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

  // Load initial months
  useEffect(() => {
    months.forEach((m) => {
      if (m.data === null && !m.loading && m.error === null) {
        fetchMonth(m.year, m.month);
      }
    });
  }, [months, fetchMonth]);

  // Auto-fetch when months are added
  useEffect(() => {
    months.forEach((m) => {
      if (m.loading && m.data === null && m.error === null) {
        fetchMonth(m.year, m.month);
      }
    });
  }, [months, fetchMonth]);

  const loadOlder = useCallback(() => {
    setMonths((prev) => {
      if (prev.length === 0) return prev;

      const oldest = prev[0];
      const olderMonth = decrementMonth(oldest.year, oldest.month);

      // Prepend older month
      let updated = [
        { year: olderMonth.year, month: olderMonth.month, data: null, loading: true, error: null },
        ...prev,
      ];

      // Trim from end if exceeding MAX_MONTHS
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

      // Don't load future months beyond current month
      if (
        newerMonth.year > currentYear ||
        (newerMonth.year === currentYear && newerMonth.month > currentMonth)
      ) {
        return prev;
      }

      // Append newer month
      let updated = [
        ...prev,
        { year: newerMonth.year, month: newerMonth.month, data: null, loading: true, error: null },
      ];

      // Trim from beginning if exceeding MAX_MONTHS
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
