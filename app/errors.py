"""
Zentrales Error-Handling für KUKANILEA Gold.
Maxime: Fail-Safe, Not Fail-Fast. Absolute Error-Boundary mit Request-IDs.
"""
import logging
import traceback
import uuid
import hashlib
import json
from datetime import datetime, timezone
from functools import wraps
from flask import jsonify, render_template_string, request, g

logger = logging.getLogger("kukanilea.errors")

class KukaniMeaError(Exception):
    """Base-Exception für alle kontrollierten KUKANILEA-Fehler."""
    def __init__(self, message: str, error_code: str, details: dict = None):
        super().__init__(message)
        self.message = message
        self.error_code = error_code
        self.details = details or {}
        # Gold Hardening: Eindeutige Request-ID pro Exception
        self.request_id = str(uuid.uuid4())
        self.timestamp = datetime.now(timezone.utc).isoformat()

class ValidationError(KukaniMeaError):
    def __init__(self, message: str, field: str = None):
        super().__init__(message, 'validation_error', {'field': field})

class PermissionDeniedError(KukaniMeaError):
    def __init__(self, message: str = "Zugriff verweigert."):
        super().__init__(message, 'forbidden')

class ResourceNotFoundError(KukaniMeaError):
    def __init__(self, resource_type: str, resource_id: str):
        super().__init__(f"{resource_type} nicht gefunden.", 'not_found', {'id': resource_id})

class SystemError(KukaniMeaError):
    def __init__(self, message: str, original_exception: Exception = None):
        super().__init__(message, 'system_error', {'exception': str(original_exception)})

def safe_execute(func):
    """
    Decorator: Fängt alle rohen Exceptions und wandelt sie in einen SystemError um.
    Generiert anonymisierten Error-Fingerprint via SHA-256.
    """
    @wraps(func)
    def wrapper(*args, **kwargs):
        try:
            return func(*args, **kwargs)
        except KukaniMeaError:
            raise
        except Exception as e:
            # Gold Hardening: Anonymisierter Fingerprint für Sentry/Logs
            error_details = f"{type(e).__name__}: {str(e)} | {traceback.format_exc()}"
            fingerprint = hashlib.sha256(error_details.encode('utf-8')).hexdigest()
            
            logger.critical(f"UNHANDLED EXCEPTION [{fingerprint[:12]}]: {e}")
            logger.debug(traceback.format_exc())
            
            raise SystemError(
                message=f"Ein interner Fehler ist aufgetreten: {str(e)} (ID: {fingerprint[:8]}).",
                original_exception=e
            )
    return wrapper

def fail_safe(func):
    """
    Agent-Level Decorator: Fällt in einen sicheren Zustand (Read-Only) zurück,
    anstatt den gesamten Agenten-Prozess zu terminieren.
    """
    @wraps(func)
    async def wrapper(*args, **kwargs):
        try:
            return await func(*args, **kwargs)
        except Exception as e:
            logger.error(f"Agent-Level Failure in {func.__name__}: {e}. Falling back to safe-state.")
            return "AGENT_SAFE_STATE: Die Aktion konnte aufgrund eines Systemfehlers nicht ausgeführt werden. (Read-Only Fallback)"
    return wrapper

def handle_error(error: Exception):
    """Zentraler Flask Error Handler mit Content-Negotiation."""
    from werkzeug.exceptions import HTTPException
    
    if isinstance(error, KukaniMeaError):
        rid = error.request_id
        code = error.error_code
        msg = error.message
        status = _get_status_code(error)
    elif isinstance(error, HTTPException):
        rid = str(uuid.uuid4())
        code = 'forbidden' if error.code == 403 else ('validation_error' if error.code == 400 else 'http_error')
        msg = str(error.description or error.name)
        status = error.code or 500
    else:
        rid = str(uuid.uuid4())
        code = 'unknown_error'
        msg = "Unerwarteter Systemfehler."
        status = 500

    # Content-Negotiation
    if request.path.startswith('/api/') or request.accept_mimetypes.best == 'application/json':
        return jsonify({
            'error': {'code': code, 'message': msg, 'request_id': rid, 'timestamp': datetime.now(timezone.utc).isoformat()}
        }), status
    else:
        try:
            from . import web
            content = render_template_string(HTML_ERROR_INNER, error_code=code, message=msg, request_id=rid, status=status)
            return web._render_base(content, active_tab="upload"), status
        except Exception:
            return render_template_string(HTML_ERROR_PAGE, error_code=code, message=msg, request_id=rid), status

def _get_status_code(error: Exception) -> int:
    if isinstance(error, ValidationError): return 400
    if isinstance(error, PermissionDeniedError): return 403
    if isinstance(error, ResourceNotFoundError): return 404
    return 500

def json_error(code: str, message: str, status: int = 400, details: dict = None):
    """Hilfsfunktion für standardisierte JSON-Fehlermeldungen."""
    return jsonify({
        'error': {
            'code': code,
            'message': message,
            'details': details or {},
            'request_id': str(uuid.uuid4()),
            'timestamp': datetime.now(timezone.utc).isoformat()
        }
    }), status

HTML_ERROR_INNER = """
<div class="max-w-3xl mx-auto" data-app-shell="1">
  <div class="card p-8 rounded-2xl border bg-white shadow-sm" style="border-left: 4px solid #ef4444;">
    <h1 class="text-2xl font-bold mb-4" style="color: #991b1b;">⚠️ Vorgang unterbrochen ({{ status }})</h1>
    <p class="text-lg mb-6"><strong>{{ message }}</strong></p>
    <div class="bg-gray-50 p-4 rounded-lg text-sm text-gray-600 mb-8 border">
        <p>Fehlercode: <code>{{ error_code }}</code></p>
        <p>Request-ID: <code>{{ request_id }}</code></p>
    </div>
    <div class="flex gap-3">
        <a href="/" class="btn btn-primary px-6 py-2">Dashboard</a>
        <button onclick="window.history.back()" class="btn btn-outline px-6 py-2">Zurueck</button>
        {% if status >= 500 %}
        <a href="/support/diagnostic" class="btn btn-danger px-6 py-2">Diagnose-Paket erstellen</a>
        {% endif %}
    </div>
  </div>
</div>
"""

HTML_ERROR_PAGE = """
<!DOCTYPE html>
<html lang="de">
<body data-app-shell="1">
    <div style="max-width:600px; margin:80px auto; font-family:sans-serif;">
        <h1>⚠️ Fehler {{ status }}</h1>
        <p>{{ message }}</p>
        <small>ID: {{ request_id }}</small>
    </div>
</body>
</html>
"""
