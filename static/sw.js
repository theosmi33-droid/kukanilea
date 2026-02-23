const CACHE_NAME = 'kukanilea-v1.4';
const ASSETS = [
  '/',
  '/static/css/style.css',
  '/static/manifest.json',
  '/static/icons/icon-192x192.png'
];

self.addEventListener('install', (event) => {
  event.waitUntil(
    caches.open(CACHE_NAME).then((cache) => {
      return cache.addAll(ASSETS);
    })
  );
});

self.addEventListener('fetch', (event) => {
  event.respondWith(
    caches.match(event.request).then((response) => {
      return response || fetch(event.request);
    })
  );
});
