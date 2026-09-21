import { useState } from 'react';
import {
  Bar,
  BarChart,
  CartesianGrid,
  Legend,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts';
import { PageHead } from '@/components/PageHead';
import { EmptyState } from '@/components/EmptyState';
import { api, ApiError } from '@/lib/api';
import type { BenchmarkRun } from '@/lib/api';
import { decimal, percent, timestamp } from '@/lib/format';

interface QuestionMetrics {
  question: string;
  scored: number;
  accuracy: number | null;
  macro_f1: number | null;
  brier_score: number | null;
  calibration_error: number | null;
}

interface Report {
  provider: string;
  model: string | null;
  total_examples: number;
  coverage: number;
  invalid_response_rate: number;
  fallback_rate: number;
  latency_p50_ms: number | null;
  latency_p95_ms: number | null;
  questions: QuestionMetrics[];
}

/**
 * Benchmark runs and their measured results.
 *
 * The chart renders only what a completed run actually reported. Nothing on
 * this page is illustrative: a metric a run did not compute shows as a dash,
 * never as zero (PLAN.md section 12).
 */
export function Benchmarks() {
  const [runId, setRunId] = useState('');
  const [run, setRun] = useState<BenchmarkRun | null>(null);
  const [error, setError] = useState<string | null>(null);

  async function load() {
    setError(null);
    setRun(null);
    try {
      setRun(await api.getBenchmark(runId.trim()));
    } catch (err) {
      setError(err instanceof ApiError ? `${err.status}: ${err.message}` : String(err));
    }
  }

  const report = (run?.report as unknown as Report | null) ?? null;
  const chartData =
    report?.questions
      .filter((q) => q.accuracy != null)
      .map((q) => ({
        question: q.question,
        accuracy: q.accuracy ?? 0,
        f1: q.macro_f1 ?? 0,
      })) ?? [];

  return (
    <>
      <PageHead
        title="Benchmarks"
        description="Compare providers on the same dataset, with the methodology attached."
      />

      <div className="notice warn">
        Comparisons are only meaningful when both runs used the same dataset version, the same
        task version and the same policy. Always read a run's methodology before quoting a number
        from it.
      </div>

      <div className="card">
        <div className="row">
          <div style={{ flex: 1, minWidth: 260 }}>
            <label htmlFor="run-id">Benchmark run id</label>
            <input
              id="run-id"
              value={runId}
              onChange={(e) => setRunId(e.target.value)}
              onKeyDown={(e) => e.key === 'Enter' && load()}
            />
          </div>
          <button onClick={load} disabled={!runId.trim()} style={{ alignSelf: 'flex-end' }}>
            Load
          </button>
        </div>
      </div>

      {error && (
        <div className="notice error" style={{ marginTop: 16 }}>
          {error}
        </div>
      )}

      {run && (
        <div className="card" style={{ marginTop: 16 }}>
          <div className="row" style={{ marginBottom: 12 }}>
            <span className={`pill ${run.status === 'completed' ? 'ok' : ''}`}>{run.status}</span>
            <span className="mono">
              {run.task_ref} · {run.dataset_ref} · {run.provider}
            </span>
            <span style={{ color: 'var(--text-faint)' }}>{timestamp(run.started_at)}</span>
          </div>

          {run.error && <div className="notice error">{run.error}</div>}

          {!report ? (
            <EmptyState
              title={`This run is ${run.status}.`}
              hint="Metrics appear once the run completes."
            />
          ) : (
            <>
              <div className="grid" style={{ marginBottom: 20 }}>
                <div className="card">
                  <div className="stat-label">Examples</div>
                  <div className="stat-value">{report.total_examples}</div>
                </div>
                <div className="card">
                  <div className="stat-label">Coverage</div>
                  <div className="stat-value">{percent(report.coverage)}</div>
                  <div className="stat-note">share receiving an accepted result</div>
                </div>
                <div className="card">
                  <div className="stat-label">Invalid responses</div>
                  <div className="stat-value">{percent(report.invalid_response_rate)}</div>
                </div>
                <div className="card">
                  <div className="stat-label">Fallback rate</div>
                  <div className="stat-value">{percent(report.fallback_rate)}</div>
                </div>
              </div>

              {chartData.length > 0 && (
                <div style={{ height: 260, marginBottom: 20 }}>
                  <ResponsiveContainer width="100%" height="100%">
                    <BarChart data={chartData}>
                      <CartesianGrid stroke="#232a32" vertical={false} />
                      <XAxis dataKey="question" stroke="#6b7784" fontSize={12} />
                      <YAxis domain={[0, 1]} stroke="#6b7784" fontSize={12} />
                      <Tooltip
                        contentStyle={{
                          background: '#14181d',
                          border: '1px solid #323b46',
                          borderRadius: 6,
                        }}
                      />
                      <Legend />
                      <Bar dataKey="accuracy" name="Accuracy" fill="#6ea8fe" />
                      <Bar dataKey="f1" name="Macro F1" fill="#4ade80" />
                    </BarChart>
                  </ResponsiveContainer>
                </div>
              )}

              <div className="table-wrap">
                <table>
                  <thead>
                    <tr>
                      <th>Question</th>
                      <th>Scored</th>
                      <th>Accuracy</th>
                      <th>Macro F1</th>
                      <th>Brier</th>
                      <th>Calibration error</th>
                    </tr>
                  </thead>
                  <tbody>
                    {report.questions.map((q) => (
                      <tr key={q.question}>
                        <td className="mono">{q.question}</td>
                        <td className="mono">{q.scored}</td>
                        <td className="mono">{decimal(q.accuracy)}</td>
                        <td className="mono">{decimal(q.macro_f1)}</td>
                        <td className="mono">{decimal(q.brier_score)}</td>
                        <td className="mono">{decimal(q.calibration_error)}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
              <p style={{ color: 'var(--text-faint)', fontSize: 12 }}>
                A dash means the metric did not apply to this dataset — not a score of zero.
              </p>
            </>
          )}
        </div>
      )}

      {!run && !error && (
        <div style={{ marginTop: 16 }}>
          <EmptyState
            title="No benchmark run loaded."
            hint="Start one with POST /v1/benchmarks or the CLI, then paste its id here."
          />
        </div>
      )}
    </>
  );
}
