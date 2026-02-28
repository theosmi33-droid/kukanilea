from __future__ import annotations

import ipaddress
import re
import time
import urllib.error
import urllib.parse
import urllib.request
from collections.abc import Mapping
from http import HTTPStatus
from typing import Any

from app.config import Config

WEBHOOK_TIMEOUT_SECONDS = 10
WEBHOOK_RETRY_SECONDS = 5
WEBHOOK_MAX_ATTEMPTS = 2
WEBHOOK_ALLOWED_PLACEHOLDERS = {
    "event_type",
    "entity_type",
    "entity_id",
    "trigger_ref",
    "tenant_id",
    "thread_id",
    "account_id",
    "source",
}
_TEMPLATE_VAR_PATTERN = re.compile(r"\{([a-zA-Z0-9_]+)\}")
_TEMPLATE_VAR_DOUBLE_PATTERN = re.compile(r"\{\{\s*([a-zA-Z0-9_]+)\s*\}\}")


def _extract_template_vars(template: str) -> set[str]:
    text = str(template or "")
    names = set(_TEMPLATE_VAR_PATTERN.findall(text))
    names.update(_TEMPLATE_VAR_DOUBLE_PATTERN.findall(text))
    return {str(name or "").strip() for name in names if str(name or "").strip()}


def _validate_template_vars(template: str) -> bool:
    names = _extract_template_vars(template)
    return names.issubset(WEBHOOK_ALLOWED_PLACEHOLDERS)


def _render_template_text(template: str, context: Mapping[str, Any]) -> str:
    rendered = str(template or "")
    for key in WEBHOOK_ALLOWED_PLACEHOLDERS:
        value = str(context.get(key) or "")
        rendered = rendered.replace("{{" + key + "}}", value)
        rendered = rendered.replace("{ " + key + " }", value)
        rendered = rendered.replace("{" + key + "}", value)
    return rendered


def _allowed_domains() -> set[str]:
    configured = getattr(Config, "WEBHOOK_ALLOWED_DOMAINS_LIST", None)
    if isinstance(configured, list):
        return {str(v).strip().lower() for v in configured if str(v).strip()}
    raw = str(getattr(Config, "WEBHOOK_ALLOWED_DOMAINS", "") or "")
    return {part.strip().lower() for part in raw.split(",") if part.strip()}


def _validate_webhook_url(url: str) -> tuple[str, str] | None:
    parsed = urllib.parse.urlparse(str(url or "").strip())
    if parsed.scheme.lower() != "https":
        return None
    if parsed.username or parsed.password:
        return None
    host = str(parsed.hostname or "").strip().lower()
    if not host:
        return None
    if host in {"localhost", "127.0.0.1", "::1"}:
        return None
    try:
        ipaddress.ip_address(host)
        return None
    except ValueError:
        pass
    allowed = _allowed_domains()
    if not allowed or host not in allowed:
        return None
    safe_url = urllib.parse.urlunparse(
        (parsed.scheme, parsed.netloc, parsed.path or "/", "", "", "")
    )
    return safe_url, host


def execute_webhook_action(
    *,
    action_cfg: Mapping[str, Any],
    context: Mapping[str, Any],
) -> dict[str, Any]:
    method = str(action_cfg.get("method") or "POST").strip().upper()
    if method != "POST":
        return {"status": "failed", "error": "method_not_allowed"}
    validated = _validate_webhook_url(str(action_cfg.get("url") or ""))
    if validated is None:
        return {"status": "failed", "error": "domain_not_allowed"}
    target_url, target_host = validated

    body_template = str(action_cfg.get("body_template") or "{}")
    if not _validate_template_vars(body_template):
        return {"status": "failed", "error": "template_variables_not_allowed"}
    body_text = _render_template_text(body_template, context)
    if len(body_text) > 20000:
        return {"status": "failed", "error": "payload_too_large"}

    headers_cfg = action_cfg.get("headers") or {}
    headers: dict[str, str] = {"Content-Type": "application/json"}
    if isinstance(headers_cfg, Mapping):
        for key, value in headers_cfg.items():
            name = str(key or "").strip()
            if not name:
                continue
            lowered = name.lower()
            if (
                "auth" in lowered
                or "token" in lowered
                or lowered in {"cookie", "set-cookie"}
            ):
                return {"status": "failed", "error": "header_not_allowed"}
            headers[name] = str(value or "")[:300]

    data = body_text.encode("utf-8")
    last_error = "webhook_failed"
    for attempt in range(WEBHOOK_MAX_ATTEMPTS):
        req = urllib.request.Request(
            target_url, data=data, headers=headers, method="POST"
        )
        try:
            with urllib.request.urlopen(req, timeout=WEBHOOK_TIMEOUT_SECONDS) as resp:
                status_code = int(getattr(resp, "status", 0) or 0)
            if HTTPStatus.OK <= status_code < HTTPStatus.MULTIPLE_CHOICES:
                return {
                    "status": "ok",
                    "result": {"status_code": status_code, "host": target_host},
                }
            if (
                status_code in {HTTPStatus.TOO_MANY_REQUESTS}
                or status_code >= HTTPStatus.INTERNAL_SERVER_ERROR
            ):
                last_error = f"webhook_transient_http_{status_code}"
                if attempt + 1 < WEBHOOK_MAX_ATTEMPTS:
                    time.sleep(WEBHOOK_RETRY_SECONDS)
                    continue
                return {"status": "failed", "error": last_error}
            return {"status": "failed", "error": f"webhook_http_{status_code}"}
        except urllib.error.HTTPError as exc:
            status_code = int(getattr(exc, "code", 0) or 0)
            if (
                status_code in {HTTPStatus.TOO_MANY_REQUESTS}
                or status_code >= HTTPStatus.INTERNAL_SERVER_ERROR
            ):
                last_error = f"webhook_transient_http_{status_code}"
                if attempt + 1 < WEBHOOK_MAX_ATTEMPTS:
                    time.sleep(WEBHOOK_RETRY_SECONDS)
                    continue
                return {"status": "failed", "error": last_error}
            return {"status": "failed", "error": f"webhook_http_{status_code}"}
        except (urllib.error.URLError, TimeoutError):
            last_error = "webhook_transient_network_error"
            if attempt + 1 < WEBHOOK_MAX_ATTEMPTS:
                time.sleep(WEBHOOK_RETRY_SECONDS)
                continue
            return {"status": "failed", "error": last_error}
    return {"status": "failed", "error": last_error}
