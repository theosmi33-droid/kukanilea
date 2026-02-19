#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
KUKANILEA Systems — Upload/UI v3 (Split-View + Theme + Local Chat)
==================================================================

Drop-in Flask UI for the KUKANILEA core.

Key features:
- Queue overview (no Jinja crashes even if fields missing)
- Review Split-View: PDF/preview LEFT, wizard RIGHT
- Dark/Light mode + Accent color (stored in localStorage)
- Upload -> background analyze -> auto-open review when READY
- Re-Extract creates new token and redirects
- Optional Tasks tab (if core exposes task_* functions)
- Local Chat tab:
    - deterministic agent-orchestrator without external LLM

Run:
  source .venv/bin/activate
  PORT=5051 KUKANILEA_SECRET="change-me" python3 kukanilea_upload_v3_ui.py

Notes:
- This UI expects a local `kukanilea_core*.py` next to it.
- OCR depends on system binaries (e.g. tesseract) + python deps.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import importlib
import importlib.util
import ipaddress
import json
import os
import re
import secrets
import sqlite3
import time
import urllib.parse
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, List, Tuple

from flask import (
    Blueprint,
    abort,
    current_app,
    flash,
    g,
    jsonify,
    redirect,
    render_template,
    render_template_string,
    request,
    send_file,
    session,
    url_for,
)

from app.agents.orchestrator import answer as agent_answer
from app.agents.retrieval_fts import enqueue as rag_enqueue
from app.agents.retrieval_fts import upsert_external_fact
from app.ai.knowledge import store_entity
from app.ai.memory import add_feedback as ai_add_feedback
from app.ai.ollama_client import ollama_is_available, ollama_list_models
from app.ai.orchestrator import process_message as ai_process_message
from app.ai.predictions import daily_report, predict_budget
from app.automation import (
    automation_rule_create,
    automation_rule_disable,
    automation_rule_get,
    automation_rule_list,
    automation_rule_toggle,
    automation_run_now,
    builder_execute_action,
    builder_execution_log_list,
    builder_pending_action_confirm_once,
    builder_pending_action_list,
    builder_pending_action_set_status,
    builder_rule_create,
    builder_rule_get,
    builder_rule_list,
    builder_rule_update,
    get_or_build_daily_insights,
    process_cron_for_tenant,
    process_events_for_tenant,
    simulate_rule_for_tenant,
)
from app.automation.cron import parse_cron_expression
from app.autonomy import (
    autotag_rule_create,
    autotag_rule_delete,
    autotag_rule_toggle,
    autotag_rules_list,
    get_health_overview,
    rotate_logs,
    run_backup,
    run_smoke_test,
)
from app.demo_data import generate_demo_data
from app.entity_links import (
    create_link as entity_link_create,
)
from app.entity_links import (
    delete_link as entity_link_delete,
)
from app.entity_links import (
    list_links_for_entity,
)
from app.entity_links.display import entity_display_title
from app.event_id_map import entity_id_int
from app.eventlog.core import event_append
from app.knowledge import (
    knowledge_email_ingest_eml,
    knowledge_email_sources_list,
    knowledge_ics_ingest,
    knowledge_ics_sources_list,
    knowledge_note_create,
    knowledge_note_delete,
    knowledge_note_update,
    knowledge_notes_list,
    knowledge_policy_get,
    knowledge_policy_update,
    knowledge_search,
)
from app.lead_intake import (
    appointment_request_to_ics,
    appointment_requests_create,
    appointment_requests_update_status,
    call_logs_create,
    lead_claim,
    lead_claim_get,
    lead_claims_auto_expire,
    lead_claims_for_leads,
    lead_convert_to_deal_quote,
    lead_release_claim,
    lead_timeline,
    leads_add_note,
    leads_assign,
    leads_block_sender,
    leads_create,
    leads_get,
    leads_inbox_counts,
    leads_list,
    leads_screen_accept,
    leads_screen_ignore,
    leads_set_priority,
    leads_update_status,
)
from app.lead_intake.core import ConflictError
from app.lead_intake.guard import require_lead_access
from app.mail import (
    ensure_postfach_schema,
    postfach_build_authorization_url,
    postfach_clear_oauth_token,
    postfach_create_account,
    postfach_create_draft,
    postfach_create_followup_task,
    postfach_email_encryption_ready,
    postfach_exchange_code_for_tokens,
    postfach_extract_intake,
    postfach_extract_structured,
    postfach_generate_oauth_state,
    postfach_generate_pkce_pair,
    postfach_get_account,
    postfach_get_draft,
    postfach_get_oauth_token,
    postfach_get_thread,
    postfach_link_entities,
    postfach_list_accounts,
    postfach_list_drafts_for_thread,
    postfach_list_threads,
    postfach_oauth_provider_config,
    postfach_safety_check_draft,
    postfach_save_oauth_token,
    postfach_send_draft,
    postfach_set_account_oauth_state,
    postfach_sync_account,
)
from app.omni import get_event as omni_get_event
from app.omni import list_events as omni_list_events
from app.security_ua_hash import ua_hmac_sha256_hex
from app.tags import (
    tag_assign,
    tag_create,
    tag_delete,
    tag_list,
    tag_unassign,
    tag_update,
    tags_for_entities,
)
from app.workflows import (
    WORKFLOW_TEMPLATE_MARKER_PREFIX,
    get_workflow_template,
    list_workflow_templates,
    workflow_template_marker,
)
from kukanilea.agents import AgentContext, CustomerAgent, SearchAgent
from kukanilea.orchestrator import Orchestrator

from .auth import (
    current_role,
    current_tenant,
    current_user,
    hash_password,
    login_required,
    login_user,
    logout_user,
    require_role,
    verify_password,
)
from .config import Config
from .db import AuthDB
from .errors import json_error

weather_spec = importlib.util.find_spec("kukanilea_weather_plugin")
if weather_spec:
    _weather_mod = importlib.import_module("kukanilea_weather_plugin")
    get_weather = getattr(_weather_mod, "get_weather", None) or getattr(
        _weather_mod, "get_berlin_weather_now", None
    )
else:
    get_weather = None  # type: ignore

rapidfuzz_spec = importlib.util.find_spec("rapidfuzz")
if rapidfuzz_spec:
    fuzz = importlib.import_module("rapidfuzz").fuzz  # type: ignore
else:
    fuzz = None  # type: ignore

werkzeug_spec = importlib.util.find_spec("werkzeug.utils")
if werkzeug_spec:
    secure_filename = importlib.import_module("werkzeug.utils").secure_filename  # type: ignore
else:
    secure_filename = None  # type: ignore

# -------- Core import (robust) ----------
core = None
_core_import_errors = []
for mod in ("kukanilea_core_v3_fixed", "kukanilea_core_v3", "kukanilea_core"):
    try:
        core = __import__(mod)
        break
    except Exception as e:
        _core_import_errors.append(f"{mod}: {e}")

if core is None:
    raise RuntimeError(
        "KUKANILEA core import failed: " + " | ".join(_core_import_errors)
    )


def _core_get(name: str, default=None):
    return getattr(core, name, default)


# Paths/config from core
EINGANG: Path = _core_get("EINGANG")
BASE_PATH: Path = _core_get("BASE_PATH")
PENDING_DIR: Path = _core_get("PENDING_DIR")
DONE_DIR: Path = _core_get("DONE_DIR")
SUPPORTED_EXT = set(
    _core_get(
        "SUPPORTED_EXT",
        {".pdf", ".jpg", ".jpeg", ".png", ".tif", ".tiff", ".bmp", ".txt"},
    )
)

# Core functions (minimum)
analyze_to_pending = _core_get("analyze_to_pending") or _core_get(
    "start_background_analysis"
)
read_pending = _core_get("read_pending")
write_pending = _core_get("write_pending")
delete_pending = _core_get("delete_pending")
list_pending = _core_get("list_pending")
write_done = _core_get("write_done")
read_done = _core_get("read_done")
process_with_answers = _core_get("process_with_answers")
normalize_component = _core_get("normalize_component", lambda s: (s or "").strip())

# Optional helpers
db_init = _core_get("db_init")
assistant_search = _core_get("assistant_search")
audit_log = _core_get("audit_log")
db_latest_path_for_doc = _core_get("db_latest_path_for_doc")
db_path_for_doc = _core_get("db_path_for_doc")

# Optional tasks
task_list = _core_get("task_list")
task_create_fn = _core_get("task_create")
task_set_status_fn = _core_get("task_set_status")
task_resolve = _core_get("task_resolve")
task_dismiss = _core_get("task_dismiss")

# Optional time tracking
time_project_create = _core_get("time_project_create")
time_project_list = _core_get("time_project_list")
time_entry_start = _core_get("time_entry_start")
time_entry_stop = _core_get("time_entry_stop")
time_entry_list = _core_get("time_entries_list")
time_entry_update = _core_get("time_entry_update")
time_entry_approve = _core_get("time_entry_approve")
time_entries_export_csv = _core_get("time_entries_export_csv")
time_entries_summary_by_task = _core_get("time_entries_summary_by_task")
time_entries_summary_by_project = _core_get("time_entries_summary_by_project")

customers_create = _core_get("customers_create")
customers_get = _core_get("customers_get")
customers_list = _core_get("customers_list")
customers_update = _core_get("customers_update")
contacts_create = _core_get("contacts_create")
contacts_list_by_customer = _core_get("contacts_list_by_customer")
deals_create = _core_get("deals_create")
deals_update_stage = _core_get("deals_update_stage")
deals_list = _core_get("deals_list")
quotes_create_from_deal = _core_get("quotes_create_from_deal")
quotes_get = _core_get("quotes_get")
quotes_add_item = _core_get("quotes_add_item")
emails_import_eml = _core_get("emails_import_eml")

# Guard minimum contract
_missing = []
if EINGANG is None:
    _missing.append("EINGANG")
if BASE_PATH is None:
    _missing.append("BASE_PATH")
if PENDING_DIR is None:
    _missing.append("PENDING_DIR")
if DONE_DIR is None:
    _missing.append("DONE_DIR")
if not callable(analyze_to_pending):
    _missing.append("analyze_to_pending")
for fn in (
    read_pending,
    write_pending,
    delete_pending,
    list_pending,
    write_done,
    read_done,
    process_with_answers,
):
    if fn is None:
        _missing.append("core_fn_missing")
        break
if _missing:
    raise RuntimeError("Core contract incomplete: " + ", ".join(_missing))


# -------- Flask ----------
bp = Blueprint("web", __name__)
ORCHESTRATOR = None

# --- Early template defaults (avoid NameError during debug reload) ---
HTML_LOGIN = ""  # will be overwritten later by the full template block


def suggest_existing_folder(
    base_path: str, tenant: str, kdnr: str, name: str
) -> Tuple[str, float]:
    """Heuristic: find an existing customer folder for this tenant."""
    try:
        root = Path(base_path) / tenant
        if not root.exists():
            return "", 0.0
        k = (kdnr or "").strip()
        n = (name or "").strip().lower()
        candidates = []
        for p in root.glob("*"):
            if not p.is_dir():
                continue
            s = p.name.lower()
            if k and s.startswith(k.lower() + "_"):
                return str(p), 0.95
            if n and n in s:
                candidates.append((str(p), 0.7))
            if n and fuzz is not None:
                score = fuzz.partial_ratio(n, s) / 100.0
                if score >= 0.6:
                    candidates.append((str(p), score))
        if not candidates:
            return "", 0.0
        candidates.sort(key=lambda x: x[1], reverse=True)
        return candidates[0]
    except Exception:
        return "", 0.0


DOCTYPE_CHOICES = [
    "ANGEBOT",
    "RECHNUNG",
    "AUFTRAGSBESTAETIGUNG",
    "AW",
    "MAHNUNG",
    "NACHTRAG",
    "SONSTIGES",
    "FOTO",
    "H_RECHNUNG",
    "H_ANGEBOT",
]

ASSISTANT_HIDE_EINGANG = True


# -------- Helpers ----------
def _b64(s: str) -> str:
    return base64.urlsafe_b64encode((s or "").encode("utf-8")).decode("ascii")


def _unb64(s: str) -> str:
    return base64.urlsafe_b64decode((s or "").encode("ascii")).decode(
        "utf-8", errors="ignore"
    )


def _audit(action: str, target: str = "", meta: dict = None) -> None:
    if audit_log is None:
        return
    try:
        role = current_role()
        user = current_user() or ""
        audit_log(
            user=user,
            role=role,
            action=action,
            target=target,
            meta=meta or {},
            tenant_id=current_tenant(),
        )
    except Exception:
        pass


def _resolve_doc_path(token: str, pending: dict | None = None) -> Path | None:
    pending = pending or {}
    direct = Path(pending.get("path", "")) if pending.get("path") else None
    if direct and direct.exists():
        return direct
    doc_id = normalize_component(pending.get("doc_id") or token)
    tenant_id = (
        current_tenant() or pending.get("tenant") or pending.get("tenant_id") or ""
    )
    if doc_id:
        if callable(db_latest_path_for_doc):
            latest = db_latest_path_for_doc(doc_id, tenant_id=tenant_id)
            if latest and Path(latest).exists():
                return Path(latest)
        if callable(db_path_for_doc):
            fallback = db_path_for_doc(doc_id, tenant_id=tenant_id)
            if fallback and Path(fallback).exists():
                return Path(fallback)
    return None


def _allowlisted_dirs() -> List[Path]:
    base = Config.BASE_DIR
    instance_dir = base / "instance"
    core_db_dir = Path(getattr(core, "DB_PATH", instance_dir)).resolve().parent
    import_root = Path(str(Config.IMPORT_ROOT or "")).expanduser()
    allowlist = [instance_dir.resolve(), core_db_dir]
    if str(import_root):
        allowlist.append(import_root.resolve())
    return allowlist


def _is_allowlisted_path(path: Path) -> bool:
    try:
        resolved = path.resolve()
    except Exception:
        return False
    for allowed in _allowlisted_dirs():
        try:
            if resolved.is_relative_to(allowed):
                return True
        except AttributeError:
            if str(resolved).startswith(str(allowed)):
                return True
    return False


def _list_allowlisted_db_files() -> List[Path]:
    files: List[Path] = []
    for folder in _allowlisted_dirs():
        if not folder.exists():
            continue
        for fp in folder.glob("*.db"):
            files.append(fp)
        for fp in folder.glob("*.sqlite3"):
            files.append(fp)
    return sorted({f.resolve() for f in files})


def _list_allowlisted_base_paths() -> List[Path]:
    candidates = {BASE_PATH.resolve()}
    base_dir = Config.BASE_DIR.resolve()
    data_dir = base_dir / "data"
    if data_dir.exists():
        candidates.add(data_dir.resolve())
    return sorted(candidates)


def _is_storage_path_valid(path: Path) -> bool:
    try:
        resolved = path.expanduser().resolve()
    except Exception:
        return False
    return resolved.exists() and resolved.is_dir()


def _seed_dev_users(auth_db: AuthDB) -> str:
    now = datetime.utcnow().isoformat()
    auth_db.upsert_tenant("KUKANILEA", "KUKANILEA", now)
    auth_db.upsert_tenant("KUKANILEA Dev", "KUKANILEA Dev", now)
    auth_db.upsert_user("admin", hash_password("admin"), now)
    auth_db.upsert_user("dev", hash_password("dev"), now)
    auth_db.upsert_membership("admin", "KUKANILEA", "ADMIN", now)
    auth_db.upsert_membership("dev", "KUKANILEA Dev", "DEV", now)
    office_email = "theosmi33@gmail.com"
    office_info = "office user unchanged"
    if auth_db.get_user_by_email(office_email) is None:
        office_password = secrets.token_urlsafe(12)
        office_username = "office"
        if auth_db.get_user(office_username) is not None:
            office_username = f"office_{secrets.randbelow(1000)}"
        auth_db.create_user(
            username=office_username,
            password_hash=hash_password(office_password),
            created_at=now,
            email=office_email,
            email_verified=1,
        )
        auth_db.upsert_membership(office_username, "KUKANILEA Dev", "OPERATOR", now)
        office_info = f"office password: {office_password}"
    return f"Seeded users: admin/admin, dev/dev, {office_info}"


def _now_iso() -> str:
    return datetime.utcnow().isoformat(timespec="seconds")


def _normalize_email(value: str) -> str:
    return (value or "").strip().lower()


def _redact_email(value: str) -> str:
    email = _normalize_email(value)
    if "@" not in email:
        return "***"
    local, domain = email.split("@", 1)
    if not local:
        return f"***@{domain}"
    keep = local[:1]
    return f"{keep}***@{domain}"


def _hash_code(value: str) -> str:
    return hashlib.sha256((value or "").encode("utf-8")).hexdigest()


def _generate_numeric_code(length: int = 6) -> str:
    width = max(4, int(length or 6))
    upper = 10**width
    return str(secrets.randbelow(upper)).zfill(width)


def _safe_filename(name: str) -> str:
    raw = (name or "").strip().replace("\\", "_").replace("/", "_")
    if secure_filename is not None:
        out = secure_filename(raw)
        return out or "upload"
    raw = re.sub(r"[^a-zA-Z0-9._-]+", "_", raw).strip("._-")
    return raw or "upload"


def _is_allowed_ext(filename: str) -> bool:
    try:
        return Path(filename).suffix.lower() in SUPPORTED_EXT
    except Exception:
        return False


def _allowed_roots() -> List[Path]:
    return [
        EINGANG.resolve(),
        BASE_PATH.resolve(),
        PENDING_DIR.resolve(),
        DONE_DIR.resolve(),
    ]


def _is_allowed_path(fp: Path) -> bool:
    try:
        rp = fp.resolve()
        for root in _allowed_roots():
            if rp == root or str(rp).startswith(str(root) + os.sep):
                return True
        return False
    except Exception:
        return False


def _norm_tenant(t: str) -> str:
    t = normalize_component(t or "").lower().replace(" ", "_")
    t = re.sub(r"[^a-z0-9_\-]+", "", t)
    return t[:40]


def _wizard_get(p: dict) -> dict:
    w = p.get("wizard") or {}
    w.setdefault("tenant", "")
    w.setdefault("kdnr", "")
    w.setdefault("use_existing", "")
    w.setdefault("name", "")
    w.setdefault("addr", "")
    w.setdefault("plzort", "")
    w.setdefault("doctype", "")
    w.setdefault("document_date", "")
    return w


def _wizard_save(token: str, p: dict, w: dict) -> None:
    p["wizard"] = w
    write_pending(token, p)


def _rag_enqueue(kind: str, pk: int, op: str) -> None:
    try:
        rag_enqueue(kind, int(pk), op)
    except Exception:
        pass


def _card(kind: str, msg: str) -> str:
    styles = {
        "error": "border-red-500/40 bg-red-500/10",
        "warn": "border-amber-500/40 bg-amber-500/10",
        "info": "border-slate-700 bg-slate-950/40",
    }
    s = styles.get(kind, styles["info"])
    return f'<div class="rounded-xl border {s} p-3 text-sm">{msg}</div>'


def _render_base(content: str, active_tab: str = "upload") -> str:
    profile = _get_profile()
    return render_template_string(
        HTML_BASE,
        content=content,
        ablage=str(BASE_PATH),
        user=current_user() or "-",
        roles=current_role(),
        tenant=current_tenant() or "-",
        profile=profile,
        active_tab=active_tab,
    )


def _get_profile() -> dict:
    if callable(getattr(core, "get_profile", None)):
        return core.get_profile()
    return {
        "name": "default",
        "db_path": str(getattr(core, "DB_PATH", "")),
        "base_path": str(BASE_PATH),
    }


def _parse_date(value: str) -> datetime.date:
    try:
        return datetime.strptime(value, "%Y-%m-%d").date()
    except Exception:
        return datetime.now().date()


def _time_range_params(range_name: str, date_value: str) -> tuple[str, str]:
    base_date = _parse_date(date_value)
    if range_name == "day":
        start_date = base_date
        end_date = base_date
    else:
        start_date = base_date - timedelta(days=base_date.weekday())
        end_date = start_date + timedelta(days=6)
    start_at = f"{start_date.isoformat()}T00:00:00"
    end_at = f"{end_date.isoformat()}T23:59:59"
    return start_at, end_at


def _clamp_page_size(raw: str | None, *, default: int = 25, max_size: int = 100) -> int:
    try:
        size = int(raw or default)
    except Exception:
        size = default
    return max(1, min(size, max_size))


def _clamp_page(raw: str | None, *, default: int = 1) -> int:
    try:
        page = int(raw or default)
    except Exception:
        page = default
    return max(1, page)


def _format_cents(value: int | None, currency: str = "EUR") -> str:
    cents = int(value or 0)
    sign = "-" if cents < 0 else ""
    cents_abs = abs(cents)
    amount = f"{cents_abs // 100}.{cents_abs % 100:02d}"
    symbol = (
        "€" if (currency or "EUR").upper() == "EUR" else (currency or "EUR").upper()
    )
    return f"{sign}{symbol}{amount}"


def _is_htmx() -> bool:
    return bool(request.headers.get("HX-Request"))


def _ensure_csrf_token() -> str:
    token = str(session.get("csrf_token") or "").strip()
    if token:
        return token
    token = secrets.token_urlsafe(24)
    session["csrf_token"] = token
    return token


@bp.app_context_processor
def _inject_csrf_token() -> dict[str, Any]:
    return {"csrf_token": _ensure_csrf_token()}


def _csrf_error_response(api: bool = True):
    rid = getattr(g, "request_id", "")
    if api:
        return (
            jsonify({"ok": False, "error_code": "csrf_invalid", "request_id": rid}),
            403,
        )
    return (
        render_template(
            "lead_intake/partials/_error.html",
            message="CSRF-Validierung fehlgeschlagen.",
            request_id=rid,
        ),
        403,
    )


def _csrf_guard(api: bool = True):
    if request.method != "POST":
        return None
    # JSON API endpoints are protected via auth/session gates; CSRF is enforced
    # for browser form submissions that mutate state.
    if request.is_json:
        return None
    expected = _ensure_csrf_token()
    provided = str(request.form.get("csrf_token") or "").strip()
    if not expected or not provided or not hmac.compare_digest(expected, provided):
        return _csrf_error_response(api=api)
    return None


def _core_db_path() -> Path:
    return Path(str(getattr(core, "DB_PATH")))


def _ensure_postfach_tables() -> None:
    ensure_postfach_schema(_core_db_path())


def _crm_db_rows(sql: str, params: tuple[Any, ...]) -> list[dict[str, Any]]:
    con = sqlite3.connect(str(getattr(core, "DB_PATH")))
    con.row_factory = sqlite3.Row
    try:
        rows = con.execute(sql, params).fetchall()
        return [dict(r) for r in rows]
    finally:
        con.close()


def _crm_customer_get(tenant_id: str, customer_id: str) -> dict[str, Any] | None:
    rows = _crm_db_rows(
        """
        SELECT id, tenant_id, name, vat_id, notes, created_at, updated_at
        FROM customers
        WHERE tenant_id=? AND id=?
        LIMIT 1
        """,
        (tenant_id, customer_id),
    )
    return rows[0] if rows else None


def _crm_deals_list(
    tenant_id: str,
    *,
    stage: str | None = None,
    query: str | None = None,
    customer_id: str | None = None,
) -> list[dict[str, Any]]:
    clauses = ["d.tenant_id=?"]
    params: list[Any] = [tenant_id]
    if stage:
        clauses.append("LOWER(d.stage)=LOWER(?)")
        params.append(stage)
    if customer_id:
        clauses.append("d.customer_id=?")
        params.append(customer_id)
    q = (query or "").strip()
    if q:
        clauses.append(
            "(LOWER(d.title) LIKE LOWER(?) OR LOWER(COALESCE(c.name,'')) LIKE LOWER(?))"
        )
        params.extend([f"%{q}%", f"%{q}%"])
    where_sql = " AND ".join(clauses)
    rows = _crm_db_rows(
        f"""
        SELECT d.id, d.customer_id, d.title, d.stage, d.value_cents, d.currency,
               d.probability, d.expected_close_date, d.updated_at,
               c.name AS customer_name
        FROM deals d
        LEFT JOIN customers c ON c.id=d.customer_id AND c.tenant_id=d.tenant_id
        WHERE {where_sql}
        ORDER BY d.updated_at DESC, d.id DESC
        """,
        tuple(params),
    )
    for row in rows:
        row["value_text"] = _format_cents(
            row.get("value_cents"), row.get("currency") or "EUR"
        )
    return rows


def _crm_quotes_list(
    tenant_id: str,
    *,
    status: str | None = None,
    query: str | None = None,
    customer_id: str | None = None,
    page: int = 1,
    page_size: int = 25,
) -> tuple[list[dict[str, Any]], int]:
    clauses = ["q.tenant_id=?"]
    params: list[Any] = [tenant_id]
    if status:
        clauses.append("LOWER(q.status)=LOWER(?)")
        params.append(status)
    if customer_id:
        clauses.append("q.customer_id=?")
        params.append(customer_id)
    qtext = (query or "").strip()
    if qtext:
        clauses.append(
            "(LOWER(COALESCE(q.quote_number,'')) LIKE LOWER(?) OR LOWER(COALESCE(c.name,'')) LIKE LOWER(?))"
        )
        params.extend([f"%{qtext}%", f"%{qtext}%"])
    where_sql = " AND ".join(clauses)
    count_rows = _crm_db_rows(
        f"SELECT COUNT(*) AS c FROM quotes q LEFT JOIN customers c ON c.id=q.customer_id AND c.tenant_id=q.tenant_id WHERE {where_sql}",
        tuple(params),
    )
    total = int((count_rows[0].get("c") if count_rows else 0) or 0)
    offset = (page - 1) * page_size
    rows = _crm_db_rows(
        f"""
        SELECT q.id, q.quote_number, q.customer_id, q.deal_id, q.status, q.currency,
               q.subtotal_cents, q.tax_amount_cents, q.total_cents, q.created_at, q.updated_at,
               c.name AS customer_name
        FROM quotes q
        LEFT JOIN customers c ON c.id=q.customer_id AND c.tenant_id=q.tenant_id
        WHERE {where_sql}
        ORDER BY q.created_at DESC, q.id DESC
        LIMIT ? OFFSET ?
        """,
        tuple(params + [page_size, offset]),
    )
    for row in rows:
        row["total_text"] = _format_cents(
            row.get("total_cents"), row.get("currency") or "EUR"
        )
    return rows, total


def _crm_emails_list(
    tenant_id: str,
    *,
    customer_id: str | None = None,
    page: int = 1,
    page_size: int = 25,
) -> tuple[list[dict[str, Any]], int]:
    clauses = ["tenant_id=?"]
    params: list[Any] = [tenant_id]
    if customer_id:
        clauses.append("customer_id=?")
        params.append(customer_id)
    where_sql = " AND ".join(clauses)
    count_rows = _crm_db_rows(
        f"SELECT COUNT(*) AS c FROM emails_cache WHERE {where_sql}",
        tuple(params),
    )
    total = int((count_rows[0].get("c") if count_rows else 0) or 0)
    offset = (page - 1) * page_size
    rows = _crm_db_rows(
        f"""
        SELECT id, customer_id, contact_id, from_addr, to_addrs, subject, received_at,
               SUBSTR(COALESCE(body_text,''),1,160) AS body_preview,
               created_at
        FROM emails_cache
        WHERE {where_sql}
        ORDER BY received_at DESC, created_at DESC, id DESC
        LIMIT ? OFFSET ?
        """,
        tuple(params + [page_size, offset]),
    )
    return rows, total


def _crm_contacts_list(tenant_id: str, customer_id: str) -> list[dict[str, Any]]:
    if callable(contacts_list_by_customer):
        try:
            return contacts_list_by_customer(tenant_id, customer_id)  # type: ignore
        except Exception:
            return []
    return []


# -------- UI Templates ----------
HTML_BASE = r"""<!doctype html>
<html lang="de">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<link rel="manifest" href="/app.webmanifest">
<title>KUKANILEA Systems</title>
<script src="https://cdn.tailwindcss.com"></script>
<script>
  const savedTheme = localStorage.getItem("ks_theme") || "dark";
  const savedAccent = localStorage.getItem("ks_accent") || "indigo";
  if(savedTheme === "light"){ document.documentElement.classList.add("light"); }
  document.documentElement.dataset.accent = savedAccent;
</script>
<style>
  :root{
    --bg:#0f172a;
    --bg-elev:#111827;
    --bg-panel:#172033;
    --border:rgba(148,163,184,.2);
    --text:#e5e7eb;
    --muted:#94a3b8;
    --accent-500:#0ea5e9;
    --accent-600:#0284c7;
    --danger-500:#dc2626;
    --danger-600:#b91c1c;
    --warn-bg:rgba(245,158,11,.12);
    --warn-border:rgba(245,158,11,.35);
    --info-bg:rgba(14,165,233,.12);
    --info-border:rgba(14,165,233,.35);
    --error-bg:rgba(220,38,38,.12);
    --error-border:rgba(220,38,38,.35);
    --radius-lg:18px;
    --radius-md:14px;
    --radius-sm:10px;
    --shadow:0 8px 30px rgba(15,23,42,.35);
    --shadow-soft:0 4px 16px rgba(15,23,42,.2);
  }
  html[data-accent="indigo"]{ --accent-500:#0ea5e9; --accent-600:#0284c7; }
  html[data-accent="emerald"]{ --accent-500:#10b981; --accent-600:#059669; }
  html[data-accent="amber"]{ --accent-500:#f59e0b; --accent-600:#d97706; }
  .light body{
    --bg:#f8fafc;
    --bg-elev:#ffffff;
    --bg-panel:#ffffff;
    --border:rgba(71,85,105,.22);
    --text:#0f172a;
    --muted:#475569;
    --shadow:0 8px 30px rgba(15,23,42,.12);
    --shadow-soft:0 4px 16px rgba(15,23,42,.08);
  }
  *{ box-sizing:border-box; }
  body{ margin:0; background:var(--bg); color:var(--text); }
  .app-shell{ display:flex; min-height:100vh; }
  .app-nav{
    width:240px; background:var(--bg-elev); border-right:1px solid var(--border);
    padding:24px 18px; position:sticky; top:0; height:100vh;
  }
  .app-nav .brand-mark{
    height:40px; width:40px; border-radius:16px; display:flex; align-items:center; justify-content:center;
    background:color-mix(in srgb, var(--accent-500) 24%, transparent);
    color:#fff;
  }
  .app-main{ flex:1; display:flex; flex-direction:column; }
  .app-topbar{
    display:flex; justify-content:space-between; align-items:flex-start;
    padding:22px 28px; border-bottom:1px solid var(--border); background:var(--bg-elev);
    gap:16px;
  }
  .topbar-primary{ display:flex; align-items:center; gap:10px; }
  .topbar-actions{ display:flex; align-items:center; gap:8px; flex-wrap:wrap; justify-content:flex-end; }
  .mobile-nav-btn{ display:none; width:36px; height:36px; border-radius:10px; }
  .app-content{ padding:24px 28px; }
  .app-overlay{
    display:none;
    position:fixed;
    inset:0;
    background:rgba(15,23,42,.55);
    z-index:40;
  }
  .app-overlay.open{ display:block; }
  .nav-link{
    display:flex; gap:12px; align-items:center; padding:10px 12px; border-radius:12px;
    color:var(--muted); text-decoration:none; transition:all .15s ease;
  }
  .nav-link:hover{ background:rgba(148,163,184,.08); color:var(--text); }
  .nav-link.active{
    background:color-mix(in srgb, var(--accent-500) 18%, transparent);
    color:var(--text);
    border:1px solid color-mix(in srgb, var(--accent-500) 42%, transparent);
  }
  .badge{
    font-size:11px; padding:3px 8px; border-radius:999px;
    border:1px solid var(--border); color:var(--muted); white-space:nowrap;
  }
  .card{ background:var(--bg-panel); border:1px solid var(--border); border-radius:var(--radius-lg); box-shadow:var(--shadow); }
  .btn{
    display:inline-flex; align-items:center; justify-content:center;
    text-decoration:none; border:1px solid transparent; border-radius:var(--radius-sm);
    transition:all .15s ease; cursor:pointer; line-height:1.2;
  }
  .btn:disabled{ opacity:.55; cursor:not-allowed; }
  .btn-primary{ background:var(--accent-600); color:white; border-color:var(--accent-600); }
  .btn-primary:hover{ filter:brightness(1.04); }
  .btn-outline{ border-color:var(--border); color:var(--text); background:transparent; }
  .btn-outline:hover{ background:rgba(148,163,184,.1); }
  .btn-danger{ background:var(--danger-600); color:white; border-color:var(--danger-600); }
  .input{
    background:transparent; border:1px solid var(--border);
    border-radius:var(--radius-sm); color:var(--text);
  }
  .label{ display:block; font-size:12px; margin-bottom:4px; color:var(--muted); }
  .muted{ color:var(--muted); }
  .pill{
    background:color-mix(in srgb, var(--accent-500) 15%, transparent);
    color:var(--text); border:1px solid color-mix(in srgb, var(--accent-500) 24%, transparent);
    padding:2px 8px; border-radius:999px; font-size:11px;
  }
  .alert{ border:1px solid var(--border); border-radius:12px; padding:12px; font-size:14px; }
  .alert-info{ background:var(--info-bg); border-color:var(--info-border); }
  .alert-warn{ background:var(--warn-bg); border-color:var(--warn-border); }
  .alert-error{ background:var(--error-bg); border-color:var(--error-border); }
  .table-shell{ border:1px solid var(--border); border-radius:14px; overflow:hidden; }
  .table-head{ border-bottom:1px solid var(--border); }
  .table-row{ border-bottom:1px solid color-mix(in srgb, var(--border) 75%, transparent); }
  .chat-fab{ background:var(--accent-600); box-shadow:var(--shadow-soft); color:white; }
  .chat-drawer{ background:var(--bg-elev); border-color:var(--border); box-shadow:var(--shadow); }
  .chat-section{ border-color:var(--border); }
  .chat-messages{ height:calc(100vh - 230px); }
  @media (max-width: 1120px){
    .mobile-nav-btn{ display:inline-flex; }
    .app-nav{
      position:fixed; top:0; left:0; z-index:50; transform:translateX(-102%);
      transition:transform .2s ease; height:100vh; box-shadow:var(--shadow-soft);
    }
    .app-nav.open{ transform:translateX(0); }
    .app-topbar{
      padding:14px 16px; position:sticky; top:0; z-index:20; backdrop-filter:blur(6px);
    }
    .app-content{ padding:16px; }
  }
</style>
</head>
<body>
<div class="app-shell">
  <div id="appNavOverlay" class="app-overlay"></div>
  <aside id="appNav" class="app-nav">
    <div class="flex items-center gap-2 mb-6">
      <div class="brand-mark">✦</div>
      <div>
        <div class="text-sm font-semibold">KUKANILEA</div>
        <div class="text-[11px] muted">Agent Orchestra</div>
      </div>
    </div>
    <nav class="space-y-2">
      <a class="nav-link {{'active' if active_tab=='upload' else ''}}" href="/">📥 Upload</a>
      <a class="nav-link {{'active' if active_tab=='tasks' else ''}}" href="/tasks">✅ Tasks</a>
      <a class="nav-link {{'active' if active_tab=='time' else ''}}" href="/time">⏱️ Time</a>
      <a class="nav-link {{'active' if active_tab=='assistant' else ''}}" href="/assistant">🧠 Assistant</a>
      <a class="nav-link {{'active' if active_tab=='chat' else ''}}" href="/chat">💬 Chat</a>
      <a class="nav-link {{'active' if active_tab=='postfach' else ''}}" href="/postfach">📨 Postfach</a>
      <a class="nav-link {{'active' if active_tab=='crm' else ''}}" href="/crm/customers">📈 CRM</a>
      <a class="nav-link {{'active' if active_tab=='leads' else ''}}" href="/leads/inbox">📬 Leads</a>
      <a class="nav-link {{'active' if active_tab=='knowledge' else ''}}" href="/knowledge">📚 Knowledge</a>
      <a class="nav-link {{'active' if active_tab=='conversations' else ''}}" href="/conversations">🧾 Conversations</a>
      <a class="nav-link {{'active' if active_tab=='workflows' else ''}}" href="/workflows">🧭 Workflows</a>
      <a class="nav-link {{'active' if active_tab=='automation' else ''}}" href="/automation">⚙️ Automation</a>
      <a class="nav-link {{'active' if active_tab=='autonomy' else ''}}" href="/autonomy/health">🩺 Autonomy Health</a>
      <a class="nav-link {{'active' if active_tab=='insights' else ''}}" href="/insights/daily">📊 Insights</a>
      {% if roles in ['DEV', 'ADMIN'] %}
      <a class="nav-link {{'active' if active_tab=='settings' else ''}}" href="/settings">🛠️ Settings</a>
      {% endif %}
    </nav>
    <div class="mt-8 text-xs muted">
      Ablage: {{ablage}}
    </div>
  </aside>
  <main class="app-main">
    <div class="app-topbar">
      <div class="topbar-primary">
        <button id="navToggle" class="btn btn-outline mobile-nav-btn px-2 py-2" type="button" aria-label="Navigation öffnen">☰</button>
        <div>
        <div class="text-lg font-semibold">Workspace</div>
        <div class="text-xs muted">Upload → Review → Ablage</div>
        </div>
      </div>
      <div class="topbar-actions">
        <span class="badge">User: {{user}}</span>
        <span class="badge">Role: {{roles}}</span>
        <span class="badge">Tenant: {{tenant}}</span>
        <span class="badge">Profile: {{ profile.name }}</span>
        <span class="badge">Live: <span id="healthLive">...</span></span>
        <span class="badge">Ready: <span id="healthReady">...</span></span>
        {% if user and user != '-' %}
        <a class="btn btn-outline px-3 py-2 text-sm" href="/logout">Logout</a>
        {% endif %}
        <button id="accentBtn" class="btn btn-outline px-3 py-2 text-sm">Accent: <span id="accentLabel"></span></button>
        <button id="themeBtn" class="btn btn-outline px-3 py-2 text-sm">Theme: <span id="themeLabel"></span></button>
      </div>
    </div>
    <div class="app-content">
      {% if read_only %}
      <div class="mb-4 alert alert-error">
        Read-only mode aktiv ({{license_reason}}). Schreibaktionen sind deaktiviert.
      </div>
      {% elif trial_active and trial_days_left <= 3 %}
      <div class="mb-4 alert alert-warn">
        Trial aktiv: noch {{trial_days_left}} Tage.
      </div>
      {% endif %}
      {{ content|safe }}
    </div>
  </main>
</div>

<!-- Floating Chat Widget -->
<div id="chatWidgetBtn" title="Chat" class="fixed bottom-6 right-6 z-50 cursor-pointer select-none">
  <div class="chat-fab relative h-12 w-12 rounded-full flex items-center justify-center">
    💬
    <span id="chatUnread" class="absolute -top-1 -right-1 h-3 w-3 rounded-full bg-rose-500 hidden"></span>
  </div>
</div>

<div id="chatDrawer" class="chat-drawer fixed inset-y-0 right-0 z-50 hidden w-[420px] max-w-[92vw] border-l">
  <div class="chat-section flex items-center justify-between px-4 py-3 border-b">
    <div>
      <div class="text-sm font-semibold">KUKANILEA Assistant</div>
      <div class="text-xs muted">Tenant: {{tenant}}</div>
    </div>
    <div class="flex items-center gap-2">
      <span id="chatWidgetStatus" class="text-[11px] muted">Bereit</span>
      <button id="chatWidgetClose" class="rounded-lg px-2 py-1 text-sm btn-outline">✕</button>
    </div>
  </div>
  <div class="chat-section px-4 py-3 border-b">
    <div class="flex flex-wrap gap-2">
      <button class="chat-quick pill" data-q="suche rechnung">Suche Rechnung</button>
      <button class="chat-quick pill" data-q="suche angebot">Suche Angebot</button>
      <button class="chat-quick pill" data-q="zeige letzte uploads">Letzte Uploads</button>
      <button class="chat-quick pill" data-q="hilfe">Hilfe</button>
    </div>
  </div>
  <div id="chatWidgetMsgs" class="chat-messages flex-1 overflow-auto px-4 py-4 space-y-3 text-sm"></div>
  <div class="chat-section border-t px-4 py-3 space-y-2">
    <div class="flex gap-2">
      <input id="chatWidgetKdnr" class="w-24 rounded-xl input px-3 py-2 text-sm" placeholder="KDNR" />
      <input id="chatWidgetInput" class="flex-1 rounded-xl input px-3 py-2 text-sm" placeholder="Frag etwas…" />
      <button id="chatWidgetSend" class="rounded-xl px-3 py-2 text-sm btn-primary">Senden</button>
    </div>
    <div class="flex items-center justify-between">
      <button id="chatWidgetRetry" class="text-xs btn-outline px-3 py-1 hidden">Retry</button>
      <button id="chatWidgetClear" class="text-xs btn-outline px-3 py-1">Clear</button>
    </div>
  </div>
</div>

<script>
(function(){
  const btnTheme = document.getElementById("themeBtn");
  const lblTheme = document.getElementById("themeLabel");
  const btnAcc = document.getElementById("accentBtn");
  const lblAcc = document.getElementById("accentLabel");
  function curTheme(){ return (localStorage.getItem("ks_theme") || "dark"); }
  function curAccent(){ return (localStorage.getItem("ks_accent") || "indigo"); }
  function applyTheme(t){
    if(t === "light"){ document.documentElement.classList.add("light"); }
    else { document.documentElement.classList.remove("light"); }
    localStorage.setItem("ks_theme", t);
    lblTheme.textContent = t;
  }
  function applyAccent(a){
    document.documentElement.dataset.accent = a;
    localStorage.setItem("ks_accent", a);
    lblAcc.textContent = a;
  }
  applyTheme(curTheme());
  applyAccent(curAccent());
  btnTheme?.addEventListener("click", ()=>{ applyTheme(curTheme() === "dark" ? "light" : "dark"); });
  btnAcc?.addEventListener("click", ()=>{
    const order = ["indigo","emerald","amber"];
    const i = order.indexOf(curAccent());
    applyAccent(order[(i+1) % order.length]);
  });

  const nav = document.getElementById("appNav");
  const navToggle = document.getElementById("navToggle");
  const navOverlay = document.getElementById("appNavOverlay");
  function closeNav(){
    nav?.classList.remove("open");
    navOverlay?.classList.remove("open");
  }
  function toggleNav(){
    nav?.classList.toggle("open");
    navOverlay?.classList.toggle("open");
  }
  navToggle?.addEventListener("click", toggleNav);
  navOverlay?.addEventListener("click", closeNav);
})();
</script>

<script>
(function(){
  async function updateHealth(){
    try{
      const l = await fetch('/api/health/live', {headers:{'Accept':'application/json'}});
      document.getElementById('healthLive').textContent = l.ok ? 'OK' : 'DOWN';
    }catch(_){
      document.getElementById('healthLive').textContent = 'DOWN';
    }
    try{
      const r = await fetch('/api/health/ready', {headers:{'Accept':'application/json'}});
      document.getElementById('healthReady').textContent = r.ok ? 'OK' : 'NOT READY';
    }catch(_){
      document.getElementById('healthReady').textContent = 'NOT READY';
    }
  }
  updateHealth();
  setInterval(updateHealth, 30000);

  if ('serviceWorker' in navigator) {
    window.addEventListener('load', function(){
      navigator.serviceWorker.register('/sw.js').catch(function(){});
    });
  }
})();
</script>
</body>
</html>"""

# ------------------------------
# Login template
# ------------------------------
HTML_LOGIN = r"""
<div class="max-w-md mx-auto mt-10">
  <div class="card p-6">
    <h1 class="text-2xl font-bold mb-2">Login</h1>
    <p class="text-sm opacity-80 mb-4">Accounts: <b>admin</b>/<b>admin</b> (Tenant: KUKANILEA) • <b>dev</b>/<b>dev</b> (Tenant: KUKANILEA Dev)</p>
    {% if error %}<div class="alert alert-error mb-3">{{ error }}</div>{% endif %}
    <form method="post" class="space-y-3">
      <div>
        <label class="label">Username oder E-Mail</label>
        <input class="input w-full" name="username" autocomplete="username" required>
      </div>
      <div>
        <label class="label">Password</label>
        <input class="input w-full" type="password" name="password" autocomplete="current-password" required>
      </div>
      <button class="btn btn-primary w-full" type="submit">Login</button>
    </form>
    <div class="mt-4 text-sm flex items-center justify-between">
      <a class="underline" href="/register">Registrieren</a>
      <a class="underline" href="/forgot-password">Passwort vergessen?</a>
    </div>
  </div>
</div>
"""

HTML_REGISTER = r"""
<div class="max-w-md mx-auto mt-10">
  <div class="card p-6">
    <h1 class="text-2xl font-bold mb-2">Registrierung</h1>
    <p class="text-sm opacity-80 mb-4">Offline-Flow: Bestätigungscode wird lokal in der Outbox abgelegt.</p>
    {% if error %}<div class="rounded-xl border border-rose-500/40 bg-rose-500/10 p-3 text-sm mb-3">{{ error }}</div>{% endif %}
    {% if info %}<div class="rounded-xl border border-emerald-500/40 bg-emerald-500/10 p-3 text-sm mb-3">{{ info }}</div>{% endif %}
    <form method="post" class="space-y-3">
      <div>
        <label class="label">E-Mail</label>
        <input class="input w-full" name="email" type="email" autocomplete="email" required>
      </div>
      <div>
        <label class="label">Passwort</label>
        <input class="input w-full" name="password" type="password" autocomplete="new-password" required>
      </div>
      <div>
        <label class="label">Passwort bestätigen</label>
        <input class="input w-full" name="password_confirm" type="password" autocomplete="new-password" required>
      </div>
      <button class="btn btn-primary w-full" type="submit">Account erstellen</button>
    </form>
    <div class="mt-4 text-sm flex items-center justify-between">
      <a class="underline" href="/login">Zum Login</a>
      <a class="underline" href="/verify-email">Code bestätigen</a>
    </div>
  </div>
</div>
"""

HTML_VERIFY_EMAIL = r"""
<div class="max-w-md mx-auto mt-10">
  <div class="card p-6">
    <h1 class="text-2xl font-bold mb-2">E-Mail bestätigen</h1>
    <p class="text-sm opacity-80 mb-4">Gib die E-Mail und den 6-stelligen Code aus der lokalen Outbox ein.</p>
    {% if error %}<div class="rounded-xl border border-rose-500/40 bg-rose-500/10 p-3 text-sm mb-3">{{ error }}</div>{% endif %}
    {% if info %}<div class="rounded-xl border border-emerald-500/40 bg-emerald-500/10 p-3 text-sm mb-3">{{ info }}</div>{% endif %}
    <form method="post" class="space-y-3">
      <div>
        <label class="label">E-Mail</label>
        <input class="input w-full" name="email" type="email" autocomplete="email" required>
      </div>
      <div>
        <label class="label">Code</label>
        <input class="input w-full" name="code" inputmode="numeric" maxlength="12" required>
      </div>
      <button class="btn btn-primary w-full" type="submit">Bestätigen</button>
    </form>
    <div class="mt-4 text-sm flex items-center justify-between">
      <a class="underline" href="/register">Registrieren</a>
      <a class="underline" href="/login">Zum Login</a>
    </div>
  </div>
</div>
"""

HTML_FORGOT_PASSWORD = r"""
<div class="max-w-md mx-auto mt-10">
  <div class="card p-6">
    <h1 class="text-2xl font-bold mb-2">Passwort vergessen</h1>
    <p class="text-sm opacity-80 mb-4">Wir erzeugen lokal einen Reset-Code und legen ihn in der Outbox ab.</p>
    {% if error %}<div class="rounded-xl border border-rose-500/40 bg-rose-500/10 p-3 text-sm mb-3">{{ error }}</div>{% endif %}
    {% if info %}<div class="rounded-xl border border-emerald-500/40 bg-emerald-500/10 p-3 text-sm mb-3">{{ info }}</div>{% endif %}
    <form method="post" class="space-y-3">
      <div>
        <label class="label">E-Mail</label>
        <input class="input w-full" name="email" type="email" autocomplete="email" required>
      </div>
      <button class="btn btn-primary w-full" type="submit">Reset-Code erzeugen</button>
    </form>
    <div class="mt-4 text-sm flex items-center justify-between">
      <a class="underline" href="/reset-password">Reset ausführen</a>
      <a class="underline" href="/login">Zum Login</a>
    </div>
  </div>
</div>
"""

HTML_RESET_PASSWORD = r"""
<div class="max-w-md mx-auto mt-10">
  <div class="card p-6">
    <h1 class="text-2xl font-bold mb-2">Passwort zurücksetzen</h1>
    <p class="text-sm opacity-80 mb-4">Nutze E-Mail + Reset-Code aus der lokalen Outbox.</p>
    {% if error %}<div class="rounded-xl border border-rose-500/40 bg-rose-500/10 p-3 text-sm mb-3">{{ error }}</div>{% endif %}
    {% if info %}<div class="rounded-xl border border-emerald-500/40 bg-emerald-500/10 p-3 text-sm mb-3">{{ info }}</div>{% endif %}
    <form method="post" class="space-y-3">
      <div>
        <label class="label">E-Mail</label>
        <input class="input w-full" name="email" type="email" autocomplete="email" required>
      </div>
      <div>
        <label class="label">Reset-Code</label>
        <input class="input w-full" name="code" inputmode="numeric" maxlength="12" required>
      </div>
      <div>
        <label class="label">Neues Passwort</label>
        <input class="input w-full" name="password" type="password" autocomplete="new-password" required>
      </div>
      <div>
        <label class="label">Passwort bestätigen</label>
        <input class="input w-full" name="password_confirm" type="password" autocomplete="new-password" required>
      </div>
      <button class="btn btn-primary w-full" type="submit">Passwort ändern</button>
    </form>
    <div class="mt-4 text-sm flex items-center justify-between">
      <a class="underline" href="/forgot-password">Code erneut anfordern</a>
      <a class="underline" href="/login">Zum Login</a>
    </div>
  </div>
</div>
"""


HTML_INDEX = r"""<div class="grid lg:grid-cols-2 gap-6">
  <div class="rounded-2xl bg-slate-900/60 border border-slate-800 p-5 card">
    <div class="text-lg font-semibold mb-2">Datei hochladen</div>
    <div class="muted text-sm mb-4">Upload → Analyse → Review öffnet automatisch.</div>
    <form id="upform" class="space-y-3">
      <input id="file" name="file" type="file"
        class="block w-full text-sm input
        file:mr-4 file:rounded-xl file:border-0 file:bg-slate-700 file:px-4 file:py-2
        file:text-sm file:font-semibold file:text-white hover:file:bg-slate-600" />
      <button id="btn" type="submit" class="rounded-xl px-4 py-2 font-semibold btn-primary">Hochladen</button>
    </form>
    <div class="mt-4">
      <div class="text-xs muted mb-1" id="pLabel">0.0%</div>
      <div class="w-full bg-slate-800 rounded-full h-3 overflow-hidden"><div id="bar" class="h-3 w-0" style="background:var(--accent-500)"></div></div>
      <div class="text-slate-300 text-sm mt-3" id="status"></div>
      <div class="muted text-xs mt-1" id="phase"></div>
    </div>
  </div>
  <div class="rounded-2xl bg-slate-900/60 border border-slate-800 p-5 card">
    <div class="text-lg font-semibold mb-2">Review Queue</div>
    {% if items %}
      <div class="space-y-2">
        {% for it in items %}
          <div class="rounded-xl border border-slate-800 hover:border-slate-600 px-3 py-2">
            <div class="flex items-center justify-between gap-2">
              <a class="text-sm font-semibold underline accentText" href="/review/{{it}}/kdnr">Review öffnen</a>
              <div class="muted text-xs">{{ (meta.get(it, {}).get('progress', 0.0) or 0.0) | round(1) }}%</div>
            </div>
            <div class="muted text-xs break-all">{{ meta.get(it, {}).get('filename','') }}</div>
            <div class="muted text-[11px]">{{ meta.get(it, {}).get('progress_phase','') }}</div>
            <div class="mt-2 flex gap-2">
              <a class="rounded-xl px-3 py-2 text-xs btn-outline card" href="/file/{{it}}" target="_blank">Datei</a>
              <form method="post" action="/review/{{it}}/delete" onsubmit="return confirm('Pending wirklich löschen?')" style="display:inline;">
                <button class="rounded-xl px-3 py-2 text-xs btn-outline card" type="submit">Delete</button>
              </form>
            </div>
          </div>
        {% endfor %}
      </div>
    {% else %}
      <div class="muted text-sm">Keine offenen Reviews.</div>
    {% endif %}
  </div>
</div>
<script>
const form = document.getElementById("upform");
const fileInput = document.getElementById("file");
const bar = document.getElementById("bar");
const pLabel = document.getElementById("pLabel");
const status = document.getElementById("status");
const phase = document.getElementById("phase");
function setProgress(p){
  const pct = Math.max(0, Math.min(100, p));
  bar.style.width = pct + "%";
  pLabel.textContent = pct.toFixed(1) + "%";
}
async function poll(token){
  const res = await fetch("/api/progress/" + token, {cache:"no-store", credentials:"same-origin"});
  const j = await res.json();
  setProgress(j.progress || 0);
  phase.textContent = j.progress_phase || "";
  if(j.status === "READY"){ status.textContent = "Analyse fertig. Review öffnet…"; setTimeout(()=>{ window.location.href = "/review/" + token + "/kdnr"; }, 120); return; }
  if(j.status === "ERROR"){ status.textContent = "Analyse-Fehler: " + (j.error || "unbekannt"); return; }
  setTimeout(()=>poll(token), 450);
}
form.addEventListener("submit", (e) => {
  e.preventDefault();
  const f = fileInput.files[0];
  if(!f){ status.textContent = "Bitte eine Datei auswählen."; return; }
  const fd = new FormData();
  fd.append("file", f);
  const xhr = new XMLHttpRequest();
  xhr.open("POST", "/upload", true);
  xhr.upload.onprogress = (ev) => {
    if(ev.lengthComputable){ setProgress((ev.loaded / ev.total) * 35); phase.textContent = "Upload…"; }
  };
  xhr.onload = () => {
    if(xhr.status === 200){
      const resp = JSON.parse(xhr.responseText);
      status.textContent = "Upload OK. Analyse läuft…";
      poll(resp.token);
    } else {
      try{ const j = JSON.parse(xhr.responseText || "{}"); status.textContent = "Fehler beim Upload: " + (j.error || ("HTTP " + xhr.status)); }
      catch(e){ status.textContent = "Fehler beim Upload: HTTP " + xhr.status; }
    }
  };
  xhr.onerror = () => { status.textContent = "Upload fehlgeschlagen (Netzwerk/Server)."; };
  status.textContent = "Upload läuft…"; setProgress(0); phase.textContent = ""; xhr.send(fd);
});
</script>"""

HTML_REVIEW_SPLIT = r"""<div class="grid lg:grid-cols-2 gap-4">
  <div class="card p-4 sticky top-6 h-fit">
    <div class="flex items-center justify-between gap-2">
      <div>
        <div class="text-lg font-semibold">Dokument</div>
        <div class="muted text-xs break-all">{{filename}}</div>
      </div>
      <div class="flex items-center gap-2 text-xs">
        <a class="underline" href="/file/{{token}}" target="_blank">Download</a>
        <a class="underline muted" href="/">Home</a>
      </div>
    </div>
    <div class="mt-3 grid grid-cols-2 gap-2 text-xs">
      <div class="badge">KDNR: {{w.kdnr or '-'}}</div>
      <div class="badge">Typ: {{suggested_doctype}}</div>
      <div class="badge">Datum: {{suggested_date or '-'}}</div>
      <div class="badge">Confidence: {{confidence}}%</div>
    </div>
    <div class="mt-3 rounded-xl overflow-hidden border" style="border-color:var(--border); height:70vh;">
      {% if is_pdf %}
        <iframe src="/file/{{token}}#page=1" class="w-full h-full"></iframe>
      {% elif is_text %}
        <iframe src="/file/{{token}}" class="w-full h-full"></iframe>
      {% else %}
        <img src="/file/{{token}}" class="w-full h-full object-contain"/>
      {% endif %}
    </div>
    {% if preview %}
      <div class="mt-3">
        <div class="text-sm font-semibold mb-1">Preview (Auszug)</div>
        <pre class="text-xs whitespace-pre-wrap rounded-xl border p-3 max-h-48 overflow-auto" style="border-color:var(--border); background:rgba(15,23,42,.35);">{{preview}}</pre>
      </div>
    {% endif %}
  </div>
  <div class="card p-4">
    {{ right|safe }}
  </div>
</div>"""

HTML_WIZARD = r"""<form method="post" class="space-y-3" autocomplete="off">
  <div class="flex items-start justify-between gap-3">
    <div>
      <div class="text-lg font-semibold">Review</div>
      <div class="muted text-xs">Bearbeitung rechts, Preview links.</div>
    </div>
    <div class="flex gap-2">
      <button class="rounded-xl px-3 py-2 text-xs btn-outline card" name="reextract" value="1" type="submit">Re-Extract</button>
    </div>
  </div>
  {% if msg %}
    <div class="rounded-xl border border-amber-500/40 bg-amber-500/10 p-3 text-sm">{{msg}}</div>
  {% endif %}
  <div class="grid md:grid-cols-2 gap-3">
    <div>
      <label class="muted text-xs">Kundennr (KDNR)</label>
      <input class="w-full rounded-xl bg-slate-800 border border-slate-700 p-2 input" name="kdnr" value="{{w.kdnr}}" placeholder="z.B. 1234"/>
    </div>
  </div>
  <div class="grid md:grid-cols-2 gap-3">
    <div>
      <label class="muted text-xs">Dokumenttyp</label>
      <select class="w-full rounded-xl bg-slate-800 border border-slate-700 p-2 input" name="doctype">
        {% for d in doctypes %}
          <option value="{{d}}" {{'selected' if d==w.doctype else ''}}>{{d}}</option>
        {% endfor %}
      </select>
      <div class="muted text-[11px] mt-1">Vorschlag: {{suggested_doctype}}</div>
    </div>
    <div>
      <label class="muted text-xs">Dokumentdatum (optional)</label>
      <input class="w-full rounded-xl bg-slate-800 border border-slate-700 p-2 input" name="document_date" value="{{w.document_date}}" placeholder="YYYY-MM-DD oder leer"/>
      <div class="muted text-[11px] mt-1">Vorschlag: {{suggested_date or '-'}} </div>
    </div>
  </div>
  <div class="grid md:grid-cols-2 gap-3">
    <div>
      <label class="muted text-xs">Name</label>
      <input class="w-full rounded-xl bg-slate-800 border border-slate-700 p-2 input" name="name" value="{{w.name}}" placeholder="z.B. Gerd Warmbrunn"/>
    </div>
    <div>
      <label class="muted text-xs">Adresse</label>
      <input class="w-full rounded-xl bg-slate-800 border border-slate-700 p-2 input" name="addr" value="{{w.addr}}" placeholder="Straße + Nr"/>
    </div>
  </div>
  <div class="grid md:grid-cols-2 gap-3">
    <div>
      <label class="muted text-xs">PLZ Ort</label>
      <input class="w-full rounded-xl bg-slate-800 border border-slate-700 p-2 input" name="plzort" value="{{w.plzort}}" placeholder="z.B. 16341 Panketal"/>
    </div>
    <div>
      <label class="muted text-xs">Existing Folder (optional)</label>
      <input class="w-full rounded-xl bg-slate-800 border border-slate-700 p-2 input" name="use_existing" value="{{w.use_existing}}" placeholder="Pfad eines existierenden Objektordners"/>
      {% if existing_folder_hint %}
        <div class="muted text-[11px] mt-1">Meintest du: {{existing_folder_hint}} (Confidence {{existing_folder_score}})</div>
      {% endif %}
    </div>
  </div>
  <div class="pt-2 flex flex-wrap gap-2">
    <button class="rounded-xl px-4 py-2 font-semibold btn-primary" name="confirm" value="1" type="submit">Alles korrekt → Ablage</button>
    <a class="rounded-xl px-4 py-2 font-semibold btn-outline card" href="/">Zurück</a>
  </div>
  <div class="mt-3">
    <div class="text-sm font-semibold">Extrahierter Text</div>
    <div class="muted text-xs">Read-only. Re-Extract aktualisiert Vorschläge.</div>
    <textarea class="w-full text-xs rounded-xl border border-slate-800 p-3 bg-slate-950/40 input mt-2" style="height:260px" readonly>{{extracted_text}}</textarea>
  </div>
</form>"""

HTML_TIME = r"""<div class="grid gap-6 lg:grid-cols-3">
  <div class="lg:col-span-1 space-y-4">
    <div class="card p-4">
      <div class="text-lg font-semibold">Timer</div>
      <div class="muted text-sm">Starte und stoppe Zeiten pro Projekt.</div>
      <div class="mt-3 space-y-2">
        <label class="text-xs muted">Projekt</label>
        <select id="timeProject" class="w-full rounded-xl border px-3 py-2 text-sm bg-transparent"></select>
        <label class="text-xs muted">Task-ID (optional)</label>
        <input id="timeTaskId" class="w-full rounded-xl border px-3 py-2 text-sm bg-transparent" placeholder="z.B. 42" />
        <label class="text-xs muted">Notiz</label>
        <input id="timeNote" class="w-full rounded-xl border px-3 py-2 text-sm bg-transparent" placeholder="z.B. Baustelle Prüfen" />
        <div class="flex gap-2 pt-2">
          <button id="timeStart" class="px-4 py-2 text-sm btn-primary w-full">Start</button>
          <button id="timeStop" class="px-4 py-2 text-sm btn-outline w-full">Stop</button>
        </div>
        <div id="timeStatus" class="muted text-xs pt-2">Timer bereit.</div>
      </div>
    </div>
    <div class="card p-4">
      <div class="text-lg font-semibold">Projekt anlegen</div>
      <div class="mt-3 space-y-2">
        <input id="projectName" class="w-full rounded-xl border px-3 py-2 text-sm bg-transparent" placeholder="Projektname" />
        <textarea id="projectDesc" class="w-full rounded-xl border px-3 py-2 text-sm bg-transparent" rows="3" placeholder="Beschreibung (optional)"></textarea>
        <div class="grid grid-cols-2 gap-2">
          <input id="projectBudgetHours" type="number" min="0" class="w-full rounded-xl border px-3 py-2 text-sm bg-transparent" placeholder="Budget h" />
          <input id="projectBudgetCost" type="number" min="0" step="0.01" class="w-full rounded-xl border px-3 py-2 text-sm bg-transparent" placeholder="Budget €" />
        </div>
        <button id="projectCreate" class="px-4 py-2 text-sm btn-outline w-full">Anlegen</button>
        <div id="projectStatus" class="muted text-xs pt-1"></div>
      </div>
    </div>
    <div class="card p-4">
      <div class="text-lg font-semibold">Export</div>
      <div class="muted text-xs">CSV Export der aktuellen Woche.</div>
      <button id="exportWeek" class="mt-3 px-4 py-2 text-sm btn-outline w-full">CSV herunterladen</button>
    </div>
  </div>
  <div class="lg:col-span-2 space-y-4">
    <div class="card p-4">
      <div class="flex flex-col md:flex-row md:items-center md:justify-between gap-2">
        <div>
          <div class="text-lg font-semibold">Wochenübersicht</div>
          <div class="muted text-xs">Summen pro Tag, direkt prüfbar.</div>
        </div>
        <input id="weekDate" type="date" class="rounded-xl border px-3 py-2 text-sm bg-transparent" />
      </div>
      <div id="weekSummary" class="grid md:grid-cols-2 gap-3 mt-4"></div>
    </div>
    <div class="card p-4">
      <div class="text-lg font-semibold">Budget-Fortschritt</div>
      <div class="muted text-xs">Warnung ab 80% Verbrauch.</div>
      <div id="projectBudget" class="mt-3 text-sm muted">Kein Projekt ausgewählt.</div>
    </div>
    <div class="card p-4">
      <div class="text-lg font-semibold">Einträge</div>
      <div class="muted text-xs">Klick auf „Bearbeiten“ für Korrekturen.</div>
      <div id="entryList" class="mt-4 space-y-3"></div>
    </div>
  </div>
</div>
<script>
(function(){
  const role = "{{role}}";
  const timeProject = document.getElementById("timeProject");
  const timeNote = document.getElementById("timeNote");
  const timeTaskId = document.getElementById("timeTaskId");
  const timeStart = document.getElementById("timeStart");
  const timeStop = document.getElementById("timeStop");
  const timeStatus = document.getElementById("timeStatus");
  const projectName = document.getElementById("projectName");
  const projectDesc = document.getElementById("projectDesc");
  const projectBudgetHours = document.getElementById("projectBudgetHours");
  const projectBudgetCost = document.getElementById("projectBudgetCost");
  const projectCreate = document.getElementById("projectCreate");
  const projectStatus = document.getElementById("projectStatus");
  const weekDate = document.getElementById("weekDate");
  const weekSummary = document.getElementById("weekSummary");
  const projectBudget = document.getElementById("projectBudget");
  const entryList = document.getElementById("entryList");
  const exportWeek = document.getElementById("exportWeek");

  function fmtDuration(seconds){
    const h = Math.floor(seconds / 3600);
    const m = Math.floor((seconds % 3600) / 60);
    return `${h}h ${m}m`;
  }

  function toast(level, msg){
    if(window.showToast){
      window.showToast(level, msg);
      return;
    }
    if(level === "error") alert(msg);
  }

  function renderBudget(summary){
    if(!projectBudget) return;
    if(!summary || !summary.project_id){
      projectBudget.innerHTML = "<div class='muted text-sm'>Kein Projekt ausgewählt.</div>";
      return;
    }
    const hPct = Math.max(0, Math.min(100, Number(summary.progress_hours_pct || 0)));
    const cPct = Math.max(0, Math.min(100, Number(summary.progress_cost_pct || 0)));
    const warn = summary.warning ? "<div class='text-amber-300 text-xs mt-2'>⚠ Budget >80% erreicht</div>" : "";
    projectBudget.innerHTML = `
      <div class="text-sm font-semibold mb-2">${summary.project_name || "Projekt"}</div>
      <div class="muted text-xs">Stunden: ${summary.spent_hours || 0} / ${summary.budget_hours || 0}</div>
      <div class="w-full bg-slate-800 rounded-full h-2 mt-1"><div class="h-2 rounded-full" style="width:${hPct}%; background:${hPct >= 80 ? '#f59e0b' : 'var(--accent-500)'}"></div></div>
      <div class="muted text-xs mt-2">Kosten: €${summary.spent_cost || 0} / €${summary.budget_cost || 0}</div>
      <div class="w-full bg-slate-800 rounded-full h-2 mt-1"><div class="h-2 rounded-full" style="width:${cPct}%; background:${cPct >= 80 ? '#f59e0b' : 'var(--accent-500)'}"></div></div>
      ${warn}`;
  }

  async function loadProjectBudget(){
    const pid = parseInt(timeProject.value || "0", 10);
    if(!pid){
      renderBudget(null);
      return;
    }
    const res = await fetch(`/api/time/project/${pid}`, {credentials:"same-origin"});
    const data = await res.json();
    if(!res.ok){
      renderBudget(null);
      return;
    }
    renderBudget(data.summary || null);
  }

  function setStatus(msg, isError){
    timeStatus.textContent = msg;
    timeStatus.style.color = isError ? "#f87171" : "";
  }

  async function loadProjects(){
    const res = await fetch("/api/time/projects", {credentials:"same-origin"});
    const data = await res.json();
    timeProject.innerHTML = "";
    const opt = document.createElement("option");
    opt.value = "";
    opt.textContent = "Ohne Projekt";
    timeProject.appendChild(opt);
    (data.projects || []).forEach(p => {
      const o = document.createElement("option");
      o.value = p.id;
      o.textContent = p.name;
      timeProject.appendChild(o);
    });
  }

  function renderSummary(items){
    weekSummary.innerHTML = "";
    if(!items.length){
      weekSummary.innerHTML = "<div class='muted text-sm'>Keine Einträge.</div>";
      return;
    }
    items.forEach(day => {
      const card = document.createElement("div");
      card.className = "rounded-xl border p-3";
      card.innerHTML = `<div class="text-sm font-semibold">${day.date}</div><div class="muted text-xs">Gesamt</div><div class="text-lg">${fmtDuration(day.total_seconds)}</div>`;
      weekSummary.appendChild(card);
    });
  }

  function renderEntries(entries){
    entryList.innerHTML = "";
    if(!entries.length){
      entryList.innerHTML = "<div class='muted text-sm'>Keine Einträge in dieser Woche.</div>";
      return;
    }
    entries.forEach(entry => {
      const wrap = document.createElement("div");
      wrap.className = "rounded-xl border p-3";
      const approveBtn = (role === "ADMIN" || role === "DEV") && entry.approval_status !== "APPROVED"
        ? `<button class="px-3 py-1 text-xs btn-outline" data-approve="${entry.id}">Freigeben</button>`
        : "";
      wrap.innerHTML = `
        <div class="flex flex-col md:flex-row md:items-center md:justify-between gap-2">
          <div>
            <div class="text-sm font-semibold">${entry.project_name || "Ohne Projekt"}</div>
            <div class="muted text-xs">${entry.start_at} → ${entry.end_at || "läuft"} · ${fmtDuration(entry.duration_seconds || 0)}</div>
            <div class="muted text-xs">Status: ${entry.approval_status || "PENDING"} ${entry.approved_by ? "(von " + entry.approved_by + ")" : ""}</div>
            ${entry.note ? `<div class="text-xs mt-1">${entry.note}</div>` : ""}
          </div>
          <div class="flex gap-2">
            <button class="px-3 py-1 text-xs btn-outline" data-edit="${entry.id}">Bearbeiten</button>
            ${approveBtn}
          </div>
        </div>`;
      entryList.appendChild(wrap);
    });
  }

  async function loadEntries(){
    const dateValue = weekDate.value;
    const res = await fetch(`/api/time/entries?range=week&date=${encodeURIComponent(dateValue)}`, {credentials:"same-origin"});
    const data = await res.json();
    renderSummary(data.summary || []);
    renderEntries(data.entries || []);
    if(data.running){
      setStatus(`Läuft seit ${data.running.start_at}.`, false);
    } else {
      setStatus("Timer bereit.", false);
    }
  }

  async function startTimer(){
    setStatus("Starte…", false);
    const payload = {project_id: timeProject.value || null, task_id: timeTaskId.value || null, note: timeNote.value || ""};
    const res = await fetch("/api/time/start", {method:"POST", headers: {"Content-Type":"application/json"}, credentials:"same-origin", body: JSON.stringify(payload)});
    const data = await res.json();
    if(!res.ok){
      setStatus(data.error?.message || "Fehler beim Start.", true);
      toast("error", data.error?.message || "Fehler beim Start.");
      return;
    }
    toast("success", "Timer gestartet.");
    timeNote.value = "";
    await loadEntries();
    await loadProjectBudget();
  }

  async function stopTimer(){
    setStatus("Stoppe…", false);
    const res = await fetch("/api/time/stop", {method:"POST", headers: {"Content-Type":"application/json"}, credentials:"same-origin", body: JSON.stringify({})});
    const data = await res.json();
    if(!res.ok){
      setStatus(data.error?.message || "Fehler beim Stoppen.", true);
      toast("error", data.error?.message || "Fehler beim Stoppen.");
      return;
    }
    toast("success", "Timer gestoppt.");
    await loadEntries();
    await loadProjectBudget();
  }

  async function createProject(){
    projectStatus.textContent = "Speichern…";
    const payload = {name: projectName.value || "", description: projectDesc.value || "", budget_hours: parseInt(projectBudgetHours?.value || "0", 10) || 0, budget_cost: parseFloat(projectBudgetCost?.value || "0") || 0};
    const res = await fetch("/api/time/projects", {method:"POST", headers: {"Content-Type":"application/json"}, credentials:"same-origin", body: JSON.stringify(payload)});
    const data = await res.json();
    if(!res.ok){
      projectStatus.textContent = data.error?.message || "Fehler beim Anlegen.";
      toast("error", projectStatus.textContent);
      return;
    }
    projectName.value = "";
    projectDesc.value = "";
    if(projectBudgetHours) projectBudgetHours.value = "";
    if(projectBudgetCost) projectBudgetCost.value = "";
    projectStatus.textContent = "Projekt angelegt.";
    toast("success", "Projekt angelegt.");
    await loadProjects();
    await loadProjectBudget();
  }

  entryList.addEventListener("click", async (e) => {
    const editId = e.target.getAttribute("data-edit");
    const approveId = e.target.getAttribute("data-approve");
    if(editId){
      const startAt = prompt("Startzeit (YYYY-MM-DDTHH:MM:SS)", "");
      if(startAt === null) return;
      const endAt = prompt("Endzeit (YYYY-MM-DDTHH:MM:SS oder leer)", "");
      const note = prompt("Notiz (optional)", "");
      const payload = {entry_id: parseInt(editId, 10), start_at: startAt || null, end_at: endAt || null, note: note || null};
      const res = await fetch("/api/time/entry/edit", {method:"POST", headers: {"Content-Type":"application/json"}, credentials:"same-origin", body: JSON.stringify(payload)});
      const data = await res.json();
      if(!res.ok){ alert(data.error?.message || "Fehler beim Update."); }
      await loadEntries();
    }
    if(approveId){
      const res = await fetch("/api/time/entry/approve", {method:"POST", headers: {"Content-Type":"application/json"}, credentials:"same-origin", body: JSON.stringify({entry_id: parseInt(approveId, 10)})});
      const data = await res.json();
      if(!res.ok){ alert(data.error?.message || "Fehler beim Freigeben."); }
      await loadEntries();
    }
  });

  exportWeek.addEventListener("click", () => {
    const dateValue = weekDate.value;
    window.location.href = `/api/time/export?range=week&date=${encodeURIComponent(dateValue)}`;
  });

  timeStart.addEventListener("click", startTimer);
  timeStop.addEventListener("click", stopTimer);
  projectCreate.addEventListener("click", createProject);
  timeProject.addEventListener("change", loadProjectBudget);

  const today = new Date().toISOString().slice(0, 10);
  weekDate.value = today;
  loadProjects().then(loadEntries).then(loadProjectBudget);
})();
</script>
"""

HTML_CHAT = r"""<div class="rounded-2xl bg-slate-900/60 border border-slate-800 p-5 card">
  <div class="flex items-center justify-between gap-2">
    <div>
      <div class="text-lg font-semibold">Local Chat</div>
      <div class="muted text-sm">Tool-faehiger Chat mit lokalem Ollama-Orchestrator.</div>
    </div>
  </div>
  <div class="mt-4 flex flex-col md:flex-row gap-2">
    <input id="kdnr" class="rounded-xl bg-slate-800 border border-slate-700 p-2 input md:w-48" placeholder="Kdnr optional" />
    <input id="q" class="rounded-xl bg-slate-800 border border-slate-700 p-2 input flex-1" placeholder="Frag etwas… z.B. 'suche Rechnung KDNR 12393'" />
    <button id="send" class="rounded-xl px-4 py-2 font-semibold btn-primary md:w-40">Senden</button>
  </div>
  <div class="mt-4 rounded-xl border border-slate-800 bg-slate-950/40 p-3" style="height:62vh; overflow:auto" id="log"></div>
  <div class="muted text-xs mt-3">
    Tipp: Nutze „öffne &lt;token&gt;“ um direkt in die Review-Ansicht zu springen.
  </div>
</div>
<script>
(function(){
  const log = document.getElementById("log");
  const q = document.getElementById("q");
  const kdnr = document.getElementById("kdnr");
  const send = document.getElementById("send");
  async function openToken(token){
    if(!token) return;
    try{
      const res = await fetch('/api/open', {method:'POST', credentials:'same-origin', headers:{'Content-Type':'application/json'}, body: JSON.stringify({token})});
      const data = await res.json();
      if(!res.ok){
        const errMsg = (data && data.error && data.error.message) ? data.error.message : (data.message || data.error || ('HTTP ' + res.status));
        add("system", "Fehler: " + errMsg);
        return;
      }
      if(data && data.token){
        window.location.href = '/review/' + data.token + '/kdnr';
      }
    }catch(e){
      add("system", "Netzwerkfehler: " + (e && e.message ? e.message : e));
    }
  }
  async function copyToken(token){
    if(!token) return;
    try{
      await navigator.clipboard.writeText(token);
      add("system", "Token kopiert: " + token);
    }catch(e){
      add("system", "Kopieren fehlgeschlagen: " + (e && e.message ? e.message : e));
    }
  }
  window.openToken = openToken;
  window.copyToken = copyToken;
  function add(role, text, actions, results, suggestions){
    const d = document.createElement("div");
    d.className = "mb-3";
    let actionHtml = "";
    if(actions && actions.length){
      actionHtml = actions.map(a => {
        if(a.type === "open_token" && a.token){
          return `<button class="inline-block mt-1 rounded-full border px-2 py-1 text-xs hover:bg-slate-800" onclick="openToken('${a.token}')">Öffnen ${a.token.slice(0,10)}…</button>
            <button class="inline-block mt-1 rounded-full border px-2 py-1 text-xs hover:bg-slate-800" onclick="copyToken('${a.token}')">Token ${a.token.slice(0,10)}…</button>`;
        }
        return `<span class="inline-block mt-1 rounded-full border px-2 py-1 text-xs">Action: ${a.type || 'tool'}</span>`;
      }).join("");
    }
    let resultHtml = "";
    if(results && results.length){
      resultHtml = results.map(r => {
        const token = r.token || r.doc_id || "";
        const label = r.file_name || token;
        if(token){
          return `<button class="inline-block mt-1 rounded-full border px-2 py-1 text-xs hover:bg-slate-800" onclick="openToken('${token}')">${label}</button>
            <button class="inline-block mt-1 rounded-full border px-2 py-1 text-xs hover:bg-slate-800" onclick="copyToken('${token}')">Token ${token.slice(0,10)}…</button>`;
        }
        return `<span class="inline-block mt-1 rounded-full border px-2 py-1 text-xs">${label}</span>`;
      }).join("");
    }
    let suggestionHtml = "";
    if(suggestions && suggestions.length){
      suggestionHtml = suggestions.map(s => `<button class="inline-block mt-1 rounded-full border px-2 py-1 text-xs hover:bg-slate-800 chat-suggestion" data-q="${s}">${s}</button>`).join("");
    }
    d.innerHTML = `<div class="muted text-[11px]">${role}</div><div class="text-sm whitespace-pre-wrap">${text}</div>${actionHtml}${resultHtml}${suggestionHtml}`;
    log.appendChild(d);
    log.scrollTop = log.scrollHeight;
  }
  async function doSend(){
    const msg = (q.value || "").trim();
    if(!msg) return;
    add("you", msg);
    q.value = "";
    send.disabled = true;
    try{
      const res = await fetch("/api/ai/chat", {method:"POST", credentials:"same-origin", credentials:"same-origin", headers: {"Content-Type":"application/json"}, body: JSON.stringify({q: msg, kdnr: (kdnr.value||"").trim()})});
      const j = await res.json();
      if(!res.ok){
        const errMsg = (j && j.error && j.error.message) ? j.error.message : (j.message || j.error || ("HTTP " + res.status));
        add("system", "Fehler: " + errMsg);
      }
      else { add("assistant", j.message || "(leer)", j.actions || [], j.results || [], j.suggestions || []); }
    }catch(e){ add("system", "Netzwerkfehler: " + (e && e.message ? e.message : e)); }
    finally{ send.disabled = false; }
  }
  send.addEventListener("click", doSend);
  q.addEventListener("keydown", (e)=>{ if(e.key==="Enter"){ e.preventDefault(); doSend(); }});
  log.addEventListener("click", (e) => {
    const btn = e.target.closest(".chat-suggestion");
    if(!btn) return;
    q.value = btn.dataset.q || "";
    doSend();
  });

  // ---- Floating Chat Widget ----
  const _cw = {
    btn: document.getElementById('chatWidgetBtn'),
    drawer: document.getElementById('chatDrawer'),
    close: document.getElementById('chatWidgetClose'),
    msgs: document.getElementById('chatWidgetMsgs'),
    input: document.getElementById('chatWidgetInput'),
    send: document.getElementById('chatWidgetSend'),
    kdnr: document.getElementById('chatWidgetKdnr'),
    clear: document.getElementById('chatWidgetClear'),
    status: document.getElementById('chatWidgetStatus'),
    retry: document.getElementById('chatWidgetRetry'),
    unread: document.getElementById('chatUnread'),
    quick: document.querySelectorAll('.chat-quick'),
  };
  let _cwLastBody = null;
  let _cwAiAvailable = true;
  function _cwAppend(role, text, actions, results, suggestions){
    if(!_cw.msgs) return;
    const wrap = document.createElement('div');
    const isUser = role === 'you';
    wrap.className = 'flex ' + (isUser ? 'justify-end' : 'justify-start');
    const bubble = document.createElement('div');
    bubble.className = (isUser
      ? 'max-w-[85%] rounded-2xl px-3 py-2 text-white'
      : 'max-w-[85%] rounded-2xl px-3 py-2 border') + ' card';
    bubble.textContent = text;
    if(actions && actions.length){
      const list = document.createElement('div');
      list.className = 'mt-2 flex flex-wrap gap-2 text-xs';
      actions.forEach((action) => {
        if(action.type === 'open_token' && action.token){
          const btn = document.createElement('button');
          btn.textContent = 'Öffnen ' + action.token.slice(0,10) + '…';
          btn.className = 'rounded-full border px-2 py-1';
          btn.addEventListener('click', () => openToken(action.token));
          list.appendChild(btn);
          const tokenBtn = document.createElement('button');
          tokenBtn.textContent = 'Token ' + action.token.slice(0,10) + '…';
          tokenBtn.className = 'rounded-full border px-2 py-1';
          tokenBtn.addEventListener('click', () => copyToken(action.token));
          list.appendChild(tokenBtn);
        } else if(action.type){
          const tag = document.createElement('span');
          tag.textContent = 'Action: ' + action.type;
          tag.className = 'rounded-full border px-2 py-1';
          list.appendChild(tag);
        }
      });
      bubble.appendChild(list);
    }
    if(results && results.length){
      const list = document.createElement('div');
      list.className = 'mt-2 flex flex-wrap gap-2 text-xs';
      results.forEach((row) => {
        const token = row.token || row.doc_id || '';
        const label = row.file_name || token || 'Dokument';
        if(token){
          const btn = document.createElement('button');
          btn.textContent = label;
          btn.className = 'rounded-full border px-2 py-1';
          btn.addEventListener('click', () => openToken(token));
          list.appendChild(btn);
          const tokenBtn = document.createElement('button');
          tokenBtn.textContent = 'Token ' + token.slice(0,10) + '…';
          tokenBtn.className = 'rounded-full border px-2 py-1';
          tokenBtn.addEventListener('click', () => copyToken(token));
          list.appendChild(tokenBtn);
        }
      });
      bubble.appendChild(list);
    }
    if(suggestions && suggestions.length){
      const list = document.createElement('div');
      list.className = 'mt-2 flex flex-wrap gap-2 text-xs';
      suggestions.forEach((s) => {
        const btn = document.createElement('button');
        btn.textContent = s;
        btn.dataset.q = s;
        btn.className = 'rounded-full border px-2 py-1 chat-suggestion';
        list.appendChild(btn);
      });
      bubble.appendChild(list);
    }
    if(isUser){
      bubble.style.background = 'var(--accent-600)';
    }
    wrap.appendChild(bubble);
    _cw.msgs.appendChild(wrap);
    _cw.msgs.scrollTop = _cw.msgs.scrollHeight;
    if(_cw.unread && _cw.drawer?.classList.contains('hidden')){
      _cw.unread.classList.remove('hidden');
    }
  }
  function _cwLoad(){
    try{
      const k = localStorage.getItem('kukanilea_cw_kdnr') || '';
      if(_cw.kdnr) _cw.kdnr.value = k;
      const hist = JSON.parse(localStorage.getItem('kukanilea_cw_hist') || '[]');
      if(_cw.msgs){
        _cw.msgs.innerHTML = '';
        hist.forEach(x => _cwAppend(x.role, x.text));
      }
    }catch(e){}
  }
  function _cwSave(){
    try{
      if(_cw.kdnr) localStorage.setItem('kukanilea_cw_kdnr', _cw.kdnr.value || '');
      const hist = [];
      if(_cw.msgs){
        _cw.msgs.querySelectorAll('div.flex').forEach(row => {
          const isUser = row.className.includes('justify-end');
          const bubble = row.querySelector('div');
          hist.push({role: isUser ? 'you' : 'assistant', text: bubble ? bubble.textContent : ''});
        });
      }
      localStorage.setItem('kukanilea_cw_hist', JSON.stringify(hist.slice(-40)));
    }catch(e){}
  }
  async function _cwRefreshAiStatus(){
    try{
      const r = await fetch('/api/ai/status', {method:'GET', headers:{'Accept':'application/json'}});
      let j = {};
      try{ j = await r.json(); }catch(e){}
      _cwAiAvailable = !!(r.ok && j && j.available);
      if(_cw.status){
        if(_cwAiAvailable){
          _cw.status.textContent = 'Bereit';
        }else{
          _cw.status.textContent = 'KI offline';
        }
      }
      if(_cw.send) _cw.send.disabled = !_cwAiAvailable;
      if(_cw.input) _cw.input.disabled = !_cwAiAvailable;
      if(!_cwAiAvailable && _cw.msgs && !_cw.msgs.dataset.aiNotice){
        _cw.msgs.dataset.aiNotice = '1';
        _cwAppend('assistant', 'KI-Assistent ist derzeit nicht verfuegbar. Bitte starte lokal `ollama serve`.');
      }
    }catch(e){
      _cwAiAvailable = false;
      if(_cw.status) _cw.status.textContent = 'KI offline';
      if(_cw.send) _cw.send.disabled = true;
      if(_cw.input) _cw.input.disabled = true;
    }
  }
  async function _cwSend(){
    if(!_cwAiAvailable){
      _cwAppend('assistant', 'KI-Assistent ist offline. Starte `ollama serve` und versuche es erneut.');
      return;
    }
    const q = (_cw.input && _cw.input.value ? _cw.input.value.trim() : '');
    if(!q) return;
    _cwAppend('you', q);
    if(_cw.input) _cw.input.value = '';
    _cwSave();
    if(_cw.status) _cw.status.textContent = 'Denke…';
    if(_cw.retry) _cw.retry.classList.add('hidden');
    try{
      const body = { q, kdnr: _cw.kdnr ? _cw.kdnr.value.trim() : '' };
      _cwLastBody = body;
      const r = await fetch('/api/ai/chat', {method:'POST', headers:{'Content-Type':'application/json'}, body: JSON.stringify(body)});
      let j = {};
      try{ j = await r.json(); }catch(e){}
      if(!r.ok){
        const msg = (j && j.error && j.error.message) ? j.error.message : (j.message || j.error || ('HTTP ' + r.status));
        _cwAppend('assistant', 'Fehler: ' + msg);
        if(_cw.status) _cw.status.textContent = 'Fehler';
        if(_cw.retry) _cw.retry.classList.remove('hidden');
        return;
      }
      _cwAppend('assistant', j.message || '(keine Antwort)', j.actions || [], j.results || [], j.suggestions || []);
      if(_cw.status) _cw.status.textContent = 'OK';
      _cwSave();
    }catch(e){
      _cwAppend('assistant', 'Fehler: ' + (e && e.message ? e.message : e));
      if(_cw.status) _cw.status.textContent = 'Fehler';
      if(_cw.retry) _cw.retry.classList.remove('hidden');
    }
  }
  if(_cw.msgs){
    _cw.msgs.addEventListener('click', (e) => {
      const btn = e.target.closest('.chat-suggestion');
      if(!btn) return;
      if(_cw.input) _cw.input.value = btn.dataset.q || '';
      _cwSend();
    });
  }
  if(_cw.btn && _cw.drawer){
    _cw.btn.addEventListener('click', () => {
      _cw.drawer.classList.toggle('hidden');
      if(_cw.unread) _cw.unread.classList.add('hidden');
      _cwLoad();
      _cwRefreshAiStatus();
      if(!_cw.drawer.classList.contains('hidden') && _cw.input) _cw.input.focus();
    });
  }
  if(_cw.close) _cw.close.addEventListener('click', () => _cw.drawer && _cw.drawer.classList.add('hidden'));
  if(_cw.send) _cw.send.addEventListener('click', _cwSend);
  if(_cw.input) _cw.input.addEventListener('keydown', (e) => { if(e.key === 'Enter'){ e.preventDefault(); _cwSend(); }});
  if(_cw.kdnr) _cw.kdnr.addEventListener('change', _cwSave);
  if(_cw.clear) _cw.clear.addEventListener('click', () => { if(_cw.msgs) _cw.msgs.innerHTML=''; localStorage.removeItem('kukanilea_cw_hist'); _cwSave(); });
  if(_cw.retry) _cw.retry.addEventListener('click', () => {
    if(!_cwLastBody) return;
    if(_cw.input) _cw.input.value = _cwLastBody.q || '';
    _cwSend();
  });
  _cw.quick?.forEach((btn) => {
    btn.addEventListener('click', () => {
      if(_cw.input) _cw.input.value = btn.dataset.q || '';
      _cwSend();
    });
  });
  _cwRefreshAiStatus();
  // ---- /Floating Chat Widget ----
})();
</script>"""

# -------- Routes / API ----------


# ============================================================
# Auth routes + global guard
# ============================================================
@bp.before_app_request
def _guard_login():
    p = request.path or "/"
    if p.startswith("/static/") or p in [
        "/login",
        "/register",
        "/verify-email",
        "/forgot-password",
        "/reset-password",
        "/health",
        "/auth/google/start",
        "/auth/google/callback",
        "/api/health",
        "/api/ping",
        "/app.webmanifest",
        "/sw.js",
    ]:
        return None
    if not current_user():
        if p.startswith("/api/"):
            return json_error(
                "auth_required", "Authentifizierung erforderlich.", status=401
            )
        return redirect(url_for("web.login", next=p))
    return None


@bp.route("/login", methods=["GET", "POST"])
def login():
    auth_db: AuthDB = current_app.extensions["auth_db"]
    error = ""
    nxt = request.args.get("next", "/")
    if request.method == "POST":
        u = (request.form.get("username") or "").strip().lower()
        pw = (request.form.get("password") or "").strip()
        if not u or not pw:
            error = "Bitte Login und Passwort eingeben."
        else:
            user = auth_db.get_user_for_login(u)
            if user and verify_password(pw, user.password_hash):
                if user.email and not int(user.email_verified or 0):
                    error = "E-Mail ist noch nicht verifiziert."
                    return _render_base(
                        render_template_string(HTML_LOGIN, error=error),
                        active_tab="upload",
                    )
                memberships = auth_db.get_memberships(u)
                if not memberships and user.username != u:
                    memberships = auth_db.get_memberships(user.username)
                if not memberships:
                    error = "Keine Mandanten-Zuordnung gefunden."
                else:
                    membership = memberships[0]
                    login_user(user.username, membership.role, membership.tenant_id)
                    _audit(
                        "login",
                        target=user.username,
                        meta={"role": membership.role, "tenant": membership.tenant_id},
                    )
                    return redirect(nxt or url_for("web.index"))
            else:
                error = "Login fehlgeschlagen."
    return _render_base(
        render_template_string(HTML_LOGIN, error=error), active_tab="upload"
    )


def _username_from_email(auth_db: AuthDB, email: str) -> str:
    base = re.sub(r"[^a-z0-9._-]+", "_", email.split("@", 1)[0].lower()).strip("_")
    if not base:
        base = "user"
    candidate = base[:48]
    idx = 1
    while auth_db.get_user(candidate) is not None:
        idx += 1
        candidate = f"{base[:40]}_{idx}"
    return candidate


@bp.route("/register", methods=["GET", "POST"])
def register():
    auth_db: AuthDB = current_app.extensions["auth_db"]
    error = ""
    info = ""
    if request.method == "POST":
        if bool(current_app.config.get("READ_ONLY", False)):
            error = "Read-only mode aktiv."
        else:
            email = _normalize_email(request.form.get("email") or "")
            password = (request.form.get("password") or "").strip()
            password_confirm = (request.form.get("password_confirm") or "").strip()
            if not re.match(r"^[^@\s]+@[^@\s]+\.[^@\s]+$", email):
                error = "Bitte eine gültige E-Mail eingeben."
            elif len(password) < 8:
                error = "Passwort muss mindestens 8 Zeichen haben."
            elif password != password_confirm:
                error = "Passwörter stimmen nicht überein."
            elif auth_db.get_user_by_email(email):
                error = "E-Mail ist bereits registriert."
            else:
                now = _now_iso()
                code = _generate_numeric_code(6)
                code_hash = _hash_code(code)
                expires = (datetime.utcnow() + timedelta(minutes=15)).isoformat(
                    timespec="seconds"
                )
                username = _username_from_email(auth_db, email)
                auth_db.create_user(
                    username=username,
                    password_hash=hash_password(password),
                    created_at=now,
                    email=email,
                    email_verified=0,
                )
                auth_db.set_email_verification_code(username, code_hash, expires, now)
                default_tenant = str(
                    current_app.config.get("TENANT_DEFAULT", "KUKANILEA")
                )
                auth_db.upsert_tenant(default_tenant, default_tenant, now)
                auth_db.upsert_membership(username, default_tenant, "OPERATOR", now)
                auth_db.add_outbox(
                    tenant_id=default_tenant,
                    kind="verify_email",
                    recipient_redacted=_redact_email(email),
                    subject="Bestätigungscode",
                    body=f"Code: {code}",
                    created_at=now,
                )
                info = "Registrierung gespeichert. Code in lokaler Outbox."
    return _render_base(
        render_template_string(HTML_REGISTER, error=error, info=info),
        active_tab="upload",
    )


@bp.route("/verify-email", methods=["GET", "POST"])
def verify_email():
    auth_db: AuthDB = current_app.extensions["auth_db"]
    error = ""
    info = ""
    if request.method == "POST":
        if bool(current_app.config.get("READ_ONLY", False)):
            error = "Read-only mode aktiv."
        else:
            email = _normalize_email(request.form.get("email") or "")
            code = (request.form.get("code") or "").strip()
            if not email or not code:
                error = "E-Mail und Code sind erforderlich."
            else:
                username = auth_db.get_user_by_email_verify_code(
                    email, _hash_code(code), _now_iso()
                )
                if not username:
                    error = "Code ungültig oder abgelaufen."
                else:
                    auth_db.mark_email_verified(username, _now_iso())
                    info = "E-Mail bestätigt. Du kannst dich jetzt einloggen."
    return _render_base(
        render_template_string(HTML_VERIFY_EMAIL, error=error, info=info),
        active_tab="upload",
    )


@bp.route("/forgot-password", methods=["GET", "POST"])
def forgot_password():
    auth_db: AuthDB = current_app.extensions["auth_db"]
    error = ""
    info = ""
    if request.method == "POST":
        if bool(current_app.config.get("READ_ONLY", False)):
            error = "Read-only mode aktiv."
        else:
            email = _normalize_email(request.form.get("email") or "")
            if not email:
                error = "Bitte E-Mail eingeben."
            else:
                user = auth_db.get_user_by_email(email)
                now = _now_iso()
                if user:
                    code = _generate_numeric_code(6)
                    expires = (datetime.utcnow() + timedelta(minutes=15)).isoformat(
                        timespec="seconds"
                    )
                    auth_db.set_password_reset_code(
                        email, _hash_code(code), expires, now
                    )
                    auth_db.add_outbox(
                        tenant_id=str(
                            current_app.config.get("TENANT_DEFAULT", "KUKANILEA")
                        ),
                        kind="reset_password",
                        recipient_redacted=_redact_email(email),
                        subject="Reset-Code",
                        body=f"Code: {code}",
                        created_at=now,
                    )
                info = "Wenn der Account existiert, wurde ein Reset-Code erzeugt."
    return _render_base(
        render_template_string(HTML_FORGOT_PASSWORD, error=error, info=info),
        active_tab="upload",
    )


@bp.route("/reset-password", methods=["GET", "POST"])
def reset_password():
    auth_db: AuthDB = current_app.extensions["auth_db"]
    error = ""
    info = ""
    if request.method == "POST":
        if bool(current_app.config.get("READ_ONLY", False)):
            error = "Read-only mode aktiv."
        else:
            email = _normalize_email(request.form.get("email") or "")
            code = (request.form.get("code") or "").strip()
            password = (request.form.get("password") or "").strip()
            password_confirm = (request.form.get("password_confirm") or "").strip()
            if not email or not code:
                error = "E-Mail und Code sind erforderlich."
            elif len(password) < 8:
                error = "Passwort muss mindestens 8 Zeichen haben."
            elif password != password_confirm:
                error = "Passwörter stimmen nicht überein."
            else:
                username = auth_db.get_user_by_reset_code(
                    email, _hash_code(code), _now_iso()
                )
                if not username:
                    error = "Code ungültig oder abgelaufen."
                else:
                    auth_db.reset_password(
                        username=username,
                        password_hash=hash_password(password),
                        now_iso=_now_iso(),
                    )
                    info = "Passwort aktualisiert. Bitte einloggen."
    return _render_base(
        render_template_string(HTML_RESET_PASSWORD, error=error, info=info),
        active_tab="upload",
    )


@bp.get("/auth/google/start")
def google_start():
    if not (
        current_app.config.get("GOOGLE_CLIENT_ID")
        and current_app.config.get("GOOGLE_CLIENT_SECRET")
    ):
        return _render_base(
            _card(
                "info",
                "Google OAuth ist nicht konfiguriert. Setze GOOGLE_CLIENT_ID/SECRET.",
            ),
            active_tab="postfach",
        )
    return _render_base(
        _card("info", "Google OAuth Flow (Stub). Callback nicht implementiert."),
        active_tab="postfach",
    )


@bp.get("/auth/google/callback")
def google_callback():
    return _render_base(
        _card("info", "Google OAuth Callback (Stub)."), active_tab="postfach"
    )


@bp.route("/logout")
def logout():
    if current_user():
        _audit("logout", target=current_user() or "", meta={})
    logout_user()
    return redirect(url_for("web.login"))


@bp.route("/api/progress/<token>")
def api_progress(token: str):
    if (not current_user()) and (request.remote_addr not in ("127.0.0.1", "::1")):
        return jsonify(error="unauthorized"), 401
    p = read_pending(token)
    if not p:
        return jsonify(error="not_found"), 404
    return jsonify(
        status=p.get("status", ""),
        progress=float(p.get("progress", 0.0) or 0.0),
        progress_phase=p.get("progress_phase", ""),
        error=p.get("error", ""),
    )


def _weather_answer(city: str) -> str:
    info = get_weather(city)
    if not info:
        return f"Ich konnte das Wetter für {city} nicht abrufen."
    return f"Wetter {info.get('city', '')}: {info.get('summary', '')} (Temp: {info.get('temp_c', '?')}°C, Wind: {info.get('wind_kmh', '?')} km/h)"


def _weather_adapter(message: str) -> str:
    city = "Berlin"
    match = re.search(r"\bin\s+([A-Za-zÄÖÜäöüß\- ]{2,40})\b", message, re.IGNORECASE)
    if match:
        city = match.group(1).strip()
    return _weather_answer(city)


ORCHESTRATOR = Orchestrator(core, weather_adapter=_weather_adapter)
_DEV_STATUS = {"index": None, "scan": None, "llm": None, "db": None}


def _mock_generate(prompt: str) -> str:
    return f"[mocked] {prompt.strip()[:200]}"


@bp.get("/api/ai/status")
@login_required
def api_ai_status():
    base_url = str(current_app.config.get("OLLAMA_BASE_URL") or "").strip() or None
    available = bool(ollama_is_available(base_url=base_url, timeout_s=5))
    models: list[str] = []
    if available:
        try:
            models = ollama_list_models(base_url=base_url, timeout_s=5)
        except Exception:
            models = []
    return jsonify(
        {
            "ok": True,
            "available": available,
            "models": models,
            "model_default": str(current_app.config.get("OLLAMA_MODEL") or ""),
        }
    )


@bp.route("/api/ai/chat", methods=["POST"])
@login_required
def api_ai_chat():
    payload = request.get_json(silent=True) or {}
    msg = (
        (payload.get("msg") if isinstance(payload, dict) else None)
        or (payload.get("q") if isinstance(payload, dict) else None)
        or request.form.get("msg")
        or request.form.get("q")
        or request.form.get("message")
        or ""
    ).strip()
    if not msg:
        return json_error("empty_query", "Leer.", status=400)
    if len(msg) > 4000:
        return json_error(
            "too_long", "Nachricht ist zu lang (max. 4000 Zeichen).", status=400
        )

    try:
        result = ai_process_message(
            tenant_id=current_tenant(),
            user_id=str(current_user() or "system"),
            user_message=msg,
            read_only=bool(current_app.config.get("READ_ONLY", False)),
        )
    except Exception as exc:
        return json_error("ai_error", f"KI-Fehler: {exc}", status=500)

    tool_used = [str(v) for v in (result.get("tool_used") or []) if str(v).strip()]
    actions = [{"type": "tool_call", "name": name} for name in tool_used[:8]]
    response_text = str(result.get("response") or "")
    out = {
        "ok": True,
        "status": str(result.get("status") or "error"),
        "conversation_id": result.get("conversation_id"),
        "tool_used": tool_used,
        "response": response_text,
        "message": response_text,
        "actions": actions,
        "results": [],
        "suggestions": [],
    }
    if request.headers.get("HX-Request"):
        return render_template_string(
            "<div class='rounded-xl border border-slate-700 p-2 text-sm'>{{text}}</div>",
            text=response_text,
        )
    return jsonify(out)


@bp.route("/api/ai/feedback", methods=["POST"])
@login_required
def api_ai_feedback():
    payload = request.get_json(silent=True) or {}
    conversation_id = (
        (payload.get("conversation_id") if isinstance(payload, dict) else None)
        or request.form.get("conversation_id")
        or ""
    ).strip()
    rating = (
        (payload.get("rating") if isinstance(payload, dict) else None)
        or request.form.get("rating")
        or ""
    ).strip()
    if not conversation_id or rating not in {"positive", "negative"}:
        return json_error("validation_error", "conversation_id/rating ungueltig.", 400)
    try:
        feedback_id = ai_add_feedback(
            tenant_id=current_tenant(),
            conversation_id=conversation_id,
            rating=rating,
        )
    except ValueError as exc:
        code = str(exc)
        if code == "not_found":
            return json_error("not_found", "Konversation nicht gefunden.", status=404)
        return json_error("validation_error", "Feedback ungueltig.", status=400)
    return jsonify({"ok": True, "feedback_id": feedback_id})


@bp.route("/api/chat", methods=["POST"])
@login_required
def api_chat():
    payload = request.get_json(silent=True) or {}
    msg = (
        (payload.get("msg") if isinstance(payload, dict) else None)
        or (payload.get("q") if isinstance(payload, dict) else None)
        or request.form.get("msg")
        or request.form.get("q")
        or ""
    ).strip()

    if not msg:
        return json_error("empty_query", "Leer.", status=400)
    if len(msg) > 4000:
        return json_error(
            "too_long", "Nachricht ist zu lang (max. 4000 Zeichen).", status=400
        )

    response = agent_answer(msg)
    if request.headers.get("HX-Request"):
        return render_template_string(
            "<div class='rounded-xl border border-slate-700 p-2 text-sm'>{{text}}</div>",
            text=str(response.get("text") or ""),
        )
    return jsonify(response)


@bp.post("/api/search")
@login_required
def api_search():
    payload = request.get_json(silent=True) or {}
    query = (payload.get("query") or "").strip()
    kdnr = (payload.get("kdnr") or "").strip()
    limit = int(payload.get("limit") or 8)
    if not query:
        return json_error("query_missing", "Query fehlt.", status=400)
    context = AgentContext(
        tenant_id=current_tenant(),
        user=str(current_user() or "dev"),
        role=str(current_role()),
        kdnr=kdnr,
    )
    agent = SearchAgent(core)
    results, suggestions = agent.search(query, context, limit=limit)
    message = "OK" if results else "Keine Treffer gefunden."
    return jsonify(
        ok=True, message=message, results=results, did_you_mean=suggestions or []
    )


@bp.post("/api/open")
@login_required
def api_open():
    payload = request.get_json(silent=True) or {}
    token = (payload.get("token") or "").strip()
    if not token:
        return json_error("token_missing", "Token fehlt.", status=400)
    src = _resolve_doc_path(token, {})
    if not src or not src.exists():
        return json_error(
            "FILE_NOT_FOUND",
            "Datei nicht gefunden. Bitte suche erneut oder prüfe den Token.",
            status=404,
            details={"token": token},
        )
    try:
        new_token = analyze_to_pending(src)
    except FileNotFoundError:
        return json_error(
            "FILE_NOT_FOUND",
            "Datei nicht gefunden. Bitte suche erneut oder prüfe den Token.",
            status=404,
            details={"token": token},
        )
    return jsonify(ok=True, token=new_token)


@bp.post("/api/customer")
@login_required
@require_role("OPERATOR")
def api_customer():
    payload = request.get_json(silent=True) or {}
    kdnr = (payload.get("kdnr") or "").strip()
    if not kdnr:
        return json_error("kdnr_missing", "KDNR fehlt.", status=400)
    context = AgentContext(
        tenant_id=current_tenant(),
        user=str(current_user() or "dev"),
        role=str(current_role()),
        kdnr=kdnr,
    )
    agent = CustomerAgent(core)
    result = agent.handle(kdnr, "customer_lookup", context)
    results = result.data.get("results", []) if isinstance(result.data, dict) else []
    summary = results[0] if results else {}
    return jsonify(
        ok=result.error is None,
        kdnr=str(summary.get("kdnr") or kdnr),
        customer_name=str(summary.get("customer_name") or ""),
        last_doc=str(summary.get("file_name") or ""),
        last_doc_date=str(summary.get("doc_date") or ""),
        results=results,
        message=result.text,
    )


_TASK_STATUS_BY_COLUMN = {
    "todo": "OPEN",
    "in_progress": "IN_PROGRESS",
    "done": "RESOLVED",
}
_TASK_STATUSES_ALL = ("OPEN", "IN_PROGRESS", "RESOLVED", "DISMISSED")


def _task_read_only_response(api: bool = True):
    if api:
        return json_error("read_only", "Read-only mode aktiv.", status=403)
    return _render_base(
        _card("error", "Read-only mode aktiv."), active_tab="tasks"
    ), 403


def _task_mutation_guard(api: bool = True):
    if bool(current_app.config.get("READ_ONLY", False)):
        return _task_read_only_response(api=api)
    return None


def _task_status_from_input(value: str) -> str | None:
    raw = (value or "").strip()
    if not raw:
        return None
    col = raw.lower()
    if col in _TASK_STATUS_BY_COLUMN:
        return _TASK_STATUS_BY_COLUMN[col]
    status = raw.upper()
    if status == "DONE":
        return "RESOLVED"
    if status in _TASK_STATUSES_ALL:
        return status
    return None


def _task_board_items(tenant_id: str) -> dict[str, list[dict]]:
    if not callable(task_list):
        return {"todo": [], "in_progress": [], "done": []}
    todo = task_list(tenant=tenant_id, status="OPEN", limit=200)  # type: ignore
    in_progress = task_list(tenant=tenant_id, status="IN_PROGRESS", limit=200)  # type: ignore
    done = task_list(tenant=tenant_id, status="RESOLVED", limit=200)  # type: ignore
    return {"todo": todo, "in_progress": in_progress, "done": done}


def _task_find(tenant_id: str, task_id: int) -> dict | None:
    if not callable(task_list):
        return None
    for status in _TASK_STATUSES_ALL:
        items = task_list(tenant=tenant_id, status=status, limit=500)  # type: ignore
        for item in items:
            if int(item.get("id") or 0) == int(task_id):
                return item
    return None


@bp.get("/api/tasks")
@login_required
def api_tasks():
    status_raw = (request.args.get("status") or "OPEN").strip()
    if not callable(task_list):
        return jsonify(ok=True, tasks=[])
    status_upper = status_raw.upper()
    tenant_id = current_tenant()
    if status_upper in {"ALL", "KANBAN"}:
        tasks_all = []
        for status in _TASK_STATUSES_ALL:
            tasks_all.extend(task_list(tenant=tenant_id, status=status, limit=200))  # type: ignore
        return jsonify(ok=True, tasks=tasks_all)
    status = _task_status_from_input(status_raw) or "OPEN"
    tasks = task_list(tenant=tenant_id, status=status, limit=200)  # type: ignore
    return jsonify(ok=True, tasks=tasks)


@bp.post("/api/tasks/create")
@login_required
@require_role("OPERATOR")
def api_tasks_create():
    if not callable(task_create_fn):
        return json_error(
            "feature_unavailable", "Tasks sind nicht verfügbar.", status=501
        )
    guarded = _task_mutation_guard(api=True)
    if guarded:
        return guarded
    payload = request.get_json(silent=True) or {}
    title = normalize_component(payload.get("title") or "")
    if not title:
        return json_error("title_missing", "Titel fehlt.", status=400)
    severity = normalize_component(payload.get("severity") or "INFO").upper() or "INFO"
    task_type = (
        normalize_component(payload.get("task_type") or "GENERAL").upper() or "GENERAL"
    )
    details = str(payload.get("details") or "").strip()
    task_id = task_create_fn(  # type: ignore
        tenant=current_tenant(),
        severity=severity,
        task_type=task_type,
        title=title,
        details=details,
        created_by=current_user() or "",
    )
    _audit(
        "task_create",
        target=str(task_id),
        meta={"tenant_id": current_tenant(), "status": "OPEN", "source": "kanban_api"},
    )
    try:
        event_append(
            event_type="task_created",
            entity_type="task",
            entity_id=int(task_id),
            payload={
                "tenant_id": current_tenant(),
                "task_status": "OPEN",
                "source": "kanban_api",
            },
        )
    except Exception:
        pass
    return jsonify(ok=True, task_id=int(task_id), status="OPEN")


@bp.post("/api/tasks/<int:task_id>/move")
@login_required
@require_role("OPERATOR")
def api_tasks_move(task_id: int):
    if not callable(task_set_status_fn):
        return json_error(
            "feature_unavailable", "Tasks sind nicht verfügbar.", status=501
        )
    guarded = _task_mutation_guard(api=True)
    if guarded:
        return guarded
    payload = request.get_json(silent=True) or {}
    status = _task_status_from_input(
        payload.get("status") or payload.get("column") or ""
    )
    if not status:
        return json_error("status_invalid", "Status ungültig.", status=400)
    changed = task_set_status_fn(  # type: ignore
        int(task_id),
        status,
        resolved_by=current_user() or "",
        tenant=current_tenant(),
    )
    if not changed:
        return json_error("task_not_found", "Task nicht gefunden.", status=404)
    _audit(
        "task_move",
        target=str(task_id),
        meta={"tenant_id": current_tenant(), "status": status, "source": "kanban_api"},
    )
    try:
        event_append(
            event_type="task_moved",
            entity_type="task",
            entity_id=int(task_id),
            payload={
                "tenant_id": current_tenant(),
                "task_status": status,
                "source": "kanban_api",
            },
        )
    except Exception:
        pass
    return jsonify(ok=True, task_id=int(task_id), status=status)


@bp.get("/api/audit")
@login_required
@require_role("ADMIN")
def api_audit():
    limit = int(request.args.get("limit") or 100)
    if callable(getattr(core, "audit_list", None)):
        events = core.audit_list(tenant_id=current_tenant(), limit=limit)
    else:
        events = []
    return jsonify(ok=True, events=events)


@bp.get("/api/time/projects")
@login_required
def api_time_projects():
    if not callable(time_project_list):
        return json_error(
            "feature_unavailable", "Time Tracking ist nicht verfügbar.", status=501
        )
    projects = time_project_list(tenant_id=current_tenant(), status="ACTIVE")  # type: ignore
    return jsonify(ok=True, projects=projects)


@bp.post("/api/time/projects")
@login_required
@require_role("OPERATOR")
def api_time_projects_create():
    if not callable(time_project_create):
        return json_error(
            "feature_unavailable", "Time Tracking ist nicht verfügbar.", status=501
        )
    payload = request.get_json(silent=True) or {}
    name = (payload.get("name") or "").strip()
    description = (payload.get("description") or "").strip()
    budget_hours = int(payload.get("budget_hours") or 0)
    budget_cost = float(payload.get("budget_cost") or 0.0)
    try:
        project = time_project_create(  # type: ignore
            tenant_id=current_tenant(),
            name=name,
            description=description,
            budget_hours=budget_hours,
            budget_cost=budget_cost,
            created_by=current_user() or "",
        )
    except ValueError as exc:
        return json_error(str(exc), "Projekt konnte nicht angelegt werden.", status=400)
    _rag_enqueue("time_project", int(project.get("id") or 0), "upsert")
    try:
        store_entity(
            "project",
            int(project.get("id") or 0),
            f"{project.get('name', '')} {project.get('description', '')}",
            {
                "tenant_id": current_tenant(),
                "budget_hours": int(project.get("budget_hours") or 0),
                "budget_cost": float(project.get("budget_cost") or 0.0),
            },
        )
    except Exception:
        pass
    return jsonify(ok=True, project=project)


@bp.post("/api/time/start")
@login_required
@require_role("OPERATOR")
def api_time_start():
    if not callable(time_entry_start):
        return json_error(
            "feature_unavailable", "Time Tracking ist nicht verfügbar.", status=501
        )
    payload = request.get_json(silent=True) or {}
    project_id = payload.get("project_id")
    task_id = payload.get("task_id")
    note = (payload.get("note") or "").strip()
    try:
        entry = time_entry_start(  # type: ignore
            tenant_id=current_tenant(),
            user=current_user() or "",
            user_id=None,
            project_id=int(project_id) if project_id else None,
            task_id=int(task_id) if task_id else None,
            note=note,
        )
    except ValueError as exc:
        return json_error(str(exc), "Timer konnte nicht gestartet werden.", status=400)
    _rag_enqueue("time_entry", int(entry.get("id") or 0), "upsert")
    return jsonify(ok=True, entry=entry)


@bp.post("/api/time/stop")
@login_required
@require_role("OPERATOR")
def api_time_stop():
    if not callable(time_entry_stop):
        return json_error(
            "feature_unavailable", "Time Tracking ist nicht verfügbar.", status=501
        )
    payload = request.get_json(silent=True) or {}
    entry_id = payload.get("entry_id")
    try:
        entry = time_entry_stop(  # type: ignore
            tenant_id=current_tenant(),
            user=current_user() or "",
            entry_id=int(entry_id) if entry_id else None,
        )
    except ValueError as exc:
        return json_error(str(exc), "Timer konnte nicht gestoppt werden.", status=400)
    _rag_enqueue("time_entry", int(entry.get("id") or 0), "upsert")
    return jsonify(ok=True, entry=entry)


@bp.get("/api/time/task/<int:task_id>")
@login_required
def api_time_task(task_id: int):
    if not callable(time_entries_summary_by_task):
        return json_error(
            "feature_unavailable", "Task-Zeitsummen sind nicht verfügbar.", status=501
        )
    try:
        summary = time_entries_summary_by_task(
            tenant_id=current_tenant(), task_id=int(task_id)
        )  # type: ignore
    except ValueError as exc:
        return json_error(
            str(exc), "Task-Summe konnte nicht geladen werden.", status=400
        )
    return jsonify(ok=True, summary=summary)


@bp.post("/api/ai/daily-report")
@login_required
@require_role("DEV")
def api_ai_daily_report():
    try:
        result = daily_report(tenant_id=current_tenant())
    except Exception as exc:
        return json_error(
            "ai_report_failed", f"AI Report fehlgeschlagen: {exc}", status=500
        )
    return jsonify(ok=True, result=result)


@bp.get("/api/time/project/<int:project_id>")
@login_required
def api_time_project_summary(project_id: int):
    if not callable(time_entries_summary_by_project):
        return json_error(
            "feature_unavailable", "Projekt-Summen sind nicht verfügbar.", status=501
        )
    try:
        summary = time_entries_summary_by_project(
            tenant_id=current_tenant(), project_id=int(project_id)
        )  # type: ignore
    except ValueError as exc:
        return json_error(
            str(exc), "Projekt-Summe konnte nicht geladen werden.", status=400
        )
    try:
        pred = predict_budget(int(project_id), tenant_id=current_tenant())
    except Exception:
        pred = None
    return jsonify(ok=True, summary=summary, prediction=pred)


@bp.get("/api/time/entries")
@login_required
def api_time_entries():
    if not callable(time_entry_list):
        return json_error(
            "feature_unavailable", "Time Tracking ist nicht verfügbar.", status=501
        )
    range_name = (request.args.get("range") or "week").strip().lower()
    date_value = (request.args.get("date") or datetime.now().date().isoformat()).strip()
    user = (request.args.get("user") or "").strip()
    if current_role() not in {"ADMIN", "DEV"}:
        user = current_user() or ""
    start_at, end_at = _time_range_params(range_name, date_value)
    entries = time_entry_list(  # type: ignore
        tenant_id=current_tenant(),
        user=user or None,
        start_at=start_at,
        end_at=end_at,
        limit=500,
    )
    summary: dict[str, int] = {}
    running = None
    for entry in entries:
        day = (entry.get("start_at") or "").split("T")[0]
        summary[day] = summary.get(day, 0) + int(entry.get("duration_seconds") or 0)
        if not entry.get("end_at") and running is None:
            running = entry
    summary_list = [{"date": k, "total_seconds": v} for k, v in sorted(summary.items())]
    return jsonify(ok=True, entries=entries, summary=summary_list, running=running)


@bp.post("/api/time/entry/edit")
@login_required
@require_role("OPERATOR")
def api_time_entry_edit():
    if not callable(time_entry_update):
        return json_error(
            "feature_unavailable", "Time Tracking ist nicht verfügbar.", status=501
        )
    payload = request.get_json(silent=True) or {}
    entry_id = payload.get("entry_id")
    if not entry_id:
        return json_error("entry_id_required", "Eintrag fehlt.", status=400)
    try:
        entry = time_entry_update(  # type: ignore
            tenant_id=current_tenant(),
            entry_id=int(entry_id),
            project_id=(
                int(payload.get("project_id")) if payload.get("project_id") else None
            ),
            task_id=(int(payload.get("task_id")) if payload.get("task_id") else None),
            user_id=(int(payload.get("user_id")) if payload.get("user_id") else None),
            start_at=(payload.get("start_at") or None),
            end_at=(payload.get("end_at") or None),
            note=payload.get("note"),
            user=current_user() or "",
        )
    except ValueError as exc:
        return json_error(
            str(exc), "Eintrag konnte nicht aktualisiert werden.", status=400
        )
    _rag_enqueue("time_entry", int(entry.get("id") or 0), "upsert")
    return jsonify(ok=True, entry=entry)


@bp.post("/api/time/entry/approve")
@login_required
@require_role("ADMIN")
def api_time_entry_approve():
    if not callable(time_entry_approve):
        return json_error(
            "feature_unavailable", "Time Tracking ist nicht verfügbar.", status=501
        )
    payload = request.get_json(silent=True) or {}
    entry_id = payload.get("entry_id")
    if not entry_id:
        return json_error("entry_id_required", "Eintrag fehlt.", status=400)
    try:
        entry = time_entry_approve(  # type: ignore
            tenant_id=current_tenant(),
            entry_id=int(entry_id),
            approved_by=current_user() or "",
        )
    except ValueError as exc:
        return json_error(
            str(exc), "Eintrag konnte nicht freigegeben werden.", status=400
        )
    _rag_enqueue("time_entry", int(entry.get("id") or 0), "upsert")
    return jsonify(ok=True, entry=entry)


@bp.get("/api/time/export")
@login_required
def api_time_export():
    if not callable(time_entries_export_csv):
        return json_error(
            "feature_unavailable", "Time Tracking ist nicht verfügbar.", status=501
        )
    range_name = (request.args.get("range") or "week").strip().lower()
    date_value = (request.args.get("date") or datetime.now().date().isoformat()).strip()
    user = (request.args.get("user") or "").strip()
    if current_role() not in {"ADMIN", "DEV"}:
        user = current_user() or ""
    start_at, end_at = _time_range_params(range_name, date_value)
    csv_payload = time_entries_export_csv(  # type: ignore
        tenant_id=current_tenant(),
        user=user or None,
        start_at=start_at,
        end_at=end_at,
    )
    response = current_app.response_class(csv_payload, mimetype="text/csv")
    response.headers["Content-Disposition"] = "attachment; filename=time_entries.csv"
    return response


def _crm_error_response(
    exc: Exception, default_message: str, *, not_found: bool = False
):
    code = str(exc)
    status = 400
    message = default_message
    if code == "not_found":
        status = 404
        code = "not_found"
        message = "Ressource nicht gefunden."
    elif code == "db_locked":
        status = 503
        code = "db_locked"
        message = "Datenbank ist gesperrt. Bitte erneut versuchen."
    elif code == "duplicate":
        status = 409
        code = "duplicate"
        message = "Doppelter Eintrag im Tenant."
    elif code == "read_only":
        status = 403
        code = "read_only"
    elif code in {
        "validation_error",
        "file_required",
        "invalid_file_type",
        "empty_file",
    }:
        status = 400
    elif not_found:
        status = 404
        code = "not_found"
    else:
        code = "validation_error"
    return json_error(code, message, status=status)


def _validate_iso(value: str) -> bool:
    try:
        datetime.fromisoformat(value)
        return True
    except Exception:
        return False


@bp.get("/api/customers")
@login_required
def api_customers_list():
    if not callable(customers_list):
        return json_error("feature_unavailable", "CRM ist nicht verfügbar.", status=501)
    limit = int(request.args.get("limit") or 100)
    offset = int(request.args.get("offset") or 0)
    query = (request.args.get("query") or "").strip() or None
    items = customers_list(current_tenant(), limit=limit, offset=offset, query=query)  # type: ignore
    return jsonify(ok=True, customers=items)


@bp.post("/api/customers")
@login_required
@require_role("OPERATOR")
def api_customers_create():
    if not callable(customers_create):
        return json_error("feature_unavailable", "CRM ist nicht verfügbar.", status=501)
    payload = request.get_json(silent=True) or {}
    try:
        cid = customers_create(  # type: ignore
            tenant_id=current_tenant(),
            name=payload.get("name") or "",
            vat_id=payload.get("vat_id"),
            notes=payload.get("notes"),
        )
        item = customers_get(current_tenant(), cid)  # type: ignore
    except ValueError as exc:
        return _crm_error_response(exc, "Kunde konnte nicht angelegt werden.")
    return jsonify(ok=True, customer=item)


@bp.get("/api/customers/<customer_id>")
@login_required
def api_customers_get(customer_id: str):
    if not callable(customers_get):
        return json_error("feature_unavailable", "CRM ist nicht verfügbar.", status=501)
    try:
        item = customers_get(current_tenant(), customer_id)  # type: ignore
    except ValueError as exc:
        return _crm_error_response(exc, "Kunde nicht gefunden.", not_found=True)
    return jsonify(ok=True, customer=item)


@bp.put("/api/customers/<customer_id>")
@login_required
@require_role("OPERATOR")
def api_customers_update(customer_id: str):
    if not callable(customers_update):
        return json_error("feature_unavailable", "CRM ist nicht verfügbar.", status=501)
    payload = request.get_json(silent=True) or {}
    try:
        item = customers_update(  # type: ignore
            current_tenant(),
            customer_id,
            name=payload.get("name"),
            vat_id=payload.get("vat_id"),
            notes=payload.get("notes"),
        )
    except ValueError as exc:
        return _crm_error_response(exc, "Kunde konnte nicht aktualisiert werden.")
    return jsonify(ok=True, customer=item)


@bp.get("/api/customers/<customer_id>/contacts")
@login_required
def api_contacts_list(customer_id: str):
    if not callable(contacts_list_by_customer):
        return json_error("feature_unavailable", "CRM ist nicht verfügbar.", status=501)
    try:
        items = contacts_list_by_customer(current_tenant(), customer_id)  # type: ignore
    except ValueError as exc:
        return _crm_error_response(
            exc, "Kontakte konnten nicht geladen werden.", not_found=True
        )
    return jsonify(ok=True, contacts=items)


@bp.post("/api/contacts")
@login_required
@require_role("OPERATOR")
def api_contacts_create():
    if not callable(contacts_create):
        return json_error("feature_unavailable", "CRM ist nicht verfügbar.", status=501)
    payload = request.get_json(silent=True) or {}
    try:
        cid = contacts_create(  # type: ignore
            tenant_id=current_tenant(),
            customer_id=payload.get("customer_id") or "",
            name=payload.get("name") or "",
            email=payload.get("email"),
            phone=payload.get("phone"),
            role=payload.get("role"),
            notes=payload.get("notes"),
        )
    except ValueError as exc:
        return _crm_error_response(exc, "Kontakt konnte nicht angelegt werden.")
    return jsonify(ok=True, contact_id=cid)


@bp.get("/api/deals")
@login_required
def api_deals_list():
    if not callable(deals_list):
        return json_error("feature_unavailable", "CRM ist nicht verfügbar.", status=501)
    stage = (request.args.get("stage") or "").strip() or None
    customer_id = (request.args.get("customer_id") or "").strip() or None
    items = deals_list(current_tenant(), stage=stage, customer_id=customer_id)  # type: ignore
    return jsonify(ok=True, deals=items)


@bp.post("/api/deals")
@login_required
@require_role("OPERATOR")
def api_deals_create():
    if not callable(deals_create):
        return json_error("feature_unavailable", "CRM ist nicht verfügbar.", status=501)
    payload = request.get_json(silent=True) or {}
    stage = (payload.get("stage") or "lead").strip().lower()
    allowed_stage = {"lead", "qualified", "proposal", "negotiation", "won", "lost"}
    if stage not in allowed_stage:
        return json_error("validation_error", "Ungültiger Deal-Status.", status=400)
    probability = payload.get("probability")
    if probability is not None:
        try:
            prob_val = int(probability)
        except Exception:
            return json_error(
                "validation_error", "Probability muss 0..100 sein.", status=400
            )
        if prob_val < 0 or prob_val > 100:
            return json_error(
                "validation_error", "Probability muss 0..100 sein.", status=400
            )
    expected_close = (payload.get("expected_close_date") or "").strip()
    if expected_close and not _validate_iso(expected_close):
        return json_error(
            "validation_error", "expected_close_date muss ISO sein.", status=400
        )
    try:
        did = deals_create(  # type: ignore
            tenant_id=current_tenant(),
            customer_id=payload.get("customer_id") or "",
            title=payload.get("title") or "",
            stage=stage,
            value_cents=payload.get("value_cents"),
            currency=payload.get("currency") or "EUR",
            notes=payload.get("notes"),
            project_id=(
                int(payload.get("project_id")) if payload.get("project_id") else None
            ),
            probability=(int(probability) if probability is not None else None),
            expected_close_date=(expected_close or None),
        )
    except ValueError as exc:
        return _crm_error_response(exc, "Deal konnte nicht angelegt werden.")
    return jsonify(ok=True, deal_id=did)


@bp.put("/api/deals/<deal_id>/stage")
@login_required
@require_role("OPERATOR")
def api_deals_stage(deal_id: str):
    if not callable(deals_update_stage):
        return json_error("feature_unavailable", "CRM ist nicht verfügbar.", status=501)
    payload = request.get_json(silent=True) or {}
    stage = (payload.get("stage") or "").strip().lower()
    if stage not in {"lead", "qualified", "proposal", "negotiation", "won", "lost"}:
        return json_error("validation_error", "Ungültiger Deal-Status.", status=400)
    try:
        item = deals_update_stage(current_tenant(), deal_id, stage)  # type: ignore
    except ValueError as exc:
        return _crm_error_response(exc, "Deal-Status konnte nicht aktualisiert werden.")
    return jsonify(ok=True, deal=item)


@bp.post("/api/quotes/from-deal/<deal_id>")
@login_required
@require_role("OPERATOR")
def api_quote_from_deal(deal_id: str):
    if not callable(quotes_create_from_deal):
        return json_error("feature_unavailable", "CRM ist nicht verfügbar.", status=501)
    try:
        quote = quotes_create_from_deal(current_tenant(), deal_id)  # type: ignore
    except ValueError as exc:
        return _crm_error_response(exc, "Angebot konnte nicht erstellt werden.")
    return jsonify(ok=True, quote=quote)


@bp.get("/api/quotes/<quote_id>")
@login_required
def api_quote_get(quote_id: str):
    if not callable(quotes_get):
        return json_error("feature_unavailable", "CRM ist nicht verfügbar.", status=501)
    try:
        quote = quotes_get(current_tenant(), quote_id)  # type: ignore
    except ValueError as exc:
        return _crm_error_response(exc, "Angebot nicht gefunden.", not_found=True)
    return jsonify(ok=True, quote=quote)


@bp.post("/api/quotes/<quote_id>/items")
@login_required
@require_role("OPERATOR")
def api_quote_add_item(quote_id: str):
    if not callable(quotes_add_item):
        return json_error("feature_unavailable", "CRM ist nicht verfügbar.", status=501)
    payload = request.get_json(silent=True) or {}
    try:
        quote = quotes_add_item(  # type: ignore
            tenant_id=current_tenant(),
            quote_id=quote_id,
            description=payload.get("description") or "",
            qty=float(payload.get("qty") or 0),
            unit_price_cents=int(payload.get("unit_price_cents") or 0),
        )
    except ValueError as exc:
        return _crm_error_response(exc, "Position konnte nicht angelegt werden.")
    return jsonify(ok=True, quote=quote)


@bp.post("/api/emails/import")
@login_required
@require_role("OPERATOR")
def api_emails_import():
    if not callable(emails_import_eml):
        return json_error(
            "feature_unavailable", "E-Mail-Import ist nicht verfügbar.", status=501
        )
    f = request.files.get("file")
    if f is None:
        return json_error("validation_error", "Bitte .eml-Datei hochladen.", status=400)
    filename = (f.filename or "").lower()
    if not filename.endswith(".eml"):
        return json_error(
            "validation_error", "Nur .eml-Dateien sind erlaubt.", status=400
        )

    max_bytes = int(current_app.config.get("MAX_EML_BYTES", 10 * 1024 * 1024))
    raw = f.read(max_bytes + 1) or b""
    if not raw:
        return json_error("validation_error", "Datei ist leer.", status=400)
    if len(raw) > max_bytes:
        return json_error(
            "payload_too_large", "Datei überschreitet das Upload-Limit.", status=413
        )

    try:
        email_id = emails_import_eml(  # type: ignore
            tenant_id=current_tenant(),
            eml_bytes=raw,
            customer_id=(request.form.get("customer_id") or None),
            contact_id=(request.form.get("contact_id") or None),
            source_notes=(request.form.get("notes") or None),
        )
    except ValueError as exc:
        return _crm_error_response(exc, "E-Mail konnte nicht importiert werden.")
    return jsonify(ok=True, email_id=email_id)


def _lead_read_only_response(api: bool = True):
    rid = getattr(g, "request_id", "")
    if api:
        return (
            jsonify({"ok": False, "error_code": "read_only", "request_id": rid}),
            403,
        )
    return (
        render_template(
            "lead_intake/partials/_error.html",
            message="Read-only mode aktiv. Schreibaktionen sind deaktiviert.",
            request_id=rid,
        ),
        403,
    )


def _lead_mutation_guard(api: bool = True):
    if bool(current_app.config.get("READ_ONLY", False)):
        return _lead_read_only_response(api=api)
    return None


def _lead_api_error(code: str, message: str, status: int = 400):
    rid = getattr(g, "request_id", "")
    return (
        jsonify(
            {
                "ok": False,
                "error": {
                    "code": code,
                    "message": message,
                    "details": {},
                    "request_id": rid,
                },
            }
        ),
        status,
    )


_LEAD_COLLISION_ROUTE_KEYS = {
    "lead_claim",
    "lead_claim_force",
    "lead_claim_release",
    "lead_screen_accept",
    "lead_screen_ignore",
    "lead_priority",
    "lead_assign",
    "lead_convert",
}

_LEAD_COLLISION_ENDPOINT_KEYS = {
    "web.leads_claim_action": "lead_claim",
    "web.leads_claim_force_action": "lead_claim_force",
    "web.leads_claim_release_action": "lead_claim_release",
    "web.leads_screen_accept_action": "lead_screen_accept",
    "web.leads_screen_ignore_action": "lead_screen_ignore",
    "web.leads_priority_action": "lead_priority",
    "web.leads_assign_action": "lead_assign",
    "web.api_leads_claim": "lead_claim",
    "web.api_leads_release_claim": "lead_claim_release",
    "web.api_leads_screen_accept": "lead_screen_accept",
    "web.api_leads_screen_ignore": "lead_screen_ignore",
    "web.api_leads_priority": "lead_priority",
    "web.api_leads_assign": "lead_assign",
    "web.leads_convert_action": "lead_convert",
    "web.api_leads_convert": "lead_convert",
}


def _lead_collision_route_key(route_key: str | None = None) -> str:
    candidate = str(route_key or "").strip().lower()
    if not candidate:
        endpoint = str(getattr(request, "endpoint", "") or "")
        candidate = _LEAD_COLLISION_ENDPOINT_KEYS.get(endpoint, "")
    if candidate in _LEAD_COLLISION_ROUTE_KEYS:
        return candidate
    return "lead_claim"


def _lead_user_agent_hash() -> str:
    ua = str(request.headers.get("User-Agent") or "")
    hashed = ua_hmac_sha256_hex(ua)
    return str(hashed or "")


def _emit_lead_claim_collision(
    details: dict[str, Any] | None,
    *,
    route_key: str | None = None,
) -> None:
    d = details or {}
    lead_id = str(d.get("lead_id") or "").strip()
    if not lead_id:
        return
    claimed_by = str(d.get("claimed_by") or "").strip()
    try:
        with core._DB_LOCK:  # type: ignore[attr-defined]
            con = core._db()  # type: ignore[attr-defined]
            try:
                event_append(
                    event_type="lead_claim_collision",
                    entity_type="lead",
                    entity_id=entity_id_int(lead_id),
                    payload={
                        "schema_version": 1,
                        "source": "web/lead_claim_guard",
                        "actor_user_id": current_user() or None,
                        "tenant_id": current_tenant(),
                        "data": {
                            "lead_id": lead_id,
                            "claimed_by_user_id": claimed_by,
                            "route_key": _lead_collision_route_key(route_key),
                            "ua_hash": _lead_user_agent_hash(),
                        },
                    },
                    con=con,
                )
                con.commit()
            finally:
                con.close()
    except Exception:
        # collision metrics are best-effort and must not break response flow
        return


def _lead_claim_conflict_message(details: dict[str, Any] | None) -> str:
    d = details or {}
    by = str(d.get("claimed_by") or "jemand")
    until = str(d.get("claimed_until") or "")
    suffix = f" bis {until}" if until else ""
    return f"Lead ist derzeit von {by} geclaimt{suffix}."


def _lead_claim_error_response(
    exc: Exception,
    *,
    api: bool,
    fallback_message: str,
    status: int = 409,
    route_key: str | None = None,
):
    code = str(exc)
    details = getattr(exc, "details", {}) if hasattr(exc, "details") else {}
    if code == "lead_claimed":
        _emit_lead_claim_collision(details, route_key=route_key)
        msg = _lead_claim_conflict_message(details)
        if api:
            return _lead_api_error("lead_claimed", msg, status)
        return (
            render_template(
                "lead_intake/partials/_claim_error.html",
                message=msg,
                request_id=getattr(g, "request_id", ""),
            ),
            status,
        )
    if code == "not_owner":
        msg = "Nur der Claim-Owner kann diese Aktion ausführen."
        if api:
            return _lead_api_error("not_owner", msg, status)
        return (
            render_template(
                "lead_intake/partials/_claim_error.html",
                message=msg,
                request_id=getattr(g, "request_id", ""),
            ),
            status,
        )
    if api:
        return _lead_api_error("validation_error", fallback_message, 400)
    return (
        render_template(
            "lead_intake/partials/_claim_error.html",
            message=fallback_message,
            request_id=getattr(g, "request_id", ""),
        ),
        400,
    )


def _decorate_leads_with_claims(
    tenant_id: str, leads: list[dict[str, Any]]
) -> list[dict[str, Any]]:
    ids = [str(r.get("id") or "") for r in leads if str(r.get("id") or "")]
    claim_map = lead_claims_for_leads(tenant_id, ids) if ids else {}
    out: list[dict[str, Any]] = []
    for row in leads:
        rid = str(row.get("id") or "")
        claim = claim_map.get(rid) if claim_map else None
        next_row = dict(row)
        next_row["claim"] = claim
        out.append(next_row)
    return out


def _lead_tab_filters(tab: str, user_id: str) -> dict[str, Any]:
    t = (tab or "all").strip().lower()
    if t == "screening":
        return {"status": "screening"}
    if t == "priority":
        return {"priority_only": True}
    if t == "assigned":
        return {"assigned_to": user_id}
    if t == "due_today":
        return {"due_mode": "today"}
    if t == "overdue":
        return {"due_mode": "overdue"}
    if t == "blocked":
        return {"blocked_only": True}
    return {}


def _lead_rows_for_request(
    tenant_id: str, tab: str, user_id: str
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    status = (request.args.get("status") or "").strip().lower() or None
    source = (request.args.get("source") or "").strip().lower() or None
    q = (request.args.get("q") or "").strip() or None
    page = _clamp_page(request.args.get("page"))
    page_size = _clamp_page_size(request.args.get("page_size"), default=25)
    offset = (page - 1) * page_size

    kwargs = _lead_tab_filters(tab, user_id)
    rows = leads_list(
        tenant_id,
        status=status,
        source=source,
        q=q,
        limit=page_size,
        offset=offset,
        priority_only=bool(kwargs.get("priority_only", False)),
        pinned_only=bool(kwargs.get("pinned_only", False)),
        assigned_to=kwargs.get("assigned_to"),
        due_mode=kwargs.get("due_mode"),
        blocked_only=bool(kwargs.get("blocked_only", False)),
    )
    meta = {
        "status": status or "",
        "source": source or "",
        "q": q or "",
        "page": page,
        "page_size": page_size,
        "has_more": len(rows) == page_size,
        "tab": tab,
    }
    return _decorate_leads_with_claims(tenant_id, rows), meta


@bp.get("/leads/inbox")
@login_required
def leads_inbox_page():
    tenant_id = current_tenant()
    tab = (request.args.get("tab") or "screening").strip().lower()
    if tab not in {
        "screening",
        "priority",
        "assigned",
        "due_today",
        "overdue",
        "blocked",
        "all",
    }:
        tab = "screening"
    user_id = current_user() or ""
    try:
        leads, meta = _lead_rows_for_request(tenant_id, tab, user_id)
    except ValueError:
        leads, meta = (
            [],
            {
                "status": "",
                "source": "",
                "q": "",
                "page": 1,
                "page_size": 25,
                "has_more": False,
                "tab": tab,
            },
        )

    counts = leads_inbox_counts(tenant_id, user_id)
    content = render_template(
        "lead_intake/inbox.html",
        leads=leads,
        counts=counts,
        read_only=bool(current_app.config.get("READ_ONLY", False)),
        **meta,
    )
    return _render_base(content, active_tab="leads")


@bp.get("/leads/new")
@login_required
def leads_new_page():
    content = render_template(
        "lead_intake/lead_form.html",
        read_only=bool(current_app.config.get("READ_ONLY", False)),
    )
    return _render_base(content, active_tab="leads")


@bp.get("/leads/<lead_id>")
@login_required
def lead_detail_page(lead_id: str):
    tenant_id = current_tenant()
    lead = leads_get(tenant_id, lead_id)
    if not lead:
        return _lead_api_error("not_found", "Lead nicht gefunden.", status=404)
    timeline = lead_timeline(tenant_id, lead_id, limit=100)
    claim = lead_claim_get(tenant_id, lead_id)
    content = render_template(
        "lead_intake/lead_detail.html",
        lead=lead,
        timeline=timeline,
        claim=claim,
        current_user_id=current_user() or "",
        read_only=bool(current_app.config.get("READ_ONLY", False)),
        link_entity_type="lead",
        link_entity_id=lead_id,
    )
    return _render_base(content, active_tab="leads")


@bp.get("/leads/<lead_id>/convert")
@login_required
def lead_convert_page(lead_id: str):
    tenant_id = current_tenant()
    lead = leads_get(tenant_id, lead_id)
    if not lead:
        return _lead_api_error("not_found", "Lead nicht gefunden.", status=404)
    claim = lead_claim_get(tenant_id, lead_id)
    content = render_template(
        "lead_intake/lead_convert_confirm.html",
        lead=lead,
        claim=claim,
        current_user_id=current_user() or "",
        read_only=bool(current_app.config.get("READ_ONLY", False)),
    )
    return _render_base(content, active_tab="leads")


@bp.get("/leads/_table")
@login_required
def leads_table_partial():
    tenant_id = current_tenant()
    tab = (request.args.get("tab") or "screening").strip().lower()
    user_id = current_user() or ""
    try:
        leads, meta = _lead_rows_for_request(tenant_id, tab, user_id)
    except ValueError:
        leads, meta = (
            [],
            {
                "status": "",
                "source": "",
                "q": "",
                "page": 1,
                "page_size": 25,
                "has_more": False,
                "tab": tab,
            },
        )
    return render_template("lead_intake/partials/_table.html", leads=leads, **meta)


@bp.get("/leads/_timeline/<lead_id>")
@login_required
def lead_timeline_partial(lead_id: str):
    tenant_id = current_tenant()
    timeline = lead_timeline(tenant_id, lead_id, limit=100)
    return render_template("lead_intake/partials/_timeline.html", timeline=timeline)


@bp.get("/leads/_status/<lead_id>")
@login_required
def lead_status_partial(lead_id: str):
    tenant_id = current_tenant()
    lead = leads_get(tenant_id, lead_id)
    if not lead:
        return render_template(
            "lead_intake/partials/_status.html",
            lead={
                "id": lead_id,
                "status": "unknown",
                "priority": "normal",
                "pinned": 0,
                "assigned_to": None,
                "response_due": None,
            },
        )
    return render_template("lead_intake/partials/_status.html", lead=lead)


@bp.get("/leads/_claim/<lead_id>")
@login_required
def lead_claim_partial(lead_id: str):
    tenant_id = current_tenant()
    lead = leads_get(tenant_id, lead_id)
    if not lead:
        return (
            render_template(
                "lead_intake/partials/_claim_error.html",
                message="Lead nicht gefunden.",
                request_id=getattr(g, "request_id", ""),
            ),
            404,
        )
    claim = lead_claim_get(tenant_id, lead_id)
    return render_template(
        "lead_intake/partials/_claim_panel.html",
        lead=lead,
        claim=claim,
        current_user_id=current_user() or "",
        read_only=bool(current_app.config.get("READ_ONLY", False)),
    )


def _lead_payload() -> dict[str, Any]:
    if request.is_json:
        return request.get_json(silent=True) or {}
    return {k: v for k, v in request.form.items()}


@bp.post("/leads")
@login_required
@require_role("OPERATOR")
def leads_create_action():
    guarded = _lead_mutation_guard(api=not _is_htmx())
    if guarded is not None:
        return guarded
    payload = _lead_payload()
    try:
        lead_id = leads_create(
            tenant_id=current_tenant(),
            source=(payload.get("source") or "manual"),
            contact_name=(payload.get("contact_name") or ""),
            contact_email=(payload.get("contact_email") or ""),
            contact_phone=(payload.get("contact_phone") or ""),
            subject=(payload.get("subject") or ""),
            message=(payload.get("message") or ""),
            customer_id=(payload.get("customer_id") or None),
            notes=(payload.get("notes") or None),
            actor_user_id=current_user() or None,
        )
    except ValueError as exc:
        code = str(exc)
        if code == "read_only":
            return _lead_mutation_guard(api=not _is_htmx())
        if code == "not_found":
            return _lead_api_error("not_found", "Kunde nicht gefunden.", 404)
        if code == "db_locked":
            return _lead_api_error("db_locked", "Datenbank gesperrt.", 503)
        if _is_htmx():
            return (
                render_template(
                    "lead_intake/partials/_error.html",
                    message="Ungültige Lead-Daten.",
                    request_id=getattr(g, "request_id", ""),
                ),
                400,
            )
        return _lead_api_error("validation_error", "Ungültige Lead-Daten.", 400)

    if _is_htmx():
        return redirect(url_for("web.lead_detail_page", lead_id=lead_id))
    return jsonify({"ok": True, "lead_id": lead_id})


@bp.post("/leads/<lead_id>/status")
@login_required
@require_role("OPERATOR")
@require_lead_access("leads_status")
def leads_status_action(lead_id: str):
    guarded = _lead_mutation_guard(api=not _is_htmx())
    if guarded is not None:
        return guarded
    payload = _lead_payload()
    try:
        leads_update_status(
            current_tenant(),
            lead_id,
            payload.get("status") or "",
            actor_user_id=current_user() or None,
        )
    except ValueError as exc:
        code = str(exc)
        if code == "read_only":
            return _lead_mutation_guard(api=not _is_htmx())
        if code == "not_found":
            return _lead_api_error("not_found", "Lead nicht gefunden.", 404)
        if code == "db_locked":
            return _lead_api_error("db_locked", "Datenbank gesperrt.", 503)
        return _lead_api_error("validation_error", "Ungültiger Status.", 400)

    if _is_htmx():
        return lead_status_partial(lead_id)
    return jsonify({"ok": True})


@bp.post("/leads/<lead_id>/convert")
@login_required
@require_role("OPERATOR")
@require_lead_access("leads_convert")
def leads_convert_action(lead_id: str):
    guarded = _lead_mutation_guard(api=not _is_htmx())
    if guarded is not None:
        return guarded
    payload = _lead_payload()
    mapping = {
        "deal_title": payload.get("deal_title") or "",
        "customer_name": payload.get("customer_name") or "",
        "use_subject_title": str(payload.get("use_subject_title") or "").strip().lower()
        in {"1", "true", "on", "yes"},
        "use_contact_name": str(payload.get("use_contact_name") or "").strip().lower()
        in {"1", "true", "on", "yes"},
    }
    try:
        out = lead_convert_to_deal_quote(
            current_tenant(),
            lead_id,
            actor_user_id=current_user() or None,
            mapping=mapping,
        )
    except ConflictError as exc:
        return _lead_claim_error_response(
            exc,
            api=not _is_htmx(),
            fallback_message="Konvertierung fehlgeschlagen.",
            status=409,
            route_key="lead_convert",
        )
    except ValueError as exc:
        code = str(exc)
        if code == "read_only":
            return _lead_mutation_guard(api=not _is_htmx())
        if code == "not_found":
            return _lead_api_error("not_found", "Lead nicht gefunden.", 404)
        if code == "db_locked":
            return _lead_api_error("db_locked", "Datenbank gesperrt.", 503)
        if _is_htmx():
            return (
                render_template(
                    "lead_intake/partials/_claim_error.html",
                    message="Konvertierung fehlgeschlagen.",
                    request_id=getattr(g, "request_id", ""),
                ),
                400,
            )
        return _lead_api_error("validation_error", "Konvertierung fehlgeschlagen.", 400)

    quote_id = str(out.get("quote_id") or "")
    if _is_htmx() or not request.is_json:
        if quote_id:
            return redirect(url_for("web.crm_quote_detail", quote_id=quote_id))
        return redirect(url_for("web.lead_detail_page", lead_id=lead_id))
    return jsonify({"ok": True, **out})


@bp.post("/leads/<lead_id>/claim")
@login_required
@require_role("OPERATOR")
def leads_claim_action(lead_id: str):
    guarded = _lead_mutation_guard(api=not _is_htmx())
    if guarded is not None:
        return guarded
    payload = _lead_payload()
    ttl_seconds = payload.get("ttl_seconds") or request.args.get("ttl_seconds") or 900
    try:
        lead_claim(
            current_tenant(),
            lead_id,
            actor_user_id=current_user() or "",
            ttl_seconds=int(ttl_seconds),
            force=False,
        )
    except ConflictError as exc:
        return _lead_claim_error_response(
            exc,
            api=not _is_htmx(),
            fallback_message="Lead kann nicht geclaimt werden.",
            status=409,
        )
    except ValueError as exc:
        code = str(exc)
        if code == "not_found":
            return _lead_api_error("not_found", "Lead nicht gefunden.", 404)
        if code == "db_locked":
            return _lead_api_error("db_locked", "Datenbank gesperrt.", 503)
        return _lead_api_error("validation_error", "Claim fehlgeschlagen.", 400)
    if _is_htmx():
        return lead_claim_partial(lead_id)
    return jsonify({"ok": True})


@bp.post("/leads/<lead_id>/claim/force")
@login_required
@require_role("OPERATOR")
def leads_claim_force_action(lead_id: str):
    guarded = _lead_mutation_guard(api=not _is_htmx())
    if guarded is not None:
        return guarded
    payload = _lead_payload()
    ttl_seconds = payload.get("ttl_seconds") or request.args.get("ttl_seconds") or 900
    try:
        lead_claim(
            current_tenant(),
            lead_id,
            actor_user_id=current_user() or "",
            ttl_seconds=int(ttl_seconds),
            force=True,
        )
    except ConflictError as exc:
        return _lead_claim_error_response(
            exc,
            api=not _is_htmx(),
            fallback_message="Force-Claim fehlgeschlagen.",
            status=409,
        )
    except ValueError as exc:
        code = str(exc)
        if code == "not_found":
            return _lead_api_error("not_found", "Lead nicht gefunden.", 404)
        if code == "db_locked":
            return _lead_api_error("db_locked", "Datenbank gesperrt.", 503)
        return _lead_api_error("validation_error", "Force-Claim fehlgeschlagen.", 400)
    if _is_htmx():
        return lead_claim_partial(lead_id)
    return jsonify({"ok": True})


@bp.post("/leads/<lead_id>/release")
@login_required
@require_role("OPERATOR")
def leads_claim_release_action(lead_id: str):
    guarded = _lead_mutation_guard(api=not _is_htmx())
    if guarded is not None:
        return guarded
    try:
        lead_release_claim(
            current_tenant(),
            lead_id,
            actor_user_id=current_user() or "",
            reason="manual",
        )
    except ConflictError as exc:
        return _lead_claim_error_response(
            exc,
            api=not _is_htmx(),
            fallback_message="Claim kann nicht freigegeben werden.",
            status=409,
        )
    except ValueError as exc:
        code = str(exc)
        if code == "not_found":
            return _lead_api_error("not_found", "Claim nicht gefunden.", 404)
        if code == "db_locked":
            return _lead_api_error("db_locked", "Datenbank gesperrt.", 503)
        return _lead_api_error("validation_error", "Claim-Release fehlgeschlagen.", 400)
    if _is_htmx():
        return lead_claim_partial(lead_id)
    return jsonify({"ok": True})


@bp.post("/leads/claims/expire-now")
@login_required
@require_role("OPERATOR")
def leads_claims_expire_now_action():
    guarded = _lead_mutation_guard(api=not _is_htmx())
    if guarded is not None:
        return guarded
    payload = _lead_payload()
    try:
        count = lead_claims_auto_expire(
            current_tenant(),
            max_actions=int(payload.get("max_actions") or 200),
            actor_user_id=current_user() or None,
        )
    except ValueError as exc:
        code = str(exc)
        if code == "db_locked":
            return _lead_api_error("db_locked", "Datenbank gesperrt.", 503)
        return _lead_api_error("validation_error", "Expire fehlgeschlagen.", 400)
    if _is_htmx():
        return redirect(url_for("web.leads_inbox_page"))
    if request.is_json or request.path.startswith("/api/"):
        return jsonify({"ok": True, "expired": count})
    return redirect(url_for("web.leads_inbox_page"))


@bp.post("/leads/<lead_id>/screen/accept")
@login_required
@require_role("OPERATOR")
@require_lead_access("leads_screen_accept")
def leads_screen_accept_action(lead_id: str):
    guarded = _lead_mutation_guard(api=not _is_htmx())
    if guarded is not None:
        return guarded
    try:
        leads_screen_accept(
            current_tenant(), lead_id, actor_user_id=current_user() or None
        )
    except ConflictError as exc:
        return _lead_claim_error_response(
            exc,
            api=not _is_htmx(),
            fallback_message="Aktion fehlgeschlagen.",
            status=409,
        )
    except ValueError as exc:
        code = str(exc)
        if code == "not_found":
            return _lead_api_error("not_found", "Lead nicht gefunden.", 404)
        if code == "db_locked":
            return _lead_api_error("db_locked", "Datenbank gesperrt.", 503)
        return _lead_api_error("validation_error", "Aktion fehlgeschlagen.", 400)
    if _is_htmx():
        return lead_status_partial(lead_id)
    return jsonify({"ok": True})


@bp.post("/leads/<lead_id>/screen/ignore")
@login_required
@require_role("OPERATOR")
@require_lead_access("leads_screen_ignore")
def leads_screen_ignore_action(lead_id: str):
    guarded = _lead_mutation_guard(api=not _is_htmx())
    if guarded is not None:
        return guarded
    payload = _lead_payload()
    try:
        leads_screen_ignore(
            current_tenant(),
            lead_id,
            actor_user_id=current_user() or None,
            reason=payload.get("reason") or None,
        )
    except ConflictError as exc:
        return _lead_claim_error_response(
            exc,
            api=not _is_htmx(),
            fallback_message="Aktion fehlgeschlagen.",
            status=409,
        )
    except ValueError as exc:
        code = str(exc)
        if code == "not_found":
            return _lead_api_error("not_found", "Lead nicht gefunden.", 404)
        if code == "db_locked":
            return _lead_api_error("db_locked", "Datenbank gesperrt.", 503)
        return _lead_api_error("validation_error", "Aktion fehlgeschlagen.", 400)
    if _is_htmx():
        return lead_status_partial(lead_id)
    return jsonify({"ok": True})


@bp.post("/leads/<lead_id>/priority")
@login_required
@require_role("OPERATOR")
@require_lead_access("leads_priority")
def leads_priority_action(lead_id: str):
    guarded = _lead_mutation_guard(api=not _is_htmx())
    if guarded is not None:
        return guarded
    payload = _lead_payload()
    pinned = (
        1
        if str(payload.get("pinned") or "0").strip().lower()
        in {"1", "true", "on", "yes"}
        else 0
    )
    try:
        leads_set_priority(
            current_tenant(),
            lead_id,
            payload.get("priority") or "normal",
            pinned,
            actor_user_id=current_user() or None,
        )
    except ConflictError as exc:
        return _lead_claim_error_response(
            exc,
            api=not _is_htmx(),
            fallback_message="Ungültige Priorität.",
            status=409,
        )
    except ValueError as exc:
        code = str(exc)
        if code == "not_found":
            return _lead_api_error("not_found", "Lead nicht gefunden.", 404)
        if code == "db_locked":
            return _lead_api_error("db_locked", "Datenbank gesperrt.", 503)
        return _lead_api_error("validation_error", "Ungültige Priorität.", 400)
    if _is_htmx():
        return lead_status_partial(lead_id)
    return jsonify({"ok": True})


@bp.post("/leads/<lead_id>/assign")
@login_required
@require_role("OPERATOR")
@require_lead_access("leads_assign")
def leads_assign_action(lead_id: str):
    guarded = _lead_mutation_guard(api=not _is_htmx())
    if guarded is not None:
        return guarded
    payload = _lead_payload()
    try:
        leads_assign(
            current_tenant(),
            lead_id,
            payload.get("assigned_to") or None,
            payload.get("response_due") or None,
            actor_user_id=current_user() or None,
        )
    except ConflictError as exc:
        return _lead_claim_error_response(
            exc,
            api=not _is_htmx(),
            fallback_message="Ungültige Zuweisung.",
            status=409,
        )
    except ValueError as exc:
        code = str(exc)
        if code == "not_found":
            return _lead_api_error("not_found", "Lead nicht gefunden.", 404)
        if code == "db_locked":
            return _lead_api_error("db_locked", "Datenbank gesperrt.", 503)
        return _lead_api_error("validation_error", "Ungültige Zuweisung.", 400)
    if _is_htmx():
        return lead_status_partial(lead_id)
    return jsonify({"ok": True})


@bp.post("/leads/blocklist/add")
@login_required
@require_role("OPERATOR")
def leads_blocklist_add_action():
    guarded = _lead_mutation_guard(api=not _is_htmx())
    if guarded is not None:
        return guarded
    payload = _lead_payload()
    try:
        leads_block_sender(
            current_tenant(),
            payload.get("kind") or "",
            payload.get("value") or "",
            actor_user_id=current_user() or None,
            reason=payload.get("reason") or None,
        )
    except ValueError as exc:
        code = str(exc)
        if code == "db_locked":
            return _lead_api_error("db_locked", "Datenbank gesperrt.", 503)
        return _lead_api_error("validation_error", "Ungültiger Blocklist-Eintrag.", 400)
    if _is_htmx():
        tenant_id = current_tenant()
        tab = (request.args.get("tab") or "screening").strip().lower()
        leads, meta = _lead_rows_for_request(tenant_id, tab, current_user() or "")
        return render_template("lead_intake/partials/_table.html", leads=leads, **meta)
    return jsonify({"ok": True})


@bp.post("/leads/<lead_id>/note")
@login_required
@require_role("OPERATOR")
@require_lead_access("leads_note_add")
def leads_note_action(lead_id: str):
    guarded = _lead_mutation_guard(api=not _is_htmx())
    if guarded is not None:
        return guarded
    payload = _lead_payload()
    try:
        leads_add_note(
            current_tenant(),
            lead_id,
            payload.get("note_text") or payload.get("note") or "",
            actor_user_id=current_user() or None,
        )
    except ValueError as exc:
        code = str(exc)
        if code == "not_found":
            return _lead_api_error("not_found", "Lead nicht gefunden.", 404)
        if code == "db_locked":
            return _lead_api_error("db_locked", "Datenbank gesperrt.", 503)
        return _lead_api_error("validation_error", "Ungültige Notiz.", 400)

    if _is_htmx():
        return lead_timeline_partial(lead_id)
    return jsonify({"ok": True})


@bp.post("/leads/<lead_id>/call-log")
@login_required
@require_role("OPERATOR")
@require_lead_access("leads_call_log_create")
def leads_call_log_action(lead_id: str):
    guarded = _lead_mutation_guard(api=not _is_htmx())
    if guarded is not None:
        return guarded
    payload = _lead_payload()
    try:
        call_id = call_logs_create(
            current_tenant(),
            lead_id,
            payload.get("caller_name") or "",
            payload.get("caller_phone") or "",
            payload.get("direction") or "inbound",
            int(payload.get("duration_seconds"))
            if payload.get("duration_seconds")
            else None,
            payload.get("notes"),
            actor_user_id=current_user() or None,
        )
    except ValueError as exc:
        code = str(exc)
        if code == "not_found":
            return _lead_api_error("not_found", "Lead nicht gefunden.", 404)
        if code == "db_locked":
            return _lead_api_error("db_locked", "Datenbank gesperrt.", 503)
        return _lead_api_error("validation_error", "Ungültige Call-Log Daten.", 400)

    if _is_htmx():
        return lead_timeline_partial(lead_id)
    return jsonify({"ok": True, "call_log_id": call_id})


@bp.post("/leads/<lead_id>/appointment")
@login_required
@require_role("OPERATOR")
@require_lead_access("leads_appointment_create")
def leads_appointment_action(lead_id: str):
    guarded = _lead_mutation_guard(api=not _is_htmx())
    if guarded is not None:
        return guarded
    payload = _lead_payload()
    try:
        req_id = appointment_requests_create(
            current_tenant(),
            lead_id,
            payload.get("requested_date") or None,
            payload.get("notes") or None,
            actor_user_id=current_user() or None,
        )
    except ValueError as exc:
        code = str(exc)
        if code == "not_found":
            return _lead_api_error("not_found", "Lead nicht gefunden.", 404)
        if code == "db_locked":
            return _lead_api_error("db_locked", "Datenbank gesperrt.", 503)
        return _lead_api_error("validation_error", "Ungültige Termin-Anfrage.", 400)

    if _is_htmx():
        return lead_timeline_partial(lead_id)
    return jsonify({"ok": True, "appointment_request_id": req_id})


@bp.get("/api/leads")
@login_required
def api_leads_list():
    try:
        tab = (request.args.get("tab") or "all").strip().lower()
        filters = _lead_tab_filters(tab, current_user() or "")
        rows = leads_list(
            current_tenant(),
            status=(request.args.get("status") or None),
            source=(request.args.get("source") or None),
            q=(request.args.get("q") or None),
            limit=min(int(request.args.get("limit") or 50), 200),
            offset=max(int(request.args.get("offset") or 0), 0),
            priority_only=bool(filters.get("priority_only", False)),
            pinned_only=bool(filters.get("pinned_only", False)),
            assigned_to=filters.get("assigned_to"),
            due_mode=filters.get("due_mode"),
            blocked_only=bool(filters.get("blocked_only", False)),
        )
    except ValueError:
        return _lead_api_error("validation_error", "Ungültige Filter.", 400)
    return jsonify({"ok": True, "items": rows})


@bp.post("/api/leads")
@login_required
@require_role("OPERATOR")
def api_leads_create():
    guarded = _lead_mutation_guard(api=True)
    if guarded is not None:
        return guarded
    payload = request.get_json(silent=True) or {}
    try:
        lead_id = leads_create(
            tenant_id=current_tenant(),
            source=(payload.get("source") or "manual"),
            contact_name=(payload.get("contact_name") or ""),
            contact_email=(payload.get("contact_email") or ""),
            contact_phone=(payload.get("contact_phone") or ""),
            subject=(payload.get("subject") or ""),
            message=(payload.get("message") or ""),
            customer_id=(payload.get("customer_id") or None),
            notes=(payload.get("notes") or None),
            actor_user_id=current_user() or None,
        )
    except ValueError as exc:
        code = str(exc)
        if code == "read_only":
            return _lead_read_only_response(api=True)
        if code == "not_found":
            return _lead_api_error("not_found", "Kunde nicht gefunden.", 404)
        if code == "db_locked":
            return _lead_api_error("db_locked", "Datenbank gesperrt.", 503)
        return _lead_api_error("validation_error", "Ungültige Lead-Daten.", 400)
    return jsonify({"ok": True, "lead_id": lead_id})


@bp.get("/api/leads/<lead_id>")
@login_required
def api_leads_get(lead_id: str):
    row = leads_get(current_tenant(), lead_id)
    if not row:
        return _lead_api_error("not_found", "Lead nicht gefunden.", 404)
    return jsonify({"ok": True, "item": row})


@bp.post("/api/leads/<lead_id>/convert")
@login_required
@require_role("OPERATOR")
@require_lead_access("leads_convert")
def api_leads_convert(lead_id: str):
    guarded = _lead_mutation_guard(api=True)
    if guarded is not None:
        return guarded
    payload = request.get_json(silent=True) or {}
    mapping = {
        "deal_title": payload.get("deal_title") or "",
        "customer_name": payload.get("customer_name") or "",
        "use_subject_title": bool(payload.get("use_subject_title", False)),
        "use_contact_name": bool(payload.get("use_contact_name", False)),
    }
    try:
        out = lead_convert_to_deal_quote(
            current_tenant(),
            lead_id,
            actor_user_id=current_user() or None,
            mapping=mapping,
        )
    except ConflictError as exc:
        return _lead_claim_error_response(
            exc,
            api=True,
            fallback_message="Konvertierung fehlgeschlagen.",
            status=409,
            route_key="lead_convert",
        )
    except ValueError as exc:
        code = str(exc)
        if code == "read_only":
            return _lead_read_only_response(api=True)
        if code == "not_found":
            return _lead_api_error("not_found", "Lead nicht gefunden.", 404)
        if code == "db_locked":
            return _lead_api_error("db_locked", "Datenbank gesperrt.", 503)
        return _lead_api_error("validation_error", "Konvertierung fehlgeschlagen.", 400)
    return jsonify({"ok": True, **out})


@bp.post("/api/leads/<lead_id>/claim")
@login_required
@require_role("OPERATOR")
def api_leads_claim(lead_id: str):
    guarded = _lead_mutation_guard(api=True)
    if guarded is not None:
        return guarded
    payload = request.get_json(silent=True) or {}
    try:
        claim = lead_claim(
            current_tenant(),
            lead_id,
            actor_user_id=current_user() or "",
            ttl_seconds=int(payload.get("ttl_seconds") or 900),
            force=bool(payload.get("force", False)),
        )
    except ConflictError as exc:
        return _lead_claim_error_response(
            exc,
            api=True,
            fallback_message="Claim fehlgeschlagen.",
            status=409,
        )
    except ValueError as exc:
        code = str(exc)
        if code == "not_found":
            return _lead_api_error("not_found", "Lead nicht gefunden.", 404)
        if code == "db_locked":
            return _lead_api_error("db_locked", "Datenbank gesperrt.", 503)
        return _lead_api_error("validation_error", "Claim fehlgeschlagen.", 400)
    return jsonify({"ok": True, "claim": claim})


@bp.post("/api/leads/<lead_id>/release")
@login_required
@require_role("OPERATOR")
def api_leads_release_claim(lead_id: str):
    guarded = _lead_mutation_guard(api=True)
    if guarded is not None:
        return guarded
    payload = request.get_json(silent=True) or {}
    try:
        lead_release_claim(
            current_tenant(),
            lead_id,
            actor_user_id=current_user() or "",
            reason=str(payload.get("reason") or "manual"),
        )
    except ConflictError as exc:
        return _lead_claim_error_response(
            exc,
            api=True,
            fallback_message="Claim-Release fehlgeschlagen.",
            status=409,
        )
    except ValueError as exc:
        code = str(exc)
        if code == "not_found":
            return _lead_api_error("not_found", "Claim nicht gefunden.", 404)
        if code == "db_locked":
            return _lead_api_error("db_locked", "Datenbank gesperrt.", 503)
        return _lead_api_error("validation_error", "Claim-Release fehlgeschlagen.", 400)
    return jsonify({"ok": True})


@bp.post("/api/leads/claims/expire-now")
@login_required
@require_role("OPERATOR")
def api_leads_claims_expire_now():
    guarded = _lead_mutation_guard(api=True)
    if guarded is not None:
        return guarded
    payload = request.get_json(silent=True) or {}
    try:
        count = lead_claims_auto_expire(
            current_tenant(),
            max_actions=int(payload.get("max_actions") or 200),
            actor_user_id=current_user() or None,
        )
    except ValueError as exc:
        code = str(exc)
        if code == "db_locked":
            return _lead_api_error("db_locked", "Datenbank gesperrt.", 503)
        return _lead_api_error("validation_error", "Expire fehlgeschlagen.", 400)
    return jsonify({"ok": True, "expired": count})


@bp.put("/api/leads/<lead_id>/status")
@login_required
@require_role("OPERATOR")
@require_lead_access("leads_status")
def api_leads_status(lead_id: str):
    guarded = _lead_mutation_guard(api=True)
    if guarded is not None:
        return guarded
    payload = request.get_json(silent=True) or {}
    try:
        leads_update_status(
            current_tenant(),
            lead_id,
            payload.get("status") or "",
            actor_user_id=current_user() or None,
        )
    except ValueError as exc:
        code = str(exc)
        if code == "read_only":
            return _lead_read_only_response(api=True)
        if code == "not_found":
            return _lead_api_error("not_found", "Lead nicht gefunden.", 404)
        if code == "db_locked":
            return _lead_api_error("db_locked", "Datenbank gesperrt.", 503)
        return _lead_api_error("validation_error", "Ungültiger Status.", 400)
    return jsonify({"ok": True})


@bp.post("/api/leads/<lead_id>/screen/accept")
@login_required
@require_role("OPERATOR")
@require_lead_access("leads_screen_accept")
def api_leads_screen_accept(lead_id: str):
    guarded = _lead_mutation_guard(api=True)
    if guarded is not None:
        return guarded
    try:
        leads_screen_accept(
            current_tenant(), lead_id, actor_user_id=current_user() or None
        )
    except ConflictError as exc:
        return _lead_claim_error_response(
            exc,
            api=True,
            fallback_message="Aktion fehlgeschlagen.",
            status=409,
        )
    except ValueError as exc:
        code = str(exc)
        if code == "not_found":
            return _lead_api_error("not_found", "Lead nicht gefunden.", 404)
        if code == "db_locked":
            return _lead_api_error("db_locked", "Datenbank gesperrt.", 503)
        return _lead_api_error("validation_error", "Aktion fehlgeschlagen.", 400)
    return jsonify({"ok": True})


@bp.post("/api/leads/<lead_id>/screen/ignore")
@login_required
@require_role("OPERATOR")
@require_lead_access("leads_screen_ignore")
def api_leads_screen_ignore(lead_id: str):
    guarded = _lead_mutation_guard(api=True)
    if guarded is not None:
        return guarded
    payload = request.get_json(silent=True) or {}
    try:
        leads_screen_ignore(
            current_tenant(),
            lead_id,
            actor_user_id=current_user() or None,
            reason=payload.get("reason") or None,
        )
    except ConflictError as exc:
        return _lead_claim_error_response(
            exc,
            api=True,
            fallback_message="Aktion fehlgeschlagen.",
            status=409,
        )
    except ValueError as exc:
        code = str(exc)
        if code == "not_found":
            return _lead_api_error("not_found", "Lead nicht gefunden.", 404)
        if code == "db_locked":
            return _lead_api_error("db_locked", "Datenbank gesperrt.", 503)
        return _lead_api_error("validation_error", "Aktion fehlgeschlagen.", 400)
    return jsonify({"ok": True})


@bp.put("/api/leads/<lead_id>/priority")
@login_required
@require_role("OPERATOR")
@require_lead_access("leads_priority")
def api_leads_priority(lead_id: str):
    guarded = _lead_mutation_guard(api=True)
    if guarded is not None:
        return guarded
    payload = request.get_json(silent=True) or {}
    try:
        leads_set_priority(
            current_tenant(),
            lead_id,
            payload.get("priority") or "normal",
            int(payload.get("pinned") or 0),
            actor_user_id=current_user() or None,
        )
    except ConflictError as exc:
        return _lead_claim_error_response(
            exc,
            api=True,
            fallback_message="Ungültige Priorität.",
            status=409,
        )
    except ValueError as exc:
        code = str(exc)
        if code == "not_found":
            return _lead_api_error("not_found", "Lead nicht gefunden.", 404)
        if code == "db_locked":
            return _lead_api_error("db_locked", "Datenbank gesperrt.", 503)
        return _lead_api_error("validation_error", "Ungültige Priorität.", 400)
    return jsonify({"ok": True})


@bp.put("/api/leads/<lead_id>/assign")
@login_required
@require_role("OPERATOR")
@require_lead_access("leads_assign")
def api_leads_assign(lead_id: str):
    guarded = _lead_mutation_guard(api=True)
    if guarded is not None:
        return guarded
    payload = request.get_json(silent=True) or {}
    try:
        leads_assign(
            current_tenant(),
            lead_id,
            payload.get("assigned_to") or None,
            payload.get("response_due") or None,
            actor_user_id=current_user() or None,
        )
    except ConflictError as exc:
        return _lead_claim_error_response(
            exc,
            api=True,
            fallback_message="Ungültige Zuweisung.",
            status=409,
        )
    except ValueError as exc:
        code = str(exc)
        if code == "not_found":
            return _lead_api_error("not_found", "Lead nicht gefunden.", 404)
        if code == "db_locked":
            return _lead_api_error("db_locked", "Datenbank gesperrt.", 503)
        return _lead_api_error("validation_error", "Ungültige Zuweisung.", 400)
    return jsonify({"ok": True})


@bp.post("/api/leads/blocklist")
@login_required
@require_role("OPERATOR")
def api_leads_blocklist_add():
    guarded = _lead_mutation_guard(api=True)
    if guarded is not None:
        return guarded
    payload = request.get_json(silent=True) or {}
    try:
        block_id = leads_block_sender(
            current_tenant(),
            payload.get("kind") or "",
            payload.get("value") or "",
            actor_user_id=current_user() or None,
            reason=payload.get("reason") or None,
        )
    except ValueError as exc:
        code = str(exc)
        if code == "db_locked":
            return _lead_api_error("db_locked", "Datenbank gesperrt.", 503)
        return _lead_api_error("validation_error", "Ungültiger Blocklist-Eintrag.", 400)
    return jsonify({"ok": True, "block_id": block_id})


@bp.post("/api/leads/<lead_id>/note")
@login_required
@require_role("OPERATOR")
@require_lead_access("leads_note_add")
def api_leads_note(lead_id: str):
    guarded = _lead_mutation_guard(api=True)
    if guarded is not None:
        return guarded
    payload = request.get_json(silent=True) or {}
    try:
        leads_add_note(
            current_tenant(),
            lead_id,
            payload.get("note_text") or payload.get("note") or "",
            actor_user_id=current_user() or None,
        )
    except ValueError as exc:
        code = str(exc)
        if code == "read_only":
            return _lead_read_only_response(api=True)
        if code == "not_found":
            return _lead_api_error("not_found", "Lead nicht gefunden.", 404)
        if code == "db_locked":
            return _lead_api_error("db_locked", "Datenbank gesperrt.", 503)
        return _lead_api_error("validation_error", "Ungültige Notiz.", 400)
    return jsonify({"ok": True})


@bp.post("/api/call-logs")
@login_required
@require_role("OPERATOR")
@require_lead_access("leads_call_log_create", lead_id_kw="lead_id")
def api_call_logs_create():
    guarded = _lead_mutation_guard(api=True)
    if guarded is not None:
        return guarded
    payload = request.get_json(silent=True) or {}
    try:
        call_id = call_logs_create(
            current_tenant(),
            payload.get("lead_id") or None,
            payload.get("caller_name") or "",
            payload.get("caller_phone") or "",
            payload.get("direction") or "inbound",
            int(payload.get("duration_seconds"))
            if payload.get("duration_seconds")
            else None,
            payload.get("notes"),
            actor_user_id=current_user() or None,
        )
    except ValueError as exc:
        code = str(exc)
        if code == "read_only":
            return _lead_read_only_response(api=True)
        if code == "not_found":
            return _lead_api_error("not_found", "Lead nicht gefunden.", 404)
        if code == "db_locked":
            return _lead_api_error("db_locked", "Datenbank gesperrt.", 503)
        return _lead_api_error("validation_error", "Ungültige Call-Log Daten.", 400)
    return jsonify({"ok": True, "call_log_id": call_id})


@bp.post("/api/appointment-requests")
@login_required
@require_role("OPERATOR")
@require_lead_access("leads_appointment_create", lead_id_kw="lead_id")
def api_appointment_requests_create():
    guarded = _lead_mutation_guard(api=True)
    if guarded is not None:
        return guarded
    payload = request.get_json(silent=True) or {}
    try:
        req_id = appointment_requests_create(
            current_tenant(),
            payload.get("lead_id") or "",
            payload.get("requested_date") or None,
            payload.get("notes") or None,
            actor_user_id=current_user() or None,
        )
    except ValueError as exc:
        code = str(exc)
        if code == "read_only":
            return _lead_read_only_response(api=True)
        if code == "not_found":
            return _lead_api_error("not_found", "Lead nicht gefunden.", 404)
        if code == "db_locked":
            return _lead_api_error("db_locked", "Datenbank gesperrt.", 503)
        return _lead_api_error("validation_error", "Ungültige Termin-Anfrage.", 400)
    return jsonify({"ok": True, "appointment_request_id": req_id})


@bp.put("/api/appointment-requests/<req_id>/status")
@login_required
@require_role("OPERATOR")
def api_appointment_requests_status(req_id: str):
    guarded = _lead_mutation_guard(api=True)
    if guarded is not None:
        return guarded
    payload = request.get_json(silent=True) or {}
    try:
        appointment_requests_update_status(
            current_tenant(),
            req_id,
            payload.get("status") or "",
            actor_user_id=current_user() or None,
        )
    except ValueError as exc:
        code = str(exc)
        if code == "read_only":
            return _lead_read_only_response(api=True)
        if code == "not_found":
            return _lead_api_error("not_found", "Termin-Anfrage nicht gefunden.", 404)
        if code == "db_locked":
            return _lead_api_error("db_locked", "Datenbank gesperrt.", 503)
        return _lead_api_error("validation_error", "Ungültiger Termin-Status.", 400)
    return jsonify({"ok": True})


@bp.get("/api/appointment-requests/<req_id>/ics")
@login_required
def api_appointment_request_ics(req_id: str):
    try:
        ics, fname = appointment_request_to_ics(current_tenant(), req_id)
    except ValueError:
        return _lead_api_error("not_found", "Termin-Anfrage nicht gefunden.", 404)
    resp = current_app.response_class(ics, mimetype="text/calendar; charset=utf-8")
    resp.headers["Content-Disposition"] = f'attachment; filename="{fname}"'
    return resp


@bp.get("/appointments/<req_id>/ics")
@login_required
def appointment_request_ics_alias(req_id: str):
    return api_appointment_request_ics(req_id)


def _automation_error(code: str, message: str, status: int = 400):
    rid = getattr(g, "request_id", "")
    return (
        jsonify(
            {
                "ok": False,
                "error": {
                    "code": code,
                    "message": message,
                    "details": {},
                    "request_id": rid,
                },
            }
        ),
        status,
    )


def _automation_read_only_response(api: bool = True):
    rid = getattr(g, "request_id", "")
    if api:
        return jsonify({"ok": False, "error_code": "read_only", "request_id": rid}), 403
    return (
        render_template(
            "lead_intake/partials/_error.html",
            message="Read-only mode aktiv. Schreibaktionen sind deaktiviert.",
            request_id=rid,
        ),
        403,
    )


def _automation_guard(api: bool = True):
    if bool(current_app.config.get("READ_ONLY", False)):
        return _automation_read_only_response(api=api)
    csrf = _csrf_guard(api=api)
    if csrf is not None:
        return csrf
    return None


_RULE_IMPORT_ALLOWED_KEYS = {
    "name",
    "description",
    "is_enabled",
    "max_executions_per_minute",
    "triggers",
    "conditions",
    "actions",
}
_RULE_COMPONENT_ALLOWED_KEYS = {
    "type",
    "trigger_type",
    "condition_type",
    "action_type",
    "config",
    "config_json",
}
_BUILDER_TRIGGER_ALLOWLIST = {"eventlog", "cron"}
_BUILDER_ACTION_ALLOWLIST = {
    "create_task",
    "create_postfach_draft",
    "create_followup",
    "email_draft",
    "email_send",
    "webhook",
}
_BUILDER_EMAIL_ALLOWED_PLACEHOLDERS = {
    "customer_name",
    "event_type",
    "trigger_ref",
    "thread_id",
    "entity_id",
    "tenant_id",
}
_BUILDER_EMAIL_SUBJECT_MAX_LENGTH = 255
_BUILDER_EMAIL_BODY_MAX_LENGTH = 20000
_BUILDER_TEMPLATE_VAR_PATTERN = re.compile(r"\{([a-zA-Z0-9_]+)\}")
_BUILDER_TEMPLATE_VAR_DOUBLE_PATTERN = re.compile(r"\{\{\s*([a-zA-Z0-9_]+)\s*\}\}")


def _split_recipients_csv(raw: Any) -> list[str]:
    if isinstance(raw, list):
        parts = [str(item or "").strip() for item in raw]
    else:
        text = str(raw or "")
        normalized = text.replace(";", ",").replace("\n", ",")
        parts = [part.strip() for part in normalized.split(",")]
    out: list[str] = []
    seen: set[str] = set()
    for value in parts:
        if not value:
            continue
        lower = value.lower()
        if "@" not in lower or "." not in lower.rsplit("@", 1)[-1]:
            continue
        if lower in seen:
            continue
        seen.add(lower)
        out.append(lower)
    return out


def _split_ids_csv(raw: Any) -> list[str]:
    if isinstance(raw, list):
        parts = [str(item or "").strip() for item in raw]
    else:
        text = str(raw or "")
        normalized = text.replace(";", ",").replace("\n", ",")
        parts = [part.strip() for part in normalized.split(",")]
    out: list[str] = []
    seen: set[str] = set()
    for value in parts:
        if not value or value in seen:
            continue
        seen.add(value)
        out.append(value)
    return out


def _extract_builder_template_vars(template: str) -> set[str]:
    text = str(template or "")
    names = set(_BUILDER_TEMPLATE_VAR_PATTERN.findall(text))
    names.update(_BUILDER_TEMPLATE_VAR_DOUBLE_PATTERN.findall(text))
    return {str(name or "").strip() for name in names if str(name or "").strip()}


def _builder_template_vars_allowed(template: str) -> bool:
    names = _extract_builder_template_vars(template)
    return names.issubset(_BUILDER_EMAIL_ALLOWED_PLACEHOLDERS)


def _builder_webhook_allowed_domains() -> set[str]:
    configured = getattr(Config, "WEBHOOK_ALLOWED_DOMAINS_LIST", None)
    if isinstance(configured, list):
        return {str(v).strip().lower() for v in configured if str(v).strip()}
    raw = str(getattr(Config, "WEBHOOK_ALLOWED_DOMAINS", "") or "")
    return {part.strip().lower() for part in raw.split(",") if part.strip()}


def _builder_webhook_url_allowed(url: str) -> bool:
    parsed = urllib.parse.urlparse(str(url or "").strip())
    if parsed.scheme.lower() != "https":
        return False
    if parsed.username or parsed.password:
        return False
    host = str(parsed.hostname or "").strip().lower()
    if not host or host in {"localhost", "127.0.0.1", "::1"}:
        return False
    try:
        ipaddress.ip_address(host)
        return False
    except ValueError:
        pass
    allowed = _builder_webhook_allowed_domains()
    return bool(allowed and host in allowed)


def _normalize_rule_component_for_import(item: Any, *, type_key: str) -> dict[str, Any]:
    if not isinstance(item, dict):
        raise ValueError("validation_error")
    unknown = set(item.keys()) - _RULE_COMPONENT_ALLOWED_KEYS
    if unknown:
        raise ValueError("validation_error")
    ctype = str(item.get(type_key) or item.get("type") or "").strip()
    if not ctype:
        raise ValueError("validation_error")
    if "config" in item:
        cfg = item.get("config")
    elif "config_json" in item:
        raw = item.get("config_json")
        cfg = json.loads(str(raw or "{}")) if not isinstance(raw, dict) else raw
    else:
        cfg = {}
    if not isinstance(cfg, dict):
        raise ValueError("validation_error")
    ctype_lower = ctype.lower()
    if type_key == "trigger_type":
        if ctype_lower not in _BUILDER_TRIGGER_ALLOWLIST:
            raise ValueError("validation_error")
        if ctype_lower == "cron":
            cron_expr = str(cfg.get("cron") or "").strip()
            if not cron_expr:
                raise ValueError("validation_error")
            parse_cron_expression(cron_expr)
            cfg = {"cron": cron_expr}
    if type_key == "action_type":
        if ctype_lower not in _BUILDER_ACTION_ALLOWLIST:
            raise ValueError("validation_error")
        if ctype_lower == "email_draft":
            allowed_keys = {
                "to",
                "subject",
                "body_template",
                "body",
                "requires_confirm",
                "account_id",
                "attachments",
            }
            if set(cfg.keys()) - allowed_keys:
                raise ValueError("validation_error")
            recipients = _split_recipients_csv(cfg.get("to"))
            subject = str(cfg.get("subject") or "").strip()
            body_template = str(
                cfg.get("body_template") or cfg.get("body") or ""
            ).strip()
            account_id = str(cfg.get("account_id") or "").strip()
            attachments = _split_ids_csv(cfg.get("attachments"))
            if not recipients:
                raise ValueError("validation_error")
            if (
                not subject
                or not body_template
                or len(subject) > _BUILDER_EMAIL_SUBJECT_MAX_LENGTH
                or len(body_template) > _BUILDER_EMAIL_BODY_MAX_LENGTH
                or not _builder_template_vars_allowed(body_template)
            ):
                raise ValueError("validation_error")
            cfg = {
                "to": recipients,
                "subject": subject,
                "body_template": body_template,
                "requires_confirm": True,
            }
            if account_id:
                cfg["account_id"] = account_id
            if attachments:
                cfg["attachments"] = attachments
        if ctype_lower == "email_send":
            allowed_keys = {
                "to",
                "subject",
                "body_template",
                "body",
                "requires_confirm",
                "account_id",
                "attachments",
            }
            if set(cfg.keys()) - allowed_keys:
                raise ValueError("validation_error")
            recipients = _split_recipients_csv(cfg.get("to"))
            subject = str(cfg.get("subject") or "").strip()
            body_template = str(
                cfg.get("body_template") or cfg.get("body") or ""
            ).strip()
            account_id = str(cfg.get("account_id") or "").strip()
            attachments = _split_ids_csv(cfg.get("attachments"))
            if not recipients or not subject or not body_template:
                raise ValueError("validation_error")
            if (
                len(subject) > _BUILDER_EMAIL_SUBJECT_MAX_LENGTH
                or len(body_template) > _BUILDER_EMAIL_BODY_MAX_LENGTH
                or not _builder_template_vars_allowed(body_template)
            ):
                raise ValueError("validation_error")
            cfg = {
                "to": recipients,
                "subject": subject,
                "body_template": body_template,
                "requires_confirm": True,
            }
            if account_id:
                cfg["account_id"] = account_id
            if attachments:
                cfg["attachments"] = attachments
        if ctype_lower == "webhook":
            allowed_keys = {"url", "method", "body_template", "headers"}
            if set(cfg.keys()) - allowed_keys:
                raise ValueError("validation_error")
            url_value = str(cfg.get("url") or "").strip()
            method = str(cfg.get("method") or "POST").strip().upper()
            body_template = str(cfg.get("body_template") or "{}")
            headers = cfg.get("headers") or {}
            if (
                not url_value
                or method != "POST"
                or not _builder_webhook_url_allowed(url_value)
                or not isinstance(headers, dict)
            ):
                raise ValueError("validation_error")
            for key in headers:
                lowered = str(key or "").strip().lower()
                if (
                    not lowered
                    or "auth" in lowered
                    or "token" in lowered
                    or lowered in {"cookie", "set-cookie"}
                ):
                    raise ValueError("validation_error")
            cfg = {
                "url": url_value,
                "method": "POST",
                "body_template": body_template,
                "headers": {str(k): str(v)[:300] for k, v in headers.items()},
            }
    return {type_key: ctype, "config": cfg}


def _normalize_rule_import_payload(payload: Any) -> dict[str, Any]:
    if not isinstance(payload, dict):
        raise ValueError("validation_error")
    unknown = set(payload.keys()) - _RULE_IMPORT_ALLOWED_KEYS
    if unknown:
        raise ValueError("validation_error")
    name = str(payload.get("name") or "").strip()
    if not name:
        raise ValueError("validation_error")
    description = str(payload.get("description") or "").strip()
    max_per_minute = int(payload.get("max_executions_per_minute") or 10)
    if max_per_minute < 1 or max_per_minute > 10000:
        raise ValueError("validation_error")

    out = {
        "name": name,
        "description": description,
        "is_enabled": False,
        "max_executions_per_minute": max_per_minute,
        "triggers": [],
        "conditions": [],
        "actions": [],
    }
    for key, type_key in (
        ("triggers", "trigger_type"),
        ("conditions", "condition_type"),
        ("actions", "action_type"),
    ):
        raw_list = payload.get(key) or []
        if not isinstance(raw_list, list):
            raise ValueError("validation_error")
        out[key] = [
            _normalize_rule_component_for_import(item, type_key=type_key)
            for item in raw_list
        ]
    return out


def _export_rule_payload(rule: dict[str, Any]) -> dict[str, Any]:
    return {
        "name": str(rule.get("name") or ""),
        "description": str(rule.get("description") or ""),
        "is_enabled": bool(rule.get("is_enabled")),
        "max_executions_per_minute": int(rule.get("max_executions_per_minute") or 10),
        "triggers": [
            {"trigger_type": str(t.get("type") or ""), "config": t.get("config") or {}}
            for t in (rule.get("triggers") or [])
            if isinstance(t, dict)
        ],
        "conditions": [
            {
                "condition_type": str(c.get("type") or ""),
                "config": c.get("config") or {},
            }
            for c in (rule.get("conditions") or [])
            if isinstance(c, dict)
        ],
        "actions": [
            {"action_type": str(a.get("type") or ""), "config": a.get("config") or {}}
            for a in (rule.get("actions") or [])
            if isinstance(a, dict)
        ],
    }


def _workflow_template_key_from_description(description: str) -> str:
    text = str(description or "")
    pattern = re.compile(
        r"\[" + re.escape(WORKFLOW_TEMPLATE_MARKER_PREFIX) + r"([a-z0-9_]+)\]"
    )
    match = pattern.search(text.lower())
    if not match:
        return ""
    return str(match.group(1) or "").strip()


def _workflow_summaries(tenant_id: str) -> list[dict[str, Any]]:
    rows = builder_rule_list(tenant_id=tenant_id)
    out: list[dict[str, Any]] = []
    for row in rows:
        rule_id = str(row.get("id") or "").strip()
        if not rule_id:
            continue
        description = str(row.get("description") or "")
        template_key = _workflow_template_key_from_description(description)
        if not template_key:
            continue
        logs = builder_execution_log_list(
            tenant_id=tenant_id, rule_id=rule_id, limit=50
        )
        out.append(
            {
                **row,
                "template_key": template_key,
                "run_count": len(logs),
                "last_status": str(logs[0].get("status") or "") if logs else "",
                "last_started_at": str(logs[0].get("started_at") or "") if logs else "",
            }
        )
    return out


def _workflow_install_rule(tenant_id: str, template_key: str) -> str:
    existing = _workflow_summaries(tenant_id)
    for row in existing:
        if str(row.get("template_key") or "") == template_key:
            return str(row.get("id") or "")

    tpl = get_workflow_template(template_key)
    if not tpl:
        raise ValueError("not_found")
    payload = _normalize_rule_import_payload(tpl.get("rule_payload") or {})
    desc = str(payload.get("description") or "").strip()
    marker = workflow_template_marker(template_key)
    payload["description"] = f"{desc}\n{marker}" if desc else marker
    return builder_rule_create(
        tenant_id=tenant_id,
        name=str(payload["name"]),
        description=str(payload["description"]),
        is_enabled=False,
        max_executions_per_minute=int(payload["max_executions_per_minute"]),
        triggers=list(payload.get("triggers") or []),
        conditions=list(payload.get("conditions") or []),
        actions=list(payload.get("actions") or []),
    )


@bp.get("/automation/rules")
@login_required
@require_role("OPERATOR")
def automation_rules_page():
    rows = automation_rule_list(current_tenant())
    content = render_template(
        "automation/rules.html",
        rules=rows,
        read_only=bool(current_app.config.get("READ_ONLY", False)),
    )
    return _render_base(content, active_tab="automation")


@bp.get("/automation/rules/new")
@login_required
@require_role("OPERATOR")
def automation_rule_new_page():
    content = render_template(
        "automation/rule_new.html",
        read_only=bool(current_app.config.get("READ_ONLY", False)),
    )
    return _render_base(content, active_tab="automation")


@bp.post("/automation/rules/create")
@login_required
@require_role("OPERATOR")
def automation_rule_create_action():
    guarded = _automation_guard(api=not _is_htmx())
    if guarded is not None:
        return guarded
    payload = (
        request.form if not request.is_json else (request.get_json(silent=True) or {})
    )
    try:
        rule_id = automation_rule_create(
            tenant_id=current_tenant(),
            name=str(payload.get("name") or ""),
            scope=str(payload.get("scope") or "leads"),
            condition_kind=str(payload.get("condition_kind") or ""),
            condition_json=str(payload.get("condition_json") or "{}"),
            action_list_json=str(payload.get("action_list_json") or "[]"),
            created_by=current_user() or "system",
        )
    except PermissionError:
        return _automation_read_only_response(api=not _is_htmx())
    except ValueError as exc:
        code = str(exc)
        if code == "db_locked":
            return _automation_error("db_locked", "Datenbank gesperrt.", 503)
        return _automation_error("validation_error", "Regel ungültig.", 400)
    if _is_htmx():
        return redirect(url_for("web.automation_rule_detail_page", rule_id=rule_id))
    return jsonify({"ok": True, "rule_id": rule_id})


@bp.get("/automation/rules/<rule_id>")
@login_required
@require_role("OPERATOR")
def automation_rule_detail_page(rule_id: str):
    row = automation_rule_get(current_tenant(), rule_id)
    if not row:
        return _automation_error("not_found", "Regel nicht gefunden.", 404)
    content = render_template(
        "automation/rule_detail.html",
        rule=row,
        read_only=bool(current_app.config.get("READ_ONLY", False)),
    )
    return _render_base(content, active_tab="automation")


@bp.post("/automation/rules/<rule_id>/toggle")
@login_required
@require_role("OPERATOR")
def automation_rule_toggle_action(rule_id: str):
    guarded = _automation_guard(api=not _is_htmx())
    if guarded is not None:
        return guarded
    payload = (
        request.form if not request.is_json else (request.get_json(silent=True) or {})
    )
    enabled = str(payload.get("enabled") or "1").strip().lower() in {
        "1",
        "true",
        "on",
        "yes",
    }
    try:
        automation_rule_toggle(
            current_tenant(), rule_id, enabled, current_user() or "system"
        )
    except PermissionError:
        return _automation_read_only_response(api=not _is_htmx())
    except ValueError:
        return _automation_error("not_found", "Regel nicht gefunden.", 404)
    if _is_htmx():
        return redirect(url_for("web.automation_rule_detail_page", rule_id=rule_id))
    return jsonify({"ok": True})


@bp.post("/automation/rules/<rule_id>/delete")
@login_required
@require_role("OPERATOR")
def automation_rule_delete_action(rule_id: str):
    guarded = _automation_guard(api=not _is_htmx())
    if guarded is not None:
        return guarded
    try:
        automation_rule_disable(current_tenant(), rule_id, current_user() or "system")
    except PermissionError:
        return _automation_read_only_response(api=not _is_htmx())
    except ValueError:
        return _automation_error("not_found", "Regel nicht gefunden.", 404)
    if _is_htmx():
        return redirect(url_for("web.automation_rules_page"))
    return jsonify({"ok": True})


@bp.post("/automation/run-now")
@login_required
@require_role("OPERATOR")
def automation_run_now_action():
    guarded = _automation_guard(api=not _is_htmx())
    if guarded is not None:
        return guarded
    payload = (
        request.form if not request.is_json else (request.get_json(silent=True) or {})
    )
    max_actions = int(payload.get("max_actions") or 50)
    try:
        run_id = automation_run_now(
            current_tenant(), current_user() or "system", max_actions=max_actions
        )
    except PermissionError:
        return _automation_read_only_response(api=not _is_htmx())
    except ValueError as exc:
        code = str(exc)
        if code == "db_locked":
            return _automation_error("db_locked", "Datenbank gesperrt.", 503)
        return _automation_error(
            "validation_error", "Automation-Run fehlgeschlagen.", 400
        )
    if _is_htmx():
        return redirect(url_for("web.automation_rules_page"))
    return jsonify({"ok": True, "run_id": run_id})


@bp.get("/workflows")
@login_required
@require_role("OPERATOR")
def workflows_page():
    templates = list_workflow_templates()
    installed_rows = _workflow_summaries(current_tenant())
    installed_by_key = {
        str(row.get("template_key") or ""): row for row in installed_rows
    }
    content = render_template(
        "workflows/list.html",
        templates=templates,
        installed_rows=installed_rows,
        installed_by_key=installed_by_key,
        read_only=bool(current_app.config.get("READ_ONLY", False)),
    )
    return _render_base(content, active_tab="workflows")


@bp.get("/workflows/<rule_id>")
@login_required
@require_role("OPERATOR")
def workflows_detail_page(rule_id: str):
    rule = builder_rule_get(tenant_id=current_tenant(), rule_id=rule_id)
    if not rule:
        return _automation_error("not_found", "Workflow nicht gefunden.", 404)
    logs = builder_execution_log_list(
        tenant_id=current_tenant(),
        rule_id=rule_id,
        limit=100,
    )
    template_key = _workflow_template_key_from_description(
        str(rule.get("description") or "")
    )
    content = render_template(
        "workflows/detail.html",
        rule=rule,
        logs=logs,
        template_key=template_key,
        read_only=bool(current_app.config.get("READ_ONLY", False)),
    )
    return _render_base(content, active_tab="workflows")


@bp.post("/workflows/install/<template_key>")
@login_required
@require_role("OPERATOR")
def workflows_install_action(template_key: str):
    guarded = _automation_guard(api=not _is_htmx())
    if guarded is not None:
        return guarded
    try:
        rule_id = _workflow_install_rule(current_tenant(), template_key)
    except ValueError as exc:
        if str(exc) == "not_found":
            return _automation_error("not_found", "Template nicht gefunden.", 404)
        return _automation_error("validation_error", "Template ungueltig.", 400)
    if _is_htmx():
        return redirect(url_for("web.workflows_detail_page", rule_id=rule_id))
    if request.is_json:
        return jsonify({"ok": True, "rule_id": rule_id})
    return redirect(url_for("web.workflows_detail_page", rule_id=rule_id))


@bp.post("/workflows/<rule_id>/toggle")
@login_required
@require_role("OPERATOR")
def workflows_toggle_action(rule_id: str):
    guarded = _automation_guard(api=not _is_htmx())
    if guarded is not None:
        return guarded
    payload = (
        request.form if not request.is_json else (request.get_json(silent=True) or {})
    )
    enabled = str(payload.get("enabled") or "1").strip().lower() in {
        "1",
        "true",
        "yes",
        "on",
    }
    row = builder_rule_update(
        tenant_id=current_tenant(),
        rule_id=rule_id,
        patch={"is_enabled": enabled},
    )
    if not row:
        return _automation_error("not_found", "Workflow nicht gefunden.", 404)
    if _is_htmx():
        return redirect(url_for("web.workflows_detail_page", rule_id=rule_id))
    if request.is_json:
        return jsonify({"ok": True, "rule": row})
    return redirect(url_for("web.workflows_page"))


@bp.get("/automation")
@login_required
@require_role("OPERATOR")
def automation_builder_page():
    rows = builder_rule_list(tenant_id=current_tenant())
    content = render_template(
        "automation/index.html",
        rules=rows,
        read_only=bool(current_app.config.get("READ_ONLY", False)),
    )
    return _render_base(content, active_tab="automation")


@bp.post("/automation/import")
@login_required
@require_role("OPERATOR")
def automation_builder_import_action():
    guarded = _automation_guard(api=not _is_htmx())
    if guarded is not None:
        return guarded
    payload = (
        request.form if not request.is_json else (request.get_json(silent=True) or {})
    )
    try:
        raw = payload.get("rule_json")
        parsed = raw if isinstance(raw, dict) else json.loads(str(raw or "{}"))
        normalized = _normalize_rule_import_payload(parsed)
        rule_id = builder_rule_create(
            tenant_id=current_tenant(),
            name=normalized["name"],
            description=normalized["description"],
            is_enabled=False,
            max_executions_per_minute=normalized["max_executions_per_minute"],
            triggers=normalized["triggers"],
            conditions=normalized["conditions"],
            actions=normalized["actions"],
        )
    except Exception:
        return _automation_error(
            "validation_error",
            "Import fehlgeschlagen. JSON prüfen.",
            400,
        )
    if _is_htmx():
        return redirect(
            url_for("web.automation_builder_rule_detail_page", rule_id=rule_id)
        )
    return jsonify({"ok": True, "rule_id": rule_id})


@bp.get("/automation/pending")
@login_required
@require_role("OPERATOR")
def automation_pending_page():
    items = builder_pending_action_list(tenant_id=current_tenant(), limit=200)
    content = render_template(
        "automation/pending.html",
        items=items,
        read_only=bool(current_app.config.get("READ_ONLY", False)),
    )
    return _render_base(content, active_tab="automation")


@bp.post("/automation/pending/<pending_id>/confirm")
@login_required
@require_role("OPERATOR")
def automation_pending_confirm_action(pending_id: str):
    guarded = _automation_guard(api=not _is_htmx())
    if guarded is not None:
        return guarded
    if current_role() not in {"ADMIN", "DEV"}:
        return _automation_error(
            "forbidden",
            "Bestätigen ist nur für ADMIN/DEV erlaubt.",
            403,
        )
    payload = (
        request.form if not request.is_json else (request.get_json(silent=True) or {})
    )
    ack = str(
        payload.get("safety_ack") or payload.get("user_confirmed") or ""
    ).strip().lower() in {
        "1",
        "true",
        "yes",
        "on",
    }
    if not ack:
        return _automation_error("confirm_required", "Bestätigung erforderlich.", 400)
    token = str(payload.get("confirm_token") or "").strip()
    if not token:
        return _automation_error(
            "confirm_token_required", "Bestätigungs-Token fehlt.", 400
        )
    item = builder_pending_action_confirm_once(
        tenant_id=current_tenant(),
        pending_id=pending_id,
        confirm_token=token,
    )
    if not item:
        return _automation_error(
            "confirm_replay_blocked",
            "Bestätigung ungültig oder bereits verwendet.",
            403,
        )

    try:
        action_cfg = json.loads(str(item.get("action_config") or "{}"))
        context_snapshot = json.loads(str(item.get("context_snapshot") or "{}"))
    except Exception:
        return _automation_error(
            "validation_error", "Pending Action ist ungültig.", 400
        )

    result = builder_execute_action(
        tenant_id=current_tenant(),
        rule_id=str(item.get("rule_id") or ""),
        action_config=action_cfg,
        context=context_snapshot,
        user_confirmed=True,
    )
    status = str(result.get("status") or "").strip().lower()
    if status == "failed":
        builder_pending_action_set_status(
            tenant_id=current_tenant(),
            pending_id=pending_id,
            status="failed",
        )
        return _automation_error(
            "action_failed", "Action konnte nicht ausgeführt werden.", 400
        )
    if _is_htmx():
        return redirect(url_for("web.automation_pending_page"))
    return jsonify({"ok": True, "result": result})


@bp.post("/automation/run")
@login_required
@require_role("OPERATOR")
def automation_builder_run_action():
    guarded = _automation_guard(api=not _is_htmx())
    if guarded is not None:
        return guarded
    event_result = process_events_for_tenant(current_tenant())
    if not bool(event_result.get("ok")):
        return _automation_error(
            "runner_failed",
            "Automation-Runner konnte nicht ausgeführt werden.",
            400,
        )
    cron_result = process_cron_for_tenant(current_tenant())
    if not bool(cron_result.get("ok")):
        return _automation_error(
            "runner_failed",
            "Automation-Runner konnte nicht ausgeführt werden.",
            400,
        )
    result = {"eventlog": event_result, "cron": cron_result}
    if _is_htmx():
        return redirect(url_for("web.automation_builder_page"))
    return jsonify({"ok": True, "result": result})


@bp.post("/automation/<rule_id>/simulate")
@login_required
@require_role("OPERATOR")
def automation_builder_simulate_rule_action(rule_id: str):
    guarded = _automation_guard(api=not _is_htmx())
    if guarded is not None:
        return guarded
    payload = (
        request.form if not request.is_json else (request.get_json(silent=True) or {})
    )
    raw_event_id = str(payload.get("event_id") or "").strip()
    ev_id = int(raw_event_id) if raw_event_id.isdigit() else None
    result = simulate_rule_for_tenant(
        current_tenant(),
        rule_id,
        event_id=ev_id,
    )
    if not bool(result.get("ok")) and str(result.get("reason") or "") not in {
        "condition_false",
        "trigger_not_matched",
    }:
        return _automation_error(
            "simulation_failed",
            "Simulation fehlgeschlagen.",
            400,
        )
    if _is_htmx():
        return redirect(
            url_for("web.automation_builder_rule_logs_page", rule_id=rule_id)
        )
    return jsonify({"ok": True, "result": result})


@bp.get("/automation/<rule_id>/logs")
@login_required
@require_role("OPERATOR")
def automation_builder_rule_logs_page(rule_id: str):
    rule = builder_rule_get(tenant_id=current_tenant(), rule_id=rule_id)
    if not rule:
        return _automation_error("not_found", "Regel nicht gefunden.", 404)
    logs = builder_execution_log_list(
        tenant_id=current_tenant(),
        rule_id=rule_id,
        limit=200,
    )
    content = render_template(
        "automation/logs.html",
        rule=rule,
        logs=logs,
        read_only=bool(current_app.config.get("READ_ONLY", False)),
    )
    return _render_base(content, active_tab="automation")


@bp.get("/automation/<rule_id>")
@login_required
@require_role("OPERATOR")
def automation_builder_rule_detail_page(rule_id: str):
    rule = builder_rule_get(tenant_id=current_tenant(), rule_id=rule_id)
    if not rule:
        return _automation_error("not_found", "Regel nicht gefunden.", 404)
    content = render_template(
        "automation/rule_detail_builder.html",
        rule=rule,
        read_only=bool(current_app.config.get("READ_ONLY", False)),
        webhook_allowed_domains=sorted(_builder_webhook_allowed_domains()),
    )
    return _render_base(content, active_tab="automation")


@bp.post("/automation/<rule_id>/trigger/cron")
@login_required
@require_role("OPERATOR")
def automation_builder_add_cron_trigger_action(rule_id: str):
    guarded = _automation_guard(api=not _is_htmx())
    if guarded is not None:
        return guarded
    payload = (
        request.form if not request.is_json else (request.get_json(silent=True) or {})
    )
    cron_expr = str(payload.get("cron_expression") or "").strip()
    if not cron_expr:
        return _automation_error("validation_error", "Cron-Ausdruck fehlt.", 400)
    try:
        parse_cron_expression(cron_expr)
    except ValueError:
        return _automation_error("validation_error", "Cron-Ausdruck ungültig.", 400)

    existing = builder_rule_get(tenant_id=current_tenant(), rule_id=rule_id)
    if not existing:
        return _automation_error("not_found", "Regel nicht gefunden.", 404)
    triggers = [
        {"trigger_type": str(t.get("type") or ""), "config": t.get("config") or {}}
        for t in (existing.get("triggers") or [])
        if isinstance(t, dict)
    ]
    triggers.append({"trigger_type": "cron", "config": {"cron": cron_expr}})
    updated = builder_rule_update(
        tenant_id=current_tenant(),
        rule_id=rule_id,
        patch={"triggers": triggers},
    )
    if not updated:
        return _automation_error("not_found", "Regel nicht gefunden.", 404)
    return redirect(url_for("web.automation_builder_rule_detail_page", rule_id=rule_id))


@bp.post("/automation/<rule_id>/action/email-draft")
@login_required
@require_role("OPERATOR")
def automation_builder_add_email_draft_action(rule_id: str):
    guarded = _automation_guard(api=not _is_htmx())
    if guarded is not None:
        return guarded
    payload = (
        request.form if not request.is_json else (request.get_json(silent=True) or {})
    )
    recipients = _split_recipients_csv(payload.get("to"))
    subject = str(payload.get("subject") or "").strip()
    body_template = str(payload.get("body_template") or "").strip()
    if not recipients or not subject or not body_template:
        return _automation_error(
            "validation_error", "Empfänger, Betreff und Inhalt sind Pflicht.", 400
        )
    if (
        len(subject) > _BUILDER_EMAIL_SUBJECT_MAX_LENGTH
        or len(body_template) > _BUILDER_EMAIL_BODY_MAX_LENGTH
        or not _builder_template_vars_allowed(body_template)
    ):
        return _automation_error(
            "validation_error", "E-Mail-Template ist ungültig.", 400
        )
    attachments_raw = str(payload.get("attachments") or "").strip()
    attachments = [
        part.strip()
        for part in attachments_raw.replace(";", ",").split(",")
        if part.strip()
    ]

    existing = builder_rule_get(tenant_id=current_tenant(), rule_id=rule_id)
    if not existing:
        return _automation_error("not_found", "Regel nicht gefunden.", 404)

    actions = [
        {"action_type": str(a.get("type") or ""), "config": a.get("config") or {}}
        for a in (existing.get("actions") or [])
        if isinstance(a, dict)
    ]
    action_cfg: dict[str, Any] = {
        "to": recipients,
        "subject": subject,
        "body_template": body_template,
        "requires_confirm": True,
    }
    account_id = str(payload.get("account_id") or "").strip()
    if account_id:
        action_cfg["account_id"] = account_id
    if attachments:
        action_cfg["attachments"] = attachments
    actions.append({"action_type": "email_draft", "config": action_cfg})
    updated = builder_rule_update(
        tenant_id=current_tenant(),
        rule_id=rule_id,
        patch={"actions": actions},
    )
    if not updated:
        return _automation_error("not_found", "Regel nicht gefunden.", 404)
    return redirect(url_for("web.automation_builder_rule_detail_page", rule_id=rule_id))


@bp.post("/automation/<rule_id>/action/email-send")
@login_required
@require_role("OPERATOR")
def automation_builder_add_email_send_action(rule_id: str):
    guarded = _automation_guard(api=not _is_htmx())
    if guarded is not None:
        return guarded
    payload = (
        request.form if not request.is_json else (request.get_json(silent=True) or {})
    )
    recipients = _split_recipients_csv(payload.get("to"))
    subject = str(payload.get("subject") or "").strip()
    body_template = str(payload.get("body_template") or "").strip()
    if not recipients or not subject or not body_template:
        return _automation_error(
            "validation_error",
            "Empfänger, Betreff und Body sind Pflicht.",
            400,
        )
    if (
        len(subject) > _BUILDER_EMAIL_SUBJECT_MAX_LENGTH
        or len(body_template) > _BUILDER_EMAIL_BODY_MAX_LENGTH
        or not _builder_template_vars_allowed(body_template)
    ):
        return _automation_error(
            "validation_error", "E-Mail-Template ist ungültig.", 400
        )
    attachments = _split_ids_csv(payload.get("attachments"))
    account_id = str(payload.get("account_id") or "").strip()

    existing = builder_rule_get(tenant_id=current_tenant(), rule_id=rule_id)
    if not existing:
        return _automation_error("not_found", "Regel nicht gefunden.", 404)

    actions = [
        {"action_type": str(a.get("type") or ""), "config": a.get("config") or {}}
        for a in (existing.get("actions") or [])
        if isinstance(a, dict)
    ]
    action_cfg: dict[str, Any] = {
        "to": recipients,
        "subject": subject,
        "body_template": body_template,
        "requires_confirm": True,
    }
    if account_id:
        action_cfg["account_id"] = account_id
    if attachments:
        action_cfg["attachments"] = attachments

    actions.append({"action_type": "email_send", "config": action_cfg})
    updated = builder_rule_update(
        tenant_id=current_tenant(),
        rule_id=rule_id,
        patch={"actions": actions},
    )
    if not updated:
        return _automation_error("not_found", "Regel nicht gefunden.", 404)
    return redirect(url_for("web.automation_builder_rule_detail_page", rule_id=rule_id))


@bp.post("/automation/<rule_id>/action/webhook")
@login_required
@require_role("OPERATOR")
def automation_builder_add_webhook_action(rule_id: str):
    guarded = _automation_guard(api=not _is_htmx())
    if guarded is not None:
        return guarded
    payload = (
        request.form if not request.is_json else (request.get_json(silent=True) or {})
    )
    url_value = str(payload.get("url") or "").strip()
    method = str(payload.get("method") or "POST").strip().upper()
    body_template = str(payload.get("body_template") or "{}")
    headers_raw = str(payload.get("headers_json") or "").strip()
    if not headers_raw:
        headers_raw = "{}"
    try:
        headers_cfg = json.loads(headers_raw)
    except Exception:
        return _automation_error("validation_error", "Headers-JSON ist ungültig.", 400)
    if not isinstance(headers_cfg, dict):
        return _automation_error("validation_error", "Headers-JSON ist ungültig.", 400)
    if method != "POST":
        return _automation_error("validation_error", "Nur POST ist erlaubt.", 400)
    if not _builder_webhook_url_allowed(url_value):
        return _automation_error(
            "validation_error",
            "Webhook-URL nicht erlaubt (HTTPS + Allowlist).",
            400,
        )
    for key in headers_cfg:
        lowered = str(key or "").strip().lower()
        if (
            not lowered
            or "auth" in lowered
            or "token" in lowered
            or lowered in {"cookie", "set-cookie"}
        ):
            return _automation_error(
                "validation_error",
                "Unsichere Header sind nicht erlaubt.",
                400,
            )

    existing = builder_rule_get(tenant_id=current_tenant(), rule_id=rule_id)
    if not existing:
        return _automation_error("not_found", "Regel nicht gefunden.", 404)

    actions = [
        {"action_type": str(a.get("type") or ""), "config": a.get("config") or {}}
        for a in (existing.get("actions") or [])
        if isinstance(a, dict)
    ]
    actions.append(
        {
            "action_type": "webhook",
            "config": {
                "url": url_value,
                "method": "POST",
                "body_template": body_template,
                "headers": {str(k): str(v)[:300] for k, v in headers_cfg.items()},
            },
        }
    )
    updated = builder_rule_update(
        tenant_id=current_tenant(),
        rule_id=rule_id,
        patch={"actions": actions},
    )
    if not updated:
        return _automation_error("not_found", "Regel nicht gefunden.", 404)
    return redirect(url_for("web.automation_builder_rule_detail_page", rule_id=rule_id))


@bp.get("/automation/<rule_id>/export")
@login_required
@require_role("OPERATOR")
def automation_builder_rule_export_action(rule_id: str):
    rule = builder_rule_get(tenant_id=current_tenant(), rule_id=rule_id)
    if not rule:
        return _automation_error("not_found", "Regel nicht gefunden.", 404)
    return jsonify({"ok": True, "item": _export_rule_payload(rule)})


@bp.post("/automation/<rule_id>/toggle")
@login_required
@require_role("OPERATOR")
def automation_builder_rule_toggle_action(rule_id: str):
    guarded = _automation_guard(api=not _is_htmx())
    if guarded is not None:
        return guarded
    payload = (
        request.form if not request.is_json else (request.get_json(silent=True) or {})
    )
    enabled = str(payload.get("enabled") or "1").strip().lower() in {
        "1",
        "true",
        "yes",
        "on",
    }
    row = builder_rule_update(
        tenant_id=current_tenant(),
        rule_id=rule_id,
        patch={"is_enabled": enabled},
    )
    if not row:
        return _automation_error("not_found", "Regel nicht gefunden.", 404)
    if _is_htmx():
        return redirect(
            url_for("web.automation_builder_rule_detail_page", rule_id=rule_id)
        )
    return jsonify({"ok": True, "rule": row})


@bp.get("/insights/daily")
@login_required
@require_role("OPERATOR")
def insights_daily_page():
    day = (request.args.get("day") or "").strip() or None
    data = get_or_build_daily_insights(current_tenant(), day)
    content = render_template("automation/insights_daily.html", data=data)
    return _render_base(content, active_tab="insights")


def _autonomy_error(code: str, message: str, status: int = 400):
    if request.is_json or request.path.startswith("/api/"):
        return json_error(code, message, status=status)
    if _is_htmx():
        return (
            render_template(
                "autonomy/partials/_errors.html",
                message=message,
                kind="error",
            ),
            status,
        )
    return (
        _render_base(
            f'<div class="card p-4"><h2 class="text-lg font-semibold">Autonomy Health</h2><p class="muted mt-2">{message}</p></div>',
            active_tab="autonomy",
        ),
        status,
    )


def _autonomy_guard(api: bool = True):
    if bool(current_app.config.get("READ_ONLY", False)):
        if api:
            return json_error("read_only", "Read-only mode aktiv.", status=403)
        return (
            render_template(
                "autonomy/partials/_errors.html",
                message="Read-only mode aktiv.",
                kind="error",
            ),
            403,
        )
    return None


@bp.get("/autonomy/health")
@login_required
@require_role("OPERATOR")
def autonomy_health_page():
    data = get_health_overview(current_tenant(), history_limit=25)
    policy = knowledge_policy_get(current_tenant())
    content = render_template(
        "autonomy/health.html",
        data=data,
        ocr_enabled=bool(int(policy.get("allow_ocr", 0))),
        read_only=bool(current_app.config.get("READ_ONLY", False)),
    )
    return _render_base(content, active_tab="autonomy")


@bp.post("/autonomy/health/backup")
@login_required
@require_role("OPERATOR")
def autonomy_health_backup_action():
    guarded = _autonomy_guard(api=not _is_htmx())
    if guarded is not None:
        return guarded
    result = run_backup(current_tenant(), actor_user_id=current_user() or None)
    if not bool(result.get("ok")):
        return _autonomy_error(
            "maintenance_error",
            "Backup konnte nicht erstellt werden.",
            status=500,
        )
    if request.is_json:
        return jsonify({"ok": True, "result": result})
    return redirect(url_for("web.autonomy_health_page"))


@bp.post("/autonomy/health/rotate-logs")
@login_required
@require_role("OPERATOR")
def autonomy_health_rotate_logs_action():
    guarded = _autonomy_guard(api=not _is_htmx())
    if guarded is not None:
        return guarded
    result = rotate_logs(current_tenant(), actor_user_id=current_user() or None)
    if not bool(result.get("ok")):
        return _autonomy_error(
            "maintenance_error",
            "Log-Rotation fehlgeschlagen.",
            status=500,
        )
    if request.is_json:
        return jsonify({"ok": True, "result": result})
    return redirect(url_for("web.autonomy_health_page"))


@bp.post("/autonomy/health/smoke-test")
@login_required
@require_role("OPERATOR")
def autonomy_health_smoke_test_action():
    guarded = _autonomy_guard(api=not _is_htmx())
    if guarded is not None:
        return guarded
    result = run_smoke_test(current_tenant(), actor_user_id=current_user() or None)
    if request.is_json:
        return jsonify({"ok": bool(result.get("ok")), "result": result})
    return redirect(url_for("web.autonomy_health_page"))


@bp.get("/api/automation/rules")
@login_required
@require_role("OPERATOR")
def api_automation_rules():
    return jsonify({"ok": True, "items": automation_rule_list(current_tenant())})


@bp.post("/api/automation/run-now")
@login_required
@require_role("OPERATOR")
def api_automation_run_now():
    guarded = _automation_guard(api=True)
    if guarded is not None:
        return guarded
    payload = request.get_json(silent=True) or {}
    try:
        run_id = automation_run_now(
            current_tenant(),
            current_user() or "system",
            max_actions=int(payload.get("max_actions") or 50),
        )
    except PermissionError:
        return _automation_read_only_response(api=True)
    except ValueError as exc:
        code = str(exc)
        if code == "db_locked":
            return _automation_error("db_locked", "Datenbank gesperrt.", 503)
        return _automation_error(
            "validation_error", "Automation-Run fehlgeschlagen.", 400
        )
    return jsonify({"ok": True, "run_id": run_id})


@bp.get("/api/insights/daily")
@login_required
@require_role("OPERATOR")
def api_insights_daily():
    day = (request.args.get("day") or "").strip() or None
    return jsonify(
        {"ok": True, "item": get_or_build_daily_insights(current_tenant(), day)}
    )


def _entity_links_error(code: str, message: str, status: int = 400):
    if request.is_json or request.path.startswith("/api/"):
        return json_error(code, message, status=status)
    return (
        render_template(
            "entity_links/partials/_errors.html",
            message=message,
            code=code,
            request_id=getattr(g, "request_id", ""),
        ),
        status,
    )


@bp.get("/entity-links/<entity_type>/<entity_id>")
@login_required
def entity_links_partial(entity_type: str, entity_id: str):
    link_type = (request.args.get("link_type") or "").strip().lower() or None
    try:
        links = list_links_for_entity(
            current_tenant(),
            entity_type,
            entity_id,
            link_type=link_type,
            limit=min(int(request.args.get("limit") or 25), 25),
            offset=max(int(request.args.get("offset") or 0), 0),
        )
    except ValueError:
        return _entity_links_error("validation_error", "Ungültige Link-Parameter.", 400)

    rendered_links: list[dict[str, Any]] = []
    with core._DB_LOCK:  # type: ignore[attr-defined]
        con = core._db()  # type: ignore[attr-defined]
        try:
            for row in links[:25]:
                display = entity_display_title(
                    con,
                    current_tenant(),
                    str(row.get("other_type") or ""),
                    str(row.get("other_id") or ""),
                )
                rendered_links.append({**row, "display": display})
        finally:
            con.close()

    return render_template(
        "entity_links/partials/_links_list.html",
        links=rendered_links,
        entity_type=entity_type,
        entity_id=entity_id,
        read_only=bool(current_app.config.get("READ_ONLY", False)),
    )


@bp.post("/entity-links/create")
@login_required
@require_role("OPERATOR")
def entity_links_create_action():
    if bool(current_app.config.get("READ_ONLY", False)):
        return _entity_links_error("read_only", "Read-only mode aktiv.", 403)

    payload = request.get_json(silent=True) if request.is_json else request.form
    left_type = (payload.get("left_type") if payload else "") or ""
    left_id = (payload.get("left_id") if payload else "") or ""
    right_type = (payload.get("right_type") if payload else "") or ""
    right_id = (payload.get("right_id") if payload else "") or ""
    link_type = (payload.get("link_type") if payload else "") or "related"

    try:
        entity_link_create(
            current_tenant(),
            left_type,
            left_id,
            right_type,
            right_id,
            link_type,
            actor_user_id=current_user() or None,
        )
    except PermissionError:
        return _entity_links_error("read_only", "Read-only mode aktiv.", 403)
    except ValueError as exc:
        code = str(exc)
        if code == "duplicate":
            return _entity_links_error("duplicate", "Link existiert bereits.", 409)
        if code == "entity_not_found":
            return _entity_links_error(
                "entity_not_found", "Entität nicht gefunden.", 404
            )
        if code == "db_locked":
            return _entity_links_error("db_locked", "Datenbank gesperrt.", 503)
        return _entity_links_error("validation_error", "Ungültige Link-Daten.", 400)

    context_type = (payload.get("context_entity_type") if payload else "") or left_type
    context_id = (payload.get("context_entity_id") if payload else "") or left_id

    if _is_htmx():
        return entity_links_partial(str(context_type), str(context_id))
    return jsonify({"ok": True})


@bp.post("/entity-links/<link_id>/delete")
@login_required
@require_role("OPERATOR")
def entity_links_delete_action(link_id: str):
    if bool(current_app.config.get("READ_ONLY", False)):
        return _entity_links_error("read_only", "Read-only mode aktiv.", 403)

    payload = request.get_json(silent=True) if request.is_json else request.form
    context_type = (payload.get("context_entity_type") if payload else "") or ""
    context_id = (payload.get("context_entity_id") if payload else "") or ""

    try:
        entity_link_delete(
            current_tenant(), link_id, actor_user_id=current_user() or None
        )
    except PermissionError:
        return _entity_links_error("read_only", "Read-only mode aktiv.", 403)
    except ValueError as exc:
        code = str(exc)
        if code == "not_found":
            return _entity_links_error("not_found", "Link nicht gefunden.", 404)
        if code == "db_locked":
            return _entity_links_error("db_locked", "Datenbank gesperrt.", 503)
        return _entity_links_error("validation_error", "Löschen fehlgeschlagen.", 400)

    if _is_htmx() and context_type and context_id:
        return entity_links_partial(str(context_type), str(context_id))
    return jsonify({"ok": True})


def _conversations_error(code: str, message: str, status: int = 400):
    if request.is_json or request.path.startswith("/api/"):
        return json_error(code, message, status=status)
    return (
        _render_base(
            f'<div class="card p-4"><h2 class="text-lg font-semibold">Conversations</h2><p class="muted mt-2">{message}</p></div>',
            active_tab="conversations",
        ),
        status,
    )


@bp.get("/conversations")
@login_required
def conversations_page():
    channel = (request.args.get("channel") or "").strip().lower() or None
    limit = _clamp_page_size(request.args.get("limit"), default=25)
    if limit > 50:
        limit = 50
    try:
        events = omni_list_events(current_tenant(), channel=channel, limit=limit)
    except ValueError:
        return _conversations_error(
            "validation_error", "Ungültiger Filter für Conversations.", status=400
        )
    content = render_template(
        "omni/inbox.html",
        events=events,
        channel=(channel or ""),
        limit=limit,
    )
    return _render_base(content, active_tab="conversations")


@bp.get("/conversations/<event_id>")
@login_required
def conversations_detail_page(event_id: str):
    try:
        event = omni_get_event(current_tenant(), event_id)
    except ValueError:
        return _conversations_error("validation_error", "Ungültige Event-ID.", 400)
    if not event:
        return _conversations_error("not_found", "Conversation nicht gefunden.", 404)
    content = render_template("omni/event_detail.html", event=event)
    return _render_base(content, active_tab="conversations")


def _knowledge_error(code: str, message: str, status: int = 400):
    if request.is_json or request.path.startswith("/api/"):
        return json_error(code, message, status=status)
    return (
        _render_base(
            f'<div class="card p-4"><h2 class="text-lg font-semibold">Knowledge</h2><p class="muted mt-2">{message}</p></div>',
            active_tab="knowledge",
        ),
        status,
    )


def _tags_error(code: str, message: str, status: int = 400):
    if request.is_json or request.path.startswith("/api/"):
        return json_error(code, message, status=status)
    if _is_htmx():
        return (
            render_template(
                "tags/partials/_errors.html",
                message=message,
                kind="error",
            ),
            status,
        )
    return (
        _render_base(
            f'<div class="card p-4"><h2 class="text-lg font-semibold">Tags</h2><p class="muted mt-2">{message}</p></div>',
            active_tab="knowledge",
        ),
        status,
    )


def _autotag_error(code: str, message: str, status: int = 400):
    if request.is_json or request.path.startswith("/api/"):
        return json_error(code, message, status=status)
    if _is_htmx():
        return (
            render_template(
                "autonomy/partials/_errors.html",
                message=message,
                kind="error",
            ),
            status,
        )
    return (
        _render_base(
            f'<div class="card p-4"><h2 class="text-lg font-semibold">Auto-Tagging</h2><p class="muted mt-2">{message}</p></div>',
            active_tab="knowledge",
        ),
        status,
    )


def _build_autotag_form_payload(
    form,
) -> tuple[str, int, dict[str, Any], list[dict[str, Any]]]:
    def _values(key: str) -> list[str]:
        if hasattr(form, "getlist"):
            return [str(v or "") for v in form.getlist(key)]
        raw = form.get(key) if isinstance(form, dict) else None
        if raw is None:
            return []
        if isinstance(raw, list):
            return [str(v or "") for v in raw]
        return [str(raw)]

    name = str((form.get("name") or "")).strip()
    try:
        priority = int(form.get("priority") or 0)
    except Exception as exc:
        raise ValueError("validation_error") from exc
    priority = max(-100, min(priority, 100))

    conds: list[dict[str, Any]] = []
    filename_glob = str(form.get("filename_glob") or "").strip()
    if filename_glob:
        conds.append({"type": "filename_glob", "pattern": filename_glob})

    ext_in = [
        str(v or "").strip().lower() for v in _values("ext_in") if str(v or "").strip()
    ]
    if ext_in:
        conds.append({"type": "ext_in", "values": ext_in[:10]})

    doctype_token = str(form.get("doctype_token") or "").strip().lower()
    if doctype_token:
        conds.append(
            {
                "type": "meta_token_in",
                "key": "doctype",
                "values": [doctype_token],
            }
        )

    if not conds:
        raise ValueError("validation_error")
    if len(conds) == 1:
        condition_obj: dict[str, Any] = conds[0]
    else:
        condition_obj = {"all": conds}

    actions: list[dict[str, Any]] = []
    tag_names = [
        str(v or "").strip() for v in _values("add_tag") if str(v or "").strip()
    ]
    for tag_name in tag_names[:3]:
        actions.append({"type": "add_tag", "tag_name": tag_name})

    set_doctype_token = str(form.get("set_doctype_token") or "").strip().lower()
    if set_doctype_token:
        actions.append({"type": "set_doctype", "token": set_doctype_token})

    set_correspondent_token = (
        str(form.get("set_correspondent_token") or "").strip().lower()
    )
    if set_correspondent_token:
        actions.append({"type": "set_correspondent", "token": set_correspondent_token})

    if not actions:
        raise ValueError("validation_error")
    return name, priority, condition_obj, actions


def _autotag_rule_summary(row: dict[str, Any]) -> dict[str, Any]:
    item = dict(row)
    cond_types: list[str] = []
    action_types: list[str] = []
    try:
        cond = json.loads(str(item.get("condition_json") or "{}"))
        acts = json.loads(str(item.get("action_json") or "[]"))

        def _walk_cond(node: Any) -> None:
            if not isinstance(node, dict):
                return
            if "all" in node and isinstance(node["all"], list):
                for c in node["all"]:
                    _walk_cond(c)
                return
            if "any" in node and isinstance(node["any"], list):
                for c in node["any"]:
                    _walk_cond(c)
                return
            ctype = str(node.get("type") or "")
            if ctype:
                cond_types.append(ctype)

        _walk_cond(cond)
        if isinstance(acts, list):
            for action in acts:
                if isinstance(action, dict):
                    atype = str(action.get("type") or "")
                    if atype:
                        action_types.append(atype)
    except Exception:
        pass

    item["condition_types"] = sorted(set(cond_types))
    item["action_types"] = sorted(set(action_types))
    return item


@bp.get("/knowledge")
@login_required
def knowledge_search_page():
    tenant_id = current_tenant()
    q = (request.args.get("q") or "").strip()
    source_type = (request.args.get("source_type") or "").strip().lower() or None
    owner_only = (request.args.get("owner_only") or "").strip() in {
        "1",
        "true",
        "on",
        "yes",
    }
    limit = _clamp_page_size(request.args.get("limit"), default=10)
    if limit > 25:
        limit = 25

    results: list[dict[str, Any]] = []
    if q:
        try:
            results = knowledge_search(
                tenant_id=tenant_id,
                query=q,
                owner_user_id=(current_user() if owner_only else None),
                source_type=source_type,
                limit=limit,
            )
        except ValueError:
            results = []

    all_tags = tag_list(tenant_id, limit=200, offset=0, include_usage=False)
    chunk_ids = [str(r.get("chunk_id") or "") for r in results if r.get("chunk_id")]
    entity_tags = (
        tags_for_entities(tenant_id, "knowledge_chunk", chunk_ids) if chunk_ids else {}
    )

    content = render_template(
        "knowledge/search.html",
        q=q,
        source_type=source_type or "",
        owner_only=owner_only,
        results=results,
        tags_by_entity=entity_tags,
        all_tags=all_tags,
        read_only=bool(current_app.config.get("READ_ONLY", False)),
    )
    return _render_base(content, active_tab="knowledge")


@bp.get("/knowledge/_results")
@login_required
def knowledge_results_partial():
    tenant_id = current_tenant()
    q = (request.args.get("q") or "").strip()
    source_type = (request.args.get("source_type") or "").strip().lower() or None
    owner_only = (request.args.get("owner_only") or "").strip() in {
        "1",
        "true",
        "on",
        "yes",
    }
    limit = _clamp_page_size(request.args.get("limit"), default=10)
    if limit > 25:
        limit = 25

    results: list[dict[str, Any]] = []
    if q:
        try:
            results = knowledge_search(
                tenant_id=tenant_id,
                query=q,
                owner_user_id=(current_user() if owner_only else None),
                source_type=source_type,
                limit=limit,
            )
        except ValueError:
            results = []

    all_tags = tag_list(tenant_id, limit=200, offset=0, include_usage=False)
    chunk_ids = [str(r.get("chunk_id") or "") for r in results if r.get("chunk_id")]
    entity_tags = (
        tags_for_entities(tenant_id, "knowledge_chunk", chunk_ids) if chunk_ids else {}
    )

    return render_template(
        "knowledge/partials/_results.html",
        results=results,
        tags_by_entity=entity_tags,
        all_tags=all_tags,
        read_only=bool(current_app.config.get("READ_ONLY", False)),
    )


@bp.get("/tags")
@login_required
def tags_page():
    page = _clamp_page(request.args.get("page"))
    page_size = _clamp_page_size(request.args.get("page_size"), default=50)
    if page_size > 200:
        page_size = 200
    offset = (page - 1) * page_size
    rows = tag_list(
        current_tenant(),
        limit=page_size,
        offset=offset,
        include_usage=True,
    )
    content = render_template(
        "tags/list.html",
        tags=rows,
        page=page,
        page_size=page_size,
        has_more=(len(rows) == page_size),
        read_only=bool(current_app.config.get("READ_ONLY", False)),
    )
    return _render_base(content, active_tab="knowledge")


@bp.post("/tags/create")
@login_required
@require_role("OPERATOR")
def tags_create_action():
    if bool(current_app.config.get("READ_ONLY", False)):
        return _tags_error("read_only", "Read-only mode aktiv.", status=403)
    payload = request.get_json(silent=True) if request.is_json else request.form
    try:
        row = tag_create(
            current_tenant(),
            name=((payload.get("name") if payload else "") or ""),
            color=((payload.get("color") if payload else "") or None),
            actor_user_id=current_user() or None,
        )
    except PermissionError:
        return _tags_error("read_only", "Read-only mode aktiv.", status=403)
    except ValueError as exc:
        code = str(exc)
        if code == "duplicate":
            return _tags_error("duplicate", "Tag existiert bereits.", status=409)
        if code == "limit_exceeded":
            return _tags_error("limit_exceeded", "Tag-Limit erreicht.", status=400)
        return _tags_error("validation_error", "Tag konnte nicht erstellt werden.", 400)

    if _is_htmx():
        return render_template("tags/partials/_tag_row.html", tag=row)
    if not request.is_json:
        return redirect(url_for("web.tags_page"))
    return jsonify({"ok": True, "tag": row})


@bp.post("/tags/<tag_id>/update")
@login_required
@require_role("OPERATOR")
def tags_update_action(tag_id: str):
    if bool(current_app.config.get("READ_ONLY", False)):
        return _tags_error("read_only", "Read-only mode aktiv.", status=403)
    payload = request.get_json(silent=True) if request.is_json else request.form
    try:
        row = tag_update(
            current_tenant(),
            tag_id=tag_id,
            name=(payload.get("name") if payload and "name" in payload else None),
            color=(payload.get("color") if payload and "color" in payload else None),
            actor_user_id=current_user() or None,
        )
    except PermissionError:
        return _tags_error("read_only", "Read-only mode aktiv.", status=403)
    except ValueError as exc:
        code = str(exc)
        if code == "not_found":
            return _tags_error("not_found", "Tag nicht gefunden.", status=404)
        if code == "duplicate":
            return _tags_error("duplicate", "Tag existiert bereits.", status=409)
        return _tags_error(
            "validation_error", "Tag konnte nicht aktualisiert werden.", 400
        )

    if _is_htmx():
        return render_template("tags/partials/_tag_row.html", tag=row)
    if not request.is_json:
        return redirect(url_for("web.tags_page"))
    return jsonify({"ok": True, "tag": row})


@bp.post("/tags/<tag_id>/delete")
@login_required
@require_role("OPERATOR")
def tags_delete_action(tag_id: str):
    if bool(current_app.config.get("READ_ONLY", False)):
        return _tags_error("read_only", "Read-only mode aktiv.", status=403)
    try:
        tag_delete(current_tenant(), tag_id, actor_user_id=current_user() or None)
    except PermissionError:
        return _tags_error("read_only", "Read-only mode aktiv.", status=403)
    except ValueError as exc:
        code = str(exc)
        if code == "not_found":
            return _tags_error("not_found", "Tag nicht gefunden.", status=404)
        return _tags_error("validation_error", "Tag konnte nicht gelöscht werden.", 400)

    if _is_htmx():
        return ""
    if not request.is_json:
        return redirect(url_for("web.tags_page"))
    return jsonify({"ok": True})


@bp.post("/tags/assign")
@login_required
@require_role("OPERATOR")
def tags_assign_action():
    if bool(current_app.config.get("READ_ONLY", False)):
        return _tags_error("read_only", "Read-only mode aktiv.", status=403)
    payload = request.get_json(silent=True) if request.is_json else request.form
    try:
        row = tag_assign(
            current_tenant(),
            entity_type=((payload.get("entity_type") if payload else "") or ""),
            entity_id=((payload.get("entity_id") if payload else "") or ""),
            tag_id=((payload.get("tag_id") if payload else "") or ""),
            actor_user_id=current_user() or None,
        )
    except PermissionError:
        return _tags_error("read_only", "Read-only mode aktiv.", status=403)
    except ValueError as exc:
        code = str(exc)
        if code == "duplicate":
            return _tags_error("duplicate", "Tag bereits zugeordnet.", status=409)
        if code == "not_found":
            return _tags_error("not_found", "Tag nicht gefunden.", status=404)
        if code == "limit_exceeded":
            return _tags_error(
                "limit_exceeded", "Zu viele Tags für dieses Objekt.", 400
            )
        return _tags_error(
            "validation_error", "Tag konnte nicht zugeordnet werden.", 400
        )

    next_url = (payload.get("next") if payload else "") or ""
    if next_url and not str(next_url).startswith("/"):
        next_url = ""
    if next_url and not request.is_json:
        return redirect(str(next_url))
    return jsonify({"ok": True, "assignment": row})


@bp.post("/tags/unassign")
@login_required
@require_role("OPERATOR")
def tags_unassign_action():
    if bool(current_app.config.get("READ_ONLY", False)):
        return _tags_error("read_only", "Read-only mode aktiv.", status=403)
    payload = request.get_json(silent=True) if request.is_json else request.form
    try:
        tag_unassign(
            current_tenant(),
            entity_type=((payload.get("entity_type") if payload else "") or ""),
            entity_id=((payload.get("entity_id") if payload else "") or ""),
            tag_id=((payload.get("tag_id") if payload else "") or ""),
            actor_user_id=current_user() or None,
        )
    except PermissionError:
        return _tags_error("read_only", "Read-only mode aktiv.", status=403)
    except ValueError as exc:
        code = str(exc)
        if code == "not_found":
            return _tags_error("not_found", "Zuordnung nicht gefunden.", status=404)
        return _tags_error("validation_error", "Tag konnte nicht entfernt werden.", 400)

    next_url = (payload.get("next") if payload else "") or ""
    if next_url and not str(next_url).startswith("/"):
        next_url = ""
    if next_url and not request.is_json:
        return redirect(str(next_url))
    return jsonify({"ok": True})


@bp.get("/autonomy/autotag/rules")
@login_required
@require_role("OPERATOR")
def autotag_rules_page():
    tenant_id = current_tenant()
    rules = [_autotag_rule_summary(r) for r in autotag_rules_list(tenant_id)]
    all_tags = tag_list(tenant_id, limit=500, offset=0, include_usage=False)
    content = render_template(
        "autonomy/autotag_rules.html",
        rules=rules,
        all_tags=all_tags,
        read_only=bool(current_app.config.get("READ_ONLY", False)),
    )
    return _render_base(content, active_tab="knowledge")


@bp.get("/autonomy/autotag/rules/new")
@login_required
@require_role("OPERATOR")
def autotag_rule_new_page():
    tenant_id = current_tenant()
    all_tags = tag_list(tenant_id, limit=500, offset=0, include_usage=False)
    content = render_template(
        "autonomy/autotag_rule_form.html",
        all_tags=all_tags,
        read_only=bool(current_app.config.get("READ_ONLY", False)),
        defaults={"priority": 0, "enabled": True},
    )
    return _render_base(content, active_tab="knowledge")


@bp.post("/autonomy/autotag/rules/create")
@login_required
@require_role("OPERATOR")
def autotag_rule_create_action():
    if bool(current_app.config.get("READ_ONLY", False)):
        return _autotag_error("read_only", "Read-only mode aktiv.", status=403)
    payload = (
        request.form if not request.is_json else (request.get_json(silent=True) or {})
    )
    try:
        name, priority, condition_obj, actions = _build_autotag_form_payload(payload)
        enabled = str(payload.get("enabled") or "1").strip().lower() not in {
            "0",
            "false",
            "off",
            "no",
        }
        row = autotag_rule_create(
            current_tenant(),
            name=name,
            priority=priority,
            condition_obj=condition_obj,
            action_list=actions,
            actor_user_id=current_user() or None,
            enabled=enabled,
        )
    except PermissionError:
        return _autotag_error("read_only", "Read-only mode aktiv.", status=403)
    except ValueError as exc:
        code = str(exc)
        if code == "duplicate":
            return _autotag_error(
                "duplicate", "Regelname existiert bereits.", status=409
            )
        if code == "limit_exceeded":
            return _autotag_error("limit_exceeded", "Regellimit erreicht.", status=400)
        return _autotag_error(
            "validation_error", "Regel konnte nicht erstellt werden.", status=400
        )

    if request.is_json:
        return jsonify({"ok": True, "rule": _autotag_rule_summary(row)})
    return redirect(url_for("web.autotag_rules_page"))


@bp.post("/autonomy/autotag/rules/<rule_id>/toggle")
@login_required
@require_role("OPERATOR")
def autotag_rule_toggle_action(rule_id: str):
    if bool(current_app.config.get("READ_ONLY", False)):
        return _autotag_error("read_only", "Read-only mode aktiv.", status=403)
    payload = (
        request.form if not request.is_json else (request.get_json(silent=True) or {})
    )
    enabled_raw = str(payload.get("enabled") or "").strip().lower()
    enabled = enabled_raw in {"1", "true", "on", "yes"}
    try:
        row = autotag_rule_toggle(
            current_tenant(),
            rule_id,
            enabled=enabled,
            actor_user_id=current_user() or None,
        )
    except PermissionError:
        return _autotag_error("read_only", "Read-only mode aktiv.", status=403)
    except ValueError as exc:
        code = str(exc)
        if code == "not_found":
            return _autotag_error("not_found", "Regel nicht gefunden.", status=404)
        return _autotag_error(
            "validation_error", "Regel konnte nicht umgeschaltet werden.", status=400
        )

    if request.is_json:
        return jsonify({"ok": True, "rule": _autotag_rule_summary(row)})
    return redirect(url_for("web.autotag_rules_page"))


@bp.post("/autonomy/autotag/rules/<rule_id>/delete")
@login_required
@require_role("OPERATOR")
def autotag_rule_delete_action(rule_id: str):
    if bool(current_app.config.get("READ_ONLY", False)):
        return _autotag_error("read_only", "Read-only mode aktiv.", status=403)
    try:
        autotag_rule_delete(
            current_tenant(), rule_id, actor_user_id=current_user() or None
        )
    except PermissionError:
        return _autotag_error("read_only", "Read-only mode aktiv.", status=403)
    except ValueError as exc:
        code = str(exc)
        if code == "not_found":
            return _autotag_error("not_found", "Regel nicht gefunden.", status=404)
        return _autotag_error(
            "validation_error", "Regel konnte nicht gelöscht werden.", status=400
        )

    if request.is_json:
        return jsonify({"ok": True})
    return redirect(url_for("web.autotag_rules_page"))


@bp.get("/knowledge/notes")
@login_required
def knowledge_notes_page():
    tenant_id = current_tenant()
    owner = current_user() or ""
    page = _clamp_page(request.args.get("page"))
    page_size = _clamp_page_size(request.args.get("page_size"), default=25)
    if page_size > 25:
        page_size = 25
    offset = (page - 1) * page_size

    notes = knowledge_notes_list(
        tenant_id, owner_user_id=owner, limit=page_size, offset=offset
    )
    selected_note_id = (request.args.get("note_id") or "").strip()
    if not selected_note_id and notes:
        selected_note_id = str(notes[0].get("chunk_id") or "")
    content = render_template(
        "knowledge/notes_list.html",
        notes=notes,
        page=page,
        page_size=page_size,
        has_more=(len(notes) == page_size),
        read_only=bool(current_app.config.get("READ_ONLY", False)),
        selected_note_id=selected_note_id,
    )
    return _render_base(content, active_tab="knowledge")


@bp.get("/knowledge/notes/new")
@login_required
def knowledge_new_note_page():
    content = render_template(
        "knowledge/note_form.html",
        mode="create",
        note={},
        read_only=bool(current_app.config.get("READ_ONLY", False)),
    )
    return _render_base(content, active_tab="knowledge")


@bp.post("/knowledge/notes/create")
@login_required
@require_role("OPERATOR")
def knowledge_create_note_action():
    if bool(current_app.config.get("READ_ONLY", False)):
        return _knowledge_error("read_only", "Read-only mode aktiv.", status=403)
    payload = request.get_json(silent=True) if request.is_json else request.form
    try:
        note = knowledge_note_create(
            tenant_id=current_tenant(),
            owner_user_id=current_user() or "",
            title=(payload.get("title") if payload else "") or "",
            body=(payload.get("body") if payload else "") or "",
            tags=(payload.get("tags") if payload else "") or None,
        )
    except PermissionError:
        return _knowledge_error("read_only", "Read-only mode aktiv.", status=403)
    except ValueError as exc:
        code = str(exc)
        if code == "policy_blocked":
            return _knowledge_error(
                "policy_blocked", "Quelle laut Policy deaktiviert.", status=403
            )
        return _knowledge_error(
            "validation_error", "Notiz konnte nicht gespeichert werden.", status=400
        )
    if _is_htmx():
        return redirect(url_for("web.knowledge_notes_page"))
    return jsonify({"ok": True, "note": note})


@bp.post("/knowledge/notes/<chunk_id>/edit")
@login_required
@require_role("OPERATOR")
def knowledge_edit_note_action(chunk_id: str):
    if bool(current_app.config.get("READ_ONLY", False)):
        return _knowledge_error("read_only", "Read-only mode aktiv.", status=403)
    payload = request.get_json(silent=True) if request.is_json else request.form
    try:
        note = knowledge_note_update(
            tenant_id=current_tenant(),
            chunk_id=chunk_id,
            owner_user_id=current_user() or "",
            title=(payload.get("title") if payload else "") or "",
            body=(payload.get("body") if payload else "") or "",
            tags=(payload.get("tags") if payload else "") or None,
        )
    except PermissionError:
        return _knowledge_error("read_only", "Read-only mode aktiv.", status=403)
    except ValueError as exc:
        code = str(exc)
        if code == "not_found":
            return _knowledge_error("not_found", "Notiz nicht gefunden.", status=404)
        if code == "forbidden":
            return _knowledge_error(
                "forbidden", "Keine Berechtigung für diese Notiz.", status=403
            )
        return _knowledge_error(
            "validation_error", "Notiz konnte nicht aktualisiert werden.", status=400
        )
    if _is_htmx():
        return redirect(url_for("web.knowledge_notes_page"))
    return jsonify({"ok": True, "note": note})


@bp.post("/knowledge/notes/<chunk_id>/delete")
@login_required
@require_role("OPERATOR")
def knowledge_delete_note_action(chunk_id: str):
    if bool(current_app.config.get("READ_ONLY", False)):
        return _knowledge_error("read_only", "Read-only mode aktiv.", status=403)
    try:
        knowledge_note_delete(
            tenant_id=current_tenant(),
            chunk_id=chunk_id,
            owner_user_id=current_user() or "",
        )
    except PermissionError:
        return _knowledge_error("read_only", "Read-only mode aktiv.", status=403)
    except ValueError as exc:
        code = str(exc)
        if code == "not_found":
            return _knowledge_error("not_found", "Notiz nicht gefunden.", status=404)
        if code == "forbidden":
            return _knowledge_error(
                "forbidden", "Keine Berechtigung für diese Notiz.", status=403
            )
        return _knowledge_error(
            "validation_error", "Notiz konnte nicht gelöscht werden.", status=400
        )
    if _is_htmx():
        return redirect(url_for("web.knowledge_notes_page"))
    return jsonify({"ok": True})


@bp.get("/knowledge/settings")
@login_required
def knowledge_settings_page():
    policy = knowledge_policy_get(current_tenant())
    content = render_template(
        "knowledge/settings.html",
        policy=policy,
        read_only=bool(current_app.config.get("READ_ONLY", False)),
    )
    return _render_base(content, active_tab="knowledge")


@bp.post("/knowledge/settings/email/toggle")
@login_required
@require_role("OPERATOR")
def knowledge_settings_email_toggle_action():
    if bool(current_app.config.get("READ_ONLY", False)):
        return _knowledge_error("read_only", "Read-only mode aktiv.", status=403)
    payload = request.get_json(silent=True) if request.is_json else request.form
    enabled = str((payload.get("enabled") if payload else "")).strip().lower() in {
        "1",
        "true",
        "on",
        "yes",
    }
    try:
        policy = knowledge_policy_update(
            current_tenant(),
            actor_user_id=current_user() or "",
            allow_email=enabled,
        )
    except PermissionError:
        return _knowledge_error("read_only", "Read-only mode aktiv.", status=403)
    except ValueError:
        return _knowledge_error(
            "validation_error", "Ungültige Policy-Konfiguration.", status=400
        )

    if _is_htmx():
        return render_template(
            "knowledge/partials/_errors.html",
            message=(
                "E-Mail Quelle aktiviert." if enabled else "E-Mail Quelle deaktiviert."
            ),
            kind="ok",
        )
    return jsonify({"ok": True, "policy": policy})


@bp.get("/knowledge/email/upload")
@login_required
def knowledge_email_upload_page():
    policy = knowledge_policy_get(current_tenant())
    page = _clamp_page(request.args.get("page"))
    page_size = _clamp_page_size(request.args.get("page_size"), default=25)
    rows, total = knowledge_email_sources_list(
        current_tenant(), page=page, page_size=page_size
    )
    content = render_template(
        "knowledge/email_upload.html",
        policy=policy,
        emails=rows,
        total=total,
        page=page,
        page_size=page_size,
        has_more=(len(rows) == page_size),
        max_eml_bytes=int(
            current_app.config.get("KNOWLEDGE_EMAIL_MAX_BYTES", 2 * 1024 * 1024)
        ),
        read_only=bool(current_app.config.get("READ_ONLY", False)),
    )
    return _render_base(content, active_tab="knowledge")


@bp.post("/knowledge/email/upload")
@login_required
@require_role("OPERATOR")
def knowledge_email_upload_action():
    if bool(current_app.config.get("READ_ONLY", False)):
        return _knowledge_error("read_only", "Read-only mode aktiv.", status=403)

    policy = knowledge_policy_get(current_tenant())
    if not int(policy.get("allow_email", 0)):
        return _knowledge_error(
            "policy_blocked", "E-Mail Quelle ist deaktiviert.", status=403
        )

    f = request.files.get("file")
    if f is None:
        return _knowledge_error(
            "file_required", "Bitte .eml-Datei hochladen.", status=400
        )
    filename = (f.filename or "").strip().lower()
    if not filename.endswith(".eml"):
        return _knowledge_error(
            "invalid_file_type", "Nur .eml-Dateien sind erlaubt.", status=400
        )

    max_bytes = int(
        current_app.config.get("KNOWLEDGE_EMAIL_MAX_BYTES", 2 * 1024 * 1024)
    )
    raw = f.read(max_bytes + 1) or b""
    if not raw:
        return _knowledge_error("empty_file", "Datei ist leer.", status=400)
    if len(raw) > max_bytes:
        return _knowledge_error(
            "payload_too_large", "Datei überschreitet das Upload-Limit.", status=413
        )

    try:
        result = knowledge_email_ingest_eml(
            tenant_id=current_tenant(),
            actor_user_id=current_user() or None,
            eml_bytes=raw,
            filename_hint=(f.filename or ""),
        )
    except PermissionError:
        return _knowledge_error("read_only", "Read-only mode aktiv.", status=403)
    except ValueError as exc:
        code = str(exc)
        if code == "policy_blocked":
            return _knowledge_error(
                "policy_blocked", "E-Mail Quelle ist deaktiviert.", status=403
            )
        if code == "payload_too_large":
            return _knowledge_error(
                "payload_too_large", "Datei überschreitet das Upload-Limit.", status=413
            )
        if code == "parse_error":
            return _knowledge_error(
                "parse_error", "EML konnte nicht verarbeitet werden.", status=400
            )
        if code == "db_locked":
            return _knowledge_error("db_locked", "Datenbank ist gesperrt.", status=503)
        return _knowledge_error(
            "validation_error", "Upload fehlgeschlagen.", status=400
        )

    if _is_htmx():
        return render_template(
            "knowledge/partials/_email_ingest_result.html", result=result
        )
    return jsonify({"ok": True, "result": result})


@bp.get("/knowledge/ics/upload")
@login_required
def knowledge_ics_upload_page():
    policy = knowledge_policy_get(current_tenant())
    page = _clamp_page(request.args.get("page"))
    page_size = _clamp_page_size(request.args.get("page_size"), default=25)
    rows, total = knowledge_ics_sources_list(
        current_tenant(), page=page, page_size=page_size
    )
    content = render_template(
        "knowledge/ics_upload.html",
        policy=policy,
        items=rows,
        total=total,
        page=page,
        page_size=page_size,
        has_more=(len(rows) == page_size),
        max_ics_bytes=int(
            current_app.config.get("KNOWLEDGE_ICS_MAX_BYTES", 256 * 1024)
        ),
        read_only=bool(current_app.config.get("READ_ONLY", False)),
    )
    return _render_base(content, active_tab="knowledge")


@bp.post("/knowledge/ics/upload")
@login_required
@require_role("OPERATOR")
def knowledge_ics_upload_action():
    if bool(current_app.config.get("READ_ONLY", False)):
        return _knowledge_error("read_only", "Read-only mode aktiv.", status=403)

    policy = knowledge_policy_get(current_tenant())
    if not int(policy.get("allow_calendar", 0)):
        return _knowledge_error(
            "policy_blocked", "Kalender-Quelle ist deaktiviert.", status=403
        )

    f = request.files.get("file")
    if f is None:
        return _knowledge_error(
            "file_required", "Bitte .ics-Datei hochladen.", status=400
        )
    filename = (f.filename or "").strip().lower()
    if not filename.endswith(".ics"):
        return _knowledge_error(
            "invalid_file_type", "Nur .ics-Dateien sind erlaubt.", status=400
        )

    max_bytes = int(current_app.config.get("KNOWLEDGE_ICS_MAX_BYTES", 256 * 1024))
    raw = f.read(max_bytes + 1) or b""
    if not raw:
        return _knowledge_error("empty_file", "Datei ist leer.", status=400)
    if len(raw) > max_bytes:
        return _knowledge_error(
            "payload_too_large", "Datei überschreitet das Upload-Limit.", status=413
        )

    try:
        result = knowledge_ics_ingest(
            tenant_id=current_tenant(),
            actor_user_id=current_user() or None,
            ics_bytes=raw,
            filename_hint=(f.filename or ""),
        )
    except PermissionError:
        return _knowledge_error("read_only", "Read-only mode aktiv.", status=403)
    except ValueError as exc:
        code = str(exc)
        if code == "policy_blocked":
            return _knowledge_error(
                "policy_blocked", "Kalender-Quelle ist deaktiviert.", status=403
            )
        if code == "payload_too_large":
            return _knowledge_error(
                "payload_too_large", "Datei überschreitet das Upload-Limit.", status=413
            )
        if code == "db_locked":
            return _knowledge_error("db_locked", "Datenbank ist gesperrt.", status=503)
        return _knowledge_error(
            "validation_error", "Upload fehlgeschlagen.", status=400
        )

    if _is_htmx():
        return render_template(
            "knowledge/partials/_ics_ingest_result.html", result=result
        )
    return jsonify({"ok": True, "result": result})


@bp.post("/knowledge/settings/save")
@login_required
@require_role("OPERATOR")
def knowledge_settings_save_action():
    if bool(current_app.config.get("READ_ONLY", False)):
        return _knowledge_error("read_only", "Read-only mode aktiv.", status=403)
    payload = request.get_json(silent=True) if request.is_json else request.form
    flag_keys = [
        "allow_manual",
        "allow_tasks",
        "allow_projects",
        "allow_documents",
        "allow_leads",
        "allow_email",
        "allow_calendar",
        "allow_ocr",
        "allow_customer_pii",
    ]
    flags: dict[str, bool] = {}
    for key in flag_keys:
        val = payload.get(key) if payload else None
        flags[key] = str(val).strip().lower() in {"1", "true", "on", "yes"}

    try:
        policy = knowledge_policy_update(
            current_tenant(),
            actor_user_id=current_user() or "",
            **flags,
        )
    except PermissionError:
        return _knowledge_error("read_only", "Read-only mode aktiv.", status=403)
    except ValueError:
        return _knowledge_error(
            "validation_error", "Ungültige Policy-Konfiguration.", status=400
        )

    if _is_htmx():
        return render_template(
            "knowledge/partials/_errors.html",
            message="Einstellungen gespeichert.",
            kind="ok",
        )
    return jsonify({"ok": True, "policy": policy})


@bp.get("/api/knowledge/search")
@login_required
def api_knowledge_search():
    q = (request.args.get("q") or "").strip()
    source_type = (request.args.get("source_type") or "").strip().lower() or None
    owner_only = (request.args.get("owner_only") or "").strip() in {
        "1",
        "true",
        "on",
        "yes",
    }
    limit = _clamp_page_size(request.args.get("limit"), default=10)
    if limit > 25:
        limit = 25
    try:
        rows = knowledge_search(
            tenant_id=current_tenant(),
            query=q,
            owner_user_id=(current_user() if owner_only else None),
            source_type=source_type,
            limit=limit,
        )
    except ValueError:
        return json_error("validation_error", "Ungültige Suchanfrage.", status=400)
    return jsonify({"ok": True, "items": rows})


@bp.get("/api/knowledge/notes")
@login_required
def api_knowledge_notes_list():
    limit = _clamp_page_size(request.args.get("limit"), default=25)
    if limit > 25:
        limit = 25
    offset = max(0, int(request.args.get("offset") or 0))
    notes = knowledge_notes_list(
        tenant_id=current_tenant(),
        owner_user_id=current_user() or "",
        limit=limit,
        offset=offset,
    )
    return jsonify({"ok": True, "items": notes})


@bp.post("/api/knowledge/notes")
@login_required
@require_role("OPERATOR")
def api_knowledge_notes_create():
    if bool(current_app.config.get("READ_ONLY", False)):
        return json_error("read_only", "Read-only mode aktiv.", status=403)
    payload = request.get_json(silent=True) or {}
    try:
        note = knowledge_note_create(
            tenant_id=current_tenant(),
            owner_user_id=current_user() or "",
            title=(payload.get("title") or ""),
            body=(payload.get("body") or ""),
            tags=(payload.get("tags") or None),
        )
    except PermissionError:
        return json_error("read_only", "Read-only mode aktiv.", status=403)
    except ValueError as exc:
        if str(exc) == "policy_blocked":
            return json_error(
                "policy_blocked", "Quelle laut Policy deaktiviert.", status=403
            )
        return json_error(
            "validation_error", "Notiz konnte nicht gespeichert werden.", status=400
        )
    return jsonify({"ok": True, "note": note})


@bp.get("/crm/customers")
@login_required
def crm_customers_page():
    tenant_id = current_tenant()
    q = (request.args.get("q") or "").strip()
    sort = (request.args.get("sort") or "name").strip().lower()
    if sort not in {"name", "since", "updated"}:
        sort = "name"
    page = _clamp_page(request.args.get("page"))
    page_size = _clamp_page_size(request.args.get("page_size"), default=25)
    offset = (page - 1) * page_size
    rows = (
        customers_list(tenant_id, limit=page_size, offset=offset, query=q)
        if callable(customers_list)
        else []
    )  # type: ignore
    if sort == "name":
        rows = sorted(
            rows, key=lambda r: ((r.get("name") or "").lower(), str(r.get("id") or ""))
        )
    elif sort == "since":
        rows = sorted(
            rows,
            key=lambda r: (str(r.get("created_at") or ""), str(r.get("id") or "")),
            reverse=True,
        )
    else:
        rows = sorted(
            rows,
            key=lambda r: (str(r.get("updated_at") or ""), str(r.get("id") or "")),
            reverse=True,
        )
    has_more = len(rows) == page_size
    content = render_template(
        "crm/customers.html",
        customers=rows,
        q=q,
        sort=sort,
        page=page,
        page_size=page_size,
        has_more=has_more,
        read_only=bool(current_app.config.get("READ_ONLY", False)),
    )
    return _render_base(content, active_tab="crm")


@bp.get("/crm/_customers_table")
@login_required
def crm_customers_table_partial():
    tenant_id = current_tenant()
    q = (request.args.get("q") or "").strip()
    sort = (request.args.get("sort") or "name").strip().lower()
    if sort not in {"name", "since", "updated"}:
        sort = "name"
    page = _clamp_page(request.args.get("page"))
    page_size = _clamp_page_size(request.args.get("page_size"), default=25)
    offset = (page - 1) * page_size
    rows = (
        customers_list(tenant_id, limit=page_size, offset=offset, query=q)
        if callable(customers_list)
        else []
    )  # type: ignore
    if sort == "name":
        rows = sorted(
            rows, key=lambda r: ((r.get("name") or "").lower(), str(r.get("id") or ""))
        )
    elif sort == "since":
        rows = sorted(
            rows,
            key=lambda r: (str(r.get("created_at") or ""), str(r.get("id") or "")),
            reverse=True,
        )
    else:
        rows = sorted(
            rows,
            key=lambda r: (str(r.get("updated_at") or ""), str(r.get("id") or "")),
            reverse=True,
        )
    return render_template(
        "crm/partials/customers_table.html",
        customers=rows,
        q=q,
        sort=sort,
        page=page,
        page_size=page_size,
        has_more=(len(rows) == page_size),
    )


@bp.get("/crm/customers/<customer_id>")
@login_required
def crm_customer_detail(customer_id: str):
    tenant_id = current_tenant()
    customer = _crm_customer_get(tenant_id, customer_id)
    if not customer:
        return json_error("not_found", "Kunde nicht gefunden.", status=404)
    active_tab = (request.args.get("tab") or "contacts").strip().lower()
    if active_tab not in {"contacts", "deals", "quotes", "emails"}:
        active_tab = "contacts"
    content = render_template(
        "crm/customer_detail.html",
        customer=customer,
        active_subtab=active_tab,
        read_only=bool(current_app.config.get("READ_ONLY", False)),
    )
    return _render_base(content, active_tab="crm")


@bp.get("/crm/_customer_contacts/<customer_id>")
@login_required
def crm_customer_contacts_partial(customer_id: str):
    tenant_id = current_tenant()
    contacts = _crm_contacts_list(tenant_id, customer_id)
    return render_template("crm/partials/customer_contacts.html", contacts=contacts)


@bp.get("/crm/_customer_deals/<customer_id>")
@login_required
def crm_customer_deals_partial(customer_id: str):
    tenant_id = current_tenant()
    deals = _crm_deals_list(tenant_id, customer_id=customer_id)
    return render_template("crm/partials/customer_deals.html", deals=deals)


@bp.get("/crm/_customer_quotes/<customer_id>")
@login_required
def crm_customer_quotes_partial(customer_id: str):
    tenant_id = current_tenant()
    rows, total = _crm_quotes_list(
        tenant_id, customer_id=customer_id, page=1, page_size=100
    )
    return render_template(
        "crm/partials/customer_quotes.html", quotes=rows, total=total
    )


@bp.get("/crm/_customer_emails/<customer_id>")
@login_required
def crm_customer_emails_partial(customer_id: str):
    tenant_id = current_tenant()
    rows, total = _crm_emails_list(
        tenant_id, customer_id=customer_id, page=1, page_size=100
    )
    return render_template(
        "crm/partials/customer_emails.html", emails=rows, total=total
    )


@bp.get("/crm/deals")
@login_required
def crm_deals_page():
    tenant_id = current_tenant()
    q = (request.args.get("q") or "").strip()
    stages = ["lead", "qualified", "proposal", "negotiation", "won", "lost"]
    grouped = {
        stage: _crm_deals_list(tenant_id, stage=stage, query=q) for stage in stages
    }
    content = render_template(
        "crm/deals.html",
        grouped=grouped,
        stages=stages,
        q=q,
        read_only=bool(current_app.config.get("READ_ONLY", False)),
    )
    return _render_base(content, active_tab="crm")


@bp.get("/crm/_deals_pipeline")
@login_required
def crm_deals_pipeline_partial():
    tenant_id = current_tenant()
    q = (request.args.get("q") or "").strip()
    stage_filter = (request.args.get("stage") or "").strip().lower()
    stages = ["lead", "qualified", "proposal", "negotiation", "won", "lost"]
    if stage_filter and stage_filter in stages:
        grouped = {
            stage_filter: _crm_deals_list(tenant_id, stage=stage_filter, query=q)
        }
    else:
        grouped = {
            stage: _crm_deals_list(tenant_id, stage=stage, query=q) for stage in stages
        }
    return render_template(
        "crm/partials/deals_pipeline.html",
        grouped=grouped,
        stages=stages,
        read_only=bool(current_app.config.get("READ_ONLY", False)),
    )


@bp.get("/crm/quotes")
@login_required
def crm_quotes_page():
    tenant_id = current_tenant()
    q = (request.args.get("q") or "").strip()
    status = (request.args.get("status") or "").strip().lower() or None
    page = _clamp_page(request.args.get("page"))
    page_size = _clamp_page_size(request.args.get("page_size"), default=25)
    rows, total = _crm_quotes_list(
        tenant_id, status=status, query=q, page=page, page_size=page_size
    )
    content = render_template(
        "crm/quotes.html",
        quotes=rows,
        total=total,
        page=page,
        page_size=page_size,
        q=q,
        status=status or "",
    )
    return _render_base(content, active_tab="crm")


@bp.get("/crm/_quotes_table")
@login_required
def crm_quotes_table_partial():
    tenant_id = current_tenant()
    q = (request.args.get("q") or "").strip()
    status = (request.args.get("status") or "").strip().lower() or None
    page = _clamp_page(request.args.get("page"))
    page_size = _clamp_page_size(request.args.get("page_size"), default=25)
    rows, total = _crm_quotes_list(
        tenant_id, status=status, query=q, page=page, page_size=page_size
    )
    return render_template(
        "crm/partials/quotes_table.html",
        quotes=rows,
        total=total,
        page=page,
        page_size=page_size,
        q=q,
        status=status or "",
    )


@bp.get("/crm/quotes/<quote_id>")
@login_required
def crm_quote_detail(quote_id: str):
    if not callable(quotes_get):
        return json_error("feature_unavailable", "CRM ist nicht verfügbar.", status=501)
    try:
        quote = quotes_get(current_tenant(), quote_id)  # type: ignore
    except Exception:
        return json_error("not_found", "Angebot nicht gefunden.", status=404)
    for item in quote.get("items", []):
        item["unit_price_text"] = _format_cents(
            item.get("unit_price_cents"), quote.get("currency") or "EUR"
        )
        item["line_total_text"] = _format_cents(
            item.get("line_total_cents"), quote.get("currency") or "EUR"
        )
    quote["subtotal_text"] = _format_cents(
        quote.get("subtotal_cents"), quote.get("currency") or "EUR"
    )
    quote["tax_text"] = _format_cents(
        quote.get("tax_amount_cents") or quote.get("tax_cents"),
        quote.get("currency") or "EUR",
    )
    quote["total_text"] = _format_cents(
        quote.get("total_cents"), quote.get("currency") or "EUR"
    )
    content = render_template(
        "crm/quote_detail.html",
        quote=quote,
        quote_items=quote.get("items", []),
        read_only=bool(current_app.config.get("READ_ONLY", False)),
        link_entity_type="quote",
        link_entity_id=quote_id,
    )
    return _render_base(content, active_tab="crm")


@bp.get("/crm/emails/import")
@login_required
def crm_emails_import_page():
    tenant_id = current_tenant()
    page = _clamp_page(request.args.get("page"))
    page_size = _clamp_page_size(request.args.get("page_size"), default=25)
    emails, total = _crm_emails_list(tenant_id, page=page, page_size=page_size)
    content = render_template(
        "crm/emails_import.html",
        emails=emails,
        total=total,
        page=page,
        page_size=page_size,
        max_eml_bytes=int(current_app.config.get("MAX_EML_BYTES", 10 * 1024 * 1024)),
        read_only=bool(current_app.config.get("READ_ONLY", False)),
    )
    return _render_base(content, active_tab="crm")


@bp.get("/app.webmanifest")
def pwa_manifest():
    payload = {
        "name": "KUKANILEA CRM",
        "short_name": "KUKANILEA",
        "start_url": "/crm/customers",
        "display": "standalone",
        "background_color": "#0b1220",
        "theme_color": "#4f46e5",
        "icons": [
            {
                "src": "/static/icons/pwa-icon.svg",
                "sizes": "any",
                "type": "image/svg+xml",
                "purpose": "any",
            }
        ],
    }
    res = jsonify(payload)
    res.headers["Content-Type"] = "application/manifest+json"
    return res


@bp.get("/sw.js")
def pwa_service_worker():
    body = """const CACHE='kukanilea-crm-v1';
const ASSETS=['/','/crm/customers','/crm/deals','/crm/quotes','/crm/emails/import','/app.webmanifest','/static/icons/pwa-icon.svg'];
self.addEventListener('install',e=>{e.waitUntil(caches.open(CACHE).then(c=>c.addAll(ASSETS)));self.skipWaiting();});
self.addEventListener('activate',e=>{e.waitUntil(caches.keys().then(keys=>Promise.all(keys.filter(k=>k!==CACHE).map(k=>caches.delete(k)))));self.clients.claim();});
self.addEventListener('fetch',e=>{const req=e.request; if(req.method!=='GET'){return;} const isHtml=req.headers.get('accept')&&req.headers.get('accept').includes('text/html'); if(isHtml){e.respondWith(fetch(req).then(r=>{const copy=r.clone(); caches.open(CACHE).then(c=>c.put(req,copy)); return r;}).catch(()=>caches.match(req).then(r=>r||caches.match('/crm/customers')))); return;} e.respondWith(caches.match(req).then(r=>r||fetch(req).then(resp=>{const copy=resp.clone(); caches.open(CACHE).then(c=>c.put(req,copy)); return resp;})));});
"""
    resp = current_app.response_class(body, mimetype="application/javascript")
    resp.headers["Cache-Control"] = "no-cache"
    return resp


# ==============================
# Mail Agent Tab (Template/Mock workflow)
# ==============================
HTML_MAIL = """
<div class="grid gap-4">
  <div class="card p-4 rounded-2xl border">
    <div class="flex items-center justify-between gap-3">
      <div>
        <div class="text-lg font-semibold">Mailbox (IMAP v0)</div>
        <div class="text-sm opacity-80">On-demand Sync ohne neue Dependencies. OAuth bleibt optional/später.</div>
      </div>
      <div class="text-right text-xs opacity-70">
        Google OAuth: {{ 'konfiguriert' if google_configured else 'nicht konfiguriert' }}
      </div>
    </div>
    {% if read_only %}
      <div class="mt-3 rounded-xl border border-rose-500/40 bg-rose-500/10 p-3 text-sm">
        READ_ONLY aktiv: Account-Anlage und Sync sind deaktiviert.
      </div>
    {% endif %}
  </div>

  <div class="grid gap-4 lg:grid-cols-3">
    <div class="lg:col-span-2 card p-4 rounded-2xl border">
      <div class="text-base font-semibold mb-3">Inbox</div>

      <form method="post" action="/mail/accounts/add" class="grid gap-2 md:grid-cols-6 mb-4">
        <input name="label" class="rounded-xl border px-3 py-2 text-sm bg-transparent md:col-span-1" placeholder="Label" required {% if read_only %}disabled{% endif %} />
        <input name="imap_host" class="rounded-xl border px-3 py-2 text-sm bg-transparent md:col-span-1" placeholder="imap.example.com" required {% if read_only %}disabled{% endif %} />
        <input name="imap_port" type="number" value="993" class="rounded-xl border px-3 py-2 text-sm bg-transparent md:col-span-1" required {% if read_only %}disabled{% endif %} />
        <input name="imap_username" class="rounded-xl border px-3 py-2 text-sm bg-transparent md:col-span-1" placeholder="user@example.com" required {% if read_only %}disabled{% endif %} />
        <input name="imap_password" type="password" class="rounded-xl border px-3 py-2 text-sm bg-transparent md:col-span-1" placeholder="Passwort" {% if read_only %}disabled{% endif %} />
        <button class="rounded-xl px-3 py-2 text-sm btn-primary md:col-span-1" type="submit" {% if read_only %}disabled{% endif %}>Account speichern</button>
      </form>

      {% if accounts %}
      <form method="post" action="/mail/accounts/sync" class="grid gap-2 md:grid-cols-6 mb-4">
        <select name="account_id" class="rounded-xl border px-3 py-2 text-sm bg-transparent md:col-span-2" required {% if read_only %}disabled{% endif %}>
          {% for a in accounts %}
            <option value="{{a.id}}" {{'selected' if selected_account_id==a.id else ''}}>{{a.label}} · {{a.imap_host}}</option>
          {% endfor %}
        </select>
        <input name="imap_password" type="password" class="rounded-xl border px-3 py-2 text-sm bg-transparent md:col-span-2" placeholder="Passwort (optional, falls gespeichert)" {% if read_only %}disabled{% endif %} />
        <input name="limit" type="number" min="1" max="200" value="50" class="rounded-xl border px-3 py-2 text-sm bg-transparent md:col-span-1" {% if read_only %}disabled{% endif %} />
        <button class="rounded-xl px-3 py-2 text-sm btn-outline md:col-span-1" type="submit" {% if read_only %}disabled{% endif %}>Sync</button>
      </form>
      {% endif %}

      {% if mail_status %}
      <div class="rounded-xl border border-slate-700 bg-slate-950/40 p-3 text-sm mb-3">{{ mail_status }}</div>
      {% endif %}

      <div class="overflow-auto">
        <table class="w-full text-sm">
          <thead>
            <tr class="text-left muted">
              <th class="py-2 pr-2">Betreff</th>
              <th class="py-2 pr-2">Von</th>
              <th class="py-2 pr-2">Datum</th>
            </tr>
          </thead>
          <tbody>
            {% for m in messages %}
            <tr class="border-t border-slate-800">
              <td class="py-2 pr-2">
                <a class="underline" href="/mail?message_id={{m.id}}{% if selected_account_id %}&account_id={{selected_account_id}}{% endif %}">{{m.subject_redacted}}</a>
              </td>
              <td class="py-2 pr-2">{{m.from_redacted}}</td>
              <td class="py-2 pr-2">{{m.received_at}}</td>
            </tr>
            {% else %}
            <tr><td colspan="3" class="py-3 muted">Noch keine synchronisierten Mails.</td></tr>
            {% endfor %}
          </tbody>
        </table>
      </div>
    </div>

    <div class="card p-4 rounded-2xl border">
      <div class="text-base font-semibold mb-2">Detail</div>
      {% if mail_detail %}
        <div class="text-xs muted mb-1">Von</div>
        <div class="text-sm mb-2">{{mail_detail.from_redacted}}</div>
        <div class="text-xs muted mb-1">An</div>
        <div class="text-sm mb-2">{{mail_detail.to_redacted}}</div>
        <div class="text-xs muted mb-1">Betreff</div>
        <div class="text-sm mb-2">{{mail_detail.subject_redacted}}</div>
        <div class="text-xs muted mb-1">Inhalt</div>
        <pre class="text-xs whitespace-pre-wrap rounded-xl border border-slate-800 p-3 max-h-80 overflow-auto">{{mail_detail.body_text_redacted}}</pre>
      {% else %}
        <div class="text-sm muted">Nachricht in der Inbox auswählen.</div>
      {% endif %}
      <div class="mt-4 border-t border-slate-800 pt-3">
        <div class="text-base font-semibold mb-2">Outbox (lokal)</div>
        <div class="space-y-2">
          {% for row in outbox %}
            <div class="rounded-xl border border-slate-800 p-2">
              <div class="text-xs muted">{{row.created_at}} · {{row.kind}}</div>
              <div class="text-xs">{{row.recipient_redacted}}</div>
              <div class="text-sm">{{row.body}}</div>
            </div>
          {% else %}
            <div class="text-sm muted">Keine Outbox-Einträge.</div>
          {% endfor %}
        </div>
      </div>
    </div>
  </div>

  <div class="card p-4 rounded-2xl border">
    <div class="text-lg font-semibold mb-1">Mail Agent (Compose)</div>
    <div class="text-sm opacity-80 mb-4">Entwurf lokal mit Template/Mock-LLM.</div>

    <div class="grid gap-3 md:grid-cols-2">
      <div>
        <label class="block text-xs opacity-70 mb-1">Empfänger (optional)</label>
        <input id="m_to" class="w-full rounded-xl border px-3 py-2 text-sm bg-transparent" placeholder="z.B. haendler@firma.de" />
      </div>
      <div>
        <label class="block text-xs opacity-70 mb-1">Betreff (optional)</label>
        <input id="m_subj" class="w-full rounded-xl border px-3 py-2 text-sm bg-transparent" placeholder="z.B. Mangel: Defekte Fliesenlieferung" />
      </div>
      <div>
        <label class="block text-xs opacity-70 mb-1">Ton</label>
        <select id="m_tone" class="w-full rounded-xl border px-3 py-2 text-sm bg-transparent">
          <option value="neutral" selected>Neutral</option>
          <option value="freundlich">Freundlich</option>
          <option value="formell">Formell</option>
          <option value="bestimmt">Bestimmt (Reklamation)</option>
          <option value="kurz">Sehr kurz</option>
        </select>
      </div>
      <div>
        <label class="block text-xs opacity-70 mb-1">Länge</label>
        <select id="m_len" class="w-full rounded-xl border px-3 py-2 text-sm bg-transparent">
          <option value="kurz" selected>Kurz</option>
          <option value="normal">Normal</option>
          <option value="detailliert">Detailliert</option>
        </select>
      </div>
      <div class="md:col-span-2">
        <label class="block text-xs opacity-70 mb-1">Kontext / Stichpunkte</label>
        <textarea id="m_ctx" class="w-full rounded-xl border px-3 py-2 text-sm bg-transparent h-32" placeholder="z.B. Bitte Fotos an Händler schicken, Rabatt anfragen, Lieferung vom ... (Details)"></textarea>
      </div>
    </div>

    <div class="mt-4 flex flex-wrap gap-2">
      <button id="m_gen" class="rounded-xl px-4 py-2 text-sm card btn-primary">Entwurf erzeugen</button>
      <button id="m_copy" class="rounded-xl px-4 py-2 text-sm btn-outline" disabled>Copy</button>
      <button id="m_eml" class="rounded-xl px-4 py-2 text-sm btn-outline" disabled>.eml Export</button>
      <button id="m_rewrite" class="rounded-xl px-4 py-2 text-sm btn-outline">Stil verbessern</button>
      <div class="text-xs opacity-70 flex items-center" id="m_status"></div>
    </div>
  </div>

  <div class="card p-4 rounded-2xl border">
    <div class="flex items-center justify-between mb-2">
      <div class="font-semibold">Output</div>
      <div class="text-xs opacity-70">Kopie: Betreff + Body</div>
    </div>
    <textarea id="m_out" class="w-full rounded-xl border px-3 py-2 text-sm bg-transparent h-[360px]" placeholder="Hier erscheint der Entwurf…"></textarea>
  </div>
</div>

<script>
(function(){
  const gen=document.getElementById('m_gen');
  const copy=document.getElementById('m_copy');
  const rewrite=document.getElementById('m_rewrite');
  const eml=document.getElementById('m_eml');
  const status=document.getElementById('m_status');
  const out=document.getElementById('m_out');

  function v(id){ return (document.getElementById(id)?.value||'').trim(); }

  async function run(){
    status.textContent='Generiere…';
    out.value='';
    copy.disabled=true;
    if(eml) eml.disabled=true;
    try{
      const res = await fetch('/api/mail/draft', {
        method:'POST',
        headers:{'Content-Type':'application/json'},
        body: JSON.stringify({
          to: v('m_to'),
          subject: v('m_subj'),
          tone: v('m_tone'),
          length: v('m_len'),
          context: v('m_ctx')
        })
      });
      const data = await res.json();
      if(!res.ok){
        status.textContent = 'Fehler: ' + (data.error || res.status);
        return;
      }
      out.value = data.text || '';
      copy.disabled = !out.value;
      if(eml) eml.disabled = !out.value;
      status.textContent = data.meta || 'OK';
    }catch(e){
      status.textContent='Fehler: '+e;
    }
  }

  async function doCopy(){
    try{
      await navigator.clipboard.writeText(out.value||'');
      status.textContent='In Zwischenablage kopiert.';
    }catch(e){
      status.textContent='Copy fehlgeschlagen (Browser-Rechte).';
    }
  }

  async function doEml(){
    if(!out.value) return;
    const payload = { to: v('m_to'), subject: v('m_subj'), body: out.value };
    const res = await fetch('/api/mail/eml', {method:'POST', headers:{'Content-Type':'application/json'}, body: JSON.stringify(payload)});
    const blob = await res.blob();
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = 'kukanilea_mail.eml';
    a.click();
    URL.revokeObjectURL(url);
  }

  function rewriteLocal(){
    if(!out.value) return;
    const lines = out.value.split('\\n').map(l => l.trim()).filter(Boolean);
    const greeting = lines[0]?.startsWith('Betreff') ? '' : 'Guten Tag,';
    const closing = 'Mit freundlichen Grüßen';
    const body = lines.filter(l => !l.toLowerCase().startsWith('betreff')).join('\\n');
    out.value = [greeting, body, '', closing].filter(Boolean).join('\\n');
    status.textContent='Stil verbessert (lokal).';
  }

  gen && gen.addEventListener('click', run);
  copy && copy.addEventListener('click', doCopy);
  rewrite && rewrite.addEventListener('click', rewriteLocal);
  eml && eml.addEventListener('click', doEml);
})();
</script>
"""

HTML_SETTINGS = """
<div class="grid gap-4">
  <div class="card p-4 rounded-2xl border">
    <div class="text-lg font-semibold mb-2">DEV Settings</div>
    <div class="grid gap-3 md:grid-cols-2 text-sm">
      <div>
        <div class="muted text-xs mb-1">Profile</div>
        <div><strong>{{ profile.name }}</strong></div>
        <div class="muted text-xs">Base Path: {{ profile.base_path }}</div>
      </div>
      <div>
        <div class="muted text-xs mb-1">Core DB</div>
        <div><strong>{{ core_db.path }}</strong></div>
        <div class="muted text-xs">Schema: {{ core_db.schema_version }} · Tenants: {{ core_db.tenants }}</div>
      </div>
      <div>
        <div class="muted text-xs mb-1">Auth DB</div>
        <div><strong>{{ auth_db_path }}</strong></div>
        <div class="muted text-xs">Schema: {{ auth_schema }} · Tenants: {{ auth_tenants }}</div>
      </div>
    </div>
  </div>

  <div class="card p-4 rounded-2xl border">
    <div class="text-sm font-semibold mb-2">DB wechseln (Allowlist)</div>
    <div class="flex flex-wrap gap-2 items-center">
      <select id="dbSelect" class="rounded-xl border px-3 py-2 text-sm bg-transparent">
        {% for p in db_files %}
          <option value="{{ p }}">{{ p }}</option>
        {% endfor %}
      </select>
      <button id="dbSwitch" class="rounded-xl px-3 py-2 text-sm btn-primary">DB wechseln</button>
      <span id="dbSwitchStatus" class="text-xs muted"></span>
    </div>
  </div>

  <div class="card p-4 rounded-2xl border">
    <div class="text-sm font-semibold mb-2">Ablage-Pfad wechseln (DEV)</div>
    <div class="flex flex-wrap gap-2 items-center">
      <select id="baseSelect" class="rounded-xl border px-3 py-2 text-sm bg-transparent">
        {% for p in base_paths %}
          <option value="{{ p }}">{{ p }}</option>
        {% endfor %}
      </select>
      <input id="baseCustom" class="rounded-xl border px-3 py-2 text-sm bg-transparent" placeholder="Benutzerdefinierter Pfad" />
      <button id="baseSwitch" class="rounded-xl px-3 py-2 text-sm btn-primary">Ablage wechseln</button>
      <span id="baseSwitchStatus" class="text-xs muted"></span>
    </div>
  </div>

  <div class="card p-4 rounded-2xl border">
    <div class="text-sm font-semibold mb-2">Import (DEV)</div>
    <div class="muted text-xs mb-2">IMPORT_ROOT: {{ import_root }}</div>
    <div class="flex flex-wrap gap-2 items-center">
      <button id="runImport" class="rounded-xl px-3 py-2 text-sm btn-outline">Import starten</button>
      <span id="importStatus" class="text-xs muted"></span>
    </div>
  </div>

  <div class="card p-4 rounded-2xl border">
    <div class="text-sm font-semibold mb-2">Tools</div>
    <div class="flex flex-wrap gap-2">
      <button id="seedUsers" class="rounded-xl px-3 py-2 text-sm btn-outline">Seed Dev Users</button>
      <button id="loadDemoData" class="rounded-xl px-3 py-2 text-sm btn-outline">Load Demo Data</button>
      <button id="rebuildIndex" class="rounded-xl px-3 py-2 text-sm btn-outline">Rebuild Index</button>
      <button id="fullScan" class="rounded-xl px-3 py-2 text-sm btn-outline">Full Scan</button>
      <button id="repairDrift" class="rounded-xl px-3 py-2 text-sm btn-outline">Repair Drift Scan</button>
      <button id="testLLM" class="rounded-xl px-3 py-2 text-sm btn-outline">Test LLM</button>
    </div>
    <div id="toolStatus" class="text-xs muted mt-2"></div>
  </div>
</div>

<script>
(function(){
  async function postJson(url, body){
    const r = await fetch(url, {method:'POST', headers:{'Content-Type':'application/json'}, body: JSON.stringify(body || {})});
    let j = {};
    try{ j = await r.json(); }catch(e){}
    if(!r.ok){
      throw new Error(j.message || j.error || ('HTTP ' + r.status));
    }
    return j;
  }

  const status = document.getElementById('toolStatus');
  const dbStatus = document.getElementById('dbSwitchStatus');
  const baseStatus = document.getElementById('baseSwitchStatus');
  const importStatus = document.getElementById('importStatus');

  document.getElementById('seedUsers')?.addEventListener('click', async () => {
    status.textContent = 'Seeding...';
    try{
      const j = await postJson('/api/dev/seed-users');
      status.textContent = j.message || 'OK';
    }catch(e){ status.textContent = 'Fehler: ' + e.message; }
  });
  document.getElementById('loadDemoData')?.addEventListener('click', async () => {
    status.textContent = 'Demo-Daten werden geladen...';
    try{
      const j = await postJson('/api/dev/load-demo-data');
      status.textContent = j.message || 'OK';
    }catch(e){ status.textContent = 'Fehler: ' + e.message; }
  });
  document.getElementById('rebuildIndex')?.addEventListener('click', async () => {
    status.textContent = 'Rebuild läuft...';
    try{
      const j = await postJson('/api/dev/rebuild-index');
      status.textContent = j.message || 'OK';
    }catch(e){ status.textContent = 'Fehler: ' + e.message; }
  });
  document.getElementById('fullScan')?.addEventListener('click', async () => {
    status.textContent = 'Scan läuft...';
    try{
      const j = await postJson('/api/dev/full-scan');
      status.textContent = j.message || 'OK';
    }catch(e){ status.textContent = 'Fehler: ' + e.message; }
  });
  document.getElementById('repairDrift')?.addEventListener('click', async () => {
    status.textContent = 'Drift-Scan läuft...';
    try{
      const j = await postJson('/api/dev/repair-drift');
      status.textContent = j.message || 'OK';
    }catch(e){ status.textContent = 'Fehler: ' + e.message; }
  });
  document.getElementById('testLLM')?.addEventListener('click', async () => {
    status.textContent = 'Teste LLM...';
    try{
      const j = await postJson('/api/dev/test-llm', {q:'suche rechnung von gerd'});
      status.textContent = j.message || 'OK';
    }catch(e){ status.textContent = 'Fehler: ' + e.message; }
  });
  document.getElementById('dbSwitch')?.addEventListener('click', async () => {
    const sel = document.getElementById('dbSelect');
    const path = sel ? sel.value : '';
    if(!path){ return; }
    dbStatus.textContent = 'Wechsle...';
    try{
      const j = await postJson('/api/dev/switch-db', {path});
      dbStatus.textContent = j.message || 'OK';
      window.location.reload();
    }catch(e){ dbStatus.textContent = 'Fehler: ' + e.message; }
  });
  document.getElementById('baseSwitch')?.addEventListener('click', async () => {
    const sel = document.getElementById('baseSelect');
    const custom = document.getElementById('baseCustom');
    const path = (custom && custom.value ? custom.value : (sel ? sel.value : ''));
    if(!path){ return; }
    baseStatus.textContent = 'Wechsle...';
    try{
      const j = await postJson('/api/dev/switch-base', {path});
      baseStatus.textContent = j.message || 'OK';
      window.location.reload();
    }catch(e){ baseStatus.textContent = 'Fehler: ' + e.message; }
  });

  document.getElementById('runImport')?.addEventListener('click', async () => {
    importStatus.textContent = 'Import läuft...';
    try{
      const j = await postJson('/api/dev/import/run');
      importStatus.textContent = j.message || 'OK';
    }catch(e){ importStatus.textContent = 'Fehler: ' + e.message; }
  });
})();
</script>
"""


def _mail_prompt(to: str, subject: str, tone: str, length: str, context: str) -> str:
    return f"""Du bist ein deutscher Office-Assistent. Schreibe einen professionellen E-Mail-Entwurf.
Wichtig:
- Du hast KEINEN Zugriff auf echte Systeme. Keine falschen Behauptungen.
- Klar, freundlich, ohne leere Floskeln.
- Wenn Fotos erwähnt werden: Bitte um Bestätigung, dass Fotos angehängt sind und nenne die Anzahl falls bekannt.
- Output-Format exakt:
BETREFF: <eine Zeile>
TEXT:
<Mailtext>

Empfänger: {to or "(nicht angegeben)"}
Betreff-Vorschlag (falls vorhanden): {subject or "(leer)"}
Ton: {tone}
Länge: {length}

Kontext/Stichpunkte:
{context or "(leer)"}
"""


def _postfach_redirect(
    *,
    account_id: str = "",
    thread_id: str = "",
    draft_id: str = "",
    status: str = "",
    query: str = "",
) -> str:
    return url_for(
        "web.postfach_page",
        account_id=(account_id or "").strip(),
        thread_id=(thread_id or "").strip(),
        draft_id=(draft_id or "").strip(),
        status=(status or "").strip(),
        q=(query or "").strip(),
    )


def _postfach_oauth_redirect_uri() -> str:
    configured = str(current_app.config.get("OAUTH_REDIRECT_BASE") or "").strip()
    if configured:
        return configured.rstrip("/") + "/postfach/accounts/oauth/callback"
    base = str(request.host_url or "").rstrip("/")
    return base + "/postfach/accounts/oauth/callback"


def _postfach_oauth_client(provider: str) -> tuple[str, str]:
    p = str(provider or "").strip().lower()
    if p == "google":
        return (
            str(current_app.config.get("GOOGLE_CLIENT_ID") or "").strip(),
            str(current_app.config.get("GOOGLE_CLIENT_SECRET") or "").strip(),
        )
    return (
        str(current_app.config.get("MICROSOFT_CLIENT_ID") or "").strip(),
        str(current_app.config.get("MICROSOFT_CLIENT_SECRET") or "").strip(),
    )


def _postfach_has_connected_oauth_token(tenant_id: str, account_id: str) -> bool:
    token = postfach_get_oauth_token(
        _core_db_path(),
        tenant_id=tenant_id,
        account_id=account_id,
    )
    return bool(token and str(token.get("access_token") or "").strip())


@bp.get("/postfach")
@bp.get("/mail")
@login_required
def postfach_page():
    if request.path == "/mail":
        q = request.query_string.decode("utf-8", errors="ignore")
        target = "/postfach"
        if q:
            target = f"{target}?{q}"
        return redirect(target, code=302)

    tenant_id = current_tenant()
    _ensure_postfach_tables()
    auth_db: AuthDB = current_app.extensions["auth_db"]
    selected_account_id = (request.args.get("account_id") or "").strip()
    selected_thread_id = (request.args.get("thread_id") or "").strip()
    selected_draft_id = (request.args.get("draft_id") or "").strip()
    postfach_status = (request.args.get("status") or "").strip()
    query = (request.args.get("q") or "").strip()

    accounts = postfach_list_accounts(_core_db_path(), tenant_id)
    for row in accounts:
        row["oauth_connected"] = _postfach_has_connected_oauth_token(
            tenant_id, str(row.get("id") or "")
        )
    if not selected_account_id and accounts:
        selected_account_id = str(accounts[0].get("id") or "")

    threads: list[dict[str, Any]] = []
    if selected_account_id:
        threads = postfach_list_threads(
            _core_db_path(),
            tenant_id=tenant_id,
            account_id=selected_account_id,
            filter_text=query,
            limit=200,
        )
        if not selected_thread_id and threads:
            selected_thread_id = str(threads[0].get("id") or "")

    thread_data = (
        postfach_get_thread(
            _core_db_path(),
            tenant_id=tenant_id,
            thread_id=selected_thread_id,
        )
        if selected_thread_id
        else None
    )
    drafts = (
        postfach_list_drafts_for_thread(
            _core_db_path(),
            tenant_id=tenant_id,
            thread_id=selected_thread_id,
            limit=20,
        )
        if selected_thread_id
        else []
    )

    selected_draft = (
        postfach_get_draft(
            _core_db_path(),
            tenant_id=tenant_id,
            draft_id=selected_draft_id,
            include_plain=True,
        )
        if selected_draft_id
        else None
    )
    if not selected_draft and drafts:
        selected_draft = postfach_get_draft(
            _core_db_path(),
            tenant_id=tenant_id,
            draft_id=str(drafts[0].get("id") or ""),
            include_plain=True,
        )

    outbox = auth_db.list_outbox(limit=20)
    postfach_key_ready = bool(postfach_email_encryption_ready())
    return _render_base(
        render_template(
            "postfach/index.html",
            accounts=accounts,
            selected_account_id=selected_account_id,
            threads=threads,
            selected_thread_id=selected_thread_id,
            thread_data=thread_data,
            drafts=drafts,
            selected_draft=selected_draft,
            postfach_status=postfach_status,
            postfach_key_ready=postfach_key_ready,
            search_query=query,
            outbox=outbox,
        ),
        active_tab="postfach",
    )


@bp.get("/postfach/thread/<thread_id>")
@login_required
def postfach_thread_page(thread_id: str):
    tenant_id = current_tenant()
    _ensure_postfach_tables()
    data = postfach_get_thread(
        _core_db_path(), tenant_id=tenant_id, thread_id=thread_id
    )
    if not data:
        return redirect(_postfach_redirect(status="Thread nicht gefunden."))
    return _render_base(
        render_template("postfach/thread.html", thread_data=data),
        active_tab="postfach",
    )


@bp.get("/postfach/compose/<draft_id>")
@login_required
def postfach_compose_page(draft_id: str):
    tenant_id = current_tenant()
    _ensure_postfach_tables()
    draft = postfach_get_draft(
        _core_db_path(), tenant_id=tenant_id, draft_id=draft_id, include_plain=True
    )
    if not draft:
        return redirect(_postfach_redirect(status="Entwurf nicht gefunden."))
    return _render_base(
        render_template("postfach/compose.html", draft=draft),
        active_tab="postfach",
    )


@bp.post("/postfach/accounts/add")
@bp.post("/mail/accounts/add")
@login_required
def postfach_account_add():
    if bool(current_app.config.get("READ_ONLY", False)):
        return redirect(_postfach_redirect(status="Read-only mode aktiv."))
    tenant_id = current_tenant()
    label = (request.form.get("label") or "").strip()
    auth_mode = (request.form.get("auth_mode") or "password").strip().lower()
    oauth_provider = (request.form.get("oauth_provider") or "").strip().lower()
    imap_host = (request.form.get("imap_host") or "").strip()
    imap_username = (request.form.get("imap_username") or "").strip()
    smtp_host = (request.form.get("smtp_host") or "").strip()
    smtp_username = (request.form.get("smtp_username") or "").strip()
    secret_plain = (request.form.get("secret") or "").strip()
    smtp_use_ssl = (request.form.get("smtp_use_ssl") or "1").strip() in {
        "1",
        "true",
        "on",
        "yes",
    }

    try:
        imap_port = int(request.form.get("imap_port") or 993)
    except Exception:
        imap_port = 993
    try:
        smtp_port = int(request.form.get("smtp_port") or 465)
    except Exception:
        smtp_port = 465

    if auth_mode in {"oauth_google", "oauth_microsoft"} and not oauth_provider:
        oauth_provider = "google" if auth_mode == "oauth_google" else "microsoft"
    if auth_mode in {"oauth_google", "oauth_microsoft"} and not imap_host:
        try:
            cfg = postfach_oauth_provider_config(oauth_provider)
            imap_host = str(cfg.get("imap_host") or "")
            imap_port = int(cfg.get("imap_port") or imap_port)
            smtp_host = str(cfg.get("smtp_host") or "")
            smtp_port = int(cfg.get("smtp_port") or smtp_port)
            if not smtp_use_ssl and oauth_provider == "google":
                smtp_use_ssl = True
        except Exception:
            pass

    if not label or not imap_host or not imap_username:
        return redirect(_postfach_redirect(status="Pflichtfelder fehlen."))
    if auth_mode == "password" and not secret_plain:
        return redirect(_postfach_redirect(status="Pflichtfelder fehlen."))
    if (
        auth_mode in {"oauth_google", "oauth_microsoft"}
        and not postfach_email_encryption_ready()
    ):
        return redirect(
            _postfach_redirect(
                status="EMAIL_ENCRYPTION_KEY fehlt. OAuth-Token koennen nicht sicher gespeichert werden."
            )
        )

    try:
        account_id = postfach_create_account(
            _core_db_path(),
            tenant_id=tenant_id,
            label=label,
            imap_host=imap_host,
            imap_port=imap_port,
            imap_username=imap_username,
            smtp_host=smtp_host,
            smtp_port=smtp_port,
            smtp_username=smtp_username,
            smtp_use_ssl=smtp_use_ssl,
            secret_plain=secret_plain,
            auth_mode=auth_mode,
            oauth_provider=oauth_provider or None,
        )
    except ValueError as exc:
        reason = str(exc)
        if reason == "email_encryption_key_missing":
            return redirect(
                _postfach_redirect(
                    status="EMAIL_ENCRYPTION_KEY fehlt. Postfach-Operationen sind deaktiviert."
                )
            )
        return redirect(
            _postfach_redirect(
                status=f"Account konnte nicht gespeichert werden ({reason})."
            )
        )

    status = "Account gespeichert."
    if auth_mode in {"oauth_google", "oauth_microsoft"}:
        status = "OAuth-Account gespeichert. Bitte jetzt verbinden."
    return redirect(_postfach_redirect(account_id=account_id, status=status))


@bp.post("/postfach/accounts/oauth/start")
@login_required
def postfach_account_oauth_start():
    if bool(current_app.config.get("READ_ONLY", False)):
        return redirect(_postfach_redirect(status="Read-only mode aktiv."))
    tenant_id = current_tenant()
    account_id = (request.form.get("account_id") or "").strip()
    if not account_id:
        return redirect(_postfach_redirect(status="Account fehlt."))
    account = postfach_get_account(_core_db_path(), tenant_id, account_id)
    if not account:
        return redirect(_postfach_redirect(status="Account nicht gefunden."))
    provider = str(account.get("oauth_provider") or "").strip().lower()
    if not provider:
        mode = str(account.get("auth_mode") or "").strip().lower()
        provider = "google" if mode == "oauth_google" else "microsoft"
    client_id, _client_secret = _postfach_oauth_client(provider)
    if not client_id:
        return redirect(
            _postfach_redirect(
                account_id=account_id,
                status=f"OAuth Client-ID fuer {provider} fehlt.",
            )
        )
    state = postfach_generate_oauth_state()
    verifier, challenge = postfach_generate_pkce_pair()
    session["postfach_oauth_state"] = state
    session["postfach_oauth_verifier"] = verifier
    session["postfach_oauth_account_id"] = account_id
    session["postfach_oauth_provider"] = provider
    redirect_uri = _postfach_oauth_redirect_uri()
    try:
        auth_url = postfach_build_authorization_url(
            provider=provider,
            client_id=client_id,
            redirect_uri=redirect_uri,
            state=state,
            code_challenge=challenge,
            login_hint=str(account.get("imap_username") or "").strip() or None,
        )
    except Exception as exc:
        postfach_set_account_oauth_state(
            _core_db_path(),
            tenant_id=tenant_id,
            account_id=account_id,
            oauth_status="error",
            oauth_last_error=f"oauth_start_failed:{exc}",
            oauth_provider=provider,
        )
        return redirect(
            _postfach_redirect(
                account_id=account_id,
                status=f"OAuth Start fehlgeschlagen ({exc}).",
            )
        )
    postfach_set_account_oauth_state(
        _core_db_path(),
        tenant_id=tenant_id,
        account_id=account_id,
        oauth_status="pending",
        oauth_last_error="",
        oauth_provider=provider,
    )
    return redirect(auth_url)


@bp.get("/postfach/accounts/oauth/callback")
@login_required
def postfach_account_oauth_callback():
    tenant_id = current_tenant()
    state = str(request.args.get("state") or "").strip()
    code = str(request.args.get("code") or "").strip()
    error = str(request.args.get("error") or "").strip()
    expected_state = str(session.get("postfach_oauth_state") or "")
    account_id = str(session.get("postfach_oauth_account_id") or "")
    provider = str(session.get("postfach_oauth_provider") or "")
    verifier = str(session.get("postfach_oauth_verifier") or "")

    session.pop("postfach_oauth_state", None)
    session.pop("postfach_oauth_account_id", None)
    session.pop("postfach_oauth_provider", None)
    session.pop("postfach_oauth_verifier", None)

    if not account_id:
        return redirect(
            _postfach_redirect(status="OAuth Callback ohne Account-Kontext.")
        )
    if error:
        postfach_set_account_oauth_state(
            _core_db_path(),
            tenant_id=tenant_id,
            account_id=account_id,
            oauth_status="error",
            oauth_last_error=f"oauth_callback_error:{error}",
            oauth_provider=provider,
        )
        return redirect(
            _postfach_redirect(account_id=account_id, status=f"OAuth Fehler: {error}")
        )
    if (
        not state
        or not expected_state
        or not hmac.compare_digest(state, expected_state)
    ):
        postfach_set_account_oauth_state(
            _core_db_path(),
            tenant_id=tenant_id,
            account_id=account_id,
            oauth_status="error",
            oauth_last_error="oauth_state_mismatch",
            oauth_provider=provider,
        )
        return redirect(
            _postfach_redirect(
                account_id=account_id,
                status="OAuth State ungueltig. Bitte erneut verbinden.",
            )
        )
    if not code or not verifier:
        return redirect(
            _postfach_redirect(
                account_id=account_id,
                status="OAuth Code/Verifier fehlt.",
            )
        )

    client_id, client_secret = _postfach_oauth_client(provider)
    if not client_id:
        return redirect(
            _postfach_redirect(
                account_id=account_id,
                status="OAuth Client-Konfiguration fehlt.",
            )
        )
    try:
        tokens = postfach_exchange_code_for_tokens(
            provider=provider,
            client_id=client_id,
            client_secret=client_secret or None,
            code=code,
            redirect_uri=_postfach_oauth_redirect_uri(),
            code_verifier=verifier,
        )
        postfach_save_oauth_token(
            _core_db_path(),
            tenant_id=tenant_id,
            account_id=account_id,
            provider=provider,
            access_token=str(tokens.get("access_token") or ""),
            refresh_token=str(tokens.get("refresh_token") or ""),
            expires_at=str(tokens.get("expires_at") or ""),
            scopes=[str(s) for s in (tokens.get("scopes") or [])],
            token_type=str(tokens.get("token_type") or "Bearer"),
        )
        postfach_set_account_oauth_state(
            _core_db_path(),
            tenant_id=tenant_id,
            account_id=account_id,
            oauth_status="connected",
            oauth_last_error="",
            oauth_provider=provider,
            oauth_scopes=[str(s) for s in (tokens.get("scopes") or [])],
        )
    except Exception as exc:
        postfach_set_account_oauth_state(
            _core_db_path(),
            tenant_id=tenant_id,
            account_id=account_id,
            oauth_status="error",
            oauth_last_error=f"oauth_exchange_failed:{exc}",
            oauth_provider=provider,
        )
        return redirect(
            _postfach_redirect(
                account_id=account_id,
                status=f"OAuth Token-Austausch fehlgeschlagen ({exc}).",
            )
        )
    return redirect(
        _postfach_redirect(account_id=account_id, status="OAuth erfolgreich verbunden.")
    )


@bp.post("/postfach/accounts/oauth/disconnect")
@login_required
def postfach_account_oauth_disconnect():
    if bool(current_app.config.get("READ_ONLY", False)):
        return redirect(_postfach_redirect(status="Read-only mode aktiv."))
    tenant_id = current_tenant()
    account_id = (request.form.get("account_id") or "").strip()
    provider = (request.form.get("provider") or "").strip().lower() or None
    if not account_id:
        return redirect(_postfach_redirect(status="Account fehlt."))
    postfach_clear_oauth_token(
        _core_db_path(),
        tenant_id=tenant_id,
        account_id=account_id,
        provider=provider,
    )
    postfach_set_account_oauth_state(
        _core_db_path(),
        tenant_id=tenant_id,
        account_id=account_id,
        oauth_status="not_connected",
        oauth_last_error="",
        oauth_provider=provider or None,
    )
    return redirect(
        _postfach_redirect(account_id=account_id, status="OAuth Verbindung getrennt.")
    )


@bp.post("/postfach/accounts/sync")
@bp.post("/mail/accounts/sync")
@login_required
def postfach_account_sync():
    if bool(current_app.config.get("READ_ONLY", False)):
        return redirect(_postfach_redirect(status="Read-only mode aktiv."))
    tenant_id = current_tenant()
    account_id = (request.form.get("account_id") or "").strip()
    if not account_id:
        return redirect(_postfach_redirect(status="Account fehlt."))
    try:
        limit = int(request.form.get("limit") or 50)
    except Exception:
        limit = 50

    result = postfach_sync_account(
        _core_db_path(),
        tenant_id=tenant_id,
        account_id=account_id,
        limit=limit,
    )
    if bool(result.get("ok")):
        status = (
            f"Sync erfolgreich: {int(result.get('imported') or 0)} importiert, "
            f"{int(result.get('duplicates') or 0)} Duplikate."
        )
    else:
        status = f"Sync fehlgeschlagen: {result.get('reason')}"
    return redirect(_postfach_redirect(account_id=account_id, status=status))


@bp.post("/postfach/thread/<thread_id>/draft")
@login_required
def postfach_thread_draft(thread_id: str):
    if bool(current_app.config.get("READ_ONLY", False)):
        return redirect(
            _postfach_redirect(thread_id=thread_id, status="Read-only mode aktiv.")
        )
    tenant_id = current_tenant()
    data = postfach_get_thread(
        _core_db_path(), tenant_id=tenant_id, thread_id=thread_id
    )
    if not data:
        return redirect(_postfach_redirect(status="Thread nicht gefunden."))
    thread = data["thread"]
    messages = data.get("messages", [])
    last_msg = messages[-1] if messages else {}
    intent = (request.form.get("intent") or "antworten").strip()
    tone = (request.form.get("tone") or "neutral").strip()
    citations_required = (request.form.get("citations_required") or "").strip() in {
        "1",
        "true",
        "on",
        "yes",
    }
    body = (
        "Guten Tag,\n\n"
        f"vielen Dank fuer Ihre Nachricht. Wir haben Ihr Anliegen ({intent}) erhalten "
        f"und bereiten eine Rueckmeldung im Ton '{tone}' vor.\n\n"
        "Naechste Schritte:\n"
        "- Eingang geprueft\n"
        "- Anliegen intern priorisiert\n"
        "- Rueckmeldung vorbereitet\n\n"
        f"Quellenhinweise erforderlich: {'Ja' if citations_required else 'Nein'}\n"
        f"Thread-ID: {thread_id}\n\n"
        "Mit freundlichen Gruessen\nKUKANILEA Systems"
    )
    subject = str(
        last_msg.get("subject_redacted") or thread.get("subject_redacted") or ""
    )
    to_value = str(last_msg.get("from_redacted") or "")
    try:
        draft_id = postfach_create_draft(
            _core_db_path(),
            tenant_id=tenant_id,
            account_id=str(thread.get("account_id") or ""),
            thread_id=thread_id,
            to_value=to_value,
            subject_value=f"Re: {subject}" if subject else "Re: Ihre Nachricht",
            body_value=body,
        )
    except ValueError as exc:
        return redirect(
            _postfach_redirect(
                account_id=str(thread.get("account_id") or ""),
                thread_id=thread_id,
                status=f"Entwurf fehlgeschlagen: {exc}",
            )
        )
    return redirect(
        _postfach_redirect(
            account_id=str(thread.get("account_id") or ""),
            thread_id=thread_id,
            draft_id=draft_id,
            status="Entwurf erstellt.",
        )
    )


@bp.post("/postfach/drafts/send")
@login_required
def postfach_draft_send():
    if bool(current_app.config.get("READ_ONLY", False)):
        return redirect(_postfach_redirect(status="Read-only mode aktiv."))
    tenant_id = current_tenant()
    draft_id = (request.form.get("draft_id") or "").strip()
    account_id = (request.form.get("account_id") or "").strip()
    thread_id = (request.form.get("thread_id") or "").strip()
    user_confirmed = (request.form.get("user_confirmed") or "").strip() in {
        "1",
        "true",
        "on",
        "yes",
    }
    safety_ack = (request.form.get("safety_ack") or "").strip() in {
        "1",
        "true",
        "on",
        "yes",
    }
    safety = postfach_safety_check_draft(
        _core_db_path(),
        tenant_id=tenant_id,
        draft_id=draft_id,
    )
    if (
        bool(safety.get("ok"))
        and int(safety.get("warning_count") or 0) > 0
        and not safety_ack
    ):
        warnings = safety.get("warnings") or []
        first_warning = str((warnings[0] or {}).get("message") or "Warnung")
        return redirect(
            _postfach_redirect(
                account_id=account_id,
                thread_id=thread_id,
                status=f"Sicherheitscheck: {first_warning} (bitte bestaetigen).",
            )
        )
    result = postfach_send_draft(
        _core_db_path(),
        tenant_id=tenant_id,
        draft_id=draft_id,
        user_confirmed=user_confirmed,
    )
    if not bool(result.get("ok")):
        status = f"Versand blockiert: {result.get('reason')}"
        return redirect(
            _postfach_redirect(
                account_id=account_id, thread_id=thread_id, status=status
            )
        )
    status = "Entwurf versendet."
    return redirect(
        _postfach_redirect(
            account_id=account_id,
            thread_id=str(result.get("thread_id") or thread_id),
            status=status,
        )
    )


@bp.post("/postfach/drafts/safety-check")
@login_required
def postfach_draft_safety_check():
    tenant_id = current_tenant()
    draft_id = (request.form.get("draft_id") or "").strip()
    account_id = (request.form.get("account_id") or "").strip()
    thread_id = (request.form.get("thread_id") or "").strip()
    if not draft_id:
        return redirect(
            _postfach_redirect(
                account_id=account_id, thread_id=thread_id, status="Draft fehlt."
            )
        )
    safety = postfach_safety_check_draft(
        _core_db_path(),
        tenant_id=tenant_id,
        draft_id=draft_id,
    )
    if not bool(safety.get("ok")):
        return redirect(
            _postfach_redirect(
                account_id=account_id,
                thread_id=thread_id,
                status=f"Sicherheitscheck fehlgeschlagen: {safety.get('reason')}",
            )
        )
    count = int(safety.get("warning_count") or 0)
    status = f"Sicherheitscheck: {count} Warnungen."
    return redirect(
        _postfach_redirect(
            account_id=account_id, thread_id=thread_id, draft_id=draft_id, status=status
        )
    )


@bp.post("/postfach/thread/<thread_id>/link")
@login_required
def postfach_thread_link(thread_id: str):
    if bool(current_app.config.get("READ_ONLY", False)):
        return redirect(
            _postfach_redirect(thread_id=thread_id, status="Read-only mode aktiv.")
        )
    tenant_id = current_tenant()
    account_id = (request.form.get("account_id") or "").strip()
    result = postfach_link_entities(
        _core_db_path(),
        tenant_id=tenant_id,
        thread_id=thread_id,
        customer_id=(request.form.get("customer_id") or "").strip() or None,
        project_id=(request.form.get("project_id") or "").strip() or None,
        lead_id=(request.form.get("lead_id") or "").strip() or None,
    )
    return redirect(
        _postfach_redirect(
            account_id=account_id,
            thread_id=thread_id,
            status=f"Verknuepfungen erstellt: {int(result.get('links_created') or 0)}",
        )
    )


@bp.post("/postfach/thread/<thread_id>/extract")
@login_required
def postfach_thread_extract(thread_id: str):
    tenant_id = current_tenant()
    account_id = (request.form.get("account_id") or "").strip()
    schema_name = (request.form.get("schema_name") or "default").strip()
    result = postfach_extract_structured(
        _core_db_path(),
        tenant_id=tenant_id,
        thread_id=thread_id,
        schema_name=schema_name,
    )
    if not bool(result.get("ok")):
        status = f"Extraktion fehlgeschlagen: {result.get('reason')}"
    else:
        fields = result.get("fields") or {}
        status = (
            f"Extraktion ok (Schema={fields.get('schema')}, "
            f"Zeilen={int(fields.get('line_count') or 0)})."
        )
    return redirect(
        _postfach_redirect(account_id=account_id, thread_id=thread_id, status=status)
    )


@bp.post("/postfach/thread/<thread_id>/intake")
@login_required
def postfach_thread_intake(thread_id: str):
    tenant_id = current_tenant()
    account_id = (request.form.get("account_id") or "").strip()
    result = postfach_extract_intake(
        _core_db_path(),
        tenant_id=tenant_id,
        thread_id=thread_id,
    )
    if not bool(result.get("ok")):
        status = f"Intake fehlgeschlagen: {result.get('reason')}"
    else:
        fields = result.get("fields") or {}
        status = (
            f"Intake extrahiert (Intent={fields.get('intent')}, "
            f"Nachrichten={int(fields.get('message_count') or 0)})."
        )
    return redirect(
        _postfach_redirect(account_id=account_id, thread_id=thread_id, status=status)
    )


@bp.post("/postfach/thread/<thread_id>/followup")
@login_required
def postfach_thread_followup(thread_id: str):
    if bool(current_app.config.get("READ_ONLY", False)):
        return redirect(
            _postfach_redirect(thread_id=thread_id, status="Read-only mode aktiv.")
        )
    tenant_id = current_tenant()
    account_id = (request.form.get("account_id") or "").strip()
    due_at = (request.form.get("due_at") or "").strip()
    owner = (request.form.get("owner") or "").strip() or str(current_user() or "dev")
    title = (request.form.get("title") or "").strip() or "Postfach Follow-up"
    result = postfach_create_followup_task(
        _core_db_path(),
        tenant_id=tenant_id,
        thread_id=thread_id,
        due_at=due_at,
        owner=owner,
        title=title,
        created_by=str(current_user() or "dev"),
    )
    return redirect(
        _postfach_redirect(
            account_id=account_id,
            thread_id=thread_id,
            status=f"Follow-up Aufgabe erstellt (Task #{int(result.get('task_id') or 0)}).",
        )
    )


@bp.post("/postfach/thread/<thread_id>/case")
@login_required
def postfach_thread_create_case(thread_id: str):
    if bool(current_app.config.get("READ_ONLY", False)):
        return redirect(
            _postfach_redirect(thread_id=thread_id, status="Read-only mode aktiv.")
        )
    tenant_id = current_tenant()
    account_id = (request.form.get("account_id") or "").strip()
    data = postfach_get_thread(
        _core_db_path(), tenant_id=tenant_id, thread_id=thread_id
    )
    if not data:
        return redirect(_postfach_redirect(status="Thread nicht gefunden."))
    if not callable(task_create_fn):
        return redirect(
            _postfach_redirect(
                account_id=account_id,
                thread_id=thread_id,
                status="Task-System nicht verfuegbar.",
            )
        )
    thread = data.get("thread") or {}
    title = f"Case: {str(thread.get('subject_redacted') or thread_id)[:160]}"
    try:
        case_id = int(
            task_create_fn(  # type: ignore[misc]
                tenant=tenant_id,
                severity="INFO",
                task_type="CASE",
                title=title,
                details=f"Postfach Thread: {thread_id}",
                created_by=str(current_user() or "dev"),
            )
        )
    except Exception as exc:
        return redirect(
            _postfach_redirect(
                account_id=account_id,
                thread_id=thread_id,
                status=f"Case-Erzeugung fehlgeschlagen: {exc}",
            )
        )
    return redirect(
        _postfach_redirect(
            account_id=account_id,
            thread_id=thread_id,
            status=f"Case erstellt (Task #{case_id}).",
        )
    )


@bp.post("/postfach/thread/<thread_id>/tasks")
@login_required
def postfach_thread_create_tasks(thread_id: str):
    if bool(current_app.config.get("READ_ONLY", False)):
        return redirect(
            _postfach_redirect(thread_id=thread_id, status="Read-only mode aktiv.")
        )
    tenant_id = current_tenant()
    account_id = (request.form.get("account_id") or "").strip()
    intake = postfach_extract_intake(
        _core_db_path(),
        tenant_id=tenant_id,
        thread_id=thread_id,
    )
    if not bool(intake.get("ok")):
        return redirect(
            _postfach_redirect(
                account_id=account_id,
                thread_id=thread_id,
                status=f"Task-Intake fehlgeschlagen: {intake.get('reason')}",
            )
        )
    fields = intake.get("fields") or {}
    intent = str(fields.get("intent") or "general_inquiry")
    task_ids: list[int] = []
    if not callable(task_create_fn):
        return redirect(
            _postfach_redirect(
                account_id=account_id,
                thread_id=thread_id,
                status="Task-System nicht verfuegbar.",
            )
        )
    try:
        task_ids.append(
            int(
                task_create_fn(  # type: ignore[misc]
                    tenant=tenant_id,
                    severity="INFO",
                    task_type="FOLLOWUP",
                    title=f"Postfach Follow-up ({intent})",
                    details=f"Thread: {thread_id}",
                    created_by=str(current_user() or "dev"),
                )
            )
        )
        if intent in {"complaint", "quote_request"}:
            task_ids.append(
                int(
                    task_create_fn(  # type: ignore[misc]
                        tenant=tenant_id,
                        severity="INFO",
                        task_type="GENERAL",
                        title=f"Postfach Klaerung ({intent})",
                        details=f"Thread: {thread_id}",
                        created_by=str(current_user() or "dev"),
                    )
                )
            )
    except Exception as exc:
        return redirect(
            _postfach_redirect(
                account_id=account_id,
                thread_id=thread_id,
                status=f"Task-Erzeugung fehlgeschlagen: {exc}",
            )
        )
    return redirect(
        _postfach_redirect(
            account_id=account_id,
            thread_id=thread_id,
            status=f"Aufgaben erzeugt: {', '.join(str(t) for t in task_ids)}",
        )
    )


@bp.post("/postfach/thread/<thread_id>/lead")
@login_required
def postfach_thread_create_lead(thread_id: str):
    if bool(current_app.config.get("READ_ONLY", False)):
        return redirect(
            _postfach_redirect(thread_id=thread_id, status="Read-only mode aktiv.")
        )
    tenant_id = current_tenant()
    account_id = (request.form.get("account_id") or "").strip()
    data = postfach_get_thread(
        _core_db_path(), tenant_id=tenant_id, thread_id=thread_id
    )
    if not data:
        return redirect(_postfach_redirect(status="Thread nicht gefunden."))
    thread = data.get("thread") or {}
    messages = data.get("messages") or []
    newest = messages[-1] if messages else {}
    subject = str(
        thread.get("subject_redacted")
        or newest.get("subject_redacted")
        or "Neue Anfrage"
    )
    message = str(newest.get("redacted_text") or "Anfrage aus Postfach")
    try:
        lead_id = leads_create(
            tenant_id=tenant_id,
            source="email",
            contact_name="Postfach Anfrage",
            contact_email="postfach.request@kukanilea.local",
            contact_phone="+490000000000",
            subject=subject[:500],
            message=message[:20000],
            actor_user_id=str(current_user() or "dev"),
        )
    except ConflictError:
        return redirect(
            _postfach_redirect(
                account_id=account_id, thread_id=thread_id, status="Lead-Konflikt."
            )
        )
    except Exception as exc:
        return redirect(
            _postfach_redirect(
                account_id=account_id,
                thread_id=thread_id,
                status=f"Lead-Erzeugung fehlgeschlagen: {exc}",
            )
        )
    postfach_link_entities(
        _core_db_path(),
        tenant_id=tenant_id,
        thread_id=thread_id,
        lead_id=lead_id,
    )
    return redirect(
        _postfach_redirect(
            account_id=account_id,
            thread_id=thread_id,
            status=f"Lead erstellt: {lead_id}",
        )
    )


@bp.get("/settings")
@login_required
def settings_page():
    if current_role() not in {"ADMIN", "DEV"}:
        return json_error("forbidden", "Nicht erlaubt.", status=403)
    auth_db: AuthDB = current_app.extensions["auth_db"]
    if callable(getattr(core, "get_db_info", None)):
        core_db = core.get_db_info()
    else:
        core_db = {
            "path": str(getattr(core, "DB_PATH", "")),
            "schema_version": "?",
            "tenants": "?",
        }
    return _render_base(
        render_template_string(
            HTML_SETTINGS,
            core_db=core_db,
            auth_db_path=str(auth_db.path),
            auth_schema=auth_db.get_schema_version(),
            auth_tenants=auth_db.count_tenants(),
            db_files=[str(p) for p in _list_allowlisted_db_files()],
            base_paths=[str(p) for p in _list_allowlisted_base_paths()],
            profile=_get_profile(),
            import_root=str(current_app.config.get("IMPORT_ROOT", "")),
        ),
        active_tab="settings",
    )


@bp.post("/api/dev/seed-users")
@login_required
@require_role("DEV")
def api_seed_users():
    auth_db: AuthDB = current_app.extensions["auth_db"]
    msg = _seed_dev_users(auth_db)
    _audit("seed_users", meta={"status": "ok"})
    return jsonify(ok=True, message=msg)


@bp.post("/api/dev/load-demo-data")
@login_required
@require_role("DEV")
def api_load_demo_data():
    if bool(current_app.config.get("READ_ONLY", False)):
        return json_error("read_only", "Read-only mode aktiv.", status=403)
    tenant_id = current_tenant() or str(
        current_app.config.get("TENANT_DEFAULT", "KUKANILEA")
    )
    _ensure_postfach_tables()
    summary = generate_demo_data(db_path=_core_db_path(), tenant_id=tenant_id)
    _audit("demo_data_load", meta={"tenant_id": tenant_id, "summary": summary})
    return jsonify(ok=True, message="Demo-Daten geladen.", summary=summary)


@bp.post("/api/dev/rebuild-index")
@login_required
@require_role("DEV")
def api_rebuild_index():
    if callable(getattr(core, "index_rebuild", None)):
        result = core.index_rebuild()
    elif callable(getattr(core, "index_run_full", None)):
        result = core.index_run_full()
    else:
        return jsonify(ok=False, message="Indexing nicht verfügbar."), 400
    _DEV_STATUS["index"] = result
    _audit("rebuild_index", meta={"result": result})
    return jsonify(ok=True, message="Index neu aufgebaut.", result=result)


@bp.post("/api/dev/full-scan")
@login_required
@require_role("DEV")
def api_full_scan():
    if callable(getattr(core, "index_run_full", None)):
        result = core.index_run_full()
    else:
        return jsonify(ok=False, message="Scan nicht verfügbar."), 400
    _DEV_STATUS["scan"] = result
    _audit("full_scan", meta={"result": result})
    return jsonify(ok=True, message="Scan abgeschlossen.", result=result)


@bp.post("/api/dev/repair-drift")
@login_required
@require_role("DEV")
def api_repair_drift():
    if callable(getattr(core, "index_run_full", None)):
        result = core.index_run_full()
    else:
        return jsonify(ok=False, message="Drift-Scan nicht verfügbar."), 400
    _DEV_STATUS["scan"] = result
    _audit("repair_drift", meta={"result": result})
    return jsonify(ok=True, message="Drift-Scan abgeschlossen.", result=result)


@bp.post("/api/dev/import/run")
@login_required
@require_role("DEV")
def api_import_run():
    import_root = Path(str(current_app.config.get("IMPORT_ROOT", ""))).expanduser()
    if not str(import_root):
        return json_error("import_root_missing", "IMPORT_ROOT fehlt.", status=400)
    if not _is_allowlisted_path(import_root):
        return json_error(
            "import_root_forbidden", "IMPORT_ROOT nicht erlaubt.", status=403
        )
    if not import_root.exists():
        return json_error(
            "import_root_missing", "IMPORT_ROOT existiert nicht.", status=400
        )
    if callable(getattr(core, "import_run", None)):
        result = core.import_run(
            import_root=import_root,
            user=str(current_user() or "dev"),
            role=str(current_role()),
        )
    else:
        return json_error("import_not_available", "Import nicht verfügbar.", status=400)
    _DEV_STATUS["scan"] = result
    _audit("import_run", meta={"result": result, "root": str(import_root)})
    return jsonify(ok=True, message="Import abgeschlossen.", result=result)


@bp.post("/api/dev/switch-db")
@login_required
@require_role("DEV")
def api_switch_db():
    payload = request.get_json(silent=True) or {}
    path = Path(str(payload.get("path", ""))).expanduser()
    if not path:
        return jsonify(ok=False, message="Pfad fehlt."), 400
    if not _is_allowlisted_path(path):
        return jsonify(ok=False, message="Pfad nicht erlaubt."), 400
    if not path.exists():
        return jsonify(ok=False, message="Datei existiert nicht."), 400
    old_path = str(getattr(core, "DB_PATH", ""))
    if callable(getattr(core, "set_db_path", None)):
        core.set_db_path(path)
        _DEV_STATUS["db"] = {"old": old_path, "new": str(path)}
        _audit("switch_db", target=str(path), meta={"old": old_path})
        return jsonify(ok=True, message="DB gewechselt.", path=str(path))
    return jsonify(ok=False, message="DB switch nicht verfügbar."), 400


@bp.post("/api/dev/switch-base")
@login_required
@require_role("DEV")
def api_switch_base():
    payload = request.get_json(silent=True) or {}
    path = Path(str(payload.get("path", ""))).expanduser()
    if not path:
        return jsonify(ok=False, message="Pfad fehlt."), 400
    if not _is_storage_path_valid(path):
        return (
            jsonify(ok=False, message="Pfad nicht erlaubt oder nicht vorhanden."),
            400,
        )
    old_path = str(getattr(core, "BASE_PATH", ""))
    if callable(getattr(core, "set_base_path", None)):
        core.set_base_path(path)
        global BASE_PATH
        BASE_PATH = path
        _DEV_STATUS["base"] = {"old": old_path, "new": str(path)}
        _audit("switch_base", target=str(path), meta={"old": old_path})
        return jsonify(ok=True, message="Ablage gewechselt.", path=str(path))
    return jsonify(ok=False, message="Ablage switch nicht verfügbar."), 400


@bp.post("/api/dev/test-llm")
@login_required
@require_role("DEV")
def api_test_llm():
    payload = request.get_json(silent=True) or {}
    q = str(payload.get("q") or "suche rechnung")
    llm = getattr(ORCHESTRATOR, "llm", None)
    if not llm:
        return jsonify(ok=False, message="LLM nicht verfügbar."), 400
    result = llm.rewrite_query(q)
    _DEV_STATUS["llm"] = result
    _audit("test_llm", meta={"result": result})
    return jsonify(ok=True, message=f"LLM: {llm.name}, intent={result.get('intent')}")


@bp.post("/api/mail/draft")
@login_required
def api_mail_draft():
    try:
        payload = request.get_json(force=True) or {}
        to = (payload.get("to") or "").strip()
        subject = (payload.get("subject") or "").strip()
        tone = (payload.get("tone") or "neutral").strip()
        length = (payload.get("length") or "kurz").strip()
        context = (payload.get("context") or "").strip()

        if not context and not subject:
            return jsonify({"error": "Bitte Kontext oder Betreff angeben."}), 400

        text = _mock_generate(_mail_prompt(to, subject, tone, length, context))
        return jsonify({"text": text, "meta": "mode=mock"}), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@bp.post("/api/mail/eml")
@login_required
def api_mail_eml():
    payload = request.get_json(force=True) or {}
    to = (payload.get("to") or "").strip()
    subject = (payload.get("subject") or "").strip()
    body = (payload.get("body") or "").strip()
    if not body:
        return jsonify({"error": "Body fehlt."}), 400
    import email.message

    msg = email.message.EmailMessage()
    msg["To"] = to or "unknown@example.com"
    msg["From"] = "noreply@kukanilea.local"
    msg["Subject"] = subject or "KUKANILEA Entwurf"
    msg.set_content(body)
    eml_bytes = msg.as_bytes()
    return current_app.response_class(eml_bytes, mimetype="message/rfc822")


@bp.route("/")
def index():
    items_meta = list_pending() or []
    items = [x.get("_token") for x in items_meta if x.get("_token")]
    meta = {}
    for it in items_meta:
        t = it.get("_token")
        if t:
            meta[t] = {
                "filename": it.get("filename", ""),
                "progress": float(it.get("progress", 0.0) or 0.0),
                "progress_phase": it.get("progress_phase", ""),
            }
    return _render_base(
        render_template_string(HTML_INDEX, items=items, meta=meta), active_tab="upload"
    )


@bp.route("/upload", methods=["POST"])
def upload():
    f = request.files.get("file")
    if not f or not f.filename:
        return jsonify(error="no_file"), 400
    tenant = _norm_tenant(current_tenant() or "default")
    # tenant is fixed by license/account; no user input here.
    filename = _safe_filename(f.filename)
    if not _is_allowed_ext(filename):
        return jsonify(error="unsupported"), 400
    tenant_in = EINGANG / tenant
    tenant_in.mkdir(parents=True, exist_ok=True)
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    dest = tenant_in / f"{ts}__{filename}"
    f.save(dest)
    token = analyze_to_pending(dest)
    try:
        p = read_pending(token) or {}
        p["tenant"] = tenant
        w = _wizard_get(p)
        w["tenant"] = tenant
        p["wizard"] = w
        write_pending(token, p)
    except Exception:
        pass
    return jsonify(token=token, tenant=tenant)


@bp.route("/review/<token>/delete", methods=["POST"])
def review_delete(token: str):
    try:
        delete_pending(token)
    except Exception:
        pass
    return redirect(url_for("web.index"))


@bp.route("/file/<token>")
def file_preview(token: str):
    p = read_pending(token)
    if not p:
        abort(404)
    file_path = Path(p.get("path", ""))
    if not file_path.exists():
        abort(404)
    if not _is_allowed_path(file_path):
        abort(403)
    return send_file(file_path, as_attachment=False)


@bp.route("/review/<token>/kdnr", methods=["GET", "POST"])
def review(token: str):
    p = read_pending(token)
    if not p:
        return _render_base(_card("error", "Nicht gefunden."), active_tab="upload")
    if p.get("status") == "ANALYZING":
        right = _card(
            "info", "Analyse läuft noch. Bitte kurz warten oder zurück zur Übersicht."
        )
        return _render_base(
            render_template_string(
                HTML_REVIEW_SPLIT,
                token=token,
                filename=p.get("filename", ""),
                is_pdf=True,
                is_text=False,
                preview="",
                right=right,
                w=_wizard_get(p),
                suggested_doctype="SONSTIGES",
                suggested_date="",
                confidence=0,
            ),
            active_tab="upload",
        )

    w = _wizard_get(p)
    if True:
        # Tenant is fixed per account/license
        w["tenant"] = _norm_tenant(current_tenant() or p.get("tenant", "") or "default")

    suggested_doctype = (p.get("doctype_suggested") or "SONSTIGES").upper()
    if not w.get("doctype"):
        w["doctype"] = (
            suggested_doctype if suggested_doctype in DOCTYPE_CHOICES else "SONSTIGES"
        )
    suggested_date = (p.get("doc_date_suggested") or "").strip()
    confidence = 40
    if suggested_doctype and suggested_doctype != "SONSTIGES":
        confidence += 20
    if suggested_date:
        confidence += 20
    if w.get("kdnr"):
        confidence += 20
    confidence = min(95, confidence)

    # Suggest an existing customer folder (best effort)
    existing_folder_hint = ""
    existing_folder_score = 0.0
    if not (w.get("existing_folder") or "").strip():
        match_path, match_score = suggest_existing_folder(
            BASE_PATH, w["tenant"], w.get("kdnr", ""), w.get("name", "")
        )
        if match_path:
            w["existing_folder"] = match_path
            existing_folder_hint = match_path
            existing_folder_score = match_score

    msg = ""
    if request.method == "POST":
        if request.form.get("reextract") == "1":
            src = _resolve_doc_path(token, p)
            if src and src.exists():
                try:
                    delete_pending(token)
                except Exception:
                    pass
                new_token = analyze_to_pending(src)
                return redirect(url_for("web.review", token=new_token))
            msg = "Quelle nicht gefunden – Re-Extract nicht möglich."

        if request.form.get("confirm") == "1":
            tenant = _norm_tenant(current_tenant() or w.get("tenant") or "default")
            terr = None
            if terr:
                msg = f"Mandant-Fehler: {terr}"
            else:
                w["tenant"] = tenant
                w["kdnr"] = normalize_component(request.form.get("kdnr") or "")
                w["doctype"] = (
                    request.form.get("doctype") or w.get("doctype") or "SONSTIGES"
                ).upper()
                w["document_date"] = normalize_component(
                    request.form.get("document_date") or ""
                )
                w["name"] = normalize_component(request.form.get("name") or "")
                w["addr"] = normalize_component(request.form.get("addr") or "")
                w["plzort"] = normalize_component(request.form.get("plzort") or "")
                w["use_existing"] = normalize_component(
                    request.form.get("use_existing") or ""
                )

                if not w["kdnr"]:
                    msg = "KDNR fehlt."
                else:
                    src = Path(p.get("path", ""))
                    if not src.exists():
                        msg = "Datei im Eingang nicht gefunden."
                    else:
                        answers = {
                            "tenant": w["tenant"],
                            "kdnr": w["kdnr"],
                            "use_existing": w.get("use_existing", ""),
                            "name": w.get("name") or "Kunde",
                            "addr": w.get("addr") or "Adresse",
                            "plzort": w.get("plzort") or "PLZ Ort",
                            "doctype": w.get("doctype") or "SONSTIGES",
                            "document_date": w.get("document_date") or "",
                        }
                        try:
                            folder, final_path, created_new = process_with_answers(
                                Path(p.get("path", "")), answers
                            )
                            write_done(
                                token, {"final_path": str(final_path), **answers}
                            )
                            try:
                                pk_like = int(
                                    hashlib.sha256(token.encode("utf-8")).hexdigest()[
                                        :12
                                    ],
                                    16,
                                )
                                fact_text = (
                                    normalize_component(p.get("extracted_text") or "")
                                    or f"{answers['doctype']} {Path(str(final_path)).name} KDNR {answers['kdnr']}"
                                )
                                upsert_external_fact(
                                    "doc",
                                    pk_like,
                                    fact_text[:6000],
                                    {
                                        "path": str(final_path),
                                        "doctype": answers["doctype"],
                                        "kdnr": answers["kdnr"],
                                        "token": token,
                                    },
                                )
                                store_entity(
                                    "document",
                                    pk_like,
                                    fact_text[:6000],
                                    {
                                        "tenant_id": current_tenant(),
                                        "path": str(final_path),
                                        "doctype": answers["doctype"],
                                        "kdnr": answers["kdnr"],
                                        "project_id": answers.get("kdnr", ""),
                                    },
                                )
                            except Exception:
                                pass
                            delete_pending(token)
                            return redirect(url_for("web.done_view", token=token))
                        except Exception as e:
                            msg = f"Ablage fehlgeschlagen: {e}"

    _wizard_save(token, p, w)

    filename = p.get("filename", "")
    ext = Path(filename).suffix.lower()
    is_pdf = ext == ".pdf"
    is_text = ext == ".txt"

    right = render_template_string(
        HTML_WIZARD,
        w=w,
        doctypes=DOCTYPE_CHOICES,
        suggested_doctype=suggested_doctype,
        suggested_date=suggested_date,
        extracted_text=p.get("extracted_text", ""),
        msg=msg,
        existing_folder_hint=existing_folder_hint,
        existing_folder_score=(
            f"{existing_folder_score:.2f}" if existing_folder_hint else ""
        ),
    )
    return _render_base(
        render_template_string(
            HTML_REVIEW_SPLIT,
            token=token,
            filename=filename,
            is_pdf=is_pdf,
            is_text=is_text,
            preview=p.get("preview", ""),
            right=right,
            w=w,
            suggested_doctype=suggested_doctype,
            suggested_date=suggested_date,
            confidence=confidence,
        ),
        active_tab="upload",
    )


@bp.route("/done/<token>")
def done_view(token: str):
    d = read_done(token) or {}
    fp = d.get("final_path", "")
    html = f"""<div class='rounded-2xl bg-slate-900/60 border border-slate-800 p-6 card'>
      <div class='text-2xl font-bold mb-2'>Fertig</div>
      <div class='muted text-sm mb-4'>Datei wurde abgelegt.</div>
      <div class='muted text-xs'>Pfad</div>
      <div class='text-sm break-all accentText'>{fp}</div>
      <div class='mt-4'><a class='rounded-xl px-4 py-2 font-semibold btn-primary' href='/'>Zur Übersicht</a></div>
    </div>"""
    return _render_base(html, active_tab="upload")


@bp.route("/assistant")
def assistant():
    # Ensure core searches within current tenant
    try:
        import kukanilea_core_v3_fixed as _core

        _core.TENANT_DEFAULT = current_tenant() or _core.TENANT_DEFAULT
    except Exception:
        pass
    q = normalize_component(request.args.get("q", "") or "")
    kdnr = normalize_component(request.args.get("kdnr", "") or "")
    results = []
    if q and assistant_search is not None:
        try:
            raw = assistant_search(
                query=q,
                kdnr=kdnr,
                limit=50,
                role=current_role(),
                tenant_id=current_tenant(),
            )
            for r in raw or []:
                fp = r.get("file_path") or ""
                if ASSISTANT_HIDE_EINGANG and fp:
                    try:
                        if str(Path(fp).resolve()).startswith(
                            str(EINGANG.resolve()) + os.sep
                        ):
                            continue
                    except Exception:
                        pass
                r["fp_b64"] = _b64(fp) if fp else ""
                results.append(r)
        except Exception:
            pass
    html = """<div class='rounded-2xl bg-slate-900/60 border border-slate-800 p-5 card'>
      <div class='text-lg font-semibold mb-1'>Assistant</div>
      <form method='get' class='flex flex-col md:flex-row gap-2 mb-4'>
        <input class='w-full rounded-xl bg-slate-800 border border-slate-700 p-2 input' name='q' value='{q}' placeholder='Suche…' />
        <input class='w-full md:w-40 rounded-xl bg-slate-800 border border-slate-700 p-2 input' name='kdnr' value='{kdnr}' placeholder='Kdnr optional' />
        <button class='rounded-xl px-4 py-2 font-semibold btn-primary md:w-40' type='submit'>Suchen</button>
      </form>
      <div class='muted text-xs'>Treffer: {n}</div>
    </div>""".format(
        q=q.replace("'", "&#39;"), kdnr=kdnr.replace("'", "&#39;"), n=len(results)
    )
    return _render_base(html, active_tab="assistant")


@bp.route("/tasks")
@login_required
def tasks():
    available = (
        callable(task_list)
        and callable(task_create_fn)
        and callable(task_set_status_fn)
    )
    if not available:
        html = """<div class='rounded-2xl bg-slate-900/60 border border-slate-800 p-5 card'>
          <div class='text-lg font-semibold'>Tasks</div>
          <div class='muted text-sm mt-2'>Tasks/Kanban sind im Core nicht verfügbar.</div>
        </div>"""
        return _render_base(html, active_tab="tasks")
    board = _task_board_items(current_tenant())
    read_only = bool(current_app.config.get("READ_ONLY", False))

    def _render_card(item: dict, current_column: str) -> str:
        tid = int(item.get("id") or 0)
        title = normalize_component(item.get("title") or "")
        sev = normalize_component(item.get("severity") or "")
        ttype = normalize_component(item.get("task_type") or "")
        move_targets = [
            ("todo", "Todo"),
            ("in_progress", "In Progress"),
            ("done", "Done"),
        ]
        controls = []
        for target_key, target_label in move_targets:
            if target_key == current_column:
                continue
            disabled = "disabled" if read_only else ""
            controls.append(
                "<form method='post' action='/tasks/{tid}/move' class='inline'>"
                "<input type='hidden' name='column' value='{target}'>"
                "<button type='submit' {disabled} class='rounded-lg px-2 py-1 text-xs btn-outline'>{label}</button>"
                "</form>".format(
                    tid=tid,
                    target=target_key,
                    label=target_label,
                    disabled=disabled,
                )
            )
        controls_html = "".join(controls) or (
            "<span class='muted text-xs'>Kein Wechsel</span>"
        )
        return (
            f"<div class='rounded-xl border border-slate-800 p-3 space-y-2'>"
            f"<a class='block text-sm font-semibold hover:underline' href='/tasks/{tid}'>#{tid} {title}</a>"
            f"<div class='muted text-xs'>Severity: {sev} · {ttype}</div>"
            f"<div class='flex flex-wrap gap-1'>{controls_html}</div>"
            f"</div>"
        )

    todo_cards = "".join(_render_card(t, "todo") for t in board["todo"])
    progress_cards = "".join(
        _render_card(t, "in_progress") for t in board["in_progress"]
    )
    done_cards = "".join(_render_card(t, "done") for t in board["done"])
    create_disabled = "disabled" if read_only else ""

    html = f"""
    <div class='rounded-2xl bg-slate-900/60 border border-slate-800 p-5 card space-y-4'>
      <div class='flex items-center justify-between'>
        <div>
          <div class='text-lg font-semibold'>Tasks Kanban</div>
          <div class='muted text-xs mt-1'>Todo: {len(board["todo"])} · In Progress: {len(board["in_progress"])} · Done: {len(board["done"])}</div>
        </div>
        <a class='rounded-xl px-3 py-2 font-semibold btn-outline text-sm' href='/api/tasks?status=ALL'>API Preview</a>
      </div>
      <form method='post' action='/tasks/create' class='grid md:grid-cols-5 gap-2'>
        <input name='title' class='rounded-xl border p-2 input md:col-span-2' placeholder='Task Titel' required>
        <input name='task_type' class='rounded-xl border p-2 input' placeholder='Type (GENERAL)'>
        <input name='severity' class='rounded-xl border p-2 input' placeholder='Severity (INFO)'>
        <button type='submit' {create_disabled} class='rounded-xl px-4 py-2 font-semibold btn-primary'>Task anlegen</button>
        <textarea name='details' class='rounded-xl border p-2 input md:col-span-5' rows='2' placeholder='Details (optional)'></textarea>
      </form>
      <div class='grid md:grid-cols-3 gap-3'>
        <div class='rounded-xl border border-slate-800 p-3 space-y-2'>
          <div class='text-sm font-semibold'>Todo</div>
          {todo_cards or "<div class='muted text-sm'>Keine Tasks.</div>"}
        </div>
        <div class='rounded-xl border border-slate-800 p-3 space-y-2'>
          <div class='text-sm font-semibold'>In Progress</div>
          {progress_cards or "<div class='muted text-sm'>Keine Tasks.</div>"}
        </div>
        <div class='rounded-xl border border-slate-800 p-3 space-y-2'>
          <div class='text-sm font-semibold'>Done</div>
          {done_cards or "<div class='muted text-sm'>Keine Tasks.</div>"}
        </div>
      </div>
      <div class='muted text-xs'>READ_ONLY: {"aktiv" if read_only else "aus"}</div>
    </div>
    """
    return _render_base(html, active_tab="tasks")


@bp.route("/tasks/create", methods=["POST"])
@login_required
@require_role("OPERATOR")
def tasks_create():
    if not callable(task_create_fn):
        return _render_base(
            _card("error", "Tasks sind nicht verfügbar."), active_tab="tasks"
        )
    guarded = _task_mutation_guard(api=False)
    if guarded:
        return guarded
    title = normalize_component(request.form.get("title") or "")
    if not title:
        flash("Task Titel fehlt.", "error")
        return redirect("/tasks")
    severity = (
        normalize_component(request.form.get("severity") or "INFO").upper() or "INFO"
    )
    task_type = (
        normalize_component(request.form.get("task_type") or "GENERAL").upper()
        or "GENERAL"
    )
    details = str(request.form.get("details") or "").strip()
    task_id = task_create_fn(  # type: ignore
        tenant=current_tenant(),
        severity=severity,
        task_type=task_type,
        title=title,
        details=details,
        created_by=current_user() or "",
    )
    _audit(
        "task_create",
        target=str(task_id),
        meta={"tenant_id": current_tenant(), "status": "OPEN", "source": "kanban_ui"},
    )
    try:
        event_append(
            event_type="task_created",
            entity_type="task",
            entity_id=int(task_id),
            payload={
                "tenant_id": current_tenant(),
                "task_status": "OPEN",
                "source": "kanban_ui",
            },
        )
    except Exception:
        pass
    flash(f"Task #{int(task_id)} angelegt.", "success")
    return redirect("/tasks")


@bp.route("/tasks/<int:task_id>/move", methods=["POST"])
@login_required
@require_role("OPERATOR")
def tasks_move(task_id: int):
    if not callable(task_set_status_fn):
        return _render_base(
            _card("error", "Tasks sind nicht verfügbar."), active_tab="tasks"
        )
    guarded = _task_mutation_guard(api=False)
    if guarded:
        return guarded
    target = request.form.get("column") or request.form.get("status") or ""
    status = _task_status_from_input(target or "")
    if not status:
        flash("Ungültiger Status.", "error")
        return redirect("/tasks")
    changed = task_set_status_fn(  # type: ignore
        int(task_id),
        status,
        resolved_by=current_user() or "",
        tenant=current_tenant(),
    )
    if not changed:
        flash("Task nicht gefunden.", "error")
        return redirect("/tasks")
    _audit(
        "task_move",
        target=str(task_id),
        meta={"tenant_id": current_tenant(), "status": status, "source": "kanban_ui"},
    )
    try:
        event_append(
            event_type="task_moved",
            entity_type="task",
            entity_id=int(task_id),
            payload={
                "tenant_id": current_tenant(),
                "task_status": status,
                "source": "kanban_ui",
            },
        )
    except Exception:
        pass
    flash(f"Task #{int(task_id)} -> {status}", "success")
    return redirect("/tasks")


@bp.route("/tasks/<int:task_id>")
@login_required
def task_detail(task_id: int):
    if not callable(task_list):
        return _render_base(
            _card("error", "Tasks sind nicht verfügbar."), active_tab="tasks"
        )
    task = _task_find(current_tenant(), int(task_id))
    if not task:
        return _render_base(_card("error", "Task nicht gefunden."), active_tab="tasks")
    read_only = bool(current_app.config.get("READ_ONLY", False))
    status = normalize_component(task.get("status") or "OPEN").upper()

    html = render_template_string(
        """
<div class='rounded-2xl bg-slate-900/60 border border-slate-800 p-5 card'>
  <div class='text-lg font-semibold'>Task #{{task.id}} · {{task.title}}</div>
  <div class='muted text-xs mt-1'>{{task.severity}} · {{task.task_type}} · Status: {{status}}</div>
  <div class='text-sm mt-3 whitespace-pre-wrap'>{{task.details}}</div>
  <div class='mt-3 flex flex-wrap gap-2'>
    {% for key,label in move_targets %}
      {% if key != current_column %}
      <form method='post' action='/tasks/{{task.id}}/move' class='inline'>
        <input type='hidden' name='column' value='{{key}}'>
        <button type='submit' class='rounded-xl px-3 py-1 text-xs btn-outline' {% if read_only %}disabled{% endif %}>{{label}}</button>
      </form>
      {% endif %}
    {% endfor %}
  </div>
  <div class='mt-4 grid md:grid-cols-2 gap-3'>
    <div>
      <label class='muted text-xs'>Projekt-ID (optional)</label>
      <input id='taskProjectId' class='w-full rounded-xl border p-2 input' placeholder='z.B. 1'>
    </div>
    <div>
      <label class='muted text-xs'>Notiz</label>
      <input id='taskTimeNote' class='w-full rounded-xl border p-2 input' placeholder='Arbeitszeit erfassen'>
    </div>
  </div>
  <div class='mt-3 flex gap-2'>
    <button id='taskTimerStart' class='rounded-xl px-4 py-2 font-semibold btn-primary'>Timer starten</button>
    <button id='taskTimerStop' class='rounded-xl px-4 py-2 font-semibold btn-outline'>Timer stoppen</button>
    <a class='rounded-xl px-4 py-2 font-semibold btn-outline' href='/tasks'>Zurück</a>
  </div>
  <div id='taskTimerMsg' class='muted text-xs mt-2'>Bereit.</div>
  <div class='mt-4 rounded-xl border border-slate-800 p-3'>
    <div class='text-sm font-semibold'>Gebuchte Zeit</div>
    <div id='taskBooked' class='muted text-sm mt-1'>Lade…</div>
  </div>
  <div class='mt-4 rounded-xl border border-slate-800 p-3'>
    <div class='text-sm font-semibold mb-2'>Verknüpfungen</div>
    <div id='taskEntityLinks' hx-get='/entity-links/task/{{task.id}}' hx-trigger='load' hx-swap='innerHTML'></div>
  </div>
</div>
<script>
(function(){
  const taskId = {{task.id}};
  const msg = document.getElementById('taskTimerMsg');
  const booked = document.getElementById('taskBooked');
  const projectId = document.getElementById('taskProjectId');
  const note = document.getElementById('taskTimeNote');
  const toast = (lvl, txt) => { if(window.showToast){ window.showToast(lvl, txt); } };

  function setMsg(t, err){
    msg.textContent = t;
    msg.style.color = err ? '#f87171' : '';
  }

  async function refresh(){
    const r = await fetch(`/api/time/task/${taskId}`, {credentials:'same-origin'});
    const j = await r.json();
    if(!r.ok){ booked.textContent = j.error?.message || 'Nicht verfügbar'; return; }
    const s = j.summary || {};
    booked.textContent = `${s.total_hours || 0}h (${s.total_seconds || 0}s) in ${s.total_entries || 0} Einträgen`;
  }

  async function start(){
    setMsg('Starte Timer…', false);
    const body = {
      task_id: taskId,
      project_id: projectId.value || null,
      note: note.value || ''
    };
    const r = await fetch('/api/time/start', {
      method:'POST',
      headers:{'Content-Type':'application/json'},
      credentials:'same-origin',
      body: JSON.stringify(body)
    });
    const j = await r.json();
    if(!r.ok){
      const m = j.error?.message || 'Start fehlgeschlagen';
      setMsg(m, true);
      toast('error', m);
      return;
    }
    setMsg('Timer läuft.', false);
    toast('success', 'Timer gestartet');
    refresh();
  }

  async function stop(){
    setMsg('Stoppe Timer…', false);
    const r = await fetch('/api/time/stop', {
      method:'POST',
      headers:{'Content-Type':'application/json'},
      credentials:'same-origin',
      body: JSON.stringify({})
    });
    const j = await r.json();
    if(!r.ok){
      const m = j.error?.message || 'Stop fehlgeschlagen';
      setMsg(m, true);
      toast('error', m);
      return;
    }
    setMsg('Timer gestoppt.', false);
    toast('success', 'Timer gestoppt');
    refresh();
  }

  document.getElementById('taskTimerStart').addEventListener('click', start);
  document.getElementById('taskTimerStop').addEventListener('click', stop);
  refresh();
})();
</script>
        """,
        task=task,
        status=status,
        read_only=read_only,
        current_column=(
            "todo"
            if status == "OPEN"
            else "in_progress"
            if status == "IN_PROGRESS"
            else "done"
        ),
        move_targets=[
            ("todo", "Todo"),
            ("in_progress", "In Progress"),
            ("done", "Done"),
        ],
    )
    return _render_base(html, active_tab="tasks")


@bp.route("/time")
@login_required
def time_tracking():
    if not callable(time_entry_list):
        html = """<div class='rounded-2xl bg-slate-900/60 border border-slate-800 p-5 card'>
          <div class='text-lg font-semibold'>Time Tracking</div>
          <div class='muted text-sm mt-2'>Time Tracking ist im Core nicht verfügbar.</div>
        </div>"""
        return _render_base(html, active_tab="time")
    return _render_base(
        render_template_string(HTML_TIME, role=current_role()), active_tab="time"
    )


@bp.route("/chat")
def chat():
    return _render_base(HTML_CHAT, active_tab="chat")


@bp.route("/health")
def health():
    return jsonify(ok=True, ts=time.time(), app="kukanilea_upload_v3_ui")
