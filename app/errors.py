from __future__ import annotations

from typing import Any, Dict

from flask import g, jsonify, render_template_string, request


def _active_tab_from_path(path: str) -> str:
    token = str(path or "").strip().lower()
    if token.startswith("/tasks"):
        return "tasks"
    if token.startswith("/time"):
        return "time"
    if token.startswith("/assistant"):
        return "assistant"
    if token.startswith("/chat"):
        return "chat"
    if token.startswith("/postfach") or token.startswith("/mail"):
        return "postfach"
    if token.startswith("/crm"):
        return "crm"
    if token.startswith("/leads"):
        return "leads"
    if token.startswith("/knowledge"):
        return "knowledge"
    if token.startswith("/conversations"):
        return "conversations"
    if token.startswith("/workflows"):
        return "workflows"
    if token.startswith("/automation"):
        return "automation"
    if token.startswith("/autonomy"):
        return "autonomy"
    if token.startswith("/insights"):
        return "insights"
    if token.startswith("/license"):
        return "license"
    if token.startswith("/settings") or token.startswith("/dev/"):
        return "settings"
    return "upload"


def wants_json_error() -> bool:
    path = str(request.path or "")
    if path.startswith("/api/"):
        return True

    # Browser navigations should prefer shell-based HTML errors.
    if str(request.headers.get("Sec-Fetch-Mode") or "").lower() == "navigate":
        return False

    accept = request.accept_mimetypes
    json_quality = float(accept["application/json"])
    html_quality = float(accept["text/html"])
    if json_quality > 0 and json_quality > html_quality:
        return True

    # XHR callers commonly expect JSON when HTML is not explicitly requested.
    xrw = str(request.headers.get("X-Requested-With") or "").lower()
    raw_accept = str(request.headers.get("Accept") or "").lower()
    if (
        xrw == "xmlhttprequest"
        and "text/html" not in raw_accept
        and ("application/json" in raw_accept or "*/*" in raw_accept)
    ):
        return True

    return False


def _html_error_response(code: str, message: str, *, status: int):
    request_id = str(getattr(g, "request_id", "unknown"))
    content = render_template_string(
        """
<div class="max-w-3xl mx-auto">
  <div class="card p-6 rounded-2xl border">
    <div class="text-xs muted mb-2">Fehler {{ status }}</div>
    <h1 class="text-2xl font-semibold mb-2">{{ title }}</h1>
    <p class="text-sm muted mb-4">{{ message }}</p>
    <div class="text-xs muted mb-4">Request-ID: <code>{{ request_id }}</code></div>
    <div class="flex flex-wrap gap-2">
      <button type="button" class="btn btn-outline px-3 py-2 text-sm" onclick="window.location.reload()">Neu laden</button>
      <button type="button" class="btn btn-outline px-3 py-2 text-sm" onclick="window.history.back()">Zurueck</button>
      <a class="btn btn-primary px-3 py-2 text-sm" href="/">Dashboard</a>
    </div>
  </div>
</div>
        """,
        status=int(status),
        title=str(code or "Fehler"),
        message=str(message or "Die Aktion konnte nicht abgeschlossen werden."),
        request_id=request_id,
    )
    from . import web

    active_tab = _active_tab_from_path(request.path or "/")
    return web._render_base(content, active_tab=active_tab), int(status)


def error_envelope(
    code: str, message: str, *, details: Dict[str, Any] | None = None
) -> Dict[str, Any]:
    payload: Dict[str, Any] = {
        "ok": False,
        "error": {
            "code": code,
            "message": message,
            "details": details or {},
        },
    }
    request_id = getattr(g, "request_id", None)
    if request_id:
        payload["error"]["request_id"] = request_id
        payload["error"]["details"].setdefault("request_id", request_id)
    return payload


def error_payload(
    code: str, message: str, *, details: Dict[str, Any] | None = None
) -> Dict[str, Any]:
    return error_envelope(code, message, details=details)["error"]


def json_error(
    code: str, message: str, *, status: int = 400, details: Dict[str, Any] | None = None
):
    if not wants_json_error():
        return _html_error_response(code, message, status=status)
    return jsonify(error_envelope(code, message, details=details)), status
