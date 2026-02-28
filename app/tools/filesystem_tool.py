from __future__ import annotations

import os
from typing import Any, Dict

from app.tools.base_tool import BaseTool
from app.tools.registry import registry


class FileSystemTool(BaseTool):
    """
    Tool for safe local filesystem operations.
    """

    name = "filesystem_list"
    description = "Listet Dateien in einem Verzeichnis auf."
    input_schema = {
        "type": "object",
        "properties": {"path": {"type": "string", "default": "."}},
    }

    def run(self, path: str = ".") -> Any:
        try:
            # Basic security check: prevent escaping app directory if needed
            # For now, just list content
            return os.listdir(path)
        except Exception as e:
            return {"error": str(e)}


# Self-registration upon import
registry.register(FileSystemTool())
