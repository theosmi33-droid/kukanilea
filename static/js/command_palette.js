/**
 * Global command palette (Cmd/Ctrl+K) for fast task switching.
 */
const CommandPalette = {
  isOpen: false,
  selectedIndex: 0,
  commands: [
    { id: 'nav-dashboard', title: 'Dashboard', subtitle: 'Overview and operational metrics', action: () => { window.location.href = '/dashboard'; } },
    { id: 'nav-systems', title: 'Systems', subtitle: 'Infrastructure and system views', action: () => { window.location.href = '/visualizer'; } },
    { id: 'nav-agents', title: 'Agents', subtitle: 'Assistant and agent controls', action: () => { window.location.href = '/assistant'; } },
    { id: 'nav-files', title: 'Files', subtitle: 'Upload and file workflows', action: () => { window.location.href = '/upload'; } },
    { id: 'nav-automation', title: 'Automation', subtitle: 'Task and automation center', action: () => { window.location.href = '/tasks'; } },
    { id: 'nav-logs', title: 'Logs', subtitle: 'System logs and audit events', action: () => { window.location.href = '/system-logs'; } },
    { id: 'nav-settings', title: 'Settings', subtitle: 'System and profile configuration', action: () => { window.location.href = '/settings'; } },
  ],

  init() {
    this.render();
    window.addEventListener('keydown', (e) => {
      if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === 'k') {
        e.preventDefault();
        this.toggle();
      }
      if (e.key === 'Escape' && this.isOpen) {
        this.close();
      }
      if (!this.isOpen) return;
      if (e.key === 'ArrowDown') {
        e.preventDefault();
        this.moveSelection(1);
      }
      if (e.key === 'ArrowUp') {
        e.preventDefault();
        this.moveSelection(-1);
      }
      if (e.key === 'Enter') {
        e.preventDefault();
        this.activateSelection();
      }
    });

    document.querySelectorAll('[data-open-global-search]').forEach((btn) => {
      btn.addEventListener('click', () => this.open());
    });
  },

  render() {
    const html = `
      <div id="cmd-palette-overlay" style="display:none; position:fixed; inset:0; background:rgba(15, 23, 42, 0.4); backdrop-filter:blur(4px); z-index:9000; align-items:flex-start; justify-content:center; padding-top:12vh;">
        <div id="cmd-palette-modal" class="panel" style="width:100%; max-width:680px; padding:0; overflow:hidden; background:var(--bg-primary); border:1px solid var(--border-color); box-shadow:var(--shadow-lg);">
          <div style="padding:12px 14px; border-bottom:1px solid var(--border-color); display:flex; align-items:center; gap:10px;">
            <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="var(--text-tertiary)" stroke-width="2"><circle cx="11" cy="11" r="8"/><line x1="21" y1="21" x2="16.65" y2="16.65"/></svg>
            <input type="text" id="cmd-input" placeholder="Search pages and actions..." style="flex:1; background:none; border:none; color:var(--text-primary); font-size:15px; outline:none; font-family:var(--font-primary);">
            <kbd style="padding:2px 6px; background:var(--bg-secondary); border-radius:4px; font-size:10px; color:var(--text-tertiary); border:1px solid var(--border-color);">ESC</kbd>
          </div>
          <div id="cmd-results" style="max-height:420px; overflow-y:auto; padding:8px;"></div>
        </div>
      </div>`;
    document.body.insertAdjacentHTML('beforeend', html);
    this.overlay = document.getElementById('cmd-palette-overlay');
    this.input = document.getElementById('cmd-input');
    this.resultsContainer = document.getElementById('cmd-results');
    this.input.oninput = () => this.filter();
    this.overlay.onclick = (e) => { if (e.target === this.overlay) this.close(); };
  },

  toggle() { this.isOpen ? this.close() : this.open(); },

  open() {
    this.isOpen = true;
    this.overlay.style.display = 'flex';
    this.input.value = '';
    this.selectedIndex = 0;
    this.filter();
    setTimeout(() => this.input.focus(), 10);
  },

  close() {
    this.isOpen = false;
    this.overlay.style.display = 'none';
  },

  filter() {
    const query = this.input.value.toLowerCase();
    const filtered = this.commands.filter((c) => c.title.toLowerCase().includes(query) || c.subtitle.toLowerCase().includes(query));
    this.selectedIndex = 0;
    this.renderResults(filtered);
  },

  moveSelection(delta) {
    const items = this.resultsContainer.querySelectorAll('.cmd-item');
    if (!items.length) return;
    this.selectedIndex = (this.selectedIndex + delta + items.length) % items.length;
    this.paintSelection(items);
  },

  paintSelection(items) {
    items.forEach((item, idx) => {
      item.style.background = idx === this.selectedIndex ? 'var(--bg-secondary)' : 'transparent';
    });
  },

  activateSelection() {
    const item = this.resultsContainer.querySelector(`.cmd-item[data-index="${this.selectedIndex}"]`);
    item?.click();
  },

  renderResults(list) {
    this.resultsContainer.innerHTML = '';
    list.forEach((c, idx) => {
      const div = document.createElement('button');
      div.type = 'button';
      div.className = 'cmd-item';
      div.dataset.index = String(idx);
      div.style.cssText = 'width:100%; text-align:left; padding:12px 14px; border-radius:10px; border:none; background:transparent; cursor:pointer; display:flex; align-items:center; gap:12px;';
      div.innerHTML = `<span style="width:8px;height:8px;border-radius:999px;background:var(--color-primary);"></span><span style="flex:1;"><strong style="font-size:14px;color:var(--text-primary);">${c.title}</strong><br><span style="font-size:12px;color:var(--text-tertiary);">${c.subtitle}</span></span>`;
      div.onclick = () => { c.action(); this.close(); };
      div.onmouseenter = () => { this.selectedIndex = idx; this.paintSelection(this.resultsContainer.querySelectorAll('.cmd-item')); };
      this.resultsContainer.appendChild(div);
    });
    this.paintSelection(this.resultsContainer.querySelectorAll('.cmd-item'));
  }
};

document.addEventListener('DOMContentLoaded', () => CommandPalette.init());

window.CommandPalette = CommandPalette;
