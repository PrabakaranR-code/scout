"""The SCOUT core engine: parallel fan-out, merge, dedupe, health (§5)."""

from __future__ import annotations

import asyncio
import concurrent.futures
import logging
import os
import time
from typing import Any

import httpx

from scout.adapters import all_adapters
from scout.adapters.base import BaseAdapter
from scout.adapters.fixture import FixtureAdapter
from scout.config import ScoutConfig
from scout.ratelimit import RateLimiter
from scout.robots import RobotsCache
from scout.schema import CATEGORIES, SearchResponse, SearchResult
from scout.urlnorm import normalize_url

logger = logging.getLogger("scout")

# Extra seconds on the hard task deadline so the HTTP-level timeout (which
# yields the better error) usually fires first.
_TIMEOUT_GRACE = 0.5


class Scout:
    """Keyless multi-source search engine, fully in-process.

    Construct with a :class:`ScoutConfig`, a dict, a path to a scout.yaml,
    or plain keyword arguments::

        engine = Scout(timeout=5, trusted_outlets=["reuters.com"])
        response = engine.search("solar sail propulsion", category="science")
    """

    def __init__(
        self,
        config: ScoutConfig | dict[str, Any] | str | None = None,
        **kwargs: Any,
    ) -> None:
        self.config = ScoutConfig.load(config, **kwargs)
        self._limiter = RateLimiter()
        self._robots = RobotsCache()
        self.adapters: dict[str, BaseAdapter] = {}
        if self.config.offline:
            adapter_classes: list[type[BaseAdapter]] = [FixtureAdapter]
        else:
            adapter_classes = list(all_adapters().values())
        for cls in adapter_classes:
            adapter = cls(self.config, limiter=self._limiter, robots=self._robots)
            self.adapters[adapter.name] = adapter

    # -- public API -----------------------------------------------------------

    def search(
        self,
        query: str,
        category: str = "all",
        limit: int = 20,
        sources: list[str] | None = None,
    ) -> SearchResponse:
        """Synchronous facade over :meth:`asearch`.

        Safe to call from a thread that already runs an event loop: the
        fan-out then executes on a private loop in a worker thread.
        """
        try:
            asyncio.get_running_loop()
        except RuntimeError:
            return asyncio.run(self.asearch(query, category, limit, sources))
        with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
            future = pool.submit(
                asyncio.run, self.asearch(query, category, limit, sources)
            )
            return future.result()

    async def asearch(
        self,
        query: str,
        category: str = "all",
        limit: int = 20,
        sources: list[str] | None = None,
    ) -> SearchResponse:
        """Query all participating sources in parallel and merge the answers.

        Args:
            query: Free-text query, passed to every source verbatim.
            category: ``"all"`` or one of general/news/science/knowledge/archive.
            limit: Maximum results in the merged list (also the per-source ask).
            sources: Explicit adapter names. Naming a source runs it even if
                it is disabled by default or by config — except sources whose
                required env var is missing, which stay disabled.

        Failures never propagate: a source that errors, times out, or blocks
        contributes nothing and is recorded in ``health``.
        """
        if not query or not query.strip():
            raise ValueError("query must be a non-empty string")
        if limit < 1:
            raise ValueError("limit must be >= 1")
        if category != "all" and category not in CATEGORIES:
            raise ValueError(
                f"unknown category {category!r}; expected 'all' or one of "
                + ", ".join(CATEGORIES)
            )
        if sources:
            unknown = [name for name in sources if name not in self.adapters]
            if unknown:
                raise ValueError(
                    f"unknown source(s): {', '.join(unknown)}; known: "
                    + ", ".join(sorted(self.adapters))
                )

        started = time.perf_counter()
        selected = self._select(category, sources)
        health: dict[str, str] = {
            name: "disabled" for name in self.adapters if name not in selected
        }
        per_source: dict[str, list[SearchResult]] = {}

        if selected:
            async with httpx.AsyncClient(follow_redirects=True) as client:
                outcomes = await asyncio.gather(
                    *(
                        self._run_source(client, adapter, query, limit)
                        for adapter in selected.values()
                    )
                )
            for name, status, results in outcomes:
                health[name] = status
                if status == "ok":
                    per_source[name] = results

        merged = _round_robin(per_source)
        deduped = _dedupe(merged)[:limit]
        elapsed_ms = int((time.perf_counter() - started) * 1000)
        return SearchResponse(
            query=query, results=deduped, health=health, elapsed_ms=elapsed_ms
        )

    def source_report(self) -> list[dict[str, Any]]:
        """Adapter inventory for the CLI ``scout sources`` command."""
        report = []
        for name in sorted(self.adapters):
            adapter = self.adapters[name]
            report.append(
                {
                    "name": name,
                    "category": adapter.category,
                    "enabled": adapter.is_enabled(),
                    "requires_env": adapter.requires_env,
                    "rate_limit": adapter.effective_rate_limit,
                    "timeout": adapter.effective_timeout,
                }
            )
        return report

    # -- internals -------------------------------------------------------------

    def _select(
        self, category: str, sources: list[str] | None
    ) -> dict[str, BaseAdapter]:
        """Adapters that participate in this search, in registry order."""
        selected: dict[str, BaseAdapter] = {}
        for name, adapter in self.adapters.items():
            if sources is not None:
                if name not in sources:
                    continue
                # Explicitly named: only the missing-env rule can veto (§4.C).
                if adapter.requires_env and not os.environ.get(adapter.requires_env):
                    continue
            elif not adapter.is_enabled():
                continue
            if category != "all" and adapter.category != category:
                continue
            selected[name] = adapter
        return selected

    async def _run_source(
        self,
        client: httpx.AsyncClient,
        adapter: BaseAdapter,
        query: str,
        limit: int,
    ) -> tuple[str, str, list[SearchResult]]:
        """Run one adapter inside its own timeout; never raises (§2.3)."""
        try:
            results = await asyncio.wait_for(
                adapter.search(client, query, limit),
                timeout=adapter.effective_timeout + _TIMEOUT_GRACE,
            )
            return adapter.name, "ok", results
        except (TimeoutError, asyncio.TimeoutError, httpx.TimeoutException):
            logger.warning("source %s timed out after %.1fs",
                           adapter.name, adapter.effective_timeout)
            return adapter.name, "timeout", []
        except Exception as exc:
            logger.warning("source %s failed: %s", adapter.name, exc)
            return adapter.name, "error", []


