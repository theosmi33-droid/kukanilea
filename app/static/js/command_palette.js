/**
 * app/static/js/command_palette.js
 * Global command palette (Cmd/Ctrl + K) with instant filtering.
 */
const CommandPalette = {
    isOpen: false,
    selectedIndex: 0,
    filteredCommands: [],

    commands: [
        // navigation
        { id: 'nav-dashboard', category: 'navigation', title: 'Open Dashboard', subtitle: 'Go to overview', path: '/', keywords: 'home dashboard overview' },
        { id: 'nav-tasks', category: 'navigation', title: 'Open Tasks', subtitle: 'View to-dos and projects', path: '/tasks', keywords: 'tasks todos projects' },
        { id: 'nav-docs', category: 'navigation', title: 'Open Documents', subtitle: 'Browse document archive', path: '/documents', keywords: 'documents files archive' },
        { id: 'nav-settings', category: 'navigation', title: 'Open Settings', subtitle: 'System configuration', path: '/settings', keywords: 'settings configuration system' },

        // actions
        { id: 'action-create-agent', category: 'actions', title: 'Create Agent', subtitle: 'Open agent setup flow', path: '/agents', keywords: 'new agent create assistant' },
        { id: 'action-open-logs', category: 'actions', title: 'Open Logs', subtitle: 'Inspect system and automation logs', path: '/system_logs', keywords: 'logs system audit events' },
        { id: 'action-run-automation', category: 'actions', title: 'Run Automation', subtitle: 'Open automation controls', path: '/automation', keywords: 'automation workflow run' },
        {
            id: 'action-search-system',
            category: 'actions',
            title: 'Search System',
            subtitle: 'Search across commands and pages',
            keywords: 'search system find query',
            action: () => {
                const search = document.getElementById('cmd-input');
                if (search) {
                    search.focus();
                    search.select();
                }
            }
        },

        // entities
        { id: 'entity-customers', category: 'entities', title: 'Search Customers', subtitle: 'Lookup CRM contacts', path: '/crm/contacts', keywords: 'customers crm contacts entities' },
        { id: 'entity-rules', category: 'entities', title: 'Search Automation Rules', subtitle: 'Find existing rules', path: '/automation/rules', keywords: 'rules automations entities' },

        // files
        { id: 'file-docs', category: 'files', title: 'Search Files', subtitle: 'Browse project files and documents', path: '/documents', keywords: 'files docs search upload' },
        { id: 'file-upload', category: 'files', title: 'Open Uploads', subtitle: 'Manage uploaded files', path: '/upload', keywords: 'upload files documents' },

        // agents
        { id: 'agent-assistant', category: 'agents', title: 'Open KI Assistant', subtitle: 'Chat with assistant', path: '/assistant', keywords: 'assistant mia ai agents' },
        { id: 'agent-admin', category: 'agents', title: 'Open Agent Admin', subtitle: 'Manage agent configuration', path: '/agents', keywords: 'agents admin configure' },
    ],

    init() {
        this.render();
        window.addEventListener('keydown', (event) => {
            if ((event.ctrlKey || event.metaKey) && event.key.toLowerCase() === 'k') {
                event.preventDefault();
                this.toggle();
                return;
            }

            if (!this.isOpen) {
                return;
            }

            if (event.key === 'Escape') {
                event.preventDefault();
                this.close();
                return;
            }

            if (event.key === 'ArrowDown') {
                event.preventDefault();
                this.moveSelection(1);
                return;
            }

            if (event.key === 'ArrowUp') {
                event.preventDefault();
                this.moveSelection(-1);
                return;
            }

            if (event.key === 'Enter') {
                event.preventDefault();
                this.executeSelected();
            }
        });
    },

    render() {
        const html = `
            <div id="cmd-palette-overlay" style="display:none; position:fixed; inset:0; background:rgba(17,24,39,0.24); z-index:9999; align-items:flex-start; justify-content:center; padding:10vh 16px 16px;">
                <div id="cmd-palette-modal" style="width:100%; max-width:720px; background:#ffffff; border-radius:14px; border:1px solid #e5e7eb; box-shadow:0 24px 60px rgba(15, 23, 42, 0.22); overflow:hidden;">
                    <div style="padding:14px 16px; border-bottom:1px solid #f1f5f9; display:flex; align-items:center; gap:10px;">
                        <span style="color:#94a3b8; font-size:14px;">⌕</span>
                        <input type="text" id="cmd-input" placeholder="Search navigation, actions, entities, files, agents..." style="flex:1; border:none; outline:none; background:transparent; font-size:15px; color:#0f172a;">
                        <kbd style="padding:2px 6px; border:1px solid #e2e8f0; border-radius:6px; font-size:11px; color:#64748b;">ESC</kbd>
                    </div>
                    <div id="cmd-results" style="max-height:420px; overflow-y:auto; padding:8px 8px 12px;"></div>
                    <div style="padding:10px 14px; border-top:1px solid #f1f5f9; font-size:11px; color:#64748b; display:flex; gap:14px;">
                        <span><kbd>↑↓</kbd> navigate</span>
                        <span><kbd>↵</kbd> open</span>
                        <span><kbd>⌘K</kbd> toggle</span>
                    </div>
                </div>
            </div>
        `;

        document.body.insertAdjacentHTML('beforeend', html);
        this.overlay = document.getElementById('cmd-palette-overlay');
        this.input = document.getElementById('cmd-input');
        this.resultsContainer = document.getElementById('cmd-results');

        this.input.addEventListener('input', () => this.filter());
        this.overlay.addEventListener('click', (event) => {
            if (event.target === this.overlay) {
                this.close();
            }
        });
    },

    toggle() {
        if (this.isOpen) {
            this.close();
        } else {
            this.open();
        }
    },

    open() {
        this.isOpen = true;
        this.overlay.style.display = 'flex';
        this.input.value = '';
        this.selectedIndex = 0;
        this.filter();
        setTimeout(() => this.input.focus(), 0);
    },

    close() {
        this.isOpen = false;
        this.overlay.style.display = 'none';
    },

    filter() {
        const query = this.input.value.trim().toLowerCase();

        const scored = this.commands
            .map((command) => {
                const haystack = `${command.title} ${command.subtitle} ${command.category} ${command.keywords || ''}`.toLowerCase();
                if (!query) {
                    return { command, score: 0 };
                }
                const index = haystack.indexOf(query);
                return index === -1 ? null : { command, score: index };
            })
            .filter(Boolean)
            .sort((a, b) => a.score - b.score || a.command.title.localeCompare(b.command.title));

        this.filteredCommands = scored.map((item) => item.command);
        this.selectedIndex = Math.min(this.selectedIndex, Math.max(this.filteredCommands.length - 1, 0));
        this.renderResults();
    },

    moveSelection(step) {
        if (!this.filteredCommands.length) {
            return;
        }
        const length = this.filteredCommands.length;
        this.selectedIndex = (this.selectedIndex + step + length) % length;
        this.renderResults();
        const selected = this.resultsContainer.querySelector('[data-selected="true"]');
        if (selected) {
            selected.scrollIntoView({ block: 'nearest' });
        }
    },

    executeSelected() {
        const command = this.filteredCommands[this.selectedIndex];
        if (!command) {
            return;
        }
        this.runCommand(command);
    },

    runCommand(command) {
        this.close();
        if (typeof command.action === 'function') {
            command.action();
            return;
        }
        if (command.path) {
            window.location.href = command.path;
        }
    },

    renderResults() {
        if (!this.filteredCommands.length) {
            this.resultsContainer.innerHTML = '<div style="padding:16px; color:#64748b; font-size:13px;">No matching commands.</div>';
            return;
        }

        const groups = {};
        this.filteredCommands.forEach((command, index) => {
            if (!groups[command.category]) {
                groups[command.category] = [];
            }
            groups[command.category].push({ command, index });
        });

        const sections = Object.entries(groups)
            .map(([category, entries]) => {
                const items = entries.map(({ command, index }) => {
                    const selected = index === this.selectedIndex;
                    return `
                        <button type="button" data-index="${index}" data-selected="${selected ? 'true' : 'false'}" style="width:100%; text-align:left; border:none; background:${selected ? '#f8fafc' : 'transparent'}; border-radius:10px; padding:10px 12px; display:flex; gap:10px; align-items:flex-start; cursor:pointer;">
                            <div style="min-width:8px; height:8px; border-radius:999px; margin-top:6px; background:${selected ? '#0f172a' : '#cbd5e1'};"></div>
                            <div>
                                <div style="font-size:14px; font-weight:600; color:#0f172a;">${command.title}</div>
                                <div style="font-size:12px; color:#64748b;">${command.subtitle}</div>
                            </div>
                        </button>
                    `;
                }).join('');

                return `
                    <section style="padding:6px 6px 10px;">
                        <div style="padding:4px 8px 6px; font-size:11px; font-weight:700; color:#94a3b8; text-transform:uppercase; letter-spacing:0.04em;">${category}</div>
                        <div style="display:grid; gap:2px;">${items}</div>
                    </section>
                `;
            })
            .join('');

        this.resultsContainer.innerHTML = sections;
        this.resultsContainer.querySelectorAll('button[data-index]').forEach((button) => {
            button.addEventListener('mouseenter', () => {
                const index = Number(button.getAttribute('data-index'));
                this.selectedIndex = index;
                this.renderResults();
            });
            button.addEventListener('click', () => {
                const index = Number(button.getAttribute('data-index'));
                this.selectedIndex = index;
                this.executeSelected();
            });
        });
    }
};

document.addEventListener('DOMContentLoaded', () => CommandPalette.init());
