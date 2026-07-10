"""Fixture-based parsing tests for the general-web engine adapters (§4.A).

Zero live network: every test feeds a saved payload straight to ``parse``.
Each adapter also gets a malformed-response test (§10): the parser must
degrade to an empty (or partial) list, never crash.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from scout.adapters.brave import BraveAdapter
from scout.adapters.duckduckgo import DuckDuckGoAdapter
from scout.adapters.marginalia import MarginaliaAdapter
from scout.adapters.mojeek import MojeekAdapter
from scout.adapters.startpage import StartpageAdapter
from scout.config import ScoutConfig

FIXTURES = Path(__file__).parent / "fixtures"

MALFORMED_PAYLOADS = [
    "",
    "<html><body><p>totally unrelated page",
    "<div class='result'><a href='relative/link'>no scheme</a>",
    "<<<>>> not even html &&& <ul><li><li></ul></zzz>",
    None,
    12345,
]


def load(name: str) -> str:
    return (FIXTURES / name).read_text(encoding="utf-8")


@pytest.fixture()
def config() -> ScoutConfig:
    return ScoutConfig()


class TestMojeek:
    def test_parses_fixture(self, config: ScoutConfig) -> None:
        results = MojeekAdapter(config).parse(load("mojeek.html"), "solar sail", 10)
        assert len(results) == 3  # the javascript: pseudo-result is dropped
        first = results[0]
        assert first.title == "Solar sails explained"
        assert first.url == "https://example-space.org/solar-sails"
        assert "radiation pressure" in first.snippet
        assert first.source == "mojeek"
        assert first.category == "general"
        assert [r.raw_rank for r in results] == [1, 2, 3]

    @pytest.mark.parametrize("payload", MALFORMED_PAYLOADS)
    def test_malformed_degrades(self, config: ScoutConfig, payload) -> None:
        assert MojeekAdapter(config).parse(payload, "q", 10) == []


class TestDuckDuckGo:
    def test_parses_fixture_and_unwraps_redirects(self, config: ScoutConfig) -> None:
        results = DuckDuckGoAdapter(config).parse(
            load("duckduckgo.html"), "solar sail", 10
        )
        assert len(results) == 2  # the ad entry is dropped
        assert results[0].url == "https://example-space.org/solar-sails"
        assert results[0].title == "Solar sails explained"
        assert "radiation pressure" in results[0].snippet
        assert results[1].url == "https://direct.example.net/sail-faq"

    @pytest.mark.parametrize("payload", MALFORMED_PAYLOADS)
    def test_malformed_degrades(self, config: ScoutConfig, payload) -> None:
        assert DuckDuckGoAdapter(config).parse(payload, "q", 10) == []


class TestBrave:
    def test_parses_fixture(self, config: ScoutConfig) -> None:
        results = BraveAdapter(config).parse(load("brave.html"), "solar sail", 10)
        assert len(results) == 2  # the linkless infobox is dropped
        assert results[0].title == "Solar sails explained"
        assert results[0].url == "https://example-space.org/solar-sails"
        assert "propellant" in results[0].snippet
        assert results[1].title == "Sail missions timeline"

    @pytest.mark.parametrize("payload", MALFORMED_PAYLOADS)
    def test_malformed_degrades(self, config: ScoutConfig, payload) -> None:
        assert BraveAdapter(config).parse(payload, "q", 10) == []


class TestStartpage:
    def test_parses_fixture(self, config: ScoutConfig) -> None:
        results = StartpageAdapter(config).parse(
            load("startpage.html"), "solar sail", 10
        )
        assert len(results) == 2  # the internal-navigation entry is dropped
        assert results[0].title == "Solar sails explained"
        assert results[1].url == "https://library.example.org/sail-history"

    @pytest.mark.parametrize("payload", MALFORMED_PAYLOADS)
    def test_malformed_degrades(self, config: ScoutConfig, payload) -> None:
        assert StartpageAdapter(config).parse(payload, "q", 10) == []

    def test_startpage_is_extra_cautious(self, config: ScoutConfig) -> None:
        # best-effort source (§4.A): slowest politeness budget of the engines
        assert StartpageAdapter(config).effective_rate_limit <= 0.5


class TestMarginalia:
    def test_parses_fixture(self, config: ScoutConfig) -> None:
        raw = json.loads(load("marginalia.json"))
        results = MarginaliaAdapter(config).parse(raw, "solar sail", 10)
        assert len(results) == 2  # non-http and non-object entries dropped
        assert results[0].title.startswith("Notes on building")
        assert results[0].snippet.startswith("Hobbyist writeup")

    @pytest.mark.parametrize(
        "payload",
        [None, "a string", 7, {}, {"results": "not-a-list"}, {"results": [None, 5]}],
    )
    def test_malformed_degrades(self, config: ScoutConfig, payload) -> None:
        assert MarginaliaAdapter(config).parse(payload, "q", 10) == []


def test_all_engine_adapters_registered() -> None:
    from scout.adapters import all_adapters

    names = set(all_adapters())
    assert {"mojeek", "brave", "duckduckgo", "startpage", "marginalia"} <= names


def test_scraping_engines_declare_politeness(config: ScoutConfig) -> None:
    """§9.5 politeness audit: scraped engines rate-limit and honor robots."""
    for cls in (MojeekAdapter, BraveAdapter, DuckDuckGoAdapter, StartpageAdapter):
        adapter = cls(config)
        assert adapter.scrapes_html is True
        assert 0 < adapter.effective_rate_limit <= 1.0
        assert adapter.request_headers()["User-Agent"].startswith("SCOUT/")


def test_no_google_or_bing_endpoints() -> None:
    """§9.5: Google and Bing are never scraped directly."""
    import scout as scout_pkg

    package_dir = Path(scout_pkg.__file__).parent
    offenders = []
    for path in package_dir.rglob("*.py"):
        text = path.read_text(encoding="utf-8")
        for fragment in ("google.com/search", "bing.com/search", "www.bing.com"):
            if fragment in text:
                offenders.append(f"{path.name}: {fragment}")
    assert offenders == []
