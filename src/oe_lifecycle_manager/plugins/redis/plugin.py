"""Redis lifecycle plugin."""

from oe_lifecycle_manager.domain.plugin import Plugin, PluginMetadata


class RedisPlugin(Plugin):
    """Redis plugin placeholder."""

    def metadata(self) -> PluginMetadata:
        raise NotImplementedError
