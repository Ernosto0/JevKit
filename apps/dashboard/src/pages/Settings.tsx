import { PageHead } from '@/components/PageHead';
import { api } from '@/lib/api';
import { useApi } from '@/lib/useApi';

/** Project and provider configuration, read from the API. */
export function Settings() {
  const health = useApi(() => api.health(), []);

  return (
    <>
      <PageHead title="Settings" description="Service and provider configuration." />

      {health.error && <div className="notice error">Cannot reach the API: {health.error}</div>}

      {health.data && (
        <div className="grid">
          <div className="card">
            <div className="stat-label">API version</div>
            <div className="stat-value" style={{ fontSize: 16 }}>
              {health.data.version}
            </div>
          </div>
          <div className="card">
            <div className="stat-label">Environment</div>
            <div className="stat-value" style={{ fontSize: 16 }}>
              {health.data.environment}
            </div>
          </div>
          <div className="card">
            <div className="stat-label">Jev schema</div>
            <div
              className="stat-value"
              style={{
                fontSize: 16,
                color: health.data.jev_schema_verified ? 'var(--ok)' : 'var(--warn)',
              }}
            >
              {health.data.jev_schema_verified ? 'verified' : 'unverified'}
            </div>
            <div className="stat-note">
              {health.data.jev_schema_verified
                ? 'Checked against the official API.'
                : 'The wire mapping is still provisional.'}
            </div>
          </div>
        </div>
      )}

      <div className="notice info" style={{ marginTop: 18 }}>
        Provider API keys are configured server-side and are never sent to this dashboard. To
        change them, edit the API service environment and restart it.
      </div>
    </>
  );
}
