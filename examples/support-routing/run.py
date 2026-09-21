"""Route a support message, then inspect the trace.

python examples/support-routing/run.py              # needs JEV_API_KEY
python examples/support-routing/run.py --dry-run    # stub provider, no spend
"""

from __future__ import annotations

import argparse
import asyncio
import json
from pathlib import Path

from jevkit import DecisionClient, DecisionPolicy, DecisionTask
from jevkit.providers import StaticProvider

TASK_PATH = Path(__file__).parent / "task.json"

MESSAGE = "I was charged twice for my subscription this month. Please refund the duplicate."


async def main(dry_run: bool) -> None:
    task = DecisionTask.model_validate_json(TASK_PATH.read_text(encoding="utf-8"))

    if dry_run:
        client = DecisionClient(
            provider=StaticProvider(
                {"department": "billing", "urgent": 0.82, "needs_escalation": 0.11},
                confidence={"urgent": 0.82, "needs_escalation": 0.89},
            ),
            policy=DecisionPolicy(primary_provider="static"),
        )
    else:
        client = DecisionClient.from_env()

    async with client:
        result, trace = await client.decide_with_trace(state={"message": MESSAGE}, task=task)

    print("decisions:", json.dumps(result.decisions, indent=2))
    print("status:   ", result.execution_status.value)
    print("provider: ", result.provider)
    print("\ntrace:")
    for line in trace.summary():
        print(" ", line)

    # The decision is a recommendation. The application still owns the routing.
    if result.accepted and result.decisions["department"] == "billing":
        print("\n-> application would route this ticket to the billing queue")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dry-run", action="store_true", help="Use the stub provider.")
    asyncio.run(main(parser.parse_args().dry_run))
