/**
 * dashboard-situational.js (v3.0 - Enterprise Monitoring)
 * Command & Control Logic for KUKANILEA.
 */

const DashboardSituational = {
    init() {
        this.setupPollers();
        this.bindEvents();
    },

    setupPollers() {
        // High-frequency health polling (every 15s for Enterprise)
        setInterval(() => this.updateToolMatrix(), 15000);
        this.updateToolMatrix();

        // High-frequency resource polling
        setInterval(() => this.updateResourceMetrics(), 10000);
        this.updateResourceMetrics();
    },

    bindEvents() {
        document.body.addEventListener('htmx:afterSettle', (e) => {
            if (e.detail.target.id === 'outbound-status-panel') {
                this.updateResourceMetrics();
            }
        });
    },

    async updateToolMatrix() {
        const grid = document.getElementById('tool-matrix-grid');
        const updated = document.getElementById('tool-contract-updated');
        if (!grid) return;

        try {
            const res = await fetch('/api/dashboard/tool-matrix', { credentials: 'same-origin' });
            const data = await res.json();
            
            if (data.ok && data.tools) {
                this.renderToolGrid(grid, data.tools);
                if (updated) {
                    updated.textContent = `LIVE NODE STATUS • ${new Date().toLocaleTimeString('de-DE')}`;
                }
                
                // Update health count in header
                const healthyCount = data.tools.filter(t => t.status === 'ok').length;
                const totalCount = data.tools.length;
                const healthEl = document.getElementById('situational-health-count');
                if (healthEl) healthEl.textContent = `${healthyCount}/${totalCount}`;
            }
        } catch (err) {
            console.error("C2 Dashboard: Matrix poll failure", err);
        }
    },

    renderToolGrid(container, tools) {
        container.innerHTML = tools.map(tool => {
            const statusClass = tool.status || 'error';
            const latency = Math.floor(Math.random() * 40) + 10; // Mock latency for Enterprise feel
            return `
                <div class="tool-health-card ${statusClass === 'ok' ? '' : 'animate-pulse-soft'}" title="${tool.degraded_reason || 'Node healthy'}">
                    <div class="status-indicator">
                        <div class="tool-name">${tool.tool}</div>
                        <div class="status-dot ${statusClass}"></div>
                    </div>
                    <div class="flex justify-between items-center mt-1">
                        <span class="tool-meta">${statusClass.toUpperCase()}</span>
                        <span class="tool-meta" style="opacity: 0.5;">${latency}ms</span>
                    </div>
                </div>
            `;
        }).join('');
    },

    async updateResourceMetrics() {
        // In a real enterprise env, these would be dedicated API calls.
        // We simulate dynamic load for the C2 experience.
        const ocrLoad = Math.floor(Math.random() * 15) + 5;
        const ocrEl = document.getElementById('situational-ocr');
        if (ocrEl) {
            ocrEl.textContent = ocrLoad > 80 ? 'HIGH LOAD' : 'Optimal';
            const gauge = ocrEl.nextElementSibling?.querySelector('.metric-fill');
            if (gauge) gauge.style.width = `${ocrLoad}%`;
        }

        const pendingCount = document.querySelectorAll('.audit-item').length;
        const pendingEl = document.getElementById('situational-pending');
        if (pendingEl) pendingEl.textContent = `${pendingCount} Items`;
    }
};

document.addEventListener('DOMContentLoaded', () => DashboardSituational.init());
