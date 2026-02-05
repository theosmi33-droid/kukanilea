from __future__ import annotations

from flask import Blueprint, jsonify, current_app

bp = Blueprint("api", __name__, url_prefix="/api")


@bp.get("/ping")
def ping():
    return jsonify(ok=True)


@bp.get("/health")
def health():
    auth_db = current_app.extensions["auth_db"]
    return jsonify(
        ok=True,
        schema_version=auth_db.get_schema_version(),
        auth_db_path=str(auth_db.path),
        tenants=auth_db.count_tenants(),
    )
