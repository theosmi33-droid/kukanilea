from __future__ import annotations

from datetime import UTC, datetime

from flask import Blueprint, current_app, jsonify

from app.health import checks as health_checks
from app.health.core import HealthRunner

bp = Blueprint("api", __name__, url_prefix="/api")


@bp.get("/ping")
def ping():
    return jsonify(ok=True)


@bp.get("/health")
def health():
    auth_db = current_app.extensions["auth_db"]
    core_stats = {}
    profile = {}
    db_path = ""
    tenant_id = ""
    try:
        from app import web  # local import to avoid circular refs

        tenant_id = web.current_tenant()
        core = getattr(web, "core", None)
        if core and callable(getattr(core, "get_health_stats", None)):
            core_stats = core.get_health_stats(tenant_id=tenant_id)
        if core and callable(getattr(core, "get_profile", None)):
            profile = core.get_profile()
        db_path = str(getattr(core, "DB_PATH", "")) if core else ""
    except Exception:
        core_stats = {}
    from app.services.clamav_client import clamav
    clamav_status = "OK" if clamav.ping() else "OFFLINE"

    return jsonify(
        ok=True,
        schema_version=auth_db.get_schema_version(),
        auth_db_path=str(auth_db.path),
        tenants=auth_db.count_tenants(),
        last_indexed_at=core_stats.get("last_indexed_at"),
        doc_count=core_stats.get("doc_count", 0),
        fts_enabled=core_stats.get("fts_enabled", False),
        tenant_id=tenant_id,
        profile=profile or None,
        db_path=db_path,
        clamav=clamav_status,
    )


@bp.get("/health/live")
def health_live():
    return jsonify(ok=True, ts=datetime.now(UTC).isoformat(timespec="seconds"))


@bp.get("/health/ready")
def health_ready():
    runner = HealthRunner(
        mode="runtime", strict=False, eventlog_limit=100, timeout_s=1.5
    )
    runner.checks = [getattr(health_checks, name) for name in health_checks.ALL_CHECKS]
    report = runner.run()
    checks = [
        {
            "name": c.name,
            "ok": bool(c.ok),
            "severity": c.severity,
            "reason": c.reason or "",
        }
        for c in report.checks
    ]
    status = 200 if report.ok else 503
    return (
        jsonify(
            ok=bool(report.ok),
            ts=report.ts.isoformat(timespec="seconds"),
            checks=checks,
        ),
        status,
    )


@bp.get("/hub/vitals")
def hub_vitals():
    """Gibt Hub-spezifische Hardware-Metriken zurück."""
    from app.core.hub_metrics import get_hub_vitals
    return jsonify(get_hub_vitals())
