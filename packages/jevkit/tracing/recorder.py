"""Trace sinks.

The default sink discards traces, so the SDK never writes to disk unless asked.
A JSONL sink is provided for local development; the API service persists traces
to PostgreSQL instead (PLAN.md §15).
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Protocol

from jevkit.tracing.trace import DecisionTrace

__all__ = ["JsonlTraceRecorder", "NullTraceRecorder", "TraceRecorder"]


class TraceRecorder(Protocol):
    """Anything that can persist a finished trace."""

    def save(self, trace: DecisionTrace) -> None: ...


class NullTraceRecorder:
    """Keeps traces in memory only. The default."""

    def save(self, trace: DecisionTrace) -> None:
        return None


class JsonlTraceRecorder:
    """Appends one JSON object per trace to a local file.

    Intended for local development. Retention and redaction are the caller's
    responsibility here -- see PLAN.md §15 before pointing this at real data.
    """

    def __init__(self, path: str | Path = ".jevkit/traces/traces.jsonl") -> None:
        self.path = Path(path)

    def save(self, trace: DecisionTrace) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.path.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(trace.model_dump(mode="json"), ensure_ascii=False) + "\n")
