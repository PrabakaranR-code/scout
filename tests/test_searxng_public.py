"""Booster adapter tests (§4.D, §9.4): off by default, opt-in via config."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from scout.adapters.searxng_public import DEFAULT_INSTANCES, SearxngPublicAdapter
from scout.config import ScoutConfig
from scout.core import Scout

FIXTURES = Path(__file__).parent / "fixtures"


def test_disabled_by_default() -> None:
    """§9.4: searxng_public must be off unless explicitly enabled."""
    adapter = SearxngPublicAdapter(ScoutConfig())
    assert adapter.default_enabled is False
    assert adapter.is_enabled() is False
    engine = Scout()
    assert engine.adapters["searxng_public"].is_enabled() is False


def test_enabling_via_config_works() -> None:
    """§9.4: enabling through config activates the source."""
    engine = Scout({"sources": {"searxng_public": {"enabled": True}}})
    assert engine.adapters["searxng_public"].is_enabled() is True


def test_privacy_trade_off_documented_in_docstring() -> None:
    import scout.adapters.searxng_public as module

    text = (module.__doc__ or "").lower()
    assert "privacy" in text
    assert "off by default" in text


def test_instance_rotation() -> None:
    cfg = ScoutConfig(searxng_instances=["https://a.example/", "https://b.example"])
    adapter = SearxngPublicAdapter(cfg)
    assert adapter.next_instance() == "https://a.example"
    assert adapter.next_instance() == "https://b.example"
    assert adapter.next_instance() == "https://a.example"  # wraps around


def test_default_instance_list_used_when_unconfigured() -> None:
    adapter = SearxngPublicAdapter(ScoutConfig())
    seen = {adapter.next_instance() for _ in range(len(DEFAULT_INSTANCES))}
    assert seen == {instance.rstrip("/") for instance in DEFAULT_INSTANCES}


def test_parses_fixture() -> None:
    raw = json.loads((FIXTURES / "searxng.json").read_text(encoding="utf-8"))
    results = SearxngPublicAdapter(ScoutConfig()).parse(raw, "solar sail", 10)
    assert len(results) == 2  # non-http entry skipped
    assert results[0].title == "Solar sails explained"
    assert results[0].published is not None
    assert results[1].published is None
    assert all(r.source == "searxng_public" for r in results)


@pytest.mark.parametrize(
    "payload", [None, "html not json", 5, {}, {"results": None}, {"results": [None]}]
)
def test_malformed_degrades(payload) -> None:
    assert SearxngPublicAdapter(ScoutConfig()).parse(payload, "q", 10) == []
