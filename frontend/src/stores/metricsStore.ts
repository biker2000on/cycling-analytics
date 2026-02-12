import { create } from 'zustand';
import type { FitnessTimeSeries, PeriodSummary } from '../api/types.ts';
import { getFitnessData, getMetricsSummary } from '../api/metrics.ts';
import { format, subDays, subMonths, subYears } from 'date-fns';

export type DateRangePreset = '30d' | '90d' | '6m' | '1y' | 'all';

export type ThresholdMethod = 'manual' | '95_20min' | '90_8min';

interface MetricsState {
  // Fitness data
  fitnessData: FitnessTimeSeries | null;
  fitnessLoading: boolean;
  fitnessError: string | null;

  // Period summary
  summary: PeriodSummary | null;
  summaryLoading: boolean;

  // Controls
  dateRangePreset: DateRangePreset;
  startDate: string;
  endDate: string;
  thresholdMethod: ThresholdMethod;

  // Actions
  setDateRangePreset: (preset: DateRangePreset) => void;
  setCustomDateRange: (startDate: string, endDate: string) => void;
  setThresholdMethod: (method: ThresholdMethod) => void;
  fetchFitnessData: () => Promise<void>;
  fetchSummary: (startDate?: string, endDate?: string) => Promise<void>;
}

function getDateRange(preset: DateRangePreset): { startDate: string; endDate: string } {
  const today = new Date();
  const endDate = format(today, 'yyyy-MM-dd');
  let startDate: string;

  switch (preset) {
    case '30d':
      startDate = format(subDays(today, 30), 'yyyy-MM-dd');
      break;
    case '90d':
      startDate = format(subDays(today, 90), 'yyyy-MM-dd');
      break;
    case '6m':
      startDate = format(subMonths(today, 6), 'yyyy-MM-dd');
      break;
    case '1y':
      startDate = format(subYears(today, 1), 'yyyy-MM-dd');
      break;
    case 'all':
      startDate = '2000-01-01';
      break;
  }

  return { startDate, endDate };
}

export const useMetricsStore = create<MetricsState>((set, get) => {
  const initial = getDateRange('90d');

  return {
    fitnessData: null,
    fitnessLoading: false,
    fitnessError: null,

    summary: null,
    summaryLoading: false,

    dateRangePreset: '90d',
    startDate: initial.startDate,
    endDate: initial.endDate,
    thresholdMethod: 'manual',

    setDateRangePreset: (preset) => {
      const { startDate, endDate } = getDateRange(preset);
      set({ dateRangePreset: preset, startDate, endDate });
      get().fetchFitnessData();
    },

    setCustomDateRange: (startDate, endDate) => {
      set({ startDate, endDate, dateRangePreset: 'all' });
      get().fetchFitnessData();
    },

    setThresholdMethod: (method) => {
      set({ thresholdMethod: method });
      get().fetchFitnessData();
    },

    fetchFitnessData: async () => {
      const { startDate, endDate, thresholdMethod } = get();
      set({ fitnessLoading: true, fitnessError: null });
      try {
        const data = await getFitnessData(startDate, endDate, thresholdMethod);
        set({ fitnessData: data, fitnessLoading: false });
      } catch (err: unknown) {
        const message =
          (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail ||
          'Failed to load fitness data';
        set({ fitnessError: message, fitnessLoading: false });
      }
    },

    fetchSummary: async (startDate?: string, endDate?: string) => {
      set({ summaryLoading: true });
      try {
        const data = await getMetricsSummary(startDate, endDate);
        set({ summary: data, summaryLoading: false });
      } catch {
        set({ summaryLoading: false });
      }
    },
  };
});
