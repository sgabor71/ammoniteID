// ============================================================
// feature-gate.js — Feature gating + account badge for all pages
// AmmoniteID
// ============================================================
//
// Add to every page (after Firebase + auth-sync.js):
//   <script src="/static/feature-gate.js"></script>
//
// WHAT IT DOES:
//   1. Fetches the feature rules from /api/features (set in admin)
//   2. On each page, locks Premium-only features for Free users
//      with a 🔒 "Upgrade to Premium to unlock" overlay
//   3. Renders the account status badge in the nav:
//        Not logged in → "Log In / Sign Up" (as now)
//        Free           → "👤 Free Account  [⭐ Upgrade to Premium]"
//        Premium        → "⭐ Premium Account"
//   4. Enforces login on pages that require it (identify, etc.)
//
// HOW TO GATE A FEATURE (in any page's HTML):
//   Add data-feature="feature_key" to any element:
//     <button data-feature="save_collection">Save to Collection</button>
//     <div data-feature="export_pdf" class="some-section">...</div>
//   The script will automatically lock/unlock it based on the rules.
//
// HOW TO REQUIRE LOGIN ON A PAGE:
//   Add this anywhere in the page's <body>:
//     <script>window.__requireLogin = true;</script>
//   Not-logged-in visitors will be redirected to a login prompt.
// ============================================================

