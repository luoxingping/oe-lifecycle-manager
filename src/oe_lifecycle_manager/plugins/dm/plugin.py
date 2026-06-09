"""DM lifecycle plugin."""

from oe_lifecycle_manager.domain.plugin import Plugin, PluginMetadata


class DmPlugin(Plugin):
    """DM plugin placeholder."""

    def metadata(self) -> PluginMetadata:
        raise NotImplementedError
