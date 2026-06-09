"""MySQL lifecycle plugin."""

from oe_lifecycle_manager.domain.plugin import Plugin, PluginMetadata


class MysqlPlugin(Plugin):
    """MySQL plugin placeholder."""

    def metadata(self) -> PluginMetadata:
        raise NotImplementedError
