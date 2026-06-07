// ============================================================
// service-worker.js — AmmoniteID PWA Service Worker
// v4 — adds TFJS model files to cache for offline mode
// ============================================================

const CACHE_NAME = 'ammoniteid-v4';   // ← bumped to v4 for new model assets

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
    '/static/tier-gates.js',
    '/static/hamburger-menu.js',
    '/static/responsive-mobile.css',
    '/static/auth-sync.js',
    '/static/feature-gate.js',
    '/static/offline-engine.js',

    // ── Data ───────────────────────────────────────────────
    '/static/class_info.json',

    // ── TFJS Model (offline mode) ──────────────────────────
    '/static/tfjs_model/model.json',
    '/static/tfjs_model/group1-shard1of5.bin',
    '/static/tfjs_model/group1-shard2of5.bin',
    '/static/tfjs_model/group1-shard3of5.bin',
    '/static/tfjs_model/group1-shard4of5.bin',
    '/static/tfjs_model/group1-shard5of5.bin',
];

// ── Install: cache core assets ──────────────────────────────
self.addEventListener('install', event => {
    event.waitUntil(
        caches.open(CACHE_NAME).then(cache => {
            console.log('SW v4: caching core assets + TFJS model');
            return cache.addAll(CORE_ASSETS).catch(err => {
                console.warn('SW v4: some assets failed to cache', err);
            });
        })
    );
    // Take over immediately — don't wait for old tabs to close
    self.skipWaiting();
});

// ── Activate: delete old caches (v1, v2, v3, etc.) ─────────
self.addEventListener('activate', event => {
    event.waitUntil(
        caches.keys().then(keys =>
            Promise.all(
                keys
                    .filter(k => k !== CACHE_NAME)
                    .map(k => {
                        console.log('SW v4: deleting old cache', k);
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
