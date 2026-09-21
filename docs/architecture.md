# Architecture

## Layers

```text
Application / Agent
        |
        v
     JevKit SDK              packages/jevkit/client
        |
        v
  Decision Engine
  - task + input validation
  - policy resolution
  - provider selection
  - bounded execution control
  - output validation
        |
        +--------------------+
        |                    |
        v                    v
   Jev Adapter        Optional Provider Adapters
        |                    |
        v                    v
    Jev API            Reference / Fallback LLM
        |
        v
  Trace + Metrics + Evaluation
        |
        v
  Optional FastAPI + PostgreSQL + Dashboard
```

## Boundaries

These are the rules that keep the project from collapsing into a single tangled layer:

- **The core library works alone.** `packages/jevkit` imports neither FastAPI nor SQLAlchemy.
  Its runtime dependencies are `httpx` and `pydantic`.
- **The API is thin.** `apps/api` owns transport, authentication, request limits and
  persistence. It contains no decision logic — every route delegates to the engine.
- **The dashboard is a client.** It talks to the API and nothing else. It never holds provider
  credentials.
- **Provider code stays in its adapter.** Nothing outside `providers/<name>/` knows a vendor's
  request shape, response shape or error codes.
- **Policy is separate from execution.** The engine asks the policy what to do; the policy
  never calls a provider.

## Execution lifecycle

Implemented once, in `packages/jevkit/client/engine.py`:

```text
1.  Receive request
2.  Validate task and input schema
3.  Resolve policy
4.  Select provider
5.  Execute provider request        <- bounded by timeout
6.  Parse provider response         <- adapter normalizes to ProviderResponse
7.  Validate normalized result      <- against the task's question types
8.  Apply acceptance policy
      accept | retry (bounded) | fallback | review | controlled failure
9.  Record trace
10. Return normalized result
```

Every stage emits a trace event, so any outcome is explainable after the fact.

### Reliability rules

- Retry **only** when the error is marked retryable. A 400 is not retried; a timeout is.
- Retries are capped by `policy.max_retries`. There is no unbounded path.
- Fallback runs at most once and cannot re-enter the primary.
- A fallback result is validated exactly like a primary result.
- Provider errors, invalid outputs and low-confidence results are three different things and
  are handled separately.
- Confidence is never treated as correctness.

## Module map

| Module | Responsibility |
|---|---|
| `decisions/questions.py` | Question types and their constraints |
| `decisions/task.py` | Task definition, versioning, input validation |
| `decisions/result.py` | Normalized result and status enums |
| `client/engine.py` | The lifecycle above |
| `client/client.py` | Public SDK surface |
| `policies/policy.py` | Provider choice, limits, acceptance rules |
| `validation/validators.py` | Answer-vs-question checking |
| `tracing/trace.py` | Trace model and stages |
| `tracing/recorder.py` | Trace sinks (null by default, JSONL for local dev) |
| `providers/base.py` | `ModelProvider` contract |
| `providers/jev/` | Jev transport and wire mapping |
| `providers/reference/` | Reference/fallback adapter — OpenAI-compatible structured outputs |
| `providers/static.py` | Deterministic stub for tests and dry runs |
| `providers/registry.py` | Name → provider lookup |
| `benchmarks/` | Datasets, metrics, runner |

## Data flow through a decision

```text
state + task
   -> DecisionTask.validate_state         InputValidationError on mismatch
   -> DecisionPolicy                      resolved, then immutable for this run
   -> ProviderRequest                     normalized, provider-agnostic
   -> adapter.build_request_payload       vendor shape (the only place it exists)
   -> HTTP
   -> adapter.parse_response_payload      back to decisions + confidence
   -> ProviderResponse
   -> validate_decisions                  per-question type checking
   -> DecisionResult                      + DecisionTrace
```

## Extension points

- **New provider:** subclass `ModelProvider`, register it, add `respx` tests.
- **New question type:** add to `questions.py`, add a branch in `validators.py`, map it in
  each adapter's schema module, and handle it in `benchmarks/runner.py`.
- **New trace sink:** implement the `TraceRecorder` protocol.
- **New metric:** add to `benchmarks/metrics.py`, returning `None` when inapplicable.
