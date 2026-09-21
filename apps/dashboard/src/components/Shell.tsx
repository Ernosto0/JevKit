import { NavLink, Outlet } from 'react-router-dom';
import { api } from '@/lib/api';
import { useApi } from '@/lib/useApi';

const NAV = [
  { to: '/', label: 'Overview', end: true },
  { to: '/tasks', label: 'Tasks' },
  { to: '/playground', label: 'Playground' },
  { to: '/traces', label: 'Traces' },
  { to: '/benchmarks', label: 'Benchmarks' },
  { to: '/policies', label: 'Policies' },
  { to: '/settings', label: 'Settings' },
];

export function Shell() {
  const health = useApi(() => api.health(), []);

  return (
    <div className="shell">
      <nav className="sidebar">
        <div className="brand">
          <div className="brand-name">JevKit</div>
          <div className="brand-tag">Decisions, not another chatbot.</div>
        </div>

        {NAV.map((item) => (
          <NavLink
            key={item.to}
            to={item.to}
            end={item.end}
            className={({ isActive }) => `nav-link${isActive ? ' active' : ''}`}
          >
            {item.label}
          </NavLink>
        ))}

        <div className="sidebar-footer">
          {health.error ? (
            <span style={{ color: 'var(--danger)' }}>API unreachable</span>
          ) : health.data ? (
            <>
              v{health.data.version} · {health.data.environment}
              {!health.data.jev_schema_verified && (
                <div style={{ color: 'var(--warn)', marginTop: 4 }}>Jev schema unverified</div>
              )}
            </>
          ) : (
            'connecting…'
          )}
        </div>
      </nav>

      <main className="main">
        <Outlet />
      </main>
    </div>
  );
}
