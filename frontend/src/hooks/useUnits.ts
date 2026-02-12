import { useContext, useCallback } from 'react';
import { UnitContext } from '../contexts/UnitContext.tsx';
import * as conv from '../utils/conversions.ts';

export function useUnits() {
  const { unitSystem, setUnitSystem } = useContext(UnitContext);
  const isImperial = unitSystem === 'imperial';

  const formatDistance = useCallback(
    (meters: number | null): string => {
      if (meters == null) return '--';
      const val = isImperial ? conv.metersToMiles(meters) : conv.metersToKm(meters);
      return val == null ? '--' : val.toFixed(1);
    },
    [isImperial],
  );

  const formatElevation = useCallback(
    (meters: number | null): string => {
      if (meters == null) return '--';
      const val = isImperial ? conv.metersToFeet(meters) : meters;
      return val == null ? '--' : Math.round(val).toString();
    },
    [isImperial],
  );

  const formatWeight = useCallback(
    (kg: number | null): string => {
      if (kg == null) return '--';
      const val = isImperial ? conv.kgToLbs(kg) : kg;
      return val == null ? '--' : val.toFixed(1);
    },
    [isImperial],
  );

  const formatSpeed = useCallback(
    (mps: number | null): string => {
      if (mps == null) return '--';
      const val = isImperial ? conv.mpsToMph(mps) : conv.mpsToKph(mps);
      return val == null ? '--' : val.toFixed(1);
    },
    [isImperial],
  );

  const formatTemp = useCallback(
    (celsius: number | null): string => {
      if (celsius == null) return '--';
      const val = isImperial ? conv.celsiusToFahrenheit(celsius) : celsius;
      return val == null ? '--' : Math.round(val).toString();
    },
    [isImperial],
  );

  return {
    unitSystem,
    setUnitSystem,
    formatDistance,
    formatElevation,
    formatWeight,
    formatSpeed,
    formatTemp,
    distanceUnit: isImperial ? 'mi' : 'km',
    elevationUnit: isImperial ? 'ft' : 'm',
    weightUnit: isImperial ? 'lbs' : 'kg',
    speedUnit: isImperial ? 'mph' : 'km/h',
    tempUnit: isImperial ? 'F' : 'C',
  };
}
