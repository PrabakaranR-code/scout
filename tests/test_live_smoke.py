"""Optional live smoke test (§9.7) — NOT run in CI.

Enable manually with::

    SCOUT_LIVE_TEST=1 pytest tests/test_live_smoke.py -m live

It hits real services, so results depend on the network and on the mood of
the engines; the assertion is deliberately soft (at least one source ok).
"""

from __future__ import annotations

import os

import pytest

pytestmark = [
    pytest.mark.live,
    pytest.mark.skipif(
        not os.environ.get("SCOUT_LIVE_TEST"),
        reason="live smoke test; set SCOUT_LIVE_TEST=1 to run",
    ),
]


def test_live_search_reaches_at_least_one_source() -> None:
    from scout import Scout

    response = Scout().search("open source software", limit=10)
    assert any(status == "ok" for status in response.health.values())
    assert response.results, f"no results; health: {response.health}"
