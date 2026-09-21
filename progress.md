# JevKit — development progress

Working state of the project against the roadmap in [`.claude/plan.md`](.claude/plan.md) §20.
Written for whoever (human or agent) picks this up next.

**Last updated:** 2026-09-21 (Phase 5 complete; v0.1.0 tagged locally) · **Version:**
`0.1.0` · **Branch:** `main` · **Tag:** `v0.1.0` (local only — not pushed, not on PyPI)

| Phase | Status |
|---|---|
| 1. Jev validation | ✅ **Done** — exit criteria met |
| 2. Core library | ✅ **Done** — exit criteria met |
| 3. Evaluation and fallback | 🟡 **Partial** — reference provider shipped, unverified live; runs persist only when Postgres persistence (below) is turned on |
| 4. Developer API | 🟡 **Partial** — Postgres persistence and migrations implemented, unverified against a live database |
| 5. CLI and v0.1 release | ✅ **Done** — benchmark results published, clean install verified, v0.1.0 tagged |
| 6. Dashboard | 🟡 **Scaffolded** — pages exist; still fed by in-memory data by default |

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

## Phase 3 — Evaluation and fallback 🟡

**Exit criteria: PARTIALLY MET.** The reference-provider blocker that used to gate this phase is
resolved — Jev and the reference provider can both run the same dataset through the same
benchmark runner under the same policy today. Two things keep this from being fully met, neither
of them the reference provider itself:

1. **Unverified live.** The reference adapter is tested against a mocked transport, same rigor
   tier as the Jev adapter's own unit tests, but nobody has run it against a real OpenAI account
   in this repo — there's no `OPENAI_API_KEY` (or other OpenAI-compatible endpoint) configured
   here. Jev's live path was verified in Phase 1; the reference provider's has not been.
2. **Persistence exists but is opt-in and unverified live.** "Persist traces and benchmark runs"
   is its own Phase 3 checklist item (`plan.md` §20, Phase 3). Phase 4's PostgreSQL persistence
   (`apps/api/db_store.py`, below) now covers this for anything that goes through the API — set
   `JEVKIT_API_PERSISTENCE=postgres` and run `alembic upgrade head`. It defaults to off (in-memory)
   so tests and a quick `--reload` loop stay database-free, and — same caveat as item 1 — nobody
   has run it against a live Postgres in this repo; see Phase 4. The SDK's own `JsonlTraceRecorder`
   (used outside the API, e.g. by the CLI) is unaffected and still only writes local JSONL.

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
      timeout, 5xx, malformed content, model refusal) are tested against a mocked transport —
      same rigor tier as the Jev adapter's own unit tests, but **not exercised against a live
      OpenAI account**, exactly the kind of gap flagged for Jev's own 429/5xx handling above.
- [x] Add fallback policies — previously stub-only; now additionally proven with two real,
      independent adapters (`JevProvider` primary failing, `ReferenceProvider` fallback
      succeeding) composed through `DecisionEngine`, each over its own mocked HTTP transport
      (`tests/unit/test_fallback_with_real_providers.py`). Still mocked, not live.
- [~] Persist traces and benchmark runs — `JsonlTraceRecorder` still only writes local JSONL;
      DB persistence for decisions/traces/tasks/benchmark runs now exists via the API's
      `PostgresStore` (Phase 4), but it's opt-in (`JEVKIT_API_PERSISTENCE=postgres`) and unverified
      against a live database

## Phase 4 — Developer API 🟡

**Exit criteria: PARTIALLY MET.** The core is usable over a documented HTTP API. Persistence is
now implemented end to end, but nobody has pointed it at a real running Postgres in this repo —
same "implemented, unverified live" shape as the reference provider in Phase 3.

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
      **Not yet run against a live Postgres** — this sandbox has none. What stands in for that:
      `tests/unit/test_db_store.py` exercises `PostgresStore`'s full read/write surface (decisions,
      traces, tasks, task versioning, benchmarks) against ephemeral SQLite via a JSON/JSONB column
      variant in `db.py`, which is a structural check on the row↔pydantic mapping, not a
      substitute for verifying the migration against real Postgres before depending on it.
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

