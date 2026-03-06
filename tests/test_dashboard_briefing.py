from __future__ import annotations

import json

from app.config import Config
from app.modules.dashboard.briefing import generate_daily_briefing, parse_feed_xml


def test_parse_feed_xml_rss_items() -> None:
    xml = """
    <rss><channel>
      <item><title>News A</title><link>https://example.org/a</link><pubDate>2026-03-06T08:00:00Z</pubDate></item>
      <item><title>News B</title><link>https://example.org/b</link></item>
    </channel></rss>
    """
    items = parse_feed_xml(xml)
    assert len(items) == 2
    assert items[0]["title"] == "News A"
    assert items[0]["link"] == "https://example.org/a"


def test_generate_daily_briefing_uses_local_cache_when_external_disabled(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(Config, "USER_DATA_ROOT", tmp_path)
    monkeypatch.setenv("ENABLE_EXTERNAL_APIS", "false")

    settings_file = tmp_path / "system_settings.json"
    settings_file.write_text(
        json.dumps({"briefing_rss_feeds": ["https://example.org/rss"]}),
        encoding="utf-8",
    )

    cache_dir = tmp_path / "briefing"
    cache_dir.mkdir(parents=True, exist_ok=True)
    (cache_dir / "feed_cache.json").write_text(
        json.dumps(
            {
                "feeds": {
                    "https://example.org/rss": [
                        {
                            "title": "Lokale Meldung",
                            "link": "https://example.org/local",
                            "published": "2026-03-06T07:30:00Z",
                            "summary": "",
                        }
                    ]
                }
            }
        ),
        encoding="utf-8",
    )

    def _fetcher(_: str) -> str:
        raise AssertionError("fetcher should not be called")

    briefing = generate_daily_briefing(fetcher=_fetcher, audit=False)
    assert briefing["external_fetch_enabled"] is False
    assert briefing["links"][0]["title"] == "Lokale Meldung"


def test_generate_daily_briefing_with_mocked_feed_fetch(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(Config, "USER_DATA_ROOT", tmp_path)
    monkeypatch.setenv("ENABLE_EXTERNAL_APIS", "true")

    (tmp_path / "system_settings.json").write_text(
        json.dumps({"briefing_rss_feeds": ["https://example.org/rss"]}),
        encoding="utf-8",
    )

    xml = """
    <rss><channel>
      <item><title>Remote Update</title><link>https://example.org/remote</link><pubDate>2026-03-06T09:00:00Z</pubDate></item>
    </channel></rss>
    """

    briefing = generate_daily_briefing(fetcher=lambda _url: xml, audit=False)
    assert briefing["external_fetch_enabled"] is True
    assert briefing["links"][0]["title"] == "Remote Update"

    cache_payload = json.loads((tmp_path / "briefing" / "feed_cache.json").read_text(encoding="utf-8"))
    assert "https://example.org/rss" in cache_payload["feeds"]
