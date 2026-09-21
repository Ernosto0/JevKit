import { useState } from 'react';
import { PageHead } from '@/components/PageHead';
import { StatusPill } from '@/components/StatusPill';
import { TraceTimeline } from '@/components/TraceTimeline';
import { api, ApiError } from '@/lib/api';
import type { DecisionResponse, Question, TraceResponse } from '@/lib/api';
import { decimal, ms } from '@/lib/format';

const SAMPLE_STATE = JSON.stringify(
  { message: 'I was charged twice for my subscription this month.' },
  null,
  2,
);

const SAMPLE_QUESTIONS = JSON.stringify(
  {
    department: { kind: 'choice', options: ['billing', 'technical', 'account', 'other'] },
    urgent: { kind: 'noul', instructions: 'Is this issue urgent?' },
  },
  null,
  2,
);

/** Run a decision against the API and inspect the result and its trace. */
export function Playground() {
  const [state, setState] = useState(SAMPLE_STATE);
  const [questions, setQuestions] = useState(SAMPLE_QUESTIONS);
  const [result, setResult] = useState<DecisionResponse | null>(null);
  const [trace, setTrace] = useState<TraceResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [running, setRunning] = useState(false);

  async function run() {
    setRunning(true);
    setError(null);
    setResult(null);
    setTrace(null);

    try {
      const parsedState = JSON.parse(state) as Record<string, unknown>;
      const parsedQuestions = JSON.parse(questions) as Record<string, Question>;

      const decision = await api.decide({ state: parsedState, questions: parsedQuestions });
      setResult(decision);

      if (decision.trace_id) {
        setTrace(await api.getTrace(decision.trace_id));
      }
    } catch (err) {
      if (err instanceof SyntaxError) setError(`Invalid JSON: ${err.message}`);
      else if (err instanceof ApiError) setError(`${err.status}: ${err.message}`);
      else setError(String(err));
    } finally {
      setRunning(false);
    }
  }

  return (
    <>
      <PageHead
        title="Playground"
        description="Send a decision through the API and inspect exactly what happened."
      />

      <div className="stack">
        <div className="card">
          <div style={{ display: 'grid', gap: 14, gridTemplateColumns: '1fr 1fr' }}>
            <div>
              <label htmlFor="state">Input state (JSON)</label>
              <textarea id="state" value={state} onChange={(e) => setState(e.target.value)} />
            </div>
            <div>
              <label htmlFor="questions">Questions (JSON)</label>
              <textarea
                id="questions"
                value={questions}
                onChange={(e) => setQuestions(e.target.value)}
              />
            </div>
          </div>

          <div className="row" style={{ marginTop: 12 }}>
            <button onClick={run} disabled={running}>
              {running ? 'Running…' : 'Run decision'}
            </button>
            <span style={{ color: 'var(--text-faint)', fontSize: 12 }}>
              Calls the configured provider. This spends real quota.
            </span>
          </div>
        </div>

        {error && <div className="notice error">{error}</div>}

        {result && (
          <div className="card">
            <h2 className="section-title">Result</h2>
            <div className="row" style={{ marginBottom: 12 }}>
              <StatusPill status={result.execution_status} />
              <StatusPill status={result.validation_status} />
              <span className="mono" style={{ color: 'var(--text-dim)' }}>
                {result.provider ?? '—'}
                {result.model ? ` / ${result.model}` : ''} · {result.attempts} attempt(s) ·{' '}
                {ms(result.latency_ms)}
                {result.used_fallback ? ' · fallback' : ''}
              </span>
            </div>

            <pre className="output">{JSON.stringify(result.decisions, null, 2)}</pre>

            {Object.keys(result.confidence).length > 0 && (
              <>
                <h3 className="section-title" style={{ marginTop: 16 }}>
                  Reported confidence
                </h3>
                <div className="row">
                  {Object.entries(result.confidence).map(([key, value]) => (
                    <span key={key} className="pill">
                      {key} {decimal(value, 2)}
                    </span>
                  ))}
                </div>
                <p style={{ color: 'var(--text-faint)', fontSize: 12, marginBottom: 0 }}>
                  Confidence is what the provider reported. It is not a guarantee of correctness.
                </p>
              </>
            )}

            {result.validation_failures.length > 0 && (
              <div className="notice error" style={{ marginTop: 16, marginBottom: 0 }}>
                <strong>Validation failures</strong>
                <ul style={{ margin: '6px 0 0', paddingLeft: 18 }}>
                  {result.validation_failures.map((failure) => (
                    <li key={failure}>{failure}</li>
                  ))}
                </ul>
              </div>
            )}
          </div>
        )}

        {trace && (
          <div className="card">
            <h2 className="section-title">
              Trace <span className="mono" style={{ color: 'var(--text-faint)' }}>{trace.trace_id}</span>
            </h2>
            <TraceTimeline events={trace.events} />
          </div>
        )}
      </div>
    </>
  );
}
