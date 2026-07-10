"""Common base class for every source adapter.

An adapter does two separable things:

* :meth:`BaseAdapter.fetch` — one polite HTTP round-trip to the source.
* :meth:`BaseAdapter.parse` — turn the raw payload into ``SearchResult``s.

The split exists so parsing is testable from saved fixtures with zero
network. :meth:`BaseAdapter.search` glues the two together and is what the
core engine calls; it also applies the per-source rate limit. The
:meth:`BaseAdapter.get` helper adds the honest User-Agent, the robots.txt
check for scraped engines, and turns blocking status codes into
:class:`~scout.errors.SourceBlockedError`.
"""

from __future__ import annotations

import os
from abc import ABC, abstractmethod
from datetime import datetime
from typing import Any, ClassVar
from urllib.parse import urlsplit

import httpx

from scout.config import ScoutConfig
from scout.errors import SourceBlockedError, SourceError
from scout.ratelimit import RateLimiter
from scout.robots import RobotsCache
from scout.schema import Category, SearchResult


class BaseAdapter(ABC):
    """One search source: an engine, an API, a feed set, or an archive.

    Class attributes declare the adapter's contract:

    * ``name`` — unique registry key, e.g. ``"mojeek"``.
    * ``category`` — the result category this source contributes to.
    * ``default_enabled`` — whether the source runs without explicit config.
    * ``rate_limit`` — maximum requests per second against this source.
    * ``timeout`` — per-request timeout in seconds; ``None`` inherits the
      config-wide default.
    * ``requires_env`` — env var that must exist for the source to activate
      (``None`` for keyless sources).
    * ``scrapes_html`` — True for HTML-endpoint engines; these honor
      robots.txt and must never point at ToS-hostile targets.
    """

    name: ClassVar[str]
    category: ClassVar[Category] = "general"
    default_enabled: ClassVar[bool] = True
    rate_limit: ClassVar[float] = 1.0
    timeout: ClassVar[float | None] = None
    requires_env: ClassVar[str | None] = None
    scrapes_html: ClassVar[bool] = False

    def __init__(
        self,
        config: ScoutConfig,
        *,
        limiter: RateLimiter | None = None,
        robots: RobotsCache | None = None,
    ) -> None:
        self.config = config
        self._limiter = limiter or RateLimiter()
        self._robots = robots or RobotsCache()
        settings = config.source_settings(self.name)
        if settings.timeout is not None:
            self.effective_timeout: float = settings.timeout
        elif self.timeout is not None:
            self.effective_timeout = self.timeout
        else:
            self.effective_timeout = config.timeout
        self.effective_rate_limit: float = (
            settings.rate_limit if settings.rate_limit is not None else self.rate_limit
        )
        self._enabled_override = settings.enabled

    # -- activation ---------------------------------------------------------

    def is_enabled(self) -> bool:
        """Whether this source participates in searches.

        Explicit config wins; otherwise the adapter default applies. A source
        whose required env var is missing is never enabled.
        """
        if self.requires_env and not os.environ.get(self.requires_env):
            return False
        if self._enabled_override is not None:
            return self._enabled_override
        return self.default_enabled

    # -- the two halves ------------------------------------------------------

    @abstractmethod
    async def fetch(self, client: httpx.AsyncClient, query: str, limit: int) -> Any:
        """Perform the HTTP request(s) and return the raw payload."""

    @abstractmethod
    def parse(self, raw: Any, query: str, limit: int) -> list[SearchResult]:
        """Turn a raw payload into results. Must degrade on malformed input,
        returning whatever could be salvaged (possibly nothing) — never raise
        for bad markup or missing fields."""

    async def search(
        self, client: httpx.AsyncClient, query: str, limit: int
    ) -> list[SearchResult]:
        """Rate-limit, fetch, then parse; the core engine calls this inside
        its own timeout and failure isolation."""
        await self._limiter.acquire(self.name, self.effective_rate_limit)
        raw = await self.fetch(client, query, limit)
        return self.parse(raw, query, limit)[:limit]

    # -- helpers for subclasses ----------------------------------------------

    async def get(
        self,
        client: httpx.AsyncClient,
        url: str,
        *,
        params: dict[str, Any] | None = None,
    ) -> httpx.Response:
        """Polite GET: honest User-Agent, robots.txt for scraped engines,
        blocking statuses surfaced as :class:`SourceBlockedError`."""
        target = str(httpx.URL(url, params=params)) if params else url
        if self.scrapes_html and self.config.respect_robots:
            allowed = await self._robots.allowed(
                client, target, self.config.resolved_user_agent()
            )
            if not allowed:
                raise SourceBlockedError(f"{self.name}: robots.txt disallows {url}")
        response = await client.get(
            target,
            headers=self.request_headers(),
            timeout=self.effective_timeout,
            follow_redirects=True,
        )
        if response.status_code in (401, 403, 429):
            raise SourceBlockedError(
                f"{self.name}: HTTP {response.status_code} from {url}"
            )
        if response.status_code >= 400:
            raise SourceError(f"{self.name}: HTTP {response.status_code} from {url}")
        return response

    def make_result(
        self,
        *,
        title: str,
        url: str,
        snippet: str = "",
        raw_rank: int = 0,
        published: datetime | None = None,
        source: str | None = None,
        category: Category | None = None,
    ) -> SearchResult:
        """Build a ``SearchResult`` stamped with this adapter's identity and
        the user's trusted-outlet marking."""
        return SearchResult(
            title=title.strip(),
            url=url,
            snippet=snippet.strip(),
            source=source or self.name,
            category=category or self.category,
            published=published,
            trusted=self._is_trusted(url),
            raw_rank=raw_rank,
        )

    def _is_trusted(self, url: str) -> bool:
        host = (urlsplit(url).hostname or "").lower()
        for outlet in self.config.trusted_outlets:
            outlet = outlet.lower().lstrip(".")
            if host == outlet or host.endswith("." + outlet):
                return True
        return False

    def request_headers(self) -> dict[str, str]:
        """Headers for every request: an honest, identifying User-Agent."""
        return {"User-Agent": self.config.resolved_user_agent()}
