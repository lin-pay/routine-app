// Daily — Service Worker（通知表示専用。キャッシュは行わない）
const ICON = 'icon-daily.png';

self.addEventListener('install', e => self.skipWaiting());
self.addEventListener('activate', e => e.waitUntil(self.clients.claim()));

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
