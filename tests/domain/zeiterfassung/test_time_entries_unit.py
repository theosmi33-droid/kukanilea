from __future__ import annotations

import csv
import io

import pytest

from app import core
from app.modules.zeiterfassung import contracts


def test_time_entry_start_stop_supports_seconds_and_task_project_link(auth_client):
    app = auth_client.application
    with app.app_context():
        tenant = "KUKANILEA"
        project = core.time_project_create(tenant_id=tenant, name="Innenausbau", created_by="admin")
        task_id = core.task_create(
            tenant=tenant,
            severity="INFO",
            task_type="GENERAL",
            title="Montage vorbereiten",
            created_by="admin",
        )

        entry = core.time_entry_start(
            tenant_id=tenant,
            user="admin",
            project_id=int(project["id"]),
            task_id=task_id,
            started_at_seconds=1772352000,
        )
        stopped = core.time_entry_stop(
            tenant_id=tenant,
            user="admin",
            entry_id=int(entry["id"]),
            ended_at_seconds=1772355600,
        )

        assert stopped["duration_seconds"] == 3600
        assert stopped["start_at_seconds"] == 1772352000
        assert stopped["end_at_seconds"] == 1772355600
        assert stopped["task_id"] == task_id
        assert stopped["project_id"] == int(project["id"])


def test_absence_export_stub_supports_vacation_and_sick(auth_client):
    app = auth_client.application
    with app.app_context():
        tenant = "KUKANILEA"
        vacation = core.time_absence_create(
            tenant_id=tenant,
            user="admin",
            absence_type="vacation",
            start_at="2026-04-10T00:00:00Z",
            end_at="2026-04-11T00:00:00Z",
        )
        sick = core.time_absence_create(
            tenant_id=tenant,
            user="admin",
            absence_type="sick",
            start_at="2026-04-12T00:00:00Z",
            end_at="2026-04-13T00:00:00Z",
        )

        payload = core.time_absences_export_csv(tenant_id=tenant, user="admin")
        rows = list(csv.DictReader(io.StringIO(payload)))

        assert vacation["absence_type"] == "VACATION"
        assert sick["absence_type"] == "SICK"
        assert [row["absence_type"] for row in rows] == ["SICK", "VACATION"]


def test_time_entry_seconds_out_of_range_raise_value_error(auth_client):
    app = auth_client.application
    with app.app_context():
        with pytest.raises(ValueError, match="invalid_timestamp_seconds"):
            core.time_entry_start(
                tenant_id="KUKANILEA",
                user="admin",
                started_at_seconds=10**30,
            )


def test_time_entry_stop_seconds_out_of_range_raise_value_error(auth_client):
    app = auth_client.application
    with app.app_context():
        running = core.time_entry_start(
            tenant_id="KUKANILEA",
            user="admin",
            started_at="2026-04-10T08:00:00Z",
        )
        with pytest.raises(ValueError, match="invalid_timestamp_seconds"):
            core.time_entry_stop(
                tenant_id="KUKANILEA",
                user="admin",
                entry_id=int(running["id"]),
                ended_at_seconds=10**30,
            )


def test_time_entry_update_seconds_out_of_range_raise_value_error(auth_client):
    app = auth_client.application
    with app.app_context():
        entry = core.time_entry_start(
            tenant_id="KUKANILEA",
            user="admin",
            started_at="2026-04-10T08:00:00Z",
        )
        with pytest.raises(ValueError, match="invalid_timestamp_seconds"):
            core.time_entry_update(
                tenant_id="KUKANILEA",
                entry_id=int(entry["id"]),
                end_at_seconds=10**30,
                user="admin",
            )


def test_zeiterfassung_health_reports_offline_persistence(auth_client):
    app = auth_client.application
    with app.app_context():
        payload, status = contracts.build_health("KUKANILEA")

    assert status in {200, 503}
    assert payload["metrics"].get("offline_persistence") == 1
