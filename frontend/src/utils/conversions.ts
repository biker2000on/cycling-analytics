/** Pure unit conversion functions. All handle null gracefully. */

export const KM_PER_MILE = 1.60934;
export const METERS_PER_FOOT = 0.3048;
export const KG_PER_LB = 0.453592;

export function metersToKm(m: number | null): number | null {
  return m == null ? null : m / 1000;
}

export function metersToMiles(m: number | null): number | null {
  return m == null ? null : m / 1000 / KM_PER_MILE;
}

export function metersToFeet(m: number | null): number | null {
  return m == null ? null : m / METERS_PER_FOOT;
}

export function kgToLbs(kg: number | null): number | null {
  return kg == null ? null : kg / KG_PER_LB;
}

export function celsiusToFahrenheit(c: number | null): number | null {
  return c == null ? null : c * 9 / 5 + 32;
}

export function mpsToKph(mps: number | null): number | null {
  return mps == null ? null : mps * 3.6;
}

export function mpsToMph(mps: number | null): number | null {
  return mps == null ? null : mps * 3.6 / KM_PER_MILE;
}
