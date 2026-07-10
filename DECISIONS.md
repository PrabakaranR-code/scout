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
