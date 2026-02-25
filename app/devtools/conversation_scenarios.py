from __future__ import annotations

import argparse
import contextlib
import json
import os
import sqlite3
from collections.abc import Iterator
from pathlib import Path
from typing import Any

from app.core import logic as legacy_core
from app.config import Config
from app.devtools.sandbox import cleanup_sandbox, create_sandbox_copy
from app.omni.hub import get_event, ingest_fixture, list_events

PII_MARKERS = ["qa-test-pii@example.com", "+49 151 12345678"]


def _resolve_config_object() -> Any:
    import app.config as config_module

    for name in ("Config", "Settings", "AppConfig"):
        candidate = getattr(config_module, name, None)
        if candidate is not None and hasattr(candidate, "CORE_DB"):
            return candidate
    return config_module


@contextlib.contextmanager
def _sandbox_db() -> Iterator[Path]:
    sandbox_db, sandbox_dir = create_sandbox_copy("omni-scenarios")
    cfg = _resolve_config_object()
    old_cfg_core = getattr(cfg, "CORE_DB", None)
    old_cfg_auth = getattr(cfg, "AUTH_DB", None)
    old_env_core = os.environ.get("KUKANILEA_CORE_DB")
    old_env_db = os.environ.get("DB_FILENAME")
    old_env_db2 = os.environ.get("TOPHANDWERK_DB_FILENAME")
    old_core_path = Path(str(legacy_core.DB_PATH))

    os.environ["KUKANILEA_CORE_DB"] = str(sandbox_db)
    os.environ["DB_FILENAME"] = str(sandbox_db)
    os.environ["TOPHANDWERK_DB_FILENAME"] = str(sandbox_db)
    cfg.CORE_DB = sandbox_db
    Config.CORE_DB = sandbox_db
    try:
        legacy_core.set_db_path(sandbox_db)
    except Exception:
        legacy_core.DB_PATH = sandbox_db
    try:
        legacy_core.db_init()
        yield sandbox_db
    finally:
        try:
            legacy_core.set_db_path(old_core_path)
        except Exception:
            legacy_core.DB_PATH = old_core_path
        if old_cfg_core is not None:
            cfg.CORE_DB = old_cfg_core
            Config.CORE_DB = old_cfg_core
        if old_cfg_auth is not None:
            cfg.AUTH_DB = old_cfg_auth
        if old_env_core is None:
            os.environ.pop("KUKANILEA_CORE_DB", None)
        else:
            os.environ["KUKANILEA_CORE_DB"] = old_env_core
        if old_env_db is None:
            os.environ.pop("DB_FILENAME", None)
        else:
            os.environ["DB_FILENAME"] = old_env_db
        if old_env_db2 is None:
            os.environ.pop("TOPHANDWERK_DB_FILENAME", None)
        else:
            os.environ["TOPHANDWERK_DB_FILENAME"] = old_env_db2
        cleanup_sandbox(sandbox_dir)


def _fixture_bytes() -> bytes:
    return (
        b"From: QA Bot <qa-test-pii@example.com>\r\n"
        b"To: Team <ops@example.test>\r\n"
        b"Subject: Bitte Rueckruf +49 151 12345678\r\n"
        b"Date: Mon, 15 Feb 2026 10:00:00 +0000\r\n"
        b"Message-ID: <qa-scenario-001@example.test>\r\n"
        b"\r\n"
        b"Hallo,\n"
        b"Bitte kontaktiert qa-test-pii@example.com unter +49 151 12345678.\n"
    )


def _write_fixture(base_dir: Path, name: str) -> Path:
    fixtures_dir = base_dir / "fixtures"
    fixtures_dir.mkdir(parents=True, exist_ok=True)
    path = fixtures_dir / name
    path.write_bytes(_fixture_bytes())
    return path


def _find_marker_count_events(db_path: Path, marker: str) -> int:
    con = sqlite3.connect(str(db_path))
    try:
        row = con.execute(
            """
            SELECT COUNT(*) AS c
            FROM events
            WHERE instr(lower(payload_json), lower(?)) > 0
            """,
            (marker,),
        ).fetchone()
        return int((row[0] if row else 0) or 0)
    finally:
        con.close()


