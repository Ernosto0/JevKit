# JevKit — development progress

Working state of the project against the roadmap in [`.claude/plan.md`](.claude/plan.md) §20.
Written for whoever (human or agent) picks this up next.

**Last updated:** 2026-10-04 (both provider live paths + Postgres verified; `v0.1.0` pushed to
origin) · **Version:** `0.1.0` · **Branch:** `main` · **Tag:** `v0.1.0` (pushed to origin; **not**
on PyPI — publishing dropped by decision 2026-10-04)

| Phase | Status |
|---|---|
| 1. Jev validation | ✅ **Done** — exit criteria met |
| 2. Core library | ✅ **Done** — exit criteria met |
| 3. Evaluation and fallback | ✅ **Done** — reference provider verified live against OpenAI (full vocabulary); persistence verified live |
| 4. Developer API | ✅ **Done** — Postgres persistence and the Alembic migration verified live against real Postgres 16, including durability across a server restart |
| 5. CLI and v0.1 release | ✅ **Done** — benchmark results published, clean install verified, `v0.1.0` tagged and pushed |
| 6. Dashboard | 🟡 **Scaffolded** — all seven pages build; data layer sources only real API responses, and the API it reads is verified Postgres-backed. Only open item: no browser walk-through against a live Postgres-backed API. |

Legend: `[x]` done · `[~]` partial, see note · `[ ]` not started

---

## Verify this yourself

Don't trust this file over the repo. These four commands establish the real state in a minute:

```bash
.venv/Scripts/python.exe -m pytest -q                          # 112 passed
.venv/Scripts/python.exe -m ruff check . && .venv/Scripts/python.exe -m mypy packages apps
.venv/Scripts/python.exe scripts/verify_jev_api.py             # exit 0 = live API contract holds
.venv/Scripts/python.exe scripts/verify_timeout_behavior.py    # exit 0 = real timeout, every layer
.venv/Scripts/python.exe examples/support-routing/run.py       # live end-to-end + trace
```

The last two spend real money (fractions of a cent) and need `JEV_API_KEY` in `.env`.

To verify PostgreSQL persistence against a real database (free, no provider key — just Docker):

```bash
docker run -d --name jevkit-pg -e POSTGRES_USER=jevkit -e POSTGRES_PASSWORD=jevkit \
  -e POSTGRES_DB=jevkit -p 5433:5432 postgres:16-alpine
export JEVKIT_DATABASE_URL="postgresql+asyncpg://jevkit:jevkit@localhost:5433/jevkit"
.venv/Scripts/alembic.exe upgrade head                          # applies the migration to real Postgres
.venv/Scripts/python.exe scripts/verify_postgres_persistence.py # exit 0 = full store surface round-trips live
```

To reproduce the published benchmark numbers (also billable):

```bash
.venv/Scripts/jevkit.exe bench --task examples/support-routing/task.json   --dataset examples/support-routing/dataset.jsonl --provider jev --out reports/sr.json
```

Compare against [`docs/benchmarks/`](docs/benchmarks/). Accuracy and F1 reproduced exactly across
two runs on 2026-09-21; Brier and ECE moved in the third decimal and p95 latency moved a lot more.

---

## Read this before touching the Jev adapter

Five things that cost time to discover. Full detail in [`docs/jev-api-notes.md`](docs/jev-api-notes.md).

