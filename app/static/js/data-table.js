(function () {
  function textContent(el) {
    return (el?.textContent || '').replace(/\s+/g, ' ').trim();
  }

  function buildSummary(table, rows) {
    const host = document.createElement('div');
    host.className = 'data-table-cards';

    const total = rows.length;
    const selected = rows.filter((row) => row.classList.contains('is-selected')).length;
    const errorCount = rows.filter((row) => /\b(error|failed|kritisch|down)\b/i.test(textContent(row))).length;
    const headers = Array.from(table.querySelectorAll('thead th')).map((th) => textContent(th).toLowerCase());
    const agentIdx = headers.findIndex((h) => /agent|owner|user|verantwortlich|assignee/.test(h));
    const activeAgents = agentIdx >= 0
      ? new Set(rows.map((r) => textContent(r.cells[agentIdx + 1] || r.cells[agentIdx])).filter(Boolean)).size
      : selected;

    const cards = [
      { title: 'System Status', metric: errorCount ? 'Attention' : 'Healthy', delta: errorCount ? `${errorCount} alerts` : 'No blocking alerts', desc: 'Live quality signal from table content' },
      { title: 'Active Agents', metric: activeAgents, delta: `${selected} rows selected`, desc: 'Distinct ownership or active row selection' },
      { title: 'Errors', metric: errorCount, delta: errorCount ? 'Needs review' : 'Stable trend', desc: 'Rows containing critical markers' },
      { title: 'Tasks Processed', metric: total, delta: `${Math.max(total - selected, 0)} unselected`, desc: 'Total rows currently visible' },
    ];

    host.innerHTML = cards.map((card) => `
      <article class="data-metric-card">
        <p class="data-metric-title">${card.title}</p>
        <p class="data-metric-value">${card.metric}</p>
        <p class="data-metric-delta">${card.delta}</p>
        <p class="data-metric-desc">${card.desc}</p>
      </article>
    `).join('');

    return host;
  }

  function sortTable(table, colIdx, direction) {
    const tbody = table.tBodies[0];
    const rows = Array.from(tbody.rows);
    const factor = direction === 'asc' ? 1 : -1;
    rows.sort((a, b) => {
      const av = textContent(a.cells[colIdx]);
      const bv = textContent(b.cells[colIdx]);
      const an = Number(av.replace(',', '.'));
      const bn = Number(bv.replace(',', '.'));
      if (!Number.isNaN(an) && !Number.isNaN(bn)) return (an - bn) * factor;
      return av.localeCompare(bv, undefined, { numeric: true, sensitivity: 'base' }) * factor;
    });
    rows.forEach((r) => tbody.appendChild(r));
  }

  function setupColumnResize(th) {
    const handle = document.createElement('span');
    handle.className = 'resize-handle';
    th.appendChild(handle);
    let startX = 0;
    let startW = 0;

    const onMove = (ev) => {
      const width = Math.max(80, startW + (ev.clientX - startX));
      th.style.width = `${width}px`;
      th.style.minWidth = `${width}px`;
    };

    handle.addEventListener('mousedown', (ev) => {
      ev.stopPropagation();
      startX = ev.clientX;
      startW = th.getBoundingClientRect().width;
      document.addEventListener('mousemove', onMove);
      document.addEventListener('mouseup', () => document.removeEventListener('mousemove', onMove), { once: true });
    });
  }

  function enhanceTable(table) {
    if (table.dataset.enhanced === '1') return;
    table.dataset.enhanced = '1';
    table.classList.add('js-data-table');
    if (!table.tHead || !table.tBodies[0]) return;

    const wrapper = table.parentElement;
    wrapper.classList.add('data-table-wrapper');
    const shell = document.createElement('section');
    shell.className = 'data-table-shell';
    wrapper.parentNode.insertBefore(shell, wrapper);

    const rows = Array.from(table.tBodies[0].rows);
    const summaryHost = document.createElement('div');
    shell.appendChild(summaryHost);
    function refreshSummary() {
      summaryHost.innerHTML = "";
      summaryHost.appendChild(buildSummary(table, Array.from(table.tBodies[0].rows)));
    }
    refreshSummary();

    const toolbar = document.createElement('div');
    toolbar.className = 'data-table-toolbar';
    toolbar.innerHTML = '<input class="data-table-search" type="search" placeholder="Search in table…" aria-label="Search in table"><div class="data-table-filters" role="group" aria-label="Quick filters"></div>';
    shell.appendChild(toolbar);
    shell.appendChild(wrapper);

    const search = toolbar.querySelector('.data-table-search');
    const chips = toolbar.querySelector('.data-table-filters');

    const headerRow = table.tHead.rows[0];
    const selectTh = document.createElement('th');
    selectTh.className = 'col-select';
    selectTh.innerHTML = '<input type="checkbox" aria-label="Select all rows">';
    headerRow.insertBefore(selectTh, headerRow.firstElementChild);

    rows.forEach((row) => {
      const td = document.createElement('td');
      td.className = 'col-select-cell';
      td.innerHTML = '<input type="checkbox" aria-label="Select row">';
      row.insertBefore(td, row.firstElementChild);
      td.querySelector('input').addEventListener('change', (ev) => {
        row.classList.toggle('is-selected', ev.target.checked);
        refreshSummary();
      });
    });

    selectTh.querySelector('input').addEventListener('change', (ev) => {
      const checked = ev.target.checked;
      table.tBodies[0].querySelectorAll('.col-select-cell input').forEach((cb) => {
        cb.checked = checked;
        cb.dispatchEvent(new Event('change'));
      });
    });

    Array.from(headerRow.cells).forEach((th, idx) => {
      if (idx === 0) return;
      th.classList.add('sortable-header');
      th.dataset.sort = '';
      setupColumnResize(th);
      th.addEventListener('click', () => {
        const current = th.dataset.sort === 'asc' ? 'desc' : 'asc';
        Array.from(headerRow.cells).forEach((h) => {
          h.dataset.sort = '';
          h.classList.remove('sort-asc', 'sort-desc');
        });
        th.dataset.sort = current;
        th.classList.add(current === 'asc' ? 'sort-asc' : 'sort-desc');
        sortTable(table, idx, current);
      });
    });

    const candidateIndex = Math.max(1, Array.from(headerRow.cells).findIndex((h) => /status|typ|rolle|enabled|integrit/i.test(textContent(h))));
    const values = Array.from(new Set(rows.map((r) => textContent(r.cells[candidateIndex])).filter(Boolean))).slice(0, 6);
    const allChip = document.createElement('button');
    allChip.className = 'data-filter-chip active';
    allChip.textContent = 'All';
    chips.appendChild(allChip);

    function applyFilter(value) {
      Array.from(table.tBodies[0].rows).forEach((row) => {
        const text = textContent(row);
        const searchOk = !search.value || text.toLowerCase().includes(search.value.toLowerCase());
        const quickOk = !value || textContent(row.cells[candidateIndex]) === value;
        row.style.display = searchOk && quickOk ? '' : 'none';
      });
    }

    let activeQuick = '';
    allChip.addEventListener('click', () => {
      activeQuick = '';
      chips.querySelectorAll('.data-filter-chip').forEach((c) => c.classList.remove('active'));
      allChip.classList.add('active');
      applyFilter(activeQuick);
    });

    values.forEach((value) => {
      const chip = document.createElement('button');
      chip.className = 'data-filter-chip';
      chip.textContent = value;
      chip.addEventListener('click', () => {
        activeQuick = value;
        chips.querySelectorAll('.data-filter-chip').forEach((c) => c.classList.remove('active'));
        chip.classList.add('active');
        applyFilter(activeQuick);
      });
      chips.appendChild(chip);
    });

    search.addEventListener('input', () => applyFilter(activeQuick));
  }

  function init() {
    document.querySelectorAll('table').forEach(enhanceTable);
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
  } else {
    init();
  }
})();
