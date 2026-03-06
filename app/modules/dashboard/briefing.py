from __future__ import annotations

import hashlib
import json
import logging
import os
import threading
import time
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from urllib.request import Request, urlopen
from xml.etree import ElementTree

from app.config import Config
from app.core.logic import audit_log
from app.modules.automation.cron import cron_match, cron_minute_ref

logger = logging.getLogger("kukanilea.dashboard.briefing")

SYSTEM_SETTINGS_FILE = Config.USER_DATA_ROOT / "system_settings.json"
BRIEFING_DIR = Config.USER_DATA_ROOT / "briefing"
FEED_CACHE_DIR = BRIEFING_DIR / "feeds"
LATEST_BRIEFING_FILE = BRIEFING_DIR / "latest.json"
DEFAULT_CRON = "0 6 * * *"
MAX_ITEMS = 24

_SCHEDULER_LOCK = threading.Lock()
_SCHEDULER_THREAD: threading.Thread | None = None
_SCHEDULER_STOP = threading.Event()


def _read_json(path: Path, default: dict[str, Any]) -> dict[str, Any]:
    if not path.exists():
        return dict(default)
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return dict(default)
    if not isinstance(data, dict):
        return dict(default)
    out = dict(default)
    out.update(data)
    return out


def load_briefing_settings() -> dict[str, Any]:
    settings = _read_json(
        SYSTEM_SETTINGS_FILE,
        {
            "rss_feeds": [],
            "briefing_cron": DEFAULT_CRON,
        },
    )
    settings["rss_feeds"] = normalize_rss_feeds(settings.get("rss_feeds"))
    settings["briefing_cron"] = str(settings.get("briefing_cron") or DEFAULT_CRON).strip() or DEFAULT_CRON
    return settings


def normalize_rss_feeds(raw: Any) -> list[str]:
    if isinstance(raw, str):
        candidates = [line.strip() for line in raw.replace(",", "\n").splitlines()]
    elif isinstance(raw, list):
        candidates = [str(item).strip() for item in raw]
    else:
        candidates = []

    seen: set[str] = set()
    out: list[str] = []
    for entry in candidates:
        if not entry:
            continue
        normalized = entry.strip()
        if normalized in seen:
            continue
        seen.add(normalized)
        out.append(normalized)
    return out


def _feed_cache_file(url: str) -> Path:
    digest = hashlib.sha256(url.encode("utf-8")).hexdigest()[:16]
    FEED_CACHE_DIR.mkdir(parents=True, exist_ok=True)
    return FEED_CACHE_DIR / f"{digest}.xml"


def _fetch_feed_xml(url: str, timeout_s: int = 8) -> str:
    request = Request(
        url,
        headers={
            "User-Agent": "KUKANILEA-Briefing/1.0",
            "Accept": "application/rss+xml, application/atom+xml, application/xml, text/xml;q=0.9, */*;q=0.1",
        },
    )
    with urlopen(request, timeout=timeout_s) as resp:  # nosec B310 - only optional feed URLs configured locally
        payload = resp.read()
    return payload.decode("utf-8", errors="replace")


def _xml_text(node: ElementTree.Element | None, xpath: str) -> str:
    if node is None:
        return ""
    value = node.findtext(xpath)
    return str(value or "").strip()


def _extract_items_from_xml(xml: str, source: str) -> list[dict[str, str]]:
    try:
        root = ElementTree.fromstring(xml)
    except ElementTree.ParseError:
        return []

    items: list[dict[str, str]] = []
    if root.tag.lower().endswith("rss"):
        channel = root.find("channel")
        for item in channel.findall("item") if channel is not None else []:
            title = _xml_text(item, "title")
            link = _xml_text(item, "link")
            summary = _xml_text(item, "description")
            if title and link:
                items.append({"title": title, "link": link, "summary": summary, "source": source})
        return items

    # Atom fallback
    atom_ns = "{http://www.w3.org/2005/Atom}"
    for entry in root.findall(f"{atom_ns}entry"):
        title = _xml_text(entry, f"{atom_ns}title")
        summary = _xml_text(entry, f"{atom_ns}summary") or _xml_text(entry, f"{atom_ns}content")
        link = ""
        for link_node in entry.findall(f"{atom_ns}link"):
            href = str(link_node.attrib.get("href") or "").strip()
            rel = str(link_node.attrib.get("rel") or "alternate").strip().lower()
            if href and rel in {"", "alternate"}:
                link = href
                break
        if title and link:
            items.append({"title": title, "link": link, "summary": summary, "source": source})
    return items


