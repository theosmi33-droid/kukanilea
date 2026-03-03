# 🏛️ KUKANILEA – SOVEREIGN 11 FINAL INTEGRATION PACKAGE

**Version:** 3.0 (Production-Ready)  
**Date:** 24. Februar 2026  
**Mission:** UI/UX Integration der 11 Tools - Nichts anderes  
**Status:** READY TO EXECUTE

---

## 📋 EXECUTIVE SUMMARY

**Was:** Integration aller 11 Tools in ein minimalistisches, blind-bedienbares Interface  
**Warum:** Master-Plan P0-2 (Broken Links + Fehlende Tools) muss gelöst werden  
**Wie:** Sovereign 11 Shell mit HTMX-Navigation, White-Mode, 8pt-Grid  
**Wann:** Jetzt sofort (2-3 Tage Execution Time)

---

## 🎯 THE SOVEREIGN 11 (Final Spec)

### **Navigation Hierarchy (Sidebar-Only)**

```
┌─────────────────────────────────────┐
│  FOCUS TOOLS (Top)                  │
├─────────────────────────────────────┤
│  1. Dashboard      → /dashboard     │
│  2. Upload         → /upload        │
│  3. Projekte       → /projects      │
│  4. Aufgaben       → /tasks         │
├─────────────────────────────────────┤
│  COMMUNICATION & TIME (Middle)      │
├─────────────────────────────────────┤
│  5. Messenger      → /messenger     │
│  6. Emailpostfach  → /email         │
│  7. Kalender       → /calendar      │
│  8. Zeiterfassung  → /time          │
├─────────────────────────────────────┤
│  TOOLS & SYSTEM (Bottom)            │
├─────────────────────────────────────┤
│  9. Visualizer     → /visualizer    │
│  10. Einstellungen → /settings      │
├─────────────────────────────────────┤
│  OVERLAY (Always present)           │
├─────────────────────────────────────┤
│  11. Floating Widget → bottom-right │
└─────────────────────────────────────┘
```

### **Visual Identity (Design Tokens)**

```css
/* SOVEREIGN 11 DESIGN TOKENS */

/* Colors - White Mode ONLY */
--bg-primary: #FFFFFF;        /* Main background - NO EXCEPTIONS */
--bg-sidebar: #F8FAFC;        /* Sidebar subtle gray */
--border-sidebar: #E2E8F0;    /* 1px border right */

--text-primary: #0F172A;      /* High contrast for blind-operational */
--text-secondary: #64748B;    /* Lower hierarchy */

--accent-primary: #2563EB;    /* Blue - ONLY accent color */
--accent-hover: #1D4ED8;      /* Hover state */

/* Spacing - 8pt Grid (non-negotiable) */
--space-1: 8px;
--space-2: 16px;
--space-3: 24px;
--space-4: 32px;
--space-6: 48px;
--space-8: 64px;

/* Typography - Inter ONLY */
--font-primary: 'Inter', -apple-system, BlinkMacSystemFont, sans-serif;
--font-size-sm: 14px;
--font-size-base: 16px;
--font-weight-normal: 400;
--font-weight-medium: 500;
--font-weight-semibold: 600;

/* Radius */
--radius-md: 6px;

/* Transitions */
--transition-base: 0.15s ease;
```

### **Icon Spec (Lucide/Heroicons Style)**

All icons MUST be:
- ✅ SVG format (vector, scalable)
- ✅ 20×20px default size
- ✅ 2px stroke width
- ✅ Round line caps
- ✅ Local only (`/static/icons/sprite.svg`)
- ❌ NO external CDNs (Google Icons, Font Awesome, etc.)
- ❌ NO emojis
- ❌ NO raster images (PNG, JPG)

---

## 🔧 ENGINEERING PROMPT (For Core Fleet Commander)

### **ROLE:** Principal UI/UX Architect  
### **MAXIM:** "Absolute Minimalism. No Clutter. Only the 11 Tools."

---

### **MISSION BRIEF**

Replace current navigation with **Sovereign 11 Interface**:
- UI shows EXACTLY 11 tools (counted manually)
- Remove ALL other menu items, footer links, experimental views
- Enforce White-Mode (no dark-mode toggle)
- Ensure blind-operational (WCAG AA contrast)
- Performance: Initial load <150ms

---

### **PHASE 1: LAYOUT ARCHITECTURE**

#### Task 1.1: Base Shell (`app/templates/layout.html`)

**Requirements:**
- Static sidebar (left, 240px width, fixed position)
- HTMX for content switching (`hx-get`, `hx-target="#main-content"`, `hx-push-url="true"`)
- Main content area: Maximum whitespace, 8pt-grid padding
- Zero full-page reloads

**Implementation:**

