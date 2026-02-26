from __future__ import annotations

import sqlite3

from flask import Flask, g, jsonify, request


def check_db_integrity(db_path: str, deep=False) -> bool:
    try:
        conn = sqlite3.connect(db_path)
        pragma = "integrity_check" if deep else "quick_check"
        cursor = conn.execute(f"PRAGMA {pragma};")
        result = cursor.fetchone()
        conn.close()
        return result is not None and result[0] == "ok"
    except Exception:
        return False


def init_healer(app: Flask) -> None:
    enabled = app.config.get("KUK_HEALER_ENABLED", False)
    if not enabled:
        return

    db_path = str(app.config.get("CORE_DB", "core.sqlite3"))

    # Simple check on startup
    if not check_db_integrity(db_path):
        app.logger.error(
            "Database integrity check failed! Switching to Degraded Read-Only Mode."
        )
        app.config["MAINTENANCE_READ_ONLY"] = True
    else:
        app.config["MAINTENANCE_READ_ONLY"] = False

    @app.before_request
    def enforce_degraded_mode():
        if not app.config.get("MAINTENANCE_READ_ONLY"):
            return None

        # For certain routes, we might allow read-only access
        # But for maintenance, it's safer to block all mutating operations
        if request.method.upper() in {"POST", "PUT", "PATCH", "DELETE"}:
            rid = getattr(g, "request_id", "-")
            return jsonify(
                {
                    "error": "maintenance_mode",
                    "message": "The system is in a degraded read-only mode due to a database integrity issue.",
                    "request_id": rid,
                    "status": "degraded",
                }
            ), 503
        return None
