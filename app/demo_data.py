from __future__ import annotations

import os
import re
import sqlite3
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from app.core import logic as core
from app.auth import hash_password
from app.automation import store as automation_store
from app.autonomy.source_scan import scan_sources_once, source_watch_config_update
from app.config import Config
from app.db import AuthDB
from app.knowledge.core import knowledge_policy_update
from app.lead_intake.core import leads_create, leads_list

DEMO_CONTACTS = [
    {
        "company": "Mustermann Ausbau GmbH",
        "name": "Max Mustermann",
        "email": "max@demo.invalid",
        "phone": "+49 000 1234567",
    },
    {
        "company": "Beispiel Elektrotechnik AG",
        "name": "Erika Beispiel",
        "email": "erika@demo.invalid",
        "phone": "+49 000 7654321",
    },
    {
        "company": "Mueller Bau Partner KG",
        "name": "Hans Mueller",
        "email": "hans@demo.invalid",
        "phone": "+49 000 5551234",
    },
    {
        "company": "Schmidt Service und Wartung",
        "name": "Laura Schmidt",
        "email": "laura@demo.invalid",
        "phone": "+49 000 6667890",
    },
    {
        "company": "Wagner Sanitaer Technik",
        "name": "Peter Wagner",
        "email": "peter@demo.invalid",
        "phone": "+49 000 7773456",
    },
]

DEMO_TASKS = [
    {"title": "Angebot fuer Mustermann vorbereiten", "status": "OPEN"},
    {"title": "Eingangspost pruefen", "status": "IN_PROGRESS"},
    {"title": "Rechnungslauf Januar abschliessen", "status": "RESOLVED"},
]

DEMO_DOCUMENTS = [
    {
        "filename": "2026-01-03_rechnung_DEMO-1001.txt",
        "mime_type": "text/plain",
        "tags": ["Rechnung", "Finanzen"],
    },
    {
        "filename": "2026-01-05_angebot_DEMO-1002.txt",
        "mime_type": "text/plain",
        "tags": ["Angebot", "Vertrieb"],
    },
    {
        "filename": "2026-01-07_vertrag_DEMO-1003.txt",
        "mime_type": "text/plain",
        "tags": ["Vertrag", "Recht"],
    },
    {
        "filename": "2026-01-09_rechnung_DEMO-1004.txt",
        "mime_type": "text/plain",
        "tags": ["Rechnung", "Offen"],
    },
    {
        "filename": "2026-01-11_angebot_DEMO-1005.txt",
        "mime_type": "text/plain",
        "tags": ["Angebot", "Nachfassen"],
    },
    {
        "filename": "2026-01-13_vertrag_DEMO-1006.txt",
        "mime_type": "text/plain",
        "tags": ["Vertrag", "Bestand"],
    },
    {
        "filename": "2026-01-15_rechnung_DEMO-1007.txt",
        "mime_type": "text/plain",
        "tags": ["Rechnung", "Eingang"],
    },
    {
        "filename": "2026-01-17_angebot_DEMO-1008.txt",
        "mime_type": "text/plain",
        "tags": ["Angebot", "Projekt"],
    },
    {
        "filename": "2026-01-19_vertrag_DEMO-1009.txt",
        "mime_type": "text/plain",
        "tags": ["Vertrag", "Ablage"],
    },
    {
        "filename": "2026-01-21_rechnung_DEMO-1010.txt",
        "mime_type": "text/plain",
        "tags": ["Rechnung", "Wichtig"],
    },
]

DEMO_RULE_NAME = "DEMO: Dokument -> Aufgabe Rechnung pruefen"


def _now_iso() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat()


def _tenant_id_from_name(tenant_name: str) -> str:
    slug = re.sub(r"[^A-Za-z0-9]+", "_", str(tenant_name or "").strip().upper())
    slug = slug.strip("_")
    return slug or "DEMO"


def _connect(path: Path) -> sqlite3.Connection:
    con = sqlite3.connect(str(path), timeout=30)
    con.row_factory = sqlite3.Row
    return con


def _table_exists(con: sqlite3.Connection, table_name: str) -> bool:
    row = con.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name=? LIMIT 1",
        (table_name,),
    ).fetchone()
    return bool(row)


