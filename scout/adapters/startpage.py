"""Startpage: best-effort HTML engine that reaches Google's index.

Expected to be the first source to degrade (§4.A): it rotates markup and
rate-limits aggressively. The parser accepts both its older and newer class
names and returning nothing is a normal outcome, not an error.
"""

from __future__ import annotations

from typing import Any, ClassVar
from urllib.parse import quote_plus

from scout.adapters._engine import HTMLEngineAdapter
from scout.adapters._html import Node, parse_html
from scout.schema import SearchResult


class StartpageAdapter(HTMLEngineAdapter):
    name: ClassVar[str] = "startpage"
    rate_limit: ClassVar[float] = 0.25  # extra caution: one request per 4s

    def search_url(self, query: str, limit: int) -> str:
        return f"https://www.startpage.com/sp/search?query={quote_plus(query)}"

    def parse(self, raw: Any, query: str, limit: int) -> list[SearchResult]:
        if not isinstance(raw, str):
            return []
        tree = parse_html(raw)
        blocks = tree.find_all(cls="w-gl__result") or tree.find_all(cls="result")
        results: list[SearchResult] = []
        for item in blocks:
            link = self._title_link(item)
            if link is None:
                continue
            url = link.attr("href")
            title = link.text()
            if not url.startswith(("http://", "https://")) or not title:
                continue
            snippet_node = item.find(cls="w-gl__description") or item.find(
                cls="description"
            )
            results.append(
                self.make_result(
                    title=title,
                    url=url,
                    snippet=snippet_node.text() if snippet_node else "",
                    raw_rank=len(results) + 1,
                )
            )
        return results

    @staticmethod
    def _title_link(item: Node) -> Node | None:
        for cls in ("w-gl__result-title", "result-title", "result-link"):
            link = item.find("a", cls=cls)
            if link is not None:
                return link
        for anchor in item.find_all("a"):
            if anchor.attr("href").startswith(("http://", "https://")):
                return anchor
        return None
