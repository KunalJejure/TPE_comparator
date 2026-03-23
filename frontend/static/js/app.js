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
        console.log('[App] Attempting to restore view:', savedView);

        // Only switch if it's a valid view
        if (savedView && viewTitles[savedView]) {
            // Check if we are arguably already on the view (avoid flicker if possible, though switchView handles toggles)
            // But we must run switchView to trigger specific load functions (like loadRequalifications)
            switchView(savedView);
        } else {
            console.log('[App] No valid saved view found, staying on default.');
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
    const sunIcon = document.getElementById('themeIconSun');
    const moonIcon = document.getElementById('themeIconMoon');
    
    if (sunIcon && moonIcon) {
        if (theme === 'light') {
            sunIcon.style.display = 'none';
            moonIcon.style.display = 'block';
        } else {
            sunIcon.style.display = 'block';
            moonIcon.style.display = 'none';
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

// Close on Esc key
document.addEventListener('keydown', function (event) {
    if (event.key === "Escape") {
        closeImageModal();
    }
});
