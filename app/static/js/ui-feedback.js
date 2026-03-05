/**
 * app/static/js/ui-feedback.js
 * Feedback & Notification System.
 */

const UIFeedback = {
    init() {
        this.ensureContainers();
    },

    ensureContainers() {
        // Ensure Toast Container exists
        if (!document.getElementById('toast-container')) {
            const container = document.createElement('div');
            container.id = 'toast-container';
            container.className = 'toast-container';
            container.setAttribute('aria-live', 'polite');
            container.setAttribute('aria-atomic', 'true');
            container.style.cssText = 'position: fixed; top: 24px; right: 24px; z-index: 10000; display: flex; flex-direction: column; gap: 12px; pointer-events: none;';
            document.body.appendChild(container);
        }

        // Ensure Confirm Dialog Template exists
        if (!document.getElementById('confirm-dialog-template')) {
            const template = document.createElement('template');
            template.id = 'confirm-dialog-template';
            template.innerHTML = `
                <div class="confirm-dialog-inner" style="position: fixed; inset: 0; background: rgba(0,0,0,0.5); backdrop-filter: blur(4px); display: flex; align-items: center; justify-content: center; z-index: 10100; padding: 20px;">
                    <div class="confirm-dialog card" style="max-width: 400px; width: 100%; padding: 24px; box-shadow: var(--shadow-xl); border: 1px solid var(--border-color); background: var(--bg-primary); border-radius: 16px;">
                        <h3 class="confirm-title" style="margin-top: 0; font-size: 18px; color: var(--text-primary);">Bestätigung</h3>
                        <p class="confirm-message" style="font-size: 14px; color: var(--text-secondary); margin-bottom: 24px; line-height: 1.5;"></p>
                        <div class="confirm-actions" style="display: flex; gap: 12px; justify-content: flex-end;">
                            <button class="confirm-btn-no btn btn-secondary" style="min-width: 100px;">Abbrechen</button>
                            <button class="confirm-btn-yes btn btn-primary" style="min-width: 100px;">Bestätigen</button>
                        </div>
                    </div>
                </div>
            `;
            document.body.appendChild(template);
        }
    },

    toast(message, level = 'info') {
        this.ensureContainers();
        const container = document.getElementById('toast-container');
        if (!container) return;

        const toast = document.createElement('div');
        toast.className = `toast toast-${level}`;
        toast.setAttribute('role', level === 'error' ? 'alert' : 'status');
        toast.setAttribute('aria-live', level === 'error' ? 'assertive' : 'polite');

        const titles = {
            'success': 'Erfolg',
            'warn': 'Warnung',
            'error': 'Fehler',
            'info': 'Information'
        };

        const icon = this.getIconForLevel(level);

        toast.innerHTML = `
            <div class="toast-icon">${icon}</div>
            <div class="toast-content">
                <span class="toast-title">${titles[level] || 'System'}</span>
                <div class="toast-message">${message}</div>
            </div>
            <button class="toast-close" aria-label="Schließen">✕</button>
        `;

        container.appendChild(toast);

        // Auto-remove logic
        const closeBtn = toast.querySelector('.toast-close');
        closeBtn.onclick = () => this.dismissToast(toast);

        const timeout = level === 'error' ? 8000 : 5000;
        setTimeout(() => this.dismissToast(toast), timeout);
    },

    dismissToast(toast) {
        if (toast.classList.contains('hiding')) return;
        toast.classList.add('hiding');
        setTimeout(() => toast.remove(), 300);
    },

    getIconForLevel(level) {
        // Placeholder for icons if needed
        return '';
    },

    /**
     * Shows a custom confirm dialog
     * @param {string} title 
     * @param {string} message 
     * @param {function} onConfirm 
     * @param {function} onCancel 
     */
    confirm(title, message, onConfirm, onCancel) {
        const template = document.getElementById('confirm-dialog-template');
        if (!template) {
            // Fallback to native if template missing
            if (window.confirm(`${title}\n\n${message}`)) {
                if (onConfirm) onConfirm();
            } else {
                if (onCancel) onCancel();
            }
            return;
        }

        // Remove existing if any
        this.closeConfirmDialog();

        const backdrop = document.createElement('div');
        backdrop.id = 'confirm-dialog-backdrop';
        backdrop.className = 'confirm-backdrop';
        backdrop.innerHTML = template.innerHTML;

        document.body.appendChild(backdrop);

        backdrop.querySelector('.confirm-title').textContent = title;
        backdrop.querySelector('.confirm-message').textContent = message;

        const confirmBtn = backdrop.querySelector('.confirm-btn-yes');
        const cancelBtn = backdrop.querySelector('.confirm-btn-no');

        confirmBtn.onclick = () => {
            this.closeConfirmDialog();
            if (onConfirm) onConfirm();
        };

        cancelBtn.onclick = () => {
            this.closeConfirmDialog();
            if (onCancel) onCancel();
        };

        // Trap focus
        if (window.UIShell) UIShell.trapFocus(backdrop);
    },

    closeConfirmDialog() {
        const dialog = document.getElementById('confirm-dialog-backdrop');
        if (dialog) dialog.remove();
    }
};

UIFeedback.init();

// Global Exposure
window.toast = (msg, lvl) => UIFeedback.toast(msg, lvl);
window.confirmUX = (title, msg, onOk, onCancel) => UIFeedback.confirm(title, msg, onOk, onCancel);

// Integration with HTMX for hx-confirm
document.addEventListener('htmx:confirm', function(evt) {
    const question = evt.detail.question;
    if (!question) return;

    evt.preventDefault();
    UIFeedback.confirm('Bestätigung erforderlich', question, () => {
        evt.detail.issueRequest();
    });
});
