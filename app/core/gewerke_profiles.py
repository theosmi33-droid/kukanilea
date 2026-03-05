from __future__ import annotations

import json
import os
from copy import deepcopy
from functools import lru_cache
from pathlib import Path
from typing import Any, Dict

DEFAULT_PROFILE_ID = "allgemein"

_DEFAULT_PROFILE: Dict[str, Any] = {
    "profile_id": DEFAULT_PROFILE_ID,
    "gewerk_name": "All-Gewerke",
    "document_types": [
        "ANGEBOT",
        "RECHNUNG",
        "AUFTRAGSBESTAETIGUNG",
        "LIEFERSCHEIN",
        "MAHNUNG",
        "NACHTRAG",
        "SONSTIGES",
    ],
    "required_fields": [
        "tenant",
        "kdnr",
        "name",
        "addr",
        "plzort",
        "doctype",
        "document_date",
    ],
    "task_templates": [
        "Dokumentenprüfung abschließen",
        "Rückfrage an Kunden vorbereiten",
        "Folgetermin planen",
    ],
    "time_export_rules": {
        "rounding_minutes": 15,
        "decimal_places": 2,
        "include_approval_fields": True,
    },
}


def _normalize_profile(raw: Dict[str, Any]) -> Dict[str, Any]:
    profile_id = str(raw.get("profile_id") or "").strip().lower() or DEFAULT_PROFILE_ID
    base = deepcopy(_DEFAULT_PROFILE)
    base.update(raw)
    base["profile_id"] = profile_id
    base["gewerk_name"] = str(base.get("gewerk_name") or profile_id).strip() or profile_id

    def _to_unique_list(key: str) -> list[str]:
        values = base.get(key)
        if not isinstance(values, list):
            return list(_DEFAULT_PROFILE[key])
        seen: set[str] = set()
        normalized: list[str] = []
        for item in values:
            entry = str(item or "").strip()
            if not entry:
                continue
            dedupe = entry.upper() if key == "document_types" else entry
            if dedupe in seen:
                continue
            seen.add(dedupe)
            normalized.append(entry.upper() if key == "document_types" else entry)
        if normalized:
            return normalized
        return list(_DEFAULT_PROFILE[key])

    base["document_types"] = _to_unique_list("document_types")
    base["required_fields"] = _to_unique_list("required_fields")
    base["task_templates"] = _to_unique_list("task_templates")

    time_rules = base.get("time_export_rules")
    if not isinstance(time_rules, dict):
        time_rules = {}
    merged_rules = dict(_DEFAULT_PROFILE["time_export_rules"])
    merged_rules.update(time_rules)
    merged_rules["rounding_minutes"] = max(1, int(merged_rules.get("rounding_minutes") or 1))
    merged_rules["decimal_places"] = max(0, min(4, int(merged_rules.get("decimal_places") or 2)))
    merged_rules["include_approval_fields"] = bool(merged_rules.get("include_approval_fields", True))
    base["time_export_rules"] = merged_rules
    return base


def _load_raw_profiles() -> Dict[str, Dict[str, Any]]:
    raw_json = os.environ.get("KUKANILEA_GEWERK_PROFILES_JSON", "").strip()
    if not raw_json:
        path = os.environ.get("KUKANILEA_GEWERK_PROFILES_PATH", "").strip()
        if path:
            try:
                raw_json = Path(path).read_text(encoding="utf-8")
            except OSError:
                raw_json = ""
    if not raw_json:
        return {}
    try:
        parsed = json.loads(raw_json)
    except json.JSONDecodeError:
        return {}
    if isinstance(parsed, dict):
        raw_profiles = parsed.get("profiles") if "profiles" in parsed else parsed
        if isinstance(raw_profiles, dict):
            return {str(k).strip().lower(): v for k, v in raw_profiles.items() if isinstance(v, dict)}
    if isinstance(parsed, list):
        loaded: Dict[str, Dict[str, Any]] = {}
        for item in parsed:
            if not isinstance(item, dict):
                continue
            item_id = str(item.get("profile_id") or "").strip().lower()
            if item_id:
                loaded[item_id] = item
        return loaded
    return {}


@lru_cache(maxsize=1)
def get_profiles_catalog() -> Dict[str, Dict[str, Any]]:
    catalog: Dict[str, Dict[str, Any]] = {DEFAULT_PROFILE_ID: _normalize_profile(_DEFAULT_PROFILE)}
    for key, raw in _load_raw_profiles().items():
        payload = dict(raw)
        payload.setdefault("profile_id", key)
        catalog[key] = _normalize_profile(payload)
    return catalog


def reset_profiles_cache() -> None:
    get_profiles_catalog.cache_clear()


def resolve_profile_id(*, tenant_id: str | None = None) -> str:
    requested = os.environ.get("KUKANILEA_GEWERK_PROFILE_ID", "").strip().lower()
    if tenant_id:
        mapping_raw = os.environ.get("KUKANILEA_TENANT_PROFILE_MAP", "").strip()
        if mapping_raw:
            try:
                mapping = json.loads(mapping_raw)
            except json.JSONDecodeError:
                mapping = {}
            if isinstance(mapping, dict):
                tenant_key = str(tenant_id).strip().lower()
                mapped = str(mapping.get(tenant_key) or "").strip().lower()
                if mapped:
                    requested = mapped
    if requested and requested in get_profiles_catalog():
        return requested
    return DEFAULT_PROFILE_ID


def get_active_profile(*, tenant_id: str | None = None, profile_id: str | None = None) -> Dict[str, Any]:
    catalog = get_profiles_catalog()
    selected = str(profile_id or "").strip().lower() or resolve_profile_id(tenant_id=tenant_id)
    return deepcopy(catalog.get(selected, catalog[DEFAULT_PROFILE_ID]))
