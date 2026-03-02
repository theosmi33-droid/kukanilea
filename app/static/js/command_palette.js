/**
 * static/js/command_palette.js
 * Global command palette (Ctrl+K) for KUKANILEA v2.0.
 */
const CommandPalette = {
    isOpen: false,
    icons: {
        'layout': '<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect width="7" height="7" x="3" y="3" rx="1"/><rect width="7" height="7" x="14" y="3" rx="1"/><rect width="7" height="7" x="14" y="14" rx="1"/><rect width="7" height="7" x="3" y="14" rx="1"/></svg>',
        'users': '<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M16 21v-2a4 4 0 0 0-4-4H6a4 4 0 0 0-4 4v2"/><circle cx="9" cy="7" r="4"/><path d="M22 21v-2a4 4 0 0 0-3-3.87"/><path d="M16 3.13a4 4 0 0 1 0 7.75"/></svg>',
        'check-square': '<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polyline points="9 11 12 14 22 4"/><path d="M21 12v7a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h11"/></svg>',
        'file-text': '<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M14.5 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V7.5L14.5 2z"/><polyline points="14.5 2 14.5 7.5 20 7.5"/><line x1="8" y1="13" x2="16" y2="13"/><line x1="8" y1="17" x2="16" y2="17"/><line x1="8" y1="9" x2="10" y2="9"/></svg>',
        'cpu': '<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect width="16" height="16" x="4" y="4" rx="2"/><rect width="6" height="6" x="9" y="9" rx="1"/><path d="M15 2v2"/><path d="M15 20v2"/><path d="M2 15h2"/><path d="M2 9h2"/><path d="M20 15h2"/><path d="M20 9h2"/><path d="M9 2v2"/><path d="M9 20v2"/></svg>',
        'shield': '<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z"/></svg>',
        'moon': '<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M12 3a6 6 0 0 0 9 9 9 9 0 1 1-9-9Z"/></svg>',
        'settings': '<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M12.22 2h-.44a2 2 0 0 0-2 2v.18a2 2 0 0 1-1 1.73l-.43.25a2 2 0 0 1-2 0l-.15-.08a2 2 0 0 0-2.73.73l-.22.38a2 2 0 0 0 .73 2.73l.15.1a2 2 0 0 1 1 1.72v.51a2 2 0 0 1-1 1.74l-.15.09a2 2 0 0 0-.73 2.73l.22.38a2 2 0 0 0 2.73.73l.15-.08a2 2 0 0 1 2 0l.43.25a2 2 0 0 1 1 1.73V20a2 2 0 0 0 2 2h.44a2 2 0 0 0 2-2v-.18a2 2 0 0 1 1-1.73l.43-.25a2 2 0 0 1 2 0l.15.08a2 2 0 0 0 2.73-.73l.22-.39a2 2 0 0 0-.73-2.73l-.15-.1a2 2 0 0 1-1-1.74v-.5a2 2 0 0 1 1-1.74l.15-.09a2 2 0 0 0 .73-2.73l-.22-.38a2 2 0 0 0-2.73-.73l-.15.08a2 2 0 0 1-2 0l-.43-.25a2 2 0 0 1-1-1.73V4a2 2 0 0 0-2-2Z"/><circle cx="12" cy="12" r="3"/></svg>',
        'default': '<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect width="18" height="18" x="3" y="3" rx="2" ry="2"/></svg>'
    },
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
        this.injectStyles();
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

    injectStyles() {
        if (document.getElementById('cmd-palette-styles')) return;
        const style = document.createElement('style');
        style.id = 'cmd-palette-styles';
        style.textContent = `
            #cmd-palette-overlay {
                display: none;
                position: fixed;
                inset: 0;
                background: rgba(0,0,0,0.6);
                backdrop-filter: blur(4px);
                z-index: 9000;
                align-items: flex-start;
                justify-content: center;
                padding-top: 15vh;
            }
            #cmd-palette-modal {
                width: 100%;
                max-width: 600px;
                padding: 0;
                overflow: hidden;
                background: var(--color-bg-root);
                border: 1px solid var(--color-border);
                box-shadow: var(--shadow-2xl);
                border-radius: var(--radius-lg);
            }
            .cmd-header {
                padding: 16px;
                border-bottom: 1px solid var(--color-border);
                display: flex;
                align-items: center;
                gap: 12px;
            }
            #cmd-input {
                flex: 1;
                background: none;
                border: none;
                color: var(--color-text-main);
                font-size: 16px;
                outline: none;
                font-family: var(--font-primary);
            }
            .cmd-kbd {
                padding: 2px 6px;
                background: var(--bg-tertiary);
                border-radius: 4px;
                font-size: 10px;
                color: var(--text-tertiary);
                border: 1px solid var(--color-border);
            }
            #cmd-results {
                max-height: 400px;
                overflow-y: auto;
                padding: 8px;
            }
            .cmd-footer {
                padding: 12px;
                background: var(--bg-secondary);
                border-top: 1px solid var(--color-border);
                display: flex;
                gap: 16px;
                font-size: 11px;
                color: var(--text-tertiary);
            }
            .cmd-item {
                padding: 12px 16px;
                border-radius: var(--radius-md);
                cursor: pointer;
                display: flex;
                align-items: center;
                gap: 16px;
                transition: background 0.1s;
            }
            .cmd-item:hover, .cmd-item.selected {
                background: rgba(255,255,255,0.05);
            }
            .cmd-icon-wrapper {
                width: 32px;
                height: 32px;
                border-radius: 6px;
                background: rgba(255,255,255,0.02);
                border: 1px solid var(--color-border);
                display: flex;
                align-items: center;
                justify-content: center;
                color: var(--color-accent);
            }
            .cmd-info {
                flex: 1;
            }
            .cmd-title {
                font-weight: 600;
                font-size: 14px;
                color: var(--color-text-main);
            }
            .cmd-subtitle {
                font-size: 12px;
                color: var(--color-text-muted);
            }
        `;
        document.head.appendChild(style);
    },

    render() {
        const html = `
            <div id="cmd-palette-overlay">
                <div id="cmd-palette-modal" class="panel">
                    <div class="cmd-header">
                        <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="var(--color-text-muted)" stroke-width="2"><circle cx="11" cy="11" r="8"/><line x1="21" y1="21" x2="16.65" y2="16.65"/></svg>
                        <input type="text" id="cmd-input" placeholder="Befehl oder Suche..." autocomplete="off">
                        <kbd class="cmd-kbd">ESC</kbd>
                    </div>
                    <div id="cmd-results"></div>
                    <div class="cmd-footer">
                        <span><kbd class="cmd-kbd">↑↓</kbd> Navigieren</span>
                        <span><kbd class="cmd-kbd">↵</kbd> Auswählen</span>
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
            div.className = 'cmd-item' + (idx === 0 ? ' selected' : '');
            
            const iconHtml = this.icons[c.icon] || this.icons['default'];
            
            div.innerHTML = `
                <div class="cmd-icon-wrapper">
                    ${iconHtml}
                </div>
                <div class="cmd-info">
                    <div class="cmd-title">${c.title}</div>
                    <div class="cmd-subtitle">${c.subtitle}</div>
                </div>
            `;
            div.onclick = () => { c.action(); this.close(); };
            this.resultsContainer.appendChild(div);
        });
    }
};

document.addEventListener('DOMContentLoaded', () => CommandPalette.init());

