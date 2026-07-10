"""``scout`` command-line entry point.

Phase A ships the skeleton only; search wiring lands with the core engine
and adapters.
"""

from __future__ import annotations

import argparse
import sys

from scout import __version__


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="scout",
        description="Keyless, multi-source web search. No servers, no API keys.",
    )
    parser.add_argument(
        "--version", action="version", version=f"scout {__version__}"
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    """CLI entry point; returns a process exit code."""
    parser = build_parser()
    parser.parse_args(argv if argv is not None else sys.argv[1:])
    parser.print_help()
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
