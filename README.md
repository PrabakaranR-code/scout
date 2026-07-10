# SCOUT — Source Collection & Outreach Utility Tool

Keyless, multi-source web search as a plain Python library and CLI.

SCOUT queries scrape-tolerant search engines, free knowledge APIs, news RSS
feeds, and archives — **in parallel, directly from your machine** — and returns
one merged, deduplicated, metadata-rich result list. It is the zero-install
alternative to running a metasearch server:

- **No Docker, no containers, no server process.** Pure in-process Python.
- **No API keys required.** Every default source works with no account.
  Optional keys (currently The Guardian) unlock extra sources.
- **Polite by design.** Per-source rate limits, an honest User-Agent,
  robots.txt respected for scraped engines, per-source timeouts.
- **Degrade, never die.** Any source failing, timing out, or blocking simply
  contributes nothing; a search succeeds if at least one source responds.

SCOUT finds candidates; it never fetches full pages, never ranks by opinion,
never answers questions. Host applications do their own reading and ranking.

## Install

```
pip install git+https://github.com/PrabakaranR-code/scout
```

Python 3.11+. Dependencies: httpx, pydantic, feedparser, pyyaml.

## Quickstart — library

```python
from scout import Scout

engine = Scout()                      # defaults; reads ./scout.yaml if present
response = engine.search("solar sail propulsion", limit=10)

for result in response.results:
    print(result.title, result.url, result.source)

print(response.health)                # {"mojeek": "ok", "startpage": "timeout", ...}
```

Async callers use `await engine.asearch(...)` with the same signature.
Narrow a search with `category=` (`general`, `news`, `science`, `knowledge`,
`archive`) or `sources=["wikipedia", "rss"]` (naming a source runs it even if
it is disabled by default).

Every result is a `SearchResult`:

| field | meaning |
|---|---|
| `title`, `url`, `snippet` | what the source returned (snippet may be empty) |
| `source` | adapter name, e.g. `mojeek` or `rss:aljazeera` |
| `category` | `general` / `news` / `science` / `knowledge` / `archive` |
| `published` | best-effort publication datetime, or `None` |
| `trusted` | `True` when the URL matches your `trusted_outlets` list |
| `raw_rank` | the position the source itself assigned |
| `also_found_in` | other sources that returned the same document |

## Quickstart — CLI

```
scout "solar sail propulsion"                 # human-readable, numbered, health footer
scout "election fact check" --category news
scout "test" --json                           # full SearchResponse as JSON
scout "quantum dots" --sources wikipedia,arxiv --limit 10
scout sources                                 # list adapters and enabled/disabled state
```

## Sources

| source | category | keyless | how it is queried | politeness notes |
|---|---|---|---|---|
| `mojeek` | general | yes | HTML results page | robots.txt honored; ≤0.5 req/s |
| `brave` | general | yes | HTML results page | robots.txt honored; ≤0.5 req/s |
| `duckduckgo` | general | yes | plain-HTML endpoint (reaches Bing's index) | robots.txt honored; redirect links unwrapped; ads dropped |
| `startpage` | general | yes | HTML results page (reaches Google's index) | best-effort: expected to degrade first; extra-slow 0.25 req/s |
| `marginalia` | general | yes | public JSON API | non-commercial small web; 1 req/s |
| `wikipedia` | knowledge | yes | official MediaWiki search API | 2 req/s |
| `arxiv` | science | yes | official Atom API | 1 request per 3 s, per arXiv guidance |
| `pubmed` | science | yes | official NCBI E-utilities | well under NCBI's keyless allowance |
| `wayback` | archive | yes | availability API | only answers URL-shaped queries |
| `rss` | news | yes | outlet feed table (see below) | one sweep per search; dead feeds skipped |
| `gdelt` | news | yes | GDELT DOC 2.0 API | 0.5 req/s |
| `guardian` | news | key | Guardian Open Platform | activates only when `GUARDIAN_API_KEY` is set |
| `searxng_public` | general | yes | volunteer-run public SearXNG instances | **OFF by default** — see Privacy |

Google and Bing are never scraped directly; their indexes are only reached
through services that expose them deliberately.

Default RSS outlets: Al Jazeera, Reuters, BBC, AP, NPR, DW, France24,
The Hindu, plus fact-checkers AFP Fact Check and Full Fact. Replace the whole
table with `rss_outlets` in config.

## Configuration

Configuration comes from keyword arguments, a dict, or a `scout.yaml` file
(auto-loaded from the working directory when present).

```yaml
# scout.yaml — everything optional
timeout: 8            # default per-source timeout, seconds
trusted_outlets:      # mark results from these domains trusted: true
  - reuters.com
  - apnews.com
sources:
  startpage:
    enabled: false    # turn any source off...
  searxng_public:
    enabled: true     # ...or opt in to the booster
  rss:
    timeout: 12       # per-source overrides
    rate_limit: 0.5   # requests per second
rss_outlets:          # replaces the default outlet table entirely
  aljazeera: https://www.aljazeera.com/xml/rss/all.xml
  bbc: https://feeds.bbci.co.uk/news/world/rss.xml
searxng_instances:    # instances for searxng_public, rotated per request
  - https://searx.example
offline: false        # true = fixture source only, zero network (for tests)
```

`Scout(timeout=5)`, `Scout({"timeout": 5})`, and `Scout("path/to/scout.yaml")`
all work; keyword arguments override file values.

## Privacy

Every default source is queried **directly from your machine to the official
service** — no relay, no aggregator, no telemetry. What each service sees is
an ordinary request from your IP with the honest User-Agent
`SCOUT/<version> (+this repo URL)`.

The one exception is `searxng_public`, which relays queries through
volunteer-run public SearXNG instances: the instance operator can see your
query and IP. That trade-off is why it ships **disabled**; enable it only if
you accept it.

## Adding an adapter (the contribution path)

1. Create `scout/adapters/yourname.py` with a `BaseAdapter` subclass. Declare
   `name`, `category`, `default_enabled`, `rate_limit`, and (if needed)
   `timeout` / `requires_env` / `scrapes_html`.
2. Implement the two halves:
   - `async fetch(client, query, limit)` — one polite HTTP round-trip. Use
     `self.get(...)`: it sends the honest User-Agent, checks robots.txt for
     scraped engines, and maps blocking statuses to the right errors.
   - `parse(raw, query, limit) -> list[SearchResult]` — build results with
     `self.make_result(...)`. **Must degrade on malformed input** — return
     what you can salvage, never raise on bad markup or missing fields.
3. Register the module path in `_ADAPTER_MODULES` in `scout/adapters/__init__.py`.
4. Add a saved response fixture under `tests/fixtures/` plus tests: one that
   parses the fixture, one that feeds malformed payloads (see any existing
   adapter test for the pattern). CI must stay free of live network calls.
5. Pick targets responsibly: official APIs first, scrape-tolerant HTML only,
   never a ToS-hostile endpoint.

## Integrating SCOUT into an application

See [docs/INTEGRATION.md](docs/INTEGRATION.md) for a copy-pasteable search
provider, config mapping, and testing advice.

## License

MIT — see [LICENSE](LICENSE).
