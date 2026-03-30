const CACHE_NAME = 'opencent-offline-v1';
const OFFLINE_URL = '/offline/';

// Wird beim Installieren der PWA ausgeführt
self.addEventListener('install', (event) => {
    event.waitUntil(
        caches.open(CACHE_NAME).then((cache) => {
            // Lade die Offline-Seite in den Cache
            return cache.addAll([
                OFFLINE_URL,
                // Hier könntest du auch noch '/static/css/style.css' etc. hinzufügen
            ]);
        })
    );
    self.skipWaiting();
});

// Wird beim Aktivieren ausgeführt (räumt alte Caches auf)
self.addEventListener('activate', (event) => {
    event.waitUntil(
        caches.keys().then((cacheNames) => {
            return Promise.all(
                cacheNames.map((cacheName) => {
                    if (cacheName !== CACHE_NAME) {
                        return caches.delete(cacheName);
                    }
                })
            );
        })
    );
    self.clients.claim();
});

// Fängt alle Netzwerkanfragen ab
self.addEventListener('fetch', (event) => {
    // Nur bei Navigationen (Seitenaufrufen) eingreifen
    if (event.request.mode === 'navigate') {
        event.respondWith(
            // Versuche die Seite aus dem Internet zu laden...
            fetch(event.request).catch(() => {
                // ... wenn das fehlschlägt (offline), zeige die Offline-Seite aus dem Cache
                return caches.match(OFFLINE_URL);
            })
        );
    }
});