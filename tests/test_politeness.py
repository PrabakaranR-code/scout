"""Politeness-layer tests (§2.2): robots.txt, honest UA, blocking statuses."""

from __future__ import annotations

import asyncio
from typing import Any, ClassVar

import httpx
import pytest

from scout.adapters.base import BaseAdapter
from scout.config import ScoutConfig
from scout.errors import SourceBlockedError, SourceError
from scout.robots import RobotsCache
from scout.schema import SearchResult


class ScraperStub(BaseAdapter):
    name: ClassVar[str] = "scraper"
    scrapes_html: ClassVar[bool] = True
    rate_limit: ClassVar[float] = 0.0

    async def fetch(self, client: httpx.AsyncClient, query: str, limit: int) -> Any:
        response = await self.get(client, "https://engine.example/search?q=" + query)
        return response.text

    def parse(self, raw: Any, query: str, limit: int) -> list[SearchResult]:
        return [self.make_result(title="t", url="https://example.org/x", raw_rank=1)]


def make_client(robots_body: str | None, page_status: int = 200) -> httpx.AsyncClient:
    """A client whose transport serves a robots.txt and a search page."""
    seen_headers: list[httpx.Headers] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen_headers.append(request.headers)
        if request.url.path == "/robots.txt":
            if robots_body is None:
                return httpx.Response(404, text="nope")
            return httpx.Response(200, text=robots_body)
        return httpx.Response(page_status, text="<html></html>")

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    client._seen_headers = seen_headers  # type: ignore[attr-defined]
    return client


def run_search(adapter: BaseAdapter, client: httpx.AsyncClient):
    async def go():
        async with client:
            return await adapter.search(client, "q", 5)

    return asyncio.run(go())


def test_robots_disallow_blocks_scraper() -> None:
    adapter = ScraperStub(ScoutConfig())
    client = make_client("User-agent: *\nDisallow: /search\n")
    with pytest.raises(SourceBlockedError):
        run_search(adapter, client)


def test_robots_allow_lets_scraper_through() -> None:
    adapter = ScraperStub(ScoutConfig())
    client = make_client("User-agent: *\nDisallow: /private\n")
    assert len(run_search(adapter, client)) == 1


def test_missing_robots_is_permissive() -> None:
    adapter = ScraperStub(ScoutConfig())
    client = make_client(None)
    assert len(run_search(adapter, client)) == 1


def test_respect_robots_false_skips_check() -> None:
    adapter = ScraperStub(ScoutConfig(respect_robots=False))
    client = make_client("User-agent: *\nDisallow: /\n")
    assert len(run_search(adapter, client)) == 1


def test_honest_user_agent_sent_everywhere() -> None:
    adapter = ScraperStub(ScoutConfig())
    client = make_client("User-agent: *\nAllow: /\n")
    run_search(adapter, client)
    headers_seen = client._seen_headers  # type: ignore[attr-defined]
    assert headers_seen, "no requests captured"
    for headers in headers_seen:
        assert headers["user-agent"].startswith("SCOUT/")
        assert "+https://github.com/" in headers["user-agent"]


@pytest.mark.parametrize("status", [401, 403, 429])
def test_blocking_statuses_raise_blocked(status: int) -> None:
    adapter = ScraperStub(ScoutConfig())
    client = make_client("User-agent: *\nAllow: /\n", page_status=status)
    with pytest.raises(SourceBlockedError):
        run_search(adapter, client)


def test_server_error_raises_source_error() -> None:
    adapter = ScraperStub(ScoutConfig())
    client = make_client("User-agent: *\nAllow: /\n", page_status=500)
    with pytest.raises(SourceError):
        run_search(adapter, client)


def test_robots_cache_fetches_once_per_host() -> None:
    calls = {"robots": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/robots.txt":
            calls["robots"] += 1
            return httpx.Response(200, text="User-agent: *\nAllow: /\n")
        return httpx.Response(200, text="ok")

    async def go() -> None:
        cache = RobotsCache()
        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
            for _ in range(5):
                assert await cache.allowed(client, "https://h.example/a", "SCOUT/0")

    asyncio.run(go())
    assert calls["robots"] == 1


def test_unfetchable_robots_is_permissive() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("no route")

    async def go() -> bool:
        cache = RobotsCache()
        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
            return await cache.allowed(client, "https://h.example/a", "SCOUT/0")

    assert asyncio.run(go()) is True
