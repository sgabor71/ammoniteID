// ============================================================
// admin-auth.js — Admin access control
// Checks if user is logged in AND has admin role
// ============================================================

(function() {
    const ADMIN_SETUP_URL = '/static/admin-setup.html';

    // Hide everything until verified
    document.documentElement.style.visibility = 'hidden';

    async function checkAccess() {
        try {
            const uid = localStorage.getItem('admin_uid');

            if (!uid) {
                window.location.href = ADMIN_SETUP_URL;
                return;
            }

            const res = await fetch('/api/auth/admin-check/' + uid);
            const data = await res.json();

            if (!data.is_admin) {
                localStorage.removeItem('admin_uid');
                window.location.href = ADMIN_SETUP_URL;
                return;
            }

            // Admin verified — show the page
            document.documentElement.style.visibility = 'visible';

        } catch (error) {
            window.location.href = ADMIN_SETUP_URL;
        }
    }

    // Logout function
    window.adminLogout = function() {
        if (confirm('Log out from admin?')) {
            localStorage.removeItem('admin_uid');
            localStorage.removeItem('admin_token');
            window.location.href = '/static/home.html';
        }
    };

    // Run check
    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', checkAccess);
    } else {
        checkAccess();
    }
})();