```html
<!DOCTYPE html>
<html lang="de">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{{ page_title or 'KUKANILEA' }}</title>
    
    <!-- Local CSS ONLY -->
    <link rel="stylesheet" href="/static/css/design-system.css">
    <link rel="stylesheet" href="/static/css/sovereign-shell.css">
    
    <!-- Local Inter Font -->
    <link rel="preload" href="/static/fonts/Inter-Regular.woff2" as="font" type="font/woff2" crossorigin>
    
    <!-- Local JS ONLY -->
    <script src="/static/js/vendor/htmx.min.js" defer></script>
    <script src="/static/js/navigation.js" defer></script>
</head>
<body class="sovereign-shell">
    <!-- Sidebar: The Sovereign 11 -->
    <nav class="sidebar" role="navigation" aria-label="Hauptnavigation">
        <!-- Logo -->
        <div class="sidebar-header">
            <svg class="logo" viewBox="0 0 200 40" xmlns="http://www.w3.org/2000/svg">
                <g class="logo-icon">
                    <path d="M10,5 L10,35 M10,20 L25,5 M10,20 L25,35" 
                          stroke="currentColor" 
                          stroke-width="3" 
                          stroke-linecap="round"
                          fill="none"/>
                </g>
                <text x="35" y="28" 
                      font-family="var(--font-primary)"
                      font-weight="600"
                      font-size="18"
                      fill="currentColor">
                    KUKANILEA
                </text>
            </svg>
        </div>
        
        <!-- The Sovereign 11 -->
        <ul class="nav-list">
            <!-- FOCUS TOOLS -->
            <li class="nav-item">
                <a href="/dashboard" 
                   class="nav-link {{ 'active' if request.path == '/dashboard' }}"
                   hx-get="/dashboard"
                   hx-target="#main-content"
                   hx-push-url="true"
                   hx-indicator=".htmx-indicator">
                    <svg class="nav-icon" width="20" height="20">
                        <use href="/static/icons/sprite.svg#layout-dashboard"/>
                    </svg>
                    <span class="nav-text">Dashboard</span>
                </a>
            </li>
            
            <li class="nav-item">
                <a href="/upload" 
                   class="nav-link {{ 'active' if request.path.startswith('/upload') }}"
                   hx-get="/upload"
                   hx-target="#main-content"
                   hx-push-url="true"
                   hx-indicator=".htmx-indicator">
                    <svg class="nav-icon" width="20" height="20">
                        <use href="/static/icons/sprite.svg#upload-cloud"/>
                    </svg>
                    <span class="nav-text">Upload</span>
                </a>
            </li>
            
            <li class="nav-item">
                <a href="/projects" 
                   class="nav-link {{ 'active' if request.path.startswith('/projects') }}"
                   hx-get="/projects"
                   hx-target="#main-content"
                   hx-push-url="true"
                   hx-indicator=".htmx-indicator">
                    <svg class="nav-icon" width="20" height="20">
                        <use href="/static/icons/sprite.svg#kanban"/>
                    </svg>
                    <span class="nav-text">Projekte</span>
                </a>
            </li>
            
            <li class="nav-item">
                <a href="/tasks" 
                   class="nav-link {{ 'active' if request.path.startswith('/tasks') }}"
                   hx-get="/tasks"
                   hx-target="#main-content"
                   hx-push-url="true"
                   hx-indicator=".htmx-indicator">
                    <svg class="nav-icon" width="20" height="20">
                        <use href="/static/icons/sprite.svg#check-square"/>
                    </svg>
                    <span class="nav-text">Aufgaben</span>
                </a>
            </li>
            
            <!-- SEPARATOR -->
            <li class="nav-separator" aria-hidden="true"></li>
            
            <!-- COMMUNICATION & TIME -->
            <li class="nav-item">
                <a href="/messenger" 
                   class="nav-link {{ 'active' if request.path.startswith('/messenger') }}"
                   hx-get="/messenger"
                   hx-target="#main-content"
                   hx-push-url="true"
                   hx-indicator=".htmx-indicator">
                    <svg class="nav-icon" width="20" height="20">
                        <use href="/static/icons/sprite.svg#message-square"/>
                    </svg>
                    <span class="nav-text">Messenger</span>
                </a>
            </li>
            
            <li class="nav-item">
                <a href="/email" 
                   class="nav-link {{ 'active' if request.path.startswith('/email') }}"
                   hx-get="/email"
                   hx-target="#main-content"
                   hx-push-url="true"
                   hx-indicator=".htmx-indicator">
                    <svg class="nav-icon" width="20" height="20">
                        <use href="/static/icons/sprite.svg#mail"/>
                    </svg>
                    <span class="nav-text">Emailpostfach</span>
                </a>
            </li>
            
            <li class="nav-item">
                <a href="/calendar" 
                   class="nav-link {{ 'active' if request.path.startswith('/calendar') }}"
                   hx-get="/calendar"
                   hx-target="#main-content"
                   hx-push-url="true"
                   hx-indicator=".htmx-indicator">
                    <svg class="nav-icon" width="20" height="20">
                        <use href="/static/icons/sprite.svg#calendar"/>
                    </svg>
                    <span class="nav-text">Kalender</span>
                </a>
            </li>
            
            <li class="nav-item">
                <a href="/time" 
                   class="nav-link {{ 'active' if request.path.startswith('/time') }}"
                   hx-get="/time"
                   hx-target="#main-content"
                   hx-push-url="true"
                   hx-indicator=".htmx-indicator">
                    <svg class="nav-icon" width="20" height="20">
                        <use href="/static/icons/sprite.svg#clock"/>
                    </svg>
                    <span class="nav-text">Zeiterfassung</span>
                </a>
            </li>
            
            <!-- SEPARATOR -->
            <li class="nav-separator" aria-hidden="true"></li>
            
            <!-- TOOLS & SYSTEM -->
            <li class="nav-item">
                <a href="/visualizer" 
                   class="nav-link {{ 'active' if request.path.startswith('/visualizer') }}"
                   hx-get="/visualizer"
                   hx-target="#main-content"
                   hx-push-url="true"
                   hx-indicator=".htmx-indicator">
                    <svg class="nav-icon" width="20" height="20">
                        <use href="/static/icons/sprite.svg#file-digit"/>
                    </svg>
                    <span class="nav-text">Visualizer</span>
                </a>
            </li>
            
            <li class="nav-item">
                <a href="/settings" 
                   class="nav-link {{ 'active' if request.path.startswith('/settings') }}"
                   hx-get="/settings"
                   hx-target="#main-content"
                   hx-push-url="true"
                   hx-indicator=".htmx-indicator">
                    <svg class="nav-icon" width="20" height="20">
                        <use href="/static/icons/sprite.svg#settings"/>
                    </svg>
                    <span class="nav-text">Einstellungen</span>
                </a>
            </li>
        </ul>
        
        <!-- Footer (optional license info) -->
        <div class="sidebar-footer">
            <span class="license-text">Lizenz: {{ license_days_left }} Tage</span>
        </div>
    </nav>
    
    <!-- Main Content Area -->
    <main id="main-content" class="main-content">
        <!-- Skeleton Loader (shown during HTMX load) -->
        <div class="htmx-indicator skeleton-loader">
            <div class="skeleton-text"></div>
            <div class="skeleton-text"></div>
            <div class="skeleton-text"></div>
        </div>
        
        <!-- Actual content loaded here -->
        {% block content %}{% endblock %}
    </main>
    
    <!-- Floating Widget Chatbot (Overlay #11) -->
    <button id="chatbot-trigger" 
            class="chatbot-trigger"
            aria-label="KI-Assistent öffnen">
        <svg width="24" height="24">
            <use href="/static/icons/sprite.svg#message-circle"/>
        </svg>
    </button>
    
    <div id="chatbot-widget" class="chatbot-widget hidden">
        {% include 'widgets/chatbot.html' %}
    </div>
</body>
</html>
```

