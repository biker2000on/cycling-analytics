import { create } from 'zustand';
import type { UserResponse } from '../api/types.ts';
import * as authApi from '../api/auth.ts';

interface AuthState {
  token: string | null;
  refreshToken: string | null;
  user: UserResponse | null;
  isAuthenticated: boolean;
  isLoading: boolean;
  error: string | null;

  login: (email: string, password: string) => Promise<void>;
  register: (email: string, password: string, displayName: string) => Promise<void>;
  logout: () => void;
  hydrate: () => void;
  clearError: () => void;
  setUser: (user: UserResponse) => void;
  setTokens: (accessToken: string, refreshToken: string) => void;
}

// Hydrate synchronously from localStorage before first render
const initialToken = localStorage.getItem('access_token');
const initialRefreshToken = localStorage.getItem('refresh_token');
const initiallyAuthenticated = !!(initialToken && initialRefreshToken);

export const useAuthStore = create<AuthState>((set) => ({
  token: initialToken,
  refreshToken: initialRefreshToken,
  user: null,
  isAuthenticated: initiallyAuthenticated,
  isLoading: false,
  error: null,

  login: async (email, password) => {
    set({ isLoading: true, error: null });
    try {
      const tokenData = await authApi.login(email, password);
      localStorage.setItem('access_token', tokenData.access_token);
      localStorage.setItem('refresh_token', tokenData.refresh_token);

      const user = await authApi.getCurrentUser();

      set({
        token: tokenData.access_token,
        refreshToken: tokenData.refresh_token,
        user,
        isAuthenticated: true,
        isLoading: false,
      });
    } catch (err: unknown) {
      const message =
        (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail ||
        'Login failed';
      set({ error: message, isLoading: false });
      throw err;
    }
  },

  register: async (email, password, displayName) => {
    set({ isLoading: true, error: null });
    try {
      const tokenData = await authApi.register(email, password, displayName);
      localStorage.setItem('access_token', tokenData.access_token);
      localStorage.setItem('refresh_token', tokenData.refresh_token);

      const user = await authApi.getCurrentUser();

      set({
        token: tokenData.access_token,
        refreshToken: tokenData.refresh_token,
        user,
        isAuthenticated: true,
        isLoading: false,
      });
    } catch (err: unknown) {
      const message =
        (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail ||
        'Registration failed';
      set({ error: message, isLoading: false });
      throw err;
    }
  },

  logout: () => {
    localStorage.removeItem('access_token');
    localStorage.removeItem('refresh_token');
    set({
      token: null,
      refreshToken: null,
      user: null,
      isAuthenticated: false,
      error: null,
    });
  },

  hydrate: () => {
    const token = localStorage.getItem('access_token');
    const refreshToken = localStorage.getItem('refresh_token');
    if (token && refreshToken) {
      set({ token, refreshToken, isAuthenticated: true });
      // Fetch user profile in background
      authApi
        .getCurrentUser()
        .then((user) => set({ user }))
        .catch(() => {
          // Token expired and refresh failed
          localStorage.removeItem('access_token');
          localStorage.removeItem('refresh_token');
          set({ token: null, refreshToken: null, isAuthenticated: false });
        });
    }
  },

  clearError: () => set({ error: null }),

  setUser: (user) => set({ user }),

  setTokens: (accessToken, refreshToken) => {
    localStorage.setItem('access_token', accessToken);
    localStorage.setItem('refresh_token', refreshToken);
    set({ token: accessToken, refreshToken, isAuthenticated: true });
  },
}));
