"""Mojeek: an independent, crawler-owned index with a plain HTML results page."""

from __future__ import annotations

from typing import Any, ClassVar
from urllib.parse import quote_plus

from scout.adapters._engine import HTMLEngineAdapter
from scout.adapters._html import parse_html
from scout.schema import SearchResult


class MojeekAdapter(HTMLEngineAdapter):
    name: ClassVar[str] = "mojeek"

    def search_url(self, query: str, limit: int) -> str:
        return f"https://www.mojeek.com/search?q={quote_plus(query)}"

    def parse(self, raw: Any, query: str, limit: int) -> list[SearchResult]:
        if not isinstance(raw, str):
            return []
        tree = parse_html(raw)
        results: list[SearchResult] = []
        container = tree.find("ul", cls="results-standard") or tree
        for item in container.find_all("li"):
            link = item.find("a", cls="title") or item.find("a", cls="ob")
            if link is None:
                continue
            url = link.attr("href")
            title = link.text()
            if not url.startswith(("http://", "https://")) or not title:
                continue
            snippet_node = item.find("p", cls="s")
            results.append(
                self.make_result(
                    title=title,
                    url=url,
                    snippet=snippet_node.text() if snippet_node else "",
                    raw_rank=len(results) + 1,
                )
            )
        return results