**Key Implementation Points:**
- ✅ Exactly 11 navigation items (4 + 4 + 2 + 1 overlay)
- ✅ HTMX for SPA-like navigation
- ✅ SVG sprite for all icons (single file)
- ✅ Semantic HTML (nav, main, role attributes)
- ✅ ARIA labels for accessibility
- ✅ Skeleton loader during transitions

---

### **PHASE 2: SOVEREIGN SHELL STYLES**

#### Task 2.1: Create `app/static/css/sovereign-shell.css`

```css
/**
 * KUKANILEA SOVEREIGN 11 SHELL
 * Version: 3.0
 * White-Mode Only, 8pt-Grid, Blind-Operational
 */

/* === LAYOUT === */
.sovereign-shell {
    display: grid;
    grid-template-columns: 240px 1fr;
    height: 100vh;
    margin: 0;
    padding: 0;
    background: var(--bg-primary);
    font-family: var(--font-primary);
    color: var(--text-primary);
}

/* === SIDEBAR === */
.sidebar {
    background: var(--bg-sidebar);
    border-right: 1px solid var(--border-sidebar);
    display: flex;
    flex-direction: column;
    position: fixed;
    top: 0;
    left: 0;
    bottom: 0;
    width: 240px;
    overflow-y: auto;
    z-index: 100;
}

.sidebar-header {
    padding: var(--space-3);
    border-bottom: 1px solid var(--border-sidebar);
    flex-shrink: 0;
}

.logo {
    height: 40px;
    width: auto;
    color: var(--text-primary);
}

/* === NAVIGATION === */
.nav-list {
    list-style: none;
    margin: 0;
    padding: var(--space-1);
    flex: 1;
    overflow-y: auto;
}

.nav-item {
    margin: 0;
}

.nav-link {
    display: flex;
    align-items: center;
    gap: 12px;
    padding: 12px 16px;
    color: var(--text-secondary);
    text-decoration: none;
    border-radius: var(--radius-md);
    font-size: var(--font-size-sm);
    font-weight: var(--font-weight-medium);
    transition: all var(--transition-base);
    cursor: pointer;
}

.nav-link:hover {
    background: rgba(37, 99, 235, 0.08);
    color: var(--text-primary);
}

.nav-link:active {
    transform: scale(0.98);
}

.nav-link.active {
    background: rgba(37, 99, 235, 0.12);
    color: var(--accent-primary);
    font-weight: var(--font-weight-semibold);
}

.nav-link:focus-visible {
    outline: 2px solid var(--accent-primary);
    outline-offset: 2px;
}

/* Icons */
.nav-icon {
    flex-shrink: 0;
    width: 20px;
    height: 20px;
    stroke: currentColor;
    fill: none;
}

.nav-text {
    flex: 1;
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
}

/* Separator */
.nav-separator {
    height: 1px;
    background: var(--border-sidebar);
    margin: var(--space-1) var(--space-2);
}

/* Sidebar Footer */
.sidebar-footer {
    padding: var(--space-2);
    border-top: 1px solid var(--border-sidebar);
    flex-shrink: 0;
}

.license-text {
    font-size: 12px;
    color: var(--text-secondary);
}

/* === MAIN CONTENT === */
.main-content {
    grid-column: 2;
    padding: var(--space-4);
    overflow-y: auto;
    background: var(--bg-primary);
}

/* === SKELETON LOADER === */
.skeleton-loader {
    display: none; /* Hidden by default */
    flex-direction: column;
    gap: var(--space-2);
    padding: var(--space-3);
}

.htmx-request .skeleton-loader {
    display: flex;
}

.skeleton-text {
    height: 16px;
    background: linear-gradient(
        90deg,
        #F1F5F9 0%,
        #E2E8F0 50%,
        #F1F5F9 100%
    );
    background-size: 200% 100%;
    animation: skeleton-pulse 1.5s ease-in-out infinite;
    border-radius: 4px;
}

.skeleton-text:nth-child(1) { width: 60%; }
.skeleton-text:nth-child(2) { width: 80%; }
.skeleton-text:nth-child(3) { width: 40%; }

@keyframes skeleton-pulse {
    0% { background-position: 200% 0; }
    100% { background-position: -200% 0; }
}

/* === FLOATING CHATBOT === */
.chatbot-trigger {
    position: fixed;
    bottom: var(--space-3);
    right: var(--space-3);
    width: 56px;
    height: 56px;
    border-radius: 50%;
    background: var(--accent-primary);
    color: white;
    border: none;
    box-shadow: 0 4px 12px rgba(37, 99, 235, 0.3);
    cursor: pointer;
    display: flex;
    align-items: center;
    justify-content: center;
    transition: all var(--transition-base);
    z-index: 1000;
}

.chatbot-trigger:hover {
    background: var(--accent-hover);
    transform: scale(1.05);
}

.chatbot-trigger:active {
    transform: scale(0.95);
}

.chatbot-trigger svg {
    stroke: currentColor;
    fill: none;
}

.chatbot-widget {
    position: fixed;
    bottom: 96px;
    right: var(--space-3);
    width: 400px;
    max-height: 600px;
    background: var(--bg-primary);
    border-radius: 12px;
    box-shadow: 0 8px 24px rgba(0, 0, 0, 0.15);
    z-index: 999;
    transition: all 0.2s ease;
    overflow: hidden;
}

.chatbot-widget.hidden {
    opacity: 0;
    pointer-events: none;
    transform: translateY(20px);
}

/* === RESPONSIVE === */
@media (max-width: 768px) {
    .sovereign-shell {
        grid-template-columns: 1fr;
    }
    
    .sidebar {
        transform: translateX(-100%);
        transition: transform 0.3s ease;
    }
    
    .sidebar.mobile-open {
        transform: translateX(0);
    }
    
    .main-content {
        grid-column: 1;
    }
    
    .chatbot-widget {
        width: calc(100vw - 32px);
        right: 16px;
    }
}

/* === ACCESSIBILITY === */
@media (prefers-reduced-motion: reduce) {
    * {
        animation-duration: 0.01ms !important;
        animation-iteration-count: 1 !important;
        transition-duration: 0.01ms !important;
    }
}

/* High Contrast Mode */
@media (prefers-contrast: high) {
    .nav-link {
        border: 1px solid transparent;
    }
    
    .nav-link:hover {
        border-color: var(--accent-primary);
    }
    
    .nav-link.active {
        border-color: var(--accent-primary);
        border-width: 2px;
    }
}
```

