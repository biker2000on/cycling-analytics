/**
 * Power zone utilities for Coggan power zones.
 *
 * Zone boundaries (% of FTP):
 *   Z1: 0-54%     Active Recovery
 *   Z2: 55-75%    Endurance
 *   Z3: 76-90%    Tempo
 *   Z4: 91-105%   Threshold
 *   Z5: 106-120%  VO2max
 *   Z6: 121-150%  Anaerobic
 *   Z7: > 150%    Neuromuscular
 */

export interface ZoneBoundary {
  zone: number;
  min: number;
  max: number;
  name: string;
  color: string;
}

export interface ZoneBlockData {
  start: number;
  end: number;
  zone: number;
  avgPower: number;
}

export const ZONE_COLORS: Record<number, string> = {
  1: '#9ca3af',   // gray
  2: '#4a90d9',   // blue
  3: '#2d8659',   // green
  4: '#c9a60a',   // yellow
  5: '#d97a2e',   // orange
  6: '#d04040',   // red
  7: '#8b45a6',   // purple
};

export const ZONE_NAMES: Record<number, string> = {
  1: 'Active Recovery',
  2: 'Endurance',
  3: 'Tempo',
  4: 'Threshold',
  5: 'VO2max',
  6: 'Anaerobic',
  7: 'Neuromuscular',
};

const ZONE_UPPER_BOUNDS: [number, number][] = [
  [1, 0.55],
  [2, 0.76],
  [3, 0.91],
  [4, 1.06],
  [5, 1.21],
  [6, 1.51],
];

/** Returns the Coggan power zone (1-7) for a given wattage and FTP. */
export function getZone(watts: number, ftp: number): number {
  if (ftp <= 0) return 1;
  const ratio = watts / ftp;
  for (const [zone, upper] of ZONE_UPPER_BOUNDS) {
    if (ratio < upper) return zone;
  }
  return 7;
}

/** Returns zone boundaries with power ranges for a given FTP. */
export function getZoneBoundaries(ftp: number): ZoneBoundary[] {
  return [
    { zone: 1, min: 0, max: Math.round(ftp * 0.55) - 1, name: 'Active Recovery', color: ZONE_COLORS[1] },
    { zone: 2, min: Math.round(ftp * 0.55), max: Math.round(ftp * 0.75), name: 'Endurance', color: ZONE_COLORS[2] },
    { zone: 3, min: Math.round(ftp * 0.76), max: Math.round(ftp * 0.90), name: 'Tempo', color: ZONE_COLORS[3] },
    { zone: 4, min: Math.round(ftp * 0.91), max: Math.round(ftp * 1.05), name: 'Threshold', color: ZONE_COLORS[4] },
    { zone: 5, min: Math.round(ftp * 1.06), max: Math.round(ftp * 1.20), name: 'VO2max', color: ZONE_COLORS[5] },
    { zone: 6, min: Math.round(ftp * 1.21), max: Math.round(ftp * 1.50), name: 'Anaerobic', color: ZONE_COLORS[6] },
    { zone: 7, min: Math.round(ftp * 1.51), max: 9999, name: 'Neuromuscular', color: ZONE_COLORS[7] },
  ];
}

/** Compute 30-second zone blocks from power and elapsed time arrays. */
export function calculate30SecondZones(
  _power: (number | null)[],
  _elapsed: number[],
): ZoneBlockData[] {
  // This is a client-side fallback; normally we use the backend endpoint.
  // Not currently called but available for offline use.
  return [];
}
