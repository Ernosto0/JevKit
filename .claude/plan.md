# JevKit: Full Project Plan

> **A Jev-first, open-source decision layer for AI applications.**  
> *Decisions, not another chatbot.*

**Status:** Planning  
**Working name:** JevKit (subject to name, domain, and trademark availability checks)  
**Primary language:** Python  
**Initial release target:** v0.1

---

## 1. Executive Summary

JevKit is an open-source developer tool that helps applications use Jev for structured decision tasks, validate the results, apply explicit policies, and measure model behavior.

It is not intended to be another chatbot or a fully autonomous agent framework in its first release. Its core responsibility is to provide a reusable decision layer that applications and agent systems can call.

Jev is the featured primary provider. The architecture should nevertheless isolate provider-specific behavior behind adapters so that JevKit can support reference or fallback models where useful.

### One-sentence description

> JevKit is an open-source decision infrastructure that helps developers define typed decision tasks, run them with Jev, validate outputs, evaluate performance, and apply controlled fallback policies.

### Product principles

1. **Jev-first:** Make Jev the primary decision provider and the central subject of demos and benchmarks.
2. **Evidence over claims:** Measure accuracy, calibration, latency, and cost instead of assuming Jev is better for every task.
3. **Typed by design:** Use explicit task schemas and validated outputs.
4. **Policy-controlled:** Model outputs do not directly trigger privileged actions.
5. **Observable:** Every execution should be explainable through traces and metrics.
6. **Python-first:** Make the core useful without requiring the web dashboard.
7. **Provider-isolated:** Keep Jev integration replaceable and testable.
8. **Small initial scope:** Build a dependable decision engine before adding a full agent runtime.

---

## 2. Naming and Positioning

### Working name: JevKit

**Tagline:** Decisions, not another chatbot.

**Short description:** A Jev-first decision layer for AI applications.

**Positioning statement:** JevKit helps developers integrate structured AI decisions into their applications, compare model behavior, and define reliable execution policies.

The name is provisional. Before public launch, check GitHub repository availability, package-name availability, domain availability, and relevant trademark or branding restrictions.

JevKit must be presented as an independent project that uses Jev, not as an official TypeSafe AI product unless an explicit partnership or authorization exists.

---

## 3. Problem Statement

Developers often use general-purpose LLMs for small, repeated decisions such as:

- Classifying a support ticket
- Selecting an agent or tool
- Scoring whether content matches criteria
- Checking whether a response satisfies a schema or requirement
- Deciding whether a task needs deeper analysis or human review

These workflows can require repeated prompt construction, output parsing, validation, retry logic, model selection, logging, and evaluation.

JevKit aims to centralize that infrastructure behind a simple interface.

### What JevKit is

- A structured decision execution layer
- A Jev integration and abstraction library
- A policy and fallback engine
- A tracing and evaluation toolkit
- A developer-facing API and, later, dashboard

### What JevKit is not in v0.1

- A chatbot
- A model training platform
- A fully autonomous agent framework
- A replacement for general-purpose text-generation models
- A guarantee that Jev is more accurate or cheaper for every workload

---

## 4. Target Users

### Primary users

1. **AI application developers** who perform many classification, scoring, or routing operations.
2. **Agent developers** who need structured decisions to choose tools, agents, or next steps.
3. **AI infrastructure developers** who want to measure model latency, cost, reliability, and fallback behavior.

### Initial user profile

A solo developer or small team building Python-based AI applications who wants to try Jev, evaluate it on a real task, and integrate it without building all the surrounding infrastructure from scratch.

---

## 5. Core Use Cases

### Use case A: Support ticket routing

Input: A support message.

Possible decisions:
- Department: billing, technical, account, other
- Urgency: yes/no probability
- Escalation required: yes/no probability

JevKit returns structured decisions and trace metadata. The application remains responsible for actually routing the ticket.

### Use case B: Agent or tool routing

Input: A user task and a list of available capabilities.

Decision: Which configured agent or tool category should handle the task?

JevKit can return a route recommendation. The calling application validates permissions and performs the action.

### Use case C: Relevance or fit scoring

Input: An item and explicit evaluation criteria.

Decision: A score or category indicating how well the item matches the criteria.

Examples include job relevance, content fit, or document categorization. These should be treated as task-specific evaluations, not universal measures of quality.

### Use case D: Validation and review gates

Input: A generated result and explicit requirements.

Decision: Whether the result appears to satisfy defined requirements, whether more review is needed, or which checks failed.

