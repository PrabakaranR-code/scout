"""``scout`` command-line entry point.

Usage::

    scout "query" [--category news] [--limit 20] [--sources mojeek,rss] [--json]
    scout sources            # list adapters and their enabled/disabled state
"""

from __future__ import annotations

import argparse
import sys

from scout import __version__
from scout.config import ScoutConfig
from scout.schema import CATEGORIES, SearchResponse


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="scout",
        description=(
            "Keyless, multi-source web search. No servers, no API keys. "
            "Run `scout sources` to list available sources."
        ),
    )
    parser.add_argument(
        "query",
        help='search query, or the word "sources" to list adapters',
    )
    parser.add_argument(
        "--category",
        default="all",
        choices=("all", *CATEGORIES),
        help="restrict to one result category (default: all)",
    )
    parser.add_argument(
        "--limit", type=int, default=20, help="maximum merged results (default: 20)"
    )
    parser.add_argument(
        "--sources",
        default=None,
        help="comma-separated adapter names to query (overrides enabled state)",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="print the full SearchResponse as JSON",
    )
    parser.add_argument(
        "--config",
        default=None,
        metavar="PATH",
        help="path to a scout.yaml (default: ./scout.yaml if present)",
    )
    parser.add_argument(
        "--offline",
        action="store_true",
        help="no network: answer from the built-in fixture source",
    )
    parser.add_argument(
        "--version", action="version", version=f"scout {__version__}"
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    """CLI entry point; returns a process exit code."""
    args = build_parser().parse_args(argv if argv is not None else sys.argv[1:])

    overrides = {}
    if args.offline:
        overrides["offline"] = True
    config = ScoutConfig.load(args.config, **overrides)

    from scout.core import Scout

    engine = Scout(config)

    if args.query == "sources":
        return _run_sources(engine, as_json=args.json)
    return _run_search(engine, args)


def _run_search(engine, args: argparse.Namespace) -> int:
    sources = [s.strip() for s in args.sources.split(",")] if args.sources else None
    try:
        response = engine.search(
            args.query, category=args.category, limit=args.limit, sources=sources
        )
    except ValueError as exc:
        print(f"scout: {exc}", file=sys.stderr)
        return 2

    if args.json:
        print(response.model_dump_json(indent=2))
    else:
        _print_human(response)
    # exit 1 only when every source failed and nothing came back
    all_failed = response.health and all(
        status in ("error", "timeout") for status in response.health.values()
    )
    return 1 if (all_failed and not response.results) else 0


def _print_human(response: SearchResponse) -> None:
    if not response.results:
        print("No results.")
    for index, result in enumerate(response.results, start=1):
        tags = f"[{result.source}]"
        if result.also_found_in:
            tags += " +" + ",".join(result.also_found_in)
        if result.trusted:
            tags += " (trusted)"
        date = f" — {result.published:%Y-%m-%d}" if result.published else ""
        print(f"{index:2}. {result.title} {tags}{date}")
        print(f"    {result.url}")
        if result.snippet:
            print(f"    {result.snippet[:300]}")
    print()
    footer = ", ".join(
        f"{source} {status.value}"
        for source, status in sorted(response.health.items())
    )
    print(f"sources: {footer}")
    print(f"elapsed: {response.elapsed_ms} ms")


def _run_sources(engine, *, as_json: bool) -> int:
    report = engine.source_report()
    if as_json:
        import json

        print(json.dumps(report, indent=2))
        return 0
    for row in report:
        state = "enabled" if row["enabled"] else "disabled"
        env_note = f" (needs {row['requires_env']})" if row["requires_env"] else ""
        print(
            f"{row['name']:<16} {row['category']:<10} {state:<9}"
            f" rate={row['rate_limit']:g}/s timeout={row['timeout']:g}s{env_note}"
        )
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