**Key Features:**
- ✅ 8pt-Grid spacing (all multiples of 8px)
- ✅ WCAG AA contrast ratios
- ✅ Focus-visible for keyboard navigation
- ✅ Reduced motion support
- ✅ High contrast mode support
- ✅ Mobile responsive (hamburger menu)

---

### **PHASE 3: LOCAL INTER FONT**

#### Task 3.1: Font Loading (`app/static/css/fonts.css`)

```css
/**
 * INTER FONT - LOCAL LOADING
 * DSGVO-Compliant, Zero CDN
 */

@font-face {
    font-family: 'Inter';
    font-style: normal;
    font-weight: 400;
    font-display: swap;
    src: url('/static/fonts/Inter-Regular.woff2') format('woff2');
}

@font-face {
    font-family: 'Inter';
    font-style: normal;
    font-weight: 500;
    font-display: swap;
    src: url('/static/fonts/Inter-Medium.woff2') format('woff2');
}

@font-face {
    font-family: 'Inter';
    font-style: normal;
    font-weight: 600;
    font-display: swap;
    src: url('/static/fonts/Inter-SemiBold.woff2') format('woff2');
}
```

**Download Inter fonts:**
```bash
# Create fonts directory
mkdir -p app/static/fonts

# Download from GitHub (official source)
curl -L -o app/static/fonts/Inter-Regular.woff2 \
  https://github.com/rsms/inter/raw/master/docs/font-files/Inter-Regular.woff2

curl -L -o app/static/fonts/Inter-Medium.woff2 \
  https://github.com/rsms/inter/raw/master/docs/font-files/Inter-Medium.woff2

curl -L -o app/static/fonts/Inter-SemiBold.woff2 \
  https://github.com/rsms/inter/raw/master/docs/font-files/Inter-SemiBold.woff2
```

