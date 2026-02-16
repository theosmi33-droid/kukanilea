from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from app.config import Config
from app.license import load_runtime_license_state
from app.omni.hub import ingest_fixture


def _read_only_runtime() -> bool:
    state = load_runtime_license_state(
        license_path=Path(str(Config.LICENSE_PATH)),
        trial_path=Path(str(Config.TRIAL_PATH)),
        trial_days=int(getattr(Config, "TRIAL_DAYS", 14)),
    )
    return bool(state.get("read_only", False))


def _next_actions_for_reason(reason: str | None) -> list[str]:
    key = str(reason or "").strip()
    if key == "read_only":
        return [
            "READ_ONLY deaktivieren, bevor --commit genutzt wird.",
            "Alternativ mit --dry-run prüfen.",
        ]
    if key == "unsupported_channel":
        return ["Nur --channel email ist in v0 verfügbar."]
    if key == "fixture_not_found":
        return ["Fixture-Pfad prüfen und erneut ausführen."]
    if key == "payload_too_large":
        return ["Kleinere Fixture-Datei verwenden (<10MB)."]
    if key == "validation_error":
        return ["Fixture/Parameter prüfen und erneut ausführen."]
    return []


def _reason_message(reason: str | None) -> str:
    if not reason:
        return "OK"
    if reason == "read_only":
        return "Read-only mode aktiv. Commit wurde blockiert."
    if reason == "unsupported_channel":
        return "Channel wird nicht unterstützt."
    if reason == "fixture_not_found":
        return "Fixture-Datei nicht gefunden."
    if reason == "payload_too_large":
        return "Fixture-Datei überschreitet das Limit."
    return "Conversation ingest fehlgeschlagen."


def _to_result(
    *,
    ok: bool,
    tenant_id: str,
    channel: str,
    fixture: Path,
    dry_run: bool,
    committed: bool,
    read_only: bool,
    reason: str | None,
    results: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    rows = list(results or [])
    event_ids = [str(r.get("event_id") or "") for r in rows if r.get("event_id")]
    reasons: list[str] = []
    if reason:
        reasons.append(reason)
    for row in rows:
        r = str(row.get("reason") or "")
        if r:
            reasons.append(r)
    reasons = sorted(set(reasons))
    return {
        "ok": bool(ok),
        "tenant_id": tenant_id,
        "channel": channel,
        "fixture": fixture.name,
        "dry_run": bool(dry_run),
        "committed": bool(committed),
        "n_events": len(rows),
        "reasons": reasons,
        "next_actions": _next_actions_for_reason(
            reason or (reasons[0] if reasons else None)
        ),
        "event_ids": event_ids,
        "read_only": bool(read_only),
        "message": _reason_message(reason),
    }


def _print_human(result: dict[str, Any]) -> None:
    print("Conversation Hub")
    print(f"tenant: {result.get('tenant_id')}")
    print(f"channel: {result.get('channel')}")
    print(f"fixture: {result.get('fixture')}")
    print(f"ok: {bool(result.get('ok'))}")
    print(f"dry_run: {bool(result.get('dry_run'))}")
    print(f"committed: {bool(result.get('committed'))}")
    print(f"n_events: {int(result.get('n_events') or 0)}")
    print(f"read_only: {bool(result.get('read_only'))}")
    print(f"reasons: {result.get('reasons') or '-'}")
    print(f"event_ids: {result.get('event_ids') or '-'}")
    print(f"next_actions: {result.get('next_actions') or '-'}")
    print(f"message: {result.get('message') or '-'}")


def main() -> int:
    parser = argparse.ArgumentParser(description="Omni Conversation Hub ingest tool")
    parser.add_argument("--tenant", required=True)
    parser.add_argument("--channel", required=True)
    parser.add_argument("--fixture", required=True)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--commit", action="store_true")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    tenant = str(args.tenant or "").strip() or "default"
    channel = str(args.channel or "").strip().lower()
    fixture = Path(str(args.fixture))
    read_only = _read_only_runtime()
    dry_run = True
    if args.commit:
        dry_run = False
    if args.dry_run:
        dry_run = True

    if not dry_run and read_only:
        result = _to_result(
            ok=False,
            tenant_id=tenant,
            channel=channel,
            fixture=fixture,
            dry_run=False,
            committed=False,
            read_only=True,
            reason="read_only",
        )
        if args.json:
            print(json.dumps(result, ensure_ascii=False, sort_keys=True))
        else:
            _print_human(result)
        return 1

    try:
        ingest_result = ingest_fixture(
            tenant,
            channel=channel,
            fixture_path=fixture,
            actor_user_id="devtools",
            dry_run=dry_run,
        )
        results = list(ingest_result.get("results") or [])
        ok = bool(ingest_result.get("ok")) and all(
            bool(item.get("ok")) for item in results
        )
        result = _to_result(
            ok=ok,
            tenant_id=tenant,
            channel=channel,
            fixture=fixture,
            dry_run=dry_run,
            committed=not dry_run,
            read_only=read_only,
            reason=None if ok else "validation_error",
            results=results,
        )
    except PermissionError:
        result = _to_result(
            ok=False,
            tenant_id=tenant,
            channel=channel,
            fixture=fixture,
            dry_run=dry_run,
            committed=False,
            read_only=read_only,
            reason="read_only",
        )
    except ValueError as exc:
        reason = str(exc) or "validation_error"
        result = _to_result(
            ok=False,
            tenant_id=tenant,
            channel=channel,
            fixture=fixture,
            dry_run=dry_run,
            committed=False,
            read_only=read_only,
            reason=reason,
        )
    except Exception:
        result = _to_result(
            ok=False,
            tenant_id=tenant,
            channel=channel,
            fixture=fixture,
            dry_run=dry_run,
            committed=False,
            read_only=read_only,
            reason="unexpected_error",
        )

    if args.json:
        print(json.dumps(result, ensure_ascii=False, sort_keys=True))
    else:
        _print_human(result)
    return 0 if result.get("ok") else 1


if __name__ == "__main__":
    raise SystemExit(main())