A model-based check should complement deterministic validation where possible, not replace it.

---

## 6. Product Scope and Releases

### v0.1: Core decision engine

Must include:

- Jev provider adapter
- Typed task definitions
- Support for Jev's documented decision question types
- Decision execution client
- Response parsing and validation
- Explicit policy interface
- Bounded retry and timeout handling
- Basic fallback interface
- Structured execution traces
- Python SDK
- CLI playground
- Benchmark runner
- Example tasks
- Unit and integration tests
- Documentation and quickstart

The exact Jev request and response schema must be verified against the current official API before implementation. Do not assume undocumented fields or behavior.

### v0.2: Developer console

Add:

- React + TypeScript dashboard
- Decision task management
- Interactive playground
- Trace viewer
- Model comparison UI
- Benchmark history
- Dataset import/export
- Reusable policy templates
- Optional decision caching

### v1.0: Production-oriented platform

Potential additions:

- Generic agent runtime integration
- Advanced routing policies
- Multi-project configuration
- Improved authentication and access controls
- Observability integrations
- More provider adapters
- Stable public SDK and compatibility policy

These are later-stage options, not MVP requirements.

---

## 7. High-Level Architecture

```text
Application / Agent
        |
        v
     JevKit SDK
        |
        v
  Decision Engine
  - Task validation
  - Policy resolution
  - Provider selection
  - Execution control
  - Result validation
        |
        +--------------------+
        |                    |
        v                    v
   Jev Adapter        Optional Provider Adapters
        |                    |
        v                    v
   Jev API              Reference / Fallback LLM
        |
        v
  Trace + Metrics + Evaluation
        |
        v
  Optional FastAPI + PostgreSQL + Dashboard
```

### Architectural boundaries

- The **core library** must work independently of FastAPI and React.
- The **API service** exposes core functionality over HTTP.
- The **dashboard** is a client of the API, not the owner of decision logic.
- The **Jev adapter** contains Jev-specific request and response handling.
- The **policy engine** decides how validated results are accepted, retried, escalated, or rejected.
- The **evaluation system** measures behavior against labeled examples and defined criteria.

---

## 8. Core Domain Concepts

### `DecisionTask`

Defines a reusable decision task:
- Task name and description
- Input schema
- Questions and their types
- Allowed options or score ranges
- Optional evaluation instructions
- Version

### `DecisionClient`

Public SDK interface for submitting decisions and retrieving results.

### `ModelProvider`

Provider abstraction implemented by Jev and optional reference/fallback providers.

### `DecisionPolicy`

Defines:
- Primary provider
- Optional fallback provider
- Timeout
- Retry limit
- Acceptance rules
- Escalation behavior
- Optional budget constraints

### `DecisionResult`

Normalized result containing:
- Decision values
- Provider and model metadata when available
- Confidence/probability fields when returned by the provider
- Validation status
- Execution status
- Timing and usage metadata when available
- Trace identifier

### `DecisionTrace`

Records the execution lifecycle:
- Request received
- Schema validation
- Policy resolution
- Provider call
- Response parsing
- Validation
- Retry/fallback events
- Final outcome

### `BenchmarkRunner`

Runs a defined task over a labeled dataset and produces comparable evaluation results.

---

## 9. Public SDK Design

The SDK should feel simple while exposing advanced behavior through optional configuration.

Illustrative API:

```python
from jevkit import DecisionClient, Choice, Noul

client = DecisionClient.from_env()

result = await client.decide(
    state={"message": "I was charged twice for my subscription."},
    questions={
        "department": Choice(options=["billing", "technical", "account", "other"]),
        "urgent": Noul(instructions="Is this issue urgent?"),
    },
)

print(result.decisions)
```

This is an API design sketch, not a claim about Jev's exact wire format. Implement against the official API contract.

### SDK requirements

- Async-first interface
- Clear typed request objects
- Predictable exceptions
- Configurable timeout
- No hidden unbounded retries
- Optional trace metadata
- Helpful error messages
- Environment-based configuration
- Minimal required dependencies

---

## 10. Decision Execution Lifecycle

```text
1. Receive request
2. Validate task and input schema
3. Resolve policy
4. Select provider
5. Execute provider request
6. Parse provider response
7. Validate normalized result
8. Apply acceptance policy
   - Accept
   - Retry within configured limit
   - Escalate to fallback
   - Mark for human review
   - Return controlled failure
9. Persist trace and metrics
10. Return normalized result
```