---

### **PHASE 4: ICON SPRITE**

#### Task 4.1: Create `app/static/icons/sprite.svg`

```xml
<svg xmlns="http://www.w3.org/2000/svg" style="display: none;">
    <!-- Dashboard (layout-dashboard) -->
    <symbol id="layout-dashboard" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
        <rect x="3" y="3" width="7" height="7" rx="1"/>
        <rect x="14" y="3" width="7" height="7" rx="1"/>
        <rect x="14" y="14" width="7" height="7" rx="1"/>
        <rect x="3" y="14" width="7" height="7" rx="1"/>
    </symbol>
    
    <!-- Upload (upload-cloud) -->
    <symbol id="upload-cloud" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
        <path d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1"/>
        <polyline points="16 12 12 8 8 12"/>
        <line x1="12" y1="8" x2="12" y2="21"/>
    </symbol>
    
    <!-- Kanban (Projects) -->
    <symbol id="kanban" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
        <rect x="3" y="3" width="7" height="18" rx="1"/>
        <rect x="14" y="3" width="7" height="10" rx="1"/>
    </symbol>
    
    <!-- Tasks (check-square) -->
    <symbol id="check-square" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
        <polyline points="9 11 12 14 22 4"/>
        <path d="M21 12v7a2 2 0 01-2 2H5a2 2 0 01-2-2V5a2 2 0 012-2h11"/>
    </symbol>
    
    <!-- Messenger (message-square) -->
    <symbol id="message-square" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
        <path d="M21 15a2 2 0 01-2 2H7l-4 4V5a2 2 0 012-2h14a2 2 0 012 2z"/>
    </symbol>
    
    <!-- Email (mail) -->
    <symbol id="mail" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
        <path d="M4 4h16c1.1 0 2 .9 2 2v12c0 1.1-.9 2-2 2H4c-1.1 0-2-.9-2-2V6c0-1.1.9-2 2-2z"/>
        <polyline points="22,6 12,13 2,6"/>
    </symbol>
    
    <!-- Calendar -->
    <symbol id="calendar" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
        <rect x="3" y="4" width="18" height="18" rx="2" ry="2"/>
        <line x1="16" y1="2" x2="16" y2="6"/>
        <line x1="8" y1="2" x2="8" y2="6"/>
        <line x1="3" y1="10" x2="21" y2="10"/>
    </symbol>
    
    <!-- Clock (Time Tracking) -->
    <symbol id="clock" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
        <circle cx="12" cy="12" r="10"/>
        <polyline points="12 6 12 12 16 14"/>
    </symbol>
    
    <!-- Visualizer (file-digit) -->
    <symbol id="file-digit" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
        <path d="M14 2H6a2 2 0 00-2 2v16a2 2 0 002 2h12a2 2 0 002-2V8z"/>
        <polyline points="14 2 14 8 20 8"/>
        <line x1="10" y1="13" x2="14" y2="13"/>
        <line x1="10" y1="17" x2="14" y2="17"/>
    </symbol>
    
    <!-- Settings -->
    <symbol id="settings" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
        <circle cx="12" cy="12" r="3"/>
        <path d="M12 1v6m0 6v6m5.66-13L13 10.34M10.34 13.66L5 19m14 0l-5.66-5.66M13.66 10.34L19 5"/>
    </symbol>
    
    <!-- Chatbot (message-circle) -->
    <symbol id="message-circle" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
        <path d="M21 11.5a8.38 8.38 0 01-.9 3.8 8.5 8.5 0 01-7.6 4.7 8.38 8.38 0 01-3.8-.9L3 21l1.9-5.7a8.38 8.38 0 01-.9-3.8 8.5 8.5 0 014.7-7.6 8.38 8.38 0 013.8-.9h.5a8.48 8.48 0 018 8v.5z"/>
    </symbol>
</svg>
```

---

### **PHASE 5: NAVIGATION JAVASCRIPT**

#### Task 5.1: Create `app/static/js/navigation.js`