(function () {
    let _featureRules = {};
    let _rulesLoaded = false;

    // ── Load feature rules from backend ─────────────────────
    async function loadFeatureRules() {
        try {
            const res = await fetch('/api/features');
            if (!res.ok) return;
            const data = await res.json();
            _featureRules = data.rules || {};
            _rulesLoaded = true;
        } catch (e) {
            console.warn('feature-gate: could not load rules', e);
        }
    }

    // ── Check if a feature is allowed for the current user ──
    function isAllowed(featureKey) {
        const rule = _featureRules[featureKey];
        if (!rule || rule === 'everyone') return true;
        if (rule === 'off') return false;
        const tier = (localStorage.getItem('ammonite_tier') || 'FREE').toUpperCase();
        if (rule === 'premium') return tier === 'PREMIUM';
        if (rule === 'free') return tier === 'FREE';
        return true;
    }

    // Expose globally
    window.featureAllowed = isAllowed;

    // ── Apply gates to all data-feature elements on the page ─
    function applyGates() {
        if (!_rulesLoaded) return;
        document.querySelectorAll('[data-feature]').forEach(el => {
            const key = el.dataset.feature;
            if (isAllowed(key)) {
                // Unlock: remove overlay if it was previously locked
                el.style.position = '';
                el.style.pointerEvents = '';
                el.style.opacity = '';
                const overlay = el.querySelector('.fg-lock-overlay');
                if (overlay) overlay.remove();
            } else {
                // Lock: add the overlay
                if (el.querySelector('.fg-lock-overlay')) return; // already locked
                el.style.position = 'relative';
                el.style.pointerEvents = 'none';
                el.style.opacity = '0.5';

                const overlay = document.createElement('div');
                overlay.className = 'fg-lock-overlay';
                overlay.style.cssText =
                    'position:absolute; inset:0; display:flex; align-items:center; justify-content:center;' +
                    'background:rgba(255,255,255,0.85); z-index:10; pointer-events:auto; cursor:pointer;' +
                    'border-radius:8px; backdrop-filter:blur(2px);';
                overlay.innerHTML =
                    '<div style="text-align:center;">' +
                    '<div style="font-size:2rem;">🔒</div>' +
                    '<div style="font-weight:bold; font-size:1rem; color:#333; margin:6px 0 4px;">Premium Feature</div>' +
                    '<div style="font-size:0.88rem; color:#e67e22; font-weight:bold; text-decoration:underline;">Upgrade to Premium to unlock</div>' +
                    '</div>';
                overlay.addEventListener('click', (e) => {
                    e.stopPropagation();
                    window.location.href = '/static/upgrade.html';
                });
                el.appendChild(overlay);
            }
        });
    }

    // ── Render account badge in the nav ─────────────────────
    function renderAccountBadge() {
        const authButtons = document.querySelector('.auth-buttons');
        if (!authButtons) return;

        const uid = localStorage.getItem('ammonite_user_id');
        const tier = (localStorage.getItem('ammonite_tier') || '').toUpperCase();

        if (!uid) {
            // Not logged in — keep default Log In / Sign Up buttons
            // (they're already in the HTML)
            return;
        }

        if (tier === 'PREMIUM') {
            authButtons.innerHTML =
                '<span style="display:flex; align-items:center; gap:8px; font-family:Arial,sans-serif;">' +
                '<span style="background:linear-gradient(135deg,#f39c12,#e67e22); color:#fff; padding:5px 14px; border-radius:20px; font-size:0.88rem; font-weight:bold;">⭐ Premium</span>' +
                '<a href="#" onclick="logoutUser(); return false;" style="font-size:0.82rem; color:#777; text-decoration:underline;">Log out</a>' +
                '</span>';
        } else {
            // Free user — show status + bright Upgrade button
            authButtons.innerHTML =
                '<span style="display:flex; align-items:center; gap:8px; font-family:Arial,sans-serif;">' +
                '<span style="background:#ecf0f1; color:#555; padding:5px 12px; border-radius:20px; font-size:0.85rem; font-weight:bold;">👤 Free</span>' +
                '<a href="/static/upgrade.html" style="background:linear-gradient(135deg,#f39c12,#e67e22); color:#fff; padding:6px 16px; border-radius:20px; font-size:0.88rem; font-weight:bold; text-decoration:none; transition:transform 0.2s; display:inline-block;" ' +
                'onmouseover="this.style.transform=\'scale(1.05)\'" onmouseout="this.style.transform=\'scale(1)\'">⭐ Upgrade to Premium</a>' +
                '<a href="#" onclick="logoutUser(); return false;" style="font-size:0.82rem; color:#777; text-decoration:underline;">Log out</a>' +
                '</span>';
        }
    }

    // ── Logout helper ───────────────────────────────────────
    window.logoutUser = function () {
        // Clear local state
        localStorage.removeItem('ammonite_user_id');
        localStorage.removeItem('ammonite_tier');
        // Sign out of Firebase if available
        try {
            const { getAuth, signOut } = window;
            if (typeof firebase !== 'undefined' && firebase.auth) {
                firebase.auth().signOut();
            }
        } catch (e) {}
        // Redirect to home
        window.location.href = '/static/home.html';
    };

    // ── Login enforcement ───────────────────────────────────
    function enforceLogin() {
        if (!window.__requireLogin) return;
        const uid = localStorage.getItem('ammonite_user_id');
        if (!uid) {
            // Show a login prompt overlay on the whole page
            const overlay = document.createElement('div');
            overlay.id = 'fg-login-overlay';
            overlay.style.cssText =
                'position:fixed; inset:0; background:rgba(255,255,255,0.95); z-index:9999;' +
                'display:flex; align-items:center; justify-content:center;';
            overlay.innerHTML =
                '<div style="text-align:center; max-width:400px; padding:40px;">' +
                '<div style="font-size:3rem; margin-bottom:16px;">🔐</div>' +
                '<h2 style="margin:0 0 10px; color:#333;">Login Required</h2>' +
                '<p style="color:#666; margin-bottom:24px;">You need to log in to use this feature.</p>' +
                '<a href="/static/home.html#login" style="display:inline-block; background:#2c5f2d; color:#fff; padding:12px 30px; border-radius:8px; text-decoration:none; font-weight:bold; font-size:1rem;">Log In</a>' +
                '<br><a href="/static/home.html#signup" style="display:inline-block; margin-top:12px; color:#2c5f2d; font-size:0.9rem;">Create an account</a>' +
                '</div>';
            document.body.appendChild(overlay);
        }
    }

    // ── Boot sequence ───────────────────────────────────────
    async function init() {
        await loadFeatureRules();
        enforceLogin();
        renderAccountBadge();
        applyGates();

        // Re-apply when user state changes (after login/sync)
        window.addEventListener('ammonite-user-ready', () => {
            renderAccountBadge();
            applyGates();
        });
    }

    // Run after DOM is ready
    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', init);
    } else {
        init();
    }
})();
