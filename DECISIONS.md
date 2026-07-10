# DECISIONS.md — ambiguity-rule log (PLAN.md §0.3)

One line per choice made where the spec was silent.

- Repo started empty: `main` was created from the initial PLAN.md commit via the
  GitHub API so the per-phase PR + auto-merge workflow has a base branch; the
  development branch remains `claude/create-plan-md-j6dide` as instructed.
- Build backend: setuptools (simplest standard choice; no extra dependency).
- Pydantic v2 API (`model_validate`, `ConfigDict`) — current stable major.
- Added a tiny `offline` config flag (no network; fixture-backed source only) to
  make acceptance check §9.2 (`scout "test" --json` offline) possible.
- HTML engine responses are parsed with the stdlib `html.parser` — no
  BeautifulSoup/lxml dependency, per the minimal-deps principle (§2.6).
- `SCOUT_NO_AUTOCONFIG` env var lets tests disable auto-loading of a
  `./scout.yaml` sitting in the working directory.
- `limit` caps the final merged list (and is the per-source ask); round-robin
  keeps the head balanced across sources.
- The health map covers every registered adapter; non-participating sources
  (disabled, filtered by category, or not in `sources=`) report `disabled`.
- Passing `sources=[...]` explicitly runs those adapters even if disabled by
  default/config; only a missing required env var still vetoes.
- Marginalia is queried via its public JSON API (keyless) instead of scraping
  its HTML — official endpoint, simpler parser.
- `wayback` contributes only when the query looks like a URL/domain (the
  availability API answers per-URL, not free-text); otherwise returns nothing.
- PubMed needs two E-utilities calls (esearch then esummary); both run inside
  the adapter's single fan-out slot and timeout.
- DuckDuckGo results hosted on duckduckgo.com itself (ads/internal) are
  dropped; redirect links are unwrapped via their `uddg` parameter.
- RSS relevance: every query term longer than 2 chars must appear in
  title+summary (case-insensitive); matches ordered newest first.
- Timeout precedence: per-source config override > adapter class default >
  config-wide `timeout`.
