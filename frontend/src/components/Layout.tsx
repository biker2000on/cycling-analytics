import { NavLink, Outlet, useNavigate } from 'react-router-dom';
import { useAuthStore } from '../stores/authStore.ts';
import { useTheme } from '../hooks/useTheme.ts';
import type { ThemeMode } from '../contexts/ThemeContext.tsx';
import './Layout.css';

export default function Layout() {
  const user = useAuthStore((s) => s.user);
  const logout = useAuthStore((s) => s.logout);
  const navigate = useNavigate();
  const { themeMode, setThemeMode } = useTheme();

  function handleLogout() {
    logout();
    navigate('/login');
  }

  function cycleTheme() {
    const modes: ThemeMode[] = ['light', 'dark', 'system'];
    const currentIndex = modes.indexOf(themeMode);
    const nextIndex = (currentIndex + 1) % modes.length;
    setThemeMode(modes[nextIndex]);
  }

  return (
    <div className="layout">
      <aside className="sidebar">
        <div className="sidebar-brand">Cycling Analytics</div>
        <nav className="sidebar-nav">
          <NavLink to="/dashboard" className={navClass}>
            Dashboard
          </NavLink>
          <NavLink to="/activities" className={navClass}>
            Activities
          </NavLink>
          <NavLink to="/calendar" className={navClass}>
            Calendar
          </NavLink>
          <NavLink to="/power-curve" className={navClass}>
            Power Curve
          </NavLink>
          <NavLink to="/totals" className={navClass}>
            Totals
          </NavLink>
          <NavLink to="/settings" className={navClass}>
            Settings
          </NavLink>
        </nav>
      </aside>
      <div className="main-wrapper">
        <header className="topbar">
          <div className="topbar-spacer" />
          <div className="topbar-right">
            <button
              className="theme-toggle-btn"
              onClick={cycleTheme}
              title={`Theme: ${themeMode}`}
            >
              {themeMode === 'light' && (
                <svg width="16" height="16" viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="1.5">
                  <circle cx="8" cy="8" r="3" />
                  <path d="M8 1v2M8 13v2M1 8h2M13 8h2M3.05 3.05l1.41 1.41M11.54 11.54l1.41 1.41M3.05 12.95l1.41-1.41M11.54 4.46l1.41-1.41" />
                </svg>
              )}
              {themeMode === 'dark' && (
                <svg width="16" height="16" viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="1.5">
                  <path d="M13.5 8.5a5.5 5.5 0 0 1-7-7 5.5 5.5 0 1 0 7 7z" />
                </svg>
              )}
              {themeMode === 'system' && (
                <svg width="16" height="16" viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="1.5">
                  <rect x="1.5" y="2" width="13" height="9" rx="1" />
                  <path d="M5.5 14h5M8 11v3" />
                </svg>
              )}
            </button>
            {user && <span className="topbar-user">{user.display_name}</span>}
            <button className="btn btn-secondary btn-sm" onClick={handleLogout}>
              Logout
            </button>
          </div>
        </header>
        <main className="main-content">
          <Outlet />
        </main>
      </div>
    </div>
  );
}

function navClass({ isActive }: { isActive: boolean }) {
  return `sidebar-link${isActive ? ' sidebar-link-active' : ''}`;
}
