import { formatDistanceToNow, format, isAfter, subDays } from 'date-fns';

/** Format seconds as HH:MM:SS */
export function formatDuration(seconds: number | null): string {
  if (seconds == null) return '--';
  const h = Math.floor(seconds / 3600);
  const m = Math.floor((seconds % 3600) / 60);
  const s = seconds % 60;
  if (h > 0) {
    return `${h}:${String(m).padStart(2, '0')}:${String(s).padStart(2, '0')}`;
  }
  return `${m}:${String(s).padStart(2, '0')}`;
}

/** Format meters to km with 1 decimal */
export function formatDistance(meters: number | null): string {
  if (meters == null) return '--';
  return (meters / 1000).toFixed(1);
}

/** Format activity date: relative if recent, absolute otherwise */
export function formatActivityDate(isoDate: string): string {
  const date = new Date(isoDate);
  const sevenDaysAgo = subDays(new Date(), 7);
  if (isAfter(date, sevenDaysAgo)) {
    return formatDistanceToNow(date, { addSuffix: true });
  }
  return format(date, 'MMM d, yyyy');
}

/** Full date and time format */
export function formatDateTime(isoDate: string): string {
  return format(new Date(isoDate), 'MMM d, yyyy h:mm a');
}

/** Format a number to 1 decimal */
export function formatDecimal1(value: number | null): string {
  if (value == null) return '--';
  return value.toFixed(1);
}

/** Format a number to 2 decimals */
export function formatDecimal2(value: number | null): string {
  if (value == null) return '--';
  return value.toFixed(2);
}

/** Format watts */
export function formatWatts(value: number | null): string {
  if (value == null) return '--';
  return `${Math.round(value)}`;
}

/** Format heart rate */
export function formatHR(value: number | null): string {
  if (value == null) return '--';
  return `${Math.round(value)}`;
}

/** Format elevation in meters */
export function formatElevation(meters: number | null): string {
  if (meters == null) return '--';
  return `${Math.round(meters)}`;
}
