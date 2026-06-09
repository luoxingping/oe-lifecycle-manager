"""MariaDB lifecycle plugin."""

from oe_lifecycle_manager.domain.plugin import Plugin, PluginMetadata


class MariadbPlugin(Plugin):
    """MariaDB plugin placeholder."""

    def metadata(self) -> PluginMetadata:
        raise NotImplementedError
