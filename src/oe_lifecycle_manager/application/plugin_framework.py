"""Plugin framework core."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from importlib import import_module
from typing import Any

from oe_lifecycle_manager.domain.plugin import Plugin, PluginMetadata


class PluginFrameworkError(RuntimeError):
    """Base plugin framework error."""


class PluginManifestError(PluginFrameworkError):
    """Raised when a plugin manifest is invalid."""


class PluginLoadError(PluginFrameworkError):
    """Raised when a plugin cannot be loaded."""


class PluginAlreadyRegisteredError(PluginFrameworkError):
    """Raised when a plugin name is already registered."""


class PluginNotFoundError(PluginFrameworkError):
    """Raised when a plugin cannot be found."""


class PluginHookError(PluginFrameworkError):
    """Raised when a plugin hook fails."""

    def __init__(self, plugin_name: str, hook: "PluginHook", original: Exception) -> None:
        self.plugin_name = plugin_name
        self.hook = hook
        self.original = original
        super().__init__(f"plugin {plugin_name} hook {hook.value} failed: {original}")


class PluginHook(str, Enum):
    """Supported plugin lifecycle hooks."""

    INVENTORY = "inventory"
    CHECKS = "checks"
    RISK = "risk"
    PRE_UPGRADE = "pre_upgrade"
    POST_UPGRADE = "post_upgrade"
    ROLLBACK = "rollback"


@dataclass(frozen=True)
class PluginManifest:
    """Plugin manifest."""

    name: str
    version: str
    entrypoint: str
    supported_versions: tuple[str, ...] = ()
    hooks: tuple[PluginHook, ...] = ()

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "PluginManifest":
        """Create a manifest from a dictionary."""
        try:
            name = str(data["name"])
            version = str(data["version"])
            entrypoint = str(data["entrypoint"])
        except KeyError as exc:
            raise PluginManifestError(f"missing plugin manifest field: {exc.args[0]}") from exc

        if ":" not in entrypoint:
            raise PluginManifestError("plugin entrypoint must use 'module:attribute' format")

        return cls(
            name=name,
            version=version,
            entrypoint=entrypoint,
            supported_versions=tuple(str(item) for item in data.get("supported_versions", ())),
            hooks=tuple(PluginHook(str(item)) for item in data.get("hooks", ())),
        )

    def metadata(self) -> PluginMetadata:
        """Return metadata represented by this manifest."""
        return PluginMetadata(
            name=self.name,
            version=self.version,
            supported_versions=list(self.supported_versions),
            hooks=[hook.value for hook in self.hooks],
        )


@dataclass(frozen=True)
class PluginRegistration:
    """Registered plugin instance and manifest."""

    manifest: PluginManifest
    plugin: Plugin
    enabled: bool = True


@dataclass(frozen=True)
class PluginHookResult:
    """Plugin hook execution result."""

    plugin_name: str
    hook: PluginHook
    value: Any = None


@dataclass
class PluginRegistry:
    """Plugin registry."""

    _plugins: dict[str, PluginRegistration] = field(default_factory=dict)

    def register(self, manifest: PluginManifest, plugin: Plugin) -> PluginRegistration:
        """Register a plugin."""
        if manifest.name in self._plugins:
            raise PluginAlreadyRegisteredError(f"plugin already registered: {manifest.name}")
        self._validate_metadata(manifest, plugin.metadata())
        registration = PluginRegistration(manifest=manifest, plugin=plugin)
        self._plugins[manifest.name] = registration
        return registration

    def get(self, name: str) -> PluginRegistration:
        """Return a registered plugin."""
        try:
            return self._plugins[name]
        except KeyError as exc:
            raise PluginNotFoundError(f"plugin not found: {name}") from exc

    def list(self, enabled_only: bool = False) -> list[PluginRegistration]:
        """List registered plugins."""
        registrations = list(self._plugins.values())
        if enabled_only:
            return [item for item in registrations if item.enabled]
        return registrations

    def set_enabled(self, name: str, enabled: bool) -> PluginRegistration:
        """Enable or disable a plugin."""
        current = self.get(name)
        updated = PluginRegistration(
            manifest=current.manifest,
            plugin=current.plugin,
            enabled=enabled,
        )
        self._plugins[name] = updated
        return updated

    def _validate_metadata(self, manifest: PluginManifest, metadata: PluginMetadata) -> None:
        if metadata.name != manifest.name:
            raise PluginManifestError(
                f"plugin metadata name mismatch: {metadata.name} != {manifest.name}"
            )
        if metadata.version != manifest.version:
            raise PluginManifestError(
                f"plugin metadata version mismatch: {metadata.version} != {manifest.version}"
            )


class PluginLoader:
    """Loads plugin instances from manifests."""

    def load(self, manifest: PluginManifest) -> Plugin:
        """Load a plugin from its manifest."""
        module_name, attribute_name = manifest.entrypoint.split(":", 1)
        try:
            module = import_module(module_name)
            plugin_class = getattr(module, attribute_name)
            plugin = plugin_class()
        except Exception as exc:  # noqa: BLE001 - dynamic plugin boundary.
            raise PluginLoadError(f"failed to load plugin {manifest.name}: {exc}") from exc

        if not isinstance(plugin, Plugin):
            raise PluginLoadError(f"plugin {manifest.name} does not implement Plugin")
        return plugin


class PluginManager:
    """Coordinates plugin loading, registration, and hook dispatch."""

    def __init__(
        self,
        registry: PluginRegistry | None = None,
        loader: PluginLoader | None = None,
    ) -> None:
        self._registry = registry or PluginRegistry()
        self._loader = loader or PluginLoader()

    def register(self, manifest: PluginManifest, plugin: Plugin) -> PluginRegistration:
        """Register an already constructed plugin."""
        return self._registry.register(manifest, plugin)

    def load_and_register(self, manifest: PluginManifest) -> PluginRegistration:
        """Load a plugin from manifest and register it."""
        plugin = self._loader.load(manifest)
        return self._registry.register(manifest, plugin)

    def get(self, name: str) -> PluginRegistration:
        """Return a registered plugin."""
        return self._registry.get(name)

    def list_plugins(self, enabled_only: bool = False) -> list[PluginRegistration]:
        """List registered plugins."""
        return self._registry.list(enabled_only=enabled_only)

    def set_enabled(self, name: str, enabled: bool) -> PluginRegistration:
        """Enable or disable a plugin."""
        return self._registry.set_enabled(name, enabled)

    def dispatch(
        self,
        hook: PluginHook,
        context: dict[str, Any] | None = None,
        plugin_name: str | None = None,
    ) -> list[PluginHookResult]:
        """Run a hook for enabled plugins that declare the hook."""
        runtime_context = context if context is not None else {}
        registrations = [self._registry.get(plugin_name)] if plugin_name else self._registry.list()
        results: list[PluginHookResult] = []

        for registration in registrations:
            if not registration.enabled or hook not in registration.manifest.hooks:
                continue
            handler = getattr(registration.plugin, hook.value)
            try:
                value = handler(runtime_context)
            except Exception as exc:  # noqa: BLE001 - dynamic plugin boundary.
                raise PluginHookError(registration.manifest.name, hook, exc) from exc
            results.append(
                PluginHookResult(
                    plugin_name=registration.manifest.name,
                    hook=hook,
                    value=value,
                )
            )
        return results
