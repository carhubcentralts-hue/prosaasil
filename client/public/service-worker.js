/**
 * AgentLocator v42 - Service Worker
 * עובד שירות מתקדם עם תמיכה בקאש, הודעות push ועבודה אופליין
 */

const CACHE_NAME = 'agentlocator-v42-cache';
const CACHE_VERSION = '2025.08.08';
const FULL_CACHE_NAME = `${CACHE_NAME}-${CACHE_VERSION}`;

// Hebrew RTL support files to cache
const CACHE_URLS = [
  '/',
  '/offline.html',
  '/assets/index.css',
  '/assets/index.js',
  '/assets/fonts/assistant-hebrew.woff2',
  '/manifest.json',
  '/logo-192.png',
  '/logo-512.png'
];

// API endpoints to cache for offline access
const API_CACHE_URLS = [
  '/api/auth/user',
  '/api/admin/stats',
  '/api/customers',
  '/api/calls',
  '/api/whatsapp/conversations'
];

// Install event - cache resources
self.addEventListener('install', event => {
  ;
  
  event.waitUntil(
    caches.open(FULL_CACHE_NAME)
      .then(cache => {
        ;
        return cache.addAll(CACHE_URLS);
      })
      .then(() => {
        ;
        // Force activation of new service worker
        return self.skipWaiting();
      })
      .catch(error => {
        console.error('❌ Failed to cache resources:', error);
      })
  );
});

// Activate event - clean up old caches
self.addEventListener('activate', event => {
  ;
  
  event.waitUntil(
    caches.keys()
      .then(cacheNames => {
        return Promise.all(
          cacheNames.map(cacheName => {
            if (cacheName.startsWith(CACHE_NAME) && cacheName !== FULL_CACHE_NAME) {
              ;
              return caches.delete(cacheName);
            }
          })
        );
      })
      .then(() => {
        ;
        return self.clients.claim();
      })
  );
});

// Fetch event - network first with cache fallback
self.addEventListener('fetch', event => {
  const { request } = event;
  const url = new URL(request.url);
  
  // Skip non-GET requests
  if (request.method !== 'GET') {
    return;
  }
  
  // Handle different request types
  if (url.pathname.startsWith('/api/')) {
    // API requests - network first, cache fallback
    event.respondWith(handleApiRequest(request));
  } else if (url.pathname.endsWith('.css') || url.pathname.endsWith('.js') || url.pathname.endsWith('.woff2')) {
    // Static assets - cache first
    event.respondWith(handleStaticAsset(request));
  } else {
    // HTML pages - network first with cache fallback
    event.respondWith(handlePageRequest(request));
  }
});

// Handle API requests with network-first strategy
async function handleApiRequest(request) {
  try {
    // Try network first
    const networkResponse = await fetch(request.clone());
    
    // Cache successful responses
    if (networkResponse.ok) {
      const cache = await caches.open(FULL_CACHE_NAME);
      await cache.put(request.clone(), networkResponse.clone());
    }
    
    return networkResponse;
  } catch (error) {
    ;
    
    // Try cache fallback
    const cachedResponse = await caches.match(request);
    if (cachedResponse) {
      return cachedResponse;
    }
    
    // Return offline response for failed API requests
    return new Response(JSON.stringify({
      error: 'המערכת אינה זמינה כעת',
      offline: true,
      cached: false
    }), {
      status: 503,
      headers: {
        'Content-Type': 'application/json; charset=utf-8',
        'Cache-Control': 'no-cache'
      }
    });
  }
}

// Handle static assets with cache-first strategy
async function handleStaticAsset(request) {
  const cachedResponse = await caches.match(request);
  
  if (cachedResponse) {
    return cachedResponse;
  }
  
  try {
    const networkResponse = await fetch(request);
    
    if (networkResponse.ok) {
      const cache = await caches.open(FULL_CACHE_NAME);
      await cache.put(request, networkResponse.clone());
    }
    
    return networkResponse;
  } catch (error) {
    ;
    return new Response('', { status: 404 });
  }
}

