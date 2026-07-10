"""Core engine tests (§5, §8.B): fan-out, merge, dedupe, health, isolation."""

from __future__ import annotations

import pytest

from scout.core import Scout, _round_robin
from scout.schema import HealthStatus, SearchResponse, SearchResult

from tests.stubs import ErrorStub, TimeoutStub, build_engine, make_stub


def result_dict(rank: int, host: str, **extra) -> dict:
    return {
        "title": f"Result {rank} from {host}",
        "url": f"https://{host}/item/{rank}",
        "snippet": f"snippet {rank}",
        "raw_rank": rank,
        **extra,
    }


AlphaStub = make_stub("alpha", [result_dict(1, "alpha.example"),
                                result_dict(2, "alpha.example")])
BetaStub = make_stub("beta", [result_dict(1, "beta.example"),
                              result_dict(2, "beta.example"),
                              result_dict(3, "beta.example")])
GammaStub = make_stub("gamma", [result_dict(1, "gamma.example")])


def test_all_sources_ok() -> None:
    engine = build_engine([AlphaStub, BetaStub, GammaStub])
    response = engine.search("anything")
    assert isinstance(response, SearchResponse)
    assert response.query == "anything"
    assert len(response.results) == 6
    assert response.health == {
        "alpha": HealthStatus.OK,
        "beta": HealthStatus.OK,
        "gamma": HealthStatus.OK,
    }
    assert response.elapsed_ms >= 0


def test_round_robin_interleaves_sources() -> None:
    engine = build_engine([AlphaStub, BetaStub, GammaStub])
    response = engine.search("q")
    order = [r.source for r in response.results]
    # tier 1 from each source first, then tier 2, then the leftovers
    assert order == ["alpha", "beta", "gamma", "alpha", "beta", "beta"]
    assert [r.raw_rank for r in response.results] == [1, 1, 1, 2, 2, 3]


def test_search_succeeds_when_sources_timeout_and_error() -> None:
    """§9.3: 3 respond + 1 times out + 1 errors -> success, health correct."""
    engine = build_engine([AlphaStub, BetaStub, GammaStub, TimeoutStub, ErrorStub])
    response = engine.search("resilience")
    assert response.health == {
        "alpha": HealthStatus.OK,
        "beta": HealthStatus.OK,
        "gamma": HealthStatus.OK,
        "sleepy": HealthStatus.TIMEOUT,
        "broken": HealthStatus.ERROR,
    }
    assert len(response.results) == 6
    assert all(r.source in {"alpha", "beta", "gamma"} for r in response.results)


def test_all_sources_failing_still_returns_response() -> None:
    engine = build_engine([TimeoutStub, ErrorStub])
    response = engine.search("nothing works")
    assert response.results == []
    assert response.health["sleepy"] == HealthStatus.TIMEOUT
    assert response.health["broken"] == HealthStatus.ERROR


def test_failed_sources_logged(caplog: pytest.LogCaptureFixture) -> None:
    engine = build_engine([ErrorStub])
    with caplog.at_level("WARNING", logger="scout"):
        engine.search("q")
    assert any("broken" in record.message for record in caplog.records)


def test_disabled_source_reported_and_not_queried() -> None:
    Disabled = make_stub("quiet", [result_dict(1, "quiet.example")], enabled=False)
    engine = build_engine([AlphaStub, Disabled])
    response = engine.search("q")
    assert response.health["quiet"] == HealthStatus.DISABLED
    assert all(r.source != "quiet" for r in response.results)


def test_config_can_disable_and_enable_sources() -> None:
    Disabled = make_stub("quiet", [result_dict(1, "quiet.example")], enabled=False)
    engine = build_engine(
        [AlphaStub, Disabled],
        {"sources": {"alpha": {"enabled": False}, "quiet": {"enabled": True}}},
    )
    response = engine.search("q")
    assert response.health["alpha"] == HealthStatus.DISABLED
    assert response.health["quiet"] == HealthStatus.OK


def test_sources_argument_selects_and_overrides() -> None:
    Disabled = make_stub("quiet", [result_dict(1, "quiet.example")], enabled=False)
    engine = build_engine([AlphaStub, BetaStub, Disabled])
    response = engine.search("q", sources=["quiet", "beta"])
    assert response.health["quiet"] == HealthStatus.OK
    assert response.health["beta"] == HealthStatus.OK
    assert response.health["alpha"] == HealthStatus.DISABLED


