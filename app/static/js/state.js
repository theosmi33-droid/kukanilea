/**
 * static/js/state.js
 * Centralized UI state store and offline handling.
 */
const StateStore = {
    state: {
        isOnline: navigator.onLine,
        theme: localStorage.getItem('ks_theme') || 'light',
        activeRequests: 0,
        systemStatus: 'LOADING' // LOADING, READY, ERROR
    },
    listeners: [],

    init() {
        window.addEventListener('online', () => this.update('isOnline', true));
        window.addEventListener('offline', () => this.update('isOnline', false));
        this.update('systemStatus', 'READY');
    },

    update(key, value) {
        this.state[key] = value;
        this.notify();
    },

    subscribe(callback) {
        this.listeners.push(callback);
    },

    notify() {
        this.listeners.forEach(cb => cb(this.state));
    },

    toggleTheme() {
        // Sovereign-11 runtime contract: white mode only.
        localStorage.setItem('ks_theme', 'light');
        document.documentElement.classList.add('light');
        document.documentElement.classList.remove('dark');
        this.update('theme', 'light');
    }
};

document.addEventListener('DOMContentLoaded', () => StateStore.init());