def _round_robin(per_source: dict[str, list[SearchResult]]) -> list[SearchResult]:
    """Interleave by source then raw_rank so no source dominates the top."""
    columns = [
        sorted(results, key=lambda r: r.raw_rank)
        for results in per_source.values()
        if results
    ]
    merged: list[SearchResult] = []
    for tier in range(max((len(col) for col in columns), default=0)):
        for column in columns:
            if tier < len(column):
                merged.append(column[tier])
    return merged


def _richness(result: SearchResult) -> tuple[int, int]:
    return (1 if result.published is not None else 0, len(result.snippet))


def _dedupe(merged: list[SearchResult]) -> list[SearchResult]:
    """Collapse results pointing at the same document.

    First occurrence keeps its position; the richer duplicate's content wins
    (longer snippet / has a date); every other contributing source is
    recorded in ``also_found_in``; ``trusted`` is OR-ed.
    """
    kept: dict[str, SearchResult] = {}
    order: list[str] = []
    for result in merged:
        key = normalize_url(result.url)
        existing = kept.get(key)
        if existing is None:
            kept[key] = result.model_copy(deep=True)
            order.append(key)
            continue
        winner, loser = existing, result
        if _richness(result) > _richness(existing):
            winner, loser = result.model_copy(deep=True), existing
        sources = [winner.source, *winner.also_found_in]
        for name in (loser.source, *loser.also_found_in):
            if name not in sources:
                sources.append(name)
        winner.also_found_in = [s for s in sources if s != winner.source]
        winner.trusted = existing.trusted or result.trusted
        kept[key] = winner
    return [kept[key] for key in order]
