# Changelog

## v0.1.0 — first release

Keyless, multi-source web search as a plain Python library and CLI. No
servers, no containers, no API keys required.

### Core

- Parallel async fan-out across all enabled sources with per-source timeouts;
  failures, timeouts, and blocks are isolated — a search succeeds if at least
  one source responds.
- Round-robin merge (by source, then each source's own rank) so no single
  source dominates the top of the list.
- URL-normalizing dedupe (tracking parameters, `www.`, scheme, trailing
  slash, fragment, parameter order); the richer duplicate wins, contributing
  sources are recorded in `also_found_in`.
- Health map for every source (`ok` / `error` / `timeout` / `disabled`) on
  every response.
- Politeness layer: per-source rate limits, honest
  `SCOUT/<version> (+repo URL)` User-Agent, robots.txt honored for scraped
  engines. Google and Bing are never scraped directly.
- Configuration via kwargs, dict, or `scout.yaml`; trusted-outlet marking;
  offline fixture mode for tests.

### Sources

- General web: `mojeek`, `brave`, `duckduckgo`, `startpage` (best-effort),
  `marginalia`.
- Knowledge & science: `wikipedia`, `arxiv`, `pubmed`, `wayback`.
- News: `rss` (Al Jazeera, Reuters, BBC, AP, NPR, DW, France24, The Hindu,
  AFP Fact Check, Full Fact — fully configurable), `gdelt`, and optional
  keyed `guardian` (`GUARDIAN_API_KEY`).
- Booster: `searxng_public` — public SearXNG instance relay, **off by
  default** for privacy.

### CLI

- `scout "query" [--category] [--limit] [--sources] [--json] [--config]
  [--offline]` and `scout sources`.

### Docs & quality

- README with source table, config reference, privacy section, and adapter
  contribution guide; `docs/INTEGRATION.md` for embedding SCOUT in host
  applications; `DECISIONS.md` design log.
- 194 offline tests (plus an env-gated live smoke test) on Python 3.11 and
  3.12; every adapter has malformed-response degradation coverage.
