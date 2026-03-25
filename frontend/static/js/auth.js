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
                localStorage.setItem('userPicture', data.user.picture || '');
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

                // Load user info from localStorage if present
                const userName = localStorage.getItem('userName');
                const userEmail = localStorage.getItem('userEmail');
                const userPicture = localStorage.getItem('userPicture');
                if (userName) {
                    updateUserInfo({ name: userName, email: userEmail, picture: userPicture });
                }

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

        // Load user info from localStorage if present
        const userName = localStorage.getItem('userName');
        const userEmail = localStorage.getItem('userEmail');
        const userPicture = localStorage.getItem('userPicture');
        if (userName) {
            updateUserInfo({ name: userName, email: userEmail, picture: userPicture });
        }

        if (typeof lucide !== 'undefined') lucide.createIcons();
    }
}

/**
 * Get a time-based greeting (Good morning, Afternoon, Evening)
 */
function getGreeting() {
    const hour = new Date().getHours();
    if (hour < 12) return "Good morning";
    if (hour < 17) return "Good afternoon";
    if (hour < 21) return "Good evening";
    return "Good night";
}

/**
 * Update the UI with user information from SSO
 */
function updateUserInfo(user) {
    console.log("[Auth] Updating UI with user info:", user);

    // Fallback info from localStorage if user object is missing
    const savedName = localStorage.getItem('userName');
    const savedEmail = localStorage.getItem('userEmail');
    const savedPicture = localStorage.getItem('userPicture');

    const name = (user && user.name) ? user.name : savedName;
    const email = (user && user.email) ? user.email : savedEmail;
    const picture = (user && user.picture) ? user.picture : savedPicture;

    if (!name) {
        console.warn("[Auth] No user name found from either param or localStorage");
        return;
    }

    const initials = getInitials(name);
    const greeting = getGreeting();

    // Dashboard Welcome Section
    const welcomeGreeting = document.getElementById('welcome-user-greeting');
    const welcomeEmail = document.getElementById('welcome-user-email');
    const welcomeAvatarContainer = document.getElementById('welcome-avatar-container');

    if (welcomeGreeting) welcomeGreeting.textContent = `${greeting}, ${name}`;
    if (welcomeEmail) welcomeEmail.textContent = email || '';

    if (welcomeAvatarContainer) {
        if (picture) {
            welcomeAvatarContainer.innerHTML = `<img src="${picture}" alt="${name}" class="welcome-avatar">`;
        } else {
            welcomeAvatarContainer.innerHTML = `<div class="welcome-avatar-initials" id="welcome-avatar-initials">${initials}</div>`;
        }
    }

    // Sidebar Footer Profile
    const sidebarFooter = document.querySelector('.sidebar-footer');
    if (sidebarFooter) {
        let userProfile = document.getElementById('sso-user-profile');
        if (!userProfile) {
            userProfile = document.createElement('div');
            userProfile.id = 'sso-user-profile';
            userProfile.className = 'sso-user-profile';
            
            const avatarContent = picture 
                ? `<img src="${picture}" class="sso-user-avatar" style="object-fit: cover;">`
                : `<div class="sso-user-avatar">${initials}</div>`;

            userProfile.innerHTML = `
                ${avatarContent}
                <div class="sso-user-details">
                    <span class="sso-user-name">${escapeHtml(name)}</span>
                    <span class="sso-user-email">${escapeHtml(email || '')}</span>
                </div>
            `;
            const firstChild = sidebarFooter.firstChild;
            if (firstChild) {
                sidebarFooter.insertBefore(userProfile, firstChild);
            } else {
                sidebarFooter.appendChild(userProfile);
            }
        } else {
            // Update existing profile
            const avatarContainer = userProfile.querySelector('.sso-user-avatar');
            const nameEl = userProfile.querySelector('.sso-user-name');
            const emailEl = userProfile.querySelector('.sso-user-email');
            
            if (avatarContainer) {
                if (picture && avatarContainer.tagName === 'DIV') {
                    // Switch to img if it was a div
                    const img = document.createElement('img');
                    img.src = picture;
                    img.className = 'sso-user-avatar';
                    img.style.objectFit = 'cover';
                    avatarContainer.replaceWith(img);
                } else if (!picture && avatarContainer.tagName === 'IMG') {
                    // Switch to div if it was an img
                    const div = document.createElement('div');
                    div.className = 'sso-user-avatar';
                    div.textContent = initials;
                    avatarContainer.replaceWith(div);
                } else if (picture) {
                    avatarContainer.src = picture;
                } else {
                    avatarContainer.textContent = initials;
                }
            }
            if (nameEl) nameEl.textContent = name;
            if (emailEl) emailEl.textContent = email || '';
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

    const form = e.target;
    const nameInput = form.querySelector('input[type="text"]');
    const emailInput = form.querySelector('input[type="email"]');

    const userName = nameInput ? nameInput.value : 'Dev User';
    const userEmail = emailInput ? emailInput.value : 'dev@company.com';

    const loginPage = document.getElementById('loginPage');
    const appContainer = document.getElementById('app-container');

    // Store login state
    localStorage.setItem('isLoggedIn', 'true');
    localStorage.setItem('userName', userName);
    localStorage.setItem('userEmail', userEmail);

    // Update UI immediately
    updateUserInfo({ name: userName, email: userEmail });

    loginPage.classList.add('hidden');

    // Wait for fade out
    setTimeout(() => {
        loginPage.style.display = 'none';
        appContainer.style.display = 'flex'; // Restore flex layout

        // Trigger reflow
        void appContainer.offsetWidth;

        appContainer.classList.add('visible');

        // Initialize stuff if needed
        if (typeof lucide !== 'undefined') lucide.createIcons();

        setTimeout(() => {
            const welcome = document.getElementById('welcomeModal');
            if (welcome) {
                welcome.style.display = 'flex';
                // trigger reflow
                void welcome.offsetWidth;
                welcome.classList.add('active');
            }
            if (typeof lucide !== 'undefined') lucide.createIcons();
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
        document.addEventListener('DOMContentLoaded', () => {
             checkAuthStatus();
             // Extra safety check after a delay to ensure components are rendered
             setTimeout(() => updateUserInfo(), 1000);
             setTimeout(() => updateUserInfo(), 3000);
        });
    } else {
        checkAuthStatus();
        setTimeout(() => updateUserInfo(), 1000);
    }
})();
