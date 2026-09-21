import { PageHead } from '@/components/PageHead';
import { EmptyState } from '@/components/EmptyState';
import { api } from '@/lib/api';
import { useApi } from '@/lib/useApi';

/**
 * Volume, latency, error rate, fallback rate and estimated cost.
 *
 * These aggregates need stored decision runs, which arrive with the
 * PostgreSQL layer in Phase 4. Until then this page reports what it can
 * actually read and says so, rather than showing illustrative numbers.
 */
export function Overview() {
  const tasks = useApi(() => api.listTasks(), []);
  const health = useApi(() => api.health(), []);

  return (
    <>
      <PageHead
        title="Overview"
        description="Decision volume, latency, error rate, fallback rate and estimated cost."
      />

      {health.error && (
        <div className="notice error">
          Cannot reach the JevKit API: {health.error}. Start it with{' '}
          <code>uvicorn apps.api.main:app --reload</code>.
        </div>
      )}

      {health.data && !health.data.jev_schema_verified && (
        <div className="notice warn">
          The Jev request/response mapping has not been verified against the official API yet.
          Results produced before that check should not be treated as measurements.
        </div>
      )}

      <div className="stack">
        <section>
          <h2 className="section-title">Stored task definitions</h2>
          {tasks.loading && <div className="empty">Loading…</div>}
          {tasks.error && <div className="notice error">{tasks.error}</div>}
          {tasks.data &&
            (tasks.data.total === 0 ? (
              <EmptyState
                title="No task definitions yet."
                hint="Create one from the Tasks page, or POST /v1/tasks."
              />
            ) : (
              <div className="grid">
                {tasks.data.items.map((task) => (
                  <div className="card" key={task.id}>
                    <div className="stat-label">{task.name}</div>
                    <div className="stat-value" style={{ fontSize: 15 }}>
                      v{task.version}
                    </div>
                    <div className="stat-note">
                      {Object.keys(task.questions).length} question(s)
                    </div>
                  </div>
                ))}
              </div>
            ))}
        </section>

        <section>
          <h2 className="section-title">Aggregate metrics</h2>
          <EmptyState
            title="Not available yet."
            hint="Volume, latency and cost aggregates need persisted decision runs (roadmap phase 4)."
          />
        </section>
      </div>
    </>
  );
}
