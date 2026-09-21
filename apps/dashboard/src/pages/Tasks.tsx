import { PageHead } from '@/components/PageHead';
import { EmptyState } from '@/components/EmptyState';
import { api } from '@/lib/api';
import { useApi } from '@/lib/useApi';
import { timestamp } from '@/lib/format';

/** List of stored decision task definitions. */
export function Tasks() {
  const tasks = useApi(() => api.listTasks(), []);

  return (
    <>
      <PageHead
        title="Tasks"
        description="Reusable, versioned decision definitions. The task ref is what makes a stored run identifiable later."
      />

      {tasks.error && <div className="notice error">{tasks.error}</div>}
      {tasks.loading && <div className="empty">Loading…</div>}

      {tasks.data &&
        (tasks.data.total === 0 ? (
          <EmptyState
            title="No tasks stored."
            hint="POST /v1/tasks, or load one of the definitions in examples/."
          />
        ) : (
          <div className="card table-wrap">
            <table>
              <thead>
                <tr>
                  <th>Name</th>
                  <th>Version</th>
                  <th>Questions</th>
                  <th>Required input</th>
                  <th>Created</th>
                </tr>
              </thead>
              <tbody>
                {tasks.data.items.map((task) => (
                  <tr key={task.id}>
                    <td className="mono">{task.name}</td>
                    <td className="mono">{task.version}</td>
                    <td>
                      {Object.entries(task.questions).map(([key, question]) => (
                        <span key={key} className="pill" style={{ marginRight: 4 }}>
                          {key}:{question.kind}
                        </span>
                      ))}
                    </td>
                    <td className="mono">{task.input_fields.join(', ') || '—'}</td>
                    <td>{timestamp(task.created_at)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ))}

      <div className="notice info" style={{ marginTop: 18 }}>
        A visual task editor is planned for v0.2. Until then, define tasks as JSON and register
        them through the API.
      </div>
    </>
  );
}
