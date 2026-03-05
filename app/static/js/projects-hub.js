/**
 * KUKANILEA Projects Hub (Kanban) v2.1
 * Extracted for G3 Workflow Modernization
 */
(function() {
  // Use data attributes for initial state if available on the hub element
  const hub = document.getElementById("project-hub");
  if (!hub) return;

  const state = {
    boardId: hub.dataset.boardId,
    projectId: hub.dataset.projectId,
    columns: [],
    cards: [],
    activities: [],
    selectedCardId: null,
    draggedCardId: null,
  };

  const kanban = document.getElementById("kanban");
  const boardSwitch = document.getElementById("board-switch");
  const statusLine = document.getElementById("status-line");
  const activityList = document.getElementById("activity-list");
  const csrfToken = document.querySelector('meta[name="csrf-token"]')?.content || "";

  function closeDrawer() { 
    const drawer = document.getElementById('detail-drawer');
    if (drawer) {
        drawer.classList.add('translate-x-full');
        // If using the newer wf-drawer class
        drawer.classList.remove('open');
    }
  }
  
  function openDrawer() { 
    const drawer = document.getElementById('detail-drawer');
    if (drawer) {
        drawer.classList.remove('translate-x-full');
        // If using the newer wf-drawer class
        drawer.classList.add('open');
    }
  }

  function esc(v) { return String(v || "").replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;"); }
  function setStatus(m, e) { 
    if (!statusLine) return;
    statusLine.textContent = m; 
    statusLine.className = e ? "text-error" : "text-muted"; 
  }

  async function api(url, method="GET", payload=null) {
    const res = await fetch(url, {
      method, headers: payload ? {"Content-Type":"application/json", "X-CSRF-Token":csrfToken} : {"X-CSRF-Token":csrfToken},
      body: payload ? JSON.stringify(payload) : null, credentials: "same-origin"
    });
    const d = await res.json().catch(()=>({}));
    if (!res.ok || !d.ok) throw new Error(d.error || `Error ${res.status}`);
    return d;
  }

  function renderCards() {
    document.querySelectorAll(".cards, .kanban-card-list").forEach(el => {
      el.innerHTML = "";
      const colId = el.dataset.columnId;
      state.cards.filter(c => c.column_id === colId).sort((a,b)=>a.position-b.position).forEach(card => {
        const cEl = document.createElement("div");
        cEl.className = "card card-drag p-4 border-light shadow-sm hover:border-primary-300 mb-3";
        cEl.draggable = true;
        cEl.innerHTML = `<div class="font-bold text-sm mb-2">${esc(card.title)}</div>
          <div class="flex justify-between text-[10px] text-muted font-bold uppercase">
            <span>${esc(card.assignee || 'Unassigned')}</span>
            <span>${card.due_date ? esc(card.due_date) : ''}</span>
          </div>`;
        cEl.onclick = () => selectCard(card.id);
        cEl.ondragstart = () => { state.draggedCardId = card.id; cEl.classList.add("dragging"); };
        cEl.ondragend = () => { state.draggedCardId = null; cEl.classList.remove("dragging"); };
        el.appendChild(cEl);
      });
      const lane = el.closest(".lane, .kanban-column");
      const count = lane ? lane.querySelector("[data-count]") : null;
      if (count) count.textContent = el.children.length;
    });
  }

  async function selectCard(id) {
    state.selectedCardId = id;
    const c = state.cards.find(x => x.id === id);
    if(!c) return;
    const noSel = document.getElementById("no-selection");
    const sel = document.getElementById("selection");
    if (noSel) noSel.style.display = "none";
    if (sel) sel.style.display = "flex";
    
    const titleInp = document.getElementById("sel-title");
    const descInp = document.getElementById("sel-description");
    const dueInp = document.getElementById("sel-due");
    const assInp = document.getElementById("sel-assignee");
    
    if (titleInp) titleInp.value = c.title || "";
    if (descInp) descInp.value = c.description || "";
    if (dueInp) dueInp.value = c.due_date || "";
    if (assInp) assInp.value = c.assignee || "";
    
    renderActivity();
    openDrawer();
  }

  function renderActivity() {
    if (!activityList) return;
    activityList.innerHTML = state.activities.slice(0,10).map(a => 
      `<li class="p-2 bg-neutral-25 rounded border border-neutral-50 mb-2">
        <div class="font-bold text-primary-600">${esc(a.action)}</div>
        <div class="text-muted mt-0.5" style="font-size: 10px;">${esc(a.created_at)}</div>
      </li>`).join("") || "<li>Keine Aktivitäten.</li>";
  }

  async function refreshState() {
    try {
        const d = await api(`/api/projects/state?board_id=${state.boardId}`);
        state.columns = d.state.columns || [];
        state.cards = d.state.cards || [];
        state.activities = d.state.activities || [];
        renderCards();
    } catch (e) {
        console.error("Failed to refresh state", e);
    }
  }

  window.openDrawer = openDrawer;
  window.closeDrawer = closeDrawer;

  const topCreateBtn = document.getElementById("create-card-btn-top");
  if (topCreateBtn) {
    topCreateBtn.onclick = () => {
        const t = prompt("Titel der neuen Karte?");
        if(t) api("/api/projects/cards", "POST", {board_id: state.boardId, column_id: state.columns[0]?.id, title: t}).then(refreshState);
    };
  }

  const saveCardBtn = document.getElementById("save-card-btn");
  if (saveCardBtn) {
    saveCardBtn.onclick = () => {
        const c = state.cards.find(x => x.id === state.selectedCardId);
        if(!c) return;
        api(`/api/projects/cards/${c.id}`, "PATCH", {
            title: document.getElementById("sel-title").value,
            description: document.getElementById("sel-description").value,
            due_date: document.getElementById("sel-due").value,
            assignee: document.getElementById("sel-assignee").value
        }).then(refreshState).then(()=>setStatus("Gespeichert."));
    };
  }

  // Handle board switching
  if (boardSwitch) {
    boardSwitch.onchange = () => {
        const newBoardId = boardSwitch.value;
        window.location.href = `/projects?board_id=${newBoardId}`;
    };
  }

  // Initialize with global variables if they exist
  if (window._INITIAL_COLUMNS) state.columns = window._INITIAL_COLUMNS;
  if (window._INITIAL_CARDS) state.cards = window._INITIAL_CARDS;
  if (window._INITIAL_ACTIVITIES) state.activities = window._INITIAL_ACTIVITIES;
  
  renderCards();
})();
