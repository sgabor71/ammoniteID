// ============================================================
// auth-sync.js — User sync + tier storage
// Call this after Firebase login to sync user and cache tier
// ============================================================

async function syncUserAndTier(uid, email, displayName) {
    try {
        // 1. Sync user to backend
        const syncRes = await fetch('/api/auth/sync', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                uid: uid,
                email: email,
                display_name: displayName || email.split('@')[0]
            })
        });

        if (!syncRes.ok) {
            console.error('Sync failed:', syncRes.status);
            return null;
        }

        const syncData = await syncRes.json();
        const tier = (syncData.user?.tier || 'FREE').toUpperCase();

        // 2. Store in localStorage for feature-gate.js to read
        localStorage.setItem('ammonite_user_id', uid);
        localStorage.setItem('ammonite_tier', tier);

        // 3. Dispatch event so pages know user is ready
        window.dispatchEvent(new Event('ammonite-user-ready'));

        console.log('✓ User synced:', { uid, tier });
        return { uid, tier };
    } catch (e) {
        console.error('syncUserAndTier error:', e);
        return null;
    }
}

// Also provide a function to check tier from backend (for pages that need current status)
async function fetchUserTier(uid) {
    try {
        const res = await fetch(`/api/auth/me/${uid}`);
        
        if (res.status === 404) {
            // User not synced yet — sync now and return
            console.log('User not in DB, syncing...');
            // This shouldn't happen if syncUserAndTier was called, but handle it
            const data = await res.json();
            return data.tier || 'FREE';
        }

        if (!res.ok) return 'FREE';

        const data = await res.json();
        const tier = (data.tier || 'FREE').toUpperCase();
        
        // Update localStorage with current tier
        localStorage.setItem('ammonite_tier', tier);
        
        return tier;
    } catch (e) {
        console.error('fetchUserTier error:', e);
        return localStorage.getItem('ammonite_tier') || 'FREE';
    }
}

window.syncUserAndTier = syncUserAndTier;
window.fetchUserTier = fetchUserTier;
