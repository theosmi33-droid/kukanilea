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
  const sidebarToggle = document.getElementById('sidebar-toggle');
  const updateSidebarLabel = () => {
    const collapsed = document.documentElement.classList.contains('sidebar-collapsed');
    if (sidebarToggle) {
      sidebarToggle.setAttribute('aria-expanded', !collapsed);
      sidebarToggle.title = collapsed ? 'Sidebar ausklappen' : 'Sidebar einklappen';
    }
  };

  if (sidebarToggle) {
    sidebarToggle.addEventListener('click', () => {
      const collapsed = document.documentElement.classList.toggle('sidebar-collapsed');
      try { localStorage.setItem('ks_sidebar_collapsed', collapsed ? '1' : '0'); } catch (e) {}
      updateSidebarLabel();
    });
  }

  const mobileToggle = document.getElementById('mobile-sidebar-toggle');
  const sidebar = document.querySelector('.sidebar');
  const mobileOverlay = document.getElementById('mobile-sidebar-overlay');
  const setMobileSidebarState = (isOpen) => {
    if (!sidebar || !mobileToggle) return;
    sidebar.classList.toggle('mobile-open', isOpen);
    document.body.classList.toggle('mobile-sidebar-open', isOpen);
    if (mobileOverlay) {
      mobileOverlay.hidden = !isOpen;
      mobileOverlay.setAttribute('aria-hidden', isOpen ? 'false' : 'true');
    }
    mobileToggle.setAttribute('aria-expanded', isOpen ? 'true' : 'false');
    mobileToggle.setAttribute('aria-label', isOpen ? 'Menü schließen' : 'Menü öffnen');
  };
  if (mobileToggle && sidebar) {
    mobileToggle.addEventListener('click', () => {
      const nextState = !sidebar.classList.contains('mobile-open');
      setMobileSidebarState(nextState);
    });
    mobileOverlay?.addEventListener('click', () => setMobileSidebarState(false));
    sidebar.querySelectorAll('a[href]').forEach((link) => {
      link.addEventListener('click', () => setMobileSidebarState(false));
    });
    window.addEventListener('resize', () => {
      if (window.innerWidth > 768 && sidebar.classList.contains('mobile-open')) {
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



  const sidebarRouteOrder = ['/dashboard', '/visualizer', '/assistant', '/upload', '/tasks', '/system-logs', '/settings'];
  const quickNavigate = (index) => {
    const target = sidebarRouteOrder[index];
    if (target) window.location.href = target;
  };

  const initKeyboardNavigation = () => {
    document.addEventListener('keydown', (event) => {
      if ((event.metaKey || event.ctrlKey) && event.key.toLowerCase() === 'k') {
        const searchInput = document.getElementById('topbar-search');
        if (searchInput) {
          event.preventDefault();
          searchInput.focus();
          searchInput.select?.();
        }
      }

      if (event.altKey && /^[1-7]$/.test(event.key)) {
        event.preventDefault();
        quickNavigate(Number(event.key) - 1);
      }

      if (event.altKey && (event.key === 'ArrowDown' || event.key === 'ArrowUp')) {
        const links = Array.from(document.querySelectorAll('#sidebar-primary-nav .nav-link'));
        if (!links.length) return;
        event.preventDefault();
        const activeElement = document.activeElement;
        let idx = links.indexOf(activeElement);
        if (idx < 0) {
          idx = links.findIndex((l) => l.classList.contains('active'));
        }
        const delta = event.key === 'ArrowDown' ? 1 : -1;
        const nextIdx = (idx + delta + links.length) % links.length;
        links[nextIdx].focus();
      }
    });

    const topbarSearch = document.getElementById('topbar-search');
    if (topbarSearch) {
      topbarSearch.addEventListener('focus', () => {
        if (window.CommandPalette?.open) window.CommandPalette.open();
      });
      topbarSearch.addEventListener('keydown', (event) => {
        if (event.key === 'Enter') {
          event.preventDefault();
          if (window.CommandPalette?.open) window.CommandPalette.open();
        }
      });
    }
  };
  const initializeUi = () => {
    updateSidebarLabel();
    updateActiveRoutes();
    initKeyboardNavigation();
    const chatToggle = document.getElementById('ki-chat-toggle');
    if (chatToggle) {
      chatToggle.addEventListener('click', () => toggleChat());
    }
    const chatClose = document.getElementById('ki-chat-close');
    if (chatClose) {
      chatClose.addEventListener('click', () => toggleChat(false));
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
  toggle.setAttribute('aria-expanded', shouldOpen ? 'true' : 'false');
  if (shouldOpen) {
    document.getElementById('chat-input')?.focus();
  } else {
    toggle.focus();
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
