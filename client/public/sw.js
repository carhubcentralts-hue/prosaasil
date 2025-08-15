// Service Worker - Push notifications only, no fetch interception
self.addEventListener('install', e => self.skipWaiting());
self.addEventListener('activate', e => self.clients.claim());

self.addEventListener('push', e => {
  const data = e.data?.json() || {};
  e.waitUntil(
    self.registration.showNotification(data.title || 'Hebrew AI CRM', { 
      body: data.body, 
      data 
    })
  );
});

// NO fetch handler to avoid interfering with /webhook/* or .mp3 files