"""arXiv preprints via the official, keyless Atom API.

arXiv asks automated clients for no more than one request every three
seconds; the rate limit honors that.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, ClassVar
from urllib.parse import quote_plus

import feedparser
import httpx

from scout.adapters.base import BaseAdapter
from scout.schema import SearchResult


class ArxivAdapter(BaseAdapter):
    name: ClassVar[str] = "arxiv"
    category = "science"
    rate_limit: ClassVar[float] = 1 / 3
    timeout: ClassVar[float] = 10.0

    def search_url(self, query: str, limit: int) -> str:
        return (
            "https://export.arxiv.org/api/query?search_query=all:"
            f"{quote_plus(query)}&start=0&max_results={min(limit, 30)}"
        )

    async def fetch(self, client: httpx.AsyncClient, query: str, limit: int) -> str:
        response = await self.get(client, self.search_url(query, limit))
        return response.text

    def parse(self, raw: Any, query: str, limit: int) -> list[SearchResult]:
        if not isinstance(raw, (str, bytes)):
            return []
        feed = feedparser.parse(raw)
        results: list[SearchResult] = []
        for entry in feed.entries:
            url = entry.get("link") or entry.get("id") or ""
            title = " ".join(str(entry.get("title") or "").split())
            if not url.startswith(("http://", "https://")) or not title:
                continue
            published = None
            if entry.get("published_parsed"):
                published = datetime(
                    *entry.published_parsed[:6], tzinfo=timezone.utc
                )
            snippet = " ".join(str(entry.get("summary") or "").split())
            results.append(
                self.make_result(
                    title=title,
                    url=url,
                    snippet=snippet[:500],
                    published=published,
                    raw_rank=len(results) + 1,
                )
            )
        return results
