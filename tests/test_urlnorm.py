"""URL normalization tests (§5 dedupe rules)."""

from __future__ import annotations

import pytest

from scout.urlnorm import normalize_url


@pytest.mark.parametrize(
    ("a", "b"),
    [
        ("https://example.org/x", "http://example.org/x"),
        ("https://example.org/x", "https://www.example.org/x"),
        ("https://example.org/x", "https://example.org/x/"),
        ("https://example.org/x", "https://example.org/x#section"),
        ("https://example.org/x", "https://example.org:443/x"),
        ("http://example.org/x", "http://example.org:80/x"),
        ("https://example.org/x?a=1&b=2", "https://example.org/x?b=2&a=1"),
        ("https://example.org/x", "https://example.org/x?utm_source=feed"),
        ("https://example.org/x", "https://example.org/x?utm_medium=a&utm_term=b"),
        ("https://example.org/x", "https://example.org/x?fbclid=abc"),
        ("https://example.org/x?id=1", "https://example.org/x?id=1&gclid=zzz"),
        ("https://EXAMPLE.org/x", "https://example.org/x"),
    ],
)
def test_equivalent_urls_collide(a: str, b: str) -> None:
    assert normalize_url(a) == normalize_url(b)


@pytest.mark.parametrize(
    ("a", "b"),
    [
        ("https://example.org/x", "https://example.org/y"),
        ("https://example.org/x?id=1", "https://example.org/x?id=2"),
        ("https://example.org/x", "https://example.org:8443/x"),
        ("https://example.org/x", "https://other.example.org/x"),
        ("https://example.org/X", "https://example.org/x"),  # path case matters
    ],
)
def test_distinct_urls_do_not_collide(a: str, b: str) -> None:
    assert normalize_url(a) != normalize_url(b)


def test_garbage_urls_do_not_crash() -> None:
    assert normalize_url("") == ""
    assert normalize_url("not a url") == "not a url"
    assert isinstance(normalize_url("https://[broken"), str)