1. **Two different services answer to "Jev".** The first-party API is TypeSafe's
   (`api.typesafe.ai/v1/systemone`, keys from <https://console.typesafe.ai/settings/keys>).
   `jevai.org` is a separate service with its own endpoint, envelope and keys. **Their keys are
   not interchangeable** — a `jevai.org` key returns `401` here and looks exactly like a broken
   key. JevKit targets TypeSafe.
2. **Jev has exactly three question types:** `noul`, `choice`, `score`. `Selection`, `Scalar`
   and `Rank` exist in JevKit's provider-agnostic vocabulary but the Jev adapter rejects them
   with `TaskDefinitionError` before making a request. For "pick several", ask one `Noul` per
   option.
3. **`noul` answers carry no `confidence` field.** The probability *is* the answer. Code that
   reads `answers[k]["confidence"]` unconditionally will `KeyError`.
4. **A `422` echoes your whole request back**, `state` included. Never log an error body
   verbatim — `provider._safe_detail()` strips the echo and there is a test pinning that.
5. **The published docs are wrong in places** — `score.probabilities`/`legend` are objects keyed
   by stringified index (not arrays), a 1-level rubric is accepted, and a top-level
   `instructions` field is a hard `400`. Probe before trusting a doc page.

---

## Phase 1 — Jev validation ✅

**Exit criteria: MET.** `scripts/verify_jev_api.py` calls Jev and parses documented responses,
exit 0. Verified against `jev-1.13.0` on 2026-09-21.

- [x] Verify current official API documentation and access
- [x] Confirm authentication and API key setup
- [x] Send a minimal real request
- [x] Test each documented question type
- [x] Test multiple questions in one request — supported, ~2× cheaper in wall time than serial
- [x] Record response schema, errors and latency
- [x] Record timeout behaviour — real (not mocked) `ConnectTimeout`/`ReadTimeout` at the
      transport layer, and a real end-to-end `TimeoutError` → retry → `TimeoutError` → `failed`
      trace through the public `DecisionClient`. `429`/`5xx` remain deliberately unforced: doing
      so means deliberately exceeding the account's Usage Limits, which the Master Customer
      Agreement prohibits (see below) — their handling stays doc-written and mock-tested only,
      by policy rather than oversight.
- [x] Review the Jev terms of use — done; surfaced one open item that needs a human/legal call,
      not an engineering one (see below)
- [x] Build a small labeled evaluation dataset — decided (with you) not to chase "real traffic"
      that doesn't exist for this project. Instead expanded all three synthetic datasets, honestly
      labeled: 18 → **35 rows** (support-routing 8→15, agent-routing 6→11, requirement-checks
      4→9), adding boundary/edge cases (security concerns, churn-risk escalation, garbled input,
      bold-text-vs-heading, fully-sourced-but-over-length). All 35 run live end to end
      (`jevkit bench`, 100% coverage, 0% invalid on all three). `synthetic: true` and an honest
      `methodology` stay mandatory and are still test-enforced
      ([`tests/unit/test_examples.py`](tests/unit/test_examples.py)). Still too small for a
      general accuracy claim — that framing is now explicit in each `dataset.meta.json` instead
      of implied by an unmet "from real traffic" goal.
- [x] Document unknowns and API limitations

**Artifacts:** [`docs/jev-api-notes.md`](docs/jev-api-notes.md),
[`scripts/verify_jev_api.py`](scripts/verify_jev_api.py),
[`scripts/verify_timeout_behavior.py`](scripts/verify_timeout_behavior.py), raw captures in
`.jevkit/phase1/` (gitignored).

**🚩 New finding, needs a decision from you:** the Master Customer Agreement (§2.3(b)) prohibits
using the Services/Output to "develop or facilitate the development of a similar or competing
product or service." Phase 3's whole point — benchmarking Jev against a reference/fallback
provider and publishing the comparison — sits close to that line. See "Terms of use" in
[`docs/jev-api-notes.md`](docs/jev-api-notes.md) for the full breakdown and options. This is not
resolved. Phase 5's "publish benchmark methodology and results" item shipped **without** waiting
for it, by taking the third option listed there — single-provider results only, no "Jev vs. X"
framing (see [`docs/benchmark-results.md`](docs/benchmark-results.md)). The flag itself is
untouched and still blocks any head-to-head comparison.

## Phase 2 — Core library ✅

**Exit criteria: MET.** A developer can run a typed decision through the Python SDK against the
real API and get a validated, traced result.

- [x] Define typed task objects — `DecisionTask`, `Noul`/`Choice`/`Score`/`Selection`/`Scalar`/`Rank`
- [x] Implement the Jev adapter — all 14 known divergences fixed, `SCHEMA_VERIFIED = True`
- [x] Implement the public decision client — `DecisionClient`
- [x] Normalize provider responses — including `usage` token counts
- [x] Add schema validation
- [x] Add typed errors
- [x] Add timeout and bounded retry behavior
- [x] Define the policy interface — `DecisionPolicy`
- [x] Add unit tests and mocked provider tests — payloads are real captures

## Phase 3 — Evaluation and fallback ✅

**Exit criteria: MET.** Jev and the reference provider both run the same dataset through the same
benchmark runner under the same policy, and both live paths are now verified. The two gaps that
used to keep this partial are both closed:

1. **Reference provider verified live (2026-10-04).** With an `OPENAI_API_KEY` supplied, a real
   decision was run through `ReferenceProvider` against OpenAI (`gpt-4o-mini`): it answered the
   **full six-type vocabulary** — including `Selection` and `Score`, which the Jev adapter rejects
   — and returned `execution_status=accepted`, `validation_status=valid`. This is the live
   counterpart to the mocked-transport tests that were the only coverage before. (The `429`/`5xx`
   paths still have not met a *real* error response — see the loose ends at the bottom.)
2. **Persistence is opt-in, and verified live.** "Persist traces and benchmark runs"
   is its own Phase 3 checklist item (`plan.md` §20, Phase 3). Phase 4's PostgreSQL persistence
   (`apps/api/db_store.py`, below) covers this for anything that goes through the API — set
   `JEVKIT_API_PERSISTENCE=postgres` and run `alembic upgrade head`. It defaults to off (in-memory)
   so tests and a quick `--reload` loop stay database-free. As of 2026-10-04 it has been run
   against a real Postgres 16 and verified end to end, including durability across a server
   restart; see Phase 4. The SDK's own `JsonlTraceRecorder` (used outside the API, e.g. by the
   CLI) is unaffected and still only writes local JSONL.

