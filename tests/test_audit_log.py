import kukanilea_core_v3_fixed as core


def test_audit_log_writes(tmp_path):
    core.DB_PATH = tmp_path / "core.db"
    core.BASE_PATH = tmp_path / "base"
    core.EINGANG = tmp_path / "eingang"
    core.PENDING_DIR = tmp_path / "pending"
    core.DONE_DIR = tmp_path / "done"
    core.db_init()

    core.audit_log(
        user="dev",
        role="ADMIN",
        action="test",
        target="demo",
        meta={"k": "v"},
        tenant_id="KUKANILEA",
    )
    events = core.audit_list(tenant_id="KUKANILEA", limit=10)
    assert events
    assert events[0]["action"] == "test"
