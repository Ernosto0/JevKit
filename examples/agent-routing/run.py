"""Pick which capability should handle a task, and honour low confidence.

    python examples/agent-routing/run.py              # needs JEV_API_KEY
    python examples/agent-routing/run.py --dry-run    # stub provider, no spend

This example shows the point of `on_low_confidence`: an uncertain route is sent
to review instead of being acted on.
"""

from __future__ import annotations

import argparse
import asyncio
import json
from pathlib import Path

from jevkit import DecisionClient, DecisionPolicy, DecisionTask, ExecutionStatus, OnFailure
from jevkit.providers import StaticProvider

TASK_PATH = Path(__file__).parent / "task.json"

ROUTES = ["search", "code", "data_analysis", "human"]
TASK_DESCRIPTION = "Look into the thing we discussed yesterday."

# Route only when the provider is reasonably sure; otherwise ask a person.
POLICY = DecisionPolicy(
    timeout_seconds=10.0,
    max_retries=1,
    min_confidence=0.6,
    on_low_confidence=OnFailure.REVIEW,
)


async def main(dry_run: bool) -> None:
    task = DecisionTask.model_validate_json(TASK_PATH.read_text(encoding="utf-8"))

    if dry_run:
        # A deliberately unsure answer, to exercise the review path.
        policy = POLICY.model_copy(update={"primary_provider": "static"})
        client = DecisionClient(
            provider=StaticProvider(
                {"route": "search", "confident_enough_to_act": 0.35},
                confidence={"route": 0.41, "confident_enough_to_act": 0.35},
            ),
            policy=policy,
        )
    else:
        policy = POLICY
        client = DecisionClient.from_env(policy=policy)

    async with client:
        result = await client.decide(
            state={"task_description": TASK_DESCRIPTION, "available_routes": ROUTES},
            task=task,
        )

    print("decisions:", json.dumps(result.decisions, indent=2))
    print("status:   ", result.execution_status.value)

    # The route is a recommendation. The application still checks permissions.
    if result.execution_status is ExecutionStatus.NEEDS_REVIEW:
        print("\n-> low confidence: application would queue this for a human")
    elif result.accepted:
        print(f"\n-> application would check permissions, then dispatch to {result['route']!r}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dry-run", action="store_true", help="Use the stub provider.")
    asyncio.run(main(parser.parse_args().dry_run))
