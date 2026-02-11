#!/usr/bin/env python3
# KUKANILEA Systems – UI FIXED11a + Agent-Orchestrator (ARCH only, no Ollama)
#
# - Each tool is an Agent (Search/Open/Index/Summary/Weather/Mail).
# - Orchestrator routes messages to agents and returns structured actions.
# - No LLM calls. Routing is rule-based. This is the backbone.

from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass, field
from datetime import datetime
from functools import wraps
from pathlib import Path
from typing import Any, Dict, List, Tuple

from flask import (
    Flask,
    jsonify,
    redirect,
    render_template_string,
    request,
    session,
    url_for,
)

# =========================
# Flask app + auth (demo)
# =========================
app = Flask(__name__)
app.secret_key = os.environ.get("KUKANILEA_SECRET", "kukanilea-dev-secret")

APP_NAME = "KUKANILEA Systems"
DEV_TENANT = "KUKANILEA Dev"

# NOTE: demo users; replace with DB/users later.
USERS = {
    "dev": {"pw": "dev", "role": "DEVELOPER", "tenant": DEV_TENANT},
    "admin": {"pw": "admin", "role": "ADMIN", "tenant": DEV_TENANT},
    "user": {"pw": "user", "role": "USER", "tenant": DEV_TENANT},
}

# Paths (override via env)
BASE_PATH = Path(
    os.environ.get("KUKANILEA_BASE_PATH", str(Path.home() / "Tophandwerk_Kundenablage"))
).expanduser()
DB_INDEX_PATH = Path(
    os.environ.get(
        "KUKANILEA_INDEX_PATH", str(Path.home() / ".kukanilea" / "index.json")
    )
).expanduser()


def login_required(fn):
    @wraps(fn)
    def wrapper(*args, **kwargs):
        if not session.get("user"):
            return redirect(url_for("login", next=request.path))
        return fn(*args, **kwargs)

    return wrapper


def current_user() -> Dict[str, str]:
    return {
        "user": session.get("user", ""),
        "role": session.get("role", "USER"),
        "tenant": session.get("tenant", DEV_TENANT),
    }


# =========================
# Orchestrator core types
# =========================
@dataclass
class Permissions:
    can_view_sensitive: bool = False
    can_open_files: bool = False
    can_search: bool = True
    can_write_mail: bool = False

    @staticmethod
    def from_role(role: str) -> "Permissions":
        role = (role or "USER").upper()
        if role in ("DEVELOPER", "ADMIN"):
            return Permissions(
                can_view_sensitive=True,
                can_open_files=True,
                can_search=True,
                can_write_mail=True,
            )
        if role == "USER":
            return Permissions(
                can_view_sensitive=False,
                can_open_files=False,
                can_search=True,
                can_write_mail=False,
            )
        return Permissions()


@dataclass
class AgentContext:
    tenant: str
    user: str
    role: str
    permissions: Permissions
    base_path: Path = BASE_PATH
    index_path: Path = DB_INDEX_PATH


@dataclass
class ToolAction:
    # UI actions for frontend
    type: str
    payload: Dict[str, Any] = field(default_factory=dict)


@dataclass
class AgentResult:
    messages: List[str] = field(default_factory=list)
    actions: List[ToolAction] = field(default_factory=list)
    data: Dict[str, Any] = field(default_factory=dict)
    errors: List[str] = field(default_factory=list)


class BaseAgent:
    name: str = "base"
    description: str = ""

    def can_handle(self, text: str) -> bool:
        return False

    def handle(
        self, ctx: AgentContext, text: str, state: Dict[str, Any]
    ) -> AgentResult:
        return AgentResult(messages=[f"{self.name}: no-op"])


# =========================
# Simple local index (JSON)
# =========================
def _load_index(path: Path) -> Dict[str, Any]:
    if not path.exists():
        return {"docs": [], "updated_at": None}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {"docs": [], "updated_at": None}


def _save_index(path: Path, idx: Dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(idx, ensure_ascii=False, indent=2), encoding="utf-8")


