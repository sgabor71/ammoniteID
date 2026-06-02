// ============================================================
// tier-gates.js — Shared tier logic for AmmoniteID
// Include in <head> on EVERY page
// ============================================================

const TIER_LEVELS = { 'FREE': 0, 'PREMIUM': 1, 'EXPERT': 2, 'ADMIN': 3 };
const PERMANENT_ADMIN_UID = '16fjKKd4XPOD8PMZhGQSHmSAdPO2';

function tierAtLeast(userTier, minTier) {
    return (TIER_LEVELS[userTier] || 0) >= (TIER_LEVELS[minTier] || 0);
}

function getTierBadgeStyle(tier) {
    const styles = {
        'FREE':    { bg: '#fff3e0', color: '#e67e22' },
        'PREMIUM': { bg: '#e8f5e9', color: '#2c5f2d' },
        'EXPERT':  { bg: '#e3f2fd', color: '#1565c0' },
        'ADMIN':   { bg: '#fce4ec', color: '#c62828' },
    };
    return styles[tier] || styles['FREE'];
}

/**
 * Fetch tier from DB, cache in localStorage, then apply nav.
 * Call this from EVERY page's onAuthStateChanged when user is logged in.
 * This is the single source of truth for tier on all pages.
 */
async function refreshTierAndApplyNav(uid) {
    if (!uid) {
        applyNavForTier('FREE');
        return 'FREE';
    }

    let tier = 'FREE';

    // Permanent admin always ADMIN — no API call needed
    if (uid === PERMANENT_ADMIN_UID) {
        tier = 'ADMIN';
        localStorage.setItem('ammonite_tier', 'ADMIN');
        localStorage.setItem('ammonite_user_id', uid);
        applyNavForTier('ADMIN');
        return 'ADMIN';
    }

    try {
        const res = await fetch(`/api/auth/me/${uid}`);
        if (res.ok) {
            const data = await res.json();
            tier = (data.tier || 'FREE').toUpperCase();
            localStorage.setItem('ammonite_tier', tier);
            localStorage.setItem('ammonite_user_id', uid);
        } else {
            // Fallback to cache
            tier = (localStorage.getItem('ammonite_tier') || 'FREE').toUpperCase();
        }
    } catch (e) {
        // Fallback to cache if offline/error
        tier = (localStorage.getItem('ammonite_tier') || 'FREE').toUpperCase();
        console.warn('Tier fetch failed, using cache:', e.message);
    }

    applyNavForTier(tier);
    return tier;
}

/**
 * Apply nav padlocks based on tier.
 * Removes stale padlocks before applying fresh ones.
 */
function applyNavForTier(tier) {
    const links = document.querySelectorAll('header nav a, .mobile-menu a, nav a');

    links.forEach(a => {
        const href = a.getAttribute('href') || '';

        // ── My Fossil Collection — PREMIUM+ ──────────────────
        if (href.includes('mylog')) {
            // Remove any existing padlock first
            const existing = a.querySelector('.padlock');
            if (existing) existing.remove();

            if (!tierAtLeast(tier, 'PREMIUM')) {
                a.insertAdjacentHTML('beforeend', ' <span class="padlock">🔒</span>');
                // Replace link with upgrade redirect
                const clone = a.cloneNode(true);
                clone.addEventListener('click', e => {
                    e.preventDefault();
                    if (confirm('This feature requires Premium. Upgrade now?')) {
                        window.location.href = '/static/upgrade.html';
                    }
                });
                a.parentNode.replaceChild(clone, a);
            }
        }

        // ── Review — EXPERT+ ──────────────────────────────────
        if (href.includes('review')) {
            a.style.display = tierAtLeast(tier, 'EXPERT') ? '' : 'none';
        }

        // ── Admin — ADMIN only ────────────────────────────────
        if (href.includes('admin.html')) {
            a.style.display = (tier === 'ADMIN') ? '' : 'none';
        }
    });
}

/**
 * Show upgrade modal.
 */
function showUpgradeModal(type) {
    if (type === 'upgrade') {
        if (confirm('This feature requires Premium. Upgrade now?')) {
            window.location.href = '/static/upgrade.html';
        }
    } else {
        if (confirm('Please log in to use this feature.')) {
            window.location.href = '/static/login.html';
        }
    }
}

/**
 * Redirect if tier is insufficient.
 */
function requireTier(currentTier, minTier, redirectTo) {
    if (!tierAtLeast(currentTier, minTier)) {
        window.location.href = redirectTo || '/static/upgrade.html';
        return false;
    }
    return true;
}

/**
 * Legacy alias — keep backward compat with pages
 * that call fetchAndCacheTier directly.
 */
async function fetchAndCacheTier(uid) {
    return await refreshTierAndApplyNav(uid);
}
