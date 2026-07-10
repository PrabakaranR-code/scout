"""Adapter registry.

Adapters register themselves by being listed in ``_ADAPTER_MODULES``; the
registry imports them lazily so a broken optional source cannot break the
package import.
"""

from __future__ import annotations

import importlib
import inspect
import logging

from scout.adapters.base import BaseAdapter

logger = logging.getLogger("scout")

# Module paths scanned for BaseAdapter subclasses, in presentation order.
_ADAPTER_MODULES: tuple[str, ...] = ()

_registry: dict[str, type[BaseAdapter]] | None = None


def all_adapters() -> dict[str, type[BaseAdapter]]:
    """Name -> adapter class for every shipped adapter."""
    global _registry
    if _registry is None:
        _registry = {}
        for module_path in _ADAPTER_MODULES:
            module = importlib.import_module(module_path)
            for _, obj in inspect.getmembers(module, inspect.isclass):
                if (
                    issubclass(obj, BaseAdapter)
                    and obj is not BaseAdapter
                    and obj.__module__ == module_path
                    and getattr(obj, "name", None)
                ):
                    _registry[obj.name] = obj
    return dict(_registry)


def get_adapter(name: str) -> type[BaseAdapter]:
    """Look up one adapter class by name."""
    adapters = all_adapters()
    try:
        return adapters[name]
    except KeyError:
        known = ", ".join(sorted(adapters)) or "(none)"
        raise KeyError(f"unknown source {name!r}; known sources: {known}") from None
