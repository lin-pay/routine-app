// Daily — Service Worker（通知の表示と、HTML のネットワーク優先取得）
const ICON = 'icon-daily.png';
const CACHE = 'daily-shell-v1';

self.addEventListener('install', e => self.skipWaiting());
self.addEventListener('activate', e => e.waitUntil(self.clients.claim()));

// HTML は必ずネットワークから取り直す。
// GitHub Pages が Cache-Control: max-age=600 を返すため、そのままだとデプロイ後しばらく
// 古いアプリが表示され続ける（特に iOS のホーム画面アプリは掴んだまま離さない）。
// オフラインのときだけ最後に取れたものを返す。
self.addEventListener('fetch', e => {
  const req = e.request;
  if (req.method !== 'GET' || req.mode !== 'navigate') return;
  // navigate リクエストは Request を作り直せないので URL で扱う
  const url = req.url;
  e.respondWith((async () => {
    try {
      const fresh = await fetch(url, { cache: 'no-store', credentials: 'same-origin' });
      if (fresh.ok) {
        const cache = await caches.open(CACHE);
        await cache.put(url, fresh.clone());
      }
      return fresh;
    } catch (_) {
      const hit = await caches.match(url);
      return hit || Response.error();
    }
  })());
});

// FCM / 標準 Web Push の両方のペイロード形を受け付ける
self.addEventListener('push', e => {
  let p = {};
  try { p = e.data ? e.data.json() : {}; } catch (_) { p = { body: e.data ? e.data.text() : '' }; }
  const n = p.notification || p.data || p;
  const title = n.title || 'Daily';
  e.waitUntil(self.registration.showNotification(title, {
    body: n.body || '',
    icon: ICON,
    badge: ICON,
    tag: n.tag || 'daily',
    data: { url: n.url || './' }
  }));
});

self.addEventListener('notificationclick', e => {
  e.notification.close();
  const url = (e.notification.data && e.notification.data.url) || './';
  e.waitUntil((async () => {
    const list = await self.clients.matchAll({ type: 'window', includeUncontrolled: true });
    for (const c of list) {
      if ('focus' in c) { await c.focus(); return; }
    }
    if (self.clients.openWindow) await self.clients.openWindow(url);
  })());
});
