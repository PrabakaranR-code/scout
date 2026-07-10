"""Per-source rate limiting (politeness, §2.2).

Each source gets an independent budget expressed as requests per second;
``acquire`` sleeps just long enough to keep the observed rate under it.
"""

from __future__ import annotations

import asyncio
from collections import defaultdict


class RateLimiter:
    """Async per-key rate limiter.

    One instance is shared by all adapters of a single Scout engine, so
    concurrent fan-outs cannot exceed a source's budget even when several
    searches run at once.
    """

    def __init__(self) -> None:
        self._next_free: dict[str, float] = {}
        self._locks: defaultdict[str, asyncio.Lock] = defaultdict(asyncio.Lock)

    async def acquire(self, key: str, per_second: float) -> None:
        """Wait until a request to ``key`` is allowed under ``per_second``.

        A non-positive budget disables limiting for that key.
        """
        if per_second <= 0:
            return
        interval = 1.0 / per_second
        async with self._locks[key]:
            loop = asyncio.get_running_loop()
            now = loop.time()
            scheduled = max(now, self._next_free.get(key, now))
            self._next_free[key] = scheduled + interval
        delay = scheduled - now
        if delay > 0:
            await asyncio.sleep(delay)
