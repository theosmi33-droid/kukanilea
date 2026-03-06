from __future__ import annotations

import json
import os
import re
import secrets
import shutil
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from flask import (
    Blueprint,
    current_app,
    jsonify,
    redirect,
    render_template,
    request,
    session,
    url_for,
)

from app.auth import (
    current_role,
    current_tenant,
    current_user,
    hash_password,
    login_required,
    require_role,
)
from app.config import Config
from app.core.logic import audit_log
from app.core.mesh_identity import ensure_mesh_identity, get_identity_paths
from app.core.mesh_network import MeshNetworkManager
from app.core.tenant_registry import tenant_registry
from app.license import load_license
from app.security.gates import (
    CRITICAL_CONFIRM_GATE_BY_ROUTE,
    confirm_gate,
    scan_payload_for_injection,
)

bp = Blueprint("admin_tenants", __name__, url_prefix="/admin")

ROLE_LABEL_TO_DB = {
    "admin": "ADMIN",
    "manager": "OPERATOR",
    "mitarbeiter": "READONLY",
}
ROLE_DB_TO_LABEL = {v: k for k, v in ROLE_LABEL_TO_DB.items()}
HOSTNAME_PATTERN = re.compile(r"^(?:[a-zA-Z0-9](?:[a-zA-Z0-9\-]{0,61}[a-zA-Z0-9])?\.)+[a-zA-Z]{2,6}$")
IP_PATTERN = re.compile(r"^(?:\d{1,3}\.){3}\d{1,3}$")
def _system_settings_file() -> Path:
    # Resolve from Config on each call so tests/runtime overrides are respected.
    return Config.USER_DATA_ROOT / "system_settings.json"


def _now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _sqlite_backup(src_path: Path, dest_path: Path) -> bool:
    """Uses the SQLite backup API for a cleaner snapshot of live DBs."""
    if not src_path.exists():
        return False
    try:
        src = sqlite3.connect(str(src_path))
        dst = sqlite3.connect(str(dest_path))
        with dst:
            src.backup(dst)
        dst.close()
        src.close()
        return True
    except Exception:
        return False


def _load_system_settings() -> dict[str, Any]:
    defaults = {
        "language": "de",
        "timezone": "Europe/Berlin",
        "backup_interval": "daily",
        "log_level": "INFO",
        "external_apis_enabled": False,
        "memory_retention_days": 60,
        "backup_verify_hook_enabled": True,
        "restore_verify_hook_enabled": True,
        "mesh_mdns_enabled": True,
        "mesh_tailscale_enabled": False,
    }
    settings_file = _system_settings_file()
    if settings_file.exists():
        try:
            data = json.loads(settings_file.read_text(encoding="utf-8"))
            if isinstance(data, dict):
                defaults.update(data)
        except Exception:
            pass
    return defaults


def _save_system_settings(payload: dict[str, Any]) -> None:
    settings_file = _system_settings_file()
    settings_file.parent.mkdir(parents=True, exist_ok=True)
    settings_file.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def _confirm_gate(value: str) -> bool:
    return confirm_gate(value)


def _reject_injection(fields: tuple[str, ...]):
    finding = scan_payload_for_injection(request.form, fields)
    if finding:
        return jsonify(ok=False, error="injection_blocked", field=finding.field), 400
    return None


def _require_confirm():
    if not _confirm_gate(request.form.get("confirm")):
        return jsonify(ok=False, error="confirm_required"), 400
    return None


def _enforce_critical_gate(route: str):
    policy = CRITICAL_CONFIRM_GATE_BY_ROUTE.get(route)
    if not policy:
        return None
    blocked = _reject_injection(policy.fields)
    if blocked:
        return blocked
    if policy.required:
        return _require_confirm()
    return None


def _auth_db():
    return current_app.extensions["auth_db"]


def _backup_dir() -> Path:
    path = Config.USER_DATA_ROOT / "backups"
    path.mkdir(parents=True, exist_ok=True)
    return path


def _backup_targets() -> dict[str, Path]:
    return {
        "auth.sqlite3": Config.AUTH_DB,
        "core.sqlite3": Config.CORE_DB,
        "license.json": Config.LICENSE_PATH,
    }


