from __future__ import annotations

import json
import os
import sqlite3
import uuid
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any

from flask import Flask, jsonify, request


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _safe_date(value: str | None) -> date | None:
    text = str(value or "").strip()
    if not text:
        return None
    try:
        return date.fromisoformat(text)
    except Exception:
        return None


def _db_connect(path: Path) -> sqlite3.Connection:
    conn = sqlite3.connect(str(path))
    conn.row_factory = sqlite3.Row
    return conn


def init_db(db_path: Path) -> None:
    db_path.parent.mkdir(parents=True, exist_ok=True)
    with _db_connect(db_path) as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS licenses (
              id TEXT PRIMARY KEY,
              customer_id TEXT NOT NULL UNIQUE,
              license_key TEXT UNIQUE,
              tier TEXT NOT NULL,
              valid_until TEXT NOT NULL,
              status TEXT NOT NULL DEFAULT 'active',
              device_fingerprint TEXT,
              max_devices INTEGER NOT NULL DEFAULT 1,
              metadata_json TEXT,
              created_at TEXT NOT NULL,
              updated_at TEXT NOT NULL
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS device_bindings (
              id TEXT PRIMARY KEY,
              license_id TEXT NOT NULL,
              device_fingerprint TEXT NOT NULL,
              first_seen_at TEXT NOT NULL,
              last_seen_at TEXT NOT NULL,
              UNIQUE(license_id, device_fingerprint),
              FOREIGN KEY(license_id) REFERENCES licenses(id)
            )
            """
        )
        conn.commit()


def _extract_customer_id(payload: dict[str, Any]) -> str:
    license_blob = payload.get("license")
    if isinstance(license_blob, dict):
        customer_id = str(license_blob.get("customer_id") or "").strip()
        if customer_id:
            return customer_id
    return str(payload.get("customer_id") or "").strip()


def _require_admin_token(app: Flask) -> bool:
    expected = str(app.config.get("API_TOKEN") or "").strip()
    if not expected:
        return True
    provided = str(request.headers.get("X-API-Token") or "").strip()
    return provided == expected


def _upsert_device_binding(
    conn: sqlite3.Connection,
    *,
    license_id: str,
    device_fingerprint: str,
) -> None:
    now = _utc_now_iso()
    row = conn.execute(
        """
        SELECT id
          FROM device_bindings
         WHERE license_id=? AND device_fingerprint=?
         LIMIT 1
        """,
        (license_id, device_fingerprint),
    ).fetchone()
    if row:
        conn.execute(
            "UPDATE device_bindings SET last_seen_at=? WHERE id=?",
            (now, str(row["id"])),
        )
        return
    conn.execute(
        """
        INSERT INTO device_bindings(
          id, license_id, device_fingerprint, first_seen_at, last_seen_at
        ) VALUES(?,?,?,?,?)
        """,
        (str(uuid.uuid4()), license_id, device_fingerprint, now, now),
    )


def create_app(config: dict[str, Any] | None = None) -> Flask:
    app = Flask(__name__)
    app.config["DB_PATH"] = Path(
        str(
            os.environ.get(
                "LICENSE_SERVER_DB",
                str(Path(__file__).resolve().parent / "license_server.db"),
            )
        )
    )
    app.config["API_TOKEN"] = os.environ.get("LICENSE_SERVER_API_TOKEN", "")

    if config:
        app.config.update(config)

    init_db(Path(app.config["DB_PATH"]))

    @app.get("/health")
    def health() -> Any:
        return jsonify({"ok": True, "service": "kukanilea-license-server"})

    @app.post("/api/v1/validate")
    def validate() -> Any:
        payload = request.get_json(silent=True)
        if not isinstance(payload, dict):
            return jsonify({"valid": False, "reason": "invalid_request"}), 400

        customer_id = _extract_customer_id(payload)
        if not customer_id:
            return jsonify({"valid": False, "reason": "missing_customer_id"}), 400

        device_fingerprint = str(payload.get("device_fingerprint") or "").strip()

        with _db_connect(Path(app.config["DB_PATH"])) as conn:
            row = conn.execute(
                """
                SELECT id, customer_id, tier, valid_until, status,
                       COALESCE(device_fingerprint, '') AS pinned_device,
                       COALESCE(max_devices, 1) AS max_devices
                  FROM licenses
                 WHERE customer_id=?
                 LIMIT 1
                """,
                (customer_id,),
            ).fetchone()

            if row is None:
                return jsonify({"valid": False, "reason": "unknown_license"})

            status = str(row["status"] or "active").strip().lower()
            if status != "active":
                return jsonify({"valid": False, "reason": status or "invalid"})

            valid_until = _safe_date(str(row["valid_until"] or ""))
            if valid_until is None:
                return jsonify({"valid": False, "reason": "invalid_valid_until"})
            if valid_until < date.today():
                return jsonify({"valid": False, "reason": "expired"})

            pinned_device = str(row["pinned_device"] or "").strip()
            max_devices = max(1, int(row["max_devices"] or 1))
            license_id = str(row["id"])

            if device_fingerprint:
                if pinned_device and pinned_device != device_fingerprint:
                    return jsonify({"valid": False, "reason": "device_mismatch"})

                if not pinned_device and max_devices == 1:
                    conn.execute(
                        "UPDATE licenses SET device_fingerprint=?, updated_at=? WHERE id=?",
                        (device_fingerprint, _utc_now_iso(), license_id),
                    )
                elif max_devices > 1:
                    count_row = conn.execute(
                        "SELECT COUNT(*) AS c FROM device_bindings WHERE license_id=?",
                        (license_id,),
                    ).fetchone()
                    used_devices = int((count_row["c"] if count_row else 0) or 0)
                    known_row = conn.execute(
                        """
                        SELECT 1
                          FROM device_bindings
                         WHERE license_id=? AND device_fingerprint=?
                         LIMIT 1
                        """,
                        (license_id, device_fingerprint),
                    ).fetchone()
                    if known_row is None and used_devices >= max_devices:
                        return jsonify(
                            {"valid": False, "reason": "device_limit_reached"}
                        )
                    _upsert_device_binding(
                        conn,
                        license_id=license_id,
                        device_fingerprint=device_fingerprint,
                    )

                conn.commit()

            return jsonify(
                {
                    "valid": True,
                    "reason": "ok",
                    "tier": str(row["tier"]),
                    "valid_until": valid_until.isoformat(),
                }
            )

    @app.post("/api/v1/licenses/upsert")
    def upsert_license() -> Any:
        if not _require_admin_token(app):
            return jsonify({"ok": False, "error": "forbidden"}), 403

        payload = request.get_json(silent=True)
        if not isinstance(payload, dict):
            return jsonify({"ok": False, "error": "invalid_request"}), 400

        customer_id = str(payload.get("customer_id") or "").strip()
        tier = str(payload.get("tier") or "").strip() or "pro"
        valid_until = str(payload.get("valid_until") or "").strip()
        status = str(payload.get("status") or "active").strip().lower()

        if not customer_id or not valid_until:
            return (
                jsonify(
                    {
                        "ok": False,
                        "error": "customer_id_and_valid_until_required",
                    }
                ),
                400,
            )

        if _safe_date(valid_until) is None:
            return jsonify({"ok": False, "error": "invalid_valid_until"}), 400

        if status not in {"active", "revoked", "expired", "invalid"}:
            return jsonify({"ok": False, "error": "invalid_status"}), 400

        metadata = payload.get("metadata")
        if metadata is None:
            metadata_json = "{}"
        else:
            metadata_json = json.dumps(metadata, ensure_ascii=False)

        now = _utc_now_iso()
        license_key = str(payload.get("license_key") or "").strip() or None
        device_fingerprint = (
            str(payload.get("device_fingerprint") or "").strip() or None
        )
        max_devices = max(1, int(payload.get("max_devices") or 1))

        with _db_connect(Path(app.config["DB_PATH"])) as conn:
            existing = conn.execute(
                "SELECT id FROM licenses WHERE customer_id=? LIMIT 1",
                (customer_id,),
            ).fetchone()
            if existing:
                license_id = str(existing["id"])
                conn.execute(
                    """
                    UPDATE licenses
                       SET license_key=?, tier=?, valid_until=?, status=?,
                           device_fingerprint=?, max_devices=?, metadata_json=?,
                           updated_at=?
                     WHERE id=?
                    """,
                    (
                        license_key,
                        tier,
                        valid_until,
                        status,
                        device_fingerprint,
                        max_devices,
                        metadata_json,
                        now,
                        license_id,
                    ),
                )
            else:
                license_id = str(uuid.uuid4())
                conn.execute(
                    """
                    INSERT INTO licenses(
                      id, customer_id, license_key, tier, valid_until, status,
                      device_fingerprint, max_devices, metadata_json,
                      created_at, updated_at
                    ) VALUES(?,?,?,?,?,?,?,?,?,?,?)
                    """,
                    (
                        license_id,
                        customer_id,
                        license_key,
                        tier,
                        valid_until,
                        status,
                        device_fingerprint,
                        max_devices,
                        metadata_json,
                        now,
                        now,
                    ),
                )
            conn.commit()

        return jsonify(
            {
                "ok": True,
                "license": {
                    "id": license_id,
                    "customer_id": customer_id,
                    "tier": tier,
                    "valid_until": valid_until,
                    "status": status,
                },
            }
        )

    return app


if __name__ == "__main__":
    app = create_app()
    app.run(host="127.0.0.1", port=int(os.environ.get("LICENSE_SERVER_PORT", "5061")))
