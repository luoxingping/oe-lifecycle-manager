"""OpenStack lifecycle plugin."""

from oe_lifecycle_manager.domain.plugin import Plugin, PluginMetadata


class OpenstackPlugin(Plugin):
    """OpenStack plugin placeholder."""

    def metadata(self) -> PluginMetadata:
        raise NotImplementedError
