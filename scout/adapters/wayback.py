"""Wayback Machine availability API (keyless): archived copies of URLs.

This source only contributes when the query itself looks like a URL or bare
domain — the availability API answers "is there an archived copy of this
page", not free-text search. For other queries it returns nothing, which is
a normal, healthy outcome.
"""

from __future__ import annotations

import re
from datetime import datetime, timezone
from typing import Any, ClassVar
from urllib.parse import quote_plus

import httpx

from scout.adapters.base import BaseAdapter
from scout.schema import SearchResult

_URLISH_RE = re.compile(
    r"^(https?://)?[a-z0-9][a-z0-9.-]*\.[a-z]{2,}(/\S*)?$", re.IGNORECASE
)


def looks_like_url(query: str) -> bool:
    return bool(_URLISH_RE.match(query.strip()))


class WaybackAdapter(BaseAdapter):
    name: ClassVar[str] = "wayback"
    category = "archive"
    rate_limit: ClassVar[float] = 1.0

    async def fetch(self, client: httpx.AsyncClient, query: str, limit: int) -> Any:
        query = query.strip()
        if not looks_like_url(query):
            return None
        url = f"https://archive.org/wayback/available?url={quote_plus(query)}"
        return (await self.get(client, url)).json()

    def parse(self, raw: Any, query: str, limit: int) -> list[SearchResult]:
        if not isinstance(raw, dict):
            return []
        closest = raw.get("archived_snapshots")
        closest = closest.get("closest") if isinstance(closest, dict) else None
        if not isinstance(closest, dict) or not closest.get("available"):
            return []
        snapshot_url = str(closest.get("url") or "")
        if not snapshot_url.startswith(("http://", "https://")):
            return []
        published: datetime | None = None
        timestamp = str(closest.get("timestamp") or "")
        if len(timestamp) == 14 and timestamp.isdigit():
            try:
                published = datetime.strptime(timestamp, "%Y%m%d%H%M%S").replace(
                    tzinfo=timezone.utc
                )
            except ValueError:
                published = None
        return [
            self.make_result(
                title=f"Archived copy of {query.strip()}",
                url=snapshot_url,
                snippet="Closest snapshot in the Internet Archive Wayback Machine"
                + (f", captured {timestamp[:8]}" if timestamp else ""),
                published=published,
                raw_rank=1,
            )
        ]
