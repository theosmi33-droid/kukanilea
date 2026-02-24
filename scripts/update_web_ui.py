
import sys
from pathlib import Path

path = Path("app/web.py")
if not path.exists():
    path = Path("Tophandwerk/kukanilea-git/app/web.py")

content = path.read_text(encoding="utf-8")

new_html_base = r'''HTML_BASE = r"""<!doctype html>
<html lang="de">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<link rel="manifest" href="/app.webmanifest">
<link rel="icon" type="image/png" href="{{ url_for('static', filename='icons/app-icon.png') }}">
<title>KUKANILEA Gold</title>
<script src="{{ url_for('static', filename='vendor/tailwindcss.min.js') }}"></script>
<script src="{{ url_for('static', filename='vendor/htmx.min.js') }}"></script>
<style>
  :root{
    --font-sans: 'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
    --bg: #ffffff;
    --text: #09090b;
    --muted: #71717a;
    --border: #f4f4f5;
    --accent: #2563eb;
  }
  * { box-sizing: border-box; }
  body {
    margin: 0; background: var(--bg); color: var(--text);
    font-family: var(--font-sans); -webkit-font-smoothing: antialiased;
  }
  .app-shell { display: flex; min-height: 100vh; flex-direction: column; }
  .app-nav {
    display: flex; justify-content: space-between; align-items: center;
    padding: 20px 40px; border-bottom: 1px solid var(--border);
    position: sticky; top: 0; background: rgba(255,255,255,0.8); backdrop-filter: blur(12px); z-index: 100;
  }
  .nav-logo { font-weight: 800; font-size: 1.2rem; text-transform: uppercase; letter-spacing: -0.02em; color: #000; text-decoration: none; display: flex; align-items: center; gap: 8px; }
  .nav-links { display: flex; gap: 32px; align-items: center; }
  .nav-link { text-decoration: none; color: var(--muted); font-size: 0.85rem; font-weight: 600; transition: color 0.2s; }
  .nav-link:hover, .nav-link.active { color: var(--text); }
  .app-main { max-width: 1000px; margin: 0 auto; width: 100%; padding: 60px 40px; flex: 1; }
  .floating-tools {
    position: fixed; bottom: 40px; left: 50%; transform: translateX(-50%);
    background: rgba(255,255,255,0.8); backdrop-filter: blur(16px);
    border: 1px solid var(--border); padding: 12px 24px; border-radius: 999px;
    display: flex; gap: 24px; box-shadow: 0 20px 40px rgba(0,0,0,0.05); z-index: 200;
  }
  .tool-btn { background: none; border: none; color: var(--muted); cursor: pointer; display: flex; align-items: center; justify-content: center; transition: color 0.2s; }
  .tool-btn:hover { color: #000; }
  #chat-sidebar {
    position: fixed; top: 0; right: 0; bottom: 0; width: 450px;
    background: #fff; border-left: 1px solid var(--border);
    transform: translateX(100%); transition: transform 0.4s cubic-bezier(0.16, 1, 0.3, 1);
    z-index: 300; display: flex; flex-direction: column;
  }
  #chat-sidebar.open { transform: translateX(0); }
  .no-scrollbar::-webkit-scrollbar { display: none; }
  .no-scrollbar { -ms-overflow-style: none; scrollbar-width: none; }
</style>
</head>
<body class="light">
<div class="app-shell">
  <header class="app-nav">
    <a href="/" class="nav-logo">
      <div class="w-8 h-8 bg-black rounded-lg flex items-center justify-center text-white text-xs">K</div>
      KUKANILEA
    </a>
    <div class="nav-links">
      <a class="nav-link {{'active' if active_tab=='tasks' else ''}}" href="/tasks">Aufgaben</a>
      <a class="nav-link {{'active' if active_tab=='crm' else ''}}" href="/crm">Kunden</a>
      <a class="nav-link {{'active' if active_tab=='knowledge' else ''}}" href="/knowledge">Wissen</a>
      <a class="nav-link {{'active' if active_tab=='settings' else ''}}" href="/settings">System</a>
      <div class="w-8 h-8 rounded-full bg-zinc-100 flex items-center justify-center text-[10px] font-bold border border-zinc-200">{{ user[0].upper() if user else '?' }}</div>
    </div>
  </header>

  <main class="app-main">
    {% if read_only %}
    <div class="mb-8 p-4 bg-rose-50 text-rose-600 rounded-2xl text-sm font-bold border border-rose-100 flex items-center justify-between">
      <span>Read-only Mode aktiv ({{license_reason}}). Schreibaktionen sind deaktiviert.</span>
      <a href="/license" class="underline">Lizenz verwalten</a>
    </div>
    {% endif %}
    {{ content | safe }}
  </main>

  <div class="floating-tools">
    <button class="tool-btn" onclick="toggleChat()" title="KI Chat">
      <svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path d="M8 10h.01M12 10h.01M16 10h.01M9 16H5a2 2 0 01-2-2V6a2 2 0 012-2h14a2 2 0 012 2v8a2 2 0 01-2 2h-5l-5 5v-5z" stroke-width="2"></path></svg>
    </button>
    <div class="w-px h-4 bg-zinc-200"></div>
    <button class="tool-btn" id="vision-camera-btn" title="Kamera">
      <svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path d="M3 9a2 2 0 012-2h.93a2 2 0 001.664-.89l.812-1.22A2 2 0 0110.07 4h3.86a2 2 0 011.664.89l.812 1.22A2 2 0 0018.07 7H19a2 2 0 012 2v9a2 2 0 01-2 2H5a2 2 0 01-2-2V9z" stroke-width="2"></path></svg>
    </button>
    <button class="tool-btn" id="voice-record-btn" title="Sprache">
      <svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path d="M19 11a7 7 0 01-7 7m0 0a7 7 0 01-7-7m7 7v4m0 0H8m4 0h4m-4-8a3 3 0 01-3-3V5a3 3 0 116 0v6a3 3 0 01-3 3z" stroke-width="2"></path></svg>
    </button>
  </div>

  <aside id="chat-sidebar">
    <div id="chat-container" class="h-full">
      <div class="flex items-center justify-center h-full text-zinc-300 text-xs uppercase tracking-widest">Initialisiere...</div>
    </div>
  </aside>
</div>

<script>
  function toggleChat() {
    const sidebar = document.getElementById('chat-sidebar');
    const container = document.getElementById('chat-container');
    sidebar.classList.toggle('open');
    if (sidebar.classList.contains('open') && !container.dataset.loaded) {
      htmx.ajax('GET', '/ai-chat/', '#chat-container');
      container.dataset.loaded = 'true';
    }
  }
  document.addEventListener('keydown', function(e) {
    if ((e.metaKey || e.ctrlKey) && e.shiftKey && (e.key === 'D' || e.key === 'd')) {
      e.preventDefault();
      window.location.href = "/dev/dashboard/";
    }
  });
</script>
<script src="{{ url_for('static', filename='js/toast.js') }}"></script>
<script src="{{ url_for('static', filename='js/voice_recorder.js') }}"></script>
<script src="{{ url_for('static', filename='js/vision_camera.js') }}"></script>
</body>
</html>"""'''

