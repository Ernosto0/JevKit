import { useState } from 'react';
import { PageHead } from '@/components/PageHead';
import { EmptyState } from '@/components/EmptyState';
import { TraceTimeline } from '@/components/TraceTimeline';
import { api, ApiError } from '@/lib/api';
import type { TraceResponse } from '@/lib/api';
import { timestamp } from '@/lib/format';

/**
 * Look up a trace by id.
 *
 * Listing and filtering traces arrives with persistence (roadmap phase 4);
 * lookup by id works against the API today.
 */
export function Traces() {
  const [traceId, setTraceId] = useState('');
  const [trace, setTrace] = useState<TraceResponse | null>(null);
  const [error, setError] = useState<string | null>(null);

  async function load() {
    setError(null);
    setTrace(null);
    try {
      setTrace(await api.getTrace(traceId.trim()));
    } catch (err) {
      setError(err instanceof ApiError ? `${err.status}: ${err.message}` : String(err));
    }
  }

  return (
    <>
      <PageHead
        title="Traces"
        description="Every step of an execution: validation, provider calls, retries, fallback and the final outcome."
      />

      <div className="card">
        <div className="row">
          <div style={{ flex: 1, minWidth: 260 }}>
            <label htmlFor="trace-id">Trace id</label>
            <input
              id="trace-id"
              value={traceId}
              placeholder="c0ac2f694086475caffdad9f79db3e6a"
              onChange={(e) => setTraceId(e.target.value)}
              onKeyDown={(e) => e.key === 'Enter' && load()}
            />
          </div>
          <button onClick={load} disabled={!traceId.trim()} style={{ alignSelf: 'flex-end' }}>
            Load
          </button>
        </div>
      </div>

      {error && (
        <div className="notice error" style={{ marginTop: 16 }}>
          {error}
        </div>
      )}

      {trace && (
        <div className="card" style={{ marginTop: 16 }}>
          <div className="row" style={{ marginBottom: 12 }}>
            <span className="mono">{trace.task_ref ?? 'ad-hoc'}</span>
            <span style={{ color: 'var(--text-faint)' }}>{timestamp(trace.started_at)}</span>
          </div>
          <TraceTimeline events={trace.events} />
          {trace.state === null && (
            <p style={{ color: 'var(--text-faint)', fontSize: 12, marginBottom: 0 }}>
              Input was not captured. Trace input storage is off by default.
            </p>
          )}
        </div>
      )}

      {!trace && !error && (
        <div style={{ marginTop: 16 }}>
          <EmptyState
            title="No trace loaded."
            hint="Run a decision in the Playground, then paste its trace id here."
          />
        </div>
      )}
    </>
  );
}
