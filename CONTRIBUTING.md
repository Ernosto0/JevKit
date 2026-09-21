# Contributing to JevKit

Thanks for your interest. JevKit is pre-alpha, so the most valuable contributions right now are
the ones that replace guesses with verified facts.

## The highest-value contribution today

**Phase 1: verify the Jev API.**

[`packages/jevkit/providers/jev/schema.py`](packages/jevkit/providers/jev/schema.py) is written
against a *guessed* wire format. If you have access to the official Jev API documentation, the
most useful thing you can do is:

1. Confirm the real endpoint, auth scheme, request body and response body.
2. Correct `build_request_payload` and `parse_response_payload`.
3. Record which question types are actually supported, and how.
4. Set `SCHEMA_VERIFIED = True` and note the API version you verified against.
5. Add tests covering the real response shapes, including error bodies.

Everything Jev-specific is confined to that one module on purpose, so this change should not
touch the engine, policies or benchmarks.

## Development setup

```bash
python -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
pip install -r requirements-dev.txt

pytest                             # offline; no credentials needed
```

Dashboard:

```bash
cd apps/dashboard
npm install
npm run dev
```

## Before you open a pull request

```bash
ruff check .
ruff format --check .
mypy
pytest

cd apps/dashboard && npm run typecheck && npm run lint && npm run build
```

CI runs all of the above.

## Guidelines

**Tests must run offline.** Nothing in `tests/unit` may touch the network. Use
`StaticProvider` or `respx`. Tests that need real credentials belong in `tests/integration` and
must be marked `@pytest.mark.integration` and skipped when credentials are absent.

**Keep provider code in its adapter.** If a change makes the engine, policies, validation or
benchmarks aware of a specific vendor's behavior, it belongs in that vendor's adapter instead.

**Never report a metric you did not measure.** Metric functions return `None` when they do not
apply, and the report and dashboard render that as a dash. A metric that silently reports `0.0`
for something it could not compute is a bug, not a rounding detail.

**Bound everything.** Retries, timeouts, request size and concurrency all have explicit limits.
A change that introduces an unbounded loop or an uncapped retry will be rejected.

**Never act on model output.** A decision is a recommendation. Authorization and execution stay
with the calling application. Do not add code paths where a model result triggers a privileged
action directly.

**Secrets never leave the server.** Do not log, trace, serialize or return API keys. Error
messages must not echo credentials — there is a test for this, keep it passing.

**Traces default to metadata only.** Input capture stays off unless explicitly enabled.

## Adding a provider adapter

1. Subclass `ModelProvider` in `packages/jevkit/providers/<name>/`.
2. Raise the typed errors from `jevkit.errors`; never leak vendor exceptions.
3. Do not retry internally — retries belong to the policy engine.
4. Honour `request.timeout_seconds`.
5. Register it in `packages/jevkit/providers/registry.py`.
6. Add tests using `respx` against a mocked transport.

## Adding a benchmark dataset

Every dataset needs a `.meta.json` with a `methodology` field that states, honestly:

- how the labels were produced,
- whether the examples are synthetic or real,
- where the labels are ambiguous,
- what the dataset does *not* support concluding.

`tests/unit/test_examples.py` checks that every shipped dataset has a methodology and that its
labels are valid answers to its task. Keep it passing.

## Commit and PR style

- One logical change per pull request.
- Explain *why*, not just what.
- Reference the roadmap phase where relevant.
- If you change behavior, update the tests and the docs in the same PR.

## Reporting issues

Use the issue templates. For anything security-related, see
[`SECURITY.md`](SECURITY.md) — please do not open a public issue.

## Code of conduct

By participating you agree to the [Code of Conduct](CODE_OF_CONDUCT.md).

## License

Contributions are accepted under the [MIT License](LICENSE).
