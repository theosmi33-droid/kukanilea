import sqlite3

from app.services import api_dispatcher


def _create_queue_db(path):
    con = sqlite3.connect(path)
    con.execute(
        """
        CREATE TABLE api_outbound_queue(
          id TEXT PRIMARY KEY,
          tenant_id TEXT NOT NULL,
          target_system TEXT NOT NULL,
          payload TEXT NOT NULL,
          file_path TEXT,
          status TEXT DEFAULT 'pending',
          retry_count INTEGER DEFAULT 0,
          created_at TEXT NOT NULL,
          last_attempt TEXT,
          error_message TEXT
        );
        """
    )
    con.execute(
        """
        INSERT INTO api_outbound_queue (id, tenant_id, target_system, payload, status, retry_count, created_at)
        VALUES ('job-1', 'tenant-1', 'unknown', '{}', 'pending', 0, '2026-01-01T00:00:00Z')
        """
    )
    con.commit()
    con.close()


def test_dispatcher_skips_online_probe_without_lexoffice_key(tmp_path, monkeypatch):
    db_path = tmp_path / "auth.sqlite3"
    _create_queue_db(db_path)

    monkeypatch.setenv("KUKANILEA_EXTERNAL_CALLS_ENABLED", "1")
    monkeypatch.setattr(api_dispatcher.Config, "LEXOFFICE_API_KEY", "")

    def _fail_online_probe():
        raise AssertionError("is_online should not be called without lexoffice key")

    monkeypatch.setattr(api_dispatcher, "is_online", _fail_online_probe)

    dispatcher = api_dispatcher.APIDispatcher(str(db_path))
    dispatcher.process_queue()

    con = sqlite3.connect(db_path)
    row = con.execute(
        "SELECT status, retry_count, error_message FROM api_outbound_queue WHERE id = 'job-1'"
    ).fetchone()
    con.close()

    assert row is not None
    assert row[0] == "pending"
    assert row[1] == 1
    assert "Unknown target system" in (row[2] or "")
