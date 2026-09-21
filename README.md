# JevKit

**A Jev-first, open-source decision layer for AI applications.**
_Decisions, not another chatbot._

[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)
[![Python 3.11+](https://img.shields.io/badge/python-3.11%2B-blue.svg)](pyproject.toml)
[![Status: pre-alpha](https://img.shields.io/badge/status-pre--alpha-orange.svg)](#project-status)

JevKit gives applications a reusable layer for **structured decisions**: define a typed
decision task, run it through a provider, validate the answer against its schema, apply an
explicit policy, and record a trace you can read afterwards.

It is not a chatbot, an agent framework, or a text-generation library.

---

## Project status

**Pre-alpha. Not usable against a real provider yet.**

The core library, policy engine, validation, tracing, benchmark runner, CLI, HTTP API and
dashboard shell are in place and tested. What is **not** done:

> ⚠️ **The Jev request and response mapping is provisional and unverified.**
> Everything Jev-specific lives in
> [`packages/jevkit/providers/jev/schema.py`](packages/jevkit/providers/jev/schema.py), which is
> written against a guessed wire format. Phase 1 of the [roadmap](#roadmap) exists to replace it
> with the documented API contract. Until `SCHEMA_VERIFIED` is `True`, treat any result from a
> real call as unvalidated. `GET /health` reports this flag so it cannot be forgotten.

Everything in this repository runs today against the built-in stub provider, which is how the
tests and `--dry-run` examples work without credentials or spend.

---

## Why

Applications make a lot of small, repeated decisions: which department a ticket belongs to,
which tool should handle a task, whether a draft meets its requirements. Each one tends to
grow the same scaffolding around it — prompt construction, output parsing, retry logic,
validation, logging, evaluation.

JevKit centralizes that scaffolding behind one interface, and makes the model's behavior
measurable instead of assumed.

**Principles**

- **Jev-first**, but provider-isolated: Jev is the primary adapter; the engine does not depend
  on it.
- **Evidence over claims**: accuracy, calibration, latency and cost are measured, not asserted.
- **Typed by design**: every answer is validated against its question's schema.
- **Policy-controlled**: a model result never triggers a privileged action on its own.
- **Observable**: every execution can produce a full trace.
- **Python-first**: the SDK is useful with no API service and no dashboard.

---

## Install

```bash
git clone https://github.com/cinaraksoy/jevkit.git
cd jevkit

python -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate

pip install -e ".[cli]"          # SDK + CLI
pip install -r requirements-dev.txt   # everything, including the API and test tools
```

Then configure credentials:

```bash
cp .env.example .env             # fill in JEV_API_KEY
```

Requires Python 3.11+. The dashboard additionally needs Node 20+.

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

    print(result.decisions)  # {'department': 'billing', 'urgent': 0.82}
    print(result.execution_status)  # ExecutionStatus.ACCEPTED

    # The decision is a recommendation. Your application still owns the action.
    if result.accepted and result.decisions["department"] == "billing":
        route_to_billing()


asyncio.run(main())
```

Want the trace too?

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
 142.7ms  response_parsed    {'provider': 'jev', 'model': 'jev-1'}
 142.8ms  output_validated   {'ok': True, 'failures': []}
 142.9ms  completed          {'status': 'accepted'}
```

### Try it with no credentials

```bash
python examples/support-routing/run.py --dry-run
```

---

## Question types

| Type | Answer | Validated against |
|---|---|---|
| `Choice` | one option | membership in a closed set |
| `Selection` | zero or more options | membership, uniqueness, min/max count |
| `Noul` | a probability in `[0, 1]` | numeric range |
| `Scalar` | a number | an explicit inclusive range |
| `Rank` | an ordering | must be a full permutation of the options |

An answer that fails validation is **never** returned as accepted.

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

## Policies

Execution policies are explicit and deterministic — there is no self-learning router and no
unbounded retry path.

```python
from jevkit import DecisionPolicy, OnFailure

policy = DecisionPolicy(
    primary_provider="jev",
    fallback_provider="reference_llm",
    timeout_seconds=10.0,
    max_retries=1,
    on_timeout=OnFailure.RETRY_THEN_FALLBACK,
    on_invalid_response=OnFailure.FALLBACK,
    on_low_confidence=OnFailure.REVIEW,
    min_confidence=0.7,
)

result = await client.decide(state=..., questions=..., policy=policy)
```

A fallback result goes through the same validation as the primary. The fallback model is not
assumed to be more accurate.

---

## Benchmarking

Measuring model behavior on real tasks is the point, so the reporting rules are strict:

- Compared providers must run the **same** examples with the **same** policy.
- Provider, model, task version, dataset version and date are recorded with every run.
- A metric that does not apply reports **nothing**, never `0.0`.
- Every dataset carries a `methodology` describing how its labels were made.

```bash
jevkit bench --task examples/support-routing/task.json \
             --dataset examples/support-routing/dataset.jsonl --provider jev
```

Metrics: accuracy, precision/recall/F1, Brier score, calibration error, p50/p95 latency, cost
per 1,000 decisions, invalid-response rate, fallback rate, coverage.

The datasets shipped in [`examples/`](examples/) are **synthetic and tiny** (6–8 examples). They
exist to make the pipeline runnable — not to support any claim about a provider. See
[`docs/benchmarking.md`](docs/benchmarking.md).

---

## HTTP API

The service is a thin layer over the library. It owns transport, auth and persistence — never
decision logic.

```bash
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

---

## Dashboard

```bash
cd apps/dashboard
npm install
npm run dev                            # http://localhost:5173
```

A dark, minimal developer console: overview, tasks, playground, trace viewer, benchmark
comparison, policies and settings. It is a client of the API and shows only values the API
actually returned — empty states instead of sample numbers.

The dashboard is v0.2 scope; the shell and API client are in place, and the pages that need
persisted runs say so plainly rather than displaying placeholder data.

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

**Boundaries that matter:**

- The core library works without FastAPI, PostgreSQL or React.
- The API service exposes the core over HTTP; the dashboard is a client of the API.
- All Jev-specific behavior is confined to `packages/jevkit/providers/jev/`.

---

## Repository layout

```text
packages/jevkit/          The installable SDK
  client/                 DecisionClient and the execution engine
  decisions/              Tasks, question types, normalized results
  providers/jev/          Jev adapter (schema.py is the unverified part)
  policies/               Explicit execution policies
  validation/             Output validation
  tracing/                Execution traces and sinks
  benchmarks/             Datasets, metrics, runner
  cli.py                  CLI playground
apps/api/                 FastAPI service
apps/dashboard/           React + TypeScript console
examples/                 Runnable tasks and labeled datasets
tests/                    unit · integration · benchmarks
docs/                     Architecture, benchmarking, security
```

---

## Development

```bash
pytest                                 # full suite, offline
pytest -m "not benchmark"              # skip benchmark tests
ruff check . && ruff format --check .
mypy

cd apps/dashboard && npm run build && npm run lint
```

`docker compose up` brings up Postgres, the API and the dashboard together.

---

## Roadmap

| Phase | Scope | Status |
|---|---|---|
| 1 | Verify the Jev API; replace the provisional wire mapping | **next** |
| 2 | Core library: tasks, adapter, client, validation, policies | scaffolded |
| 3 | Benchmark runner, metrics, fallback provider | scaffolded |
| 4 | FastAPI service, PostgreSQL persistence, migrations | partial |
| 5 | CLI, examples, docs, v0.1 release | partial |
| 6 | Dashboard (v0.2) | shell only |

See [`.claude/plan.md`](.claude/plan.md) for the full plan.

---

## Safety

- Provider keys stay server-side and are never logged or returned.
- All input and output is schema-validated.
- Retries, request size, execution time and concurrency are bounded.
- Model output never executes a shell command or an external action.
- Trace input capture is **off by default**; retention is configurable.
- For decisions affecting money, access, employment, health or legal status, JevKit supports
  human review and does not present model output as a determination.

See [`docs/security.md`](docs/security.md).

---

## Contributing

Contributions are welcome — see [`CONTRIBUTING.md`](CONTRIBUTING.md). The most useful thing
right now is Phase 1: verifying the real Jev API contract.

---

## License

MIT — see [`LICENSE`](LICENSE).

JevKit is an **independent open-source project**. Jev is developed by TypeSafe AI; JevKit is
not an official client and carries no endorsement or affiliation. JevKit's license is separate
from Jev's own access and usage terms.

The name "JevKit" is provisional, pending repository, package, domain and trademark
availability checks.