def _backup_targets_status() -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for label, target in _backup_targets().items():
        resolved = target.expanduser().resolve()
        rows.append(
            {
                "label": label,
                "path": str(resolved),
                "exists": resolved.exists(),
            }
        )
    return rows


def _list_backups() -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for item in sorted(_backup_dir().glob("*.bak"), key=lambda p: p.stat().st_mtime, reverse=True):
        stat = item.stat()
        rows.append(
            {
                "name": item.name,
                "size": stat.st_size,
                "mtime": datetime.fromtimestamp(stat.st_mtime, tz=timezone.utc).isoformat().replace("+00:00", "Z"),
            }
        )
    return rows


def _run_backup() -> list[str]:
    ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    targets = _backup_targets()
    written: list[str] = []
    for label, src in targets.items():
        if not src.exists():
            continue
        dest = _backup_dir() / f"{label}__{ts}.bak"
        if src.suffix.lower() in (".sqlite3", ".db", ".sqlite"):
            if _sqlite_backup(src, dest):
                written.append(dest.name)
        else:
            shutil.copy2(src, dest)
            written.append(dest.name)
    return written


def _restore_backup(backup_name: str) -> str:
    allowed = _backup_targets()
    src = (_backup_dir() / str(backup_name or "")).resolve()
    if not src.exists() or src.suffix.lower() != ".bak":
        raise ValueError("backup_not_found")
    if src.parent != _backup_dir().resolve():
        raise ValueError("invalid_backup_path")

    label = src.name.split("__", 1)[0]
    target = allowed.get(label)
    if not target:
        raise ValueError("unsupported_backup")

    target.parent.mkdir(parents=True, exist_ok=True)
    if target.suffix.lower() in (".sqlite3", ".db", ".sqlite"):
        if not _sqlite_backup(src, target):
            raise RuntimeError(f"failed_to_restore_db:{label}")
    else:
        shutil.copy2(src, target)
    return str(target)


def _list_users_with_roles() -> list[dict[str, Any]]:
    with _auth_db()._db() as con:
        rows = con.execute(
            """
            SELECT
              u.username,
              u.needs_reset,
              m.tenant_id,
              m.role
            FROM users u
            LEFT JOIN memberships m ON m.username = u.username
            ORDER BY u.username ASC, m.tenant_id ASC
            """
        ).fetchall()
        return [
            {
                "username": str(r["username"]),
                "needs_reset": int(r["needs_reset"] or 0),
                "tenant_id": str(r["tenant_id"] or ""),
                "role_db": str(r["role"] or "READONLY"),
                "role_label": ROLE_DB_TO_LABEL.get(str(r["role"] or "READONLY"), "mitarbeiter"),
            }
            for r in rows
        ]


def _list_mesh_peers() -> list[dict[str, Any]]:
    try:
        manager = MeshNetworkManager(_auth_db())
        peers = manager.get_peers()
    except Exception:
        return []
    for peer in peers:
        peer["status"] = str(peer.get("status") or "OFFLINE")
        peer["last_seen"] = str(peer.get("last_seen") or "-")
    return peers


@bp.route("/tenants")
@login_required
@require_role("ADMIN")
def list_tenants():
    # Router-style Settings Console entrypoint for Admins.
    return redirect(url_for("admin_tenants.settings_console"))


