"""Shared test setup: keep tests hermetic regardless of the invoking cwd."""

from __future__ import annotations

import pytest


@pytest.fixture(autouse=True)
def _no_autoconfig(monkeypatch: pytest.MonkeyPatch) -> None:
    # A scout.yaml in the developer's cwd must never leak into tests.
    monkeypatch.setenv("SCOUT_NO_AUTOCONFIG", "1")
