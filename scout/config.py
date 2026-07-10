"""Configuration loading for SCOUT.

Configuration can come from keyword arguments, a plain dict, or a
``scout.yaml`` file. Loading is idempotent: feeding the same input twice
always produces an equal :class:`ScoutConfig`.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel, ConfigDict, Field

DEFAULT_CONFIG_FILENAME = "scout.yaml"


class SourceSettings(BaseModel):
    """Per-source overrides. ``None`` means "use the adapter's default"."""

    model_config = ConfigDict(extra="ignore")

    enabled: bool | None = None
    timeout: float | None = None
    rate_limit: float | None = None


class ScoutConfig(BaseModel):
    """Runtime configuration for :class:`scout.core.Scout`.

    Attributes:
        sources: Per-source overrides keyed by adapter name
            (e.g. ``{"mojeek": {"enabled": False}}``).
        trusted_outlets: Domains (suffix-matched against result hosts) whose
            results are marked ``trusted=True``.
        timeout: Default per-source timeout in seconds; adapters may declare
            their own default, and per-source overrides win over both.
        user_agent: Sent on every request. Defaults to the honest
            ``SCOUT/<version> (+repo URL)`` identity; override with care.
        respect_robots: When True (default), HTML-scraping adapters check
            robots.txt before fetching.
        rss_outlets: Outlet table for the ``rss`` adapter (name -> feed URL).
            ``None`` means "use the shipped default outlets".
        searxng_instances: Public SearXNG instance base URLs used by the
            (off-by-default) ``searxng_public`` booster adapter.
        offline: When True, no network is used: only fixture-backed sources
            respond. Intended for tests and smoke checks.
    """

    model_config = ConfigDict(extra="ignore")

    sources: dict[str, SourceSettings] = Field(default_factory=dict)
    trusted_outlets: list[str] = Field(default_factory=list)
    timeout: float = 8.0
    user_agent: str | None = None
    respect_robots: bool = True
    rss_outlets: dict[str, str] | None = None
    searxng_instances: list[str] = Field(default_factory=list)
    offline: bool = False

    def resolved_user_agent(self) -> str:
        """The User-Agent string to send: configured value or honest default."""
        if self.user_agent:
            return self.user_agent
        from scout import USER_AGENT

        return USER_AGENT

    def source_settings(self, name: str) -> SourceSettings:
        """Overrides for one adapter; empty settings when none configured."""
        return self.sources.get(name, SourceSettings())

    @classmethod
    def load(
        cls,
        config: "ScoutConfig | dict[str, Any] | str | Path | None" = None,
        **kwargs: Any,
    ) -> "ScoutConfig":
        """Build a config from a ScoutConfig, dict, YAML path, or kwargs.

        With ``config=None`` and no kwargs, ``./scout.yaml`` is used if it
        exists (unless SCOUT_NO_AUTOCONFIG is set); otherwise pure defaults.
        Keyword arguments override values from the base source.
        """
        if isinstance(config, ScoutConfig):
            data = config.model_dump()
        elif isinstance(config, dict):
            data = dict(config)
        elif isinstance(config, (str, Path)):
            data = _read_yaml(Path(config))
        elif config is None:
            data = {}
            default_file = Path(DEFAULT_CONFIG_FILENAME)
            if default_file.is_file() and not os.environ.get("SCOUT_NO_AUTOCONFIG"):
                data = _read_yaml(default_file)
        else:
            raise TypeError(
                f"config must be ScoutConfig, dict, str, Path, or None, "
                f"not {type(config).__name__}"
            )
        data.update(kwargs)
        return cls.model_validate(data)


def _read_yaml(path: Path) -> dict[str, Any]:
    """Read a YAML mapping; an empty or list-shaped file is an error."""
    text = path.read_text(encoding="utf-8")
    loaded = yaml.safe_load(text)
    if loaded is None:
        return {}
    if not isinstance(loaded, dict):
        raise ValueError(f"{path}: expected a YAML mapping at the top level")
    return loaded
