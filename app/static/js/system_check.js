// Test script for Interaction & Motion System
const testSystem = () => {
    console.log("Checking Interaction & Motion System...");
    
    // Check Global Objects
    if (typeof UIShell !== 'undefined') {
        console.log("PASS: UIShell is defined.");
    } else {
        console.error("FAIL: UIShell is missing.");
    }

    if (typeof UIFeedback !== 'undefined') {
        console.log("PASS: UIFeedback is defined.");
    } else {
        console.error("FAIL: UIFeedback is missing.");
    }

    // Check Global Shortcuts
    if (typeof window.toast === 'function') {
        console.log("PASS: window.toast is a function.");
    } else {
        console.error("FAIL: window.toast is missing.");
    }

    if (typeof window.confirmUX === 'function') {
        console.log("PASS: window.confirmUX is a function.");
    } else {
        console.error("FAIL: window.confirmUX is missing.");
    }

    // Check HTMX Integration
    const bodyListeners = getEventListeners(document.body);
    if (bodyListeners['htmx:confirm'] || bodyListeners['htmx:afterSettle']) {
        console.log("PASS: HTMX Event listeners found (Note: getEventListeners only works in DevTools console usually).");
    }
};

// Mock for headless environment if needed
if (typeof getEventListeners === 'undefined') {
    window.getEventListeners = (el) => ({});
}

testSystem();
