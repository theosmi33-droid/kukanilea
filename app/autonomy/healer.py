from __future__ import annotations

import logging
from flask import Flask, g, request, jsonify, render_template_string

logger = logging.getLogger("kukanilea.healer")

# Global State for Degraded Mode
DEGRADED_MODE = False

ERROR_SHELL_HTML = """
<!DOCTYPE html>
<html>
<head>
    <title>KUKANILEA - System Maintenance</title>
    <style>
        body { font-family: sans-serif; padding: 2rem; line-height: 1.5; background: #f8f9fa; }
        .container { max-width: 600px; margin: 0 auto; background: white; padding: 2rem; border-radius: 8px; box-shadow: 0 2px 4px rgba(0,0,0,0.1); border-top: 4px solid #dc3545; }
        h1 { color: #dc3545; }
        .rid { color: #6c757d; font-size: 0.8rem; margin-top: 2rem; }
    </style>
</head>
<body>
    <div class="container">
        <h1>Degraded Mode</h1>
        <p>The system is currently in a <strong>Read-Only Degraded Mode</strong> due to database integrity issues.</p>
        <p>Mutating operations (saving, deleting, updating) are disabled to prevent further data loss.</p>
        <p>Please contact technical support if this persists.</p>
        <div class="rid">Request-ID: {{ rid }}</div>
    </div>
</body>
</html>
"""

def init_healer(app: Flask):
    @app.before_request
    def enforce_degraded_mode():
        if not DEGRADED_MODE:
            return None
            
        if request.method.upper() in {"POST", "PUT", "PATCH", "DELETE"}:
            rid = getattr(g, "rid", "unknown")
            
            # Content Negotiation
            accept = request.headers.get("Accept", "")
            if "text/html" in accept:
                return render_template_string(ERROR_SHELL_HTML, rid=rid), 503
            else:
                return jsonify({
                    "error": "degraded_mode",
                    "message": "System is in Degraded Read-Only Mode due to integrity issues.",
                    "request_id": rid
                }), 503
        return None

def set_degraded_mode(active: bool):
    global DEGRADED_MODE
    DEGRADED_MODE = active
    if active:
        logger.critical("Entering Degraded Mode!")
    else:
        logger.info("Exiting Degraded Mode.")
