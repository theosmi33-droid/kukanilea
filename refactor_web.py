import re
from pathlib import Path

web_py_path = Path("/Users/gensuminguyen/Kukanilea/kukanilea_production/app/web.py")
content = web_py_path.read_text(encoding="utf-8")

# 1. Add render_template to imports if not there
if "from flask import" in content and "render_template," not in content and "render_template " not in content:
    content = content.replace("from flask import Blueprint,", "from flask import Blueprint, render_template,")

# 2. Remove the huge HTML constants. We can just use a regex to strip them out.
# HTML_LOGIN, HTML_BASE, HTML_INDEX, HTML_REVIEW_SPLIT, HTML_WIZARD
html_blocks = ["HTML_LOGIN", "HTML_BASE", "HTML_INDEX", "HTML_REVIEW_SPLIT", "HTML_WIZARD", "SVG_LOGO"]
for block in html_blocks:
    content = re.sub(rf'{block}\s*=\s*r?"""[\s\S]*?"""\n?', '', content)
    content = re.sub(rf"{block}\s*=\s*r?'''[\s\S]*?'''\n?", '', content)

# 3. Update the _render_base function
new_render_base = """def _render_base(template_name: str, **kwargs):
    kwargs.setdefault('branding', Config.get_branding())
    kwargs.setdefault('tenant', _norm_tenant(current_tenant() or "default"))
    kwargs.setdefault('roles', current_role())
    kwargs.setdefault('user', current_user() or "-")
    kwargs.setdefault('profile', _get_profile())
    kwargs.setdefault('ablage', str(BASE_PATH))
    return render_template(template_name, **kwargs)"""

content = re.sub(r'def _render_base\(content: str, active_tab: str = "upload"\):[\s\S]*?ablage=str\(BASE_PATH\)\n    \)', new_render_base, content)

# 4. Update the routes
content = content.replace('return render_template_string(HTML_LOGIN, error=error, branding=Config.get_branding())', 'return render_template("login.html", error=error, branding=Config.get_branding())')

content = content.replace('return _render_base(render_template_string(HTML_INDEX, items=items, meta=meta, recent=recent), active_tab="upload")', 'return _render_base("dashboard.html", active_tab="upload", items=items, meta=meta, recent=recent)')

# Review Route
review_html_old = """    right = render_template_string(HTML_WIZARD, w=w, doctypes=DOCTYPE_CHOICES, suggested_doctype="SONSTIGES", suggested_date="", confidence=50, msg=msg)
    return _render_base(render_template_string(HTML_REVIEW_SPLIT, token=token, filename=p.get("filename",""), is_pdf=Path(p.get("filename","")).suffix.lower()==".pdf", preview=p.get("preview"), right=right, confidence=50), active_tab="upload")"""
review_html_new = """    return _render_base("review.html", active_tab="upload", token=token, filename=p.get("filename",""), is_pdf=Path(p.get("filename","")).suffix.lower()==".pdf", preview=p.get("preview"), w=w, doctypes=DOCTYPE_CHOICES, suggested_doctype=p.get("doctype_suggested", "SONSTIGES"), suggested_date=p.get("doc_date_suggested", ""), confidence=85, msg=msg, is_duplicate=p.get("is_duplicate", False), kdnr_ranked=p.get("kdnr_ranked", []), name_suggestions=p.get("name_suggestions", []))"""
content = content.replace(review_html_old, review_html_new)

# Review Loading state
review_loading_old = """    if p.get("status") == "ANALYZING":
        return _render_base(render_template_string(HTML_REVIEW_SPLIT, token=token, filename=p.get("filename",""), is_pdf=True, right=_card("info","KI Analyse läuft..."), confidence=0))"""
review_loading_new = """    if p.get("status") == "ANALYZING":
        return _render_base("review.html", active_tab="upload", token=token, filename=p.get("filename",""), is_pdf=True, preview=None, msg="KI Analyse läuft...", doctypes=[], kdnr_ranked=[], name_suggestions=[], confidence=0)"""
