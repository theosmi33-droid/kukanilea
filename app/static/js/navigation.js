/**
 * app/static/js/navigation.js
 * Subtle navigation motion and interaction feedback.
 */

(function initNavigationMotion() {
  if (window.__kukanileaNavigationMotionInit) return;
  window.__kukanileaNavigationMotionInit = true;

  const ready = () => {
    setupPressedState();
    setupHtmxLoadingFeedback();
    setupDisclosure();
    setupAutoAriaLabels();
    syncDrawerVisualState();
    markCurrentNavigation();

    document.body.addEventListener('htmx:afterSettle', () => {
      window.requestAnimationFrame(markCurrentNavigation);
    }, { passive: true });
  };

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', ready, { once: true });
  } else {
    ready();
  }

  function setupPressedState() {
    const targetSelector = '.nav-link, .btn, .mobile-nav-item';

    const setPressed = (event, value) => {
      const target = event.target instanceof Element ? event.target.closest(targetSelector) : null;
      if (target) target.classList.toggle('is-pressed', value);
    };

    document.addEventListener('pointerdown', (event) => setPressed(event, true), { passive: true });
    document.addEventListener('pointerup', (event) => setPressed(event, false), { passive: true });
    document.addEventListener('pointercancel', (event) => setPressed(event, false), { passive: true });
    document.addEventListener('blur', (event) => setPressed(event, false), { capture: true, passive: true });
  }

  function setupHtmxLoadingFeedback() {
    let requestsInFlight = 0;

    const setLoading = (isLoading) => {
      document.body.setAttribute('data-htmx-loading', isLoading ? '1' : '0');
    };

    setLoading(false);

    document.body.addEventListener('htmx:beforeRequest', () => {
      requestsInFlight += 1;
      setLoading(true);
    });

    const finalize = () => {
      requestsInFlight = Math.max(0, requestsInFlight - 1);
      if (requestsInFlight === 0) setLoading(false);
    };

    document.body.addEventListener('htmx:afterRequest', finalize);
    document.body.addEventListener('htmx:responseError', finalize);
    document.body.addEventListener('htmx:sendError', finalize);
  }

  function setupDisclosure() {
    document.querySelectorAll('[data-disclosure-toggle]').forEach((toggle) => {
      const targetId = toggle.getAttribute('data-disclosure-target');
      if (!targetId) return;
      const panel = document.getElementById(targetId);
      if (!panel) return;

      const setExpanded = (expanded) => {
        toggle.setAttribute('aria-expanded', expanded ? 'true' : 'false');
        panel.classList.toggle('is-open', expanded);
        panel.hidden = !expanded;
      };

      const expandedByDefault = toggle.getAttribute('aria-expanded') === 'true';
      setExpanded(expandedByDefault);

      toggle.addEventListener('click', () => {
        setExpanded(toggle.getAttribute('aria-expanded') !== 'true');
      });

      toggle.addEventListener('keydown', (event) => {
        if (event.key === 'Enter' || event.key === ' ') {
          event.preventDefault();
          setExpanded(toggle.getAttribute('aria-expanded') !== 'true');
          return;
        }
        if (event.key === 'Escape') {
          event.preventDefault();
          setExpanded(false);
          toggle.focus();
          return;
        }
        if (event.key === 'ArrowDown' && toggle.getAttribute('aria-expanded') === 'true') {
          event.preventDefault();
          panel.querySelector('a, button, [tabindex]:not([tabindex="-1"])')?.focus();
        }
      });

      panel.addEventListener('keydown', (event) => {
        if (event.key !== 'Escape') return;
        event.preventDefault();
        setExpanded(false);
        toggle.focus();
      });
    });
  }



  function setupAutoAriaLabels() {
    document.querySelectorAll('button, [role="button"], a, input:not([type="hidden"]), select, textarea').forEach((el) => {
      if (el.getAttribute('aria-label') || el.getAttribute('aria-labelledby')) return;
      const id = el.getAttribute('id');
      if (id) {
        const label = document.querySelector(`label[for="${id}"]`);
        if (label && label.textContent?.trim()) {
          el.setAttribute('aria-label', label.textContent.trim());
          return;
        }
      }
      const text = el.getAttribute('title') || el.getAttribute('placeholder') || el.textContent;
      if (text && text.trim()) el.setAttribute('aria-label', text.trim());
    });
  }

  function syncDrawerVisualState() {
    const sidebar = document.getElementById('app-sidebar');
    if (!sidebar) return;

    const apply = () => {
      sidebar.classList.toggle('drawer-open', sidebar.classList.contains('mobile-open'));
    };

    apply();
    const observer = new MutationObserver(apply);
    observer.observe(sidebar, { attributes: true, attributeFilter: ['class'] });
  }

  function markCurrentNavigation() {
    const links = document.querySelectorAll('.nav-link[data-route], .mobile-nav-item[data-route]');
    links.forEach((link) => {
      const isCurrent = link.getAttribute('aria-current') === 'page' || link.classList.contains('active');
      link.toggleAttribute('data-current', isCurrent);
    });
  }
})();
