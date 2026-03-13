let lastChatTrigger = null;
let chatPendingId = '';

window.addEventListener('DOMContentLoaded', () => {
  const bar = document.getElementById('boot-bar');
  const splash = document.getElementById('boot-splash');
  if (bar) bar.style.width = '100%';
  const prefersReducedMotion = window.matchMedia('(prefers-reduced-motion: reduce)').matches;
  if (prefersReducedMotion) {
    if (splash) splash.classList.add('fade-out');
    return;
  }
  setTimeout(() => {
    if (splash) splash.classList.add('fade-out');
  }, 600);
}, { once: true });

document.addEventListener('DOMContentLoaded', () => {
  const SIDEBAR_MOBILE_MAX = 768;
  const SIDEBAR_AUTO_COLLAPSE_MAX = 1366;
  const sidebarToggle = document.getElementById('sidebar-toggle');
  const sidebarToggleTop = document.getElementById('sidebar-toggle-top');
  const sidebarToggles = [sidebarToggle, sidebarToggleTop].filter(Boolean);

  const isMobileViewport = () => window.matchMedia(`(max-width: ${SIDEBAR_MOBILE_MAX}px)`).matches;
  const isAutoCollapseViewport = () => (
    !isMobileViewport() && window.matchMedia(`(max-width: ${SIDEBAR_AUTO_COLLAPSE_MAX}px)`).matches
  );

  const applySidebarCollapsed = (collapsed, { persist = true } = {}) => {
    document.documentElement.classList.toggle('sidebar-collapsed', collapsed);
    if (persist) {
      try { localStorage.setItem('ks_sidebar_collapsed', collapsed ? '1' : '0'); } catch (_err) {}
    }
  };

  const updateSidebarLabel = () => {
    const collapsed = document.documentElement.classList.contains('sidebar-collapsed');
    sidebarToggles.forEach((toggle) => {
      toggle.setAttribute('aria-expanded', !collapsed);
      toggle.setAttribute('aria-label', collapsed ? 'Reiter aufklappen' : 'Reiter minimieren');
      toggle.title = collapsed ? 'Reiter aufklappen' : 'Reiter minimieren';
    });
  };

  const syncSidebarToViewport = () => {
    if (isMobileViewport()) {
      applySidebarCollapsed(false, { persist: false });
      updateSidebarLabel();
      return;
    }
    if (isAutoCollapseViewport()) {
      applySidebarCollapsed(true);
      updateSidebarLabel();
      return;
    }
    // Wide viewports default to expanded sidebar.
    applySidebarCollapsed(false);
    updateSidebarLabel();
  };

  if (sidebarToggles.length) {
    const toggleSidebar = () => {
      if (isAutoCollapseViewport()) return;
      const collapsed = !document.documentElement.classList.contains('sidebar-collapsed');
      applySidebarCollapsed(collapsed);
      updateSidebarLabel();
    };
    sidebarToggles.forEach((toggle) => {
      toggle.addEventListener('click', toggleSidebar);
    });
  }

  let sidebarResizeRaf = 0;
  window.addEventListener('resize', () => {
    if (sidebarResizeRaf) window.cancelAnimationFrame(sidebarResizeRaf);
    sidebarResizeRaf = window.requestAnimationFrame(() => {
      syncSidebarToViewport();
      sidebarResizeRaf = 0;
    });
  }, { passive: true });

  const mobileToggle = document.getElementById('mobile-sidebar-toggle');
  const sidebar = document.querySelector('.sidebar');
  const setMobileSidebarState = (isOpen) => {
    if (!sidebar || !mobileToggle) return;
    sidebar.classList.toggle('mobile-open', isOpen);
    mobileToggle.setAttribute('aria-expanded', isOpen ? 'true' : 'false');
    mobileToggle.setAttribute('aria-label', isOpen ? 'Menü schließen' : 'Menü öffnen');
  };
  if (mobileToggle && sidebar) {
    mobileToggle.addEventListener('click', () => {
      const nextState = !sidebar.classList.contains('mobile-open');
      setMobileSidebarState(nextState);
    });
    document.addEventListener('click', (e) => {
      if (sidebar.classList.contains('mobile-open') && !sidebar.contains(e.target) && !mobileToggle.contains(e.target)) {
        setMobileSidebarState(false);
      }
    }, { passive: true });
  }

  const updateActiveRoutes = () => {
    const current = window.location.pathname;

    document.querySelectorAll('.nav-link[data-route]').forEach((a) => {
      const route = a.getAttribute('data-route') || '';
      const active = route === '/dashboard' ? (current === '/' || current === '/dashboard') : current.startsWith(route);
      a.classList.toggle('active', active);
      a.setAttribute('aria-current', active ? 'page' : 'false');
    });

    document.querySelectorAll('.mobile-nav-item[data-route]').forEach((a) => {
      const route = a.getAttribute('data-route') || '';
      const active = route === '/dashboard' ? (current === '/' || current === '/dashboard') : current.startsWith(route);
      a.classList.toggle('active', active);
      a.setAttribute('aria-current', active ? 'page' : 'false');
    });
  };

  const initializeUi = () => {
    const topbarClock = document.getElementById('topbar-clock');
    const topbarOnline = document.getElementById('topbar-online-count');
    const topbarRunning = document.getElementById('topbar-running-timer');
    const topbarTimeHide = document.getElementById('topbar-time-hide');
    const topbarTimeShowIcon = topbarTimeHide?.querySelector('.topbar-time-icon-show');
    const topbarTimeHideIcon = topbarTimeHide?.querySelector('.topbar-time-icon-hide');
    let topbarTimerHidden = false;
    let topbarRunningAnchorMs = null;
    let topbarRunningState = 0;

    const fmtHms = (totalSeconds) => {
      const sec = Math.max(0, Number(totalSeconds) || 0);
      const h = Math.floor(sec / 3600);
      const m = Math.floor((sec % 3600) / 60);
      const s = sec % 60;
      return [h, m, s].map((v) => String(v).padStart(2, '0')).join(':');
    };
    const updateTopbarClock = () => {
      if (!topbarClock) return;
      const next = new Date().toLocaleTimeString('de-DE', {
        hour: '2-digit',
        minute: '2-digit',
        second: '2-digit',
      });
      if (topbarClock.textContent !== next) topbarClock.textContent = next;
    };

    const renderTopbarOnline = () => {
      if (!topbarOnline) return;
      topbarOnline.textContent = navigator.onLine ? '1' : '0';
    };

    const renderTopbarRunning = () => {
      if (!topbarRunning) return;
      const seconds = topbarRunningState > 0 && topbarRunningAnchorMs
        ? Math.floor((Date.now() - topbarRunningAnchorMs) / 1000)
        : 0;
      const next = topbarTimerHidden ? '••:••:••' : fmtHms(seconds);
      if (topbarRunning.textContent !== next) topbarRunning.textContent = next;
    };

    const applyTopbarTimeToggle = () => {
      if (!topbarTimeHide) return;
      topbarTimeHide.setAttribute('aria-label', topbarTimerHidden ? 'Zeit einblenden' : 'Zeit ausblenden');
      topbarTimeHide.title = topbarTimerHidden ? 'Zeit einblenden' : 'Zeit ausblenden';
      if (topbarTimeShowIcon) topbarTimeShowIcon.hidden = topbarTimerHidden;
      if (topbarTimeHideIcon) topbarTimeHideIcon.hidden = !topbarTimerHidden;
      renderTopbarRunning();
    };

    const refreshTopbarTimeState = async () => {
      if (!topbarRunning) return;
      try {
        const res = await fetch('/api/time/summary', { credentials: 'same-origin' });
        if (!res.ok) return;
        const payload = await res.json();
        const running = Number(payload?.metrics?.running || 0);
        if (running > 0 && !topbarRunningAnchorMs) topbarRunningAnchorMs = Date.now();
        if (running <= 0) topbarRunningAnchorMs = null;
        topbarRunningState = running > 0 ? 1 : 0;
        renderTopbarRunning();
      } catch (_err) {
        // Keep last known topbar state; do not disrupt shell.
      }
    };

    try {
      topbarTimerHidden = localStorage.getItem('kuka_topbar_time_hidden') === '1';
    } catch (_err) {
      topbarTimerHidden = false;
    };

    updateTopbarClock();
    renderTopbarOnline();
    applyTopbarTimeToggle();
    refreshTopbarTimeState();
    window.setInterval(updateTopbarClock, 1000);
    window.setInterval(renderTopbarRunning, 1000);
    window.setInterval(refreshTopbarTimeState, 30000);
    window.addEventListener('online', renderTopbarOnline);
    window.addEventListener('offline', renderTopbarOnline);
    if (topbarTimeHide) {
      topbarTimeHide.addEventListener('click', () => {
        topbarTimerHidden = !topbarTimerHidden;
        try { localStorage.setItem('kuka_topbar_time_hidden', topbarTimerHidden ? '1' : '0'); } catch (_err) {}
        applyTopbarTimeToggle();
      });
    }

    syncSidebarToViewport();
    updateActiveRoutes();
    const chatToggle = document.getElementById('ki-chat-toggle');
    if (chatToggle) {
      chatToggle.addEventListener('click', () => toggleChat());
    }
    const chatClose = document.getElementById('ki-chat-close');
    if (chatClose) {
      chatClose.addEventListener('click', () => toggleChat(false));
    }
    const chatForm = document.querySelector('.ki-chat-composer');
    if (chatForm) {
      chatForm.addEventListener('submit', (event) => {
        event.preventDefault();
        sendChatMessage();
      });
    }
    const chatSendBtn = document.getElementById('chat-send-btn');
    if (chatSendBtn) {
      chatSendBtn.addEventListener('click', () => sendChatMessage());
    }
    const chatInput = document.getElementById('chat-input');
    if (chatInput) {
      chatInput.addEventListener('keydown', (event) => {
        if (event.key === 'Enter' && !event.shiftKey) {
          event.preventDefault();
          sendChatMessage();
        }
      });
    }
    document.body.addEventListener('htmx:afterSettle', () => {
      updateActiveRoutes();
      document.getElementById('app-main')?.focus();
    });
    document.addEventListener('keydown', (event) => {
      if (event.key === 'Escape') {
        setMobileSidebarState(false);
        const chatWindow = document.getElementById('ki-chat-window');
        if (chatWindow && window.getComputedStyle(chatWindow).display !== 'none') {
          toggleChat(false);
        }
      }
    });
  };

  if ('requestIdleCallback' in window) {
    window.requestIdleCallback(initializeUi, { timeout: 300 });
  } else {
    setTimeout(initializeUi, 0);
  }
}, { once: true });

