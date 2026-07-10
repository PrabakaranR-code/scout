"""Marginalia Search: the non-commercial, independent small web.

Uses the engine's public JSON API (keyless, identified by the literal
``public`` key segment the service offers to anonymous callers), so this is
an official endpoint rather than a scrape.
"""

from __future__ import annotations

from typing import Any, ClassVar
from urllib.parse import quote

import httpx

from scout.adapters.base import BaseAdapter
from scout.schema import SearchResult


class MarginaliaAdapter(BaseAdapter):
    name: ClassVar[str] = "marginalia"
    category = "general"
    rate_limit: ClassVar[float] = 1.0

    def search_url(self, query: str, limit: int) -> str:
        return (
            "https://api.marginalia-search.com/public/search/"
            f"{quote(query)}?count={min(limit, 20)}"
        )

    async def fetch(self, client: httpx.AsyncClient, query: str, limit: int) -> Any:
        response = await self.get(client, self.search_url(query, limit))
        return response.json()

    def parse(self, raw: Any, query: str, limit: int) -> list[SearchResult]:
        if not isinstance(raw, dict):
            return []
        entries = raw.get("results")
        if not isinstance(entries, list):
            return []
        results: list[SearchResult] = []
        for entry in entries:
            if not isinstance(entry, dict):
                continue
            url = str(entry.get("url") or "")
            title = str(entry.get("title") or "")
            if not url.startswith(("http://", "https://")) or not title:
                continue
            results.append(
                self.make_result(
                    title=title,
                    url=url,
                    snippet=str(entry.get("description") or ""),
                    raw_rank=len(results) + 1,
                )
            )
        return results
