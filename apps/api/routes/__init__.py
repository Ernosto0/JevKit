"""HTTP routes. Each module owns one resource group."""

from apps.api.routes import benchmarks, decisions, health, tasks

__all__ = ["benchmarks", "decisions", "health", "tasks"]