function toggleChat(forceOpen) {
  const win = document.getElementById('ki-chat-window');
  const toggle = document.getElementById('ki-chat-toggle');
  if (!win || !toggle) return;
  const isHidden = window.getComputedStyle(win).display === 'none';
  const shouldOpen = typeof forceOpen === 'boolean' ? forceOpen : isHidden;
  win.style.display = shouldOpen ? 'flex' : 'none';
  win.setAttribute('aria-hidden', shouldOpen ? 'false' : 'true');
  win.setAttribute('aria-modal', shouldOpen ? 'true' : 'false');
  toggle.setAttribute('aria-expanded', shouldOpen ? 'true' : 'false');
  if (shouldOpen) {
    lastChatTrigger = document.activeElement instanceof HTMLElement ? document.activeElement : toggle;
    document.body.classList.add('chat-open');
    if (window.UIShell) window.UIShell.trapFocus(win);
    document.getElementById('chat-input')?.focus();
  } else {
    document.body.classList.remove('chat-open');
    (lastChatTrigger || toggle).focus();
    lastChatTrigger = null;
  }
}

function appendChatBubble(text, isUser = false) {
  const container = document.getElementById('chat-messages');
  if (!container) return;
  const msg = document.createElement('div');
  msg.style.cssText = isUser
    ? 'background: var(--color-primary); color: white; padding: 10px 14px; border-radius: 12px 12px 2px 12px; align-self: flex-end; max-width: 85%; line-height: 1.4;'
    : 'background: var(--bg-tertiary); padding: 10px 14px; border-radius: 12px 12px 12px 2px; align-self: flex-start; max-width: 85%; line-height: 1.4;';
  msg.textContent = text;
  container.appendChild(msg);
  container.scrollTop = container.scrollHeight;
}

