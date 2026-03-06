from __future__ import annotations

import json
import os
import threading
import urllib.request
import xml.etree.ElementTree as ET
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Callable

from flask import current_app, has_app_context

from app.config import Config
from app.modules.automation.cron import cron_match

FetchFn = Callable[[str], str]

_DEFAULT_CRON = "0 7 * * *"
_BRIEFING_LOCK = threading.Lock()
_BRIEFING_SCHEDULER: "BriefingScheduler | None" = None


def _now_utc() -> datetime:
    return datetime.now(UTC)


def _settings_path() -> Path:
    return Config.USER_DATA_ROOT / "system_settings.json"


def _briefing_dir() -> Path:
    if has_app_context():
        return Path(current_app.config.get("USER_DATA_ROOT", Config.USER_DATA_ROOT)) / "briefing"
    return Config.USER_DATA_ROOT / "briefing"


def _feed_cache_path() -> Path:
    return _briefing_dir() / "feed_cache.json"


def _latest_briefing_path() -> Path:
    return _briefing_dir() / "latest.json"


def _read_json(path: Path, default: dict[str, Any]) -> dict[str, Any]:
    if not path.exists():
        return dict(default)
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
        if isinstance(raw, dict):
            merged = dict(default)
            merged.update(raw)
            return merged
    except Exception:
        pass
    return dict(default)


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")


def _external_enabled() -> bool:
    return str(os.getenv("ENABLE_EXTERNAL_APIS", "false")).strip().lower() in {"1", "true", "yes", "on"}


def load_briefing_settings() -> dict[str, Any]:
    defaults = {
        "briefing_rss_feeds": [],
        "briefing_cron": _DEFAULT_CRON,
    }
    settings = _read_json(_settings_path(), defaults)
    feeds = settings.get("briefing_rss_feeds")
    if isinstance(feeds, str):
        feeds = [line.strip() for line in feeds.splitlines() if line.strip()]
    if not isinstance(feeds, list):
        feeds = []
    settings["briefing_rss_feeds"] = [str(v).strip() for v in feeds if str(v).strip()]
    settings["briefing_cron"] = str(settings.get("briefing_cron") or _DEFAULT_CRON).strip() or _DEFAULT_CRON
    return settings


def save_briefing_settings(*, feeds: list[str], cron_expression: str) -> dict[str, Any]:
    settings = _read_json(_settings_path(), {})
    settings["briefing_rss_feeds"] = [str(v).strip() for v in feeds if str(v).strip()]
    settings["briefing_cron"] = str(cron_expression or _DEFAULT_CRON).strip() or _DEFAULT_CRON
    _write_json(_settings_path(), settings)
    return settings


def _default_fetch(url: str) -> str:
    with urllib.request.urlopen(url, timeout=8) as res:  # nosec B310
        return res.read().decode("utf-8", errors="replace")


def _strip(tag: str) -> str:
    if "}" in tag:
        return tag.rsplit("}", 1)[1]
    return tag


def _item_dict(node: ET.Element) -> dict[str, str]:
    out: dict[str, str] = {"title": "", "link": "", "published": "", "summary": ""}
    for child in list(node):
        key = _strip(child.tag).lower()
        text = (child.text or "").strip()
        if key == "link" and not text:
            text = str(child.attrib.get("href") or "").strip()
        if key in {"title", "link", "published", "updated", "pubdate", "summary", "description"}:
            if key in {"published", "updated", "pubdate"}:
                out["published"] = out["published"] or text
            elif key in {"summary", "description"}:
                out["summary"] = out["summary"] or text
            else:
                out[key] = out[key] or text
    return out


def parse_feed_xml(xml_text: str, *, max_items: int = 12) -> list[dict[str, str]]:
    if not xml_text.strip():
        return []
    try:
        root = ET.fromstring(xml_text)
    except ET.ParseError:
        return []

    candidates: list[ET.Element] = []
    root_name = _strip(root.tag).lower()
    if root_name == "rss":
        channel = next((node for node in list(root) if _strip(node.tag).lower() == "channel"), None)
        if channel is not None:
            candidates = [n for n in list(channel) if _strip(n.tag).lower() == "item"]
    elif root_name == "feed":
        candidates = [n for n in list(root) if _strip(n.tag).lower() == "entry"]
    if not candidates:
        candidates = [n for n in root.iter() if _strip(n.tag).lower() in {"item", "entry"}]

    out: list[dict[str, str]] = []
    for node in candidates[: max(1, max_items)]:
        item = _item_dict(node)
        if item.get("title") or item.get("summary"):
            out.append(item)
    return out


def load_feed_cache() -> dict[str, list[dict[str, str]]]:
    payload = _read_json(_feed_cache_path(), {"feeds": {}})
    feeds = payload.get("feeds")
    if not isinstance(feeds, dict):
        return {}
    normalized: dict[str, list[dict[str, str]]] = {}
    for url, entries in feeds.items():
        if not isinstance(entries, list):
            continue
        normalized[str(url)] = [
            {
                "title": str(item.get("title") or ""),
                "link": str(item.get("link") or ""),
                "published": str(item.get("published") or ""),
                "summary": str(item.get("summary") or ""),
            }
            for item in entries
            if isinstance(item, dict)
        ]
    return normalized


