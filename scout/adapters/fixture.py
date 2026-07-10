"""Offline fixture source.

Used when ``ScoutConfig.offline`` is True: it answers every query with
deterministic canned results and touches the network never. This exists for
smoke tests, CI, and host-application test suites.
"""

from __future__ import annotations

from typing import Any, ClassVar

import httpx

from scout.adapters.base import BaseAdapter
from scout.schema import SearchResult


class FixtureAdapter(BaseAdapter):
    """Deterministic, network-free source for offline mode."""

    name: ClassVar[str] = "fixture"
    default_enabled: ClassVar[bool] = True
    rate_limit: ClassVar[float] = 0.0  # no network, no budget needed

    async def fetch(self, client: httpx.AsyncClient, query: str, limit: int) -> Any:
        return {"query": query, "count": min(limit, 3)}

    def parse(self, raw: Any, query: str, limit: int) -> list[SearchResult]:
        if not isinstance(raw, dict):
            return []
        count = int(raw.get("count", 0))
        slug = "-".join(query.lower().split()) or "empty"
        return [
            self.make_result(
                title=f"Offline result {rank} for {query!r}",
                url=f"https://example.org/{slug}/{rank}",
                snippet=f"Canned offline snippet {rank} for query {query!r}.",
                raw_rank=rank,
            )
            for rank in range(1, count + 1)
        ]
