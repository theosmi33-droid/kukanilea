from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .store import create_rule


def _load_doc(path: Path) -> dict[str, Any]:
    raw = path.read_text(encoding="utf-8").strip()
    if not raw:
        raise ValueError(f"empty_rule_file:{path}")
    try:
        data = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise ValueError(
            f"unsupported_format:{path}. Use JSON syntax for .json/.yaml/.yml rule files"
        ) from exc
    if not isinstance(data, dict):
        raise ValueError(f"invalid_rule_doc:{path}")
    return data


def load_rule_file(path: Path | str) -> dict[str, Any]:
    file_path = Path(path)
    if file_path.suffix.lower() not in {".json", ".yaml", ".yml"}:
        raise ValueError(f"unsupported_extension:{file_path}")
    data = _load_doc(file_path)
    for key in ("name", "triggers", "conditions", "actions"):
        if key not in data:
            raise ValueError(f"missing_key:{key}:{file_path}")
    return data


def load_rules_from_dir(
    *,
    tenant_id: str,
    rules_dir: Path | str,
    db_path: Path | str | None = None,
) -> list[str]:
    base = Path(rules_dir)
    if not base.exists():
        raise ValueError(f"rules_dir_not_found:{base}")

    created_ids: list[str] = []
    for path in sorted(base.glob("*")):
        if path.suffix.lower() not in {".json", ".yaml", ".yml"}:
            continue
        doc = load_rule_file(path)
        created_ids.append(
            create_rule(
                tenant_id=tenant_id,
                name=str(doc.get("name") or "").strip(),
                description=str(doc.get("description") or "").strip(),
                is_enabled=bool(doc.get("enabled", True)),
                max_executions_per_minute=int(doc.get("max_executions_per_minute") or 10),
                triggers=doc.get("triggers") or [],
                conditions=doc.get("conditions") or [],
                actions=doc.get("actions") or [],
                db_path=db_path,
            )
        )
    return created_ids