def index_build(base_path: Path, index_path: Path) -> Dict[str, Any]:
    """
    Lightweight index scan (ARCH-only).
    Later: enrich with OCR/embeddings + tenant scoping.
    """
    docs: List[Dict[str, Any]] = []
    for p in base_path.rglob("*"):
        if p.is_file() and p.suffix.lower() in (
            ".pdf",
            ".png",
            ".jpg",
            ".jpeg",
            ".txt",
            ".docx",
        ):
            rel = str(p.relative_to(base_path))
            name = p.name
            tokens = sorted(set(re.findall(r"[A-Za-zÄÖÜäöüß]+|\d{2,}", name)))
            docs.append(
                {
                    "path": str(p),
                    "rel": rel,
                    "name": name,
                    "ext": p.suffix.lower(),
                    "tokens": [t.lower() for t in tokens],
                    "mtime": int(p.stat().st_mtime),
                }
            )
    idx = {"docs": docs, "updated_at": datetime.utcnow().isoformat() + "Z"}
    _save_index(index_path, idx)
    return idx


def index_search(
    idx: Dict[str, Any], query: str, limit: int = 10
) -> List[Dict[str, Any]]:
    q = (query or "").strip().lower()
    if not q:
        return []
    q_terms = [t.lower() for t in re.findall(r"[A-Za-zÄÖÜäöüß]+|\d{2,}", q)]
    scored: List[Tuple[int, Dict[str, Any]]] = []
    for d in idx.get("docs", []):
        tokens = set(d.get("tokens", []))
        score = sum(2 for t in q_terms if t in tokens)
        score += sum(1 for t in q_terms if t in d.get("name", "").lower())
        if score > 0:
            scored.append((score, d))
    scored.sort(key=lambda x: (-x[0], -x[1].get("mtime", 0)))
    return [d for _, d in scored[:limit]]


# =========================
# Agents
# =========================
class HelpAgent(BaseAgent):
    name = "help"
    description = "Shows tool commands."

    def can_handle(self, text: str) -> bool:
        return text.strip().lower() in ("help", "hilfe", "?")

    def handle(
        self, ctx: AgentContext, text: str, state: Dict[str, Any]
    ) -> AgentResult:
        return AgentResult(
            messages=[
                "Agent-Chat (ARCH, ohne LLM). Commands:",
                "• help",
                "• index neu",
                "• suche <keywords>",
                "• öffne <pfad>   (nur Admin/Dev)",
                "• zusammenfassen <text>",
                "• mail: <anlass> (nur Admin/Dev)",
                "• wetter berlin  (stub)",
            ]
        )


class IndexAgent(BaseAgent):
    name = "index"
    description = "Index status + rebuild."

    def can_handle(self, text: str) -> bool:
        return text.strip().lower().startswith("index")

    def handle(
        self, ctx: AgentContext, text: str, state: Dict[str, Any]
    ) -> AgentResult:
        t = text.strip().lower()
        if "neu" in t or "rebuild" in t or "build" in t:
            idx = index_build(ctx.base_path, ctx.index_path)
            return AgentResult(
                messages=[
                    f"Index aktualisiert: {len(idx.get('docs', []))} Dateien.",
                    f"Stand: {idx.get('updated_at')}",
                ],
                data={
                    "index_updated_at": idx.get("updated_at"),
                    "count": len(idx.get("docs", [])),
                },
            )
        idx = _load_index(ctx.index_path)
        return AgentResult(
            messages=[
                f"Index: {len(idx.get('docs', []))} Dateien.",
                f"Stand: {idx.get('updated_at') or 'unbekannt'}",
                f"Pfad: {ctx.index_path}",
            ]
        )