- [x] Implement benchmark dataset format — JSONL + `dataset.meta.json` with required `methodology`
- [x] Implement benchmark runner — works live: `acc=0.875 f1=0.867` on support-routing
- [x] Add applicable classification metrics — accuracy, F1
- [x] Add probability/calibration metrics — Brier, ECE
- [~] Record latency and cost metadata — latency and token counts recorded; `usage.cost_usd`
      is deliberately left `None` (hardcoding $42/B would silently go stale)
- [x] **Implement one reference/fallback provider** — `packages/jevkit/providers/reference/`,
      registered as `"reference"`. Calls an OpenAI-compatible Chat Completions API with
      JSON-schema structured outputs, so unlike the Jev adapter it supports JevKit's full
      question vocabulary (`Noul`, `Choice`, `Score`, `Selection`, `Scalar`, `Rank`), not just
      Jev's three. Wired into `config.py` (`JEVKIT_FALLBACK_*`), `.env.example`, the registry,
      and `jevkit providers`. Request/response mapping and error handling (auth, rate limit,
      timeout, 5xx, malformed content, model refusal) are tested against a mocked transport, and
      the happy path is now **also verified live** against OpenAI `gpt-4o-mini` (2026-10-04): a
      real decision over the full six-type vocabulary returned `accepted`/`valid`. The error
      branches (429/5xx) remain mock-tested only — see the loose ends at the bottom.
- [x] Add fallback policies — previously stub-only; now additionally proven with two real,
      independent adapters (`JevProvider` primary failing, `ReferenceProvider` fallback
      succeeding) composed through `DecisionEngine`, each over its own mocked HTTP transport
      (`tests/unit/test_fallback_with_real_providers.py`). Still mocked, not live.
- [x] Persist traces and benchmark runs — `JsonlTraceRecorder` still only writes local JSONL;
      DB persistence for decisions/traces/tasks/benchmark runs exists via the API's `PostgresStore`
      (Phase 4), opt-in (`JEVKIT_API_PERSISTENCE=postgres`) and **verified live** against real
      Postgres 16 on 2026-10-04 (`scripts/verify_postgres_persistence.py`)

