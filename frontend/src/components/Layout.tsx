import { NavLink, Outlet, useNavigate } from 'react-router-dom';
import { useAuthStore } from '../stores/authStore.ts';
import './Layout.css';

export default function Layout() {
  const user = useAuthStore((s) => s.user);
  const logout = useAuthStore((s) => s.logout);
  const navigate = useNavigate();

  function handleLogout() {
    logout();
    navigate('/login');
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
