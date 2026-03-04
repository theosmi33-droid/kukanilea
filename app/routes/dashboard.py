from flask import Blueprint, render_template, current_app, json, request
from ..auth import login_required, current_tenant
from app import core

bp = Blueprint("dashboard", __name__)

def _core_get(name: str, default=None):
    return getattr(core, name, default)

def _norm_tenant(t: str) -> str:
    return (t or "default").lower().replace(" ", "_")

@bp.get("/dashboard")
@login_required
def dashboard_page():
    try:
        # Helper to check for HX request (simplified for scaffold)
        is_hx = request.headers.get("HX-Request") == "true"
        
        if is_hx:
            # Import local to avoid circular or early import issues
            from ..web import _render_sovereign_tool
            return _render_sovereign_tool(
                "dashboard",
                "Dashboard",
                "Dashboard-Widgets werden geladen...",
                active_tab="dashboard",
            )
            
        # Get items for dashboard.html
        auth_db = current_app.extensions["auth_db"]
        from app import core
        PENDING_DIR = getattr(core, "PENDING_DIR", None)
        
        tenant = _norm_tenant(current_tenant() or "default")
        
        items = []
        if PENDING_DIR and (PENDING_DIR / tenant).exists():
            items = [f.name for f in (PENDING_DIR / tenant).iterdir() if f.is_dir()]
        
        meta = {}
        for token in items:
            m_path = PENDING_DIR / tenant / token / "meta.json"
            if m_path.exists():
                with open(m_path, "r") as f:
                    meta[token] = json.load(f)
            else:
                meta[token] = {"filename": "Unbekannt", "status": "PENDING"}

        # Get recent from core
        recent = []
        get_recent_docs = _core_get("get_recent_docs")
        if callable(get_recent_docs):
            recent = get_recent_docs(tenant, limit=6)

        # Import local to avoid circular
        from ..web import _render_base
        return _render_base(
            "dashboard.html",
            active_tab="dashboard",
            items=items,
            meta=meta,
            recent=recent,
            suggestions={"doctypes": ["Rechnung", "Angebot", "Lieferschein"]},
            keywords=["Maler", "Sanitär", "Elektro"]
        )
    except Exception as e:
        current_app.logger.error(f"Dashboard Error: {e}", exc_info=True)
        return str(e), 500
