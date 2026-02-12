import { createContext, useState, useEffect, useCallback } from 'react';
import type { ReactNode } from 'react';
import client from '../api/client.ts';

export type UnitSystem = 'metric' | 'imperial';

interface UnitContextValue {
  unitSystem: UnitSystem;
  setUnitSystem: (system: UnitSystem) => void;
}

export const UnitContext = createContext<UnitContextValue>({
  unitSystem: 'metric',
  setUnitSystem: () => {},
});

export function UnitProvider({ children }: { children: ReactNode }) {
  const [unitSystem, setUnitSystemState] = useState<UnitSystem>('metric');

  useEffect(() => {
    client
      .get('/settings')
      .then(({ data }) => {
        if (data.unit_system === 'imperial') setUnitSystemState('imperial');
      })
      .catch(() => {});
  }, []);

  const setUnitSystem = useCallback((system: UnitSystem) => {
    setUnitSystemState(system);
    client.put('/settings', { unit_system: system }).catch(() => {});
  }, []);

  return (
    <UnitContext.Provider value={{ unitSystem, setUnitSystem }}>
      {children}
    </UnitContext.Provider>
  );
}
