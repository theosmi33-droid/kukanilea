
import sys
from pathlib import Path

path = Path("app/web.py")
if not path.exists():
    path = Path("Tophandwerk/kukanilea-git/app/web.py")

content = path.read_text(encoding="utf-8")

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

# HTML_INDEX
start_idx_m = 'HTML_INDEX = r"""<div class="grid lg:grid-cols-2 gap-6">'
next_block = 'HTML_REVIEW_SPLIT = r"""'
s_idx = content.find(start_idx_m)
e_idx = content.find(next_block, s_idx)

if s_idx != -1 and e_idx != -1:
    content = content[:s_idx] + new_html_index + "\n\n" + content[e_idx:]
    path.write_text(content, encoding="utf-8")
    print("FIX SUCCESS")
else:
    print(f"FIX FAILED: start={s_idx}, end={e_idx}")
