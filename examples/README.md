# Examples

Each folder holds a `task.json`, a runnable `run.py`, a small labeled `dataset.jsonl`, and a
`dataset.meta.json` documenting how the labels were made.

| Example | What it decides |
|---|---|
| [`support-routing/`](support-routing/) | Department and urgency for an inbound support message |
| [`agent-routing/`](agent-routing/) | Which capability handles a task — and what low confidence does |
| [`requirement-checks/`](requirement-checks/) | Whether an artifact satisfies an explicit checklist |

`agent-routing` shows `on_low_confidence=REVIEW` routing an uncertain answer to a human.
`requirement-checks` shows a model check running *alongside* deterministic checks, not instead
of them.

## Run one

```bash
# No credentials and no spend: uses the deterministic stub provider.
python examples/support-routing/run.py --dry-run
python examples/agent-routing/run.py --dry-run
python examples/requirement-checks/run.py --dry-run

# Against the real provider (requires JEV_API_KEY in .env).
python examples/support-routing/run.py

# Same task through the CLI, with the execution trace.
jevkit decide --task examples/support-routing/task.json \
  --state '{"message": "I was charged twice."}' --dry-run
```

## Benchmark one

```bash
jevkit bench --task examples/support-routing/task.json \
  --dataset examples/support-routing/dataset.jsonl --provider jev
```

## About these datasets

They are **synthetic, hand-authored, and tiny** — six to eight examples each.
They exist to make the pipeline runnable end to end and to give the metrics
code something to compute. They are not large or representative enough to
support any claim about a provider's accuracy, and numbers produced from them
must never be published as benchmark results. See
[`docs/benchmarking.md`](../docs/benchmarking.md).
