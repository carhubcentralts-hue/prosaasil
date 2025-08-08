/**
 * AgentLocator v39 - Service Worker
 * Service Worker עבור PWA ו־Push Notifications
 */

const CACHE_NAME = 'agentlocator-v39-cache';
const STATIC_ASSETS = [
    '/',
    '/static/css/index.css',
    '/static/js/index.js',
    '/manifest.json'
];

// Install event - cache static assets
self.addEventListener('install', (event) => {
    console.log('🔧 Service Worker: Installing');
    
    event.waitUntil(
        caches.open(CACHE_NAME)
            .then((cache) => {
                console.log('📦 Service Worker: Caching static assets');
                return cache.addAll(STATIC_ASSETS.filter(url => url !== '/'));
            })
            .then(() => {
                console.log('✅ Service Worker: Installation complete');
                self.skipWaiting();
            })
            .catch((error) => {
                console.error('❌ Service Worker: Installation failed', error);
            })
    );
});

// Activate event - cleanup old caches
self.addEventListener('activate', (event) => {
    console.log('🚀 Service Worker: Activating');
    
    event.waitUntil(
        caches.keys()
            .then((cacheNames) => {
                return Promise.all(
                    cacheNames.map((cacheName) => {
                        if (cacheName !== CACHE_NAME) {
                            console.log('🗑️ Service Worker: Deleting old cache', cacheName);
                            return caches.delete(cacheName);
                        }
                    })
                );
            })
            .then(() => {
                console.log('✅ Service Worker: Activation complete');
                return self.clients.claim();
            })
    );
});

// Fetch event - serve cached content when offline
self.addEventListener('fetch', (event) => {
    // Skip non-GET requests and external resources
    if (event.request.method !== 'GET' || 
        !event.request.url.startsWith(self.location.origin)) {
        return;
    }
    
    event.respondWith(
        caches.match(event.request)
            .then((response) => {
                // Return cached version if available
                if (response) {
                    return response;
                }
                
                // Otherwise fetch from network
                return fetch(event.request)
                    .then((response) => {
                        // Cache successful responses
                        if (response.status === 200) {
                            const responseClone = response.clone();
                            caches.open(CACHE_NAME)
                                .then((cache) => {
                                    cache.put(event.request, responseClone);
                                });
                        }
                        return response;
                    })
                    .catch((error) => {
                        console.log('🔌 Service Worker: Network fetch failed, serving offline page');
                        
                        // Return offline page for navigation requests
                        if (event.request.mode === 'navigate') {
                            return new Response(`
                                <!DOCTYPE html>
                                <html lang="he" dir="rtl">
                                <head>
                                    <meta charset="UTF-8">
                                    <meta name="viewport" content="width=device-width, initial-scale=1.0">
                                    <title>AgentLocator - לא מחובר</title>
                                    <style>
                                        body { font-family: 'Segoe UI', sans-serif; text-align: center; padding: 2rem; background: #f5f5f5; }
                                        .offline-container { max-width: 400px; margin: 0 auto; background: white; padding: 2rem; border-radius: 10px; box-shadow: 0 4px 6px rgba(0,0,0,0.1); }
                                        h1 { color: #333; margin-bottom: 1rem; }
                                        p { color: #666; margin-bottom: 1.5rem; }
                                        button { background: #007bff; color: white; border: none; padding: 10px 20px; border-radius: 5px; cursor: pointer; }
                                        button:hover { background: #0056b3; }
                                    </style>
                                </head>
                                <body>
                                    <div class="offline-container">
                                        <h1>🔌 לא מחובר לרשת</h1>
                                        <p>AgentLocator זמין במצב לא מקוון מוגבל. חלק מהתכונות עשויות שלא לפעול.</p>
                                        <button onclick="window.location.reload()">נסה שוב</button>
                                    </div>
                                    <script>
                                        // Auto-retry when back online
                                        window.addEventListener('online', () => {
                                            window.location.reload();
                                        });
                                    </script>
                                </body>
                                </html>
                            `, { 
                                headers: { 'Content-Type': 'text/html; charset=utf-8' } 
                            });
                        }
                        
                        throw error;
                    });
            })
    );
});

