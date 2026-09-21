# Quickstart

## 1. Install

```bash
git clone https://github.com/cinaraksoy/jevkit.git
cd jevkit

python -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate

pip install -e ".[cli]"
```

Python 3.11 or newer.

## 2. Run something without credentials

The stub provider makes the whole pipeline runnable offline:

```bash
python examples/support-routing/run.py --dry-run
```

You should see decisions, a status, and a trace with one line per lifecycle stage.

## 3. Configure Jev

```bash
cp .env.example .env
```

Set `JEV_API_KEY`, and confirm `JEV_BASE_URL` against the official documentation — the default
in `.env.example` is a placeholder, not a real endpoint.

> Real calls are not expected to succeed until the wire mapping in
> `packages/jevkit/providers/jev/schema.py` has been verified. See
> [jev-api-notes.md](jev-api-notes.md).

## 4. Your first decision

```python
import asyncio
from jevkit import Choice, DecisionClient, Noul


async def main() -> None:
    async with DecisionClient.from_env() as client:
        result, trace = await client.decide_with_trace(
            state={"message": "I was charged twice for my subscription."},
            questions={
                "department": Choice(options=["billing", "technical", "account", "other"]),
                "urgent": Noul(instructions="Is this issue urgent?"),
            },
        )

    print(result.decisions)
    print(result.execution_status.value)
    for line in trace.summary():
        print(line)


asyncio.run(main())
```

## 5. Reuse a task

Ad-hoc questions are fine for experiments, but anything you want to benchmark or store should
be a named, versioned task — the task ref is what makes a run identifiable later.

```python
from pathlib import Path
from jevkit import DecisionTask

task = DecisionTask.model_validate_json(Path("examples/support-routing/task.json").read_text())

result = await client.decide(state={"message": "..."}, task=task)
```

## 6. Add a policy

```python
from jevkit import DecisionPolicy, OnFailure

policy = DecisionPolicy(
    primary_provider="jev",
    timeout_seconds=8.0,
    max_retries=1,
    on_invalid_response=OnFailure.FALLBACK,
    on_low_confidence=OnFailure.REVIEW,
    min_confidence=0.7,
)

result = await client.decide(state=..., task=task, policy=policy)

if result.execution_status is ExecutionStatus.NEEDS_REVIEW:
    send_to_human_queue(result)
```

## 7. Benchmark it

```bash
jevkit bench --task examples/support-routing/task.json \
             --dataset examples/support-routing/dataset.jsonl \
             --provider jev --out reports/jev.json
```

Read [benchmarking.md](benchmarking.md) before quoting any number this produces.

## 8. Run the API and dashboard

```bash
uvicorn apps.api.main:app --reload       # http://localhost:8000/docs

cd apps/dashboard && npm install && npm run dev    # http://localhost:5173
```

## Reading a result

| Field | Meaning |
|---|---|
| `decisions` | The answer per question key |
| `confidence` | Provider-reported probabilities. **Absent ≠ low** — it means none was reported |
| `execution_status` | `accepted`, `fallback_accepted`, `needs_review`, `rejected`, `failed` |
| `validation_status` | Whether the answer satisfied the task's questions |
| `attempts` | How many provider calls it took |
| `used_fallback` | Whether the fallback provider produced this |
| `trace_id` | Look the full trace up by this |

`result.accepted` is true only for `accepted` and `fallback_accepted`. `needs_review` is not an
acceptance.
