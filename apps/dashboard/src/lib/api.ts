/**
 * Typed client for the JevKit API.
 *
 * The dashboard is a client of the API and never owns decision logic
 * (PLAN.md section 7). Every value it displays comes from a real API response;
 * there is no placeholder data in this module by design.
 */

const BASE_URL = import.meta.env.VITE_API_BASE_URL ?? '';
const API_KEY = import.meta.env.VITE_API_KEY ?? '';

export class ApiError extends Error {
  constructor(
    message: string,
    readonly status: number,
    readonly traceId?: string,
  ) {
    super(message);
    this.name = 'ApiError';
  }
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const headers: Record<string, string> = {
    'Content-Type': 'application/json',
    ...((init?.headers as Record<string, string>) ?? {}),
  };
  if (API_KEY) headers['X-API-Key'] = API_KEY;

  const response = await fetch(`${BASE_URL}${path}`, { ...init, headers });

  if (!response.ok) {
    let detail = `${response.status} ${response.statusText}`;
    let traceId: string | undefined;
    try {
      const body = (await response.json()) as { detail?: string; trace_id?: string };
      if (body.detail) detail = body.detail;
      traceId = body.trace_id ?? undefined;
    } catch {
      // Body was not JSON; the status line is the best description available.
    }
    throw new ApiError(detail, response.status, traceId);
  }

  return (await response.json()) as T;
}

/* ---------------------------------------------------------------- types -- */

export type QuestionKind = 'choice' | 'noul' | 'selection' | 'scalar' | 'rank';

export interface Question {
  kind: QuestionKind;
  instructions?: string | null;
  options?: string[];
  threshold?: number;
  minimum?: number;
  maximum?: number;
  min_selected?: number;
  max_selected?: number | null;
}

export type ExecutionStatus =
  | 'accepted'
  | 'fallback_accepted'
  | 'needs_review'
  | 'rejected'
  | 'failed';

export type ValidationStatus = 'valid' | 'invalid' | 'not_run';

export interface DecisionResponse {
  decisions: Record<string, unknown>;
  confidence: Record<string, number>;
  task_ref: string | null;
  provider: string | null;
  model: string | null;
  execution_status: ExecutionStatus;
  validation_status: ValidationStatus;
  validation_failures: string[];
  attempts: number;
  used_fallback: boolean;
  latency_ms: number | null;
  trace_id: string | null;
  created_at: string;
}

export interface TraceEvent {
  stage: string;
  at: string;
  elapsed_ms: number | null;
  detail: Record<string, unknown>;
}

export interface TraceResponse {
  trace_id: string;
  task_ref: string | null;
  started_at: string;
  events: TraceEvent[];
  state: Record<string, unknown> | null;
}

export interface TaskResponse {
  id: string;
  name: string;
  version: string;
  description: string | null;
  instructions: string | null;
  questions: Record<string, Question>;
  input_fields: string[];
  created_at: string;
}

export interface BenchmarkRun {
  id: string;
  status: 'queued' | 'running' | 'completed' | 'failed';
  task_ref: string;
  dataset_ref: string;
  provider: string;
  started_at: string;
  finished_at: string | null;
  error: string | null;
  report: Record<string, unknown> | null;
}

export interface Health {
  status: string;
  version: string;
  environment: string;
  jev_schema_verified: boolean;
}

/* ------------------------------------------------------------- endpoints -- */

export const api = {
  health: () => request<Health>('/health'),

  decide: (body: {
    state: Record<string, unknown>;
    questions?: Record<string, Question>;
    task_name?: string;
    task_version?: string;
  }) => request<DecisionResponse>('/v1/decisions', { method: 'POST', body: JSON.stringify(body) }),

  getDecision: (id: string) => request<DecisionResponse>(`/v1/decisions/${id}`),

  getTrace: (id: string) => request<TraceResponse>(`/v1/traces/${id}`),

  listTasks: () => request<{ items: TaskResponse[]; total: number }>('/v1/tasks'),

  createTask: (body: Omit<TaskResponse, 'id' | 'created_at'>) =>
    request<TaskResponse>('/v1/tasks', { method: 'POST', body: JSON.stringify(body) }),

  startBenchmark: (body: {
    task_name: string;
    task_version?: string;
    dataset_ref: string;
    provider: string;
  }) => request<BenchmarkRun>('/v1/benchmarks', { method: 'POST', body: JSON.stringify(body) }),

  getBenchmark: (id: string) => request<BenchmarkRun>(`/v1/benchmarks/${id}`),
};
