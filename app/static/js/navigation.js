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
    syncDrawerVisualState();
    markCurrentNavigation();

    document.body.addEventListener('htmx:afterSettle', () => {
      markCurrentNavigation();
    }, { passive: true });
  };

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', ready, { once: true });
  } else {
    ready();
  }

  function setupPressedState() {
    document.querySelectorAll('.nav-link, .btn, .mobile-nav-item').forEach((el) => {
      el.addEventListener('pointerdown', () => el.classList.add('is-pressed'), { passive: true });
      el.addEventListener('pointerup', () => el.classList.remove('is-pressed'), { passive: true });
      el.addEventListener('pointercancel', () => el.classList.remove('is-pressed'), { passive: true });
      el.addEventListener('blur', () => el.classList.remove('is-pressed'), { passive: true });
    });
  }

  function setupHtmxLoadingFeedback() {
    let requestsInFlight = 0;

    const contentRoot = document.getElementById('main-content');

    const setLoading = (isLoading) => {
      document.body.setAttribute('data-htmx-loading', isLoading ? '1' : '0');
      if (contentRoot) {
        contentRoot.classList.toggle('loading-skeleton', isLoading);
        contentRoot.setAttribute('aria-busy', isLoading ? 'true' : 'false');
      }
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
    document.querySelectorAll('.nav-link[data-route], .mobile-nav-item[data-route]').forEach((link) => {
      const isCurrent = link.getAttribute('aria-current') === 'page' || link.classList.contains('active');
      link.toggleAttribute('data-current', isCurrent);
    });
  }
})();
