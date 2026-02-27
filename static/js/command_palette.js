/**
 * static/js/command_palette.js
 * Global command palette (Ctrl+K) for KUKANILEA v2.0.
 */
const CommandPalette = {
    isOpen: false,
    commands: [
        { id: 'nav-dash', title: 'Dashboard', subtitle: 'Zur Übersicht', icon: 'layout', action: () => window.location.href = '/' },
        { id: 'nav-crm', title: 'CRM - Kontakte', subtitle: 'Kunden verwalten', icon: 'users', action: () => window.location.href = '/crm/contacts' },
        { id: 'nav-tasks', title: 'Aufgaben', subtitle: 'To-Dos und Projekte', icon: 'check-square', action: () => window.location.href = '/tasks' },
        { id: 'nav-docs', title: 'Dokumente', subtitle: 'Archiv durchsuchen', icon: 'file-text', action: () => window.location.href = '/documents' },
        { id: 'nav-assistant', title: 'KI-Assistent', subtitle: 'Frag die KI', icon: 'cpu', action: () => window.location.href = '/assistant' },
        { id: 'nav-audit', title: 'Audit Trail', subtitle: 'GoBD Compliance prüfen', icon: 'shield', action: () => window.location.href = '/admin/audit' },
        { id: 'action-theme', title: 'Farbschema wechseln', subtitle: 'Hell / Dunkel Modus', icon: 'moon', action: () => StateStore.toggleTheme() },
        { id: 'nav-settings', title: 'Einstellungen', subtitle: 'System-Konfiguration', icon: 'settings', action: () => window.location.href = '/settings' },
    ],

    init() {
        this.render();
        window.addEventListener('keydown', (e) => {
            if ((e.ctrlKey || e.metaKey) && e.key === 'k') {
                e.preventDefault();
                this.toggle();
            }
            if (e.key === 'Escape' && this.isOpen) {
                this.close();
            }
        });
    },

    render() {
        const html = `
            <div id="cmd-palette-overlay" style="display:none; position:fixed; inset:0; background:rgba(0,0,0,0.6); backdrop-filter:blur(4px); z-index:9000; align-items:flex-start; justify-content:center; padding-top:15vh;">
                <div id="cmd-palette-modal" class="panel" style="width:100%; max-width:600px; padding:0; overflow:hidden; background:var(--color-bg-root); border:1px solid var(--color-border); box-shadow:var(--shadow-2xl);">
                    <div style="padding:16px; border-bottom:1px solid var(--color-border); display:flex; align-items:center; gap:12px;">
                        <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="var(--color-text-muted)" stroke-width="2"><circle cx="11" cy="11" r="8"/><line x1="21" y1="21" x2="16.65" y2="16.65"/></svg>
                        <input type="text" id="cmd-input" placeholder="Befehl oder Suche..." style="flex:1; background:none; border:none; color:var(--color-text-main); font-size:16px; outline:none; font-family:var(--font-primary);">
                        <kbd style="padding:2px 6px; background:var(--bg-tertiary); border-radius:4px; font-size:10px; color:var(--text-tertiary); border:1px solid var(--color-border);">ESC</kbd>
                    </div>
                    <div id="cmd-results" style="max-height:400px; overflow-y:auto; padding:8px;"></div>
                    <div style="padding:12px; background:var(--bg-secondary); border-top:1px solid var(--color-border); display:flex; gap:16px; font-size:11px; color:var(--text-tertiary);">
                        <span><kbd>↑↓</kbd> Navigieren</span>
                        <span><kbd>↵</kbd> Auswählen</span>
                    </div>
                </div>
            </div>
        `;
        document.body.insertAdjacentHTML('beforeend', html);
        
        this.overlay = document.getElementById('cmd-palette-overlay');
        this.input = document.getElementById('cmd-input');
        this.resultsContainer = document.getElementById('cmd-results');

        this.input.oninput = () => this.filter();
        this.overlay.onclick = (e) => { if(e.target === this.overlay) this.close(); };
    },

    toggle() {
        this.isOpen ? this.close() : this.open();
    },

    open() {
        this.isOpen = true;
        this.overlay.style.display = 'flex';
        this.input.value = '';
        this.filter();
        setTimeout(() => this.input.focus(), 10);
    },

    close() {
        this.isOpen = false;
        this.overlay.style.display = 'none';
    },

    filter() {
        const query = this.input.value.toLowerCase();
        const filtered = this.commands.filter(c => 
            c.title.toLowerCase().includes(query) || 
            c.subtitle.toLowerCase().includes(query)
        );
        this.renderResults(filtered);
    },

    renderResults(list) {
        this.resultsContainer.innerHTML = '';
        list.forEach((c, idx) => {
            const div = document.createElement('div');
            div.style.cssText = `
                padding: 12px 16px;
                border-radius: var(--radius-md);
                cursor: pointer;
                display: flex;
                align-items: center;
                gap: 16px;
                transition: background 0.1s;
            `;
            div.className = 'cmd-item';
            if(idx === 0) div.style.background = 'rgba(255,255,255,0.05)';
            
            div.innerHTML = `
                <div style="width:32px; height:32px; border-radius:6px; background:rgba(255,255,255,0.02); border:1px solid var(--color-border); display:flex; align-items:center; justify-content:center; color:var(--color-accent);">
                    <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect width="18" height="18" x="3" y="3" rx="2" ry="2"/></svg>
                </div>
                <div style="flex:1;">
                    <div style="font-weight:600; font-size:14px; color:var(--color-text-main);">${c.title}</div>
                    <div style="font-size:12px; color:var(--color-text-muted);">${c.subtitle}</div>
                </div>
            `;
            div.onclick = () => { c.action(); this.close(); };
            this.resultsContainer.appendChild(div);
        });
    }
};

document.addEventListener('DOMContentLoaded', () => CommandPalette.init());
