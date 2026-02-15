from __future__ import annotations

from pathlib import Path

import kukanilea_core_v3_fixed as core
from app.autonomy.maintenance import get_health_overview, run_smoke_test
from app.autonomy.source_scan import scan_sources_once, source_watch_config_update
from app.knowledge.core import knowledge_policy_update


def _init_core(tmp_path: Path) -> None:
    core.DB_PATH = tmp_path / "core.db"
    core.BASE_PATH = tmp_path / "base"
    core.EINGANG = tmp_path / "eingang"
    core.PENDING_DIR = tmp_path / "pending"
    core.DONE_DIR = tmp_path / "done"
    core.db_init()


def test_scan_history_is_recorded_and_visible_in_health(
    tmp_path: Path, monkeypatch
) -> None:
    _init_core(tmp_path)
    monkeypatch.setenv("KUKANILEA_ANONYMIZATION_KEY", "scan-test-key")
    knowledge_policy_update(
        "TENANT_A",
        actor_user_id="dev",
        allow_customer_pii=True,
        allow_documents=True,
    )

    docs = tmp_path / "docs"
    docs.mkdir(parents=True, exist_ok=True)
    (docs / "doc.txt").write_text("content", encoding="utf-8")
    source_watch_config_update("TENANT_A", documents_inbox_dir=str(docs), enabled=True)

    result = scan_sources_once("TENANT_A", actor_user_id="dev")
    assert int(result["ingested_ok"]) == 1

    overview = get_health_overview("TENANT_A", history_limit=10)
    assert overview["scan_history"]
    latest = overview["latest_scan"]
    assert latest is not None
    assert int(latest["files_ingested"]) >= 1


def test_smoke_test_updates_status(tmp_path: Path) -> None:
    _init_core(tmp_path)
    result = run_smoke_test("TENANT_A", actor_user_id="dev")
    assert result["result"] in {"ok", "warn", "error"}

    overview = get_health_overview("TENANT_A", history_limit=5)
    status = overview["status"]
    assert status["last_smoke_test_at"] is not None
    assert status["last_smoke_test_result"] in {"ok", "warn", "error"}