class SearchAgent(BaseAgent):
    name = "search"
    description = "Local index search."

    def can_handle(self, text: str) -> bool:
        t = text.strip().lower()
        return t.startswith("suche") or t.startswith("search")

    def handle(
        self, ctx: AgentContext, text: str, state: Dict[str, Any]
    ) -> AgentResult:
        if not ctx.permissions.can_search:
            return AgentResult(errors=["Keine Berechtigung zum Suchen."])

        idx = _load_index(ctx.index_path)
        if not idx.get("docs"):
            idx = index_build(ctx.base_path, ctx.index_path)

        q = re.sub(r"^(suche|search)\s*", "", text.strip(), flags=re.I).strip()
        hits = index_search(idx, q, limit=10)
        if not hits:
            return AgentResult(
                messages=[f"Keine Treffer für: {q!r}. Tipp: `index neu`"]
            )

        redacted = []
        for h in hits:
            item = dict(h)
            if not ctx.permissions.can_view_sensitive:
                item["path"] = None
                item["rel"] = item.get("name")
            redacted.append(item)

        lines = [f"Treffer ({len(hits)}):"]
        for i, h in enumerate(redacted, 1):
            show = h.get("rel") or h.get("name")
            lines.append(f"{i}. {show}")

        return AgentResult(
            messages=lines,
            actions=[ToolAction(type="search_results", payload={"results": redacted})],
            data={"results": redacted, "handled_by": self.name},
        )


class OpenFileAgent(BaseAgent):
    name = "open"
    description = "Open file (admin/dev)."

    def can_handle(self, text: str) -> bool:
        t = text.strip().lower()
        return t.startswith("öffne") or t.startswith("open")

    def handle(
        self, ctx: AgentContext, text: str, state: Dict[str, Any]
    ) -> AgentResult:
        if not ctx.permissions.can_open_files:
            return AgentResult(
                messages=[
                    "Keine Berechtigung zum Öffnen.",
                    "Nutze `suche ...` oder Admin/Dev.",
                ]
            )

        path = (
            re.sub(r"^(öffne|open)\s*", "", text.strip(), flags=re.I)
            .strip()
            .strip('"')
            .strip("'")
        )
        if not path:
            path = (state.get("last_selected_path") or "").strip()
        if not path:
            return AgentResult(errors=["Kein Pfad angegeben."])

        p = Path(path).expanduser()
        if not p.exists():
            p2 = (ctx.base_path / path).resolve()
            if p2.exists():
                p = p2
            else:
                return AgentResult(errors=[f"Datei nicht gefunden: {path}"])

        return AgentResult(
            messages=[f"Öffne: {p.name}"],
            actions=[ToolAction(type="open_file", payload={"path": str(p)})],
            data={"path": str(p), "handled_by": self.name},
        )


class SummaryAgent(BaseAgent):
    name = "summary"
    description = "Rule-based summarizer."

    def can_handle(self, text: str) -> bool:
        t = text.strip().lower()
        return t.startswith("zusammenfassen") or t.startswith("summary")

    def handle(
        self, ctx: AgentContext, text: str, state: Dict[str, Any]
    ) -> AgentResult:
        raw = re.sub(
            r"^(zusammenfassen|summary)\s*", "", text.strip(), flags=re.I
        ).strip()
        if not raw:
            raw = (state.get("last_text") or "").strip()
        if not raw:
            return AgentResult(errors=["Kein Text zum Zusammenfassen."])
        lines = [line.strip() for line in raw.splitlines() if line.strip()]
        head = lines[:6]
        bullets = [f"• {line[:140]}" for line in head]
        return AgentResult(
            messages=["Kurz-Zusammenfassung:"] + bullets, data={"handled_by": self.name}
        )


class WeatherAgent(BaseAgent):
    name = "weather"
    description = "Weather stub (no API)."

    def can_handle(self, text: str) -> bool:
        t = text.strip().lower()
        return "wetter" in t or t.startswith("weather")

    def handle(
        self, ctx: AgentContext, text: str, state: Dict[str, Any]
    ) -> AgentResult:
        return AgentResult(
            messages=[
                "Weather-Agent (Stub): keine externe API in dieser Version.",
                "Nächster Schritt: Plugin anschließen + UI-Kachel (Wind/Luftqualität).",
            ],
            data={"handled_by": self.name},
        )


