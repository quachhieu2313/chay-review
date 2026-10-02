---
layout: null
sitemap: false
---
// Service worker: luôn ưu tiên mạng (dữ liệu luôn mới), chỉ dùng bản đã lưu khi mất mạng.
const BO_NHO = 'kcn-{{ site.time | date: "%Y%m%d%H%M%S" }}';
self.addEventListener('install', e => self.skipWaiting());
self.addEventListener('activate', e => {
  e.waitUntil(caches.keys().then(ks => Promise.all(ks.filter(k => k !== BO_NHO).map(k => caches.delete(k)))).then(() => self.clients.claim()));
});
self.addEventListener('fetch', e => {
  const req = e.request;
  if(req.method !== 'GET' || new URL(req.url).origin !== location.origin) return;
  e.respondWith(
    fetch(req).then(res => {
      if(res.ok){ const ban = res.clone(); caches.open(BO_NHO).then(c => c.put(req, ban)); }
      return res;
    }).catch(() => caches.match(req, {ignoreSearch: true}).then(r => r || caches.match('{{ '/' | relative_url }}')))
  );
});
