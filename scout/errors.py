"""Exceptions used across SCOUT. Failures never escape the core engine."""

from __future__ import annotations


class ScoutError(Exception):
    """Base class for SCOUT errors."""


class SourceError(ScoutError):
    """A source failed to respond usefully (HTTP error, bad payload, ...)."""


class SourceBlockedError(SourceError):
    """A source refused the request (robots.txt disallow, HTTP 403/429)."""
