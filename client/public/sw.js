/**
 * AgentLocator v42 - Service Worker
 * תמיכה במידע offline ו-push notifications
 */

const CACHE_NAME = 'agentlocator-v42-1.0.0';
const OFFLINE_URL = '/offline.html';

// Files to cache for offline functionality
const CACHE_FILES = [
  '/',
  '/offline.html',
  '/assets/index.css',
  '/assets/index.js',
  // Add other critical assets
];

// Install event - cache resources
self.addEventListener('install', (event) => {
  ;
  
  event.waitUntil(
    caches.open(CACHE_NAME)
      .then((cache) => {
        ;
        return cache.addAll(CACHE_FILES);
      })
      .then(() => {
        ;
        return self.skipWaiting();
      })
      .catch((error) => {
        console.error('❌ Service Worker install failed:', error);
      })
  );
});

// Activate event - clean up old caches
self.addEventListener('activate', (event) => {
  ;
  
  event.waitUntil(
    caches.keys().then((cacheNames) => {
      return Promise.all(
        cacheNames.map((cacheName) => {
          if (cacheName !== CACHE_NAME) {
            ;
            return caches.delete(cacheName);
          }
        })
      );
    }).then(() => {
      ;
      return self.clients.claim();
    })
  );
});

// Fetch event - serve cached content when offline
self.addEventListener('fetch', (event) => {
  // Only handle GET requests
  if (event.request.method !== 'GET') return;
  
  // Skip Chrome extension and other non-http requests
  if (!event.request.url.startsWith('http')) return;
  
  event.respondWith(
    caches.match(event.request)
      .then((cachedResponse) => {
        // Return cached version if available
        if (cachedResponse) {
          return cachedResponse;
        }
        
        // Try to fetch from network
        return fetch(event.request)
          .then((response) => {
            // Don't cache non-successful responses
            if (!response || response.status !== 200 || response.type !== 'basic') {
              return response;
            }
            
            // Clone the response for caching
            const responseToCache = response.clone();
            
            // Cache successful responses
            caches.open(CACHE_NAME).then((cache) => {
              cache.put(event.request, responseToCache);
            });
            
            return response;
          })
          .catch(() => {
            // Network failed, serve offline page for navigation requests
            if (event.request.mode === 'navigate') {
              return caches.match(OFFLINE_URL);
            }
            
            // For other requests, just fail
            throw new Error('Network error and no cached version');
          });
      })
  );
});

// Push notification event
self.addEventListener('push', (event) => {
  ;
  
  if (!event.data) {
    ;
    return;
  }
  
  const data = event.data.json();
  
  const options = {
    body: data.body || 'יש לך הודעה חדשה',
    icon: '/logo-192.png',
    badge: '/badge-72.png',
    image: data.image,
    tag: data.tag || 'default',
    renotify: true,
    requireInteraction: data.requireInteraction || false,
    actions: data.actions || [],
    data: data.data || {},
    dir: 'rtl', // Hebrew text direction
    lang: 'he'
  };
  
  event.waitUntil(
    self.registration.showNotification(data.title || 'AgentLocator CRM', options)
  );
});

// Notification click event
self.addEventListener('notificationclick', (event) => {
  ;
  
  event.notification.close();
  
  const data = event.notification.data;
  const action = event.action;
  
  // Handle specific actions
  if (action === 'open_customer') {
    event.waitUntil(
      clients.openWindow(`/customers/${data.customerId}`)
    );
  } else if (action === 'open_call') {
    event.waitUntil(
      clients.openWindow(`/calls/${data.callId}`)
    );
  } else {
    // Default action - focus the app or open it
    event.waitUntil(
      clients.matchAll({ type: 'window' }).then((clientList) => {
        // Find an existing window and focus it
        for (let client of clientList) {
          if (client.url.includes(self.location.origin)) {
            return client.focus();
          }
        }
        
        // No existing window, open a new one
        return clients.openWindow('/');
      })
    );
  }
});

// Background sync for offline actions
self.addEventListener('sync', (event) => {
  ;
  
  if (event.tag === 'background-sync-calls') {
    event.waitUntil(syncCalls());
  } else if (event.tag === 'background-sync-messages') {
    event.waitUntil(syncMessages());
  }
});

// Sync functions
async function syncCalls() {
  try {
    ;
    
    // Get offline calls from IndexedDB
    const offlineCalls = await getOfflineCalls();
    
    for (const call of offlineCalls) {
      try {
        const response = await fetch('/api/calls', {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
          },
          body: JSON.stringify(call)
        });
        
        if (response.ok) {
          await removeOfflineCall(call.id);
          ;
        }
      } catch (error) {
        console.error('❌ Failed to sync call:', call.id, error);
      }
    }
  } catch (error) {
    console.error('❌ Background sync failed:', error);
  }
}

async function syncMessages() {
  try {
    ;
    // Similar implementation for messages
  } catch (error) {
    console.error('❌ Message sync failed:', error);
  }
}

// Placeholder functions for IndexedDB operations
async function getOfflineCalls() {
  // Implementation would use IndexedDB to get offline calls
  return [];
}

async function removeOfflineCall(id) {
  // Implementation would remove call from IndexedDB
  ;
}

// Error handling
self.addEventListener('error', (event) => {
  console.error('❌ Service Worker error:', event.error);
});

self.addEventListener('unhandledrejection', (event) => {
  console.error('❌ Service Worker unhandled rejection:', event.reason);
});

;