/**
 * Service Worker for Push Notifications
 * 
 * Handles:
 * - Push events (displays notifications)
 * - Notification click (opens relevant page)
 */

// Push event - show notification
self.addEventListener('push', function(event) {
  console.log('[SW] Push received');
  
  let data = {};
  try {
    data = event.data ? event.data.json() : {};
  } catch (e) {
    console.error('[SW] Error parsing push data:', e);
    data = {
      title: 'התראה חדשה',
      body: event.data ? event.data.text() : 'יש לך התראה חדשה'
    };
  }
  
  const title = data.title || 'ProSaaS CRM';
  const options = {
    body: data.body || '',
    icon: '/icons/icon-192x192.png',
    badge: '/icons/icon-72x72.png',
    tag: data.tag || 'default',
    requireInteraction: data.type === 'urgent',
    vibrate: [200, 100, 200],
    dir: 'rtl',
    lang: 'he',
    data: {
      url: data.url || '/app',
      type: data.type,
      entity_id: data.entity_id,
      business_id: data.business_id
    }
  };
  
  event.waitUntil(
    self.registration.showNotification(title, options)
  );
});

// Notification click - open relevant page
self.addEventListener('notificationclick', function(event) {
  console.log('[SW] Notification clicked');
  
  event.notification.close();
  
  const notificationData = event.notification.data || {};
  let targetUrl = notificationData.url || '/app';
  
  // Make sure URL is absolute
  if (targetUrl.startsWith('/')) {
    targetUrl = self.location.origin + targetUrl;
  }
  
  event.waitUntil(
    clients.matchAll({ type: 'window', includeUncontrolled: true })
      .then(function(clientList) {
        // Check if there's already a window open
        for (let client of clientList) {
          if (client.url && 'focus' in client) {
            // Navigate existing window
            return client.navigate(targetUrl).then(() => client.focus());
          }
        }
        // Open new window
        return clients.openWindow(targetUrl);
      })
  );
});

// Notification close event
self.addEventListener('notificationclose', function(event) {
  console.log('[SW] Notification closed');
});

// Service worker activation
self.addEventListener('activate', function(event) {
  console.log('[SW] Service Worker activated');
  // Take control of all clients
  event.waitUntil(clients.claim());
});

// Service worker installation
self.addEventListener('install', function(event) {
  console.log('[SW] Service Worker installed');
  // Skip waiting to activate immediately
  self.skipWaiting();
});
