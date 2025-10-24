const CACHE_NAME = 'gestor-pedidos-v1';
const urlsToCache = [
  '/',
  '/static/gestorapp/css/gestion.css',
  '/static/gestorapp/css/cards.css',
  '/static/gestorapp/vendor/bootstrap/css/bootstrap.min.css',
  '/static/gestorapp/vendor/jquery/jquery.min.js',
  '/static/img/logo.png',
  '/static/img/icon-192x192.png',
  '/static/img/icon-512x512.png',
  'https://cdn.jsdelivr.net/npm/bootstrap@5.1.3/dist/css/bootstrap.min.css',
  'https://cdn.jsdelivr.net/npm/bootstrap@5.1.3/dist/js/bootstrap.bundle.min.js',
  'https://fonts.googleapis.com/css2?family=Raleway:wght@300&display=swap',
  'https://fonts.googleapis.com/css?family=Lora:400,400i,700,700i',
  'https://cdnjs.cloudflare.com/ajax/libs/font-awesome/5.15.4/css/all.min.css',
  'https://cdn.jsdelivr.net/npm/sweetalert2@11',
  'https://cdn.jsdelivr.net/npm/toastify-js/src/toastify.min.css',
  'https://cdn.jsdelivr.net/npm/toastify-js'
];

self.addEventListener('install', event => {
  event.waitUntil(
    caches.open(CACHE_NAME)
      .then(cache => cache.addAll(urlsToCache))
  );
});

self.addEventListener('fetch', event => {
  event.respondWith(
    caches.match(event.request)
      .then(response => {
        if (response) {
          return response;
        }
        return fetch(event.request)
          .then(response => {
            if (!response || response.status !== 200 || response.type !== 'basic') {
              return response;
            }
            const responseToCache = response.clone();
            caches.open(CACHE_NAME)
              .then(cache => {
                cache.put(event.request, responseToCache);
              });
            return response;
          })
          .catch(() => {
            // Fallback page when no internet connection
            return caches.match('/offline.html');
          });
      })
  );
});