function appendLine(container, text) {
  container.appendChild(document.createTextNode(text));
  container.appendChild(document.createElement('br'));
}

function renderManagerState(data) {
  const planEl = document.getElementById('chat-plan');
  const actionsEl = document.getElementById('chat-actions');
  if (!planEl || !actionsEl) return;

  const manager = data.manager_agent || {};
  const plan = manager.plan || [];
  const progress = manager.progress || {};
  const refs = manager.object_refs || {};
  const actions = data.actions || [];

  if (plan.length) {
    planEl.style.display = 'block';
    planEl.replaceChildren();

    const planTitle = document.createElement('strong');
    planTitle.textContent = 'Plan';
    planEl.appendChild(planTitle);

    const completedSteps = Number.isFinite(Number(progress.completed_steps)) ? Number(progress.completed_steps) : 0;
    const totalSteps = Number.isFinite(Number(progress.total_steps)) ? Number(progress.total_steps) : plan.length;
    planEl.appendChild(document.createTextNode(` (${completedSteps}/${totalSteps})`));
    planEl.appendChild(document.createElement('br'));

    plan.forEach((step) => {
      const status = step?.status === 'completed'
        ? '✅'
        : step?.status === 'in_progress'
          ? '⏳'
          : '•';
      const label = step?.step ? String(step.step) : 'Unbenannter Schritt';
      appendLine(planEl, `${status} ${label}`);
    });
  } else {
    planEl.style.display = 'none';
    planEl.replaceChildren();
  }

  if (actions.length || Object.keys(refs).length) {
    actionsEl.style.display = 'block';
    actionsEl.replaceChildren();

    const actionsTitle = document.createElement('strong');
    actionsTitle.textContent = 'Vorgeschlagene Aktionen';
    actionsEl.appendChild(actionsTitle);
    actionsEl.appendChild(document.createElement('br'));

    if (actions.length) {
      actions.forEach((action) => {
        const actionType = action?.type ? String(action.type) : 'Aktion';
        const requiresConfirm = action?.confirm_required ? ' (Bestätigung nötig)' : '';
        appendLine(actionsEl, `• ${actionType}${requiresConfirm}`);
      });
    } else {
      appendLine(actionsEl, '• Keine vorgeschlagenen Aktionen');
    }

    if (Object.keys(refs).length) {
      const normalizedRefs = Object.entries(refs).map(([key, rawValue]) => {
        const values = Array.isArray(rawValue)
          ? rawValue.map((entry) => String(entry))
          : [String(rawValue)];
        return `${String(key)}: ${values.join(', ')}`;
      });
      actionsEl.appendChild(document.createElement('br'));
      const refsTitle = document.createElement('strong');
      refsTitle.textContent = 'Referenzen:';
      actionsEl.appendChild(refsTitle);
      actionsEl.appendChild(document.createTextNode(` ${normalizedRefs.join(' · ')}`));
    }
  } else {
    actionsEl.style.display = 'none';
    actionsEl.replaceChildren();
  }
}