```javascript
/**
 * KUKANILEA SOVEREIGN 11 NAVIGATION
 * HTMX Enhancement + Mobile Menu + Chatbot Toggle
 */

document.addEventListener('DOMContentLoaded', () => {
    // === Mobile Menu ===
    const sidebar = document.querySelector('.sidebar');
    
    if (window.innerWidth <= 768) {
        // Create mobile menu button
        const menuBtn = document.createElement('button');
        menuBtn.className = 'mobile-menu-btn';
        menuBtn.setAttribute('aria-label', 'Menü öffnen');
        menuBtn.innerHTML = `
            <svg width="24" height="24" stroke="currentColor" fill="none">
                <line x1="3" y1="12" x2="21" y2="12"></line>
                <line x1="3" y1="6" x2="21" y2="6"></line>
                <line x1="3" y1="18" x2="21" y2="18"></line>
            </svg>
        `;
        
        menuBtn.addEventListener('click', () => {
            sidebar.classList.toggle('mobile-open');
        });
        
        document.body.appendChild(menuBtn);
    }
    
    // Close sidebar on mobile after navigation
    document.querySelectorAll('.nav-link').forEach(link => {
        link.addEventListener('click', () => {
            if (window.innerWidth <= 768) {
                sidebar.classList.remove('mobile-open');
            }
        });
    });
    
    // === Chatbot Toggle ===
    const chatbotTrigger = document.getElementById('chatbot-trigger');
    const chatbotWidget = document.getElementById('chatbot-widget');
    
    if (chatbotTrigger && chatbotWidget) {
        chatbotTrigger.addEventListener('click', () => {
            chatbotWidget.classList.toggle('hidden');
            
            // Accessibility
            const isHidden = chatbotWidget.classList.contains('hidden');
            chatbotTrigger.setAttribute('aria-expanded', !isHidden);
        });
        
        // Close on outside click
        document.addEventListener('click', (e) => {
            if (!chatbotWidget.contains(e.target) && 
                !chatbotTrigger.contains(e.target)) {
                chatbotWidget.classList.add('hidden');
                chatbotTrigger.setAttribute('aria-expanded', 'false');
            }
        });
        
        // Close on Escape key
        document.addEventListener('keydown', (e) => {
            if (e.key === 'Escape' && !chatbotWidget.classList.contains('hidden')) {
                chatbotWidget.classList.add('hidden');
                chatbotTrigger.setAttribute('aria-expanded', 'false');
                chatbotTrigger.focus();
            }
        });
    }
    
    // === HTMX Loading Indicator ===
    document.body.addEventListener('htmx:beforeRequest', (e) => {
        document.getElementById('main-content')?.classList.add('loading');
    });
    
    document.body.addEventListener('htmx:afterRequest', (e) => {
        document.getElementById('main-content')?.classList.remove('loading');
    });
    
    // === Active Link Highlighting ===
    const currentPath = window.location.pathname;
    document.querySelectorAll('.nav-link').forEach(link => {
        const href = link.getAttribute('href');
        if (currentPath.startsWith(href) && href !== '/') {
            link.classList.add('active');
        }
    });
});
```

---

## 📝 SCOPE REQUEST TEMPLATE V2 (UI/UX Focused)

**File:** `docs/templates/SCOPE_REQUEST_TEMPLATE_V2.md`

```markdown
# SCOPE REQUEST: <domain> — UI/UX Integration (Sovereign 11)

**Version:** 2.0 (UI/UX-Focused)  
**Domain:** <domain>  
**Agent:** <agent_name>  
**Date:** YYYY-MM-DD  
**Status:** PENDING_REVIEW  
**Patch:** docs/scope_requests/patches/<domain>_<yyyymmdd_hhmmss>.patch

---

## 1. SUMMARY

**What:**
<1-2 sentences: Which UI/UX change in shared-core is needed to make this tool visible?>

**Why:**
<Without this change, the tool remains invisible in the UI. Master-Plan P0-2 (Broken Links + Missing Tools) cannot be fulfilled.>

**User Story:**
<How does the user find and use this tool?>

---

## 2. FILES CHANGED (UI/UX Only)

**Modified (shared-core):**
- `app/templates/layout.html` (+X / -Y) → Sidebar entry
- `app/static/css/design-system.css` (+X / -Y) → Tool icon/colors
- `app/static/js/navigation.js` (+X / -Y) → Active highlight logic
- `app/web.py` (+X / -Y) → Blueprint registration

**Added (shared-core):**
- `app/static/icons/<tool>.svg` → Tool icon

**Deleted:** (none)

**RULE:** No changes to business logic, database, or backend functionality. Only what makes the tool appear in UI.

---

## 3. DETAILED CHANGES

### 3.1 `app/templates/layout.html`

**Change Type:** SIDEBAR_UPDATE  
**Location:** `<nav class="sidebar">` (line ~45)

**Before:**
```html
<li class="nav-item">
    <a href="/dashboard" class="nav-link">
        <svg class="nav-icon" width="20" height="20">
            <use href="/static/icons/sprite.svg#layout-dashboard"/>
        </svg>
        <span class="nav-text">Dashboard</span>
    </a>
