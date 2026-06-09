"""Plugin domain contracts."""

from abc import ABC
from dataclasses import dataclass, field


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
