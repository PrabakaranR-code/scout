"""Rate limiter tests (§2.2)."""

from __future__ import annotations

import asyncio
import time

from scout.ratelimit import RateLimiter


def test_spacing_enforced_per_key() -> None:
    async def run() -> float:
        limiter = RateLimiter()
        start = time.perf_counter()
        for _ in range(3):
            await limiter.acquire("engine", per_second=20)
        return time.perf_counter() - start

    elapsed = asyncio.run(run())
    # three requests at 20 rps: the second and third wait ~0.05s each
    assert elapsed >= 0.09


def test_keys_are_independent() -> None:
    async def run() -> float:
        limiter = RateLimiter()
        start = time.perf_counter()
        await asyncio.gather(
            limiter.acquire("a", per_second=100),
            limiter.acquire("b", per_second=100),
            limiter.acquire("c", per_second=100),
        )
        return time.perf_counter() - start

    # first request per key never waits
    assert asyncio.run(run()) < 0.05


def test_concurrent_acquires_on_one_key_are_serialized() -> None:
    async def run() -> float:
        limiter = RateLimiter()
        start = time.perf_counter()
        await asyncio.gather(
            *(limiter.acquire("k", per_second=25) for _ in range(4))
        )
        return time.perf_counter() - start

    # 4 concurrent requests at 25 rps: last one waits ~0.12s
    assert asyncio.run(run()) >= 0.1


def test_zero_rate_disables_limiting() -> None:
    async def run() -> float:
        limiter = RateLimiter()
        start = time.perf_counter()
        for _ in range(10):
            await limiter.acquire("free", per_second=0)
        return time.perf_counter() - start

    assert asyncio.run(run()) < 0.05