@bp.route("/settings")
@login_required
def settings_console():
    role = current_role()
    settings = _load_system_settings()

    if role not in {"ADMIN", "DEV"}:
        return render_template(
            "settings.html",
            active_tab="settings",
            settings_mode="profile",
            user_profile={
                "username": current_user() or "",
                "role": role,
                "tenant_id": current_tenant(),
                "language": session.get("ui_language", settings.get("language", "de")),
                "timezone": session.get("ui_timezone", settings.get("timezone", "Europe/Berlin")),
            },
        )

    auth_db = _auth_db()
    with auth_db._db() as con:
        tenant_rows = con.execute(
            "SELECT tenant_id, display_name, core_db_path FROM tenants ORDER BY tenant_id ASC"
        ).fetchall()

    license_info = load_license(Config.LICENSE_PATH)
    runtime_status = str(current_app.config.get("LICENSE_STATUS", "active"))
    mesh_pub, mesh_node = ensure_mesh_identity()

    return render_template(
        "settings.html",
        active_tab="settings",
        settings_mode="admin",
        users=_list_users_with_roles(),
        tenants=[
            {
                "tenant_id": str(r["tenant_id"]),
                "display_name": str(r["display_name"]),
                "core_db_path": str(r["core_db_path"] or ""),
            }
            for r in tenant_rows
        ],
        tenant_registry_rows=tenant_registry.list_tenants(),
        license_info=license_info,
        license_runtime_status=runtime_status,
        mesh_peers=_list_mesh_peers(),
        mesh_config=settings,
        mesh_node_id=mesh_node,
        mesh_public_key=mesh_pub,
        system_settings=settings,
        branding=Config.get_branding(),
        backups=_list_backups(),
        backup_targets=_backup_targets_status(),
        role_options=["admin", "manager", "mitarbeiter"],
    )


@bp.route("/settings/profile", methods=["POST"])
@login_required
def update_profile_preferences():
    confirm_error = _enforce_critical_gate("/admin/settings/profile")
    if confirm_error:
        return confirm_error

    session["ui_language"] = (request.form.get("language") or "de").strip().lower()
    session["ui_timezone"] = (request.form.get("timezone") or "Europe/Berlin").strip()
    return redirect(url_for("admin_tenants.settings_console"))


@bp.route("/settings/users/create", methods=["POST"])
@login_required
@require_role("ADMIN")
def create_user():
    confirm_error = _enforce_critical_gate("/admin/settings/users/create")
    if confirm_error:
        return confirm_error

    username = (request.form.get("username") or "").strip().lower()
    password = (request.form.get("password") or "").strip()
    tenant_id = (request.form.get("tenant_id") or "").strip() or "SYSTEM"
    role_label = (request.form.get("role") or "mitarbeiter").strip().lower()
    role_db = ROLE_LABEL_TO_DB.get(role_label, "READONLY")

    if not username or not password:
        return jsonify(ok=False, error="username_password_required"), 400

    now = _now_iso()
    auth_db = _auth_db()
    auth_db.upsert_user(username, hash_password(password), now)
    auth_db.upsert_membership(username, tenant_id, role_db, now)

    audit_log(
        user=current_user() or "system",
        role=current_role() or "ADMIN",
        action="USER_CREATE",
        target=username,
        meta={"tenant_id": tenant_id, "role": role_db},
        tenant_id=current_tenant() or "SYSTEM",
    )
    return redirect(url_for("admin_tenants.settings_console", section="users"))


@bp.route("/settings/users/update", methods=["POST"])
@login_required
@require_role("ADMIN")
def update_user_role():
    confirm_error = _enforce_critical_gate("/admin/settings/users/update")
    if confirm_error:
        return confirm_error

    username = (request.form.get("username") or "").strip().lower()
    tenant_id = (request.form.get("tenant_id") or "").strip() or "SYSTEM"
    role_label = (request.form.get("role") or "mitarbeiter").strip().lower()
    role_db = ROLE_LABEL_TO_DB.get(role_label, "READONLY")

    if not username:
        return jsonify(ok=False, error="username_required"), 400

    _auth_db().upsert_membership(username, tenant_id, role_db, _now_iso())

    audit_log(
        user=current_user() or "system",
        role=current_role() or "ADMIN",
        action="USER_ROLE_UPDATE",
        target=username,
        meta={"tenant_id": tenant_id, "role": role_db},
        tenant_id=current_tenant() or "SYSTEM",
    )
    return redirect(url_for("admin_tenants.settings_console", section="users"))


