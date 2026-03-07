/**
 * app/static/js/outbound_poller.js
 * Centralized, visibility-aware poller for outbound status.
 */

const OutboundPoller = {
    interval: 10000, // 10s default
    minInterval: 10000,
    maxInterval: 60000,
    hiddenInterval: 300000, // 5m if hidden
    idleMultiplier: 1.5,
    errorMultiplier: 2,
    timer: null,
    lastHash: null,

    init() {
        console.log("[OutboundPoller] Initializing...");
        this.start();
        this.setupVisibilityHandler();
        
        // Listen for HTMX events to detect if the panel actually exists
        document.body.addEventListener('htmx:afterSettle', (e) => {
            if (e.detail.target.id === 'outbound-status-panel') {
                // If it was just added, maybe trigger a quick refresh if needed
            }
        });
    },

    setupVisibilityHandler() {
        document.addEventListener("visibilitychange", () => {
            if (document.hidden) {
                console.log("[OutboundPoller] Tab hidden, slowing down...");
                this.stop();
                this.start(this.hiddenInterval);
            } else {
                console.log("[OutboundPoller] Tab visible, resuming...");
                this.stop();
                this.interval = this.minInterval;
                this.start();
            }
        });
    },

    start(customInterval = null) {
        const time = customInterval || this.interval;
        this.timer = setTimeout(() => this.poll(), time);
    },

    stop() {
        if (this.timer) {
            clearTimeout(this.timer);
            this.timer = null;
        }
    },

    async poll() {
        const panel = document.getElementById('outbound-status-panel');
        if (!panel) {
            // Panel not on current page, wait longer but keep alive in case of SPA navigation
            this.interval = Math.min(this.interval * this.idleMultiplier, this.maxInterval);
            this.start();
            return;
        }

        if (document.hidden) {
            this.start(this.hiddenInterval);
            return;
        }

        try {
            // Use htmx.ajax to trigger the refresh
            // We target the panel itself
            await htmx.ajax('GET', '/api/outbound/status', {
                target: '#outbound-status-panel',
                swap: 'outerHTML'
            });

            // If successful, reset interval if it was an error backoff, 
            // but keep idle backoff if we want (for now just reset to min)
            this.interval = this.minInterval;
        } catch (err) {
            console.error("[OutboundPoller] Poll failed", err);
            this.interval = Math.min(this.interval * this.errorMultiplier, this.maxInterval);
        }

        this.start();
    }
};

// Initialize on DOM load
if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', () => OutboundPoller.init());
} else {
    OutboundPoller.init();
}

window.OutboundPoller = OutboundPoller;
