"""The JevKit CLI playground (PLAN.md section 20, phase 5).

    jevkit version
    jevkit providers
    jevkit decide --task examples/support-routing/task.json --state '{"message": "..."}'
    jevkit decide --task ... --state ... --dry-run     # no network, no spend
    jevkit bench   --task ... --dataset ... --provider jev

Requires the `cli` extra: ``pip install "jevkit[cli]"``.
"""

from __future__ import annotations

import asyncio
import json
from pathlib import Path
from typing import Any

try:
    import typer
    from rich.console import Console
    from rich.table import Table
except ModuleNotFoundError as exc:  # pragma: no cover - import guard
    raise SystemExit(
        "The JevKit CLI needs the 'cli' extra. Install it with:\n    pip install \"jevkit[cli]\""
    ) from exc

from jevkit.__about__ import __version__
from jevkit.decisions.task import DecisionTask
from jevkit.policies.policy import DecisionPolicy
from jevkit.providers.registry import build_provider, known_providers
from jevkit.tracing.trace import DecisionTrace

app = typer.Typer(
    name="jevkit",
    help="Run typed decisions against Jev and inspect what happened.",
    no_args_is_help=True,
    add_completion=False,
)
console = Console()


def _load_task(path: Path) -> DecisionTask:
    return DecisionTask.model_validate_json(path.read_text(encoding="utf-8"))


def _load_state(raw: str) -> dict[str, Any]:
    candidate = Path(raw)
    text = candidate.read_text(encoding="utf-8") if candidate.is_file() else raw
    state = json.loads(text)
    if not isinstance(state, dict):
        raise typer.BadParameter("--state must be a JSON object (or a path to one)")
    return state


def _print_trace(trace: DecisionTrace) -> None:
    console.print(f"\n[dim]trace {trace.trace_id}[/dim]")
    for line in trace.summary():
        console.print(f"  [dim]{line}[/dim]")


@app.command()
def version() -> None:
    """Print the installed JevKit version."""
    console.print(f"jevkit {__version__}")


@app.command()
def providers() -> None:
    """List registered provider adapters."""
    table = Table("provider", "notes")
    for name in known_providers():
        note = "primary provider" if name == "jev" else ""
        if name == "reference":
            note = "reference/fallback; OpenAI-compatible, needs JEVKIT_FALLBACK_API_KEY"
        if name == "static":
            note = "deterministic stub; never benchmark this as a model"
        table.add_row(name, note)
    console.print(table)


@app.command()
def decide(
    task_path: Path = typer.Option(..., "--task", "-t", exists=True, help="Task definition JSON."),
    state: str = typer.Option(..., "--state", "-s", help="Input JSON, or a path to a JSON file."),
    provider: str = typer.Option("jev", "--provider", "-p", help="Provider to call."),
    timeout: float = typer.Option(10.0, "--timeout", help="Per-attempt timeout in seconds."),
    max_retries: int = typer.Option(1, "--max-retries", min=0, max=5),
    dry_run: bool = typer.Option(
        False, "--dry-run", help="Use the static stub provider: no network, no spend."
    ),
    show_trace: bool = typer.Option(True, "--trace/--no-trace", help="Print the execution trace."),
) -> None:
    """Run one decision and print the normalized result."""
    from jevkit.client.client import DecisionClient

    task = _load_task(task_path)
    provider_name = "static" if dry_run else provider
    policy = DecisionPolicy(
        primary_provider=provider_name, timeout_seconds=timeout, max_retries=max_retries
    )

    async def run() -> None:
        async with DecisionClient(provider=build_provider(provider_name), policy=policy) as client:
            result, trace = await client.decide_with_trace(state=_load_state(state), task=task)

        console.print_json(json.dumps(result.decisions, default=str))
        status = (
            f"[bold]{result.execution_status.value}[/bold]"
            f"  provider={result.provider}"
            f"  attempts={result.attempts}"
        )
        if result.latency_ms is not None:
            status += f"  latency={result.latency_ms:.0f}ms"
        console.print(status)
        if result.validation_failures:
            console.print("[red]validation failures:[/red]")
            for failure in result.validation_failures:
                console.print(f"  - {failure}")
        if show_trace:
            _print_trace(trace)

    asyncio.run(run())


@app.command()
def bench(
    task_path: Path = typer.Option(..., "--task", "-t", exists=True),
    dataset_path: Path = typer.Option(..., "--dataset", "-d", exists=True),
    provider: str = typer.Option("jev", "--provider", "-p"),
    concurrency: int = typer.Option(4, "--concurrency", "-c", min=1, max=32),
    output: Path | None = typer.Option(None, "--out", "-o", help="Write the JSON report here."),
    dry_run: bool = typer.Option(False, "--dry-run", help="Use the static stub provider."),
) -> None:
    """Run a task over a labeled dataset and print measured metrics."""
    from jevkit.benchmarks.dataset import BenchmarkDataset
    from jevkit.benchmarks.runner import BenchmarkReport, run_benchmark

    task = _load_task(task_path)
    dataset = BenchmarkDataset.from_jsonl(dataset_path)
    provider_name = "static" if dry_run else provider

    async def run() -> BenchmarkReport:
        adapter = build_provider(provider_name)
        try:
            return await run_benchmark(
                task=task, dataset=dataset, provider=adapter, concurrency=concurrency
            )
        finally:
            await adapter.aclose()

    report = asyncio.run(run())

    for line in report.summary_lines():
        console.print(line)
    if dry_run:
        console.print(
            "\n[yellow]Dry run: these numbers come from a stub, not a model. "
            "Do not report them as results.[/yellow]"
        )
    if output is not None:
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(report.model_dump_json(indent=2), encoding="utf-8")
        console.print(f"\n[dim]report written to {output}[/dim]")


def main() -> None:
    """Console-script entry point."""
    app()


if __name__ == "__main__":
    main()