### Reliability rules

- Retry only when the error is retryable.
- Set strict retry and timeout limits.
- Avoid fallback loops.
- Distinguish provider errors from invalid outputs and low-confidence decisions.
- Never treat model confidence as guaranteed correctness.
- Never execute privileged actions solely because a model returned a decision.

---

## 11. Model Routing and Fallback

Jev is the primary provider in the initial product experience.

Routing should begin with explicit, deterministic policies rather than a self-learning router.

Illustrative policy:

```yaml
policy:
  primary_provider: jev
  fallback_provider: reference_llm
  timeout_seconds: 10
  max_retries: 1
  on_invalid_response: fallback
  on_timeout: retry_then_fallback
  on_low_confidence: escalate
```

The schema is illustrative and must be finalized during implementation.

### Fallback triggers

- Provider timeout
- Provider/API error after allowed retries
- Invalid or unparseable response
- Policy-defined low-confidence result
- Policy-defined budget or availability condition

A fallback result must go through its own validation and acceptance policy. The fallback model is not automatically assumed to be more accurate.

---

## 12. Evaluation and Benchmarking

Benchmarking is a central differentiator of JevKit.

The goal is to make model behavior measurable on real tasks, not to publish unsupported claims.

### Benchmark workflow

1. Define a task and its expected output schema.
2. Prepare a labeled dataset.
3. Run Jev on the dataset.
4. Optionally run one or more reference models on the same examples.
5. Evaluate outputs against ground truth.
6. Record provider/model identifiers, task version, dataset version, date, and configuration.
7. Generate a reproducible report.

### Metrics

| Metric | Purpose |
|---|---|
| Accuracy | Overall correctness for suitable labeled tasks |
| Precision / Recall / F1 | Classification error profile |
| Brier score | Quality of probabilistic predictions when applicable |
| Calibration error | Agreement between confidence and observed correctness |
| P50 / P95 latency | Typical and tail latency |
| Cost per 1,000 decisions | Estimated provider cost under recorded pricing |
| Invalid response rate | Output parsing/validation failures |
| Fallback rate | Frequency of escalation to another provider |
| Coverage | Share of inputs receiving an accepted result |

Metrics should only be reported when applicable and computed from a documented dataset and methodology.

### Benchmark safeguards

- Use the same examples for compared models.
- Record model versions and configuration.
- Keep a clear separation between demo data and measured data.
- Do not present illustrative numbers as real results.
- Publish limitations, dataset composition, and evaluation methodology.
- Avoid claiming Jev wins universally.

---

## 13. Example Benchmark Datasets

Start with small, transparent datasets that can be inspected and reproduced.

### Dataset 1: Support ticket routing

Fields:
- `input_message`
- `expected_department`
- `expected_urgent`

### Dataset 2: Agent task routing

Fields:
- `task_description`
- `available_routes`
- `expected_route`

### Dataset 3: Requirement checks

Fields:
- `artifact`
- `requirements`
- `expected_pass_fail`
- `expected_missing_requirements`

Use synthetic or appropriately licensed examples initially. Document how labels were created and where ambiguity exists.

---

## 14. FastAPI Service

The API is a thin layer around the core library.

### Proposed endpoints

| Endpoint | Purpose |
|---|---|
| `POST /v1/decisions` | Execute a decision |
| `GET /v1/decisions/{id}` | Retrieve a decision |
| `GET /v1/traces/{id}` | Retrieve execution trace |
| `POST /v1/tasks` | Create a task definition |
| `GET /v1/tasks` | List task definitions |
| `POST /v1/benchmarks` | Start a benchmark |
| `GET /v1/benchmarks/{id}` | Retrieve benchmark status/results |
| `GET /health` | Health check |

These are JevKit endpoints, not Jev's own API.

### API requirements

- Pydantic request and response schemas
- API-key authentication for hosted or multi-user deployments
- Request size limits
- Timeouts and bounded concurrency
- Safe error responses
- OpenAPI documentation
- No provider secrets returned to clients

---

## 15. Data Model

Use PostgreSQL for API-backed persistence. The standalone SDK should not require a database.

### Initial entities

- `projects`
- `decision_tasks`
- `decision_policies`
- `decision_runs`
- `decision_traces`
- `model_calls`
- `benchmark_runs`
- `evaluation_results`

### Data retention

