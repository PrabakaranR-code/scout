# PLAN.md — SCOUT (Source Collection & Outreach Utility Tool)

Build specification. Execute top to bottom, autonomously, start to finish. All code,
prompts, and docs are written from scratch for this repository. Do not copy code
from, or refer by name to, any other project or person anywhere in code, comments,
commits, or documentation (naming the public services SCOUT queries — e.g. Mojeek,
Wikipedia, SearXNG instances — is of course fine and required).

---

## 0. STANDING AUTHORITY — NO QUESTIONS BACK TO THE OWNER

1. **Auto-merge:** every PR merges automatically once CI is green on Python 3.11
   and 3.12. Never wait for approval. Never ask "should I merge/release/continue".
2. **Blocked only if truly blocked:** if a test cannot be made green or the spec
   must be violated, first attempt a documented workaround; stop and ask only if
   genuinely impossible. Anything else: decide and proceed.
3. **Ambiguity rule:** where this spec is silent, choose the simplest option
   consistent with its principles, record one line in `DECISIONS.md`, continue.
4. **Self-testing:** you run all acceptance checks yourself (§9). Never ask the
   owner to test.
5. **No watchers:** no PR-watch jobs, no scheduled check-ins. Work, finish,
   unsubscribe, report once.
6. **Finish line:** when §9 passes, tag and publish GitHub release **v0.1.0**
   with a changelog, then post a single final report that begins with the word
   **COMPLETE** and contains: phase summary, test counts, the three acceptance-run
   results, and the repo's install line.

## 1. MISSION

SCOUT is a standalone, pip-installable Python library + CLI that performs
keyless, multi-source web search with zero external services: no Docker, no
containers, no server process, no API keys required (optional keys unlock extra
sources). It queries scrape-tolerant search engines, free knowledge APIs, news
RSS feeds, and archives — in parallel, directly from the caller's machine — and
returns one merged, deduplicated, metadata-rich result list. It is the
zero-install alternative to running a metasearch server.

SCOUT finds candidates; it never fetches full pages, never ranks by opinion,
never answers questions. Host applications do their own reading and ranking.

## 2. HARD PRINCIPLES

1. **Keyless by default.** Every default source works with no account and no key.
   Optional keyed sources activate only when their env var is present.
2. **Polite by design.** Per-source rate limits, honest User-Agent
   ("SCOUT/<version> (+repo URL)"), robots.txt respected for scraped engines,
   per-source timeouts. No ToS-hostile targets: Google and Bing are never
   scraped directly.
3. **Degrade, never die.** Any source failing, timing out, or blocking returns
   an empty contribution and a health note. A search succeeds if at least one
   source responds.
4. **Privacy stance.** All queries go direct from the user's machine to the
   official service. The public-instance relay source (§4.D) is OFF by default
   and documented as a privacy trade-off.
5. **In-process only.** Pure Python library. No daemon, no port, nothing to
   install besides `pip install`.
6. **Plain code.** Python 3.11+, type-hinted, minimal deps: httpx, pydantic,
   feedparser, pyyaml (CLI config), pytest for tests. Nothing else without a
   DECISIONS.md entry.

## 3. RESULT SCHEMA (pydantic, used by every adapter)

```
SearchResult:
  title: str
  url: str
  snippet: str                  # may be empty for some feeds
  source: str                   # adapter name, e.g. "mojeek", "rss:aljazeera"
  category: general|news|science|knowledge|archive
  published: datetime | None    # best effort
  trusted: bool                 # True when from the user's trusted list (§5)
  raw_rank: int                 # position given by the source itself
SearchResponse:
  query, results: list[SearchResult], health: dict[source -> ok|error|timeout|disabled],
  elapsed_ms
```

## 4. ADAPTERS (one file each in `scout/adapters/`, common base class)

