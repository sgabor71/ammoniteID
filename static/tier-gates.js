// ============================================================
// tier-gates.js — Shared tier logic for AmmoniteID
// Include on every page: <script src="/static/tier-gates.js"></script>
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
 * Fetch tier from DB and cache in localStorage.
 * DB is always the source of truth.
 * Returns tier string: FREE, PREMIUM, EXPERT, ADMIN
 */
async function fetchAndCacheTier(uid) {
    if (!uid) return 'FREE';
    // Permanent admin shortcut
    if (uid === PERMANENT_ADMIN_UID) {
        localStorage.setItem('ammonite_tier', 'ADMIN');
        return 'ADMIN';
    }
    try {
        const res = await fetch(`/api/auth/me/${uid}`);
        if (res.ok) {
            const data = await res.json();
            const tier = (data.tier || 'FREE').toUpperCase();
            localStorage.setItem('ammonite_tier', tier);
            localStorage.setItem('ammonite_user_id', uid);
            return tier;
        }
    } catch (e) {
        console.warn('Tier fetch failed, using cache:', e.message);
    }
    // Fallback to localStorage cache
    return (localStorage.getItem('ammonite_tier') || 'FREE').toUpperCase();
}

/**
 * Apply nav padlocks and show/hide nav links based on tier.
 * Call after tier is known.
 */
function applyNavForTier(tier) {
    const links = document.querySelectorAll('header nav a, .mobile-menu a');

    links.forEach(a => {
        const href = a.getAttribute('href') || '';

        // My Fossil Collection — PREMIUM+
        if (href.includes('mylog')) {
            if (!tierAtLeast(tier, 'PREMIUM')) {
                if (!a.querySelector('.padlock')) {
                    a.insertAdjacentHTML('beforeend', ' <span class="padlock">🔒</span>');
                }
                a.addEventListener('click', e => {
                    e.preventDefault();
                    showUpgradeModal('upgrade');
                }, { once: false });
            } else {
                const p = a.querySelector('.padlock');
                if (p) p.remove();
            }
        }

        // Identify — requires login
        if (href.includes('test.html') && !localStorage.getItem('ammonite_user_id')) {
            if (!a.querySelector('.padlock')) {
                a.insertAdjacentHTML('beforeend', ' <span class="padlock">🔒</span>');
            }
        }

        // Review — EXPERT+
        if (href.includes('review')) {
            if (!tierAtLeast(tier, 'EXPERT')) {
                a.style.display = 'none';
            } else {
                a.style.display = '';
            }
        }

        // Admin — ADMIN only
        if (href.includes('admin.html')) {
            if (tier !== 'ADMIN') {
                a.style.display = 'none';
            } else {
                a.style.display = '';
            }
        }
    });
}

/**
 * Show upgrade or login modal.
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
 * Call on protected pages after auth check.
 */
function requireTier(currentTier, minTier, redirectTo) {
    if (!tierAtLeast(currentTier, minTier)) {
        window.location.href = redirectTo || '/static/upgrade.html';
        return false;
    }
    return true;
}