def test_unknown_source_rejected() -> None:
    engine = build_engine([AlphaStub])
    with pytest.raises(ValueError, match="unknown source"):
        engine.search("q", sources=["nope"])


def test_category_filter() -> None:
    NewsStub = make_stub(
        "newsy", [result_dict(1, "news.example", category="news")],
        stub_category="news",
    )
    engine = build_engine([AlphaStub, NewsStub])
    response = engine.search("q", category="news")
    assert response.health["newsy"] == HealthStatus.OK
    assert response.health["alpha"] == HealthStatus.DISABLED
    assert all(r.category == "news" for r in response.results)


def test_invalid_inputs_rejected() -> None:
    engine = build_engine([AlphaStub])
    with pytest.raises(ValueError):
        engine.search("")
    with pytest.raises(ValueError):
        engine.search("   ")
    with pytest.raises(ValueError):
        engine.search("q", category="opinions")
    with pytest.raises(ValueError):
        engine.search("q", limit=0)


def test_limit_caps_merged_list() -> None:
    engine = build_engine([AlphaStub, BetaStub])
    response = engine.search("q", limit=3)
    assert len(response.results) == 3
    # the cap keeps the interleaved head, one per source first
    assert [r.source for r in response.results] == ["alpha", "beta", "alpha"]


def test_dedupe_collision_keeps_first_position_and_richer_content() -> None:
    First = make_stub(
        "first",
        [{
            "title": "Short",
            "url": "https://example.org/story",
            "snippet": "brief",
            "raw_rank": 1,
        }],
    )
    Second = make_stub(
        "second",
        [{
            "title": "Longer, richer take",
            "url": "http://www.example.org/story/?utm_source=feed",
            "snippet": "a much longer and more informative snippet",
            "raw_rank": 1,
            "published": "2026-01-01T00:00:00Z",
        }],
    )
    engine = build_engine([First, Second])
    response = engine.search("q")
    assert len(response.results) == 1
    merged = response.results[0]
    # richer content won, first position retained
    assert merged.source == "second"
    assert merged.also_found_in == ["first"]
    assert merged.published is not None
    assert "longer" in merged.snippet


def test_dedupe_records_all_sources_and_ors_trusted() -> None:
    A = make_stub("a", [{"title": "t", "url": "https://example.org/x", "raw_rank": 1}])
    B = make_stub("b", [{"title": "t", "url": "https://example.org/x/", "raw_rank": 1}])
    C = make_stub("c", [{"title": "t", "url": "http://example.org/x", "raw_rank": 1}])
    engine = build_engine([A, B, C], {"trusted_outlets": ["example.org"]})
    response = engine.search("q")
    assert len(response.results) == 1
    merged = response.results[0]
    assert set(merged.also_found_in) == {"a", "b", "c"} - {merged.source}
    assert merged.trusted is True


def test_round_robin_empty_input() -> None:
    assert _round_robin({}) == []
    assert _round_robin({"a": []}) == []


def test_trusted_marking_from_config() -> None:
    Trusted = make_stub(
        "wire", [result_dict(1, "feeds.reuters.com"), result_dict(2, "example.net")]
    )
    engine = build_engine([Trusted], {"trusted_outlets": ["reuters.com"]})
    response = engine.search("q")
    by_host = {r.url: r.trusted for r in response.results}
    assert by_host["https://feeds.reuters.com/item/1"] is True
    assert by_host["https://example.net/item/2"] is False


def test_offline_mode_uses_fixture_only() -> None:
    engine = Scout({"offline": True})
    assert list(engine.adapters) == ["fixture"]
    response = engine.search("test")
    assert response.health == {"fixture": HealthStatus.OK}
    assert response.results
    assert all(r.source == "fixture" for r in response.results)


@pytest.mark.anyio
async def test_asearch_from_async_context() -> None:
    engine = build_engine([AlphaStub])
    response = await engine.asearch("q")
    assert response.health["alpha"] == HealthStatus.OK
    # the sync facade must also work with a loop already running
    sync_response = engine.search("q")
    assert sync_response.health["alpha"] == HealthStatus.OK


def test_source_report_shape() -> None:
    engine = build_engine([AlphaStub, TimeoutStub])
    report = engine.source_report()
    names = [row["name"] for row in report]
    assert names == sorted(names)
    row = next(r for r in report if r["name"] == "sleepy")
    assert row["enabled"] is True
    assert row["timeout"] == 0.2
