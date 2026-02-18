// ================================================================
// auth.js — SSO Login / Logout / Session Logic
// ================================================================

/**
 * Check SSO auth status from backend on page load.
 * Shows / hides the login page based on session state.
 */
async function checkAuthStatus() {
    try {
        const res = await fetch('/auth/status');
        const data = await res.json();

        const loginPage = document.getElementById('loginPage');
        const appContainer = document.getElementById('app-container');
        const ssoSection = document.getElementById('ssoSection');
        const fallbackLogin = document.getElementById('fallbackLogin');

        if (data.authenticated) {
            // User is SSO-authenticated — show the app
            loginPage.classList.add('hidden');
            loginPage.style.display = 'none';
            appContainer.style.display = 'flex';
            void appContainer.offsetWidth;
            appContainer.classList.add('visible');

            // Store user info for in-app use
            if (data.user) {
                localStorage.setItem('isLoggedIn', 'true');
                localStorage.setItem('userName', data.user.name || '');
                localStorage.setItem('userEmail', data.user.email || '');
            }

            // Update UI with user info
            updateUserInfo(data.user);

            if (typeof lucide !== 'undefined') lucide.createIcons();
            return;
        }

        // Not SSO-authenticated — check if SSO is enabled
        if (data.sso_enabled) {
            // Show SSO button, hide fallback form
            if (ssoSection) ssoSection.style.display = 'block';
            if (fallbackLogin) fallbackLogin.style.display = 'none';
        } else {
            // SSO not configured — show dev-mode fallback form
            if (ssoSection) ssoSection.style.display = 'none';
            if (fallbackLogin) fallbackLogin.style.display = 'block';

            // Check localStorage for dev-mode sessions
            const isLoggedIn = localStorage.getItem('isLoggedIn');
            if (isLoggedIn === 'true') {
                loginPage.classList.add('hidden');
                loginPage.style.display = 'none';
                appContainer.style.display = 'flex';
                void appContainer.offsetWidth;
                appContainer.classList.add('visible');
                if (typeof lucide !== 'undefined') lucide.createIcons();
                return;
            }
        }

        // Show login page
        loginPage.style.display = 'flex';
        if (typeof lucide !== 'undefined') lucide.createIcons();

    } catch (err) {
        console.warn('Auth status check failed, falling back to localStorage:', err);
        // Fallback to old localStorage-based logic
        fallbackAuthCheck();
    }
}

/**
 * Fallback auth check using localStorage (dev mode / no SSO)
 */
function fallbackAuthCheck() {
    const loginPage = document.getElementById('loginPage');
    const appContainer = document.getElementById('app-container');
    const ssoSection = document.getElementById('ssoSection');
    const fallbackLogin = document.getElementById('fallbackLogin');

    // In fallback mode, show the dev form
    if (ssoSection) ssoSection.style.display = 'none';
    if (fallbackLogin) fallbackLogin.style.display = 'block';

    const isLoggedIn = localStorage.getItem('isLoggedIn');
    if (isLoggedIn === 'true') {
        loginPage.classList.add('hidden');
        loginPage.style.display = 'none';
        appContainer.style.display = 'flex';
        void appContainer.offsetWidth;
        appContainer.classList.add('visible');
        if (typeof lucide !== 'undefined') lucide.createIcons();
    }
}

/**
 * Update the UI with user information from SSO
 */
function updateUserInfo(user) {
    if (!user) return;

    // Update the sidebar footer with user name if available
    const sidebarFooter = document.querySelector('.sidebar-footer');
    if (sidebarFooter && user.name) {
        // Check if user profile element already exists
        let userProfile = document.getElementById('sso-user-profile');
        if (!userProfile) {
            userProfile = document.createElement('div');
            userProfile.id = 'sso-user-profile';
            userProfile.className = 'sso-user-profile';
            userProfile.innerHTML = `
                <div class="sso-user-avatar">${getInitials(user.name)}</div>
                <div class="sso-user-details">
                    <span class="sso-user-name">${escapeHtml(user.name)}</span>
                    <span class="sso-user-email">${escapeHtml(user.email || '')}</span>
                </div>
            `;
            sidebarFooter.insertBefore(userProfile, sidebarFooter.firstChild);
        }
    }
}

/**
 * Get user initials from name
 */
function getInitials(name) {
    if (!name) return '?';
    return name.split(' ')
        .map(w => w[0])
        .join('')
        .toUpperCase()
        .slice(0, 2);
}

/**
 * Escape HTML to prevent XSS
 */
function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

/**
 * Dev-mode manual login handler (fallback when SSO is not configured)
 */
function handleLogin(e) {
    e.preventDefault();

    const loginPage = document.getElementById('loginPage');
    const appContainer = document.getElementById('app-container');

    // Store login state
    localStorage.setItem('isLoggedIn', 'true');

    loginPage.classList.add('hidden');

    // Wait for fade out
    setTimeout(() => {
        loginPage.style.display = 'none';
        appContainer.style.display = 'flex'; // Restore flex layout

        // Trigger reflow
        void appContainer.offsetWidth;

        appContainer.classList.add('visible');

        // Initialize stuff if needed
        lucide.createIcons();

        setTimeout(() => {
            const welcome = document.getElementById('welcomeModal');
            welcome.style.display = 'flex';
            // trigger reflow
            void welcome.offsetWidth;
            welcome.classList.add('active');
            lucide.createIcons();
        }, 400);

    }, 500);
}

function closeWelcomePopup() {
    const welcome = document.getElementById('welcomeModal');
    welcome.classList.remove('active');
    setTimeout(() => {
        welcome.style.display = 'none';
    }, 400);
}

/**
 * Logout handler — clears both SSO session and localStorage
 */
function handleLogout() {
    localStorage.removeItem('isLoggedIn');
    localStorage.removeItem('userName');
    localStorage.removeItem('userEmail');

    // Redirect to SSO logout endpoint (handles both SSO and non-SSO)
    window.location.href = '/auth/logout';
}

// ================================================================
// Initialize auth on page load
// ================================================================
(function initAuth() {
    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', checkAuthStatus);
    } else {
        checkAuthStatus();
    }
})();
