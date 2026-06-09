"""Containerd lifecycle plugin."""

from oe_lifecycle_manager.domain.plugin import Plugin, PluginMetadata


class ContainerdPlugin(Plugin):
    """Containerd plugin placeholder."""

    def metadata(self) -> PluginMetadata:
        raise NotImplementedError
