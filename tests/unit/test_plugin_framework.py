"""Unit tests for the plugin framework."""

from __future__ import annotations

import unittest

from oe_lifecycle_manager.application.plugin_framework import (
    PluginAlreadyRegisteredError,
    PluginHook,
    PluginHookError,
    PluginLoadError,
    PluginManager,
    PluginManifest,
    PluginManifestError,
    PluginNotFoundError,
)
from oe_lifecycle_manager.domain.plugin import Plugin, PluginMetadata


class DemoPlugin(Plugin):
    """Test plugin."""

    def metadata(self) -> PluginMetadata:
        return PluginMetadata(
            name="demo",
            version="1.0.0",
            supported_versions=["22.03-SP1"],
            hooks=["inventory", "pre_upgrade"],
        )

    def inventory(self, context):
        return {"host_id": context["host_id"]}

    def pre_upgrade(self, context):
        context["pre_upgrade_called"] = True
        return "ok"


class MismatchedPlugin(Plugin):
    """Plugin with metadata that does not match its manifest."""

    def metadata(self) -> PluginMetadata:
        return PluginMetadata(name="other", version="1.0.0")


class FailingPlugin(Plugin):
    """Plugin whose hook fails."""

    def metadata(self) -> PluginMetadata:
        return PluginMetadata(name="failing", version="1.0.0", hooks=["inventory"])

    def inventory(self, context):
        raise RuntimeError("hook failed")


class NotAPlugin:
    """Object that is not a plugin."""


def demo_manifest() -> PluginManifest:
    """Create a demo plugin manifest."""
    return PluginManifest(
        name="demo",
        version="1.0.0",
        entrypoint="tests.unit.test_plugin_framework:DemoPlugin",
        supported_versions=("22.03-SP1",),
        hooks=(PluginHook.INVENTORY, PluginHook.PRE_UPGRADE),
    )


class PluginFrameworkTest(unittest.TestCase):
    """Plugin framework unit tests."""

    def test_manifest_from_dict_parses_hooks_and_metadata(self) -> None:
        manifest = PluginManifest.from_dict(
            {
                "name": "demo",
                "version": "1.0.0",
                "entrypoint": "tests.unit.test_plugin_framework:DemoPlugin",
                "supported_versions": ["22.03-SP1"],
                "hooks": ["inventory", "pre_upgrade"],
            }
        )

        self.assertEqual(manifest.name, "demo")
        self.assertEqual(manifest.hooks, (PluginHook.INVENTORY, PluginHook.PRE_UPGRADE))
        self.assertEqual(manifest.metadata().hooks, ["inventory", "pre_upgrade"])

    def test_manifest_rejects_missing_required_field(self) -> None:
        with self.assertRaisesRegex(PluginManifestError, "missing plugin manifest field"):
            PluginManifest.from_dict({"name": "demo", "version": "1.0.0"})

    def test_manifest_rejects_invalid_entrypoint_format(self) -> None:
        with self.assertRaisesRegex(PluginManifestError, "module:attribute"):
            PluginManifest.from_dict(
                {
                    "name": "demo",
                    "version": "1.0.0",
                    "entrypoint": "invalid",
                }
            )

    def test_register_and_dispatch_declared_hook(self) -> None:
        manager = PluginManager()
        manager.register(demo_manifest(), DemoPlugin())

        results = manager.dispatch(PluginHook.INVENTORY, {"host_id": "host-1"})

        self.assertEqual(len(results), 1)
        self.assertEqual(results[0].plugin_name, "demo")
        self.assertEqual(results[0].hook, PluginHook.INVENTORY)
        self.assertEqual(results[0].value, {"host_id": "host-1"})

    def test_dispatch_skips_undeclared_hook(self) -> None:
        manager = PluginManager()
        manager.register(demo_manifest(), DemoPlugin())

        results = manager.dispatch(PluginHook.ROLLBACK, {})

        self.assertEqual(results, [])

    def test_disable_plugin_skips_dispatch(self) -> None:
        manager = PluginManager()
        manager.register(demo_manifest(), DemoPlugin())
        manager.set_enabled("demo", False)

        results = manager.dispatch(PluginHook.INVENTORY, {"host_id": "host-1"})

        self.assertEqual(results, [])
        self.assertEqual(manager.list_plugins(enabled_only=True), [])

    def test_dispatch_specific_plugin(self) -> None:
        manager = PluginManager()
        context = {"host_id": "host-1"}
        manager.register(demo_manifest(), DemoPlugin())

        results = manager.dispatch(PluginHook.PRE_UPGRADE, context, plugin_name="demo")

        self.assertEqual(results[0].value, "ok")
        self.assertTrue(context["pre_upgrade_called"])

    def test_duplicate_registration_is_rejected(self) -> None:
        manager = PluginManager()
        manager.register(demo_manifest(), DemoPlugin())

        with self.assertRaisesRegex(PluginAlreadyRegisteredError, "demo"):
            manager.register(demo_manifest(), DemoPlugin())

    def test_metadata_mismatch_is_rejected(self) -> None:
        manager = PluginManager()

        with self.assertRaisesRegex(PluginManifestError, "metadata name mismatch"):
            manager.register(demo_manifest(), MismatchedPlugin())

    def test_missing_plugin_is_rejected(self) -> None:
        manager = PluginManager()

        with self.assertRaisesRegex(PluginNotFoundError, "missing"):
            manager.get("missing")

    def test_hook_failure_is_wrapped(self) -> None:
        manager = PluginManager()
        manifest = PluginManifest(
            name="failing",
            version="1.0.0",
            entrypoint="tests.unit.test_plugin_framework:FailingPlugin",
            hooks=(PluginHook.INVENTORY,),
        )
        manager.register(manifest, FailingPlugin())

        with self.assertRaises(PluginHookError) as exc_info:
            manager.dispatch(PluginHook.INVENTORY, {})

        self.assertEqual(exc_info.exception.plugin_name, "failing")
        self.assertEqual(exc_info.exception.hook, PluginHook.INVENTORY)
        self.assertIsInstance(exc_info.exception.original, RuntimeError)

    def test_load_and_register_imports_plugin(self) -> None:
        manager = PluginManager()

        registration = manager.load_and_register(demo_manifest())

        self.assertEqual(registration.manifest.name, "demo")
        self.assertIsInstance(registration.plugin, DemoPlugin)

    def test_loader_rejects_non_plugin_entrypoint(self) -> None:
        manager = PluginManager()
        manifest = PluginManifest(
            name="bad",
            version="1.0.0",
            entrypoint="tests.unit.test_plugin_framework:NotAPlugin",
        )

        with self.assertRaisesRegex(PluginLoadError, "does not implement Plugin"):
            manager.load_and_register(manifest)


if __name__ == "__main__":
    unittest.main()
