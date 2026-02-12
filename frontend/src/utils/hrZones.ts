/**
 * Heart rate zone utilities (5-zone model).
 *
 * Zone boundaries (% of Max HR):
 *   Z1: < 68%    Recovery
 *   Z2: 68-82%   Aerobic
 *   Z3: 83-87%   Tempo
 *   Z4: 88-92%   Threshold
 *   Z5: > 92%    VO2max
 */

export interface HRZoneBoundary {
  zone: number;
  min: number;
  max: number;
  name: string;
  color: string;
}

export const HR_ZONE_COLORS: Record<number, string> = {
  1: '#9ca3af',   // gray
  2: '#4a90d9',   // blue
  3: '#2d8659',   // green
  4: '#c9a60a',   // yellow
  5: '#d04040',   // red
};

export const HR_ZONE_NAMES: Record<number, string> = {
  1: 'Recovery',
  2: 'Aerobic',
  3: 'Tempo',
  4: 'Threshold',
  5: 'VO2max',
};

/** Returns HR zone boundaries for a given max HR. */
export function getHRZoneBoundaries(maxHR: number): HRZoneBoundary[] {
  return [
    { zone: 1, min: 0, max: Math.round(maxHR * 0.68) - 1, name: 'Recovery', color: HR_ZONE_COLORS[1] },
    { zone: 2, min: Math.round(maxHR * 0.68), max: Math.round(maxHR * 0.82), name: 'Aerobic', color: HR_ZONE_COLORS[2] },
    { zone: 3, min: Math.round(maxHR * 0.83), max: Math.round(maxHR * 0.87), name: 'Tempo', color: HR_ZONE_COLORS[3] },
    { zone: 4, min: Math.round(maxHR * 0.88), max: Math.round(maxHR * 0.92), name: 'Threshold', color: HR_ZONE_COLORS[4] },
    { zone: 5, min: Math.round(maxHR * 0.93), max: maxHR, name: 'VO2max', color: HR_ZONE_COLORS[5] },
  ];
}

/** Returns the HR zone (1-5) for a given heart rate and max HR. */
export function getHRZone(hr: number, maxHR: number): number {
  if (maxHR <= 0) return 1;
  const ratio = hr / maxHR;
  if (ratio < 0.68) return 1;
  if (ratio < 0.82) return 2;
  if (ratio < 0.87) return 3;
  if (ratio < 0.92) return 4;
  return 5;
}
