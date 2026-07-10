"""Result schema shared by every adapter and the core engine."""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Literal

from pydantic import BaseModel, Field

Category = Literal["general", "news", "science", "knowledge", "archive"]

CATEGORIES: tuple[str, ...] = ("general", "news", "science", "knowledge", "archive")


class HealthStatus(str, Enum):
    """Per-source outcome of a search fan-out."""

    OK = "ok"
    ERROR = "error"
    TIMEOUT = "timeout"
    DISABLED = "disabled"


class SearchResult(BaseModel):
    """A single candidate result returned by one source.

    SCOUT only collects candidates: it never fetches the full page and never
    ranks by opinion. ``raw_rank`` is the position the source itself assigned.
    """

    title: str
    url: str
    snippet: str = ""
    source: str
    category: Category = "general"
    published: datetime | None = None
    trusted: bool = False
    raw_rank: int = 0
    also_found_in: list[str] = Field(default_factory=list)


class SearchResponse(BaseModel):
    """The merged, deduplicated answer to one query."""

    query: str
    results: list[SearchResult] = Field(default_factory=list)
    health: dict[str, HealthStatus] = Field(default_factory=dict)
    elapsed_ms: int = 0
