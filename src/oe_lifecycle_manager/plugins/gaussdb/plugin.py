"""GaussDB lifecycle plugin."""

from oe_lifecycle_manager.domain.plugin import Plugin, PluginMetadata


class GaussdbPlugin(Plugin):
    """GaussDB plugin placeholder."""

    def metadata(self) -> PluginMetadata:
        raise NotImplementedError
