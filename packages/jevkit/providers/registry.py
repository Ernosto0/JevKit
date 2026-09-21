"""Name -> provider lookup, so policies can reference providers by string."""

from __future__ import annotations

from collections.abc import Callable

from jevkit.errors import ConfigurationError
from jevkit.providers.base import ModelProvider

__all__ = ["build_provider", "known_providers", "register_provider"]

_FACTORIES: dict[str, Callable[..., ModelProvider]] = {}


def register_provider(name: str, factory: Callable[..., ModelProvider]) -> None:
    """Register a provider factory under `name`, replacing any existing entry."""
    _FACTORIES[name] = factory


def known_providers() -> list[str]:
    return sorted(_FACTORIES)


def build_provider(name: str, **kwargs: object) -> ModelProvider:
    """Instantiate a registered provider.

    Raises:
        ConfigurationError: if no provider is registered under `name`.
    """
    try:
        factory = _FACTORIES[name]
    except KeyError:
        raise ConfigurationError(
            f"Unknown provider {name!r}. Registered providers: {known_providers()}"
        ) from None
    return factory(**kwargs)


def _register_builtins() -> None:
    from jevkit.providers.jev.provider import JevProvider
    from jevkit.providers.reference.provider import ReferenceProvider
    from jevkit.providers.static import StaticProvider

    register_provider("jev", JevProvider)
    register_provider("reference", ReferenceProvider)
    register_provider("static", StaticProvider)


_register_builtins()
