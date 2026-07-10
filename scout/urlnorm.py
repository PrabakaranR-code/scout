"""URL normalization used by the dedupe step (§5).

Two URLs that differ only in scheme, a ``www.`` prefix, default port,
trailing slash, fragment, tracking parameters, or query-parameter order are
considered the same document.
"""

from __future__ import annotations

from urllib.parse import parse_qsl, urlencode, urlsplit

# Query parameters that only track the click, never select the document.
TRACKING_PARAMS: frozenset[str] = frozenset(
    {
        "fbclid",
        "gclid",
        "gclsrc",
        "dclid",
        "msclkid",
        "igshid",
        "mc_cid",
        "mc_eid",
        "ref",
        "ref_src",
        "cmpid",
        "ncid",
    }
)
TRACKING_PREFIXES: tuple[str, ...] = ("utm_",)


def normalize_url(url: str) -> str:
    """Return the canonical dedupe key for ``url``.

    The key is not guaranteed to be fetchable; it exists only for equality
    comparison. Unparseable URLs normalize to themselves.
    """
    try:
        parts = urlsplit(url.strip())
    except ValueError:
        return url
    host = (parts.hostname or "").lower()
    if host.startswith("www."):
        host = host[4:]
    port = parts.port
    if port and port not in (80, 443):
        host = f"{host}:{port}"
    path = parts.path.rstrip("/")
    kept_params = [
        (key, value)
        for key, value in parse_qsl(parts.query, keep_blank_values=True)
        if key.lower() not in TRACKING_PARAMS
        and not key.lower().startswith(TRACKING_PREFIXES)
    ]
    query = urlencode(sorted(kept_params))
    normalized = host + path
    if query:
        normalized += "?" + query
    return normalized or url