@bp.route("/settings/users/disable", methods=["POST"])
@login_required
@require_role("ADMIN")
def disable_user():
    confirm_error = _enforce_critical_gate("/admin/settings/users/disable")
    if confirm_error:
        return confirm_error

    username = (request.form.get("username") or "").strip().lower()
    actor = current_user() or ""
    if not username:
        return jsonify(ok=False, error="username_required"), 400
    if username == actor:
        return jsonify(ok=False, error="cannot_disable_self"), 400

    random_pw = secrets.token_urlsafe(32)
    with _auth_db()._db() as con:
        con.execute(
            "UPDATE users SET password_hash=?, needs_reset=1 WHERE username=?",
            (hash_password(random_pw), username),
        )
        con.commit()

    audit_log(
        user=actor,
        role=current_role() or "ADMIN",
        action="USER_DISABLE",
        target=username,
        tenant_id=current_tenant() or "SYSTEM",
    )
    return redirect(url_for("admin_tenants.settings_console", section="users"))


@bp.route("/settings/users/delete", methods=["POST"])
@login_required
@require_role("ADMIN")
def delete_user():
    confirm_error = _enforce_critical_gate("/admin/settings/users/delete")
    if confirm_error:
        return confirm_error

    username = (request.form.get("username") or "").strip().lower()
    actor = current_user() or ""

    if not username:
        return jsonify(ok=False, error="username_required"), 400
    if username == actor:
        return jsonify(ok=False, error="cannot_delete_self"), 400

    with _auth_db()._db() as con:
        admin_count = con.execute(
            "SELECT COUNT(*) AS c FROM memberships WHERE role='ADMIN'"
        ).fetchone()["c"]
        is_admin_user = con.execute(
            "SELECT 1 FROM memberships WHERE username=? AND role='ADMIN' LIMIT 1", (username,)
        ).fetchone()
        if int(admin_count or 0) <= 1 and is_admin_user:
            return jsonify(ok=False, error="cannot_delete_last_admin"), 400

        con.execute("DELETE FROM users WHERE username=?", (username,))
        con.commit()

    audit_log(
        user=actor,
        role=current_role() or "ADMIN",
        action="USER_DELETE",
        target=username,
        tenant_id=current_tenant() or "SYSTEM",
    )
    return redirect(url_for("admin_tenants.settings_console", section="users"))


@bp.route("/settings/tenants/add", methods=["POST"])
@login_required
@require_role("ADMIN")
def add_tenant():
    confirm_error = _enforce_critical_gate("/admin/settings/tenants/add")
    if confirm_error:
        return confirm_error

    name = (request.form.get("name") or "").strip()
    db_path = (request.form.get("db_path") or "").strip()

    if not name or not db_path:
        return jsonify(ok=False, error="name_path_required"), 400

    tenant_id = tenant_registry.normalize_tenant_id(name)
    if not tenant_id:
        return jsonify(ok=False, error="invalid_tenant_id"), 400

    path = Path(db_path).expanduser().resolve()
    if not tenant_registry.validate_path(str(path), tenant_id=tenant_id):
        return jsonify(ok=False, error="invalid_path"), 400
    if not path.exists() or not os.access(path, os.R_OK | os.W_OK):
        return jsonify(ok=False, error="db_not_accessible"), 400

    if not tenant_registry.add_tenant(tenant_id, name, str(path.resolve())):
        return jsonify(ok=False, error="tenant_register_failed"), 500

    with _auth_db()._db() as con:
        con.execute(
            "INSERT OR IGNORE INTO tenants(tenant_id, display_name, core_db_path, created_at) VALUES (?,?,?,?)",
            (tenant_id, name, str(path.resolve()), _now_iso()),
        )
        con.commit()

    return redirect(url_for("admin_tenants.settings_console", section="tenants"))


@bp.route("/context/switch", methods=["POST"])
@login_required
@require_role("ADMIN")
def switch_context():
    gate_error = _enforce_critical_gate("/admin/context/switch")
    if gate_error:
        return gate_error

    tenant_id = request.form.get("tenant_id")
    if not tenant_id:
        return "", 400

    tenant = tenant_registry.get_tenant(tenant_id)
    if not tenant:
        return "Mandant nicht gefunden", 404

    session["tenant_id"] = tenant_id
    session["tenant_name"] = tenant["name"]
    session["tenant_db_path"] = tenant["db_path"]

    response = jsonify(ok=True)
    response.headers["HX-Refresh"] = "true"
    return response