React + TypeScript app under `apps/dashboard/`. All seven pages are scaffolded and build.

- [~] Overview page — exists
- [~] Task list and task editor — exists
- [~] Playground — exists
- [~] Trace viewer — exists (`TraceTimeline` component)
- [~] Benchmark comparison page — exists
- [~] Settings and policy views — exist
- [ ] **Verify that all displayed metrics are sourced from real stored runs** — Phase 4 now has a
      persistence path (`JEVKIT_API_PERSISTENCE=postgres`); this item is blocked on actually
      running the API against a live Postgres with that flag set and confirming the dashboard's
      pages reflect it, which hasn't happened yet — no Postgres instance in this environment

---

## MVP acceptance criteria (plan §21)

- [x] Jev integration works against the verified current API
- [x] Supported decision types are represented through typed task objects
- [x] Provider errors and invalid outputs are handled predictably
- [x] Retry and fallback limits are enforced
- [x] Every execution can produce a trace
- [x] A benchmark can run on a labeled dataset
- [~] Metrics are reproducible and their methodology is documented — methodology yes; a
      persistence path now exists (Phase 4) but is opt-in and unverified live, so in practice
      reproducibility today is still by re-running, not by a confirmed durable record
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
3. ~~Wire PostgreSQL persistence + migrations~~ **Implemented 2026-09-21** (Phase 4) —
   `apps/api/db_store.py`, `migrations/`, opt-in via `JEVKIT_API_PERSISTENCE=postgres`. What's
   left here: run `alembic upgrade head` and the API against a real Postgres instance (this
   environment has none) to confirm it live, the way Phase 1 verified Jev live; only then does
   Phase 6's "real stored runs" requirement and full MVP reproducibility actually close out.
4. ~~Verify a clean install in a fresh venv~~ **Done 2026-09-21** — it did surface packaging
   gaps: a repo URL that 404s, baked into the release metadata, plus stale quickstart and README
   claims. All fixed; see Phase 5.
5. ~~Publish benchmark results and tag v0.1~~ **Done 2026-09-21** — single-provider results in
   [`docs/benchmark-results.md`](docs/benchmark-results.md), `v0.1.0` tagged locally.

**What's actually left**, now that Phases 1-5 are closed:

6. **Push the tag and decide on PyPI.** `v0.1.0` exists only in this clone.
7. **Run the API against a live Postgres** — the last thing standing between Phase 6 and "metrics
   come from real stored runs", and between the MVP criteria and genuine reproducibility.
8. **Get the §2.3(b) legal answer** if a head-to-head comparison is ever wanted. Publishing
   single-provider results sidesteps the question; it does not settle it.

Smaller loose ends: `usage.cost_usd` is never populated; `429`/`5xx` handling has never met a
real response for either provider (deliberately, for Jev — see above; the reference provider's
429/5xx handling is written and mocked-tested only, for the same reason plus the more basic one
that no live key has been supplied at all); timeout handling has met a real response, live, for
Jev only; the labeled datasets are synthetic and still small (35 rows total, up from 18), which is
too thin to claim anything about accuracy; PostgreSQL persistence is implemented and tested against
SQLite but has never been run against a live Postgres in this repo.

---

## Conventions worth keeping

- `make check` (or `ruff check . && ruff format --check . && mypy packages apps && pytest`) is
  what CI runs. Keep it green.
- Anything Jev-specific belongs in `packages/jevkit/providers/jev/`. The engine, policies,
  validation and benchmarks must not learn the wire format.
- A metric that does not apply reports **nothing**, never `0.0`.
- Datasets carry a `methodology` field and a `synthetic` flag. Tests enforce both.
- Secrets never reach a trace, a log or an exception message. There are tests for this.