**A. General-web engines (HTML endpoints, scrape-tolerant):**
mojeek, brave, duckduckgo (its HTML endpoint; effectively reaches Bing's index),
startpage (best-effort; reaches Google's index; expected to be the first to
degrade — code must tolerate that), marginalia (non-commercial web).

**B. Knowledge & science APIs (official, keyless):**
wikipedia (search API), arxiv (API), pubmed (E-utilities), wayback (availability
API for archived copies).

**C. News:**
- `rss` — generic feed adapter driven by a configurable outlet table
  (name → feed URL). Ship defaults: Al Jazeera, Reuters, BBC, AP, NPR, DW,
  France24, The Hindu, plus fact-checker feeds (AFP Fact Check, Full Fact).
  Relevance = query-term match against title/summary of recent items.
- `gdelt` — free API, world news at scale.
- `guardian` — optional: activates only if GUARDIAN_API_KEY env var exists.

**D. Booster (off by default):**
`searxng_public` — queries public SearXNG instances from a configurable list,
rotating between them. Disabled unless the user explicitly enables it in config;
docstring and README state the privacy trade-off (queries transit a volunteer's
server).

Each adapter declares: name, category, default_enabled, rate_limit, timeout, and
implements `search(query, limit) -> list[SearchResult]` plus fixture-based
parsing tests.

## 5. CORE ENGINE (`scout/core.py`)

- `Scout(config)` — config from kwargs, dict, or scout.yaml: enabled sources,
  per-source overrides, trusted_outlets list (marks `trusted=True`), timeouts,
  public-instance list.
- `search(query, category="all", limit=20, sources=None)` — sync facade over an
  async fan-out: all enabled adapters queried in parallel, each within its own
  timeout; failures isolated (§2.3).
- **Merge:** interleave by source then raw_rank (round-robin) so no single
  source dominates the top.
- **Dedupe:** normalize URLs (strip tracking params, trailing slashes, scheme);
  on collision keep the richer result (longer snippet/has date), record both
  sources in a `also_found_in` field.
- Health map always returned; a logger warning names any silent source.

## 6. CLI (`scout` entry point)

`scout "query" [--category news] [--limit 20] [--sources mojeek,rss] [--json]`
Human output: numbered results with source tags and health footer.
`--json` prints the full SearchResponse. `scout sources` lists adapters and
their enabled/disabled state.

## 7. DOCS

- README: what/why, install (`pip install git+https://github.com/<owner>/scout`),
  quickstart (library + CLI), source table with politeness notes, config
  reference, privacy section, "adding an adapter" guide (the contribution path).
- `docs/INTEGRATION.md` — generic guide for embedding SCOUT as a search backend
  inside any host application: a complete, copy-pasteable example implementing a
  `search(query) -> results` provider on top of SCOUT, config mapping, and test
  advice. Written for any host; no specific project named.
- `DECISIONS.md` — running log of ambiguity-rule choices.

## 8. BUILD ORDER (commit + PR + auto-merge per phase)

- **A. CI first + scaffold:** .github/workflows/ci.yml (pytest on 3.11 & 3.12,
  push to main + PRs) so auto-merge works from the first PR; package skeleton
  (pyproject.toml — distribution name `scout-search`, import name `scout`),
  schema, adapter base, config loading, empty CLI. Tests for schema/config.
- **B. Core engine:** parallel fan-out, merge, dedupe, health, rate limiter.
  Unit tests with stub adapters (success, timeout, failure, dedupe collisions).
- **C. Engine adapters (§4.A):** each with saved-fixture parsing tests; zero
  live network in CI.
- **D. Knowledge, news, archive adapters (§4.B + C):** fixtures likewise; RSS
  default outlet table; guardian behind env flag.
- **E. Booster + CLI + docs:** searxng_public (default off), CLI, README,
  INTEGRATION.md.
- **F. Acceptance + release:** run §9; on pass, tag v0.1.0, GitHub release with
  changelog, final COMPLETE report.

## 9. ACCEPTANCE (self-run; all must pass)

1. Full pytest suite green on 3.11 and 3.12 in CI.
2. Fresh-venv install from the repo (`pip install .`) then `scout "test" --json`
   using a fixture/offline mode returns a valid SearchResponse.
3. Stub-based end-to-end: 3 sources respond + 1 times out + 1 errors → search
   succeeds, health map correct, dedupe verified.
4. `searxng_public` verified disabled by default; enabling via config works.
5. Politeness audit: every scraping adapter has rate limit + honest UA + robots
   check; grep-test enforces no google.com/bing.com scraping endpoints.
6. **Stability rule: run the entire acceptance sequence (1–5) three consecutive
   times; all three must pass.** Record the three runs in the final report.
7. Optional (not gating): a live smoke test behind SCOUT_LIVE_TEST=1 exists for
   humans to run later; excluded from CI.

## 10. QUALITY BAR

Type hints throughout; docstrings on public API; no secrets anywhere in the
repo; idempotent config handling; MIT license; every adapter ships with at least
one malformed-response test (parser must degrade, not crash).
