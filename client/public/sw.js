/**
 * Service Worker for Push Notifications
 * 
 * Handles:
 * - Push events (displays notifications)
 * - Notification click (opens relevant page)
 * - Error handling to prevent crashes
 */

// Global error handler to catch unhandled errors
self.addEventListener('error', function(event) {
  console.error('[SW] Global error:', event.error || event.message);
});

// Unhandled promise rejection handler
self.addEventListener('unhandledrejection', function(event) {
  console.error('[SW] Unhandled promise rejection:', event.reason);
  // Prevent the error from propagating
  event.preventDefault();
});

// Push event - show notification
self.addEventListener('push', function(event) {
  console.log('[SW] Push received');
  
  // Wrap everything in a try-catch to prevent unhandled errors
  const handlePush = async () => {
    try {
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
      
      await self.registration.showNotification(title, options);
    } catch (error) {
      console.error('[SW] Error in push handler:', error);
      // Show fallback notification
      try {
        await self.registration.showNotification('ProSaaS CRM', {
          body: 'התראה חדשה',
          icon: '/icons/icon-192x192.png'
        });
      } catch (fallbackError) {
        console.error('[SW] Failed to show fallback notification:', fallbackError);
      }
    }
  };
  
  event.waitUntil(handlePush());
});

// Notification click - open relevant page
self.addEventListener('notificationclick', function(event) {
  console.log('[SW] Notification clicked');
  
  event.notification.close();
  
  // Wrap in async handler with error handling
  const handleClick = async () => {
    try {
      const notificationData = event.notification.data || {};
      let targetUrl = notificationData.url || '/app';
      
      // Make sure URL is absolute
      if (targetUrl.startsWith('/')) {
        targetUrl = self.location.origin + targetUrl;
      }
      
      // Get all clients
      const clientList = await clients.matchAll({ type: 'window', includeUncontrolled: true });
      
      // Look for a window that's already on our app
      const appOrigin = self.location.origin;
      for (let client of clientList) {
        if (client.url && client.url.startsWith(appOrigin) && 'focus' in client) {
          // Found an app window - navigate and focus it
          try {
            await client.navigate(targetUrl);
            return await client.focus();
          } catch (navError) {
            console.error('[SW] Error navigating client:', navError);
            // Continue to try opening new window
          }
        }
      }
      
      // No app window open - open a new one
      return await clients.openWindow(targetUrl);
      
    } catch (error) {
      console.error('[SW] Error in notification click handler:', error);
      // Try to open default app page as fallback
      try {
        await clients.openWindow(self.location.origin + '/app');
      } catch (fallbackError) {
        console.error('[SW] Failed to open fallback window:', fallbackError);
      }
    }
  };
  
  event.waitUntil(handleClick());
});

// Notification close event
self.addEventListener('notificationclose', function(event) {
  console.log('[SW] Notification closed');
});

// Service worker activation
self.addEventListener('activate', function(event) {
  console.log('[SW] Service Worker activated');
  
  // Wrap in async handler with error handling
  const handleActivate = async () => {
    try {
      // Take control of all clients
      await clients.claim();
      console.log('[SW] Claimed all clients');
    } catch (error) {
      console.error('[SW] Error during activation:', error);
    }
  };
  
  event.waitUntil(handleActivate());
});

// Service worker installation
self.addEventListener('install', function(event) {
  console.log('[SW] Service Worker installed');
  // Skip waiting to activate immediately
  self.skipWaiting();
});
