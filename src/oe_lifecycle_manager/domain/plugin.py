"""Plugin domain contracts."""

from __future__ import annotations

from abc import ABC
from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class PluginMetadata:
    """Plugin metadata."""

    name: str
    version: str
    supported_versions: list[str] = field(default_factory=list)
    hooks: list[str] = field(default_factory=list)


class Plugin(ABC):
    """Base class for lifecycle plugins."""

    def metadata(self) -> PluginMetadata:
        """Return plugin metadata."""
        raise NotImplementedError

    def inventory(self, context: dict[str, Any]) -> Any:
        """Collect plugin inventory."""
        return None

    def checks(self, context: dict[str, Any]) -> Any:
        """Return plugin check definitions or results."""
        return None

    def risk_rules(self, context: dict[str, Any]) -> Any:
        """Return plugin risk rules."""
        return None

    def pre_upgrade(self, context: dict[str, Any]) -> Any:
        """Run plugin pre-upgrade hook."""
        return None

    def post_upgrade(self, context: dict[str, Any]) -> Any:
        """Run plugin post-upgrade hook."""
        return None

    def rollback(self, context: dict[str, Any]) -> Any:
        """Run plugin rollback hook."""
        return None