## Phase 4 — Developer API ✅

**Exit criteria: MET.** The core is usable over a documented HTTP API, and persistence is
implemented and now **verified live** against a real Postgres 16 (2026-10-04) — the migration
applies, the full store surface round-trips, and data written by one API process is read back by
a freshly restarted process, which the in-memory store cannot do.

- [x] Implement FastAPI decision endpoints — `POST /v1/decisions`
- [x] Add task endpoints — `POST /v1/tasks`, `GET /v1/tasks`
- [x] Add trace retrieval — `GET /v1/traces/{trace_id}`
- [x] Add API-key authentication — warns loudly when unset
- [x] **Add PostgreSQL persistence and migrations** — `apps/api/store.py` defines the `Store`
      protocol; `apps/api/db_store.py`'s `PostgresStore` implements it against the ORM models in
      `apps/api/db.py`, and `apps/api/routes/*` now `await` the store instead of assuming
      in-memory. Selected with `JEVKIT_API_PERSISTENCE=postgres` (default stays `memory`, which is
      what tests and a bare `--reload` use — no DB required). Alembic is wired up under
      `migrations/`, with one hand-written initial migration covering all eight tables from
      `plan.md` §15; `alembic upgrade head --sql` confirms it compiles to valid PostgreSQL DDL, and
      `docker-compose.yml`/`docker/api.Dockerfile` run it automatically before the server starts.
      **Verified live on 2026-10-04** against `postgres:16-alpine`: `alembic upgrade head` applied
      the migration cleanly (all 8 tables, JSONB columns confirmed native via
      `information_schema`), `downgrade base` → `upgrade head` round-tripped, and
      `scripts/verify_postgres_persistence.py` round-tripped the full `PostgresStore` surface
      (decisions, traces with captured state, tasks + versioning, benchmark reports) against the
      live database. The real uvicorn server was then run with `JEVKIT_API_PERSISTENCE=postgres`:
      a task POSTed through `POST /v1/tasks` landed as a physical row and — the decisive check —
      was still returned by `GET /v1/tasks` after the server process was killed and a fresh one
      started, proving durability the in-memory store cannot provide. `tests/unit/test_db_store.py`
      still exercises the same surface against ephemeral SQLite in CI (no DB required) as the
      fast, offline structural check.
- [x] Add health endpoint and OpenAPI docs — `/health` (unprefixed) reports `jev_schema_verified`
- [x] Add integration tests
- [x] Add Docker Compose setup

Beyond the checklist: `POST /v1/benchmarks` and `GET /v1/benchmarks/{run_id}` also exist.

## Phase 5 — CLI and v0.1 release ✅

**Exit criteria: MET.** A new developer can install JevKit from a built wheel in a clean
environment, configure Jev credentials, run an example, and read the trace — verified, not
assumed. The one qualifier is that `v0.1.0` is tagged locally and deliberately not pushed or
published; that was your call, not a blocker.

- [x] Build a CLI playground — `jevkit version | providers | decide | bench`, with `--dry-run`
- [x] Add support-routing and agent-routing examples — plus requirement-checks; all three run live
- [x] Write README and quickstart
- [x] **Publish benchmark methodology and results** — methodology in
      [`docs/benchmarking.md`](docs/benchmarking.md); measured results now in
      [`docs/benchmark-results.md`](docs/benchmark-results.md), with raw per-example reports in
      [`docs/benchmarks/`](docs/benchmarks/). All 35 examples ran live against `jev-1.13.0`:
      100% coverage, 0% invalid, latency p50 304-364ms. Accuracy 0.455-1.000 by question.
      **Single-provider only** — this takes the "drop head-to-head framing" option from the
      §2.3(b) flag in Phase 1 above rather than resolving it, so the legal question stays open and still
      blocks any published "Jev vs. X" comparison.
