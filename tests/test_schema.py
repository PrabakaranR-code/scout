"""Schema tests (§3)."""

from __future__ import annotations

from datetime import datetime, timezone

import pytest
from pydantic import ValidationError

from scout.schema import HealthStatus, SearchResponse, SearchResult


def test_search_result_minimal_fields() -> None:
    r = SearchResult(title="Example", url="https://example.org/", source="mojeek")
    assert r.snippet == ""
    assert r.category == "general"
    assert r.published is None
    assert r.trusted is False
    assert r.raw_rank == 0
    assert r.also_found_in == []


def test_search_result_full_fields() -> None:
    when = datetime(2026, 1, 2, 3, 4, 5, tzinfo=timezone.utc)
    r = SearchResult(
        title="A paper",
        url="https://arxiv.org/abs/1234.5678",
        snippet="An abstract.",
        source="arxiv",
        category="science",
        published=when,
        trusted=True,
        raw_rank=3,
        also_found_in=["wikipedia"],
    )
    assert r.published == when
    assert r.category == "science"
    assert r.also_found_in == ["wikipedia"]


def test_search_result_rejects_bad_category() -> None:
    with pytest.raises(ValidationError):
        SearchResult(
            title="x", url="https://example.org", source="s", category="opinions"
        )


def test_search_result_parses_iso_published() -> None:
    r = SearchResult(
        title="x",
        url="https://example.org",
        source="s",
        published="2026-05-01T12:00:00Z",
    )
    assert r.published is not None
    assert r.published.year == 2026


def test_search_response_defaults() -> None:
    resp = SearchResponse(query="hello")
    assert resp.results == []
    assert resp.health == {}
    assert resp.elapsed_ms == 0


def test_search_response_health_statuses() -> None:
    resp = SearchResponse(
        query="q",
        health={
            "mojeek": HealthStatus.OK,
            "startpage": HealthStatus.TIMEOUT,
            "guardian": HealthStatus.DISABLED,
            "brave": HealthStatus.ERROR,
        },
    )
    dumped = resp.model_dump()
    assert dumped["health"]["mojeek"] == "ok"
    assert dumped["health"]["startpage"] == "timeout"
    assert dumped["health"]["guardian"] == "disabled"
    assert dumped["health"]["brave"] == "error"


def test_search_response_json_round_trip() -> None:
    resp = SearchResponse(
        query="q",
        results=[
            SearchResult(title="t", url="https://example.org", source="mojeek")
        ],
        health={"mojeek": HealthStatus.OK},
        elapsed_ms=12,
    )
    again = SearchResponse.model_validate_json(resp.model_dump_json())
    assert again == resp
