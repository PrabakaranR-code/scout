"""Config loading tests (§5): kwargs, dict, and scout.yaml sources."""

from __future__ import annotations

from pathlib import Path

import pytest

from scout.config import ScoutConfig, SourceSettings


def test_defaults() -> None:
    cfg = ScoutConfig()
    assert cfg.sources == {}
    assert cfg.trusted_outlets == []
    assert cfg.timeout == 8.0
    assert cfg.respect_robots is True
    assert cfg.rss_outlets is None
    assert cfg.searxng_instances == []
    assert cfg.offline is False


def test_load_from_kwargs() -> None:
    cfg = ScoutConfig.load(timeout=3.5, trusted_outlets=["bbc.co.uk"])
    assert cfg.timeout == 3.5
    assert cfg.trusted_outlets == ["bbc.co.uk"]


def test_load_from_dict_with_source_overrides() -> None:
    cfg = ScoutConfig.load(
        {
            "sources": {
                "mojeek": {"enabled": False},
                "rss": {"timeout": 12, "rate_limit": 0.5},
            }
        }
    )
    assert cfg.source_settings("mojeek").enabled is False
    assert cfg.source_settings("rss").timeout == 12
    assert cfg.source_settings("rss").rate_limit == 0.5
    # unknown source -> empty settings, not an error
    assert cfg.source_settings("nope") == SourceSettings()


def test_load_from_yaml_file(tmp_path: Path) -> None:
    path = tmp_path / "scout.yaml"
    path.write_text(
        "timeout: 4\n"
        "trusted_outlets: [reuters.com, apnews.com]\n"
        "sources:\n"
        "  startpage:\n"
        "    enabled: false\n",
        encoding="utf-8",
    )
    cfg = ScoutConfig.load(path)
    assert cfg.timeout == 4
    assert cfg.trusted_outlets == ["reuters.com", "apnews.com"]
    assert cfg.source_settings("startpage").enabled is False


def test_kwargs_override_file(tmp_path: Path) -> None:
    path = tmp_path / "scout.yaml"
    path.write_text("timeout: 4\n", encoding="utf-8")
    cfg = ScoutConfig.load(path, timeout=9)
    assert cfg.timeout == 9


def test_load_is_idempotent(tmp_path: Path) -> None:
    path = tmp_path / "scout.yaml"
    path.write_text("timeout: 4\noffline: true\n", encoding="utf-8")
    first = ScoutConfig.load(path)
    second = ScoutConfig.load(path)
    assert first == second
    assert ScoutConfig.load(first) == first  # re-loading a config is a no-op


def test_empty_yaml_file_means_defaults(tmp_path: Path) -> None:
    path = tmp_path / "scout.yaml"
    path.write_text("", encoding="utf-8")
    assert ScoutConfig.load(path) == ScoutConfig()


def test_non_mapping_yaml_rejected(tmp_path: Path) -> None:
    path = tmp_path / "scout.yaml"
    path.write_text("- just\n- a list\n", encoding="utf-8")
    with pytest.raises(ValueError):
        ScoutConfig.load(path)


def test_unknown_keys_ignored() -> None:
    cfg = ScoutConfig.load({"timeout": 2, "no_such_option": True})
    assert cfg.timeout == 2


def test_bad_type_rejected() -> None:
    with pytest.raises(TypeError):
        ScoutConfig.load(42)  # type: ignore[arg-type]


def test_autoload_scout_yaml_from_cwd(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    (tmp_path / "scout.yaml").write_text("timeout: 6\n", encoding="utf-8")
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv("SCOUT_NO_AUTOCONFIG", raising=False)
    assert ScoutConfig.load().timeout == 6
    monkeypatch.setenv("SCOUT_NO_AUTOCONFIG", "1")
    assert ScoutConfig.load().timeout == 8.0


def test_resolved_user_agent_is_honest_by_default() -> None:
    from scout import REPO_URL, __version__

    ua = ScoutConfig().resolved_user_agent()
    assert ua == f"SCOUT/{__version__} (+{REPO_URL})"
    assert ScoutConfig(user_agent="custom/1").resolved_user_agent() == "custom/1"
