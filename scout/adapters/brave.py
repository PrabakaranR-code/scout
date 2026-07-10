"""Brave Search: independent index with a server-rendered HTML results page."""

from __future__ import annotations

from typing import Any, ClassVar
from urllib.parse import quote_plus

from scout.adapters._engine import HTMLEngineAdapter
from scout.adapters._html import parse_html
from scout.schema import SearchResult


class BraveAdapter(HTMLEngineAdapter):
    name: ClassVar[str] = "brave"

    def search_url(self, query: str, limit: int) -> str:
        return f"https://search.brave.com/search?q={quote_plus(query)}&source=web"

    def parse(self, raw: Any, query: str, limit: int) -> list[SearchResult]:
        if not isinstance(raw, str):
            return []
        tree = parse_html(raw)
        results: list[SearchResult] = []
        for item in tree.find_all(cls="snippet"):
            link = None
            for anchor in item.find_all("a"):
                if anchor.attr("href").startswith(("http://", "https://")):
                    link = anchor
                    break
            if link is None:
                continue
            title_node = item.find(cls="title") or link
            title = title_node.text()
            if not title:
                continue
            snippet_node = item.find(cls="snippet-description")
            results.append(
                self.make_result(
                    title=title,
                    url=link.attr("href"),
                    snippet=snippet_node.text() if snippet_node else "",
                    raw_rank=len(results) + 1,
                )
            )
        return results
