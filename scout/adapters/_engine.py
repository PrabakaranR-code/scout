"""Shared base for general-web engines with HTML endpoints (§4.A).

These are the scraped sources, so the full politeness stack applies:
robots.txt, honest User-Agent, conservative per-source rate limits. Google
and Bing are never scraped directly (§2.2); their indexes are only reached
through engines that expose them deliberately.
"""

from __future__ import annotations

from abc import abstractmethod
from typing import Any, ClassVar

import httpx

from scout.adapters.base import BaseAdapter
from scout.schema import SearchResult


class HTMLEngineAdapter(BaseAdapter):
    """One scrape-tolerant search engine speaking HTML."""

    scrapes_html: ClassVar[bool] = True
    rate_limit: ClassVar[float] = 0.5  # at most one request every two seconds
    category = "general"

    @abstractmethod
    def search_url(self, query: str, limit: int) -> str:
        """The results-page URL for ``query``."""

    async def fetch(self, client: httpx.AsyncClient, query: str, limit: int) -> str:
        response = await self.get(client, self.search_url(query, limit))
        return response.text

    @abstractmethod
    def parse(self, raw: Any, query: str, limit: int) -> list[SearchResult]: ...