- Make trace retention configurable.
- Avoid storing sensitive input by default in hosted deployments unless needed and clearly disclosed.
- Support metadata-only traces where appropriate.
- Mask secrets and credentials from logs.
- Document what is persisted and for how long.

---

## 16. Dashboard (v0.2)

### Pages

1. **Overview:** Decision volume, latency, error rate, fallback rate, estimated cost.
2. **Tasks:** Create and manage decision definitions.
3. **Playground:** Test a task against sample inputs.
4. **Traces:** Inspect each execution step.
5. **Benchmarks:** Compare providers on the same dataset.
6. **Policies:** Configure provider choice, timeouts, retries, and fallback.
7. **Settings:** Project and provider configuration.

### Design direction

- Dark, minimal developer-tool interface
- Clear distinction between measured values and illustrative/demo data
- Focus on execution clarity rather than decorative AI visuals
- Show model/provider, task version, trace status, and validation outcome
- Make benchmark methodology accessible from result views

---

## 17. Security and Safety

### MVP requirements

- Keep provider API keys server-side.
- Never log raw secrets.
- Validate all input and output schemas.
- Bound retries, request size, execution time, and concurrency.
- Do not execute shell commands or external actions based only on model output.
- Separate decision recommendations from application-side authorization.
- Treat user input and retrieved content as untrusted data.
- Provide configurable trace retention and redaction.
- Document provider data handling and relevant terms.

### High-impact decisions

For decisions affecting money, access, employment, health, legal status, or other consequential outcomes, JevKit should support human review and should not present model output as a definitive determination.

---

## 18. Repository Structure

```text
jevkit/
├── apps/
│   ├── api/
│   │   ├── routes/
│   │   ├── schemas/
│   │   └── main.py
│   └── dashboard/
├── packages/
│   └── jevkit/
│       ├── client/
│       ├── providers/
│       │   └── jev/
│       ├── decisions/
│       ├── policies/
│       ├── validation/
│       ├── tracing/
│       └── benchmarks/
├── examples/
│   ├── support-routing/
│   ├── agent-routing/
│   └── requirement-checks/
├── tests/
│   ├── unit/
│   ├── integration/
│   └── benchmarks/
├── docs/
├── docker-compose.yml
├── pyproject.toml
├── .env.example
├── README.md
├── CONTRIBUTING.md
├── LICENSE
└── PLAN.md
```

The package directory should remain independently installable. The dashboard and API should not be required for SDK use.

---

## 19. Technology Stack

| Layer | Technology |
|---|---|
| Core library | Python 3.11+ |
| API | FastAPI |
| Validation | Pydantic |
| HTTP client | httpx |
| Database | PostgreSQL |
| Migrations | Alembic |
| Testing | pytest |
| Dashboard | React + TypeScript |
| Charts | Recharts |
| Local development | Docker Compose |

Avoid adding Redis, Kubernetes, or a distributed task queue until actual requirements justify them.

---

## 20. Development Roadmap

Estimates are for one developer and may change depending on Jev API access and integration complexity.

### Phase 1: Jev validation (Week 1)

- [ ] Verify current official API documentation and access.
- [ ] Confirm authentication and API key setup.
- [ ] Send a minimal real request.
- [ ] Test each documented question type.
- [ ] Test multiple questions in one request if supported.
- [ ] Record response schema, errors, timeouts, and latency.
- [ ] Build a small labeled evaluation dataset.
- [ ] Document unknowns and API limitations.

**Exit criteria:** A repeatable script can call Jev and parse a documented response.

### Phase 2: Core library (Weeks 2–3)

- [ ] Define typed task objects.
- [ ] Implement the Jev adapter.
- [ ] Implement the public decision client.
- [ ] Normalize provider responses.
- [ ] Add schema validation.
- [ ] Add typed errors.
- [ ] Add timeout and bounded retry behavior.
- [ ] Define the policy interface.
- [ ] Add unit tests and mocked provider tests.

**Exit criteria:** A developer can run a typed decision through the Python SDK.

### Phase 3: Evaluation and fallback (Week 4)

- [ ] Implement benchmark dataset format.
- [ ] Implement benchmark runner.
- [ ] Add applicable classification metrics.
- [ ] Add probability/calibration metrics where supported.
- [ ] Record latency and cost metadata when available.
- [ ] Implement one reference/fallback provider.
- [ ] Add fallback policies.
- [ ] Persist traces and benchmark runs.

**Exit criteria:** The same dataset can be run reproducibly through Jev and a reference provider.

### Phase 4: Developer API (Week 5)

