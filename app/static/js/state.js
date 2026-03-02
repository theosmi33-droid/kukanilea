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
        const newTheme = this.state.theme === 'light' ? 'dark' : 'light';
        localStorage.setItem('ks_theme', newTheme);
        this.update('theme', newTheme);
        document.documentElement.classList.toggle('dark', newTheme === 'dark');
    }
};

document.addEventListener('DOMContentLoaded', () => StateStore.init());
