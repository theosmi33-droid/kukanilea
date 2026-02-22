from __future__ import annotations

import re
from datetime import UTC, datetime
from email import policy
from email.parser import BytesParser
from email.utils import parsedate_to_datetime
from pathlib import Path
from typing import Any

from .base import Adapter

MAX_BODY_CHARS = 20_000

TAG_RE = re.compile(r"<[^>]+>")
SCRIPT_STYLE_RE = re.compile(r"<(script|style)\b.*?</\1>", re.IGNORECASE | re.DOTALL)
WS_RE = re.compile(r"\s+")


def _now_iso() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds")


def _to_utc_iso(raw_value: str) -> str:
    text = str(raw_value or "").strip()
    if not text:
        return _now_iso()
    try:
        parsed = parsedate_to_datetime(text)
        if parsed is None:
            return _now_iso()
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=UTC)
        return parsed.astimezone(UTC).isoformat(timespec="seconds")
    except Exception:
        return _now_iso()


def _html_to_text(value: str) -> str:
    text = SCRIPT_STYLE_RE.sub(" ", value or "")
    text = TAG_RE.sub(" ", text)
    return WS_RE.sub(" ", text).strip()


def _extract_body(msg) -> tuple[str, bool, bool]:
    body_parts: list[str] = []
    html_parts: list[str] = []
    if msg.is_multipart():
        for part in msg.walk():
            ctype = (part.get_content_type() or "").lower()
            disp = (part.get_content_disposition() or "").lower()
            if disp == "attachment" or part.get_filename():
                continue
            try:
                text = part.get_content()
            except Exception:
                payload = part.get_payload(decode=True) or b""
                text = payload.decode(
                    part.get_content_charset() or "utf-8", errors="replace"
                )
            if not isinstance(text, str):
                continue
            if ctype == "text/plain" and text.strip():
                body_parts.append(text)
            elif ctype == "text/html" and text.strip():
                html_parts.append(text)
    else:
        ctype = (msg.get_content_type() or "").lower()
        try:
            text = msg.get_content()
        except Exception:
            payload = msg.get_payload(decode=True) or b""
            text = payload.decode(
                msg.get_content_charset() or "utf-8", errors="replace"
            )
        if isinstance(text, str) and text.strip():
            if ctype == "text/plain":
                body_parts.append(text)
            elif ctype == "text/html":
                html_parts.append(text)

    used_html_fallback = False
    if body_parts:
        body = "\n".join(body_parts)
    elif html_parts:
        body = _html_to_text("\n".join(html_parts))
        used_html_fallback = True
    else:
        body = ""
    body = body.replace("\x00", " ").strip()
    truncated = len(body) > MAX_BODY_CHARS
    if truncated:
        body = body[:MAX_BODY_CHARS]
    return body, truncated, used_html_fallback


class EmailSimAdapter(Adapter):
    @staticmethod
    def ingest(tenant_id: str, fixture_path: Path) -> list[dict[str, Any]]:
        _ = str(tenant_id or "").strip() or "default"
        path = Path(str(fixture_path))
        raw = path.read_bytes()
        msg = BytesParser(policy=policy.default).parsebytes(raw)
        body_text, body_truncated, used_html_fallback = _extract_body(msg)
        draft = {
            "channel": "email",
            "channel_ref": str(msg.get("message-id") or "").strip() or None,
            "direction": "inbound",
            "occurred_at": _to_utc_iso(str(msg.get("date") or "")),
            "raw_payload": {
                "message_id": str(msg.get("message-id") or "").strip() or None,
                "from": str(msg.get("from") or ""),
                "to": str(msg.get("to") or ""),
                "subject": str(msg.get("subject") or ""),
                "body": body_text,
                "body_truncated": bool(body_truncated),
                "used_html_fallback": bool(used_html_fallback),
            },
        }
        return [draft]


def ingest(tenant_id: str, fixture_path: Path) -> list[dict[str, Any]]:
    return EmailSimAdapter.ingest(tenant_id, fixture_path)
