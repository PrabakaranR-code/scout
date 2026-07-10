"""robots.txt checks for HTML-scraping adapters (politeness, §2.2).

Only scraped engines are checked; official APIs and feeds are exercised the
way their operators intend and skip this step. Failure to fetch or parse a
robots.txt is treated permissively (allow), matching common crawler practice
for transient errors on well-behaved, low-volume clients.
"""

from __future__ import annotations

import asyncio
import logging
import urllib.robotparser
from urllib.parse import urlsplit

import httpx

logger = logging.getLogger("scout")


class RobotsCache:
    """Fetches and caches robots.txt verdicts per host."""

    def __init__(self) -> None:
        self._parsers: dict[str, urllib.robotparser.RobotFileParser | None] = {}
        self._lock = asyncio.Lock()

    async def allowed(self, client: httpx.AsyncClient, url: str, user_agent: str) -> bool:
        """True when ``user_agent`` may fetch ``url`` per the host's robots.txt."""
        parts = urlsplit(url)
        if not parts.hostname:
            return True
        origin = f"{parts.scheme or 'https'}://{parts.netloc}"
        async with self._lock:
            if origin not in self._parsers:
                self._parsers[origin] = await self._fetch(client, origin, user_agent)
        parser = self._parsers[origin]
        if parser is None:
            return True
        return parser.can_fetch(user_agent, url)

    async def _fetch(
        self, client: httpx.AsyncClient, origin: str, user_agent: str
    ) -> urllib.robotparser.RobotFileParser | None:
        try:
            response = await client.get(
                f"{origin}/robots.txt",
                headers={"User-Agent": user_agent},
                timeout=5.0,
            )
        except Exception as exc:
            logger.debug("robots.txt fetch failed for %s: %s", origin, exc)
            return None
        if response.status_code >= 400:
            # Missing/forbidden robots.txt: nothing to obey.
            return None
        parser = urllib.robotparser.RobotFileParser()
        try:
            parser.parse(response.text.splitlines())
        except Exception as exc:
            logger.debug("robots.txt parse failed for %s: %s", origin, exc)
            return None
        return parser
