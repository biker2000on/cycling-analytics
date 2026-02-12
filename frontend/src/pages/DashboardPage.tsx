export default function DashboardPage() {
  return (
    <div>
      <h1 style={{ fontSize: '1.5rem', fontWeight: 700, marginBottom: 'var(--space-md)' }}>
        Dashboard
      </h1>
      <div className="card" style={{ padding: 'var(--space-xl)', textAlign: 'center' }}>
        <p style={{ color: 'var(--color-text-secondary)' }}>
          Dashboard with fitness tracker, critical power curve, and calendar coming in Phase 8.
        </p>
      </div>
    </div>
  );
}