- [ ] Implement FastAPI decision endpoints.
- [ ] Add task endpoints.
- [ ] Add trace retrieval.
- [ ] Add API-key authentication.
- [ ] Add PostgreSQL persistence and migrations.
- [ ] Add health endpoint and OpenAPI docs.
- [ ] Add integration tests.
- [ ] Add Docker Compose setup.

**Exit criteria:** The core can be used through a documented HTTP API.

### Phase 5: CLI and v0.1 release (Weeks 6–7)

- [ ] Build a CLI playground.
- [ ] Add support-routing and agent-routing examples.
- [ ] Write README and quickstart.
- [ ] Publish benchmark methodology and results.
- [ ] Add contribution guide and license.
- [ ] Verify clean installation in a fresh environment.
- [ ] Tag and publish v0.1.

**Exit criteria:** A new developer can install JevKit, configure Jev credentials, run an example, and understand the trace.

### Phase 6: Dashboard (Additional 1–2 weeks)

- [ ] Build overview page.
- [ ] Build task list and task editor.
- [ ] Build playground.
- [ ] Build trace viewer.
- [ ] Build benchmark comparison page.
- [ ] Add settings and policy views.
- [ ] Verify that all displayed metrics are sourced from real stored runs.

---

## 21. MVP Acceptance Criteria

The MVP is ready when:

- Jev integration works against the verified current API.
- Supported decision types are represented through typed task objects.
- Provider errors and invalid outputs are handled predictably.
- Retry and fallback limits are enforced.
- Every execution can produce a trace.
- A benchmark can run on a labeled dataset.
- Metrics are reproducible and their methodology is documented.
- The Python SDK works without the dashboard.
- API documentation and examples are complete.
- A fresh install succeeds using the documented steps.
- No unsupported claims about accuracy, cost, or speed are made.

---

## 22. Risks and Mitigations

| Risk | Mitigation |
|---|---|
| Jev API changes | Isolate integration in an adapter; pin and document supported API behavior. |
| Jev is not suitable for some tasks | Benchmark by task type; allow explicit provider choice and fallback. |
| Confidence is mistaken for correctness | Evaluate calibration on labeled data; avoid treating confidence as a guarantee. |
| Scope grows into a full agent platform | Keep autonomous execution and visual workflow editing out of v0.1. |
| Benchmarks are misleading | Use identical datasets and settings; publish methodology and limitations. |
| Provider outages or limits | Add bounded retries, timeout policies, and controlled fallback. |
| Sensitive data appears in traces | Add redaction, retention controls, and metadata-only options. |
| Name conflicts | Check repository, package, domain, and trademark availability before launch. |

---

## 23. Open-Source Strategy

### Repository essentials

- Clear README and quickstart
- Architecture diagram
- Jev integration explanation
- Working examples
- Reproducible benchmark methodology
- Transparent limitations
- Contribution guide
- License
- Changelog and release notes
- Issue templates

### License

Evaluate MIT and Apache-2.0. Choose after considering contribution expectations and compatibility needs. JevKit's license is separate from Jev's own access and usage terms.

### Launch message

> **Meet JevKit: an open-source decision layer for Jev.**  
> Define typed decisions, evaluate model behavior, build controlled fallback policies, and integrate Jev into Python applications.

Make clear that Jev is developed by TypeSafe AI and that JevKit is an independent project unless an official relationship is established.

---

## 24. Future Direction: Generic Agent Runtime

Once the decision layer is stable, JevKit can optionally grow into a generic agent runtime.

Potential architecture:

```text
User task
   |
Planner / application logic
   |
JevKit decision calls
   |
Tool or agent selection
   |
External execution layer
   |
Result evaluation
   |
Final response
```

The future runtime should use JevKit for structured routing and evaluation while leaving text generation and tool execution to appropriate providers and controlled application code.

This expansion should happen only after the standalone decision layer has demonstrated clear utility.

---

## 25. Immediate Next Steps

1. Verify Jev's current official API documentation, authentication, supported question types, response schema, pricing, and usage terms.
2. Build a minimal Python proof of concept that makes real Jev calls.
3. Create a small labeled dataset for support-ticket routing.
4. Measure output validity, correctness, latency, and cost where measurable.
5. Finalize the core SDK interface based on real API behavior.
6. Start the core library before building the dashboard.

**First milestone:** A small, tested Python prototype that demonstrates Jev-based structured decisions and records enough information to evaluate them.
