"""Public-instance SearXNG relay — the booster source, OFF by default.

Privacy trade-off (§2.4): every other SCOUT source is queried directly from
your machine to the official service. This adapter instead relays your query
through volunteer-run public SearXNG instances, so the instance operator can
see your query and IP. Nothing here runs unless you explicitly enable it::

    sources:
      searxng_public:
        enabled: true

Instances are taken from ``searxng_instances`` in config (falling back to a
small shipped list) and rotated between requests to spread load. Instances
that refuse JSON output or are down simply contribute nothing.
"""

from __future__ import annotations

import itertools
from datetime import datetime
from typing import Any, ClassVar

import httpx

from scout.adapters.base import BaseAdapter
from scout.config import ScoutConfig
from scout.ratelimit import RateLimiter
from scout.robots import RobotsCache
from scout.schema import SearchResult

DEFAULT_INSTANCES: tuple[str, ...] = (
    "https://searx.be",
    "https://searx.tiekoetter.com",
    "https://priv.au",
    "https://paulgo.io",
)


class SearxngPublicAdapter(BaseAdapter):
    name: ClassVar[str] = "searxng_public"
    category = "general"
    default_enabled: ClassVar[bool] = False  # privacy trade-off: opt-in only
    rate_limit: ClassVar[float] = 0.5

    def __init__(
        self,
        config: ScoutConfig,
        *,
        limiter: RateLimiter | None = None,
        robots: RobotsCache | None = None,
    ) -> None:
        super().__init__(config, limiter=limiter, robots=robots)
        instances = list(config.searxng_instances) or list(DEFAULT_INSTANCES)
        self._rotation = itertools.cycle(instances)

    def next_instance(self) -> str:
        return next(self._rotation).rstrip("/")

    async def fetch(self, client: httpx.AsyncClient, query: str, limit: int) -> Any:
        instance = self.next_instance()
        response = await self.get(
            client, f"{instance}/search", params={"q": query, "format": "json"}
        )
        try:
            return response.json()
        except ValueError:
            return None  # instance has JSON output disabled

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
            published: datetime | None = None
            stamp = entry.get("publishedDate")
            if isinstance(stamp, str) and stamp:
                try:
                    published = datetime.fromisoformat(stamp.replace("Z", "+00:00"))
                except ValueError:
                    published = None
            results.append(
                self.make_result(
                    title=title,
                    url=url,
                    snippet=str(entry.get("content") or ""),
                    published=published,
                    raw_rank=len(results) + 1,
                )
            )
        return results
