import { create } from 'zustand';
import type { Activity } from '../api/types.ts';
import * as activitiesApi from '../api/activities.ts';

type SortField = 'activity_date' | 'duration_seconds' | 'distance_meters' | 'tss' | 'name';
type SortDir = 'asc' | 'desc';

interface ActivityState {
  activities: Activity[];
  total: number;
  loading: boolean;
  error: string | null;
  page: number;
  pageSize: number;
  sortField: SortField;
  sortDir: SortDir;

  fetchActivities: () => Promise<void>;
  deleteActivity: (id: number) => Promise<void>;
  setPage: (page: number) => void;
  setSort: (field: SortField) => void;
  clearError: () => void;
}

export const useActivityStore = create<ActivityState>((set, get) => ({
  activities: [],
  total: 0,
  loading: false,
  error: null,
  page: 0,
  pageSize: 25,
  sortField: 'activity_date',
  sortDir: 'desc',

  fetchActivities: async () => {
    const { page, pageSize, sortField, sortDir } = get();
    set({ loading: true, error: null });
    try {
      const data = await activitiesApi.getActivities(
        pageSize,
        page * pageSize,
        sortField,
        sortDir,
      );
      set({
        activities: data.items,
        total: data.total,
        loading: false,
      });
    } catch (err: unknown) {
      const message =
        (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail ||
        'Failed to load activities';
      set({ error: message, loading: false });
    }
  },

  deleteActivity: async (id) => {
    try {
      await activitiesApi.deleteActivity(id);
      // Re-fetch the current page
      await get().fetchActivities();
    } catch (err: unknown) {
      const message =
        (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail ||
        'Failed to delete activity';
      set({ error: message });
    }
  },

  setPage: (page) => {
    set({ page });
  },

  setSort: (field) => {
    const { sortField, sortDir } = get();
    if (field === sortField) {
      set({ sortDir: sortDir === 'asc' ? 'desc' : 'asc', page: 0 });
    } else {
      set({ sortField: field, sortDir: 'desc', page: 0 });
    }
  },

  clearError: () => set({ error: null }),
}));
