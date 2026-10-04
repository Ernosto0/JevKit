# JevKit

**A Jev-first, open-source decision layer for AI applications.**
_Decisions, not another chatbot._

[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)
[![Python 3.11+](https://img.shields.io/badge/python-3.11%2B-blue.svg)](pyproject.toml)
[![Version: 0.1.0](https://img.shields.io/badge/version-0.1.0-blue.svg)](CHANGELOG.md)

JevKit gives your application a reusable layer for **structured decisions**: define a typed
decision task, run it through a provider, validate the answer against its schema, apply an
explicit policy, and keep a trace you can read afterwards.

It is **not** a chatbot, an agent framework, or a text-generation library. If you need a model
to answer a closed question — *which department? is this urgent? does this draft meet its
requirements?* — and you want that answer typed, validated, and auditable, that is what JevKit
is for.

```python
from jevkit import Choice, DecisionClient, Noul

async with DecisionClient.from_env() as client:
    result = await client.decide(
        state={"message": "I was charged twice for my subscription."},
        questions={
            "department": Choice(options=["billing", "technical", "account", "other"]),
            "urgent": Noul(instructions="Is this issue urgent?"),
        },
    )

result.decisions        # {'department': 'billing', 'urgent': 0.95}
result.execution_status # ExecutionStatus.ACCEPTED
```

---

## Install

```bash
pip install "jevkit[cli]"        # SDK + command-line playground
pip install "jevkit[all]"        # + HTTP API and benchmark extras
```

Just the SDK, no extras:

```bash
pip install jevkit
```

Or from source, for the latest `main`:

```bash
git clone https://github.com/Ernosto0/JevKit.git
cd JevKit
python -m venv .venv
source .venv/bin/activate         # Windows: .venv\Scripts\activate
pip install -e ".[all]"
```

Requires **Python 3.11+**. The optional dashboard needs **Node 20+**.

### Configure a provider

JevKit talks to the real Jev API. Get a key from
**<https://console.typesafe.ai/settings/keys>**, then:

```bash
cp .env.example .env              # set JEV_API_KEY
```

> **Heads-up:** keys issued by `jevai.org` are for a *different* service and will return `401`
> here. JevKit targets TypeSafe's Jev at `api.typesafe.ai`.

No key yet? Everything below also runs against a built-in stub provider with `--dry-run`, so
you can try the shape of it without credentials or spend.

---

## Quickstart

```python
import asyncio
from jevkit import Choice, DecisionClient, Noul


async def main() -> None:
    async with DecisionClient.from_env() as client:
        result = await client.decide(
            state={"message": "I was charged twice for my subscription."},
            questions={
                "department": Choice(options=["billing", "technical", "account", "other"]),
                "urgent": Noul(instructions="Is this issue urgent?"),
            },
        )

    print(result.decisions)          # {'department': 'billing', 'urgent': 0.95}
    print(result.execution_status)   # ExecutionStatus.ACCEPTED

    # The decision is a recommendation. Your application still owns the action.
    if result.accepted and result.decisions["department"] == "billing":
        route_to_billing()


asyncio.run(main())
```

Want to see exactly what happened?

```python
result, trace = await client.decide_with_trace(state=..., questions=...)
for line in trace.summary():
    print(line)
```

```
   0.0ms  received           {'questions': ['department', 'urgent']}
   0.0ms  input_validated
   0.0ms  policy_resolved    {'primary': 'jev', 'fallback': None, 'max_retries': 1}
   0.1ms  provider_call      {'provider': 'jev', 'attempt': 1}
 925.9ms  response_parsed    {'provider': 'jev', 'model': 'jev-1.13.0'}
 926.0ms  output_validated   {'ok': True, 'failures': []}
 926.0ms  completed          {'status': 'accepted'}
```

### Try it with no credentials

```bash
python examples/support-routing/run.py --dry-run
```

---

## Question types

| Type | Answer | Validated against | Jev | Reference provider |
|---|---|---|---|---|
| `Noul` | a probability in `[0, 1]` | numeric range | ✅ | ✅ |
| `Choice` | one option | membership in a closed set | ✅ | ✅ |
| `Score` | a position on a rubric | `[0, len(levels) - 1]` | ✅ | ✅ |
| `Selection` | zero or more options | membership, uniqueness, min/max count | ❌ | ✅ |
| `Scalar` | a number | an explicit inclusive range | ❌ | ✅ |
| `Rank` | an ordering | a full permutation of the options | ❌ | ✅ |

An answer that fails validation is **never** returned as accepted.

Jev implements three question types. The other three are part of JevKit's provider-agnostic
vocabulary; the Jev adapter rejects them with a `TaskDefinitionError` *before* making a request,
rather than sending something the API will refuse. The reference provider (below) supports all
six. To express "pick several" with Jev, ask one `Noul` per option — each answer then carries
its own probability.

`Score` answers are deliberately **unrounded**: `2.94` on a four-level rubric means "almost
exactly the top level". Round it yourself if you only want the bucket.

---

## Providers and fallback

JevKit is Jev-first but provider-isolated — the engine never depends on a specific provider.

- **`jev`** — the primary adapter, verified end to end against the live `jev-1.13.0` API.
- **`reference`** — an OpenAI-compatible Chat Completions adapter using JSON-schema structured
  outputs. It supports the full six-type vocabulary and is meant as a fallback or a baseline,
  **not** as a more-accurate oracle. Point it at any OpenAI-compatible endpoint:

  ```bash
  JEVKIT_FALLBACK_PROVIDER=reference
  JEVKIT_FALLBACK_API_KEY=sk-...
  JEVKIT_FALLBACK_BASE_URL=https://api.openai.com/v1   # default
  JEVKIT_FALLBACK_MODEL=gpt-4o-mini                    # default
  ```

Execution policies are explicit and deterministic — no self-learning router, no unbounded
retries:

```python
from jevkit import DecisionPolicy, OnFailure

policy = DecisionPolicy(
    primary_provider="jev",
    fallback_provider="reference",
    timeout_seconds=10.0,
    max_retries=1,
    on_timeout=OnFailure.RETRY_THEN_FALLBACK,
    on_invalid_response=OnFailure.FALLBACK,
    on_low_confidence=OnFailure.REVIEW,
    min_confidence=0.7,
)

result = await client.decide(state=..., questions=..., policy=policy)
```

A fallback result goes through the **same** validation as the primary.

---

## CLI

```bash
jevkit providers                                     # registered adapters

jevkit decide --task examples/support-routing/task.json \
              --state '{"message": "I was charged twice."}'

jevkit decide --task ... --state ... --dry-run       # stub provider, no spend

jevkit bench --task examples/support-routing/task.json \
             --dataset examples/support-routing/dataset.jsonl \
             --provider jev --out reports/jev.json
```

---

## Benchmarking

Measuring model behavior on real tasks is the whole point, so the reporting rules are strict:

- Compared providers must run the **same** examples with the **same** policy.
- Provider, model, task version, dataset version and date are recorded with every run.
- A metric that does not apply reports **nothing**, never `0.0`.
- Every dataset carries a `methodology` describing how its labels were made.

Metrics: accuracy, precision/recall/F1, Brier score, calibration error, p50/p95 latency, cost
per 1,000 decisions, invalid-response rate, fallback rate, coverage.

> **On the shipped datasets:** the examples in [`examples/`](examples/) are **synthetic and
> tiny** (9–15 examples each, 35 total). They exist to make the pipeline runnable — not to
> support any claim about a provider. Measured results from running them against Jev are in
> [`docs/benchmark-results.md`](docs/benchmark-results.md) (100% coverage, 0% invalid across all
> 35; accuracy 0.455–1.000 by question). At this sample size the numbers describe a *pipeline*,
> not a provider. Method: [`docs/benchmarking.md`](docs/benchmarking.md).

---

## HTTP API (optional)

The service is a thin layer over the library — it owns transport, auth and persistence, never
decision logic.

```bash
pip install "jevkit[api]"
uvicorn apps.api.main:app --reload     # http://localhost:8000/docs
```

| Endpoint | Purpose |
|---|---|
| `POST /v1/decisions` | Execute a decision |
| `GET /v1/decisions/{id}` | Retrieve a decision |
| `GET /v1/traces/{id}` | Retrieve an execution trace |
| `POST /v1/tasks` · `GET /v1/tasks` | Manage task definitions |
| `POST /v1/benchmarks` · `GET /v1/benchmarks/{id}` | Run and read benchmarks |
| `GET /health` | Health, version, and Jev schema verification status |

Provider API keys stay server-side and are never returned to a client.

By default the service uses an in-memory store — nothing survives a restart, which is what a
quick `--reload` loop wants. For durable storage, set `JEVKIT_API_PERSISTENCE=postgres` and run
`alembic upgrade head`; `docker compose up` does both for you. The PostgreSQL path (schema,
migration and store) is verified against real Postgres 16 — reproduce it with
`python scripts/verify_postgres_persistence.py`.

---

## Dashboard (optional)

```bash
cd apps/dashboard
npm install
npm run dev                            # http://localhost:5173
```

A dark, minimal developer console: overview, tasks, playground, trace viewer, benchmark
comparison, policies and settings. It is a client of the API and shows only values the API
actually returned — empty states instead of sample numbers. Point it at a Postgres-backed API
to see real stored runs.

---

## Architecture

```text
Application / Agent
        |
        v
     JevKit SDK              packages/jevkit/client
        |
        v
  Decision Engine            validation → policy → provider → retry/fallback
        |
        +--------------------+
        v                    v
   Jev Adapter        Reference / Fallback LLM
        |                    |
        v                    v
    Jev API            OpenAI-compatible API
        |
        v
  Trace + Metrics + Evaluation
        |
        v
  Optional FastAPI + PostgreSQL + Dashboard
```

**Boundaries that matter:**

- The core library works without FastAPI, PostgreSQL or React.
- The API service exposes the core over HTTP; the dashboard is a client of the API.
- All Jev-specific behavior is confined to `packages/jevkit/providers/jev/`.

### Repository layout

```text
packages/jevkit/          The installable SDK
  client/                 DecisionClient and the execution engine
  decisions/              Tasks, question types, normalized results
  providers/jev/          Jev adapter (schema.py holds the wire mapping)
  providers/reference/    OpenAI-compatible fallback adapter
  policies/               Explicit execution policies
  validation/             Output validation
  tracing/                Execution traces and sinks
  benchmarks/             Datasets, metrics, runner
  cli.py                  CLI playground
apps/api/                 FastAPI service + PostgreSQL persistence
apps/dashboard/           React + TypeScript console
examples/                 Runnable tasks and labeled datasets
scripts/                  Live verification probes (Jev, timeouts, Postgres)
tests/                    unit · integration · benchmarks
docs/                     Architecture, benchmarking, security
```

---

## Safety

- Provider keys stay server-side and are never logged or returned.
- All input and output is schema-validated.
- Retries, request size, execution time and concurrency are bounded.
- Model output never executes a shell command or an external action.
- Trace input capture is **off by default**; retention is configurable.
- For decisions affecting money, access, employment, health or legal status, JevKit supports
  human review and does not present model output as a determination.

See [`docs/security.md`](docs/security.md) and [`SECURITY.md`](SECURITY.md).

---

## Project status

**v0.1.0 — usable, and verified against real services.** The Jev wire mapping was verified end
to end against `jev-1.13.0`; the reference provider was verified live against an
OpenAI-compatible API; and PostgreSQL persistence was verified against real Postgres 16,
including durability across an API restart. The three verification probes under
[`scripts/`](scripts/) let you reproduce each of those yourself.

The shipped datasets are synthetic and small, so JevKit makes **no** accuracy claim about any
provider — see the benchmarking note above.

| Phase | Scope | Status |
|---|---|---|
| 1 | Verify the Jev API; replace the provisional wire mapping | **done** — verified live against `jev-1.13.0` |
| 2 | Core library: tasks, adapter, client, validation, policies | **done** |
| 3 | Benchmark runner, metrics, fallback provider | **done** — reference provider verified live |
| 4 | FastAPI service, PostgreSQL persistence, migrations | **done** — persistence verified against live Postgres 16 |
| 5 | CLI, examples, docs, v0.1 release | **done** — v0.1.0 |
| 6 | Dashboard (v0.2) | shell + API client in place; pages render real stored runs from a Postgres-backed API |

See [`.claude/plan.md`](.claude/plan.md) for the full plan and [`CHANGELOG.md`](CHANGELOG.md)
for release notes.

---

## Contributing

Contributions are welcome — see [`CONTRIBUTING.md`](CONTRIBUTING.md). Run the suite before you
open a PR:

```bash
pytest                                 # full suite, offline
pytest -m "not benchmark"              # skip billable benchmark tests
ruff check . && ruff format --check . && mypy packages apps
cd apps/dashboard && npm run build
```

`docker compose up` brings up Postgres, the API and the dashboard together.

---

## License

MIT — see [`LICENSE`](LICENSE).

JevKit is an **independent open-source project**. Jev is developed by TypeSafe AI; JevKit is
not an official client and carries no endorsement or affiliation. JevKit's license is separate
from Jev's own access and usage terms.
