"""Docker lifecycle plugin."""

from oe_lifecycle_manager.domain.plugin import Plugin, PluginMetadata


class DockerPlugin(Plugin):
    """Docker plugin placeholder."""

    def metadata(self) -> PluginMetadata:
        raise NotImplementedError