new_html_index = r'''HTML_INDEX = r"""
<section class="mb-32 text-center pt-20">
    <h1 class="text-5xl font-bold tracking-tight text-black mb-6">Wie kann ich heute <br/><span class="text-zinc-400">unterstützen?</span></h1>
    
    <div class="relative group mt-12 max-w-2xl mx-auto">
        <div class="relative bg-zinc-50 border border-zinc-200 rounded-2xl p-2 flex items-center shadow-sm focus-within:ring-2 focus-within:ring-blue-500/20 transition-all">
            <input type="text" 
                   id="hero-chat-input"
                   placeholder="Frage stellen oder Aktion ausführen..." 
                   class="flex-1 bg-transparent border-none px-6 py-4 text-lg focus:outline-none placeholder:text-zinc-300"
                   onkeydown="if(event.key === 'Enter') { 
                       const msg = this.value;
                       if(msg.trim()) {
                           toggleChat();
                           setTimeout(() => {
                               const chatIn = document.getElementById('chat-input');
                               if(chatIn) { chatIn.value = msg; chatIn.dispatchEvent(new Event('input')); }
                           }, 200);
                           this.value = '';
                       }
                   }">
            <button onclick="const input = document.getElementById('hero-chat-input'); if(input.value.trim()){ toggleChat(); setTimeout(() => { const chatIn = document.getElementById('chat-input'); if(chatIn){ chatIn.value = input.value; chatIn.dispatchEvent(new Event('input')); } input.value = ''; }, 200); }" 
                    class="bg-black hover:bg-zinc-800 text-white p-4 rounded-xl transition-all shadow-lg active:scale-95">
                <svg class="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2.5" d="M14 5l7 7m0 0l-7 7m7-7H3"></path></svg>
            </button>
        </div>
        <div class="mt-6 flex gap-3 justify-center overflow-x-auto no-scrollbar">
            <button class="px-4 py-2 bg-white border border-zinc-200 rounded-full text-[10px] font-bold text-zinc-500 hover:border-black hover:text-black transition-all uppercase tracking-widest">Soll-Ist Vergleich</button>
            <button class="px-4 py-2 bg-white border border-zinc-200 rounded-full text-[10px] font-bold text-zinc-500 hover:border-black hover:text-black transition-all uppercase tracking-widest">Offene Aufgaben</button>
            <button class="px-4 py-2 bg-white border border-zinc-200 rounded-full text-[10px] font-bold text-zinc-500 hover:border-black hover:text-black transition-all uppercase tracking-widest">Materialbestellung</button>
        </div>
    </div>
</section>

<section class="grid grid-cols-1 md:grid-cols-2 gap-16 pb-20">
    <div class="group cursor-pointer" onclick="window.location.href='/tasks'">
        <div class="text-[9px] font-black text-blue-600 uppercase tracking-[0.3em] mb-4">Operations</div>
        <h2 class="text-xl font-bold mb-2 group-hover:translate-x-1 transition-transform">Betrieb & Aufgaben</h2>
        <p class="text-sm text-zinc-400 leading-relaxed">Steuern Sie Ihre Baustellen und verfolgen Sie den Fortschritt Ihrer Teams.</p>
    </div>

    <div class="group cursor-pointer" onclick="window.location.href='/knowledge'">
        <div class="text-[9px] font-black text-blue-600 uppercase tracking-[0.3em] mb-4">Intelligence</div>
        <h2 class="text-xl font-bold mb-2 group-hover:translate-x-1 transition-transform">Wissensdatenbank</h2>
        <p class="text-sm text-zinc-400 leading-relaxed">Technische Details, Normen und Projektunterlagen durch lokale KI-Suche.</p>
    </div>
</section>
"""'''

# HTML_BASE
start_base = 'HTML_BASE = r"""<!doctype html>'
end_base = '</html>"""'
s_idx = content.find(start_base)
e_idx = content.find(end_base, s_idx)

if s_idx != -1 and e_idx != -1:
    content = content[:s_idx] + new_html_base + content[e_idx + len(end_base):]

# HTML_INDEX
start_idx_m = 'HTML_INDEX = r"""<div class="grid lg:grid-cols-2 gap-6">'
next_block = 'HTML_LOGIN = r"""'
s_idx = content.find(start_idx_m)
e_idx = content.find(next_block, s_idx)

if s_idx != -1 and e_idx != -1:
    content = content[:s_idx] + new_html_index + "\n\n" + content[e_idx:]

path.write_text(content, encoding="utf-8")
print("SUCCESS")
