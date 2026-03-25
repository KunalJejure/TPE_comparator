// ================================================================
// app.js — Core Application Logic
// Handles: Icon init, View switching, Sidebar toggle
// ================================================================

// --- Init Icons ---
lucide.createIcons();

// ================================================================
// VIEW SWITCHING
// ================================================================
const viewTitles = {
    dashboard: { title: 'Dashboard', subtitle: 'Compare PDFs and track differences. Your AI-powered document QA tool.' },
    compare: { title: 'Compare PDFs', subtitle: 'Upload original and revised documents for side-by-side analysis.' },
    results: { title: 'Comparison Results', subtitle: 'Side-by-side text diff and visual comparison.' },
    reports: { title: 'Reports & Analytics', subtitle: 'Detailed insights into your comparison history.' },
    requalifications: { title: 'Requalifications', subtitle: 'Batch compare multiple PDF pairs simultaneously.' },
    scopeValidator: { title: 'Scope Validator', subtitle: 'Verify scope and deliverables coverage in your validation plan.' },
    settings: { title: 'Settings', subtitle: 'Manage application preferences and security settings.' },
};

function switchView(viewName) {
    // Hide all views
    document.querySelectorAll('.view').forEach(v => v.classList.remove('active'));
    // Show target view
    const target = document.getElementById('view-' + viewName);
    if (target) target.classList.add('active');

    // Update nav
    document.querySelectorAll('.nav-item[data-view]').forEach(n => n.classList.remove('active'));
    const navItem = document.querySelector(`.nav-item[data-view="${viewName}"]`);
    if (navItem) navItem.classList.add('active');

    // Update header
    const info = viewTitles[viewName] || viewTitles.dashboard;
    const titleEl = document.getElementById('pageTitle');
    const subEl = document.getElementById('pageSubtitle');

    if (titleEl) titleEl.textContent = info.title;
    if (subEl) subEl.textContent = info.subtitle;

    // Save current view
    localStorage.setItem('activeView', viewName);

    if (viewName === 'reports') {
        if (typeof loadReports === 'function') loadReports();
    } else if (viewName === 'requalifications') {
        if (typeof loadRequalifications === 'function') loadRequalifications();
    }

    lucide.createIcons();

    // Auto-close mobile sidebar when navigating
    if (window.innerWidth <= 1024) {
        const sidebar = document.getElementById('sidebar');
        if (sidebar && sidebar.classList.contains('mobile-open')) {
            toggleMobileSidebar();
        }
    }
}

// Restore view on load
function restoreSavedView() {
    try {
        const savedView = localStorage.getItem('activeView');
        // Do NOT restore the results view — it requires live data that won't be present on fresh load
        if (savedView && viewTitles[savedView] && savedView !== 'results') {
            switchView(savedView);
        }
    } catch (err) {
        console.error('[App] Failed to restore view:', err);
    }
}

// Run restoration logic
if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', restoreSavedView);
} else {
    // DOM already ready
    restoreSavedView();
}

// ================================================================
// SIDEBAR TOGGLE LOGIC
// ================================================================
function toggleSidebar() {
    const sidebar = document.getElementById('sidebar');
    const main = document.getElementById('mainContent');
    sidebar.classList.toggle('collapsed');
    main.classList.toggle('collapsed');

    // Re-render icons if needed ensuring everything is fine
    lucide.createIcons();
}

// ================================================================
// MOBILE SIDEBAR TOGGLE
// ================================================================
function toggleMobileSidebar() {
    const sidebar = document.getElementById('sidebar');
    if (!sidebar) return;

    // Create or find overlay
    let overlay = document.getElementById('mobileOverlay');
    if (!overlay) {
        overlay = document.createElement('div');
        overlay.id = 'mobileOverlay';
        overlay.style.cssText = 'display: none; position: fixed; top: 0; left: 0; right: 0; bottom: 0; background: rgba(0,0,0,0.4); z-index: 9998; opacity: 0; transition: opacity 0.3s ease;';
        overlay.onclick = toggleMobileSidebar;
        document.body.appendChild(overlay);
    }

    const isOpen = sidebar.classList.toggle('mobile-open');
    
    if (isOpen) {
        overlay.style.display = 'block';
        // forced reflow for transition
        window.getComputedStyle(overlay).opacity;
        overlay.style.opacity = '1';
        document.body.style.overflow = 'hidden';
    } else {
        overlay.style.opacity = '0';
        setTimeout(() => {
            overlay.style.display = 'none';
        }, 300);
        document.body.style.overflow = '';
    }
}

// ================================================================
// MODAL LOGIC
// ================================================================
function openImageModal(src, caption) {
    const modal = document.getElementById('imageModal');
    const modalImg = document.getElementById('modalImage');
    const captionText = document.getElementById('modalCaption');

    modal.style.display = "flex";
    modalImg.src = src;
    if (captionText) captionText.textContent = caption;

    // Prevent body scrolling
    document.body.style.overflow = 'hidden';
}

