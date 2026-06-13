// ============================================================
// admin-auth.js — Admin access control (FIXED)
// Checks if user is logged in AND has ADMIN tier
// ============================================================

(function() {
    // Hide everything until verified
    document.documentElement.style.visibility = 'hidden';

    async function checkAccess() {
        try {
            // Check if user is logged in (Firebase)
            const uid = localStorage.getItem('ammonite_user_id');
            
            if (!uid) {
                // Not logged in at all
                window.location.href = '/static/login.html';
                return;
            }

            // Check user tier from backend
            const res = await fetch(`/api/auth/me/${uid}`);
            
            if (!res.ok) {
                // User not found
                localStorage.removeItem('ammonite_user_id');
                localStorage.removeItem('ammonite_tier');
                window.location.href = '/static/login.html';
                return;
            }

            const data = await res.json();
            const tier = (data.tier || 'FREE').toUpperCase();

            // Check if user is ADMIN tier
            if (tier !== 'ADMIN') {
                // Not an admin
                alert('⚠️ Admin access required. You are logged in as ' + tier);
                window.location.href = '/static/home.html';
                return;
            }

            // Admin verified — show the page
            document.documentElement.style.visibility = 'visible';

        } catch (error) {
            console.error('Auth check error:', error);
            window.location.href = '/static/login.html';
        }
    }

    // Logout function
    window.adminLogout = function() {
        if (confirm('Log out from admin?')) {
            localStorage.removeItem('ammonite_user_id');
            localStorage.removeItem('ammonite_tier');
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
