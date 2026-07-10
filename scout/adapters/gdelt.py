"""GDELT DOC 2.0 API (keyless): world news coverage at scale."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, ClassVar
from urllib.parse import quote_plus

import httpx

from scout.adapters.base import BaseAdapter
from scout.schema import SearchResult


class GdeltAdapter(BaseAdapter):
    name: ClassVar[str] = "gdelt"
    category = "news"
    rate_limit: ClassVar[float] = 0.5
    timeout: ClassVar[float] = 10.0

    def search_url(self, query: str, limit: int) -> str:
        return (
            "https://api.gdeltproject.org/api/v2/doc/doc?query="
            f"{quote_plus(query)}&mode=artlist&format=json"
            f"&maxrecords={min(limit, 50)}&sort=hybridrel"
        )

    async def fetch(self, client: httpx.AsyncClient, query: str, limit: int) -> Any:
        response = await self.get(client, self.search_url(query, limit))
        try:
            return response.json()
        except ValueError:
            # GDELT answers some rejected queries with plain-text messages
            return None

    def parse(self, raw: Any, query: str, limit: int) -> list[SearchResult]:
        if not isinstance(raw, dict):
            return []
        articles = raw.get("articles")
        if not isinstance(articles, list):
            return []
        results: list[SearchResult] = []
        for article in articles:
            if not isinstance(article, dict):
                continue
            url = str(article.get("url") or "")
            title = str(article.get("title") or "")
            if not url.startswith(("http://", "https://")) or not title:
                continue
            published: datetime | None = None
            seendate = str(article.get("seendate") or "")
            try:
                published = datetime.strptime(seendate, "%Y%m%dT%H%M%SZ").replace(
                    tzinfo=timezone.utc
                )
            except ValueError:
                published = None
            domain = str(article.get("domain") or "")
            country = str(article.get("sourcecountry") or "")
            snippet = " — ".join(part for part in (domain, country) if part)
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
