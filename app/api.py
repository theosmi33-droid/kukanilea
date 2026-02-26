from __future__ import annotations

from flask import Blueprint, current_app, jsonify

from .rate_limit import search_limiter

bp = Blueprint("api", __name__, url_prefix="/api")


@bp.get("/ping")
@search_limiter.limit_required
def ping():
    return jsonify(ok=True)


@bp.get("/health")
@search_limiter.limit_required
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
    )
