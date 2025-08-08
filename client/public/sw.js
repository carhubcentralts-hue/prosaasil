// Service Worker for Hebrew AI Call Center CRM
// עובד שירות עבור מערכת CRM מוקד שיחות AI בעברית

const CACHE_NAME = 'hebrew-ai-crm-v1';
const STATIC_CACHE_URLS = [
  '/',
  '/admin/dashboard',
  '/admin/calls', 
  '/admin/whatsapp',
  '/admin/crm',
  '/static/css/app.css',
];

// Install event - cache static assets
self.addEventListener('install', event => {
  console.log('🔧 Service Worker installing...');
  event.waitUntil(
    caches.open(CACHE_NAME)
      .then(cache => {
        console.log('📦 Caching static assets');
        return cache.addAll(STATIC_CACHE_URLS);
      })
      .then(() => {
        console.log('✅ Service Worker installed successfully');
        return self.skipWaiting();
      })
  );
});

// Activate event - cleanup old caches
self.addEventListener('activate', event => {
  console.log('🚀 Service Worker activating...');
  event.waitUntil(
    caches.keys()
      .then(cacheNames => {
        return Promise.all(
          cacheNames
            .filter(cacheName => cacheName !== CACHE_NAME)
            .map(cacheName => {
              console.log('🗑️ Deleting old cache:', cacheName);
              return caches.delete(cacheName);
            })
        );
      })
      .then(() => {
        console.log('✅ Service Worker activated');
        return self.clients.claim();
      })
  );
});

// Fetch event - serve from cache, fallback to network
self.addEventListener('fetch', event => {
  // Skip non-GET requests
  if (event.request.method !== 'GET') {
    return;
  }

  event.respondWith(
    caches.match(event.request)
      .then(response => {
        // Return cached version or fetch from network
        return response || fetch(event.request);
      })
      .catch(() => {
        // Fallback for offline scenarios
        if (event.request.destination === 'document') {
          return caches.match('/');
        }
      })
  );
});

// Push event - handle task notifications
self.addEventListener('push', event => {
  console.log('📱 Push notification received');
  
  let data = {};
  if (event.data) {
    try {
      data = event.data.json();
    } catch (e) {
      console.error('Failed to parse push data:', e);
      data = {
        title: 'Hebrew AI CRM',
        body: event.data.text() || 'התראה חדשה'
      };
    }
  }

  const title = data.title || 'AgentLocator';
  const options = {
    body: data.body || 'יש לך משימה חדשה',
    icon: '/favicon.ico',
    badge: '/favicon.ico',
    tag: data.tag || 'task-notification',
    data: data,
    actions: [
      {
        action: 'call',
        title: 'התקשר 📞',
        icon: '/icons/phone.png'
      },
      {
        action: 'whatsapp', 
        title: 'WhatsApp 💬',
        icon: '/icons/whatsapp.png'
      },
      {
        action: 'snooze_15',
        title: 'נדנוד 15 דקות ⏰',
        icon: '/icons/snooze.png'
      }
    ],
    requireInteraction: true, // Keep notification visible until user interacts
    vibrate: [200, 100, 200] // Vibration pattern for mobile devices
  };

  event.waitUntil(
    self.registration.showNotification(title, options)
      .then(() => {
        console.log('✅ Notification displayed successfully');
      })
      .catch(error => {
        console.error('❌ Failed to show notification:', error);
      })
  );
});

// Notification click event - handle user interaction
self.addEventListener('notificationclick', event => {
  console.log('👆 Notification clicked:', event.notification.tag, event.action);
  
  event.notification.close();
  
  const data = event.notification.data || {};
  const action = event.action;
  
  // Handle different notification actions
  if (action === 'call') {
    // Open the calls page and focus on specific task
    event.waitUntil(
      clients.openWindow(`/admin/calls?task_id=${data.task_id}`)
    );
  } else if (action === 'whatsapp') {
    // Open WhatsApp page for the customer
    event.waitUntil(
      clients.openWindow(`/admin/whatsapp?customer_id=${data.customer_id}`)
    );
  } else if (action === 'snooze_15') {
    // Send snooze request to API
    event.waitUntil(
      fetch(`/api/tasks/${data.task_id}`, {
        method: 'PATCH',
        headers: {
          'Content-Type': 'application/json'
        },
        body: JSON.stringify({
          snooze_until: new Date(Date.now() + 15 * 60 * 1000).toISOString()
        })
      })
      .then(response => {
        if (response.ok) {
          console.log('✅ Task snoozed for 15 minutes');
        }
      })
      .catch(error => {
        console.error('❌ Failed to snooze task:', error);
      })
    );
  } else {
    // Default action - open the task or dashboard
    const url = data.task_id ? `/admin/crm?task_id=${data.task_id}` : '/admin/dashboard';
    event.waitUntil(
      clients.openWindow(url)
    );
  }
});

// Background sync event - for offline task updates
self.addEventListener('sync', event => {
  console.log('🔄 Background sync event:', event.tag);
  
  if (event.tag === 'task-sync') {
    event.waitUntil(
      // Sync pending task updates when back online
      syncTaskUpdates()
    );
  }
});

// Helper function to sync task updates
async function syncTaskUpdates() {
  try {
    // Get pending updates from IndexedDB or localStorage
    const pendingUpdates = await getPendingTaskUpdates();
    
    for (const update of pendingUpdates) {
      try {
        const response = await fetch(`/api/tasks/${update.taskId}`, {
          method: 'PATCH',
          headers: {
            'Content-Type': 'application/json'
          },
          body: JSON.stringify(update.data)
        });
        
        if (response.ok) {
          await removePendingUpdate(update.id);
          console.log('✅ Synced task update:', update.taskId);
        }
      } catch (error) {
        console.error('❌ Failed to sync task update:', error);
      }
    }
  } catch (error) {
    console.error('❌ Background sync failed:', error);
  }
}

// Mock function - would need to implement with IndexedDB
async function getPendingTaskUpdates() {
  // This would fetch from IndexedDB in a real implementation
  return [];
}

// Mock function - would need to implement with IndexedDB  
async function removePendingUpdate(updateId) {
  // This would remove from IndexedDB in a real implementation
  console.log('Removing pending update:', updateId);
}