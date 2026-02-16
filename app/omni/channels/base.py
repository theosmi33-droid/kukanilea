from __future__ import annotations

from pathlib import Path
from typing import Any


class Adapter:
    @staticmethod
    def ingest(tenant_id: str, fixture_path: Path) -> list[dict[str, Any]]:
        raise NotImplementedError
