"""Generic news-RSS adapter driven by a configurable outlet table.

The shipped table covers international wire and public-service outlets plus
fact-checker feeds. Users can replace it entirely via ``rss_outlets`` in
config. Feeds die and move routinely; a dead feed contributes nothing and
never fails the search.

Relevance is plain query-term matching against title + summary of recent
items: every term longer than two characters must appear (case-insensitive).
Matches are ordered newest first.
"""

from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from typing import Any, ClassVar

import feedparser
import httpx

from scout.adapters.base import BaseAdapter
from scout.schema import SearchResult

DEFAULT_OUTLETS: dict[str, str] = {
    "aljazeera": "https://www.aljazeera.com/xml/rss/all.xml",
    "reuters": "https://www.reutersagency.com/feed/?best-topics=top-news&post_type=best",
    "bbc": "https://feeds.bbci.co.uk/news/world/rss.xml",
    "ap": "https://apnews.com/hub/ap-top-news.rss",
    "npr": "https://feeds.npr.org/1001/rss.xml",
    "dw": "https://rss.dw.com/rdf/rss-en-all",
    "france24": "https://www.france24.com/en/rss",
    "thehindu": "https://www.thehindu.com/news/national/feeder/default.rss",
    "afpfactcheck": "https://factcheck.afp.com/rss.xml",
    "fullfact": "https://fullfact.org/feed/all/",
}


def _terms(query: str) -> list[str]:
    return [t for t in query.lower().split() if len(t) > 2] or [query.lower().strip()]


class RSSAdapter(BaseAdapter):
    name: ClassVar[str] = "rss"
    category = "news"
    rate_limit: ClassVar[float] = 1.0  # one sweep per second across the table
    timeout: ClassVar[float] = 10.0

    @property
    def outlets(self) -> dict[str, str]:
        if self.config.rss_outlets is not None:
            return self.config.rss_outlets
        return DEFAULT_OUTLETS

    async def fetch(
        self, client: httpx.AsyncClient, query: str, limit: int
    ) -> list[tuple[str, str]]:
        """Fetch every outlet's feed concurrently; dead feeds are skipped."""

        async def fetch_one(outlet: str, url: str) -> tuple[str, str] | None:
            try:
                response = await self.get(client, url)
                return outlet, response.text
            except Exception:
                return None

        fetched = await asyncio.gather(
            *(fetch_one(outlet, url) for outlet, url in self.outlets.items())
        )
        return [pair for pair in fetched if pair is not None]

    def parse(self, raw: Any, query: str, limit: int) -> list[SearchResult]:
        if not isinstance(raw, list):
            return []
        terms = _terms(query)
        matches: list[tuple[datetime, SearchResult]] = []
        epoch = datetime(1970, 1, 1, tzinfo=timezone.utc)
        for pair in raw:
            if not (isinstance(pair, (tuple, list)) and len(pair) == 2):
                continue
            outlet, feed_text = pair
            if not isinstance(feed_text, (str, bytes)):
                continue
            feed = feedparser.parse(feed_text)
            for entry in feed.entries:
                title = " ".join(str(entry.get("title") or "").split())
                url = str(entry.get("link") or "")
                summary = " ".join(str(entry.get("summary") or "").split())
                if not title or not url.startswith(("http://", "https://")):
                    continue
                haystack = f"{title} {summary}".lower()
                if not all(term in haystack for term in terms):
                    continue
                published: datetime | None = None
                if entry.get("published_parsed"):
                    published = datetime(
                        *entry.published_parsed[:6], tzinfo=timezone.utc
                    )
                elif entry.get("updated_parsed"):
                    published = datetime(
                        *entry.updated_parsed[:6], tzinfo=timezone.utc
                    )
                result = self.make_result(
                    title=title,
                    url=url,
                    snippet=summary[:500],
                    published=published,
                    source=f"rss:{outlet}",
                )
                matches.append((published or epoch, result))
        matches.sort(key=lambda pair: pair[0], reverse=True)
        results = [result for _, result in matches]
        for rank, result in enumerate(results, start=1):
            result.raw_rank = rank
        return results
