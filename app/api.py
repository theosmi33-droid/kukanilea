from __future__ import annotations

import sqlite3
from datetime import datetime, timezone
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


@bp.post("/mesh/handshake")
def mesh_handshake():
    """Handles incoming handshake requests from peer Hubs."""
    from flask import request
    from app.core.mesh_network import MeshNetworkManager
    from app.core.mesh_identity import verify_signature, sign_message, ensure_mesh_identity
    import json

    body = request.json
    data = body.get("data")
    sig = body.get("signature")

    if not data or not sig:
        return jsonify(ok=False, error="invalid_request"), 400

    # Verify peer signature
    peer_pub_key = data.get("public_key")
    if not verify_signature(peer_pub_key, json.dumps(data, sort_keys=True).encode('utf-8'), sig):
        return jsonify(ok=False, error="invalid_signature"), 401

    # Register peer locally
    auth_db = current_app.extensions["auth_db"]
    manager = MeshNetworkManager(auth_db)
    manager.register_peer(
        data["node_id"],
        data["name"],
        data["public_key"],
        request.remote_addr
    )

    # Respond with our identity
    my_pub, my_node = ensure_mesh_identity()
    response_data = {
        "node_id": my_node,
        "name": current_app.config.get("APP_NAME", "KUKANILEA Hub"),
        "public_key": my_pub,
        "timestamp": datetime.now(timezone.utc).isoformat() + "Z"
    }
    my_sig = sign_message(json.dumps(response_data, sort_keys=True).encode('utf-8'))

    return jsonify(ok=True, peer=response_data, signature=my_sig)


@bp.get("/outbound/status")
def outbound_status():
    """Returns the current status of the API outbound queue."""
    auth_db = current_app.extensions["auth_db"]
    try:
        with auth_db._db() as con:
            con.row_factory = sqlite3.Row
            rows = con.execute(
                "SELECT status, COUNT(*) as count FROM api_outbound_queue GROUP BY status"
            ).fetchall()
            stats = {row["status"]: row["count"] for row in rows}
            
            recent_failed = con.execute(
                "SELECT target_system, error_message, last_attempt FROM api_outbound_queue WHERE status = 'failed' ORDER BY last_attempt DESC LIMIT 5"
            ).fetchall()
            
            return jsonify(
                ok=True, 
                stats=stats,
                recent_failed=[dict(r) for r in recent_failed]
            )
    except Exception as e:
        return jsonify(ok=False, error=str(e)), 500
