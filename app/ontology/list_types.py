from __future__ import annotations

from .registry import get_registry


def main() -> int:
    reg = get_registry()
    rows = reg.list_types()
    if not rows:
        print("ontology: no registered types")
        return 0
    for row in rows:
        print(
            f"{row.get('type_name')} -> {row.get('table_name')}"
            f" (pk={row.get('pk_field')}, title={row.get('title_field')}, desc={row.get('description_field')})"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