- [x] Add contribution guide and license — MIT, CONTRIBUTING.md, issue/PR templates, CI
- [x] **Verify clean installation in a fresh environment** — built `jevkit-0.1.0` (sdist + wheel)
      with `python -m build` in an isolated env, installed the wheel with `[cli]` into a fresh
      venv with no repo on the path, and ran `import jevkit`, `jevkit version`, `jevkit providers`,
      the public `from jevkit import DecisionClient, Choice, Noul` surface, and
      `examples/support-routing/run.py --dry-run` end to end. Wheel ships `py.typed` and all seven
      subpackages. This surfaced packaging gaps — see below.
- [~] Tag and publish v0.1 — **tagged `v0.1.0` locally**, not pushed and not published to PyPI
      (your call, per the decision recorded on 2026-09-21). To finish: `git push origin main
      --follow-tags`, then `twine upload dist/*` if PyPI is wanted.

**What the clean-install check found:** the repository URL was wrong in 10 places across 6 files
(`cinaraksoy/jevkit`, which does not exist — the remote is `Ernosto0/JevKit`), including the
`[project.urls]` block in `pyproject.toml`, which would have shipped 404 links as the release's
PyPI metadata. Also fixed: the quickstart still told users live Jev calls were not expected to
work and that the base URL was a placeholder — both untrue since Phase 1 — and the README's
roadmap table still listed Phase 1 as "next" and Phase 2 as "scaffolded".

## Phase 6 — Dashboard 🟡

React + TypeScript app under `apps/dashboard/`. All seven pages are scaffolded and build cleanly
(`npm run build` verified 2026-10-04). Every page sources its data from the real API via
`src/lib/api.ts`; there is no mock data in the app.

- [~] Overview page — exists
- [~] Task list and task editor — exists
- [~] Playground — exists
- [~] Trace viewer — exists (`TraceTimeline` component)
- [~] Benchmark comparison page — exists
- [~] Settings and policy views — exist
- [~] **Verify that all displayed metrics are sourced from real stored runs** — the data layer is
      confirmed: `apps/dashboard/src/lib/api.ts` fetches every value from the real API's endpoints
      and there is zero mock/fixture data anywhere under `src/` (the only "placeholder" is an HTML
      input hint on the Traces page). The API those endpoints read is now verified Postgres-backed
      and durable (Phase 4). The dashboard also builds clean (`npm run build`: tsc type-check +
      vite, 847 modules, 2026-10-04). What remains is purely visual: nobody has opened the built
      dashboard in a browser pointed at a live Postgres-backed API and eyeballed each page. The
      substantive requirement — "no value on screen comes from anything but a real stored run" — is
      satisfied by construction; the browser walk-through is the only open piece.

---

## MVP acceptance criteria (plan §21)

- [x] Jev integration works against the verified current API
- [x] Supported decision types are represented through typed task objects
- [x] Provider errors and invalid outputs are handled predictably
- [x] Retry and fallback limits are enforced
- [x] Every execution can produce a trace
- [x] A benchmark can run on a labeled dataset
- [x] Metrics are reproducible and their methodology is documented — methodology documented, and
      the persistence path (Phase 4) is now verified live against real Postgres 16, so benchmark
      runs and their reports can be recorded durably and read back (`POST`/`GET /v1/benchmarks`),
      not only reproduced by re-running
- [x] The Python SDK works without the dashboard
- [x] API documentation and examples are complete
- [x] A fresh install succeeds using the documented steps — verified 2026-09-21 against the
      built `0.1.0` wheel in a clean venv; the documented steps themselves needed fixing first
- [x] No unsupported claims about accuracy, cost, or speed are made

---

## Suggested next steps

In dependency order — each unblocks the next.

1. ~~Review the Jev terms of use~~ **Done 2026-09-21** — see "Terms of use" in
   [`docs/jev-api-notes.md`](docs/jev-api-notes.md). It did not close clean: §2.3(b) of the MCA
   is a real risk to publishing any "Jev vs. reference provider" comparison. **Get a decision on
   that before step 2 turns into a published benchmark.**
