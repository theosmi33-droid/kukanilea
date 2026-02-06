import kukanilea_core_v3_fixed as core


def test_core_pipeline_smoke(tmp_path):
    core.DB_PATH = tmp_path / "core.db"
    core.EINGANG = tmp_path / "eingang"
    core.PENDING_DIR = tmp_path / "pending"
    core.DONE_DIR = tmp_path / "done"
    core.BASE_PATH = tmp_path / "base"
    core.db_init()

    stats = core.get_health_stats(tenant_id="KUKANILEA")
    assert "doc_count" in stats
    assert isinstance(stats["fts_enabled"], bool)
