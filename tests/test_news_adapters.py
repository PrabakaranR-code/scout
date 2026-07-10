"""Fixture parsing tests for the news adapters (§4.C)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from scout.adapters.gdelt import GdeltAdapter
from scout.adapters.guardian import GuardianAdapter
from scout.adapters.rss import DEFAULT_OUTLETS, RSSAdapter
from scout.config import ScoutConfig

FIXTURES = Path(__file__).parent / "fixtures"


def load(name: str) -> str:
    return (FIXTURES / name).read_text(encoding="utf-8")


@pytest.fixture()
def config() -> ScoutConfig:
    return ScoutConfig()


class TestRSS:
    def raw(self) -> list[tuple[str, str]]:
        return [
            ("worldnews", load("rss_worldnews.xml")),
            ("factcheck", load("rss_factcheck.xml")),
        ]

    def test_matches_query_terms_across_outlets(self, config: ScoutConfig) -> None:
        results = RSSAdapter(config).parse(self.raw(), "flood", 10)
        # 2 flood items in worldnews + 1 in factcheck; grain/vaccine items excluded
        assert len(results) == 3
        assert {r.source for r in results} == {"rss:worldnews", "rss:factcheck"}
        assert all(r.category == "news" for r in results)
        # newest first
        dates = [r.published for r in results]
        assert dates == sorted(dates, reverse=True)
        assert [r.raw_rank for r in results] == [1, 2, 3]

    def test_multi_term_queries_require_all_terms(self, config: ScoutConfig) -> None:
        results = RSSAdapter(config).parse(self.raw(), "flood insurance", 10)
        assert len(results) == 1
        assert results[0].url == "https://outlet-one.example/news/flood-insurance"

    def test_no_match_returns_empty(self, config: ScoutConfig) -> None:
        assert RSSAdapter(config).parse(self.raw(), "cryptocurrency", 10) == []

    def test_default_outlet_table_shipped(self, config: ScoutConfig) -> None:
        adapter = RSSAdapter(config)
        expected = {
            "aljazeera", "reuters", "bbc", "ap", "npr", "dw", "france24",
            "thehindu", "afpfactcheck", "fullfact",
        }
        assert set(DEFAULT_OUTLETS) == expected
        assert adapter.outlets == DEFAULT_OUTLETS
        assert all(url.startswith("https://") for url in DEFAULT_OUTLETS.values())

    def test_outlet_table_configurable(self) -> None:
        cfg = ScoutConfig(rss_outlets={"mine": "https://feeds.example/rss"})
        assert RSSAdapter(cfg).outlets == {"mine": "https://feeds.example/rss"}

    @pytest.mark.parametrize(
        "payload",
        [None, "x", 9, {}, [None], [("a",)], [("a", None)], [("a", "<<bad xml")]],
    )
    def test_malformed_degrades(self, config: ScoutConfig, payload) -> None:
        assert RSSAdapter(config).parse(payload, "q", 10) == []


class TestGdelt:
    def test_parses_fixture(self, config: ScoutConfig) -> None:
        raw = json.loads(load("gdelt.json"))
        results = GdeltAdapter(config).parse(raw, "flood barriers", 10)
        assert len(results) == 2  # broken entry skipped
        first = results[0]
        assert first.title == "Flood barrier pilots expand to twelve cities"
        assert first.category == "news"
        assert first.published is not None and first.published.day == 8
        assert "paper.example" in first.snippet

    @pytest.mark.parametrize(
        "payload", [None, "плохо", 2, {}, {"articles": None}, {"articles": [7]}]
    )
    def test_malformed_degrades(self, config: ScoutConfig, payload) -> None:
        assert GdeltAdapter(config).parse(payload, "q", 10) == []


class TestGuardian:
    def test_disabled_without_key(self, config: ScoutConfig,
                                  monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.delenv("GUARDIAN_API_KEY", raising=False)
        assert GuardianAdapter(config).is_enabled() is False

    def test_enabled_with_key(self, config: ScoutConfig,
                              monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("GUARDIAN_API_KEY", "k")
        assert GuardianAdapter(config).is_enabled() is True

    def test_parses_fixture(self, config: ScoutConfig) -> None:
        raw = json.loads(load("guardian.json"))
        results = GuardianAdapter(config).parse(raw, "flood", 10)
        assert len(results) == 2
        first = results[0]
        assert first.title == "The new generation of flood barriers, explained"
        assert first.snippet.startswith("How movable walls")
        assert first.published is not None
        assert results[1].snippet == ""  # missing fields tolerated

    @pytest.mark.parametrize(
        "payload",
        [None, "x", 0, {}, {"response": None}, {"response": {"results": "no"}}],
    )
    def test_malformed_degrades(self, config: ScoutConfig, payload) -> None:
        assert GuardianAdapter(config).parse(payload, "q", 10) == []


def test_all_phase_d_adapters_registered() -> None:
    from scout.adapters import all_adapters

    names = set(all_adapters())
    assert {"wikipedia", "arxiv", "pubmed", "wayback", "rss", "gdelt",
            "guardian"} <= names


def test_categories_assigned_correctly(config: ScoutConfig) -> None:
    from scout.adapters import all_adapters

    expected = {
        "wikipedia": "knowledge",
        "arxiv": "science",
        "pubmed": "science",
        "wayback": "archive",
        "rss": "news",
        "gdelt": "news",
        "guardian": "news",
    }
    adapters = all_adapters()
    for name, category in expected.items():
        assert adapters[name].category == category, name