function closeImageModal() {
    const modal = document.getElementById('imageModal');
    modal.style.display = "none";
    // Restore body scrolling
    document.body.style.overflow = '';
}

// ================================================================
// THEME TOGGLE (Dark/Light Mode)
// ================================================================
function toggleTheme() {
    const html = document.documentElement;
    const currentTheme = html.getAttribute('data-theme') || 'dark';
    const newTheme = currentTheme === 'dark' ? 'light' : 'dark';
    
    html.setAttribute('data-theme', newTheme);
    localStorage.setItem('app-theme', newTheme);
    
    updateThemeIcons(newTheme);
}

function updateThemeIcons(theme) {
    const sunIcon = document.getElementById('settingsThemeIconSun');
    const moonIcon = document.getElementById('settingsThemeIconMoon');
    const label = document.getElementById('themeStatusLabel');
    
    if (sunIcon && moonIcon) {
        if (theme === 'light') {
            sunIcon.style.display = 'block';
            moonIcon.style.display = 'none';
            if (label) label.textContent = 'Light Mode Active';
        } else {
            sunIcon.style.display = 'none';
            moonIcon.style.display = 'block';
            if (label) label.textContent = 'Dark Mode Active';
        }
    }
    // Re-init icons to be safe
    if (window.lucide) lucide.createIcons();
}

function initTheme() {
    const savedTheme = localStorage.getItem('app-theme') || 'dark';
    document.documentElement.setAttribute('data-theme', savedTheme);
    updateThemeIcons(savedTheme);
}

// Run init
initTheme();

// ================================================================
// TOAST NOTIFICATIONS
// ================================================================
function showToast(message, type = 'info') {
    const toastContainer = document.getElementById('toastContainer');
    if (!toastContainer) {
        const container = document.createElement('div');
        container.id = 'toastContainer';
        container.style.cssText = `
            position: fixed;
            bottom: 30px;
            right: 30px;
            z-index: 10000;
            display: flex;
            flex-direction: column;
            gap: 12px;
        `;
        document.body.appendChild(container);
    }

    const toast = document.createElement('div');
    toast.className = `toast toast-${type}`;
    
    // Style the toast
    let bgColor = 'var(--accent)';
    let icon = 'info';
    if (type === 'success') {
        bgColor = 'var(--success)';
        icon = 'check-circle';
    } else if (type === 'danger' || type === 'error') {
        bgColor = 'var(--danger)';
        icon = 'alert-circle';
    } else if (type === 'warning') {
        bgColor = 'var(--warning)';
        icon = 'alert-triangle';
    }

    toast.style.cssText = `
        background: var(--card);
        color: var(--text-primary);
        padding: 16px 24px;
        border-radius: var(--radius-sm);
        box-shadow: 0 10px 40px -10px rgba(0,0,0,0.15), 0 0 0 1px var(--card-border);
        display: flex;
        align-items: center;
        gap: 14px;
        min-width: 300px;
        max-width: 450px;
        transform: translateX(100px);
        opacity: 0;
        transition: all 0.4s cubic-bezier(0.175, 0.885, 0.32, 1.275);
        border-left: 4px solid ${bgColor};
    `;

    toast.innerHTML = `
        <i data-lucide="${icon}" style="width:20px; height:20px; color:${bgColor}"></i>
        <div style="flex:1; font-size:0.92rem; font-weight:500;">${message}</div>
        <button onclick="this.parentElement.remove()" style="background:none; border:none; color:var(--text-muted); cursor:pointer; padding:4px;">
            <i data-lucide="x" style="width:16px; height:16px;"></i>
        </button>
    `;

    document.getElementById('toastContainer').appendChild(toast);
    if (window.lucide) lucide.createIcons();

    // Trigger animation
    setTimeout(() => {
        toast.style.transform = 'translateX(0)';
        toast.style.opacity = '1';
    }, 10);

    
    // Auto-remove
    setTimeout(() => {
        toast.style.transform = 'translateX(100px)';
        toast.style.opacity = '0';
        setTimeout(() => toast.remove(), 400);
    }, 4000);
}


// ================================================================
// ACCORDION / EXPANDABLE LOGIC
// ================================================================
function toggleAccordion(event, element) {
    // Prevent toggle if clicking interactive elements inside
    const interactive = event.target.closest('button, a, input, select, .toggle-switch-label, range');
    if (interactive && !element.contains(interactive)) return; 
    if (interactive) return;

    // Toggle current
    const isActive = element.classList.contains('active');
    
    // Optional: Close others in the same list
    const list = element.closest('.accordion-list') || element.closest('.tile-grid');
    if (list) {
        list.querySelectorAll('.accordion-item, .action-tile').forEach(item => {
            item.classList.remove('active');
        });
    }

    if (!isActive) {
        element.classList.add('active');
    }
}


