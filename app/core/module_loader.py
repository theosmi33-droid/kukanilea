"""
app/core/module_loader.py
Auto-discovery for KUKANILEA modules.
"""
import importlib
import pkgutil
import logging
from pathlib import Path

logger = logging.getLogger("kukanilea.modules")

def discover_and_load_modules(package_name: str = "app.modules"):
    """Dynamically loads all modules in a given package."""
    try:
        package = importlib.import_module(package_name)
    except ImportError:
        logger.warning(f"Package {package_name} not found. Skipping module discovery.")
        return []

    loaded = []
    for _, module_name, is_pkg in pkgutil.iter_modules(package.__path__):
        full_module_name = f"{package_name}.{module_name}"
        try:
            mod = importlib.import_module(full_module_name)
            loaded.append(mod)
            logger.info(f"Loaded module: {full_module_name}")
        except Exception as e:
            logger.error(f"Failed to load module {full_module_name}: {e}")
    return loaded
