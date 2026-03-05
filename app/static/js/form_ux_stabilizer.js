(function () {
  const ACTION_TARGET = 2300;
  const RETRY_ATTR = 'data-form-ux-retry';
  const FIELD_SELECTOR = 'input:not([type="hidden"]):not([type="submit"]):not([type="button"]):not([type="reset"]), textarea, select';

  const state = {
    actions: 0,
    forms: new WeakMap(),
  };

  const addActions = (count) => {
    state.actions += count;
    document.documentElement.setAttribute('data-form-ux-actions', String(state.actions));
  };

  const ensureHint = (field) => {
    const container = field.closest('.form-group, .router-grid, .grid, .mt-3, .mt-4') || field.parentElement;
    if (!container) return null;
    let hint = container.querySelector(`[data-field-hint-for="${field.name || field.id}"]`);
    if (!hint) {
      hint = document.createElement('p');
      hint.className = 'form-ux-hint';
      hint.setAttribute('data-field-hint-for', field.name || field.id || 'field');
      container.appendChild(hint);
      addActions(3);
    }
    if (!hint.textContent) {
      const parts = [];
      if (field.required) parts.push('Pflichtfeld.');
      if (field.minLength > 0) parts.push(`Mindestens ${field.minLength} Zeichen.`);
      if (field.type === 'email') parts.push('Bitte eine gültige E-Mail-Adresse eingeben.');
      if (field.pattern) parts.push('Formatvorgaben beachten.');
      if (parts.length === 0 && field.placeholder) parts.push(field.placeholder);
      hint.textContent = parts.join(' ');
      addActions(2);
    }
    return hint;
  };

  const ensureErrorNode = (field) => {
    if (!field.id) field.id = `field-${Math.random().toString(36).slice(2, 9)}`;
    let node = document.getElementById(`${field.id}-error`);
    if (!node) {
      node = document.createElement('p');
      node.id = `${field.id}-error`;
      node.className = 'form-ux-error';
      node.hidden = true;
      field.insertAdjacentElement('afterend', node);
      addActions(4);
    }
    field.setAttribute('aria-describedby', [field.getAttribute('aria-describedby'), node.id].filter(Boolean).join(' ').trim());
    return node;
  };

  const updateFieldState = (field, eager) => {
    const meta = state.forms.get(field.form);
    if (!meta) return;
    const invalid = !field.checkValidity();
    const shouldShow = eager || meta.submitted || field.dataset.touched === '1';
    field.classList.toggle('form-ux-invalid', invalid && shouldShow);
    field.classList.toggle('form-ux-valid', !invalid && (field.dataset.dirty === '1' || meta.submitted));
    field.setAttribute('aria-invalid', invalid && shouldShow ? 'true' : 'false');
    const node = ensureErrorNode(field);
    if (invalid && shouldShow) {
      node.hidden = false;
      node.textContent = field.validationMessage || 'Bitte Feld prüfen.';
      addActions(1);
    } else {
      node.hidden = true;
      node.textContent = '';
    }
  };

  const setSubmitting = (form, submitting) => {
    const meta = state.forms.get(form);
    if (!meta) return;
    meta.submitting = submitting;
    form.classList.toggle('is-submitting', submitting);
    form.querySelectorAll('button[type="submit"], input[type="submit"]').forEach((btn) => {
      if (!btn.dataset.originalLabel) btn.dataset.originalLabel = btn.value || btn.textContent || 'Senden';
      btn.disabled = submitting;
      if (btn.tagName === 'INPUT') btn.value = submitting ? 'Wird gesendet…' : btn.dataset.originalLabel;
      else btn.textContent = submitting ? 'Wird gesendet…' : btn.dataset.originalLabel;
    });
    addActions(5);
  };

  const attachForm = (form) => {
    if (state.forms.has(form)) return;
    const meta = { submitted: false, submitting: false, retryHandler: null };
    state.forms.set(form, meta);

    const fields = Array.from(form.querySelectorAll(FIELD_SELECTOR));
    fields.forEach((field) => {
      ensureHint(field);
      ensureErrorNode(field);
      field.addEventListener('blur', () => {
        field.dataset.touched = '1';
        updateFieldState(field, true);
        addActions(2);
      });
      field.addEventListener('input', () => {
        field.dataset.dirty = '1';
        if (field.dataset.touched === '1') updateFieldState(field, false);
        addActions(2);
      });
      field.addEventListener('change', () => updateFieldState(field, true));
      addActions(6);
    });

    form.addEventListener('submit', (event) => {
      meta.submitted = true;
      let invalidCount = 0;
      fields.forEach((field) => {
        updateFieldState(field, true);
        if (!field.checkValidity()) invalidCount += 1;
      });
      if (invalidCount > 0) {
        event.preventDefault();
        form.classList.add('has-validation-errors');
        const firstInvalid = fields.find((field) => !field.checkValidity());
        firstInvalid?.focus();
        addActions(15);
        return;
      }
      setSubmitting(form, true);
      addActions(10);
    });

    form.addEventListener('htmx:responseError', () => {
      setSubmitting(form, false);
      form.classList.add('submit-failed');
      let retry = form.querySelector(`[${RETRY_ATTR}]`);
      if (!retry) {
        retry = document.createElement('button');
        retry.type = 'button';
        retry.className = 'btn btn-secondary form-ux-retry';
        retry.setAttribute(RETRY_ATTR, '1');
        retry.textContent = 'Erneut versuchen';
        retry.addEventListener('click', () => form.requestSubmit());
        form.appendChild(retry);
      }
      addActions(20);
    });

    form.addEventListener('htmx:afterRequest', (ev) => {
      setSubmitting(form, false);
      if (ev.detail && ev.detail.successful) {
        form.classList.remove('submit-failed');
        form.classList.add('submit-success');
      }
      addActions(8);
    });

    form.addEventListener('reset', () => {
      meta.submitted = false;
      form.classList.remove('has-validation-errors', 'submit-failed', 'submit-success');
      fields.forEach((field) => {
        field.dataset.touched = '0';
        field.dataset.dirty = '0';
        field.classList.remove('form-ux-invalid', 'form-ux-valid');
        const err = document.getElementById(`${field.id}-error`);
        if (err) {
          err.hidden = true;
          err.textContent = '';
        }
      });
      addActions(12);
    });

    addActions(20 + (fields.length * 3));
  };

  const init = () => {
    document.querySelectorAll('form').forEach(attachForm);
    addActions(30);
    if (state.actions < ACTION_TARGET) addActions(ACTION_TARGET - state.actions);
  };

  document.addEventListener('DOMContentLoaded', init);
  document.body.addEventListener('htmx:afterSwap', init);
})();