async function sendChatMessage() {
  const input = document.getElementById('chat-input');
  const sendBtn = document.getElementById('chat-send-btn');
  if (!input || !sendBtn) return;

  const text = input.value.trim();
  if (!text) return;

  appendChatBubble(text, true);
  input.value = '';
  input.disabled = true;
  sendBtn.disabled = true;

  const csrf = document.querySelector('meta[name="csrf-token"]')?.content || '';
  try {
    const body = chatPendingId
      ? { confirm: true, pending_id: chatPendingId, current_context: window.location.pathname }
      : { msg: text, current_context: window.location.pathname };
    const res = await fetch('/api/chat/compact', {
      method: 'POST',
      credentials: 'same-origin',
      headers: {
        'Content-Type': 'application/json',
        ...(csrf ? { 'X-CSRF-Token': csrf } : {}),
      },
      body: JSON.stringify(body),
    });

    let data = {};
    try { data = await res.json(); } catch (_) { data = {}; }
    const reply = data.text || data.response || '';
    if (reply) {
      appendChatBubble(reply, false);
    } else {
      appendChatBubble('Der Assistent konnte keine Antwort erzeugen.', false);
    }
    chatPendingId = data.pending_id || '';
    if (data.requires_confirm && chatPendingId) {
      appendChatBubble(data.confirm_prompt || 'Bitte bestätige die geplante Aktion mit erneutem Senden.', false);
    }
    renderManagerState(data);
  } catch (err) {
    appendChatBubble('Der Assistent ist aktuell nicht erreichbar.', false);
  } finally {
    input.disabled = false;
    sendBtn.disabled = false;
    input.focus();
  }
}
