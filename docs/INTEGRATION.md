# Embedding SCOUT as a search backend

SCOUT is designed to sit inside a host application — an agent framework, a
research tool, a fact-checking pipeline, a notebook — as its web-search
provider. This guide shows the complete pattern. It assumes nothing about
your application beyond "it wants a `search(query) -> results` function".

## The contract

SCOUT gives you candidates, not answers:

- `SearchResponse.results` is a merged, deduplicated candidate list. SCOUT
  never fetches the full pages and never ranks by opinion; your application
  does its own reading, filtering, and ranking.
- `SearchResponse.health` tells you which sources answered. **Empty results
  with all-failing health is a signal to retry or alert; empty results with
  healthy sources means the query genuinely found nothing.**
- Failures never raise out of a search. The only exceptions you'll see from
  `Scout.search` are `ValueError`s for invalid arguments.

## A complete search provider

```python
"""search_provider.py — a SCOUT-backed provider for any host application."""

from dataclasses import dataclass

from scout import Scout, ScoutConfig


@dataclass
class Candidate:
    """Whatever shape YOUR application wants; map SCOUT fields onto it."""

    title: str
    url: str
    summary: str
    source: str
    published_iso: str | None
    trusted: bool


class WebSearchProvider:
    """Thread-safe, reusable: build once, call search() many times."""

    def __init__(self, config: dict | str | None = None) -> None:
        # config can be a dict from YOUR app's settings, a path to a
        # scout.yaml, or None for defaults. See "Config mapping" below.
        self._engine = Scout(ScoutConfig.load(config))

    def search(
        self,
        query: str,
        *,
        category: str = "all",
        max_results: int = 20,
    ) -> list[Candidate]:
        response = self._engine.search(query, category=category, limit=max_results)
        return [
            Candidate(
                title=r.title,
                url=r.url,
                summary=r.snippet,
                source=r.source,
                published_iso=r.published.isoformat() if r.published else None,
                trusted=r.trusted,
            )
            for r in response.results
        ]

    def healthy(self, query: str = "connectivity check") -> bool:
        """True when at least one source currently answers."""
        response = self._engine.search(query, limit=1)
        return any(status == "ok" for status in response.health.values())
```

Async hosts call `await self._engine.asearch(...)` instead — same signature,
same response — and should build one provider per process, not per request.

## Config mapping

Map your application's settings onto `ScoutConfig` keys rather than exposing
a second config file:

| your app probably has | SCOUT config key |
|---|---|
| a request timeout | `timeout` |
| an allow/deny list of sources | `sources: {name: {enabled: bool}}` |
| a list of publishers you trust | `trusted_outlets` |
| custom news feeds | `rss_outlets` |
| a "no external relays" privacy switch | leave `searxng_public` disabled (the default) |

```python
def scout_config_from(app_settings) -> dict:
    return {
        "timeout": app_settings.http_timeout_seconds,
        "trusted_outlets": app_settings.trusted_publishers,
        "sources": {name: {"enabled": False} for name in app_settings.blocked_sources},
    }
```

## Choosing categories per intent

If your host distinguishes query intents, pass a category instead of
filtering afterwards — disabled sources aren't queried at all:

```python
CATEGORY_BY_INTENT = {
    "current_events": "news",
    "background": "knowledge",
    "literature": "science",
    "dead_link": "archive",
}
```

For a dead-link recovery flow, pass the URL itself as the query with
`category="archive"`: the Wayback source answers URL-shaped queries with the
closest archived snapshot.

## Testing your integration

- **Unit tests: use offline mode.** `Scout(offline=True)` (or
  `{"offline": true}` in config) answers every query deterministically from a
  built-in fixture source with zero network — your provider, mapping, and
  plumbing get exercised end to end:

  ```python
  def test_provider_maps_fields():
      provider = WebSearchProvider({"offline": True})
      candidates = provider.search("anything")
      assert candidates and candidates[0].url.startswith("https://")
  ```

- **Don't mock SCOUT's internals.** Offline mode exists so you never have to
  patch adapters or HTTP clients in host-application tests.
- **Keep live tests out of CI.** If you want a periodic real-network check,
  gate it behind an env var the way SCOUT's own live smoke test is gated
  (`SCOUT_LIVE_TEST=1`).
- **Watch health in production.** Log `response.health` on empty results;
  it distinguishes "the web has nothing" from "sources are blocking us".

## Operational notes

- One `Scout` instance shares one rate limiter: many concurrent searches in
  one process still respect per-source budgets. Multiple processes multiply
  load — slow the per-source `rate_limit` down accordingly.
- Results arrive interleaved by source; if you re-rank, `raw_rank` preserves
  each source's own opinion and `also_found_in` tells you when several
  sources agree on a document (a useful relevance signal).
- SCOUT sends an honest User-Agent naming this repository. If you fork or
  rebrand, set `user_agent` in config to identify *your* application honestly.