content = content.replace(review_loading_old, review_loading_new)

# Done view
done_old = """    html = f"<div class='card p-16 bg-white text-center max-w-xl mx-auto'><div class='h-24 w-24 rounded-full bg-emerald-50 text-emerald-500 flex items-center justify-center mx-auto mb-8 shadow-xl border border-emerald-100'><svg xmlns='http://www.w3.org/2000/svg' width='48' height='48' viewBox='0 0 24 24' fill='none' stroke='currentColor' stroke-width='3'><polyline points='20 6 9 17 4 12'/></svg></div><h1 class='text-3xl font-black mb-4'>Archiviert</h1><p class='muted mb-12 font-bold uppercase tracking-widest text-[10px]'>Dokument sicher im Ledger abgelegt</p><a class='btn-primary px-12 py-4' href='/'>Zur Übersicht</a></div>"
    return _render_base(html, active_tab="upload")"""
done_new = """    return _render_base("done.html", active_tab="upload")"""
content = content.replace(done_old, done_new)

# Generic tools mapping
tool_replacements = [
    ('return _render_base("<div class=\'card p-12 bg-white text-center\'><h1 class=\'text-xl font-black\'>Zeiterfassung</h1><p class=\'muted mt-4\'>Zeiterfassung bereit.</p></div>", active_tab="time")', 'return _render_base("generic_tool.html", active_tab="time", title="Zeiterfassung", message="Zeiterfassung bereit.")'),
    ('return _render_base("<div class=\'card p-12 bg-white text-center\'><h1 class=\'text-xl font-black\'>Assistent</h1><p class=\'muted mt-4\'>Wie kann ich Ihnen heute helfen?</p></div>", active_tab="assistant")', 'return _render_base("generic_tool.html", active_tab="assistant", title="KI-Assistent", message="Wie kann ich Ihnen heute helfen?")'),
    ('return _render_base("<div class=\'card p-12 bg-white text-center\'><h1 class=\'text-xl font-black\'>Mesh-Netzwerk</h1><p class=\'muted mt-4\'>ZimaBlade Cluster-Status: Online (3 Knoten)</p></div>", active_tab="mesh")', 'return _render_base("generic_tool.html", active_tab="mesh", title="Mesh-Netzwerk", message="ZimaBlade Cluster-Status: Online (3 Knoten)")')
]
for old, new in tool_replacements:
    content = content.replace(old, new)

# Chat and Mail placeholders
content = re.sub(r'return _render_base\(f"<div class=\'card.*?Chat.*?</div>", active_tab="chat"\)', 'return _render_base("generic_tool.html", active_tab="chat", title="Chat", message="Kommunikation wird geladen...")', content, flags=re.DOTALL)
content = re.sub(r'return _render_base\(f"<div class=\'card.*?Postfach.*?</div>", active_tab="mail"\)', 'return _render_base("generic_tool.html", active_tab="mail", title="Postfach", message="Postfach wird synchronisiert...")', content, flags=re.DOTALL)
content = re.sub(r'return _render_base\(f"<div class=\'card.*?Einstellungen.*?</div>", active_tab="settings"\)', 'return _render_base("generic_tool.html", active_tab="settings", title="Einstellungen", message="Systemkonfiguration laden...")', content, flags=re.DOTALL)
content = re.sub(r'return _render_base\(f"<div class=\'card.*?Aufgaben.*?</div>", active_tab="tasks"\)', 'return _render_base("generic_tool.html", active_tab="tasks", title="Aufgaben", message="Aufgabenliste wird geladen...")', content, flags=re.DOTALL)

# In the login route, we need to handle "error=error" without string formatting
# It's already handled above via exact replace.

web_py_path.write_text(content, encoding="utf-8")
print("Refactored web.py successfully.")
