/**
 * Accessible command palette for AI OS shell.
 */
const CommandPalette = {
  isOpen: false,
  selectedIndex: 0,
  filtered: [],
  commands: [
    { id: 'nav-dash', title: 'Übersicht', subtitle: 'Zur Startübersicht', keywords: 'dashboard home', href: '/dashboard' },
    { id: 'nav-upload', title: 'Hochladen', subtitle: 'Neue Dokumente verarbeiten', keywords: 'upload dokumente', href: '/upload' },
    { id: 'nav-email', title: 'E-Mails', subtitle: 'Postfach und Entwürfe', keywords: 'email postfach mail', href: '/email' },
    { id: 'nav-messenger', title: 'Nachrichten', subtitle: 'Teamkommunikation', keywords: 'chat messenger messages', href: '/messenger' },
    { id: 'nav-calendar', title: 'Kalender', subtitle: 'Termine und Erinnerungen', keywords: 'calendar termine', href: '/calendar' },
    { id: 'nav-tasks', title: 'Aufgaben', subtitle: 'To-Dos und Workflows', keywords: 'tasks todos', href: '/tasks' },
    { id: 'nav-time', title: 'Zeiterfassung', subtitle: 'Zeiten buchen und prüfen', keywords: 'time zeiterfassung', href: '/time' },
    { id: 'nav-projects', title: 'Projekte', subtitle: 'Projektstatus und Steuerung', keywords: 'projects kunden', href: '/projects' },
    { id: 'nav-visualizer', title: 'Analyseansicht', subtitle: 'Dokumente und Daten analysieren', keywords: 'visualizer analyse excel docs', href: '/visualizer' },
    { id: 'nav-settings', title: 'Einstellungen', subtitle: 'System konfigurieren', keywords: 'settings admin', href: '/settings' },
    { id: 'nav-assistant', title: 'KI Assistant', subtitle: 'Mit dem Assistenten arbeiten', keywords: 'assistant ai', href: '/assistant' },
  ],

  init() {
    this.render();
    this.bindEvents();
    this.filtered = this.commands.slice();
    this.renderResults();
  },

  render() {
    document.body.insertAdjacentHTML('beforeend', `
      <div id="cmd-palette-overlay" class="cmdk-overlay" aria-hidden="true">
        <section class="cmdk-modal" role="dialog" aria-modal="true" aria-label="Command Palette">
          <header class="cmdk-header">
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" aria-hidden="true"><circle cx="11" cy="11" r="8"></circle><path d="m21 21-4.3-4.3"></path></svg>
            <input id="cmd-input" class="cmdk-input" type="text" placeholder="Befehl, Seite oder Aktion…" aria-label="Command Palette Suche" autocomplete="off" />
            <kbd class="topbar-shortcut">ESC</kbd>
          </header>
          <div id="cmd-results" class="cmdk-list" role="listbox" aria-label="Suchergebnisse"></div>
          <footer class="cmdk-footer"><span>↑↓ Navigieren</span><span>↵ Ausführen</span><span>ESC schließen</span></footer>
        </section>
      </div>
    `);

    this.overlay = document.getElementById('cmd-palette-overlay');
    this.input = document.getElementById('cmd-input');
    this.resultsContainer = document.getElementById('cmd-results');
  },

  bindEvents() {
    window.addEventListener('keydown', (event) => {
      if ((event.ctrlKey || event.metaKey) && event.key.toLowerCase() === 'k') {
        event.preventDefault();
        this.toggle();
        return;
      }
      if (!this.isOpen) return;
      if (event.key === 'Escape') {
        event.preventDefault();
        this.close();
      } else if (event.key === 'ArrowDown') {
        event.preventDefault();
        this.move(1);
      } else if (event.key === 'ArrowUp') {
        event.preventDefault();
        this.move(-1);
      } else if (event.key === 'Enter') {
        event.preventDefault();
        this.execute(this.filtered[this.selectedIndex]);
      }
    });

    this.input.addEventListener('input', () => {
      this.filter(this.input.value);
    });

    this.overlay.addEventListener('click', (event) => {
      if (event.target === this.overlay) {
        this.close();
      }
    });

    document.getElementById('topbar-search-trigger')?.addEventListener('click', () => this.open());
  },

  filter(query = '') {
    const normalized = query.trim().toLowerCase();
    this.filtered = this.commands.filter((command) => {
      const haystack = `${command.title} ${command.subtitle} ${command.keywords || ''}`.toLowerCase();
      return haystack.includes(normalized);
    });
    this.selectedIndex = 0;
    this.renderResults();
  },

  renderResults() {
    if (!this.resultsContainer) return;
    if (!this.filtered.length) {
      this.resultsContainer.innerHTML = '<p class="cmdk-empty">Keine Treffer. Versuche einen anderen Begriff.</p>';
      return;
    }

    this.resultsContainer.innerHTML = this.filtered.map((command, index) => `
      <button type="button" class="cmdk-item" role="option" aria-selected="${index === this.selectedIndex ? 'true' : 'false'}" data-index="${index}">
        <span class="cmdk-item-icon" aria-hidden="true">⌘</span>
        <span>
          <span class="cmdk-item-title">${command.title}</span>
          <span class="cmdk-item-subtitle">${command.subtitle}</span>
        </span>
      </button>
    `).join('');

    this.resultsContainer.querySelectorAll('.cmdk-item').forEach((item) => {
      item.addEventListener('mouseenter', () => {
        this.selectedIndex = Number(item.dataset.index || 0);
        this.renderResults();
      });
      item.addEventListener('click', () => {
        const idx = Number(item.dataset.index || 0);
        this.execute(this.filtered[idx]);
      });
    });
  },

  execute(command) {
    if (!command) return;
    if (command.href) {
      window.location.href = command.href;
      return;
    }
    this.close();
  },

  move(direction) {
    if (!this.filtered.length) return;
    const length = this.filtered.length;
    this.selectedIndex = (this.selectedIndex + direction + length) % length;
    this.renderResults();
  },

  open() {
    this.isOpen = true;
    this.overlay.classList.add('is-open');
    this.overlay.setAttribute('aria-hidden', 'false');
    this.input.value = '';
    this.filter('');
    window.setTimeout(() => this.input.focus(), 0);
  },

  close() {
    this.isOpen = false;
    this.overlay.classList.remove('is-open');
    this.overlay.setAttribute('aria-hidden', 'true');
  },

  toggle() {
    if (this.isOpen) {
      this.close();
      return;
    }
    this.open();
  },
};

document.addEventListener('DOMContentLoaded', () => CommandPalette.init());
