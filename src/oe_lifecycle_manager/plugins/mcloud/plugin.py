"""MCloud lifecycle plugin."""

from oe_lifecycle_manager.domain.plugin import Plugin, PluginMetadata


class McloudPlugin(Plugin):
    """MCloud plugin placeholder."""

    def metadata(self) -> PluginMetadata:
        raise NotImplementedError
