(function initTasksPerformance() {
  if (window.__tasksPerfInitialized) return;
  window.__tasksPerfInitialized = true;

  const root = document.getElementById('tasks-virtualized');
  if (!root) return;

  const sourceNode = document.getElementById('tasks-data-json');
  const body = document.getElementById('tasks-table-body');
  const viewport = document.getElementById('tasks-table-viewport');
  const searchInput = document.getElementById('tasks-search-input');
  const countNode = document.getElementById('tasks-search-count');

  if (!sourceNode || !body || !viewport || !searchInput || !countNode) return;

  let parsed = [];
  try {
    parsed = JSON.parse(sourceNode.textContent || '[]');
  } catch (_err) {
    parsed = [];
  }

  const rows = Array.isArray(parsed) ? parsed : [];
  const textCache = new Map();
  const filterCache = new Map();

  const state = {
    filteredIndexes: rows.map((_, idx) => idx),
    rowHeight: 66,
    overscan: 8,
  };

  const safe = (value, fallback = '-') => {
    if (value === null || value === undefined || value === '') return fallback;
    return String(value);
  };

  const escapeHtml = (value) => String(value).replace(/[&<>"']/g, (char) => {
    const map = {
      '&': '&amp;',
      '<': '&lt;',
      '>': '&gt;',
      '"': '&quot;',
      "'": '&#39;',
    };
    return map[char] || char;
  });

  const memoizedTaskText = (idx) => {
    if (textCache.has(idx)) return textCache.get(idx);
    const task = rows[idx] || {};
    const composite = [
      safe(task.title, ''),
      safe(task.description, ''),
      safe(task.status, ''),
      safe(task.column_name, ''),
      safe(task.assigned_to || task.assigned_user, ''),
      safe(task.due_at || task.due_date, ''),
    ].join(' ').toLowerCase();
    textCache.set(idx, composite);
    return composite;
  };

  const getFilteredIndexes = (query) => {
    const key = query.trim().toLowerCase();
    if (filterCache.has(key)) return filterCache.get(key);
    if (!key) {
      const all = rows.map((_, idx) => idx);
      filterCache.set(key, all);
      return all;
    }
    const filtered = [];
    for (let i = 0; i < rows.length; i += 1) {
      if (memoizedTaskText(i).includes(key)) filtered.push(i);
    }
    filterCache.set(key, filtered);
    return filtered;
  };

  const renderWindow = () => {
    const total = state.filteredIndexes.length;
    if (!total) {
      body.innerHTML = '<tr><td colspan="5" class="tasks-empty">Keine Treffer für die aktuelle Suche.</td></tr>';
      countNode.textContent = '0 Ergebnisse';
      return;
    }

    const viewportHeight = viewport.clientHeight || 480;
    const visibleCount = Math.ceil(viewportHeight / state.rowHeight) + state.overscan;
    const start = Math.max(0, Math.floor(viewport.scrollTop / state.rowHeight) - Math.floor(state.overscan / 2));
    const end = Math.min(total, start + visibleCount);

    const topSpacer = start * state.rowHeight;
    const bottomSpacer = Math.max(0, (total - end) * state.rowHeight);

    const fragment = document.createDocumentFragment();

    if (topSpacer > 0) {
      const spacerTop = document.createElement('tr');
      spacerTop.className = 'tasks-spacer';
      spacerTop.innerHTML = `<td colspan="5" style="height:${topSpacer}px"></td>`;
      fragment.appendChild(spacerTop);
    }

    for (let i = start; i < end; i += 1) {
      const taskIdx = state.filteredIndexes[i];
      const task = rows[taskIdx] || {};

      const tr = document.createElement('tr');
      tr.innerHTML = `
        <td>
          <strong>${escapeHtml(safe(task.title, 'Ohne Titel'))}</strong>
          ${task.description ? `<div class="tasks-muted">${escapeHtml(safe(task.description, ''))}</div>` : ''}
        </td>
        <td><span class="tasks-badge">${escapeHtml(safe(task.status, '-'))}</span></td>
        <td>${escapeHtml(safe(task.column_name, '-'))}</td>
        <td>${escapeHtml(safe(task.assigned_to || task.assigned_user, '-'))}</td>
        <td>${escapeHtml(safe(task.due_at || task.due_date, '-'))}</td>
      `;
      fragment.appendChild(tr);
    }

    if (bottomSpacer > 0) {
      const spacerBottom = document.createElement('tr');
      spacerBottom.className = 'tasks-spacer';
      spacerBottom.innerHTML = `<td colspan="5" style="height:${bottomSpacer}px"></td>`;
      fragment.appendChild(spacerBottom);
    }

    body.replaceChildren(fragment);
    countNode.textContent = `${total} Ergebnis${total === 1 ? '' : 'se'}`;
  };

  const debounce = (fn, delayMs) => {
    let timer = null;
    return (...args) => {
      if (timer) window.clearTimeout(timer);
      timer = window.setTimeout(() => fn(...args), delayMs);
    };
  };

  const applySearch = debounce(() => {
    state.filteredIndexes = getFilteredIndexes(searchInput.value || '');
    viewport.scrollTop = 0;
    renderWindow();
  }, 180);

  viewport.addEventListener('scroll', () => {
    window.requestAnimationFrame(renderWindow);
  }, { passive: true });

  window.addEventListener('resize', debounce(renderWindow, 120), { passive: true });
  searchInput.addEventListener('input', applySearch, { passive: true });

  renderWindow();
})();
