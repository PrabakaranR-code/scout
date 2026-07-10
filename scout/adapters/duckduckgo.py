"""DuckDuckGo's plain-HTML endpoint (effectively reaches Bing's index).

Result links are usually redirect URLs carrying the real target in the
``uddg`` query parameter; both redirect and direct forms are handled.
"""

from __future__ import annotations

from typing import Any, ClassVar
from urllib.parse import parse_qs, quote_plus, unquote, urlsplit

from scout.adapters._engine import HTMLEngineAdapter
from scout.adapters._html import parse_html
from scout.schema import SearchResult


def _unwrap_redirect(href: str) -> str:
    """Extract the destination from a result link, redirect-wrapped or not."""
    if href.startswith("//"):
        href = "https:" + href
    parts = urlsplit(href)
    if parts.path.startswith("/l/") and "uddg" in parts.query:
        target = parse_qs(parts.query).get("uddg", [""])[0]
        return unquote(target)
    return href


class DuckDuckGoAdapter(HTMLEngineAdapter):
    name: ClassVar[str] = "duckduckgo"

    def search_url(self, query: str, limit: int) -> str:
        return f"https://html.duckduckgo.com/html/?q={quote_plus(query)}"

    def parse(self, raw: Any, query: str, limit: int) -> list[SearchResult]:
        if not isinstance(raw, str):
            return []
        tree = parse_html(raw)
        results: list[SearchResult] = []
        for item in tree.find_all("div", cls="result"):
            link = item.find("a", cls="result__a")
            if link is None:
                continue
            url = _unwrap_redirect(link.attr("href"))
            title = link.text()
            if not url.startswith(("http://", "https://")) or not title:
                continue
            host = urlsplit(url).hostname or ""
            if host == "duckduckgo.com" or host.endswith(".duckduckgo.com"):
                continue  # ads and internal links, not the web
            snippet_node = item.find(cls="result__snippet")
            results.append(
                self.make_result(
                    title=title,
                    url=url,
                    snippet=snippet_node.text() if snippet_node else "",
                    raw_rank=len(results) + 1,
                )
            )
        return results
