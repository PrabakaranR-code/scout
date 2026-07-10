"""The Guardian Open Platform — an optional keyed source.

Activates only when the ``GUARDIAN_API_KEY`` env var is present (§2.1);
without it the source reports as disabled and is never queried.
"""

from __future__ import annotations

import os
from datetime import datetime
from typing import Any, ClassVar
from urllib.parse import quote_plus

import httpx

from scout.adapters.base import BaseAdapter
from scout.schema import SearchResult


class GuardianAdapter(BaseAdapter):
    name: ClassVar[str] = "guardian"
    category = "news"
    rate_limit: ClassVar[float] = 1.0
    requires_env: ClassVar[str] = "GUARDIAN_API_KEY"

    def search_url(self, query: str, limit: int) -> str:
        key = os.environ.get(self.requires_env, "")
        return (
            "https://content.guardianapis.com/search?q="
            f"{quote_plus(query)}&page-size={min(limit, 50)}"
            f"&show-fields=trailText&api-key={key}"
        )

    async def fetch(self, client: httpx.AsyncClient, query: str, limit: int) -> Any:
        response = await self.get(client, self.search_url(query, limit))
        return response.json()

    def parse(self, raw: Any, query: str, limit: int) -> list[SearchResult]:
        if not isinstance(raw, dict):
            return []
        payload = raw.get("response")
        entries = payload.get("results") if isinstance(payload, dict) else None
        if not isinstance(entries, list):
            return []
        results: list[SearchResult] = []
        for entry in entries:
            if not isinstance(entry, dict):
                continue
            url = str(entry.get("webUrl") or "")
            title = str(entry.get("webTitle") or "")
            if not url.startswith(("http://", "https://")) or not title:
                continue
            published: datetime | None = None
            stamp = entry.get("webPublicationDate")
            if isinstance(stamp, str):
                try:
                    published = datetime.fromisoformat(stamp.replace("Z", "+00:00"))
                except ValueError:
                    published = None
            fields = entry.get("fields")
            snippet = (
                str(fields.get("trailText") or "") if isinstance(fields, dict) else ""
            )
            results.append(
                self.make_result(
                    title=title,
                    url=url,
                    snippet=snippet,
                    published=published,
                    raw_rank=len(results) + 1,
                )
            )
        return results
