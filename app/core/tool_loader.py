from __future__ import annotations

import importlib
import logging
import pkgutil

logger = logging.getLogger("kukanilea.core.tool_loader")


def load_all_tools():
    """
    Dynamically discovers and imports all tools in the app.tools package.
    Ensures that each tool registers itself upon import.
    """
    import app.tools as tools_pkg

    count = 0
    for _, module_name, _ in pkgutil.iter_modules(tools_pkg.__path__):
        if module_name in ["registry", "base_tool"]:
            continue

        try:
            importlib.import_module(f"app.tools.{module_name}")
            count += 1
        except Exception as e:
            logger.error(f"Failed to load tool module {module_name}: {e}")

    logger.info(f"Successfully loaded {count} tool modules.")
