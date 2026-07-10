"""SCOUT — Source Collection & Outreach Utility Tool.

Keyless, multi-source web search as a plain Python library: scrape-tolerant
search engines, free knowledge APIs, news RSS feeds, and archives, queried in
parallel from the caller's machine and merged into one deduplicated list.

No servers, no containers, no API keys required.
"""

__version__ = "0.1.0"

REPO_URL = "https://github.com/PrabakaranR-code/scout"
USER_AGENT = f"SCOUT/{__version__} (+{REPO_URL})"

from scout.config import ScoutConfig
from scout.schema import Category, HealthStatus, SearchResponse, SearchResult

__all__ = [
    "Category",
    "HealthStatus",
    "REPO_URL",
    "Scout",
    "ScoutConfig",
    "SearchResponse",
    "SearchResult",
    "USER_AGENT",
    "__version__",
]


def __getattr__(name: str):  # pragma: no cover - trivial lazy import
    # Imported lazily so that `import scout` stays cheap and avoids a
    # circular import between scout.core and scout.adapters.
    if name == "Scout":
        from scout.core import Scout

        return Scout
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
