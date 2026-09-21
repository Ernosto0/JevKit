"""Labeled benchmark datasets (PLAN.md sections 12-13).

A dataset is a list of examples, each pairing an input `state` with the
expected answers. Datasets are stored as JSONL so they stay diffable and
inspectable; how the labels were produced belongs in the accompanying
`methodology` field, not in a commit message.
"""

from __future__ import annotations

import json
from collections.abc import Iterator
from pathlib import Path
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

__all__ = ["BenchmarkDataset", "DatasetExample"]


class DatasetExample(BaseModel):
    """One labeled example."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    id: str
    state: dict[str, Any]
    expected: dict[str, Any] = Field(
        description="Expected answer per question key. Omit a key to skip scoring it."
    )
    notes: str | None = Field(
        default=None, description="Where the label came from, or why it is ambiguous."
    )


class BenchmarkDataset(BaseModel):
    """A named, versioned set of labeled examples."""

    model_config = ConfigDict(extra="forbid")

    name: str
    version: str = "1"
    description: str | None = None
    methodology: str | None = Field(
        default=None,
        description="How labels were created and what their known limitations are.",
    )
    synthetic: bool = Field(
        default=True,
        description="True when examples are authored rather than sampled from real traffic.",
    )
    examples: list[DatasetExample] = Field(default_factory=list)

    @property
    def ref(self) -> str:
        return f"{self.name}@{self.version}"

    def __len__(self) -> int:
        return len(self.examples)

    def __iter__(self) -> Iterator[DatasetExample]:  # type: ignore[override]
        return iter(self.examples)

    @classmethod
    def from_jsonl(cls, path: str | Path, **meta: Any) -> BenchmarkDataset:
        """Load examples from a JSONL file, one `DatasetExample` per line.

        Metadata (name, version, methodology...) is read from a sibling
        `<name>.meta.json` when present, and may be overridden via `**meta`.
        """
        source = Path(path)
        meta_path = source.with_suffix(".meta.json")
        metadata: dict[str, Any] = {"name": source.stem}
        if meta_path.exists():
            metadata.update(json.loads(meta_path.read_text(encoding="utf-8")))
        metadata.update(meta)

        examples = [
            DatasetExample.model_validate_json(line)
            for line in source.read_text(encoding="utf-8").splitlines()
            if line.strip()
        ]
        return cls(examples=examples, **metadata)

    def to_jsonl(self, path: str | Path) -> None:
        """Write examples to JSONL and metadata to the sibling meta file."""
        target = Path(path)
        target.parent.mkdir(parents=True, exist_ok=True)
        with target.open("w", encoding="utf-8") as fh:
            for example in self.examples:
                fh.write(example.model_dump_json() + "\n")

        metadata = self.model_dump(mode="json", exclude={"examples"})
        target.with_suffix(".meta.json").write_text(
            json.dumps(metadata, indent=2) + "\n", encoding="utf-8"
        )
