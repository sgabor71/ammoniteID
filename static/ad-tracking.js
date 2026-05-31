// ad-tracking.js - Add this script to all pages with partner banners
// This tracks ad impressions and clicks for analytics

(function() {
    // Generate or retrieve session ID
    function getSessionId() {
        let sessionId = sessionStorage.getItem('ammonite_session_id');
        if (!sessionId) {
            sessionId = 'sess_' + Date.now() + '_' + Math.random().toString(36).substr(2, 9);
            sessionStorage.setItem('ammonite_session_id', sessionId);
        }
        return sessionId;
    }

    // Get current user ID if logged in (from Firebase)
    function getUserId() {
        // This will be populated by Firebase auth
        // For now return null if not logged in
        return localStorage.getItem('ammonite_user_id') || null;
    }

    // Get current page name
    function getCurrentPage() {
        const path = window.location.pathname;
        if (path.includes('home.html') || path === '/' || path === '/static/') return 'home';
        if (path.includes('test.html')) return 'identify';
        if (path.includes('mylog.html')) return 'mylog';
        if (path.includes('about.html')) return 'about';
        if (path.includes('contact.html')) return 'contact';
        if (path.includes('partners.html')) return 'partners';
        return 'unknown';
    }

    // Track ad impression
    async function trackAdImpression(partnerId, partnerName) {
        try {
            await fetch('http://localhost:8000/api/track/ad-impression', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({
                    partner_id: partnerId,
                    partner_name: partnerName,
                    page: getCurrentPage(),
                    user_id: getUserId(),
                    session_id: getSessionId()
                })
            });
        } catch (error) {
            console.error('Error tracking impression:', error);
        }
    }

    // Track ad click
    async function trackAdClick(partnerId, partnerName, secondsViewed) {
        try {
            await fetch('http://localhost:8000/api/track/ad-click', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({
                    partner_id: partnerId,
                    partner_name: partnerName,
                    page: getCurrentPage(),
                    user_id: getUserId(),
                    session_id: getSessionId(),
                    seconds_viewed: secondsViewed
                })
            });
        } catch (error) {
            console.error('Error tracking click:', error);
        }
    }

    // Track page visit on load
    async function trackPageVisit() {
        const startTime = Date.now();
        
        // Track when user leaves
        window.addEventListener('beforeunload', async () => {
            const timeSpent = Math.round((Date.now() - startTime) / 1000);
            
            try {
                // Use sendBeacon for reliable tracking on page unload
                const data = JSON.stringify({
                    page: getCurrentPage(),
                    user_id: getUserId(),
                    session_id: getSessionId(),
                    time_spent: timeSpent
                });
                
                navigator.sendBeacon(
                    'http://localhost:8000/api/track/page-visit',
                    new Blob([data], { type: 'application/json' })
                );
            } catch (error) {
                console.error('Error tracking page visit:', error);
            }
        });
    }

    // ── DEPRECATED ──────────────────────────────────────────────────
    // Rendering is now handled by the canonical showAd() defined in each
    // page, which calls trackAdImpression / trackAdClick directly.
    // This stub only forwards to showAd so any legacy call still works.
    window.showAdWithTracking = function(index) {
        if (typeof showAd === 'function') showAd(index);
    };

    // Initialize tracking on page load
    trackPageVisit();

    // Make tracking functions globally available
    window.trackAdImpression = trackAdImpression;
    window.trackAdClick = trackAdClick;
})();

/* ============================================
   INTEGRATION INSTRUCTIONS:
   ============================================

   1. Add this script to all HTML pages with ads:
      <script src="/static/ad-tracking.js"></script>

   2. Update the showAd function in your existing ad rotation code:
      Replace:
        showAd(index);
      With:
        showAdWithTracking(index);

   3. Update Firebase auth to store user ID in localStorage:
      After successful login:
        localStorage.setItem('ammonite_user_id', user.uid);
      
      After logout:
        localStorage.removeItem('ammonite_user_id');

   4. For production, update API URLs from localhost:8000 to your domain
*/
