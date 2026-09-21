# Changelog

All notable changes to JevKit are documented here.

The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and this project
adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [0.1.0] - 2026-09-21

First release. A typed decision layer for Jev: define a task, run it, validate the output, apply
a policy, and measure what happened.

### Added

- Core domain types: `DecisionTask`, question types (`Choice`, `Selection`, `Noul`, `Score`,
  `Scalar`, `Rank`), `DecisionResult`, `DecisionTrace`.
- `DecisionEngine` implementing the execution lifecycle with bounded retries and controlled
  fallback, and `DecisionClient` as the public async SDK surface.
- `DecisionPolicy` with explicit acceptance, retry, fallback and review rules.
- Output validation for every question type, and typed errors.
- **Jev provider adapter, verified against the live API** (`jev-1.13.0`, 2026-09-21). Jev's three
  question types (`noul`, `choice`, `score`) are supported; `Selection`, `Scalar` and `Rank` are
  rejected with `TaskDefinitionError` before a request is made, because the API does not
  implement them.
- **Reference/fallback provider** (`packages/jevkit/providers/reference/`) calling an
  OpenAI-compatible Chat Completions API with JSON-schema structured outputs. Supports JevKit's
  full question vocabulary. Tested against a mocked transport only.
- Provider registry and a deterministic `StaticProvider` for offline testing.
- Benchmark dataset format, metrics (accuracy, P/R/F1, Brier, calibration error, latency
  percentiles, coverage, invalid-response and fallback rates) and an async runner.
- CLI: `jevkit version | providers | decide | bench`, with `--dry-run` throughout.
- FastAPI service: decisions, traces, tasks, benchmarks, health, API-key auth, OpenAPI docs.
- **PostgreSQL persistence and Alembic migrations** for the API, opt-in via
  `JEVKIT_API_PERSISTENCE=postgres`. Defaults to in-memory so tests and local development need no
  database.
- React + TypeScript dashboard shell with API client and trace viewer.
- Three worked examples with labeled datasets and documented methodology (35 rows total), all of
  which run live end to end.
- **Published benchmark results** ([`docs/benchmark-results.md`](docs/benchmark-results.md)):
  single-provider measurements on the shipped datasets, with raw per-example reports.
- Test suite (unit, integration, benchmark) running fully offline, plus `scripts/verify_jev_api.py`
  and `scripts/verify_timeout_behavior.py` for live verification.

### Fixed

- `BenchmarkReport.model` was always `null`: the runner looked for a `__model__` key inside the
  decisions map, which no provider sets. Reports now record the provider's model identifier,
  which `docs/benchmarking.md` requires before any number may be published.

### Known limitations

These are stated plainly rather than left for you to discover:

- **PostgreSQL persistence has never been run against a live database.** It is implemented and
  tested against ephemeral SQLite, which checks the row↔model mapping but not the migration
  against real PostgreSQL. Verify before depending on it.
- **The reference provider has never been run against a live account.** Its mapping and error
  handling are mock-tested only; nothing in this repo has spent against it.
- **`429` and `5xx` handling has never met a real response** for either provider. Forcing them
  against Jev would mean deliberately exceeding the account's Usage Limits, which the Master
  Customer Agreement prohibits. Handling is doc-written and mock-tested, by policy.
- **The labeled datasets are synthetic and small** (35 rows). They do not support a general
  accuracy claim, and `docs/benchmark-results.md` says so explicitly.
- **No head-to-head benchmark is published.** MCA §2.3(b) bears on public "Jev vs. X"
  comparisons; see "Terms of use" in `docs/jev-api-notes.md`. This is unresolved and needs a
  legal answer, not an engineering one.
- `usage.cost_usd` is never populated — JevKit does not hardcode provider pricing, because a
  stale price is worse than no price.
- Dashboard pages need a live Postgres to show real runs; until then they show in-memory data.

[Unreleased]: https://github.com/Ernosto0/JevKit/compare/v0.1.0...HEAD
[0.1.0]: https://github.com/Ernosto0/JevKit/releases/tag/v0.1.0
