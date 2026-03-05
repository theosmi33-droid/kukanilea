/**
 * app/static/js/ui-shell.js
 * Core Shell Interactions & Focus Management.
 */

const UIShell = {
    init() {
        this.setupPageReveal();
        this.setupKeyboardShortcuts();
        this.setupHTMXIntegration();
    },

    setupPageReveal() {
        // Trigger reveal when DOM is ready
        document.addEventListener('DOMContentLoaded', () => {
            const mainContent = document.getElementById('main-content');
            if (mainContent) {
                mainContent.setAttribute('data-page-ready', '1');
            }
        });
    },

    setupKeyboardShortcuts() {
        document.addEventListener('keydown', (e) => {
            // Global Escape handling
            if (e.key === 'Escape') {
                this.handleEscape();
            }

            // Command Palette (Legacy support)
            if ((e.metaKey || e.ctrlKey) && e.key === 'k') {
                // Command palette is already handled by command_palette.js
            }
        });
    },

    handleEscape() {
        // Close modals or dialogs
        const dialog = document.getElementById('confirm-dialog-backdrop');
        if (dialog) {
            UIFeedback.closeConfirmDialog();
        }

        // Close Chatbot if open
        const chatWin = document.getElementById('ki-chat-window');
        if (chatWin && window.getComputedStyle(chatWin).display !== 'none') {
            if (typeof toggleChat === 'function') toggleChat();
        }
    },

    setupHTMXIntegration() {
        // Handle focus management after content updates
        document.body.addEventListener('htmx:afterSettle', (e) => {
            const target = e.detail.target;

            requestAnimationFrame(() => {
                // If main content updated, reveal it
                if (target.id === 'main-content') {
                    target.removeAttribute('data-page-ready');
                    // Force reflow
                    void target.offsetWidth;
                    target.setAttribute('data-page-ready', '1');

                    // Focus the main element for screen readers
                    const main = document.getElementById('app-main');
                    if (main) main.focus();
                }

                // Reveal items if any
                target.querySelectorAll('.reveal-item').forEach((item, index) => {
                    setTimeout(() => {
                        item.classList.add('revealed');
                    }, index * 40);
                });
            });
        }, { passive: true });

        // Show feedback on long requests
        document.body.addEventListener('htmx:send', () => {
            // Optional: Start global loading bar
        });
    },

    /**
     * Traps focus within an element (A11y)
     * @param {HTMLElement} element 
     */
    trapFocus(element) {
        const focusableElements = element.querySelectorAll('button, [href], input, select, textarea, [tabindex]:not([tabindex="-1"])');
        const firstFocusableElement = focusableElements[0];
        const lastFocusableElement = focusableElements[focusableElements.length - 1];

        element.addEventListener('keydown', function(e) {
            if (e.key !== 'Tab') return;

            if (e.shiftKey) {
                if (document.activeElement === firstFocusableElement) {
                    lastFocusableElement.focus();
                    e.preventDefault();
                }
            } else {
                if (document.activeElement === lastFocusableElement) {
                    firstFocusableElement.focus();
                    e.preventDefault();
                }
            }
        });

        if (firstFocusableElement) firstFocusableElement.focus();
    }
};

UIShell.init();
window.UIShell = UIShell;
