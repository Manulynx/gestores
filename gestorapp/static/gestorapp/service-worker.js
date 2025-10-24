const CACHE_NAME = 'app-cache-v1';
const OFFLINE_URL = '/';

const PRECACHE = [
  '/',
  '/static/css/main.css',   // ajusta rutas reales
  '/static/js/main.js',
  '/icons/icon-192.png',
  '/icons/icon-512.png'
];

self.addEventListener('install', (event) => {
  event.waitUntil(
    caches.open(CACHE_NAME).then(cache => cache.addAll(PRECACHE))
  );
  self.skipWaiting();
});

self.addEventListener('activate', (event) => {
  event.waitUntil(self.clients.claim());
});

self.addEventListener('fetch', (event) => {
  // Strategy: cache-first for navigation and precached resources
  event.respondWith(
    caches.match(event.request).then(cached => {
      if (cached) return cached;
      return fetch(event.request).then(response => {
        // opcional: cachear respuestas dinámicas aquí
        return response;
      }).catch(() => {
        // fallback a la página index si es navegación
        if (event.request.mode === 'navigate') {
          return caches.match(OFFLINE_URL);
        }
      });
    })
  );
});