@bp.route("/settings/license/upload", methods=["POST"])
@login_required
@require_role("ADMIN")
def upload_license():
    confirm_error = _enforce_critical_gate("/admin/settings/license/upload")
    if confirm_error:
        return confirm_error

    payload_text = (request.form.get("license_json") or "").strip()

    if not payload_text:
        return jsonify(ok=False, error="license_required"), 400

    try:
        payload = json.loads(payload_text)
    except Exception:
        return jsonify(ok=False, error="invalid_json"), 400

    temp_license = Config.LICENSE_PATH.with_suffix(".new")
    try:
        temp_license.parent.mkdir(parents=True, exist_ok=True)
        temp_license.write_text(json.dumps(payload, indent=2), encoding="utf-8")

        # Test validation before committing to final path
        parsed = load_license(temp_license)
        if not parsed.get("valid"):
            if temp_license.exists():
                temp_license.unlink()
            return jsonify(ok=False, error="invalid_license", reason=parsed.get("reason")), 400

        # Atomic swap
        os.replace(temp_license, Config.LICENSE_PATH)
        try:
            os.chmod(Config.LICENSE_PATH, 0o600)
        except OSError:
            pass

        audit_log(
            user=current_user() or "system",
            role=current_role() or "ADMIN",
            action="LICENSE_UPLOAD",
            meta={"plan": payload.get("plan"), "customer_id": payload.get("customer_id")},
            tenant_id=current_tenant() or "SYSTEM",
        )
    except Exception as e:
        if temp_license.exists():
            temp_license.unlink()
        return jsonify(ok=False, error="system_error", detail=str(e)), 500

    return redirect(url_for("admin_tenants.settings_console", section="license"))


@bp.route("/settings/system", methods=["POST"])
@login_required
@require_role("ADMIN")
def save_system_settings():
    confirm_error = _enforce_critical_gate("/admin/settings/system")
    if confirm_error:
        return confirm_error

    payload = _load_system_settings()
    retention_raw = (request.form.get("memory_retention_days") or payload.get("memory_retention_days") or 60)
    try:
        retention_days = max(1, int(retention_raw))
    except (TypeError, ValueError):
        retention_days = int(payload.get("memory_retention_days") or 60)
    payload.update(
        {
            "language": (request.form.get("language") or payload.get("language") or "de").strip().lower(),
            "timezone": (request.form.get("timezone") or payload.get("timezone") or "Europe/Berlin").strip(),
            "backup_interval": (request.form.get("backup_interval") or payload.get("backup_interval") or "daily").strip().lower(),
            "log_level": (request.form.get("log_level") or payload.get("log_level") or "INFO").strip().upper(),
            "external_apis_enabled": (request.form.get("external_apis_enabled") or "off") == "on",
            "memory_retention_days": retention_days,
            "backup_verify_hook_enabled": (request.form.get("backup_verify_hook_enabled") or "off") == "on",
            "restore_verify_hook_enabled": (request.form.get("restore_verify_hook_enabled") or "off") == "on",
            "mesh_mdns_enabled": (request.form.get("mesh_mdns_enabled") or "off") == "on",
            "mesh_tailscale_enabled": (request.form.get("mesh_tailscale_enabled") or "off") == "on",
        }
    )
    _save_system_settings(payload)
    audit_log(
        user=current_user() or "system",
        role=current_role() or "ADMIN",
        action="SYSTEM_SETTINGS_UPDATE",
        meta=payload,
        tenant_id=current_tenant() or "SYSTEM",
    )
    return redirect(url_for("admin_tenants.settings_console", section="system"))


