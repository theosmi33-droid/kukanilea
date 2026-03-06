from __future__ import annotations

import sqlite3
from pathlib import Path

from app.core import observer


def _make_outbound_db(path: Path, rows: list[str]) -> None:
    conn = sqlite3.connect(path)
    conn.execute("CREATE TABLE api_outbound_queue (status TEXT NOT NULL)")
    if rows:
        values = ",".join(["(?)" for _ in rows])
        conn.execute(f"INSERT INTO api_outbound_queue(status) VALUES {values}", rows)
    conn.commit()
    conn.close()


def test_resolve_auth_db_path_uses_env_first(monkeypatch, tmp_path):
    env_db = tmp_path / "custom.sqlite3"
    monkeypatch.setenv("KUKANILEA_AUTH_DB", str(env_db))
    assert observer._resolve_auth_db_path() == str(env_db)


def test_resolve_auth_db_path_falls_back_to_legacy_when_no_env_or_instance(monkeypatch, tmp_path):
    fake_observer = tmp_path / "app" / "core" / "observer.py"
    fake_observer.parent.mkdir(parents=True)
    fake_observer.write_text("# fake", encoding="utf-8")

    monkeypatch.delenv("KUKANILEA_AUTH_DB", raising=False)
    monkeypatch.setattr(observer, "__file__", str(fake_observer))

    assert observer._resolve_auth_db_path().endswith("/data/auth.sqlite3")


def test_read_outbound_queue_stats_returns_zero_without_database(monkeypatch, tmp_path):
    missing_db = tmp_path / "missing.sqlite3"
    monkeypatch.setenv("KUKANILEA_AUTH_DB", str(missing_db))

    assert observer._read_outbound_queue_stats() == {"pending": 0, "failed": 0}


def test_read_outbound_queue_stats_handles_missing_table(monkeypatch, tmp_path):
    db_path = tmp_path / "auth.sqlite3"
    sqlite3.connect(db_path).close()
    monkeypatch.setenv("KUKANILEA_AUTH_DB", str(db_path))

    assert observer._read_outbound_queue_stats() == {"pending": 0, "failed": 0}


def test_get_system_status_without_psutil_returns_degraded(monkeypatch, tmp_path):
    db_path = tmp_path / "auth.sqlite3"
    _make_outbound_db(db_path, ["pending", "failed"])
    monkeypatch.setenv("KUKANILEA_AUTH_DB", str(db_path))
    monkeypatch.setattr(observer, "psutil", None)
    monkeypatch.setattr(observer, "_read_queue_stats", lambda: {"pending": 3, "failed": 0, "workers": 2})

    status = observer.get_system_status()

    assert status["status"] == "DEGRADED_NO_PSUTIL"
    assert status["http_code"] == 503
    assert status["observer_active"] is True
    assert status["sync_queue"]["workers"] == 2
    assert status["outbound_queue"] == {"pending": 1, "failed": 1}


def test_get_system_status_returns_warning_sync_when_failures_present(monkeypatch):
    class _Mem:
        rss = 128 * 1024 * 1024

    class _Proc:
        def memory_info(self):
            return _Mem()

    class _PsutilStub:
        @staticmethod
        def Process():
            return _Proc()

        @staticmethod
        def cpu_percent(interval=0.1):
            return 17.0

    monkeypatch.setattr(observer, "psutil", _PsutilStub)
    monkeypatch.setattr(observer, "_read_queue_stats", lambda: {"pending": 0, "failed": 1, "workers": 1})
    monkeypatch.setattr(observer, "_read_outbound_queue_stats", lambda: {"pending": 0, "failed": 0})

    status = observer.get_system_status()

    assert status["status"] == "WARNING_SYNC"
    assert status["http_code"] == 503
    assert status["cpu_usage_pct"] == 17.0


def test_get_system_status_returns_warning_memory_when_rss_too_high(monkeypatch):
    class _Mem:
        rss = 700 * 1024 * 1024

    class _Proc:
        def memory_info(self):
            return _Mem()

    class _PsutilStub:
        @staticmethod
        def Process():
            return _Proc()

        @staticmethod
        def cpu_percent(interval=0.1):
            return 8.5

    monkeypatch.setattr(observer, "psutil", _PsutilStub)
    monkeypatch.setattr(observer, "_read_queue_stats", lambda: {"pending": 0, "failed": 0, "workers": 1})
    monkeypatch.setattr(observer, "_read_outbound_queue_stats", lambda: {"pending": 0, "failed": 0})

    status = observer.get_system_status()

    assert status["status"] == "WARNING_MEMORY"
    assert status["http_code"] == 503


def test_get_system_status_returns_error_when_psutil_raises(monkeypatch):
    class _PsutilExplodes:
        @staticmethod
        def Process():
            raise RuntimeError("boom")

        @staticmethod
        def cpu_percent(interval=0.1):
            return 0.0

    monkeypatch.setattr(observer, "psutil", _PsutilExplodes)
    monkeypatch.setattr(observer, "_read_queue_stats", lambda: {"pending": 1, "failed": 0, "workers": 1})
    monkeypatch.setattr(observer, "_read_outbound_queue_stats", lambda: {"pending": 1, "failed": 0})

    status = observer.get_system_status()

    assert status["status"] == "ERROR"
    assert status["http_code"] == 500
    assert "error" in status