class MailAgent(BaseAgent):
    name = "mail"
    description = "Mail draft templates."

    def can_handle(self, text: str) -> bool:
        return text.strip().lower().startswith("mail:")

    def handle(
        self, ctx: AgentContext, text: str, state: Dict[str, Any]
    ) -> AgentResult:
        if not ctx.permissions.can_write_mail:
            return AgentResult(errors=["Keine Berechtigung für Mail-Entwürfe."])
        body = text.split(":", 1)[1].strip()
        if not body:
            return AgentResult(errors=["Gib nach `mail:` kurz Anlass/Details an."])
        draft = (
            "Betreff: Mangel / defekte Fliesenlieferung – Bitte um Lösung\n\n"
            "Guten Tag,\n\n"
            f"wir melden einen Mangel: {body}\n\n"
            "Bitte teilen Sie uns mit, ob Sie eine Gutschrift/Rabatt anbieten können oder wie der weitere Ablauf ist.\n"
            "Fotos sind beigefügt.\n\n"
            "Mit freundlichen Grüßen\n"
            f"{ctx.user}\n"
        )
        return AgentResult(
            messages=["Mail-Entwurf erstellt."],
            actions=[ToolAction(type="mail_draft", payload={"draft": draft})],
            data={"draft": draft, "handled_by": self.name},
        )


# =========================
# Orchestrator
# =========================
class AgentOrchestrator:
    def __init__(self):
        self.agents: List[BaseAgent] = [
            HelpAgent(),
            IndexAgent(),
            SearchAgent(),
            OpenFileAgent(),
            SummaryAgent(),
            WeatherAgent(),
            MailAgent(),
        ]

    def route(self, ctx: AgentContext, text: str, state: Dict[str, Any]) -> AgentResult:
        text = (text or "").strip()
        if not text:
            return AgentResult(
                messages=["Sag `help` für Beispiele."], data={"handled_by": "empty"}
            )

        for ag in self.agents:
            if ag.can_handle(text):
                res = ag.handle(ctx, text, state)
                res.data.setdefault("handled_by", ag.name)
                return res

        return AgentResult(
            messages=[
                "Nicht erkannt.",
                "Tipps: `suche ...`, `index neu`, `öffne ...`, `mail: ...`, `help`",
            ],
            data={"handled_by": "fallback"},
        )


ORCH = AgentOrchestrator()