2. ~~Build a reference/fallback provider~~ **Done 2026-09-21** — `packages/jevkit/providers/reference/`,
   an OpenAI-compatible adapter, registered as `"reference"`; see Phase 3 above. What's left here:
   (a) actually run it against a live account — needs `OPENAI_API_KEY` this environment doesn't
   have; (b) per step 1, decide how any resulting comparison will be presented (private-only,
   separate-not-head-to-head, or with TypeSafe's written permission) before building toward a
   public "vs." benchmark.
3. ~~Wire PostgreSQL persistence + migrations~~ **Implemented 2026-09-21, verified live
   2026-10-04** (Phase 4) — `apps/api/db_store.py`, `migrations/`, opt-in via
   `JEVKIT_API_PERSISTENCE=postgres`. Confirmed against real `postgres:16-alpine`: migration
   applies and round-trips, `scripts/verify_postgres_persistence.py` passes, and data survives an
   API restart. This closed out Phase 6's "real stored runs" data path and full MVP
   reproducibility.
4. ~~Verify a clean install in a fresh venv~~ **Done 2026-09-21** — it did surface packaging
   gaps: a repo URL that 404s, baked into the release metadata, plus stale quickstart and README
   claims. All fixed; see Phase 5.
5. ~~Publish benchmark results and tag v0.1~~ **Done 2026-09-21** — single-provider results in
   [`docs/benchmark-results.md`](docs/benchmark-results.md), `v0.1.0` tagged locally.

**What's actually left.** All six phases' exit criteria and all MVP acceptance criteria (below)
are met. Every remaining item is a human decision or a deliberate non-goal — none is an
engineering gap:

6. ~~Push the tag~~ **Done 2026-10-04** — `v0.1.0` (annotated, on commit `6a376dc`) is pushed to
   `origin`. **PyPI publishing was dropped by decision on 2026-10-04** ("forget PyPI"). The
   `0.1.0` wheel + sdist are built and `twine check`-clean in `dist/` (gitignored) if that
   decision is ever revisited; note the `jevkit` name is still flagged provisional in `LICENSE`/
   `README`.
7. ~~Run the API against a live Postgres~~ **Done 2026-10-04** — see Phase 4.
8. ~~Run the reference provider against a live OpenAI account~~ **Done 2026-10-04** — see Phase 3.
9. **Get the §2.3(b) legal answer** — only matters if a head-to-head "Jev vs. reference provider"
   comparison is ever published. Single-provider results sidestep it; they do not settle it. This
   is a human/legal call, not an engineering task.
10. **Visually walk the dashboard** against a live Postgres-backed API — the data path is proven
    (no mock data; builds clean) and the API is verified Postgres-backed, so this is the one
    remaining cosmetic confirmation for Phase 6. Not done.

Smaller loose ends (all deliberate or documented limitations, not blockers): `usage.cost_usd` is
never populated (hardcoding a rate would silently go stale); `429`/`5xx` handling has never met a
*real* error response for either provider (for Jev, deliberately — forcing it would breach the
account's Usage Limits; for the reference provider, the happy path is now live-verified but the
error branches stay mock-tested only); the labeled datasets are synthetic and small (35 rows),
too thin to claim anything about accuracy, which every `dataset.meta.json` states outright.

---

## Conventions worth keeping

- `make check` (or `ruff check . && ruff format --check . && mypy packages apps && pytest`) is
  what CI runs. Keep it green.
- Anything Jev-specific belongs in `packages/jevkit/providers/jev/`. The engine, policies,
  validation and benchmarks must not learn the wire format.
- A metric that does not apply reports **nothing**, never `0.0`.
- Datasets carry a `methodology` field and a `synthetic` flag. Tests enforce both.
- Secrets never reach a trace, a log or an exception message. There are tests for this.
