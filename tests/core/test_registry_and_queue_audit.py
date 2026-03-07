from __future__ import annotations

import sqlite3
import threading

from app.core.audit import AuditVault
from app.core.registry import ComponentRegistry
from app.core.task_queue import BackgroundTaskQueue


class _Agent:
    pass


def test_component_registry_roundtrip_and_copy_isolation() -> None:
    registry = ComponentRegistry()

    def _tool(payload):
        return payload

    registry.register_agent("agent.demo", _Agent)
    registry.register_tool("tool.demo", _tool)
    registry.register_service("svc.demo", object())

    assert registry.get_agent("agent.demo") is _Agent
    assert registry.get_tool("tool.demo") is _tool

    agents_snapshot = registry.get_all_agents()
    agents_snapshot["agent.injected"] = str
    assert registry.get_agent("agent.injected") is None


def test_audit_vault_chain_and_tenant_filter(tmp_path) -> None:
    db_path = tmp_path / "audit.sqlite3"
    vault = AuditVault(db_path)

    vault.store_evidence(
        doc_id="doc-1",
        tenant_id="tenant-a",
        metadata_hash="m1",
        payload={"kind": "upload", "status": "queued"},
    )
    vault.store_evidence(
        doc_id="doc-2",
        tenant_id="tenant-b",
        metadata_hash="m2",
        payload={"kind": "mail", "status": "sent"},
    )

    ok, errors = vault.verify_chain()
    assert ok is True
    assert errors == []

    tenant_a_rows = vault.get_audit_trail(tenant_id="tenant-a")
    assert len(tenant_a_rows) == 1
    assert tenant_a_rows[0]["tenant_id"] == "tenant-a"


def test_audit_vault_verify_chain_detects_manual_tampering(tmp_path) -> None:
    db_path = tmp_path / "audit.sqlite3"
    vault = AuditVault(db_path)
    vault.store_evidence("doc-1", "tenant-a", "meta", {"x": 1})

    con = sqlite3.connect(str(db_path))
    try:
        con.execute("DROP TRIGGER IF EXISTS prevent_vault_update")
        con.execute(
            "UPDATE evidence_vault SET payload_json=? WHERE id=1",
            ('{"x":999}',),
        )
        con.commit()
    finally:
        con.close()

    ok, errors = vault.verify_chain()
    assert ok is False
    assert any("Node-Hash Mismatch" in row["error"] for row in errors)


def test_background_task_queue_records_failures_without_flakes() -> None:
    q = BackgroundTaskQueue(num_workers=1)
    ran_ok = threading.Event()

    def _ok_task():
        ran_ok.set()

    def _failing_task():
        raise RuntimeError("boom")

    q.start()
    try:
        q.submit(_ok_task)
        q.submit(_failing_task)
        assert ran_ok.wait(timeout=1.5)

        q.q.join()
        stats = q.get_stats()
        assert stats["failed"] == 1
        assert stats["workers"] == 1
        assert stats["pending"] == 0
    finally:
        q.stop()

    stopped_stats = q.get_stats()
    assert stopped_stats["workers"] == 0
