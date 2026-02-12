import { useEffect } from 'react';
import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom';
import { useAuthStore } from './stores/authStore.ts';
import { UnitProvider } from './contexts/UnitContext.tsx';
import Layout from './components/Layout.tsx';
import ProtectedRoute from './components/ProtectedRoute.tsx';
import LoginPage from './pages/LoginPage.tsx';
import RegisterPage from './pages/RegisterPage.tsx';
import SetupWizardPage from './pages/SetupWizardPage.tsx';
import ActivityListPage from './pages/ActivityListPage.tsx';
import ActivityDetailPage from './pages/ActivityDetailPage.tsx';
import DashboardPage from './pages/DashboardPage.tsx';
import CalendarPage from './pages/CalendarPage.tsx';
import PowerCurvePage from './pages/PowerCurvePage.tsx';
import TotalsPage from './pages/TotalsPage.tsx';
import SettingsPage from './pages/SettingsPage.tsx';

export default function App() {
  const hydrate = useAuthStore((s) => s.hydrate);

  useEffect(() => {
    hydrate();
  }, [hydrate]);

  return (
    <BrowserRouter>
      <UnitProvider>
        <Routes>
          {/* Public routes */}
          <Route path="/login" element={<LoginPage />} />
          <Route path="/register" element={<RegisterPage />} />
          <Route path="/setup" element={<SetupWizardPage />} />

          {/* Protected routes with layout */}
          <Route
            element={
              <ProtectedRoute>
                <Layout />
              </ProtectedRoute>
            }
          >
            <Route path="/dashboard" element={<DashboardPage />} />
            <Route path="/activities" element={<ActivityListPage />} />
            <Route path="/activities/:id" element={<ActivityDetailPage />} />
            <Route path="/calendar" element={<CalendarPage />} />
            <Route path="/power-curve" element={<PowerCurvePage />} />
            <Route path="/totals" element={<TotalsPage />} />
            <Route path="/settings" element={<SettingsPage />} />
          </Route>

          {/* Default redirect */}
          <Route path="*" element={<Navigate to="/activities" replace />} />
        </Routes>
      </UnitProvider>
    </BrowserRouter>
  );
}
