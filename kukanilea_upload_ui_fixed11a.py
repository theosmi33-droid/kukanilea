#!/usr/bin/env python3
# KUKANILEA Systems – UI FIXED11a (single file, runnable)

from flask import Flask, request, redirect, url_for, session, render_template_string
from functools import wraps

app = Flask(__name__)
app.secret_key = "kukanilea-dev-secret"

APP_NAME = "KUKANILEA Systems"
DEV_TENANT = "KUKANILEA Dev"

def login_required(fn):
    @wraps(fn)
    def wrapper(*args, **kwargs):
        if not session.get("user"):
            return redirect(url_for("login", next=request.path))
        return fn(*args, **kwargs)
    return wrapper

BASE_HTML = '''
<!doctype html>
<html>
<head>
<meta charset="utf-8"/>
<title>{{title}}</title>
<style>
body { font-family: system-ui; margin:0; background:#0f172a; color:#e5e7eb; }
header { padding:12px 16px; background:#020617; display:flex; justify-content:space-between; }
nav a { margin-right:12px; color:#a7f3d0; text-decoration:none; }
main { padding:24px; }
.card { background:#020617; border:1px solid #1f2937; border-radius:12px; padding:16px; margin-bottom:16px;}
input, textarea, button { padding:8px; border-radius:8px; border:1px solid #334155; background:#020617; color:#e5e7eb; width:100%; }
button { width:auto; cursor:pointer; }
.muted { color:#94a3b8; font-size:13px; }
</style>
</head>
<body>
<header>
<div><b>{{app}}</b></div>
<div>{% if user %}{{user}} · {{tenant}} · <a href="{{url_for('logout')}}">Logout</a>{% endif %}</div>
</header>
<nav style="padding:8px 16px;">
{% if user %}
<a href="/">Upload</a>
<a href="/assistant">Assistant</a>
<a href="/mail">Mail Agent</a>
<a href="/weather">Weather</a>
{% endif %}
</nav>
<main>{{content|safe}}</main>
</body>
</html>
'''

@app.route("/login", methods=["GET","POST"])
def login():
    error = ""
    if request.method == "POST":
        if request.form.get("user")=="dev" and request.form.get("pw")=="dev":
            session["user"]="DEVELOPER"
            session["tenant"]=DEV_TENANT
            return redirect(request.args.get("next","/"))
        error="Login fehlgeschlagen (dev/dev)"
    content = f'''
    <div class="card">
    <h2>Login</h2>
    <form method="post">
    <input name="user" placeholder="user"/><br/><br/>
    <input type="password" name="pw" placeholder="password"/><br/><br/>
    <button>Login</button>
    <div class="muted">{error}</div>
    </form>
    </div>
    '''
    return render_template_string(BASE_HTML, title="Login", app=APP_NAME, user=None, tenant=None, content=content)

@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("login"))

@app.route("/")
@login_required
def upload():
    return render_template_string(BASE_HTML, title="Upload", app=APP_NAME,
        user=session["user"], tenant=session["tenant"],
        content="<div class='card'><h2>Upload</h2><p class='muted'>Stub – stabiler Startpunkt.</p></div>")

@app.route("/assistant")
@login_required
def assistant():
    return render_template_string(BASE_HTML, title="Assistant", app=APP_NAME,
        user=session["user"], tenant=session["tenant"],
        content="<div class='card'><h2>Agent Chat</h2><input placeholder='Frag etwas…'/></div>")

@app.route("/mail")
@login_required
def mail():
    return render_template_string(BASE_HTML, title="Mail Agent", app=APP_NAME,
        user=session["user"], tenant=session["tenant"],
        content="<div class='card'><h2>Mail Agent</h2><textarea></textarea></div>")

@app.route("/weather")
@login_required
def weather():
    return render_template_string(BASE_HTML, title="Weather", app=APP_NAME,
        user=session["user"], tenant=session["tenant"],
        content="<div class='card'><h2>Weather</h2><p class='muted'>Stub</p></div>")

if __name__=="__main__":
    print("http://127.0.0.1:5051")
    app.run(port=5051, debug=True)
