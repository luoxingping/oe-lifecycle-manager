"""Kubernetes lifecycle plugin."""

from oe_lifecycle_manager.domain.plugin import Plugin, PluginMetadata


class KubernetesPlugin(Plugin):
    """Kubernetes plugin placeholder."""

    def metadata(self) -> PluginMetadata:
        raise NotImplementedError
