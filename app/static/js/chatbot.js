(function () {
  "use strict";

  const STORAGE_KEY = "kukanilea_widget_state_v1";
  const MIN_SEND_INTERVAL_MS = 250;
  const MAX_RENDERED_MESSAGES = 80;

  const els = {
    root: document.getElementById("floating-chat-widget"),
    toggle: document.getElementById("floating-chat-toggle"),
    panel: document.getElementById("floating-chat-panel"),
    body: document.getElementById("floating-chat-body"),
    close: document.getElementById("floating-chat-close"),
    minimize: document.getElementById("floating-chat-minimize"),
    unread: document.getElementById("floating-chat-unread-badge"),
    status: document.getElementById("floating-chat-status"),
    contextTag: document.getElementById("floating-chat-context-tag"),
    quickActions: document.getElementById("floating-chat-quick-actions"),
    messages: document.getElementById("floating-chat-messages"),
    thinking: document.getElementById("floating-chat-thinking"),
    steps: document.getElementById("floating-chat-steps"),
    confirm: document.getElementById("floating-chat-confirm"),
    confirmText: document.getElementById("floating-chat-confirm-text"),
    confirmYes: document.getElementById("floating-chat-confirm-yes"),
    confirmNo: document.getElementById("floating-chat-confirm-no"),
    pendingQueue: document.getElementById("floating-chat-pending-queue"),
    form: document.getElementById("floating-chat-form"),
    input: document.getElementById("floating-chat-input"),
  };

  if (!els.root || !els.toggle || !els.panel || !els.form || !els.input) {
    return;
  }

  const routeContext = window.location.pathname || "/";
  const csrfToken =
    document.querySelector('meta[name="csrf-token"]')?.getAttribute("content") || "";
  const weakHardware =
    (typeof navigator.hardwareConcurrency === "number" && navigator.hardwareConcurrency <= 4) ||
    (typeof navigator.deviceMemory === "number" && navigator.deviceMemory <= 4);

  let lastSendAt = 0;
  let inFlight = false;
  let pendingConfirmId = "";
  let lastFocusedElement = null;

  const state = {
    open: false,
    minimized: false,
    unread: 0,
    width: 380,
    height: 540,
    historyLoaded: false,
  };

  function getQuickActions(pathname) {
    const actions = [
      { label: "Notiz erfassen", prompt: "quick capture note: " },
      { label: "Lead erfassen", prompt: "quick capture lead: " },
      { label: "Task vorschlagen", prompt: "quick capture task suggestion: " },
      { label: "Hilfe", prompt: "hilfe" },
      { label: "Suche Rechnung", prompt: "suche rechnung" },
    ];

    if (pathname.startsWith("/upload") || pathname.startsWith("/review")) {
      actions.unshift({ label: "Extrahiere Daten", prompt: "extrahiere daten aus aktuellem dokument" });
      actions.push({ label: "Letzte Uploads", prompt: "zeige letzte uploads" });
    }
    if (pathname.startsWith("/time") || pathname.startsWith("/zeiterfassung")) {
      actions.unshift({ label: "Zeit starten", prompt: "starte zeit für aktuelles projekt" });
      actions.push({ label: "Heutige Zeiten", prompt: "zeige heutige zeiteinträge" });
    }
    if (pathname.startsWith("/dashboard")) {
      actions.unshift({ label: "Tagesüberblick", prompt: "gib mir den dashboard überblick" });
    }
    return actions.slice(0, 6);
  }

  function loadState() {
    try {
      const raw = window.localStorage.getItem(STORAGE_KEY);
      if (!raw) return;
      const parsed = JSON.parse(raw);
      if (typeof parsed.open === "boolean") state.open = parsed.open;
      if (typeof parsed.minimized === "boolean") state.minimized = parsed.minimized;
      if (typeof parsed.unread === "number" && parsed.unread >= 0) state.unread = parsed.unread;
      if (typeof parsed.width === "number") state.width = Math.min(Math.max(parsed.width, 320), 680);
      if (typeof parsed.height === "number") state.height = Math.min(Math.max(parsed.height, 360), 820);
    } catch (_err) {}
  }

  function saveState() {
    try {
      window.localStorage.setItem(
        STORAGE_KEY,
        JSON.stringify({
          open: state.open,
          minimized: state.minimized,
          unread: state.unread,
          width: state.width,
          height: state.height,
        })
      );
    } catch (_err) {}
  }

  function setUnread(count) {
    state.unread = Math.max(0, count || 0);
    if (!els.unread) return;
    if (state.unread > 0) {
      els.unread.hidden = false;
      els.unread.textContent = String(Math.min(state.unread, 99));
    } else {
      els.unread.hidden = true;
      els.unread.textContent = "0";
    }
  }

  function bumpUnread() {
    setUnread(state.unread + 1);
    saveState();
  }

  function applySize() {
    els.panel.style.width = state.width + "px";
    els.panel.style.height = state.height + "px";
  }

  function setStatus(text) {
    if (els.status) els.status.textContent = text;
  }

  function renderSteps(steps) {
    if (!els.steps) return;
    els.steps.innerHTML = "";
    if (!Array.isArray(steps) || !steps.length) return;
    for (const step of steps) {
      const li = document.createElement("li");
      li.textContent = String(step || "");
      els.steps.appendChild(li);
    }
  }

  function setThinking(active) {
    if (els.thinking) {
      els.thinking.hidden = !active;
    }
  }

  function scrollMessages() {
    if (!els.messages) return;
    els.messages.scrollTop = els.messages.scrollHeight;
  }

  function trimMessages() {
    if (!els.messages) return;
    while (els.messages.children.length > MAX_RENDERED_MESSAGES) {
      els.messages.removeChild(els.messages.firstChild);
    }
  }

  function addMessage(kind, text, meta) {
    if (!els.messages || !text) return;
    const li = document.createElement("li");
    li.className = "floating-chat-msg floating-chat-msg-" + kind;

    const bubble = document.createElement("div");
    bubble.className = "floating-chat-bubble";
    bubble.textContent = String(text);
    li.appendChild(bubble);

    if (meta && meta.model) {
      const small = document.createElement("small");
      small.className = "floating-chat-meta";
      small.textContent = String(meta.model);
      li.appendChild(small);
    }

    els.messages.appendChild(li);
    trimMessages();
    scrollMessages();
  }

  function clearMessages() {
    if (els.messages) {
      els.messages.innerHTML = "";
    }
  }

  function setContextTag() {
    if (els.contextTag) {
      els.contextTag.textContent = "Kontext: " + routeContext;
    }
  }

  function hideConfirmGate() {
    pendingConfirmId = "";
    if (els.confirm) els.confirm.hidden = true;
    if (els.confirmText) els.confirmText.textContent = "";
  }

  function renderPendingQueue(items) {
    if (!els.pendingQueue) return;
    const queue = Array.isArray(items) ? items : [];
    els.pendingQueue.innerHTML = "";
    if (!queue.length) {
      els.pendingQueue.hidden = true;
      return;
    }

    const title = document.createElement("p");
    title.className = "floating-chat-pending-title";
    title.textContent = "Pending approvals (" + queue.length + ")";
    els.pendingQueue.appendChild(title);

    const list = document.createElement("ul");
    for (const item of queue) {
      const li = document.createElement("li");
      const pid = String(item.pending_id || "");
      const prompt = String(item.confirm_prompt || "Bestätigung erforderlich.");
      const count = Number(item.action_count || 0);
      li.textContent = (count > 0 ? count + " Aktion(en): " : "") + prompt;
      li.dataset.pendingId = pid;
      list.appendChild(li);
    }
    els.pendingQueue.appendChild(list);
    els.pendingQueue.hidden = false;
  }

  function showConfirmGate(confirmText, pendingId, actions) {
    pendingConfirmId = String(pendingId || "");
    if (!els.confirm || !pendingConfirmId) return;
    const labels = Array.isArray(actions)
      ? actions.map((a) => a.label || a.type || "Aktion").join(", ")
      : "Aktion";
    els.confirm.hidden = false;
    if (els.confirmText) {
      els.confirmText.textContent = confirmText ||
        "Bestätigung erforderlich für: " + labels;
    }
  }

  async function loadPendingQueue() {
    try {
      const response = await fetch("/api/chat/compact?pending=1", {
        method: "GET",
        headers: {
          "X-CSRF-Token": csrfToken,
        },
      });
      if (!response.ok) return;
      const data = await response.json();
      renderPendingQueue(data.pending_approvals || []);
    } catch (_err) {
      renderPendingQueue([]);
    }
  }

  function setPanelState(open, minimized) {
    state.open = !!open;
    state.minimized = !!minimized;

    els.panel.hidden = !state.open;
    els.toggle.setAttribute("aria-expanded", state.open ? "true" : "false");

    if (state.open) {
      els.panel.classList.toggle("is-minimized", state.minimized);
      if (state.minimized) {
        if (els.body) els.body.hidden = true;
        if (els.form) els.form.hidden = true;
        if (els.confirm) els.confirm.hidden = true;
      } else {
        if (els.body) els.body.hidden = false;
        if (els.form) els.form.hidden = false;
      }
    }

    if (state.open && !state.minimized) {
      setUnread(0);
      if (els.input) {
        window.setTimeout(() => els.input.focus(), 0);
      }
    }

    saveState();
  }

  function openPanel() {
    if (!state.open) {
      lastFocusedElement = document.activeElement;
    }
    setPanelState(true, false);
    if (!state.historyLoaded) {
      loadHistory();
    }
  }

  function closePanel() {
    setPanelState(false, false);
    hideConfirmGate();
    if (lastFocusedElement && typeof lastFocusedElement.focus === "function") {
      lastFocusedElement.focus();
    }
  }

  function minimizePanel() {
    if (!state.open) {
      openPanel();
      return;
    }
    setPanelState(true, !state.minimized);
  }

  function renderQuickActions() {
    if (!els.quickActions) return;
    els.quickActions.innerHTML = "";
    const actions = getQuickActions(routeContext);
    for (const action of actions) {
      const btn = document.createElement("button");
      btn.type = "button";
      btn.className = "floating-chat-quick-action btn btn-secondary btn-sm";
      btn.textContent = action.label;
      btn.dataset.prompt = action.prompt;
      els.quickActions.appendChild(btn);
    }
  }

  async function loadHistory() {
    try {
      const response = await fetch("/api/chat/compact?history=1&limit=30", {
        method: "GET",
        credentials: "same-origin",
        headers: csrfToken ? { "X-CSRF-Token": csrfToken } : {},
      });
      if (!response.ok) return;
      const data = await response.json();
      clearMessages();
      const items = Array.isArray(data.messages) ? data.messages : [];
      for (const item of items) {
        const direction = item.direction === "in" ? "user" : "assistant";
        addMessage(direction, item.message || "", { model: item.model || "" });
      }
      state.historyLoaded = true;
      if (!items.length) {
        addMessage("assistant", "Guten Tag. Ich bin auf dieser Seite kontextbewusst verfügbar.");
      }
    } catch (_err) {
      addMessage("assistant", "Verlauf konnte nicht geladen werden.");
    }
  }

  function buildHeaders() {
    const headers = { "Content-Type": "application/json" };
    if (csrfToken) {
      headers["X-CSRF-Token"] = csrfToken;
    }
    return headers;
  }

  async function ask(message, options) {
    const now = Date.now();
    if (!options?.isConfirm && now - lastSendAt < MIN_SEND_INTERVAL_MS) {
      return;
    }
    if (inFlight) return;

    const prompt = String(message || "").trim();
    if (!prompt && !options?.isConfirm) return;

    lastSendAt = now;
    inFlight = true;
    setThinking(true);
    setStatus("Agent denkt...");
    renderSteps([]);

    if (!options?.isConfirm) {
      addMessage("user", prompt);
    }

    try {
      const payload = {
        message: prompt,
        current_context: routeContext,
        weak_hw: weakHardware,
        offline: !navigator.onLine,
      };
      if (options?.isConfirm) {
        payload.confirm = true;
        payload.pending_id = options.pendingId || pendingConfirmId;
      }

      const response = await fetch("/api/chat/compact", {
        method: "POST",
        credentials: "same-origin",
        headers: buildHeaders(),
        body: JSON.stringify(payload),
      });

      const data = await response.json().catch(function () {
        return { ok: false, text: "Ungültige Serverantwort." };
      });

      if (!response.ok || data.ok === false) {
        throw new Error(data.text || data.error || "Anfrage fehlgeschlagen.");
      }

      if (Array.isArray(data.thinking_steps)) {
        renderSteps(data.thinking_steps);
      }

      if (data.text) {
        addMessage("assistant", data.text, { model: data.model });
      }

      if (data.requires_confirm) {
        showConfirmGate(data.confirm_prompt, data.pending_id, data.actions || []);
      } else {
        hideConfirmGate();
      }

      renderPendingQueue(data.pending_approvals);

      setStatus(data.status || "Bereit");

      if (!state.open || state.minimized) {
        bumpUnread();
      }
    } catch (err) {
      addMessage("assistant", err.message || "Die Anfrage konnte nicht verarbeitet werden.");
      setStatus("Fehler");
      if (!state.open || state.minimized) {
        bumpUnread();
      }
    } finally {
      setThinking(false);
      inFlight = false;
      saveState();
      scrollMessages();
    }
  }

  function attachEvents() {
    els.toggle.addEventListener("click", function () {
      if (state.open && !state.minimized) {
        closePanel();
      } else {
        openPanel();
      }
    });

    if (els.close) {
      els.close.addEventListener("click", closePanel);
    }

    if (els.minimize) {
      els.minimize.addEventListener("click", minimizePanel);
    }

    els.form.addEventListener("submit", function (event) {
      event.preventDefault();
      const text = els.input.value.trim();
      if (!text) return;
      els.input.value = "";
      ask(text, { isConfirm: false });
    });

    if (els.quickActions) {
      els.quickActions.addEventListener("click", function (event) {
        const btn = event.target.closest("button[data-prompt]");
        if (!btn) return;
        openPanel();
        ask(btn.dataset.prompt || "", { isConfirm: false });
      });
    }

    if (els.confirmYes) {
      els.confirmYes.addEventListener("click", function () {
        ask("bestätigen", { isConfirm: true, pendingId: pendingConfirmId });
      });
    }

    if (els.confirmNo) {
      els.confirmNo.addEventListener("click", function () {
        hideConfirmGate();
        addMessage("assistant", "Aktion wurde abgebrochen.");
      });
    }

    if (els.pendingQueue) {
      els.pendingQueue.addEventListener("click", function (event) {
        const row = event.target.closest("li[data-pending-id]");
        if (!row) return;
        pendingConfirmId = row.dataset.pendingId || "";
        if (pendingConfirmId) {
          showConfirmGate("Bestätigung für ausstehende Aktion erforderlich.", pendingConfirmId, []);
        }
      });
    }

    document.addEventListener("keydown", function (event) {
      if (event.key === "Escape" && state.open) {
        closePanel();
      }
    });

    els.panel.addEventListener("mouseup", function () {
      const rect = els.panel.getBoundingClientRect();
      const width = Math.round(rect.width);
      const height = Math.round(rect.height);
      if (width >= 320 && height >= 360) {
        state.width = Math.min(width, 680);
        state.height = Math.min(height, 820);
        saveState();
      }
    });
  }

  function boot() {
    loadState();
    setContextTag();
    renderQuickActions();
    loadPendingQueue();
    setUnread(state.unread);

    applySize();
    els.root.hidden = false;
    if (weakHardware) {
      els.root.classList.add("is-weak-hw");
    }

    attachEvents();

    if (state.open) {
      setPanelState(true, state.minimized);
      loadHistory();
    }
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", boot, { once: true });
  } else {
    boot();
  }
})();
