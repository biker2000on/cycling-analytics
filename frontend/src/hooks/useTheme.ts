import { useContext } from 'react';
import { ThemeContext } from '../contexts/ThemeContext.tsx';

export function useTheme() {
  return useContext(ThemeContext);
}
