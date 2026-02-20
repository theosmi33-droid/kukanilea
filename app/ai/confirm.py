from __future__ import annotations

import base64
import hashlib
import hmac
import json
import sqlite3
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from flask import current_app, has_app_context

from app.config import Config


def _db_path() -> Path:
    if has_app_context():
        return Path(current_app.config["CORE_DB"])
    return Path(Config.CORE_DB)


def _connect() -> sqlite3.Connection:
    db_path = _db_path()
    db_path.parent.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(str(db_path), timeout=30)
    con.row_factory = sqlite3.Row
    con.execute("PRAGMA foreign_keys=ON;")
    return con


def _secret() -> str:
    if has_app_context():
        return str(current_app.config.get("SECRET_KEY") or "")
    return str(Config.SECRET_KEY or "")


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _iso(dt: datetime) -> str:
    return dt.astimezone(timezone.utc).replace(microsecond=0).isoformat()


def _b64url(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).decode("ascii").rstrip("=")


def _b64url_decode(token: str) -> bytes:
    data = str(token or "")
    pad = "=" * ((4 - len(data) % 4) % 4)
    return base64.urlsafe_b64decode((data + pad).encode("ascii"))


def _sign(payload_json: str) -> str:
    key = _secret().encode("utf-8")
    msg = payload_json.encode("utf-8")
    return hmac.new(key, msg, hashlib.sha256).hexdigest()


def ensure_confirm_schema() -> None:
    con = _connect()
    try:
        con.execute(
            """
            CREATE TABLE IF NOT EXISTS ai_tool_confirmations (
              nonce TEXT PRIMARY KEY,
              tenant_id TEXT NOT NULL,
              user_id TEXT NOT NULL,
              tool_name TEXT NOT NULL,
              expires_at TEXT NOT NULL,
              consumed_at TEXT,
              created_at TEXT NOT NULL
            )
            """
        )
        con.execute(
            "CREATE INDEX IF NOT EXISTS idx_ai_tool_confirms_tenant_user ON ai_tool_confirmations(tenant_id, user_id, created_at DESC)"
        )
        con.commit()
    finally:
        con.close()


def sign_confirmation(
    *,
    tenant_id: str,
    user_id: str,
    tool_name: str,
    args: dict[str, Any],
    ttl_seconds: int = 300,
) -> str:
    ensure_confirm_schema()
    now = _now()
    ttl = max(30, min(int(ttl_seconds or 300), 3600))
    nonce = str(uuid.uuid4())
    payload: dict[str, Any] = {
        "nonce": nonce,
        "tenant_id": str(tenant_id or ""),
        "user_id": str(user_id or "system"),
        "tool_name": str(tool_name or ""),
        "args": args or {},
        "iat": _iso(now),
        "exp": _iso(now + timedelta(seconds=ttl)),
    }
    payload_json = json.dumps(payload, ensure_ascii=False, sort_keys=True)
    signature = _sign(payload_json)

    con = _connect()
    try:
        con.execute(
            """
            INSERT INTO ai_tool_confirmations(
              nonce, tenant_id, user_id, tool_name, expires_at, consumed_at, created_at
            ) VALUES (?,?,?,?,?,?,?)
            """,
            (
                nonce,
                str(tenant_id or ""),
                str(user_id or "system"),
                str(tool_name or ""),
                str(payload["exp"]),
                None,
                _iso(now),
            ),
        )
        con.commit()
    finally:
        con.close()

    return f"{_b64url(payload_json.encode('utf-8'))}.{signature}"


def verify_confirmation(
    *, token: str, tenant_id: str, user_id: str, consume: bool = False
) -> dict[str, Any]:
    raw = str(token or "").strip()
    if "." not in raw:
        raise ValueError("invalid_token")
    payload_part, signature = raw.rsplit(".", 1)
    payload_json = _b64url_decode(payload_part).decode("utf-8")
    expected = _sign(payload_json)
    if not hmac.compare_digest(expected, signature):
        raise ValueError("invalid_signature")

    payload = json.loads(payload_json)
    if not isinstance(payload, dict):
        raise ValueError("invalid_payload")

    if str(payload.get("tenant_id") or "") != str(tenant_id or ""):
        raise ValueError("tenant_mismatch")
    if str(payload.get("user_id") or "") != str(user_id or ""):
        raise ValueError("user_mismatch")

    exp_iso = str(payload.get("exp") or "").strip()
    if not exp_iso:
        raise ValueError("missing_exp")
    exp_token = exp_iso[:-1] + "+00:00" if exp_iso.endswith("Z") else exp_iso
    expires_at = datetime.fromisoformat(exp_token)
    if expires_at.tzinfo is None:
        expires_at = expires_at.replace(tzinfo=timezone.utc)
    if _now() > expires_at.astimezone(timezone.utc):
        raise ValueError("token_expired")

    nonce = str(payload.get("nonce") or "").strip()
    if not nonce:
        raise ValueError("missing_nonce")

    con = _connect()
    try:
        row = con.execute(
            """
            SELECT nonce, tenant_id, user_id, tool_name, expires_at, consumed_at
            FROM ai_tool_confirmations
            WHERE nonce=?
            LIMIT 1
            """,
            (nonce,),
        ).fetchone()
        if row is None:
            raise ValueError("nonce_not_found")
        if str(row["tenant_id"] or "") != str(tenant_id or ""):
            raise ValueError("tenant_mismatch")
        if str(row["user_id"] or "") != str(user_id or ""):
            raise ValueError("user_mismatch")
        if str(row["consumed_at"] or "").strip():
            raise ValueError("token_replayed")

        if consume:
            now_iso = _iso(_now())
            cur = con.execute(
                """
                UPDATE ai_tool_confirmations
                SET consumed_at=?
                WHERE nonce=? AND consumed_at IS NULL
                """,
                (now_iso, nonce),
            )
            if int(cur.rowcount or 0) != 1:
                raise ValueError("token_replayed")
            con.commit()
    finally:
        con.close()

    return payload
