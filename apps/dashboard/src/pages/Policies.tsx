import { PageHead } from '@/components/PageHead';

const FIELDS = [
  ['primary_provider', 'jev', 'Provider tried first.'],
  ['fallback_provider', 'null', 'Optional. No fallback runs unless this is set.'],
  ['timeout_seconds', '10.0', 'Per-attempt timeout.'],
  ['max_retries', '1', 'Hard ceiling. There is no unbounded retry path.'],
  ['on_provider_error', 'retry_then_fallback', 'Applies only to retryable errors.'],
  ['on_timeout', 'retry_then_fallback', 'A timeout is always retryable.'],
  ['on_invalid_response', 'fallback', 'The answer did not satisfy the task schema.'],
  ['on_low_confidence', 'review', 'Applies only when min_confidence is set.'],
  ['min_confidence', 'null', 'Unset means confidence never gates a result.'],
  ['max_cost_usd', 'null', 'Per-decision ceiling, when the provider reports cost.'],
];

/** Reference view of the policy fields the engine honours. */
export function Policies() {
  return (
    <>
      <PageHead
        title="Policies"
        description="Explicit, deterministic rules for provider choice, limits, retries and fallback."
      />

      <div className="notice info">
        Policies are sent per decision or configured server-side. Stored, reusable policy
        templates are planned for v0.2; this page documents the fields the engine honours today.
      </div>

      <div className="card table-wrap">
        <table>
          <thead>
            <tr>
              <th>Field</th>
              <th>Default</th>
              <th>Notes</th>
            </tr>
          </thead>
          <tbody>
            {FIELDS.map(([field, value, note]) => (
              <tr key={field}>
                <td className="mono">{field}</td>
                <td className="mono" style={{ color: 'var(--text-dim)' }}>
                  {value}
                </td>
                <td style={{ color: 'var(--text-dim)' }}>{note}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      <div className="notice warn" style={{ marginTop: 18 }}>
        A returned decision is a recommendation. Authorization and any resulting action stay with
        the calling application — a model result never triggers a privileged action on its own.
      </div>
    </>
  );
}
