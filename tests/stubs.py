"""Stub adapters used by core-engine tests. No network anywhere."""

from __future__ import annotations

import asyncio
from typing import Any, ClassVar

import httpx

from scout.adapters.base import BaseAdapter
from scout.schema import SearchResult


class StubAdapter(BaseAdapter):
    """Returns pre-baked results supplied at class-creation time."""

    name: ClassVar[str] = "stub"
    rate_limit: ClassVar[float] = 0.0
    canned: ClassVar[list[dict[str, Any]]] = []

    async def fetch(self, client: httpx.AsyncClient, query: str, limit: int) -> Any:
        return list(self.canned)

    def parse(self, raw: Any, query: str, limit: int) -> list[SearchResult]:
        return [self.make_result(**item) for item in raw]


def make_stub(
    stub_name: str,
    results: list[dict[str, Any]],
    *,
    enabled: bool = True,
    stub_category: str = "general",
) -> type[StubAdapter]:
    """Create a stub adapter class returning the given results."""
    return type(
        f"Stub_{stub_name}",
        (StubAdapter,),
        {
            "name": stub_name,
            "canned": results,
            "default_enabled": enabled,
            "category": stub_category,
        },
    )


class TimeoutStub(BaseAdapter):
    """Never finishes; the engine's timeout must cut it off."""

    name: ClassVar[str] = "sleepy"
    rate_limit: ClassVar[float] = 0.0
    timeout: ClassVar[float] = 0.2

    async def fetch(self, client: httpx.AsyncClient, query: str, limit: int) -> Any:
        await asyncio.sleep(60)

    def parse(self, raw: Any, query: str, limit: int) -> list[SearchResult]:
        return []


class ErrorStub(BaseAdapter):
    """Always raises, simulating a broken source."""

    name: ClassVar[str] = "broken"
    rate_limit: ClassVar[float] = 0.0

    async def fetch(self, client: httpx.AsyncClient, query: str, limit: int) -> Any:
        raise RuntimeError("boom")

    def parse(self, raw: Any, query: str, limit: int) -> list[SearchResult]:
        return []


def build_engine(adapter_classes, config=None, **kwargs):
    """A Scout wired to the given adapter classes only."""
    from scout.core import Scout

    engine = Scout(config, **kwargs)
    engine.adapters = {}
    for cls in adapter_classes:
        adapter = cls(engine.config, limiter=engine._limiter, robots=engine._robots)
        engine.adapters[adapter.name] = adapter
    return engine
