from __future__ import annotations

from .core import event_verify_chain


def main() -> int:
    ok, first_bad_id, reason = event_verify_chain()
    if ok:
        print("eventlog: OK")
        return 0
    print(f"eventlog: BROKEN first_bad_id={first_bad_id} reason={reason}")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
