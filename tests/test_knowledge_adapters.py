"""Fixture parsing tests for knowledge, science, and archive adapters (§4.B)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from scout.adapters.arxiv import ArxivAdapter
from scout.adapters.pubmed import PubMedAdapter
from scout.adapters.wayback import WaybackAdapter, looks_like_url
from scout.adapters.wikipedia import WikipediaAdapter
from scout.config import ScoutConfig

FIXTURES = Path(__file__).parent / "fixtures"


def load(name: str) -> str:
    return (FIXTURES / name).read_text(encoding="utf-8")


@pytest.fixture()
def config() -> ScoutConfig:
    return ScoutConfig()


class TestWikipedia:
    def test_parses_fixture(self, config: ScoutConfig) -> None:
        raw = json.loads(load("wikipedia.json"))
        results = WikipediaAdapter(config).parse(raw, "solar sail", 10)
        assert len(results) == 2  # the title-less entry is skipped
        first = results[0]
        assert first.title == "Solar sail"
        assert first.url == "https://en.wikipedia.org/wiki/Solar_sail"
        assert "<span" not in first.snippet  # highlight markup stripped
        assert "solar sail is a method" in first.snippet
        assert first.category == "knowledge"
        assert first.published is not None and first.published.year == 2026

    @pytest.mark.parametrize(
        "payload",
        [None, "x", 3, {}, {"query": None}, {"query": {"search": "no"}},
         {"query": {"search": [None, 4]}}],
    )
    def test_malformed_degrades(self, config: ScoutConfig, payload) -> None:
        assert WikipediaAdapter(config).parse(payload, "q", 10) == []


class TestArxiv:
    def test_parses_fixture(self, config: ScoutConfig) -> None:
        results = ArxivAdapter(config).parse(load("arxiv.xml"), "solar sail", 10)
        assert len(results) == 2
        first = results[0]
        assert first.title == "Attitude control strategies for large solar sails"
        assert first.url == "http://arxiv.org/abs/2601.01234v1"
        assert first.snippet.startswith("We survey momentum-management")
        assert first.category == "science"
        assert first.published is not None and first.published.month == 1

    @pytest.mark.parametrize("payload", [None, 5, {}, [], "", "<<<not xml"])
    def test_malformed_degrades(self, config: ScoutConfig, payload) -> None:
        assert ArxivAdapter(config).parse(payload, "q", 10) == []

    def test_respects_arxiv_request_spacing(self, config: ScoutConfig) -> None:
        assert ArxivAdapter(config).effective_rate_limit <= 1 / 3


class TestPubMed:
    def test_parses_fixture(self, config: ScoutConfig) -> None:
        raw = {
            "esummary": json.loads(load("pubmed_esummary.json")),
            "ids": ["38012345", "37654321"],
        }
        results = PubMedAdapter(config).parse(raw, "circadian light", 10)
        assert len(results) == 2
        first = results[0]
        assert first.url == "https://pubmed.ncbi.nlm.nih.gov/38012345/"
        assert "Circadian regulation" in first.title
        assert "Journal of Experimental Biology" in first.snippet
        assert first.published is not None and first.published.year == 2026
        # year-only pubdate still parses
        assert results[1].published is not None
        assert results[1].published.year == 2025

    @pytest.mark.parametrize(
        "payload",
        [None, "x", {}, {"esummary": None}, {"esummary": {"result": "no"}},
         {"esummary": {"result": {"uids": ["1"], "1": None}}}],
    )
    def test_malformed_degrades(self, config: ScoutConfig, payload) -> None:
        assert PubMedAdapter(config).parse(payload, "q", 10) == []


class TestWayback:
    def test_parses_fixture(self, config: ScoutConfig) -> None:
        raw = json.loads(load("wayback.json"))
        results = WaybackAdapter(config).parse(raw, "example.org/old-page", 10)
        assert len(results) == 1
        result = results[0]
        assert result.url.startswith("http://web.archive.org/web/20240101")
        assert result.category == "archive"
        assert result.published is not None and result.published.year == 2024

    def test_url_detection(self) -> None:
        assert looks_like_url("example.org")
        assert looks_like_url("https://example.org/page")
        assert looks_like_url("sub.domain.example.co.uk/x?y=1")
        assert not looks_like_url("solar sail propulsion")
        assert not looks_like_url("what is a url")

    def test_non_url_query_contributes_nothing(self, config: ScoutConfig) -> None:
        # fetch() short-circuits to None for text queries; parse degrades
        assert WaybackAdapter(config).parse(None, "plain text", 10) == []

    @pytest.mark.parametrize(
        "payload",
        [None, 1, "x", {}, {"archived_snapshots": {}},
         {"archived_snapshots": {"closest": {"available": False}}},
         {"archived_snapshots": {"closest": {"available": True, "url": "junk"}}}],
    )
    def test_malformed_degrades(self, config: ScoutConfig, payload) -> None:
        assert WaybackAdapter(config).parse(payload, "example.org", 10) == []
