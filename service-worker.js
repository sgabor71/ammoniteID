// ============================================================
// service-worker.js — AmmoniteID PWA Service Worker
// Caches app pages and assets for offline use
// ============================================================

const CACHE_NAME = 'ammoniteid-v1';
const CORE_ASSETS = [
    '/static/home.html',
    '/static/test.html',
    '/static/about.html',
    '/static/contact.html',
    '/static/partners.html',
    '/static/mylog.html',
    '/static/upgrade.html',
    '/static/terms.html',
    '/static/privacy.html',
    '/static/disclaimer.html',
    '/static/auth-sync.js',
    '/static/feature-gate.js',
    '/static/offline-engine.js',
    '/static/class_info.json',
];

// ── Install: cache core assets ──────────────────────────────
self.addEventListener('install', event => {
    event.waitUntil(
        caches.open(CACHE_NAME).then(cache => {
            console.log('SW: caching core assets');
            return cache.addAll(CORE_ASSETS).catch(err => {
                console.warn('SW: some assets failed to cache', err);
            });
        })
    );
    self.skipWaiting();
});

// ── Activate: clean old caches ──────────────────────────────
self.addEventListener('activate', event => {
    event.waitUntil(
        caches.keys().then(keys =>
            Promise.all(
                keys.filter(k => k !== CACHE_NAME).map(k => caches.delete(k))
            )
        )
    );
    self.clients.claim();
});

// ── Fetch: serve from cache when offline ────────────────────
self.addEventListener('fetch', event => {
    const url = new URL(event.request.url);

    // Don't cache API calls or POST requests
    if (event.request.method !== 'GET') return;
    if (url.pathname.startsWith('/api/')) return;
    if (url.pathname.startsWith('/identify')) return;

    event.respondWith(
        // Try network first, fall back to cache
        fetch(event.request)
            .then(response => {
                // Cache successful responses
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

                    // If requesting a page and it's not cached, show offline page
                    if (event.request.headers.get('accept') &&
                        event.request.headers.get('accept').includes('text/html')) {
                        return caches.match('/static/home.html');
                    }
                });
            })
    );
});
