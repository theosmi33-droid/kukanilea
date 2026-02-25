/* 
  KUKANILEA Service Worker 
  Fokus: PWA-Deployment & Offline-Buffer für Baustellen-Szenarien.
*/

const CACHE_NAME = 'kukanilea-v1';
const ASSETS = [
  '/',
  '/static/css/style.css',
  '/static/css/haptic.css',
  '/mobile/capture'
];

self.addEventListener('install', (e) => {
  e.waitUntil(
    caches.open(CACHE_NAME).then((cache) => {
      return cache.addAll(ASSETS);
    })
  );
});

self.addEventListener('fetch', (e) => {
  // In der Gold-Edition: Cache-First für statische Assets, Network-First für API
  e.respondWith(
    fetch(e.request).catch(() => {
      return caches.match(e.request);
    })
  );
});
