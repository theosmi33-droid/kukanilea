/**
 * static/js/toast.js
 * Globales Toast-System für KUKANILEA.
 */

window.toast = function(message, level = 'info') {
    const container = document.getElementById('toast-container');
    if (!container) return;

    const toast = document.createElement('div');
    toast.className = `toast toast-${level}`;
    
    const titles = {
        'success': 'Erfolg',
        'warn': 'Warnung',
        'error': 'Fehler',
        'info': 'Information'
    };

    toast.innerHTML = `
        <div class="toast-content">
            <span class="toast-title">${titles[level] || 'System'}</span>
            <div class="toast-message">${message}</div>
        </div>
        <button class="toast-close" onclick="this.parentElement.remove()">✕</button>
    `;

    container.appendChild(toast);

    // Trigger animation
    setTimeout(() => toast.classList.add('show'), 10);

    // Auto-remove
    const timeout = level === 'error' ? 8000 : 5000;
    setTimeout(() => {
        toast.classList.remove('show');
        setTimeout(() => toast.remove(), 400);
    }, timeout);
};

// Legacy alias
window.showToast = window.toast;
