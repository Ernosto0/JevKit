# Changelog

All notable changes to JevKit are documented here.

The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and this project
adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added

- Project scaffolding for the v0.1 decision engine.
- Core domain types: `DecisionTask`, question types (`Choice`, `Selection`, `Noul`, `Scalar`,
  `Rank`), `DecisionResult`, `DecisionTrace`.
- `DecisionEngine` implementing the execution lifecycle with bounded retries and controlled
  fallback.
- `DecisionPolicy` with explicit acceptance, retry, fallback and review rules.
- Output validation for every question type.
- Provider abstraction, a provider registry, and a deterministic `StaticProvider` for offline
  testing.
- Jev adapter with typed error mapping. **Its wire schema is provisional and unverified.**
- Benchmark dataset format, metrics (accuracy, P/R/F1, Brier, calibration error, latency
  percentiles) and an async runner.
- CLI: `version`, `providers`, `decide`, `bench`.
- FastAPI service: decisions, traces, tasks, benchmarks, health.
- React + TypeScript dashboard shell with API client and trace viewer.
- Three worked examples with labeled datasets and documented methodology.
- Test suite (unit, integration, benchmark) running fully offline.

### Known limitations

- The Jev request/response mapping has not been verified against the official API. Real calls
  are not expected to work until roadmap phase 1 is complete.
- The API service persists to an in-memory store; PostgreSQL wiring is roadmap phase 4.
- Benchmark execution over the HTTP API is queued but not yet dispatched.
- Dashboard pages that need persisted runs show empty states rather than data.

[Unreleased]: https://github.com/cinaraksoy/jevkit/commits/main