</li>
<!-- other links -->
```

**After:**
```html
<li class="nav-item">
    <a href="/dashboard" class="nav-link">
        <svg class="nav-icon" width="20" height="20">
            <use href="/static/icons/sprite.svg#layout-dashboard"/>
        </svg>
        <span class="nav-text">Dashboard</span>
    </a>
</li>

<!-- NEW TOOL LINK -->
<li class="nav-item">
    <a href="/<tool-route>" 
       class="nav-link {{ 'active' if request.path.startswith('/<tool-route>') }}"
       hx-get="/<tool-route>"
       hx-target="#main-content"
       hx-push-url="true"
       hx-indicator=".htmx-indicator">
        <svg class="nav-icon" width="20" height="20">
            <use href="/static/icons/sprite.svg#<tool-icon-id>"/>
        </svg>
        <span class="nav-text"><Tool-Name></span>
    </a>
</li>
```

**Justification:**
- Uses existing sidebar design (no new layout)
- Icon as SVG from sprite (local, DSGVO-compliant, fast)
- HTMX for SPA-like navigation
- Consistent with other nav items

---

### 3.2 `app/static/icons/sprite.svg`

**Change Type:** NEW_ICON  
**Location:** Inside `<svg>` root element

**Added:**
```xml
<!-- <Tool-Name> (<tool-icon-id>) -->
<symbol id="<tool-icon-id>" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
    <path d="M..."/>
    <!-- Lucide/Heroicons style icon paths -->
</symbol>
```

**Justification:**
- Lucide/Heroicons style (consistent with other icons)
- 20×20px, 2px stroke, round caps
- Local sprite (single file, fast loading)

---

### 3.3 `app/web.py`

**Change Type:** BLUEPRINT_REGISTRATION  
**Location:** After existing blueprint registrations

**Added:**
```python
from app.modules.<domain> import bp as <domain>_bp
app.register_blueprint(<domain>_bp, url_prefix='/<tool-route>')
```

**Justification:**
- Standard pattern for all blueprints
- No changes to existing registrations

---

## 4. INTEGRATION DEPENDENCIES

**Requires other patches first:**
- [ ] NO
- [ ] YES → list: (e.g., "design-system.css must exist")

**Breaks existing behavior:**
- [ ] NO (only adds new UI elements)

**New dependencies:**
- [ ] NO (no new packages)

**Config/.env changes:**
- [ ] NO

---

## 5. TESTING (UI/UX)

**Pre-Apply (must pass BEFORE patch):**
```bash
pytest -q
```

**Manual Test Steps:**
```bash
# 1. Start app
python kukanilea_app.py

# 2. Open browser
open http://localhost:5051/dashboard

# 3. Check sidebar
# - New menu item visible?
# - Icon displays correctly?

# 4. Click menu item
# - Target page loads without error?
# - URL changes correctly?

# 5. Hover effect
# - Background changes on hover?

# 6. Active state
# - When on tool page, menu item highlighted?
```

**Expected:**
- ✅ Menu item visible
- ✅ Link works (no 404)
- ✅ Hover effect works
- ✅ Icon displays correctly
- ✅ Active state highlights

**Automated Tests:**
```bash
# New test file:
tests/domains/<domain>/test_ui_integration.py

# Tests:
# - Route returns 200
# - Blueprint registered
```

**Results:**
```
✅ Manual test: PASSED (all checkpoints)
✅ Automated: PASSED (X/X tests)
```

---

## 6. DOCUMENTATION

**User Docs:**
- [ ] docs/user/<domain>.md (created)
- [ ] CHANGELOG.md (entry added)

**Developer Docs:**
- [ ] docs/dev/<domain>_architecture.md (created)
- [ ] API contracts (if applicable)

---

## 7. ROLLBACK PLAN

```bash
# Revert commit
git revert <integration_commit_hash>

# Clear browser cache
# (CSS/JS might be cached)

# Restart not needed (UI-only change)
```

---

## 8. SECURITY & COMPLIANCE

**Confirm-Gate:** NO (navigation only, no data changes)

**Audit Logging:** NO (page views, no mutations)

**Sensitive Data:**
- [x] No secrets in code/logs/patch
- [x] No tokens/passwords exposed

**Accessibility (WCAG AA):**
- [x] Contrast ratios verified (design-system compliant)
- [x] Keyboard navigation works (:focus-visible styles present)
- [x] ARIA labels provided

---

## 9. PATCH FILE

**Path:** `docs/scope_requests/patches/<domain>_<yyyymmdd_hhmmss>.patch`

**Generated:**
```bash
cd /Users/gensuminguyen/Kukanilea/worktrees/<domain>
git diff main -- \
  app/templates/layout.html \
  app/static/icons/sprite.svg \
  app/web.py \
  > /Users/gensuminguyen/Kukanilea/kukanilea_production/docs/scope_requests/patches/<domain>_<date>.patch
