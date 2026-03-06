from __future__ import annotations

import json
from pathlib import Path

from app.modules.dashboard import briefing


RSS_XML = """<?xml version='1.0' encoding='UTF-8'?>
<rss version="2.0"><channel>
  <title>Local Feed</title>
  <item><title>Meldung Eins</title><link>https://example.org/1</link><description>A</description></item>
  <item><title>Meldung Zwei</title><link>https://example.org/2</link><description>B</description></item>
</channel></rss>
"""


def _configure_paths(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(briefing, "SYSTEM_SETTINGS_FILE", tmp_path / "system_settings.json")
    monkeypatch.setattr(briefing, "BRIEFING_DIR", tmp_path / "briefing")
    monkeypatch.setattr(briefing, "FEED_CACHE_DIR", tmp_path / "briefing" / "feeds")
    monkeypatch.setattr(briefing, "LATEST_BRIEFING_FILE", tmp_path / "briefing" / "latest.json")


def test_generate_daily_briefing_uses_mocked_fetcher(tmp_path: Path, monkeypatch):
    _configure_paths(tmp_path, monkeypatch)
    settings = {
        "rss_feeds": ["https://example.org/feed.xml"],
        "briefing_cron": "0 6 * * *",
    }
    (tmp_path / "system_settings.json").write_text(json.dumps(settings), encoding="utf-8")

    result = briefing.generate_daily_briefing(
        fetcher=lambda _url: RSS_XML,
        enable_external_apis=True,
        write_audit=False,
    )

    assert "Top-Themen heute" in result["summary"]
    assert len(result["links"]) == 2
    assert result["links"][0]["title"] == "Meldung Eins"


def test_generate_daily_briefing_reads_local_cache_when_external_disabled(tmp_path: Path, monkeypatch):
    _configure_paths(tmp_path, monkeypatch)
    feed_url = "https://example.org/feed.xml"
    settings = {
        "rss_feeds": [feed_url],
        "briefing_cron": "0 6 * * *",
    }
    (tmp_path / "system_settings.json").write_text(json.dumps(settings), encoding="utf-8")

    cache_file = briefing._feed_cache_file(feed_url)
    cache_file.parent.mkdir(parents=True, exist_ok=True)
    cache_file.write_text(RSS_XML, encoding="utf-8")

    result = briefing.generate_daily_briefing(
        fetcher=lambda _url: (_ for _ in ()).throw(RuntimeError("must not be used")),
        enable_external_apis=False,
        write_audit=False,
    )

    assert len(result["links"]) == 2
    assert result["sources"] == [feed_url]


def test_save_system_settings_persists_rss_feeds(tmp_path: Path, monkeypatch):
    from app import create_app
    from app.auth import hash_password
    from app.config import Config

    monkeypatch.setattr(Config, "USER_DATA_ROOT", tmp_path)
    monkeypatch.setattr(Config, "AUTH_DB", tmp_path / "auth.sqlite3")
    monkeypatch.setattr(Config, "CORE_DB", tmp_path / "core.sqlite3")
    monkeypatch.setattr(Config, "LICENSE_PATH", tmp_path / "license.json")
    monkeypatch.setattr(Config, "TRIAL_PATH", tmp_path / "trial.json")

    app = create_app()
    app.config["TESTING"] = True

    from app.routes import admin_tenants

    monkeypatch.setattr(admin_tenants, "SYSTEM_SETTINGS_FILE", tmp_path / "system_settings.json")

    with app.app_context():
        auth_db = app.extensions["auth_db"]
        auth_db.upsert_tenant("KUKANILEA", "KUKANILEA", "2026-01-01T00:00:00Z")
        auth_db.upsert_user("admin", hash_password("admin"), "2026-01-01T00:00:00Z")
        auth_db.upsert_membership("admin", "KUKANILEA", "ADMIN", "2026-01-01T00:00:00Z")

    client = app.test_client()
    with client.session_transaction() as sess:
        sess["user"] = "admin"
        sess["role"] = "ADMIN"
        sess["tenant_id"] = "KUKANILEA"

    response = client.post(
        "/admin/settings/system",
        data={
            "language": "de",
            "timezone": "Europe/Berlin",
            "backup_interval": "daily",
            "log_level": "INFO",
            "briefing_cron": "0 7 * * *",
            "rss_feeds": "https://example.org/one.xml\nhttps://example.org/two.xml",
            "confirm": "CONFIRM",
        },
    )

    assert response.status_code == 302
    payload = json.loads((tmp_path / "system_settings.json").read_text(encoding="utf-8"))
    assert payload["briefing_cron"] == "0 7 * * *"
    assert payload["rss_feeds"] == ["https://example.org/one.xml", "https://example.org/two.xml"]
