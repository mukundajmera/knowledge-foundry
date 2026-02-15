"""Knowledge Foundry — Plugin Registry & Loader.

Manages dynamic loading and execution of plugins.
"""

from __future__ import annotations

import importlib
import pkgutil
import sys
from typing import Any, Type

import structlog

from src.core.interfaces import Plugin, PluginManifest, PluginResult

logger = structlog.get_logger(__name__)


class PluginRegistry:
    """Singleton registry for managing plugins."""

    _instance: PluginRegistry | None = None
    _plugins: dict[str, Plugin] = {}

    def __new__(cls) -> PluginRegistry:
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def register(self, plugin: Plugin) -> None:
        """Register a plugin instance."""
        manifest = plugin.manifest()
        if manifest.name in self._plugins:
            logger.warning("Plugin already registered, overwriting", name=manifest.name)
        self._plugins[manifest.name] = plugin
        logger.info("Registered plugin", name=manifest.name, version=manifest.version)

    def get_plugin(self, name: str) -> Plugin | None:
        """Get a plugin by name."""
        return self._plugins.get(name)

    def list_plugins(self) -> list[PluginManifest]:
        """List all registered plugin manifests."""
        return [p.manifest() for p in self._plugins.values()]

    async def execute(self, plugin_name: str, action: str, params: dict[str, Any]) -> PluginResult:
        """Execute a plugin action."""
        plugin = self.get_plugin(plugin_name)
        if not plugin:
            return PluginResult(success=False, error=f"Plugin '{plugin_name}' not found")
        
        try:
            return await plugin.execute(action, params)
        except Exception as e:
            logger.exception("Plugin execution failed", plugin=plugin_name, action=action)
            return PluginResult(success=False, error=str(e))


class PluginLoader:
    """Discovers and loads plugins from the plugins directory."""

    @staticmethod
    def load_plugins(package_path: str = "src.plugins") -> None:
        """Load all plugins in the given package path."""
        registry = PluginRegistry()
        
        try:
            package = importlib.import_module(package_path)
        except ImportError:
            logger.error("Could not import plugin package", path=package_path)
            return

        # Walk through all modules in the package
        if hasattr(package, "__path__"):
            for _, name, _ in pkgutil.iter_modules(package.__path__):
                if name == "registry":  # Skip self
                    continue
                
                full_name = f"{package_path}.{name}"
                try:
                    module = importlib.import_module(full_name)
                    # Find all Plugin subclasses in the module
                    for attr_name in dir(module):
                        attr = getattr(module, attr_name)
                        if (
                            isinstance(attr, type) 
                            and issubclass(attr, Plugin) 
                            and attr is not Plugin
                        ):
                            # Instantiate and register
                            try:
                                plugin_instance = attr()
                                registry.register(plugin_instance)
                            except Exception as e:
                                logger.error("Failed to instantiate plugin", plugin=attr_name, error=str(e))
                except Exception as e:
                    logger.error("Failed to load plugin module", module=full_name, error=str(e))