def _build_summary(items: list[dict[str, str]]) -> str:
    if not items:
        return "Keine lokalen Feed-Einträge verfügbar."
    top_titles = [str(item.get("title") or "").strip() for item in items[:5] if str(item.get("title") or "").strip()]
    if not top_titles:
        return "Neue Feed-Einträge wurden geladen, aber ohne verwertbare Titel."
    return "Top-Themen heute: " + "; ".join(top_titles)


def latest_briefing() -> dict[str, Any]:
    return _read_json(
        LATEST_BRIEFING_FILE,
        {
            "generated_at": "",
            "summary": "Noch kein Briefing erstellt.",
            "links": [],
            "sources": [],
        },
    )


def generate_daily_briefing(
    *,
    fetcher: Callable[[str], str] | None = None,
    enable_external_apis: bool | None = None,
    now: datetime | None = None,
    write_audit: bool = True,
) -> dict[str, Any]:
    settings = load_briefing_settings()
    feeds = settings.get("rss_feeds") or []
    fetch = fetcher or _fetch_feed_xml
    allow_external = (
        bool(enable_external_apis)
        if enable_external_apis is not None
        else str(os.environ.get("ENABLE_EXTERNAL_APIS", "false")).strip().lower() == "true"
    )

    all_items: list[dict[str, str]] = []
    loaded_sources: list[str] = []

    FEED_CACHE_DIR.mkdir(parents=True, exist_ok=True)
    BRIEFING_DIR.mkdir(parents=True, exist_ok=True)

    for feed_url in feeds:
        xml_payload = ""
        cache_file = _feed_cache_file(feed_url)
        if allow_external:
            try:
                xml_payload = fetch(feed_url)
                cache_file.write_text(xml_payload, encoding="utf-8")
            except Exception:
                logger.warning("Briefing feed fetch failed for %s", feed_url, exc_info=True)
        if not xml_payload and cache_file.exists():
            xml_payload = cache_file.read_text(encoding="utf-8", errors="ignore")
        if not xml_payload:
            continue
        items = _extract_items_from_xml(xml_payload, source=feed_url)
        if not items:
            continue
        loaded_sources.append(feed_url)
        all_items.extend(items)

    # de-duplicate links while keeping order
    deduped: list[dict[str, str]] = []
    seen_links: set[str] = set()
    for item in all_items:
        link = str(item.get("link") or "").strip()
        if not link or link in seen_links:
            continue
        seen_links.add(link)
        deduped.append(item)

    trimmed = deduped[:MAX_ITEMS]
    now_utc = (now or datetime.now(UTC)).replace(microsecond=0).isoformat().replace("+00:00", "Z")
    briefing = {
        "generated_at": now_utc,
        "summary": _build_summary(trimmed),
        "links": [
            {
                "title": str(item.get("title") or "").strip(),
                "url": str(item.get("link") or "").strip(),
                "source": str(item.get("source") or "").strip(),
            }
            for item in trimmed
        ],
        "sources": loaded_sources,
    }
    LATEST_BRIEFING_FILE.write_text(json.dumps(briefing, indent=2, ensure_ascii=False), encoding="utf-8")

    if write_audit:
        try:
            audit_log(
                user="system",
                role="SYSTEM",
                action="briefing.generated",
                meta={"sources": loaded_sources, "count": len(trimmed)},
                tenant_id="SYSTEM",
            )
        except Exception:
            logger.warning("Could not write briefing audit event", exc_info=True)
    return briefing


def _scheduler_loop(*, sleep_s: int = 30) -> None:
    last_ref = ""
    while not _SCHEDULER_STOP.is_set():
        settings = load_briefing_settings()
        expression = str(settings.get("briefing_cron") or DEFAULT_CRON).strip() or DEFAULT_CRON
        now = datetime.now(UTC)
        try:
            if cron_match(expression, now):
                minute_ref = cron_minute_ref(now)
                if minute_ref != last_ref:
                    generate_daily_briefing()
                    last_ref = minute_ref
        except ValueError:
            logger.warning("Invalid briefing cron expression: %s", expression)
        _SCHEDULER_STOP.wait(timeout=max(5, int(sleep_s)))


def start_briefing_scheduler() -> None:
    global _SCHEDULER_THREAD
    with _SCHEDULER_LOCK:
        if _SCHEDULER_THREAD and _SCHEDULER_THREAD.is_alive():
            return
        _SCHEDULER_STOP.clear()
        _SCHEDULER_THREAD = threading.Thread(
            target=_scheduler_loop,
            name="briefing-scheduler",
            daemon=True,
        )
        _SCHEDULER_THREAD.start()


def stop_briefing_scheduler() -> None:
    _SCHEDULER_STOP.set()