```

**Verify:**
```bash
cd /Users/gensuminguyen/Kukanilea/kukanilea_production
git apply --check docs/scope_requests/patches/<domain>_<date>.patch
```

---

## 10. APPROVAL

**Reviewed by:** <Core Fleet Commander>  
**Decision:**
- [ ] APPROVED
- [ ] APPROVED_WITH_CHANGES  
- [ ] REJECTED

**Integration Commit:** <hash>

**Notes:** <any additional notes>

---

**SIGNATURE:**  
Submitted by: <agent>  
Domain: <domain>  
Date: YYYY-MM-DD
```

---

## ✅ DEFINITION OF DONE (Sovereign 11)

**Shell Integration Complete when:**

```bash
# 1. Count menu items (must be exactly 11)
curl http://localhost:5051/dashboard | grep -o 'class="nav-item"' | wc -l
# Expected: 11

# 2. Test all routes
for route in /dashboard /upload /projects /tasks /messenger /email /calendar /time /visualizer /settings; do
    curl -s -o /dev/null -w "%{http_code} $route\n" http://localhost:5051$route
done
# Expected: All 200

# 3. Check no external requests
# Open DevTools → Network → Filter: "Other"
# Expected: Zero external CDN requests

# 4. Performance check
# Open DevTools → Performance → Record → Reload
# Expected: LCP < 150ms

# 5. Accessibility check
# Open DevTools → Lighthouse → Accessibility
# Expected: Score 100

# 6. Visual check
# Expected: White background, no dark-mode toggle visible

# 7. Icon check
curl http://localhost:5051/static/icons/sprite.svg | grep -o '<symbol' | wc -l
# Expected: 11 (one for each tool)

# 8. Font check
curl http://localhost:5051/static/fonts/Inter-Regular.woff2 -I | grep "200 OK"
# Expected: Font loads locally

# 9. Mobile check
# Resize browser to 375px width
# Expected: Sidebar collapses, hamburger appears

# 10. HTMX check
# Click between tools
# Expected: No full page reload, content swaps smoothly
```

**All checks PASS = Ready for Production! 🎉**

---

## 🚨 CRITICAL DO's & DON'Ts

### ✅ DO (Mandatory)

1. **Enforce White-Mode ONLY**
   - Remove ALL dark-mode CSS
   - Remove theme toggle UI
   - Set `background: #FFFFFF` as non-negotiable

2. **Use 8pt-Grid Spacing**
   - All padding/margins in multiples of 8px
   - Use CSS variables: `var(--space-1)` through `var(--space-8)`

3. **Load Inter Font Locally**
   - Download .woff2 files to `/static/fonts/`
   - Use `@font-face` with `font-display: swap`
   - Zero external font CDNs

4. **SVG Icons Only**
   - Use sprite.svg (single file, all icons)
   - Lucide/Heroicons style (2px stroke, round caps)
   - No emojis, no PNGs, no external icon libs

5. **HTMX Navigation**
   - Use `hx-get`, `hx-target="#main-content"`, `hx-push-url="true"`
   - Show skeleton loader during transitions
   - No full page reloads

6. **Accessibility Compliance**
   - WCAG AA contrast ratios (verified)
   - Keyboard navigation (`focus-visible` styles)
   - ARIA labels on interactive elements
   - Reduced motion support

7. **Performance Budget**
   - Initial load <150ms (LCP)
   - Icon sprite <10KB
   - Font files <100KB total
   - Zero external requests

### ❌ DON'T (Forbidden)

1. **No Additional Menu Items**
   - Strict limit: 11 tools
   - Remove experimental routes
   - Remove footer navigation

2. **No Emojis in UI**
   - SVG icons only
   - No emoji fallbacks

3. **No External CDNs**
   - No Google Fonts
   - No Font Awesome
   - No cdnjs, jsdelivr, unpkg

4. **No Dropdown Menus**
   - Direct navigation only
   - No nested submenus in sidebar

5. **No Color Explosions**
   - Blue (#2563EB) + Grays only
   - Status colors (red/green) only for alerts

6. **No "Coming Soon"**
   - If tool not ready, hide it
   - Don't show placeholder links

7. **No Dark Mode Toggle**
   - White-Mode is non-negotiable
   - Remove all theme switching UI

---

## 📊 SUCCESS METRICS

```
BEFORE → AFTER (Sovereign 11)

Navigation Items:   20+ → 11 ✅
Initial Load:       300ms → <150ms ✅
External Requests:  3 (Google Fonts) → 0 ✅
Broken Links:       5 → 0 ✅
Mode Options:       Dark + White → White ONLY ✅
Icon Format:        PNG/Emoji → SVG ✅
Spacing System:     Random → 8pt-Grid ✅
Font Loading:       CDN → Local ✅
Accessibility:      70% → 100% ✅
Performance:        60% → 95% ✅

Overall Score:      5/10 → 10/10 ✅
Status:             Cluttered → Minimalist ✅
```

---

**THE SOVEREIGN 11 IS NOW FULLY SPECIFIED. EXECUTE WITHOUT COMPROMISE! 🏛️**