// Push notification event
self.addEventListener('push', (event) => {
    console.log('🔔 Service Worker: Push notification received');
    
    let data = {};
    try {
        data = event.data ? event.data.json() : {};
    } catch (e) {
        console.error('❌ Service Worker: Failed to parse push data', e);
        data = { title: 'התראה חדשה', body: 'יש לך הודעה חדשה ב־AgentLocator' };
    }
    
    const { title, body, icon, badge, tag, requireInteraction } = data;
    
    const options = {
        body: body || 'יש לך הודעה חדשה',
        icon: icon || '/favicon.ico',
        badge: badge || '/favicon.ico',
        tag: tag || 'default',
        requireInteraction: requireInteraction || true,
        data: data,
        actions: [
            {
                action: 'open',
                title: 'פתח',
                icon: '/icons/open.png'
            },
            {
                action: 'call',
                title: 'התקשר',
                icon: '/icons/call.png'
            },
            {
                action: 'whatsapp',
                title: 'WhatsApp',
                icon: '/icons/whatsapp.png'
            },
            {
                action: 'snooze',
                title: 'דחה',
                icon: '/icons/snooze.png'
            }
        ],
        vibrate: [200, 100, 200],
        silent: false
    };
    
    event.waitUntil(
        self.registration.showNotification(title || 'AgentLocator', options)
    );
});

// Notification click event
self.addEventListener('notificationclick', (event) => {
    console.log('👆 Service Worker: Notification clicked', event.action);
    
    event.notification.close();
    
    const { action } = event;
    const { task_id, customer_phone, customer_id } = event.notification.data || {};
    
    event.waitUntil(
        self.clients.matchAll({ type: 'window', includeUncontrolled: true })
            .then((clients) => {
                // Try to focus existing window
                for (const client of clients) {
                    if (client.url.includes(self.location.origin)) {
                        return client.focus().then(() => {
                            // Send message to client about the action
                            client.postMessage({
                                type: 'NOTIFICATION_CLICK',
                                action: action,
                                data: { task_id, customer_phone, customer_id }
                            });
                        });
                    }
                }
                
                // Open new window if no existing window
                let url = '/';
                
                if (action === 'call' && customer_phone) {
                    url = `/?action=call&phone=${encodeURIComponent(customer_phone)}`;
                } else if (action === 'whatsapp' && customer_phone) {
                    url = `/?action=whatsapp&phone=${encodeURIComponent(customer_phone)}`;
                } else if (customer_id) {
                    url = `/?customer_id=${customer_id}`;
                }
                
                return self.clients.openWindow(url);
            })
    );
});

// Background sync event (for offline task completion)
self.addEventListener('sync', (event) => {
    console.log('🔄 Service Worker: Background sync', event.tag);
    
    if (event.tag === 'sync-tasks') {
        event.waitUntil(
            syncPendingTasks()
        );
    }
});

// Helper function to sync pending tasks
async function syncPendingTasks() {
    try {
        // Get pending tasks from IndexedDB or localStorage
        const pendingTasks = JSON.parse(localStorage.getItem('pendingTasks') || '[]');
        
        for (const task of pendingTasks) {
            try {
                const response = await fetch('/api/tasks/sync', {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json',
                    },
                    body: JSON.stringify(task)
                });
                
                if (response.ok) {
                    // Remove synced task from pending list
                    const updatedTasks = pendingTasks.filter(t => t.id !== task.id);
                    localStorage.setItem('pendingTasks', JSON.stringify(updatedTasks));
                    console.log('✅ Service Worker: Task synced', task.id);
                } else {
                    console.error('❌ Service Worker: Task sync failed', task.id, response.status);
                }
            } catch (error) {
                console.error('❌ Service Worker: Task sync error', task.id, error);
            }
        }
    } catch (error) {
        console.error('❌ Service Worker: Background sync failed', error);
    }
}

// Message event - handle messages from main thread
self.addEventListener('message', (event) => {
    console.log('💬 Service Worker: Message received', event.data);
    
    const { type, data } = event.data || {};
    
    switch (type) {
        case 'SKIP_WAITING':
            self.skipWaiting();
            break;
        case 'GET_VERSION':
            event.ports[0].postMessage({ version: CACHE_NAME });
            break;
        case 'CLEAR_CACHE':
            caches.delete(CACHE_NAME).then(() => {
                event.ports[0].postMessage({ cleared: true });
            });
            break;
        case 'CACHE_URLS':
            if (data && data.urls) {
                caches.open(CACHE_NAME).then((cache) => {
                    cache.addAll(data.urls);
                });
            }
            break;
        default:
            console.log('🤷 Service Worker: Unknown message type', type);
    }
});

console.log('🚀 Service Worker: Loaded and ready for AgentLocator v39');