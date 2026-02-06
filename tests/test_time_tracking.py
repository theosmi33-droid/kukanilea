import kukanilea_core_v3_fixed as core


def _setup(tmp_path):
    core.DB_PATH = tmp_path / "core.db"
    core.EINGANG = tmp_path / "eingang"
    core.PENDING_DIR = tmp_path / "pending"
    core.DONE_DIR = tmp_path / "done"
    core.BASE_PATH = tmp_path / "base"
    core.db_init()


def test_time_tracking_single_timer(tmp_path):
    _setup(tmp_path)
    project_id = core.time_project_create(tenant="KUKANILEA", name="Projekt A")
    first_id = core.time_entry_start(tenant="KUKANILEA", username="dev", project_id=project_id)
    second_id = core.time_entry_start(tenant="KUKANILEA", username="dev", project_id=project_id)
    assert first_id == second_id
    stopped_id = core.time_entry_stop(tenant="KUKANILEA", username="dev")
    assert stopped_id == first_id


def test_time_tracking_tenant_isolation(tmp_path):
    _setup(tmp_path)
    project_id = core.time_project_create(tenant="KUKANILEA", name="Projekt A")
    core.time_entry_start(tenant="KUKANILEA", username="dev", project_id=project_id)
    entries = core.time_entry_list_week(tenant="OTHER", username="dev", week_start="2024-01-01")
    assert entries == []