// Handle page requests
async function handlePageRequest(request) {
  try {
    // Try network first
    const networkResponse = await fetch(request);
    
    // Cache successful HTML responses
    if (networkResponse.ok && networkResponse.headers.get('Content-Type')?.includes('text/html')) {
      const cache = await caches.open(FULL_CACHE_NAME);
      await cache.put(request, networkResponse.clone());
    }
    
    return networkResponse;
  } catch (error) {
    ;
    
    // Try cache fallback
    const cachedResponse = await caches.match(request);
    if (cachedResponse) {
      return cachedResponse;
    }
    
    // Return offline page for failed page requests
    const offlineResponse = await caches.match('/offline.html');
    if (offlineResponse) {
      return offlineResponse;
    }
    
    // Fallback offline HTML
    return new Response(`
      <!DOCTYPE html>
      <html lang="he" dir="rtl">
      <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>AgentLocator - אופליין</title>
        <style>
          body { 
            font-family: Assistant, Arial, sans-serif;
            text-align: center; 
            padding: 2rem;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            min-height: 100vh;
            display: flex;
            align-items: center;
            justify-content: center;
          }
          .container {
            background: rgba(255,255,255,0.1);
            padding: 2rem;
            border-radius: 1rem;
            backdrop-filter: blur(10px);
          }
        </style>
      </head>
      <body>
        <div class="container">
          <h1>🔌 אין חיבור לאינטרנט</h1>
          <p>מערכת AgentLocator CRM זמנית לא זמינה</p>
          <button onclick="window.location.reload()" style="
            background: white;
            color: #667eea;
            border: none;
            padding: 1rem 2rem;
            border-radius: 0.5rem;
            font-weight: bold;
            cursor: pointer;
          ">נסה שוב</button>
        </div>
      </body>
      </html>
    `, {
      headers: {
        'Content-Type': 'text/html; charset=utf-8'
      }
    });
  }
}

// Background sync for offline actions
self.addEventListener('sync', event => {
  ;
  
  if (event.tag === 'background-sync-customers') {
    event.waitUntil(syncCustomerData());
  } else if (event.tag === 'background-sync-calls') {
    event.waitUntil(syncCallData());
  }
});

// Sync customer data when back online
async function syncCustomerData() {
  ;
  try {
    // Implement customer data sync logic here
    const response = await fetch('/api/customers/sync', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' }
    });
    
    if (response.ok) {
      ;
    } else {
      ;
    }
  } catch (error) {
    console.error('❌ Error syncing customer data:', error);
  }
}

// Sync call data when back online
async function syncCallData() {
  ;
  try {
    const response = await fetch('/api/calls/sync', {
      method: 'POST', 
      headers: { 'Content-Type': 'application/json' }
    });
    
    if (response.ok) {
      ;
    }
  } catch (error) {
    console.error('❌ Error syncing call data:', error);
  }
}

// Push notification handler
self.addEventListener('push', event => {
  ;
  
  if (!event.data) {
    return;
  }
  
  try {
    const data = event.data.json();
    const options = {
      body: data.body || 'הודעה חדשה מ-AgentLocator CRM',
      icon: '/logo-192.png',
      badge: '/logo-192.png',
      dir: 'rtl',
      lang: 'he',
      tag: data.tag || 'general',
      requireInteraction: data.requireInteraction || false,
      actions: data.actions || [
        {
          action: 'view',
          title: 'צפייה'
        },
        {
          action: 'dismiss', 
          title: 'ביטול'
        }
      ],
      data: data.data || {}
    };
    
    event.waitUntil(
      self.registration.showNotification(
        data.title || 'AgentLocator CRM',
        options
      )
    );
  } catch (error) {
    console.error('❌ Error handling push notification:', error);
  }
});

// Notification click handler
self.addEventListener('notificationclick', event => {
  ;
  
  event.notification.close();
  
  const action = event.action;
  const data = event.notification.data;
  
  if (action === 'view') {
    // Open the app to relevant page
    const urlToOpen = data.url || '/';
    
    event.waitUntil(
      clients.matchAll({ type: 'window', includeUncontrolled: true })
        .then(clientList => {
          // Check if app is already open
          for (const client of clientList) {
            if (client.url.includes(self.location.origin) && 'focus' in client) {
              client.navigate(urlToOpen);
              return client.focus();
            }
          }
          
          // Open new window if app not open
          if (clients.openWindow) {
            return clients.openWindow(urlToOpen);
          }
        })
    );
  }
});

// Message handler for communication with main thread
self.addEventListener('message', event => {
  ;
  
  if (event.data && event.data.type === 'SKIP_WAITING') {
    self.skipWaiting();
  } else if (event.data && event.data.type === 'CACHE_URLS') {
    // Cache additional URLs requested by main thread
    const { urls } = event.data;
    event.waitUntil(
      caches.open(FULL_CACHE_NAME)
        .then(cache => cache.addAll(urls))
        .then(() => {
          event.ports[0].postMessage({ success: true });
        })
        .catch(error => {
          console.error('❌ Failed to cache additional URLs:', error);
          event.ports[0].postMessage({ success: false, error: error.message });
        })
    );
  }
});

;
;
;