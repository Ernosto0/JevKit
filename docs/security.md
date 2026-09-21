# Security and safety

See [`../SECURITY.md`](../SECURITY.md) for vulnerability reporting. This document covers the
design decisions behind it.

## Threat model

JevKit sits between an application and a model provider. That places it on the path of:

- **Provider credentials** — high-value secrets that must never travel outward.
- **User-supplied input** — untrusted text, often reaching a model verbatim.
- **Model output** — untrusted, and specifically not an instruction.
- **Traces** — potentially a durable copy of sensitive input.

## Credentials

- Keys are read from the environment via `pydantic.SecretStr` and never printed by `repr`.
- `_safe_detail()` truncates provider error bodies and never includes request headers.
- `DecisionResponse` in the API omits `raw_response` entirely.
- There is a test asserting the API key does not appear in an auth error message. Keep it.

Never accept a provider key from an API client. The service holds its own credentials; a
client presenting its own key would make the service an open relay.

## Untrusted input

Input and retrieved content are **data**, not instructions. JevKit does not interpret model
output as a command to itself or to the host system. Specifically, it:

- does not execute shell commands based on a decision,
- does not call external services based on a decision,
- does not modify its own configuration based on a decision.

## Output handling

A decision is a **recommendation**. The chain is:

```text
JevKit returns a decision
        |
        v
Application checks authorization      <- your code, not JevKit's
        |
        v
Application performs the action       <- your code, not JevKit's
```

Do not collapse these steps. A model answering `"route": "admin_tool"` is not authorization to
run an admin tool.

## Resource bounds

| Bound | Where | Default |
|---|---|---|
| Per-attempt timeout | `DecisionPolicy.timeout_seconds` | 10s |
| Retry count | `DecisionPolicy.max_retries` | 1, hard cap 5 |
| Fallback depth | Engine | at most one, cannot re-enter primary |
| Request body size | API middleware | 256 KB |
| Concurrent decisions | API dependency | 16 |
| Benchmark concurrency | Runner semaphore | 4 |

## Traces and data retention

- **Input capture is off by default.** `trace_store_inputs` must be explicitly enabled.
- `decision_traces.state` is nullable on purpose.
- `expires_at` exists on the trace table so retention can be enforced.
- Metadata-only traces remain useful: stage timings, provider, attempts and validation results
  need no input text.

Before enabling input capture on anything handling personal data, decide what you are storing,
for how long, and who can read it — and document it for your users.

## Authentication

The API authenticates clients by `X-API-Key`. Leaving `JEVKIT_API_API_KEYS` empty **disables
authentication entirely**; this is for local development only. The service logs a warning at
startup when it is unauthenticated.

## High-impact decisions

For decisions affecting money, access, employment, health, legal status, or comparable
outcomes:

- Set `on_low_confidence=OnFailure.REVIEW` and a meaningful `min_confidence`.
- Treat `needs_review` as a stop, not a hint — `result.accepted` is false for it.
- Keep a human in the loop for the final determination.
- Log enough to explain the decision to the person it affected.

JevKit does not present model output as a definitive determination, and applications built on
it should not either.

## Provider data handling

You are sending your users' data to a third party. Before production:

- Read the provider's data handling and retention terms.
- Confirm whether inputs are used for training.
- Confirm where data is processed.
- Disclose this to your users where required.

This is outside JevKit's control and inside your responsibility.
