"""Common base class for every source adapter.

An adapter does two separable things:

* :meth:`BaseAdapter.fetch` — one polite HTTP round-trip to the source.
* :meth:`BaseAdapter.parse` — turn the raw payload into ``SearchResult``s.

The split exists so parsing is testable from saved fixtures with zero
network. :meth:`BaseAdapter.search` glues the two together and is what the
core engine calls.
"""

from __future__ import annotations

import os
from abc import ABC, abstractmethod
from datetime import datetime
from typing import Any, ClassVar
from urllib.parse import urlsplit

import httpx

from scout.config import ScoutConfig
from scout.schema import Category, SearchResult


class BaseAdapter(ABC):
    """One search source: an engine, an API, a feed set, or an archive.

    Class attributes declare the adapter's contract:

    * ``name`` — unique registry key, e.g. ``"mojeek"``.
    * ``category`` — the result category this source contributes to.
    * ``default_enabled`` — whether the source runs without explicit config.
    * ``rate_limit`` — maximum requests per second against this source.
    * ``timeout`` — per-request timeout in seconds.
    * ``requires_env`` — env var that must exist for the source to activate
      (``None`` for keyless sources).
    * ``scrapes_html`` — True for HTML-endpoint engines; these honor
      robots.txt and must never point at ToS-hostile targets.
    """

    name: ClassVar[str]
    category: ClassVar[Category] = "general"
    default_enabled: ClassVar[bool] = True
    rate_limit: ClassVar[float] = 1.0
    timeout: ClassVar[float] = 8.0
    requires_env: ClassVar[str | None] = None
    scrapes_html: ClassVar[bool] = False

    def __init__(self, config: ScoutConfig) -> None:
        self.config = config
        settings = config.source_settings(self.name)
        self.effective_timeout: float = (
            settings.timeout if settings.timeout is not None else self.timeout
        )
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
        """Fetch then parse; the core engine calls this inside its own
        timeout and failure isolation."""
        raw = await self.fetch(client, query, limit)
        return self.parse(raw, query, limit)[:limit]

    # -- helpers for subclasses ----------------------------------------------

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
        host = urlsplit(url).hostname or ""
        for outlet in self.config.trusted_outlets:
            outlet = outlet.lower().lstrip(".")
            if host == outlet or host.endswith("." + outlet):
                return True
        return False

    def request_headers(self) -> dict[str, str]:
        """Headers for every request: an honest, identifying User-Agent."""
        return {"User-Agent": self.config.resolved_user_agent()}
