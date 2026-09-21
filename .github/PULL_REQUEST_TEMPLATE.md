## What this changes

<!-- And why. Reference the roadmap phase if relevant. -->

## Type

- [ ] Bug fix
- [ ] New feature
- [ ] Breaking change
- [ ] Documentation
- [ ] Jev API verification (phase 1)

## Checklist

- [ ] `pytest` passes
- [ ] `ruff check .` and `ruff format --check .` pass
- [ ] `mypy` passes
- [ ] Dashboard changes: `npm run typecheck && npm run lint && npm run build` pass
- [ ] New tests cover the change, and they run offline
- [ ] Docs updated if behavior changed

## Project invariants

Confirm this change does not break any of these:

- [ ] No unbounded retry, fallback or request loop
- [ ] No provider-specific behavior outside its adapter
- [ ] No credential in a log, trace, result or error message
- [ ] No metric reported as `0.0` when it was not measured
- [ ] No code path where model output triggers a privileged action
