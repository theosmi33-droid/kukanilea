/**
 * KUKANILEA Settings & Trust UX (Enterprise Edition)
 */

document.addEventListener('DOMContentLoaded', () => {
    initSettingsNavigation();
    initConfirmGates();
    initSystemMetrics();
    initAuditLogs();
});

/**
 * Handles section navigation and active menu states.
 */
function initSettingsNavigation() {
    const menuItems = document.querySelectorAll('.settings-menu-item');
    
    const updateActiveItem = () => {
        const hash = window.location.hash || '#users';
        menuItems.forEach(item => {
            const isActive = item.getAttribute('href') === hash;
            item.classList.toggle('active', isActive);
            item.setAttribute('aria-current', isActive ? 'page' : 'false');
        });
    };

    window.addEventListener('hashchange', updateActiveItem);
    updateActiveItem();
}

/**
 * Validates confirm-gate inputs before form submission.
 */
function initConfirmGates() {
    document.querySelectorAll('form').forEach(form => {
        const confirmInput = form.querySelector('input[name="confirm"]');
        if (!confirmInput) return;

        form.addEventListener('submit', (e) => {
            const value = confirmInput.value.trim().toUpperCase();
            if (value !== 'CONFIRM' && value !== 'YES') {
                e.preventDefault();
                alert('Sicherheitsbestätigung erforderlich: Bitte geben Sie "CONFIRM" ein.');
                confirmInput.focus();
                confirmInput.classList.add('is-invalid');
            } else {
                if (!confirm('Riskante Aktion ausführen?')) {
                    e.preventDefault();
                }
            }
        });
    });
}

/**
 * Simulates real-time system metrics for Enterprise UI.
 */
function initSystemMetrics() {
    const memEl = document.getElementById('metric-memory');
    const diskEl = document.getElementById('metric-disk');
    if (!memEl || !diskEl) return;

    const updateMetrics = () => {
        // Mocking real-time feedback
        const mem = (Math.random() * 15 + 40).toFixed(1);
        const disk = (Math.random() * 2 + 12).toFixed(1);
        
        memEl.textContent = `${mem}%`;
        diskEl.textContent = `${disk} GB / 50 GB`;
        
        memEl.parentElement.style.setProperty('--progress', `${mem}%`);
    };

    setInterval(updateMetrics, 5000);
    updateMetrics();
}

/**
 * Populates and manages the Audit Log view.
 */
function initAuditLogs() {
    const logBody = document.getElementById('audit-log-body');
    if (!logBody) return;

    const mockLogs = [
        { ts: new Date().toISOString(), user: 'admin', event: 'LOGIN_SUCCESS', ip: '127.0.0.1', severity: 'info' },
        { ts: new Date(Date.now() - 3600000).toISOString(), user: 'admin', event: 'BACKUP_CREATED', ip: '127.0.0.1', severity: 'success' },
        { ts: new Date(Date.now() - 7200000).toISOString(), user: 'system', event: 'LICENSE_CHECK_OK', ip: 'internal', severity: 'info' },
        { ts: new Date(Date.now() - 86400000).toISOString(), user: 'manager', event: 'USER_CREATED', ip: '192.168.1.45', severity: 'warning' }
    ];

    logBody.innerHTML = mockLogs.map(log => `
        <tr>
            <td class="font-mono text-xs">${log.ts.replace('T', ' ').split('.')[0]}</td>
            <td><span class="badge badge-secondary">${log.user}</span></td>
            <td class="font-bold">${log.event}</td>
            <td class="text-xs text-muted">${log.ip}</td>
            <td><span class="badge badge-${log.severity}">${log.severity.toUpperCase()}</span></td>
        </tr>
    `).join('');
}
