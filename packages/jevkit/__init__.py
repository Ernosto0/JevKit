"""JevKit: an open-source, Jev-first decision layer for AI applications.

JevKit is an independent open-source project. Jev is developed by TypeSafe AI;
JevKit is not an official client and carries no endorsement.

Quick start::

    import asyncio
    from jevkit import Choice, DecisionClient, Noul

    async def main() -> None:
        async with DecisionClient.from_env() as client:
            result = await client.decide(
                state={"message": "I was charged twice for my subscription."},
                questions={
                    "department": Choice(options=["billing", "technical", "account", "other"]),
                    "urgent": Noul(instructions="Is this issue urgent?"),
                },
            )
            print(result.decisions)

    asyncio.run(main())
"""

from jevkit.__about__ import __version__
from jevkit.client import DecisionClient, DecisionEngine
from jevkit.config import JevKitSettings, get_settings
from jevkit.decisions import (
    Choice,
    DecisionResult,
    DecisionTask,
    ExecutionStatus,
    Noul,
    Question,
    Rank,
    Scalar,
    Score,
    Selection,
    ValidationStatus,
)
from jevkit.errors import (
    ConfigurationError,
    InputValidationError,
    JevKitError,
    OutputValidationError,
    PolicyError,
    ProviderError,
    ProviderTimeoutError,
    TaskDefinitionError,
)
from jevkit.policies import DecisionPolicy, OnFailure
from jevkit.providers import JevProvider, ModelProvider, StaticProvider
from jevkit.tracing import DecisionTrace, TraceStage

__all__ = [
    "Choice",
    "ConfigurationError",
    "DecisionClient",
    "DecisionEngine",
    "DecisionPolicy",
    "DecisionResult",
    "DecisionTask",
    "DecisionTrace",
    "ExecutionStatus",
    "InputValidationError",
    "JevKitError",
    "JevKitSettings",
    "JevProvider",
    "ModelProvider",
    "Noul",
    "OnFailure",
    "OutputValidationError",
    "PolicyError",
    "ProviderError",
    "ProviderTimeoutError",
    "Question",
    "Rank",
    "Scalar",
    "Score",
    "Selection",
    "StaticProvider",
    "TaskDefinitionError",
    "TraceStage",
    "ValidationStatus",
    "__version__",
    "get_settings",
]
