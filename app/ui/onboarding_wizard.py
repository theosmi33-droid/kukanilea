"""
app/ui/onboarding_wizard.py
Erster Start-Assistent für KUKANILEA Gold.
Leitet den Nutzer durch die Hardware-Aktivierung.
"""
from flask import Blueprint, render_template_string, request, redirect, url_for, flash
from app.core.license_manager import license_manager

onboarding_bp = Blueprint("onboarding", __name__)

@onboarding_bp.route("/activate", methods=["GET", "POST"])
def activate():
    if license_manager.is_valid():
        return redirect("/")

    hwid = license_manager.hardware_id
    error = None
    
    if request.method == "POST":
        key = request.form.get("license_key", "").strip()
        if license_manager.verify_and_install(key):
            return redirect("/")
        error = "Ungültiger Lizenzschlüssel. Bitte prüfen Sie die HWID und das Ablaufdatum."

    return render_template_string(HTML_WIZARD, hwid=hwid, error=error)

HTML_WIZARD = r"""
<!DOCTYPE html>
<html lang="de">
<head>
    <meta charset="UTF-8">
    <title>KUKANILEA Gold - Aktivierung</title>
    <script src="/static/vendor/tailwindcss.min.js"></script>
    <style>
        body { background: #f8fafc; }
        .glass { background: rgba(255, 255, 255, 0.9); backdrop-filter: blur(10px); }
    </script>
</head>
<body class="flex items-center justify-center min-h-screen p-4">
    <div class="max-w-2xl w-full glass rounded-3xl border shadow-2xl p-10">
        <div class="text-center mb-8">
            <h1 class="text-3xl font-bold text-slate-900">KUKANILEA v1.5.0 Gold</h1>
            <p class="text-slate-500 mt-2">Herzlich willkommen. Bitte aktivieren Sie Ihre Installation.</p>
        </div>

        <div class="bg-slate-100 p-6 rounded-2xl border-2 border-dashed border-slate-200 mb-8">
            <label class="block text-xs font-bold uppercase tracking-wider text-slate-400 mb-2">Ihre Hardware-ID (HWID):</label>
            <div class="flex items-center gap-4">
                <code class="flex-1 bg-white p-3 rounded-lg border font-mono text-sm select-all">{{ hwid }}</code>
            </div>
            <p class="text-[11px] text-slate-400 mt-3">Senden Sie diesen Code an den Support, um Ihren RSA-Schlüssel zu erhalten.</p>
        </div>

        {% if error %}<div class="bg-rose-50 border border-rose-200 text-rose-600 p-4 rounded-xl mb-6 text-sm">{{ error }}</div>{% endif %}

        <form method="post" class="space-y-4">
            <div>
                <label class="block text-sm font-semibold mb-2">Lizenzschlüssel (Base64)</label>
                <textarea name="license_key" rows="5" class="w-full rounded-xl border-slate-200 shadow-sm focus:ring-sky-500 p-4 font-mono text-xs" placeholder="KUKANI-GOLD-..."></textarea>
            </div>
            <button class="w-full bg-slate-900 text-white font-bold py-4 rounded-xl hover:bg-slate-800 transition-all">Jetzt Aktivieren</button>
        </form>
        
        <p class="text-center text-[10px] text-slate-400 mt-10">100% Offline-Verifizierung • DSGVO-konform • GoBD-zertifiziert</p>
    </div>
</body>
</html>
"""