def _core_db_setup(db_path: Path) -> None:
    path = Path(db_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    core.set_db_path(path)
    os.environ["DB_FILENAME"] = str(path)
    os.environ["KUKANILEA_DB_FILENAME"] = str(path)
    os.environ["TOPHANDWERK_DB_FILENAME"] = str(path)
    automation_store.ensure_automation_schema(path)


def _purge_tenant_data(db_path: Path, tenant_id: str) -> None:
    tenant_norm = core.normalize_component(tenant_id)
    tenant_lower = tenant_norm.lower()
    con = _connect(db_path)
    try:
        con.execute("PRAGMA foreign_keys=OFF")
        rows = con.execute(
            "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name ASC"
        ).fetchall()
        for row in rows:
            table_name = str(row["name"])
            if table_name.startswith("sqlite_"):
                continue
            cols = {
                str(c["name"])
                for c in con.execute(f"PRAGMA table_info({table_name})").fetchall()
            }
            if "tenant_id" in cols:
                con.execute(
                    f"DELETE FROM {table_name} WHERE tenant_id=?", (tenant_norm,)
                )
            elif "tenant" in cols:
                con.execute(f"DELETE FROM {table_name} WHERE tenant=?", (tenant_lower,))
        con.execute("PRAGMA foreign_keys=ON")
        con.commit()
    finally:
        con.close()


def _purge_auth_demo(auth_db_path: Path, tenant_id: str, username: str) -> None:
    con = sqlite3.connect(str(auth_db_path), timeout=30)
    try:
        con.execute("DELETE FROM memberships WHERE tenant_id=?", (tenant_id,))
        con.execute("DELETE FROM tenants WHERE tenant_id=?", (tenant_id,))
        con.execute("DELETE FROM users WHERE username=?", (username,))
        con.commit()
    finally:
        con.close()


def _ensure_auth_demo(
    auth_db_path: Path,
    *,
    tenant_id: str,
    tenant_name: str,
    username: str,
    password: str,
) -> None:
    auth_db = AuthDB(auth_db_path)
    auth_db.init()
    now_iso = _now_iso()
    auth_db.upsert_tenant(tenant_id, tenant_name, now_iso)
    auth_db.upsert_user(username, hash_password(password), now_iso)
    auth_db.upsert_membership(username, tenant_id, "ADMIN", now_iso)


def _ensure_customers_and_contacts(tenant_id: str) -> list[str]:
    existing_customers = {
        str(item.get("name") or ""): str(item.get("id") or "")
        for item in core.customers_list(tenant_id=tenant_id, limit=500)
    }
    customer_ids: list[str] = []
    for record in DEMO_CONTACTS:
        company = str(record["company"])
        customer_id = existing_customers.get(company)
        if not customer_id:
            customer_id = core.customers_create(
                tenant_id=tenant_id,
                name=company,
                notes="Demo customer generated by seed_demo_data.py",
                actor_user_id=None,
            )
            existing_customers[company] = customer_id
        customer_ids.append(customer_id)

        contacts = core.contacts_list_by_customer(tenant_id, customer_id)
        emails = {str(item.get("email") or "").lower() for item in contacts}
        target_email = str(record["email"]).lower()
        if target_email in emails:
            continue
        core.contacts_create(
            tenant_id=tenant_id,
            customer_id=customer_id,
            name=str(record["name"]),
            email=target_email,
            phone=str(record["phone"]),
            role="Ansprechpartner",
            notes="Demo contact",
            actor_user_id=None,
        )
    return customer_ids


def _all_task_rows(tenant_id: str) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for status in ("OPEN", "IN_PROGRESS", "RESOLVED", "DISMISSED"):
        rows.extend(core.task_list(tenant=tenant_id, status=status, limit=2000))
    return rows


def _ensure_tasks(tenant_id: str) -> None:
    existing_by_title = {
        str(item.get("title") or ""): int(item.get("id") or 0)
        for item in _all_task_rows(tenant_id)
        if item.get("title")
    }
    for record in DEMO_TASKS:
        title = str(record["title"])
        target_status = str(record["status"])
        task_id = existing_by_title.get(title)
        if not task_id:
            task_id = core.task_create(
                tenant=tenant_id,
                severity="INFO",
                task_type="GENERAL",
                title=title,
                details="Demo task",
                created_by="demo",
                meta={"demo_seed": True},
            )
            existing_by_title[title] = task_id
        if target_status != "OPEN":
            core.task_set_status(
                task_id,
                target_status,
                resolved_by="demo",
                tenant=tenant_id,
            )


def _ensure_demo_lead(tenant_id: str, customer_ids: list[str]) -> None:
    rows = leads_list(tenant_id=tenant_id, q="Wichtige Rechnung", limit=20)
    if any(
        str(item.get("subject") or "") == "Wichtige Rechnung pruefen" for item in rows
    ):
        return
    leads_create(
        tenant_id=tenant_id,
        source="manual",
        contact_name="Max Mustermann",
        contact_email="max@demo.invalid",
        contact_phone="+49 000 1234567",
        subject="Wichtige Rechnung pruefen",
        message="Bitte Rechnung mit Referenz DEMO-1010 priorisiert pruefen.",
        customer_id=customer_ids[0] if customer_ids else None,
        notes="Demo lead generated by seed script",
        actor_user_id="demo",
    )


def _ensure_demo_rule(tenant_id: str, db_path: Path) -> None:
    rules = automation_store.list_rules(tenant_id=tenant_id, db_path=db_path)
    if any(str(item.get("name") or "") == DEMO_RULE_NAME for item in rules):
        return
    automation_store.create_rule(
        tenant_id=tenant_id,
        name=DEMO_RULE_NAME,
        description="Erstellt Demo-Task fuer markierte Rechnungen",
        is_enabled=True,
        max_executions_per_minute=10,
        triggers=[
            {
                "trigger_type": "document.uploaded",
                "config": {"doctype": "invoice"},
            }
        ],
        conditions=[
            {
                "condition_type": "field_contains",
                "config": {"field": "subject", "contains": "wichtig"},
            }
        ],
        actions=[
            {
                "action_type": "create_task",
                "config": {
                    "title": "Rechnung pruefen",
                    "details": "Automatisch durch Demo-Regel erzeugt",
                    "due_in_days": 3,
                },
            }
        ],
        db_path=db_path,
    )


def _seed_documents(
    tenant_id: str,
    *,
    documents_root: Path,
    force: bool,
) -> dict[str, Any]:
    docs_dir = Path(documents_root)
    docs_dir.mkdir(parents=True, exist_ok=True)

    if force:
        for path in docs_dir.glob("*.txt"):
            path.unlink(missing_ok=True)

    for idx, spec in enumerate(DEMO_DOCUMENTS, start=1):
        fp = docs_dir / str(spec["filename"])
        tags = ",".join(spec.get("tags") or [])
        content = (
            f"Demo Dokument {idx}\n"
            f"Dateiname: {spec['filename']}\n"
            f"MIME: {spec['mime_type']}\n"
            f"Tags: {tags}\n"
            f"Hinweis: fiktive Pilotdaten ohne echte PII.\n"
        )
        if force or not fp.exists() or fp.read_text(encoding="utf-8") != content:
            fp.write_text(content, encoding="utf-8")

    os.environ.setdefault("KUKANILEA_ANONYMIZATION_KEY", "demo-seed-anon-key")
    os.environ.setdefault("KUKANILEA_SECRET", "demo-seed-secret")

    knowledge_policy_update(
        tenant_id,
        actor_user_id="demo",
        allow_manual=True,
        allow_tasks=True,
        allow_projects=True,
        allow_documents=True,
        allow_leads=False,
        allow_email=False,
        allow_calendar=False,
        allow_ocr=False,
        allow_customer_pii=True,
    )
    source_watch_config_update(
        tenant_id,
        documents_inbox_dir=str(docs_dir),
        enabled=True,
        max_files_per_scan=200,
        max_bytes_per_file=512_000,
    )
    return scan_sources_once(tenant_id, actor_user_id="demo", budget_ms=5000)


def _count_summary(db_path: Path, tenant_id: str) -> dict[str, int]:
    tenant = core.normalize_component(tenant_id)
    tenant_task = tenant.lower()
    con = _connect(db_path)
    try:
        counts: dict[str, int] = {
            "customers": 0,
            "contacts": 0,
            "leads": 0,
            "tasks": 0,
            "documents": 0,
            "automation_rules": 0,
        }
        table_queries = [
            ("customers", "SELECT COUNT(*) FROM customers WHERE tenant_id=?", tenant),
            ("contacts", "SELECT COUNT(*) FROM contacts WHERE tenant_id=?", tenant),
            ("leads", "SELECT COUNT(*) FROM leads WHERE tenant_id=?", tenant),
            ("tasks", "SELECT COUNT(*) FROM tasks WHERE tenant=?", tenant_task),
            (
                "documents",
                "SELECT COUNT(*) FROM source_files WHERE tenant_id=? AND source_kind='document'",
                tenant,
            ),
            (
                "automation_rules",
                "SELECT COUNT(*) FROM automation_builder_rules WHERE tenant_id=?",
                tenant,
            ),
        ]
        for key, sql, value in table_queries:
            try:
                row = con.execute(sql, (value,)).fetchone()
                counts[key] = int(row[0] if row else 0)
            except sqlite3.OperationalError:
                counts[key] = 0
        return counts
    finally:
        con.close()


def seed_demo_dataset(
    *,
    db_path: Path,
    tenant_id: str,
    tenant_name: str,
    force: bool = False,
    auth_db_path: Path | None = None,
    create_auth_user: bool = False,
    demo_username: str = "demo",
    demo_password: str = "demo",
    documents_root: Path | None = None,
) -> dict[str, Any]:
    db_target = Path(db_path)
    tenant_norm = core.normalize_component(tenant_id) or "DEMO"
    tenant_display = str(tenant_name or "DEMO AG").strip() or "DEMO AG"

    _core_db_setup(db_target)
    if force:
        _purge_tenant_data(db_target, tenant_norm)

    if create_auth_user:
        auth_path = Path(auth_db_path or Config.AUTH_DB)
        if force:
            _purge_auth_demo(auth_path, tenant_norm, demo_username)
        _ensure_auth_demo(
            auth_path,
            tenant_id=tenant_norm,
            tenant_name=tenant_display,
            username=demo_username,
            password=demo_password,
        )

    customer_ids = _ensure_customers_and_contacts(tenant_norm)
    _ensure_tasks(tenant_norm)
    _ensure_demo_lead(tenant_norm, customer_ids)

    seed_root = (
        Path(documents_root)
        if documents_root is not None
        else Path(Config.IMPORT_ROOT) / "demo_seed" / tenant_norm / "documents"
    )
    scan_result = _seed_documents(tenant_norm, documents_root=seed_root, force=force)
    _ensure_demo_rule(tenant_norm, db_target)

    summary_counts = _count_summary(db_target, tenant_norm)
    summary: dict[str, Any] = {
        "tenant_id": tenant_norm,
        "tenant_name": tenant_display,
        "demo_user": demo_username if create_auth_user else None,
        "documents_dir": str(seed_root),
        "force": bool(force),
        "scan": {
            "ok": bool(scan_result.get("ok", False)),
            "ingested_ok": int(scan_result.get("ingested_ok") or 0),
            "failed": int(scan_result.get("failed") or 0),
            "skipped_unchanged": int(scan_result.get("skipped_unchanged") or 0),
        },
    }
    summary.update(summary_counts)
    return summary


def generate_demo_data(*, db_path: Path, tenant_id: str) -> dict[str, int]:
    tenant_norm = core.normalize_component(tenant_id) or "DEMO"
    summary = seed_demo_dataset(
        db_path=Path(db_path),
        tenant_id=tenant_norm,
        tenant_name=tenant_norm,
        force=False,
        create_auth_user=False,
    )
    return {
        "customers": int(summary.get("customers") or 0),
        "contacts": int(summary.get("contacts") or 0),
        "leads": int(summary.get("leads") or 0),
        "tasks": int(summary.get("tasks") or 0),
        "documents": int(summary.get("documents") or 0),
        "automation_rules": int(summary.get("automation_rules") or 0),
    }


def demo_tenant_id_from_name(tenant_name: str) -> str:
    return _tenant_id_from_name(tenant_name)