def _scenario_email_with_pii(tenant_id: str) -> dict[str, Any]:
    steps: list[str] = []
    invariants: list[str] = []
    reasons: list[str] = []
    with _sandbox_db() as sandbox_db:
        fixture = _write_fixture(sandbox_db.parent, "email_with_pii.eml")
        steps.append("fixture_created")

        dry = ingest_fixture(
            tenant_id,
            channel="email",
            fixture_path=fixture,
            actor_user_id="scenario",
            dry_run=True,
        )
        steps.append("dry_run_ingest")
        if not bool(dry.get("ok")):
            reasons.append("dry_run_failed")

        live = ingest_fixture(
            tenant_id,
            channel="email",
            fixture_path=fixture,
            actor_user_id="scenario",
            dry_run=False,
        )
        steps.append("commit_ingest")
        if not bool(live.get("ok")):
            reasons.append("commit_failed")

        events = list_events(tenant_id, channel="email", limit=10)
        if events:
            invariants.append("event_created")
        else:
            reasons.append("event_missing")

        pii_hits_conversation = 0
        for marker in PII_MARKERS:
            pii_hits_conversation += _find_marker_count_events(
                sandbox_db, marker
            )  # events table
        con = sqlite3.connect(str(sandbox_db))
        try:
            for marker in PII_MARKERS:
                row = con.execute(
                    """
                    SELECT COUNT(*) AS c
                    FROM conversation_events
                    WHERE tenant_id=? AND instr(lower(redacted_payload_json), lower(?)) > 0
                    """,
                    (tenant_id, marker),
                ).fetchone()
                pii_hits_conversation += int((row[0] if row else 0) or 0)
        finally:
            con.close()

        if pii_hits_conversation == 0:
            invariants.append("pii_redacted")
        else:
            reasons.append("pii_leak")

    ok = not reasons
    return {
        "ok": ok,
        "scenario": "email_with_pii",
        "steps": steps,
        "invariants_passed": invariants,
        "reasons": sorted(set(reasons)),
        "next_actions": _next_actions(reasons),
    }


def _scenario_two_tenants(tenant_id: str) -> dict[str, Any]:
    tenant_a = tenant_id
    tenant_b = f"{tenant_id}_B"
    steps: list[str] = []
    invariants: list[str] = []
    reasons: list[str] = []
    with _sandbox_db() as sandbox_db:
        fixture = _write_fixture(sandbox_db.parent, "two_tenants.eml")
        steps.append("fixture_created")
        ingest_fixture(
            tenant_a,
            channel="email",
            fixture_path=fixture,
            actor_user_id="scenario",
            dry_run=False,
        )
        ingest_fixture(
            tenant_b,
            channel="email",
            fixture_path=fixture,
            actor_user_id="scenario",
            dry_run=False,
        )
        steps.append("tenant_a_and_b_ingested")

        rows_a = list_events(tenant_a, channel="email", limit=20)
        rows_b = list_events(tenant_b, channel="email", limit=20)
        if rows_a and rows_b:
            invariants.append("both_tenants_have_data")
        else:
            reasons.append("tenant_data_missing")

        if rows_a:
            other = get_event(tenant_b, str(rows_a[0]["id"]))
            if other is None:
                invariants.append("tenant_isolation")
            else:
                reasons.append("tenant_leak")
        else:
            reasons.append("tenant_data_missing")

    ok = not reasons
    return {
        "ok": ok,
        "scenario": "two_tenants",
        "steps": steps,
        "invariants_passed": invariants,
        "reasons": sorted(set(reasons)),
        "next_actions": _next_actions(reasons),
    }


def _next_actions(reasons: list[str]) -> list[str]:
    if "pii_leak" in reasons:
        return [
            "Redaction-Logik im Omni Hub prüfen.",
            "Keine weiteren Merges bis die PII-Invariante grün ist.",
        ]
    if "tenant_leak" in reasons:
        return [
            "Tenant-Filter in list/get/store prüfen.",
            "Isolation-Tests vor Merge erweitern.",
        ]
    if "event_missing" in reasons or "commit_failed" in reasons:
        return [
            "Schema-Migration für conversation_events prüfen.",
            "Dry-run/commit Ablauf im Hub verifizieren.",
        ]
    if "tenant_data_missing" in reasons:
        return ["Fixture-Ingest und Query-Pfad für beide Tenants erneut prüfen."]
    return []


def run_scenario(tenant_id: str, scenario: str) -> dict[str, Any]:
    name = str(scenario or "").strip().lower()
    if name == "email_with_pii":
        return _scenario_email_with_pii(tenant_id)
    if name == "two_tenants":
        return _scenario_two_tenants(tenant_id)
    return {
        "ok": False,
        "scenario": name,
        "steps": [],
        "invariants_passed": [],
        "reasons": ["unknown_scenario"],
        "next_actions": ["Verfügbare Szenarien: email_with_pii, two_tenants"],
    }


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Deterministic Omni conversation scenarios"
    )
    parser.add_argument("--tenant", required=True)
    parser.add_argument("--scenario", required=True)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    report = run_scenario(args.tenant, args.scenario)
    if args.json:
        print(json.dumps(report, ensure_ascii=False, sort_keys=True))
    else:
        print("Conversation Scenarios")
        print(f"scenario: {report.get('scenario')}")
        print(f"ok: {bool(report.get('ok'))}")
        print(f"steps: {report.get('steps')}")
        print(f"invariants_passed: {report.get('invariants_passed')}")
        print(f"reasons: {report.get('reasons')}")
        print(f"next_actions: {report.get('next_actions')}")
    return 0 if report.get("ok") else 1


if __name__ == "__main__":
    raise SystemExit(main())