# =========================
# UI (minimal) + floating chat
# =========================
BASE_HTML = """
<!doctype html>
<html>
<head>
<meta charset="utf-8"/>
<title>{{title}}</title>
<style>
:root{
  --bg:#0b1220; --panel:#0f172a; --panel2:#111c34; --text:#e5e7eb; --muted:#94a3b8;
  --border:#24324a; --accent:#10b981;
}
body { font-family: system-ui, -apple-system; margin:0; background:var(--bg); color:var(--text); }
header { padding:12px 16px; background:#020617; display:flex; justify-content:space-between; align-items:center; border-bottom:1px solid var(--border); }
a { color:var(--text); text-decoration:none; }
nav a { margin-right:10px; padding:6px 10px; border-radius:10px; background:var(--panel); border:1px solid var(--border); }
nav a.active { outline:2px solid var(--accent); }
main { padding:16px; max-width:1100px; margin:0 auto; }
.card { background:var(--panel); border:1px solid var(--border); border-radius:16px; padding:14px; margin:12px 0; }
.muted { color:var(--muted); }
input, textarea, button, select { background:var(--panel2); color:var(--text); border:1px solid var(--border); border-radius:12px; padding:10px; }
button { cursor:pointer; }
.row { display:flex; gap:12px; flex-wrap:wrap; align-items:center; }

/* Floating chat button + drawer */
#chatBtn{
  position:fixed; right:18px; bottom:18px;
  width:56px; height:56px; border-radius:999px;
  background:var(--accent); border:none; color:#052e2a;
  box-shadow: 0 10px 25px rgba(0,0,0,.35);
  font-weight:700; font-size:18px;
}
#chatDrawer{
  position:fixed; right:18px; bottom:86px; width:360px; max-width: calc(100vw - 36px);
  height:520px; max-height: calc(100vh - 120px);
  background:var(--panel); border:1px solid var(--border); border-radius:18px;
  display:none; overflow:hidden;
}
#chatHeader{ padding:10px 12px; border-bottom:1px solid var(--border); display:flex; justify-content:space-between; align-items:center; }
#chatLog{ padding:12px; height:400px; overflow:auto; }
.msg{ margin:10px 0; }
.msg .who{ font-size:12px; color:var(--muted); margin-bottom:4px; }
.bubble{ background:var(--panel2); border:1px solid var(--border); border-radius:14px; padding:10px; white-space:pre-wrap; }
.msg.you .bubble{ outline:2px solid rgba(16,185,129,.35); }
#chatForm{ padding:10px 12px; border-top:1px solid var(--border); display:flex; gap:8px; }
#chatInput{ flex:1; }
.small{ font-size:12px; color:var(--muted); }
pre { white-space:pre-wrap; }
code { color: #a7f3d0; }
</style>
</head>
<body>
<header>
  <div><strong>{{app}}</strong> <span class="muted">• tenant: {{tenant}} • role: {{user.role}}</span></div>
  <div>
    {% if user.user %}
      <span class="muted">{{user.user}}</span>
      <a class="muted" style="margin-left:10px;" href="{{url_for('logout')}}">Logout</a>
    {% endif %}
  </div>
</header>
<main>
  <nav>
    <a class="{{'active' if active_tab=='home' else ''}}" href="{{url_for('home')}}">Home</a>
    <a class="{{'active' if active_tab=='assistant' else ''}}" href="{{url_for('assistant')}}">Assistant</a>
    <a class="{{'active' if active_tab=='mail' else ''}}" href="{{url_for('mail')}}">Mail Agent</a>
    <a class="{{'active' if active_tab=='weather' else ''}}" href="{{url_for('weather')}}">Weather</a>
  </nav>

  {{content|safe}}
</main>

<button id="chatBtn" title="Agent Chat">💬</button>
<div id="chatDrawer">
  <div id="chatHeader">
    <div>
      <strong>Agent Chat</strong><div class="small">Commands: help / index neu / suche / öffne / mail</div>
    </div>
    <button id="chatClose">✕</button>
  </div>
  <div id="chatLog"></div>
  <form id="chatForm">
    <input id="chatInput" placeholder="z.B. 'help' oder 'suche rechnung gerd'"/>
    <button type="submit">Senden</button>
  </form>
</div>

<script>
const btn = document.getElementById('chatBtn');
const drawer = document.getElementById('chatDrawer');
const closeBtn = document.getElementById('chatClose');
const log = document.getElementById('chatLog');
const form = document.getElementById('chatForm');
const input = document.getElementById('chatInput');

function addMsg(who, text){
  const el = document.createElement('div');
  el.className = 'msg ' + (who === 'you' ? 'you' : 'assistant');
  el.innerHTML = `<div class="who">${who}</div><div class="bubble"></div>`;
  el.querySelector('.bubble').textContent = text;
  log.appendChild(el);
  log.scrollTop = log.scrollHeight;
}

btn.onclick = () => {
  drawer.style.display = 'block';
  if(!log.dataset.boot){
    addMsg('assistant','Hi! Tippe `help` für Beispiele.');
    log.dataset.boot='1';
  }
};
closeBtn.onclick = () => { drawer.style.display = 'none'; };

form.addEventListener('submit', async (e) => {
  e.preventDefault();
  const msg = input.value.trim();
  if(!msg) return;
  addMsg('you', msg);
  input.value = '';
  const r = await fetch('/api/agent', {
    method:'POST',
    headers:{'Content-Type':'application/json'},
    body: JSON.stringify({message: msg})
  });
  const j = await r.json();
  if(j.error){ addMsg('assistant', 'Error: ' + j.error); return; }
  const out = (j.messages || []).join('\n');
  addMsg('assistant', out || '(keine Antwort)');
});
</script>
</body>
</html>
"""


