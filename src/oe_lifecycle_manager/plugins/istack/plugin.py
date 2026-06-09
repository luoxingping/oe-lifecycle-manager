"""iStack lifecycle plugin."""

from oe_lifecycle_manager.domain.plugin import Plugin, PluginMetadata


class IstackPlugin(Plugin):
    """iStack plugin placeholder."""

    def metadata(self) -> PluginMetadata:
        raise NotImplementedError
