"""Wikipedia full-text search via the official, keyless MediaWiki API."""

from __future__ import annotations

import html
import re
from datetime import datetime
from typing import Any, ClassVar
from urllib.parse import quote

import httpx

from scout.adapters.base import BaseAdapter
from scout.schema import SearchResult

_TAG_RE = re.compile(r"<[^>]+>")


def _strip_tags(markup: str) -> str:
    return html.unescape(_TAG_RE.sub("", markup))


class WikipediaAdapter(BaseAdapter):
    name: ClassVar[str] = "wikipedia"
    category = "knowledge"
    rate_limit: ClassVar[float] = 2.0

    def search_url(self, query: str, limit: int) -> str:
        return (
            "https://en.wikipedia.org/w/api.php?action=query&list=search"
            f"&srsearch={quote(query)}&srlimit={min(limit, 50)}"
            "&srprop=snippet%7Ctimestamp&format=json"
        )

    async def fetch(self, client: httpx.AsyncClient, query: str, limit: int) -> Any:
        response = await self.get(client, self.search_url(query, limit))
        return response.json()

    def parse(self, raw: Any, query: str, limit: int) -> list[SearchResult]:
        if not isinstance(raw, dict):
            return []
        entries = raw.get("query", {})
        entries = entries.get("search") if isinstance(entries, dict) else None
        if not isinstance(entries, list):
            return []
        results: list[SearchResult] = []
        for entry in entries:
            if not isinstance(entry, dict):
                continue
            title = str(entry.get("title") or "")
            if not title:
                continue
            published: datetime | None = None
            timestamp = entry.get("timestamp")
            if isinstance(timestamp, str):
                try:
                    published = datetime.fromisoformat(timestamp.replace("Z", "+00:00"))
                except ValueError:
                    published = None
            results.append(
                self.make_result(
                    title=title,
                    url="https://en.wikipedia.org/wiki/"
                    + quote(title.replace(" ", "_")),
                    snippet=_strip_tags(str(entry.get("snippet") or "")),
                    published=published,
                    raw_rank=len(results) + 1,
                )
            )
        return results
