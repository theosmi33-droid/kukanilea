/* 
  KUKANILEA Service Worker 
  Fokus: PWA-Deployment & Offline-Buffer für Baustellen-Szenarien.
*/

const CACHE_NAME = 'kukanilea-v2';
const ASSETS = [
  '/',
  '/static/css/haptic.css'
];

self.addEventListener('install', (e) => {
  e.waitUntil(
    caches.open(CACHE_NAME).then((cache) => {
      // ignore errors during install caching to prevent SW failure
      return cache.addAll(ASSETS).catch(err => console.warn('SW Cache install warning:', err));
    })
  );
});

self.addEventListener('fetch', (e) => {
  // FIX: Chrome extensions (chrome-extension://) cannot be cached.
  // Only cache http/https requests.
  if (!(e.request.url.indexOf('http') === 0)) return;

  e.respondWith(
    caches.match(e.request).then((response) => {
      return response || fetch(e.request).then(fetchRes => {
        return caches.open(CACHE_NAME).then(cache => {
          // Only cache successful GET requests
          if (e.request.method === 'GET' && fetchRes.status === 200) {
            cache.put(e.request.url, fetchRes.clone());
          }
          return fetchRes;
        });
      });
    }).catch(() => {
      // Fallback logic if needed
    })
  );
});
