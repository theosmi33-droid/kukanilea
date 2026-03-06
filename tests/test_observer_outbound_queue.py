import sqlite3

from app.core import observer


def test_read_outbound_queue_stats_uses_env_db(monkeypatch, tmp_path):
    db_path = tmp_path / "auth.sqlite3"
    conn = sqlite3.connect(db_path)
    conn.execute("CREATE TABLE api_outbound_queue (status TEXT NOT NULL)")
    conn.execute("INSERT INTO api_outbound_queue(status) VALUES ('pending'), ('pending'), ('failed')")
    conn.commit()
    conn.close()

    monkeypatch.setenv("KUKANILEA_AUTH_DB", str(db_path))

    stats = observer._read_outbound_queue_stats()

    assert stats == {"pending": 2, "failed": 1}


def test_resolve_auth_db_path_prefers_local_instance(monkeypatch, tmp_path):
    fake_observer = tmp_path / "app" / "core" / "observer.py"
    fake_observer.parent.mkdir(parents=True)
    fake_observer.touch()
    local_db = tmp_path / "instance" / "auth.sqlite3"
    local_db.parent.mkdir(parents=True)
    local_db.touch()

    monkeypatch.delenv("KUKANILEA_AUTH_DB", raising=False)
    monkeypatch.setattr(observer, "__file__", str(fake_observer))

    assert observer._resolve_auth_db_path() == str(local_db)
