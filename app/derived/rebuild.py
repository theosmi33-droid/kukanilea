from __future__ import annotations

from .views import rebuild_all


def main() -> int:
    out = rebuild_all()
    print(
        f"derived: rebuilt active_timers={out['active_timers']} budget_rows={out['budget_rows']}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
