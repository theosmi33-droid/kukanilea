"""Prometheus-style metrics endpoint blueprint."""

from __future__ import annotations

import os
import sqlite3

from flask import Blueprint, Response

from app.auth import login_required, require_role

bp = Blueprint("metrics", __name__)


def get_last_backup_age_seconds(tenant_id: str = "M001") -> int:
    # Placeholder until NAS backup metadata integration is connected.
    _ = tenant_id
    return 24 * 3600


@bp.route("/metrics")
@login_required
@require_role("ADMIN")
def metrics() -> Response:
    lines = [f"kukanilea_last_backup_age_seconds {get_last_backup_age_seconds()}"]

    db_path = os.environ.get("KUKANILEA_AUTH_DB", "instance/auth.sqlite3")
    pending = 0
    try:
        conn = sqlite3.connect(db_path)
        try:
            cur = conn.cursor()
            cur.execute("SELECT COUNT(*) FROM api_outbound_queue WHERE status='pending'")
            pending = int(cur.fetchone()[0])
        finally:
            conn.close()
    except Exception:
        pending = 0

    lines.append(f"kukanilea_outbound_queue_pending {pending}")
    return Response("\n".join(lines) + "\n", mimetype="text/plain")