def _render_base(content: str, title: str, active_tab: str):
    u = current_user()
    return render_template_string(
        BASE_HTML,
        title=title,
        app=APP_NAME,
        tenant=u["tenant"],
        user=u,
        active_tab=active_tab,
        content=content,
    )


# =========================
# Routes
# =========================
HTML_LOGIN = """
<div class="card">
  <h2>Login</h2>
  <p class="muted">Demo-Login. Dev-Tenant ist fix: <b>KUKANILEA Dev</b></p>
  {% if error %}<p style="color:#fb7185;"><b>{{error}}</b></p>{% endif %}
  <form method="post" class="row">
    <input name="user" placeholder="dev / admin / user" />
    <input name="pw" placeholder="password" type="password"/>
    <button type="submit">Login</button>
  </form>
  <p class="muted small">Tipp: dev/dev oder admin/admin</p>
</div>
"""


@app.route("/login", methods=["GET", "POST"])
def login():
    error = ""
    nxt = request.args.get("next", "/")
    if request.method == "POST":
        u = (request.form.get("user") or "").strip()
        pw = (request.form.get("pw") or "").strip()
        rec = USERS.get(u)
        if not rec or rec["pw"] != pw:
            error = "Login fehlgeschlagen"
        else:
            session["user"] = u
            session["role"] = rec["role"]
            session["tenant"] = rec["tenant"]
            return redirect(nxt)
    return _render_base(
        render_template_string(HTML_LOGIN, error=error), "Login", "home"
    )


@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("login"))


@app.route("/")
@login_required
def home():
    content = f"""
    <div class="card">
      <h2>Home</h2>
      <p class="muted">Base-Path: <b>{BASE_PATH}</b></p>
      <p class="muted">Index: <b>{DB_INDEX_PATH}</b></p>
      <p class="muted small">Chat unten rechts: 💬</p>
    </div>
    """
    return _render_base(content, APP_NAME, "home")


@app.route("/assistant")
@login_required
def assistant():
    content = """
    <div class="card">
      <h2>Assistant</h2>
      <p class="muted">Der Orchestrator ist aktiv. Nutze den 💬-Button oder sende JSON an <code>/api/agent</code>.</p>
      <div class="card">
        <div class="muted">Beispiele:</div>
        <pre class="muted">help
index neu
suche rechnung gerd 24.10.2025
öffne /Pfad/zur/Datei.pdf
mail: defekte fliesenlieferung, bitte rabatt</pre>
      </div>
    </div>
    """
    return _render_base(content, "Assistant", "assistant")


@app.route("/mail")
@login_required
def mail():
    content = """
    <div class="card">
      <h2>Mail Agent</h2>
      <p class="muted">ARCH-only: Mail-Entwürfe via <code>mail: ...</code> im Chat.</p>
      <p class="muted small">Später: API-Anbindung (SMTP/Gmail/Exchange) + Versand-Flow.</p>
    </div>
    """
    return _render_base(content, "Mail Agent", "mail")


@app.route("/weather")
@login_required
def weather():
    content = """
    <div class="card">
      <h2>Weather</h2>
      <p class="muted">ARCH-only: Weather-Agent ist stub (keine externe API).</p>
      <p class="muted small">Später: Plugin mit Wind/Luftqualität + Forecast-Kachel.</p>
    </div>
    """
    return _render_base(content, "Weather", "weather")


@app.route("/api/agent", methods=["POST"])
@login_required
def api_agent():
    payload = request.get_json(silent=True) or {}
    msg = (payload.get("message") or "").strip()
    state = payload.get("state") or {}

    u = current_user()
    ctx = AgentContext(
        tenant=u["tenant"],
        user=u["user"],
        role=u["role"],
        permissions=Permissions.from_role(u["role"]),
        base_path=BASE_PATH,
        index_path=DB_INDEX_PATH,
    )

    res = ORCH.route(ctx, msg, state)

    return jsonify(
        {
            "messages": res.messages,
            "actions": [a.__dict__ for a in res.actions],
            "data": res.data,
            "errors": res.errors,
        }
    )


if __name__ == "__main__":
    print("http://127.0.0.1:5051")
    app.run(port=5051, debug=True)
