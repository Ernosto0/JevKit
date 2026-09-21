"""Check an artifact against an explicit requirement checklist.

    python examples/requirement-checks/run.py              # needs JEV_API_KEY
    python examples/requirement-checks/run.py --dry-run    # stub provider, no spend

Note the deterministic pre-check below: a model-based check complements code
you can verify, it does not replace it.
"""

from __future__ import annotations

import argparse
import asyncio
import json
from pathlib import Path

from jevkit import DecisionClient, DecisionPolicy, DecisionTask
from jevkit.providers import StaticProvider

TASK_PATH = Path(__file__).parent / "task.json"

REQUIREMENTS = ["has_title", "has_summary", "cites_sources", "under_word_limit"]

ARTIFACT = """Revenue grew a lot this quarter."""


def deterministic_checks(artifact: str) -> dict[str, bool]:
    """The requirements that can be checked without a model. Always run these."""
    return {
        "has_title": artifact.lstrip().startswith("#"),
        "under_word_limit": len(artifact.split()) <= 200,
    }


async def main(dry_run: bool) -> None:
    task = DecisionTask.model_validate_json(TASK_PATH.read_text(encoding="utf-8"))

    if dry_run:
        client = DecisionClient(
            provider=StaticProvider(
                {
                    "passes": 0.08,
                    "missing_requirements": ["has_title", "cites_sources"],
                    "review_depth": 0.6,
                }
            ),
            policy=DecisionPolicy(primary_provider="static"),
        )
    else:
        client = DecisionClient.from_env()

    async with client:
        result = await client.decide(
            state={"artifact": ARTIFACT, "requirements": REQUIREMENTS}, task=task
        )

    checked = deterministic_checks(ARTIFACT)
    print("deterministic:", json.dumps(checked, indent=2))
    print("model:        ", json.dumps(result.decisions, indent=2))
    print("status:       ", result.execution_status.value)

    if not result.accepted:
        print("\n-> no usable model result; deterministic checks still stand")
        return

    # Where the two disagree, trust the deterministic check and flag the gap.
    model_missing = set(result["missing_requirements"])
    for requirement, passed in checked.items():
        model_says_missing = requirement in model_missing
        if passed and model_says_missing:
            print(f"\n!  {requirement}: code says it passes, model called it missing")
        elif not passed and not model_says_missing:
            print(f"\n!  {requirement}: code says it fails, model did not flag it")

    print(f"\n-> application would request review depth {result['review_depth']}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dry-run", action="store_true", help="Use the stub provider.")
    asyncio.run(main(parser.parse_args().dry_run))