@bp.route("/settings/branding", methods=["POST"])
@login_required
@require_role("ADMIN")
def save_branding():
    confirm_error = _enforce_critical_gate("/admin/settings/branding")
    if confirm_error:
        return confirm_error

    payload = {
        "app_name": (request.form.get("app_name") or "KUKANILEA").strip(),
        "primary_color": (request.form.get("primary_color") or "#2563eb").strip(),
        "footer_text": (request.form.get("footer_text") or "").strip(),
    }
    Config.BRANDING_FILE.parent.mkdir(parents=True, exist_ok=True)
    temp_branding = Config.BRANDING_FILE.with_suffix(".tmp")
    try:
        temp_branding.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        os.replace(temp_branding, Config.BRANDING_FILE)
    except Exception as e:
        if temp_branding.exists():
            temp_branding.unlink()
        raise e

    audit_log(
        user=current_user() or "system",
        role=current_role() or "ADMIN",
        action="BRANDING_UPDATE",
        meta=payload,
        tenant_id=current_tenant() or "SYSTEM",
    )
    return redirect(url_for("admin_tenants.settings_console", section="branding"))


@bp.route("/settings/backup/run", methods=["POST"])
@login_required
@require_role("ADMIN")
def backup_run():
    confirm_error = _enforce_critical_gate("/admin/settings/backup/run")
    if confirm_error:
        return confirm_error

    written = _run_backup()
    audit_log(
        user=current_user() or "system",
        role=current_role() or "ADMIN",
        action="BACKUP_RUN",
        meta={"files": written},
        tenant_id=current_tenant() or "SYSTEM",
    )
    return redirect(url_for("admin_tenants.settings_console", section="backup"))


@bp.route("/settings/backup/restore", methods=["POST"])
@login_required
@require_role("ADMIN")
def backup_restore():
    confirm_error = _enforce_critical_gate("/admin/settings/backup/restore")
    if confirm_error:
        return confirm_error

    backup_name = (request.form.get("backup_name") or "").strip()
    target = _restore_backup(backup_name)
    audit_log(
        user=current_user() or "system",
        role=current_role() or "ADMIN",
        action="BACKUP_RESTORE",
        target=backup_name,
        meta={"restored_path": target},
        tenant_id=current_tenant() or "SYSTEM",
    )
    return redirect(url_for("admin_tenants.settings_console", section="backup"))


@bp.route("/settings/mesh/connect", methods=["POST"])
@login_required
@require_role("ADMIN")
def mesh_connect():
    confirm_error = _enforce_critical_gate("/admin/settings/mesh/connect")
    if confirm_error:
        return confirm_error

    peer_ip = (request.form.get("peer_ip") or "").strip()
    peer_port_text = (request.form.get("peer_port") or "5051").strip()
    if not peer_ip:
        return jsonify(ok=False, error="peer_ip_required"), 400

    if not IP_PATTERN.fullmatch(peer_ip) and not HOSTNAME_PATTERN.fullmatch(peer_ip):
        # Allow 'localhost' or single-word hostnames for local dev
        if peer_ip.lower() not in ("localhost", "hub-1", "hub-2"):
            return jsonify(ok=False, error="invalid_peer_address"), 400

    try:
        peer_port = int(peer_port_text)
    except ValueError:
        return jsonify(ok=False, error="invalid_port"), 400

    manager = MeshNetworkManager(_auth_db())
    ok = manager.initiate_handshake(peer_ip, peer_port)
    if not ok:
        return jsonify(ok=False, error="handshake_failed"), 400

    audit_log(
        user=current_user() or "system",
        role=current_role() or "ADMIN",
        action="MESH_PEER_CONNECT",
        target=f"{peer_ip}:{peer_port}",
        tenant_id=current_tenant() or "SYSTEM",
    )
    return redirect(url_for("admin_tenants.settings_console", section="mesh"))


@bp.route("/settings/mesh/rotate-key", methods=["POST"])
@login_required
@require_role("ADMIN")
def mesh_rotate_key():
    confirm_error = _enforce_critical_gate("/admin/settings/mesh/rotate-key")
    if confirm_error:
        return confirm_error

    priv_path, pub_path = get_identity_paths()
    if priv_path.exists():
        priv_path.unlink()
    if pub_path.exists():
        pub_path.unlink()

    ensure_mesh_identity()

    audit_log(
        user=current_user() or "system",
        role=current_role() or "ADMIN",
        action="MESH_KEY_ROTATE",
        tenant_id=current_tenant() or "SYSTEM",
    )
    return redirect(url_for("admin_tenants.settings_console", section="mesh"))
