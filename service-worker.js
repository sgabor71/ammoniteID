// ============================================================
// service-worker.js — AmmoniteID PWA Service Worker
// v3 — forces re-cache: offline mode auto-download, UI cleanup
// ============================================================

const CACHE_NAME = 'ammoniteid-v3';   // ← bumped to force fresh cache on all devices

const CORE_ASSETS = [
    // ── Pages ──────────────────────────────────────────────
    '/static/home.html',
    '/static/test.html',
    '/static/mylog.html',
    '/static/upgrade.html',
    '/static/upgrade-success.html',
    '/static/login.html',
    '/static/my-account.html',
    '/static/admin.html',
    '/static/review.html',
    '/static/about.html',
    '/static/contact.html',
    '/static/partners.html',
    '/static/terms.html',
    '/static/privacy.html',
    '/static/disclaimer.html',

    // ── Shared JS ──────────────────────────────────────────
    '/static/tier-gates.js',          // ← NEW: must be cached for offline nav to work
    '/static/hamburger-menu.js',
    '/static/responsive-mobile.css',
    '/static/auth-sync.js',
    '/static/feature-gate.js',
    '/static/offline-engine.js',

    // ── Data ───────────────────────────────────────────────
    '/static/class_info.json',
];

// ── Install: cache core assets ──────────────────────────────
self.addEventListener('install', event => {
    event.waitUntil(
        caches.open(CACHE_NAME).then(cache => {
            console.log('SW v3: caching core assets');
            return cache.addAll(CORE_ASSETS).catch(err => {
                console.warn('SW v3: some assets failed to cache', err);
            });
        })
    );
    // Take over immediately — don't wait for old tabs to close
    self.skipWaiting();
});

// ── Activate: delete old caches (v1 and any others) ─────────
self.addEventListener('activate', event => {
    event.waitUntil(
        caches.keys().then(keys =>
            Promise.all(
                keys
                    .filter(k => k !== CACHE_NAME)
                    .map(k => {
                        console.log('SW v3: deleting old cache', k);
                        return caches.delete(k);
                    })
            )
        )
    );
    // Take control of all open pages immediately
    self.clients.claim();
});

// ── Fetch: network first, fall back to cache ─────────────────
self.addEventListener('fetch', event => {
    const url = new URL(event.request.url);

    // Never intercept API calls or POST requests
    if (event.request.method !== 'GET') return;
    if (url.pathname.startsWith('/api/')) return;
    if (url.pathname.startsWith('/identify')) return;
    if (url.pathname.startsWith('/photo/')) return;
    if (url.pathname.startsWith('/queue')) return;

    event.respondWith(
        // Always try network first — gets latest deployed files
        fetch(event.request)
            .then(response => {
                // Cache fresh responses
                if (response.ok) {
                    const clone = response.clone();
                    caches.open(CACHE_NAME).then(cache => {
                        cache.put(event.request, clone);
                    });
                }
                return response;
            })
            .catch(() => {
                // Offline — serve from cache
                return caches.match(event.request).then(cached => {
                    if (cached) return cached;

                    // Offline HTML fallback → home page
                    if (event.request.headers.get('accept') &&
                        event.request.headers.get('accept').includes('text/html')) {
                        return caches.match('/static/home.html');
                    }
                });
            })
    );
});