def refresh_feed_cache(
    *,
    feed_urls: list[str],
    fetcher: FetchFn | None = None,
) -> dict[str, list[dict[str, str]]]:
    cache = load_feed_cache()
    if not _external_enabled():
        return cache

    fetch = fetcher or _default_fetch
    updated = dict(cache)
    for url in feed_urls:
        source = str(url or "").strip()
        if not source:
            continue
        try:
            xml_text = fetch(source)
            updated[source] = parse_feed_xml(xml_text)
        except Exception:
            continue
    _write_json(
        _feed_cache_path(),
        {
            "updated_at": _now_utc().replace(microsecond=0).isoformat().replace("+00:00", "Z"),
            "feeds": updated,
        },
    )
    return updated


def _sorted_entries(entries: list[dict[str, str]]) -> list[dict[str, str]]:
    return sorted(entries, key=lambda row: str(row.get("published") or ""), reverse=True)


def generate_daily_briefing(
    *,
    fetcher: FetchFn | None = None,
    max_links: int = 8,
    tenant_id: str = "SYSTEM",
    audit: bool = True,
) -> dict[str, Any]:
    settings = load_briefing_settings()
    feed_urls = settings.get("briefing_rss_feeds") or []
    cache = refresh_feed_cache(feed_urls=feed_urls, fetcher=fetcher)

    merged: list[dict[str, str]] = []
    for url in feed_urls:
        merged.extend(cache.get(str(url), []))
    merged = _sorted_entries(merged)

    links: list[dict[str, str]] = []
    for item in merged:
        if len(links) >= max(1, max_links):
            break
        title = str(item.get("title") or item.get("summary") or "Update").strip()
        link = str(item.get("link") or "").strip()
        published = str(item.get("published") or "").strip()
        if not title:
            continue
        links.append({"title": title, "url": link, "published": published})

    if links:
        summary = " · ".join([row["title"] for row in links[:3]])
    elif feed_urls:
        summary = "Keine neuen Feed-Updates gefunden."
    else:
        summary = "Keine RSS-Feeds konfiguriert."

    payload = {
        "generated_at": _now_utc().replace(microsecond=0).isoformat().replace("+00:00", "Z"),
        "summary": summary,
        "links": links,
        "feed_count": len(feed_urls),
        "external_fetch_enabled": _external_enabled(),
    }
    _write_json(_latest_briefing_path(), payload)

    if audit:
        try:
            from app.core.logic import audit_log

            audit_log(
                user="system",
                role="SYSTEM",
                action="briefing.generated",
                target="dashboard",
                meta={"link_count": len(links), "feed_count": len(feed_urls)},
                tenant_id=tenant_id or "SYSTEM",
            )
        except Exception:
            pass

    return payload


def get_latest_briefing() -> dict[str, Any]:
    return _read_json(
        _latest_briefing_path(),
        {
            "generated_at": "",
            "summary": "Noch kein Daily Briefing generiert.",
            "links": [],
            "feed_count": 0,
            "external_fetch_enabled": _external_enabled(),
        },
    )


class BriefingScheduler:
    def __init__(self, *, sleep_seconds: int = 60):
        self.sleep_seconds = max(15, int(sleep_seconds))
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None
        self._last_run_key = ""

    def start(self) -> None:
        if self._thread and self._thread.is_alive():
            return
        self._stop.clear()
        self._thread = threading.Thread(target=self._run, name="briefing-scheduler", daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()
        if self._thread:
            self._thread.join(timeout=2)

    def _run(self) -> None:
        while not self._stop.is_set():
            now = _now_utc()
            settings = load_briefing_settings()
            expr = str(settings.get("briefing_cron") or _DEFAULT_CRON)
            run_key = now.strftime("%Y-%m-%dT%H:%M")
            try:
                matched = cron_match(expr, now)
            except ValueError:
                matched = False
            if matched and run_key != self._last_run_key:
                self._last_run_key = run_key
                try:
                    generate_daily_briefing(audit=True)
                except Exception:
                    pass
            self._stop.wait(self.sleep_seconds)


def start_briefing_scheduler() -> None:
    global _BRIEFING_SCHEDULER
    with _BRIEFING_LOCK:
        if _BRIEFING_SCHEDULER is None:
            _BRIEFING_SCHEDULER = BriefingScheduler()
        _BRIEFING_SCHEDULER.start()


def stop_briefing_scheduler() -> None:
    global _BRIEFING_SCHEDULER
    with _BRIEFING_LOCK:
        if _BRIEFING_SCHEDULER is not None:
            _BRIEFING_SCHEDULER.stop()
            _BRIEFING_SCHEDULER = None
