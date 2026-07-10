"""CLI tests (§6) — run entirely offline via the fixture source."""

from __future__ import annotations

import json

import pytest

from scout.cli import main
from scout.schema import SearchResponse


def run_cli(capsys: pytest.CaptureFixture, *argv: str) -> tuple[int, str]:
    code = main(list(argv))
    return code, capsys.readouterr().out


def test_search_json_returns_valid_search_response(
    capsys: pytest.CaptureFixture,
) -> None:
    """§9.2: `scout "test" --json` offline yields a valid SearchResponse."""
    code, out = run_cli(capsys, "test", "--json", "--offline")
    assert code == 0
    response = SearchResponse.model_validate_json(out)
    assert response.query == "test"
    assert response.results
    assert response.health["fixture"] == "ok"


def test_search_human_output(capsys: pytest.CaptureFixture) -> None:
    code, out = run_cli(capsys, "test query", "--offline")
    assert code == 0
    assert "1." in out
    assert "[fixture]" in out
    assert "sources: fixture ok" in out
    assert "elapsed:" in out


def test_limit_flag(capsys: pytest.CaptureFixture) -> None:
    code, out = run_cli(capsys, "test", "--json", "--offline", "--limit", "1")
    assert code == 0
    assert len(SearchResponse.model_validate_json(out).results) == 1


def test_sources_command_lists_adapters(capsys: pytest.CaptureFixture) -> None:
    code, out = run_cli(capsys, "sources")
    assert code == 0
    for name in ("mojeek", "brave", "duckduckgo", "startpage", "marginalia",
                 "wikipedia", "arxiv", "pubmed", "wayback", "rss", "gdelt",
                 "guardian", "searxng_public"):
        assert name in out
    assert "searxng_public" in out
    # the booster and the keyed source both show as disabled by default
    searx_line = next(l for l in out.splitlines() if l.startswith("searxng_public"))
    assert "disabled" in searx_line
    guardian_line = next(l for l in out.splitlines() if l.startswith("guardian"))
    assert "disabled" in guardian_line
    assert "GUARDIAN_API_KEY" in guardian_line


def test_sources_command_json(capsys: pytest.CaptureFixture) -> None:
    code, out = run_cli(capsys, "sources", "--json")
    assert code == 0
    report = json.loads(out)
    by_name = {row["name"]: row for row in report}
    assert by_name["searxng_public"]["enabled"] is False
    assert by_name["mojeek"]["enabled"] is True


def test_invalid_source_is_usage_error(capsys: pytest.CaptureFixture) -> None:
    code = main(["q", "--sources", "definitely-not-real", "--offline"])
    captured = capsys.readouterr()
    assert code == 2
    assert "unknown source" in captured.err


def test_config_file_flag(tmp_path, capsys: pytest.CaptureFixture) -> None:
    config_path = tmp_path / "scout.yaml"
    config_path.write_text("offline: true\n", encoding="utf-8")
    code, out = run_cli(capsys, "test", "--json", "--config", str(config_path))
    assert code == 0
    assert SearchResponse.model_validate_json(out).health["fixture"] == "ok"


def test_category_flag_rejects_unknown(capsys: pytest.CaptureFixture) -> None:
    with pytest.raises(SystemExit):
        main(["q", "--category", "opinions"])
