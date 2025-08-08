/**
 * AgentLocator v42 - Service Worker Registration
 * רישום עובד שירות מתקדם עם תמיכה בעברית ו-PWA
 */

const isLocalhost = Boolean(
  window.location.hostname === 'localhost' ||
  window.location.hostname === '[::1]' ||
  window.location.hostname.match(
    /^127(?:\.(?:25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)){3}$/
  )
);

export function register(config) {
  if ('serviceWorker' in navigator) {
    const publicUrl = new URL(process.env.PUBLIC_URL || '', window.location.href);
    if (publicUrl.origin !== window.location.origin) {
      return;
    }

    window.addEventListener('load', () => {
      const swUrl = `${process.env.PUBLIC_URL}/service-worker.js`;

      if (isLocalhost) {
        checkValidServiceWorker(swUrl, config);
        navigator.serviceWorker.ready.then(() => {
          console.log('🚀 AgentLocator v42 Service Worker ready in development mode');
        });
      } else {
        registerValidSW(swUrl, config);
      }
    });
  }
}

function registerValidSW(swUrl, config) {
  navigator.serviceWorker
    .register(swUrl)
    .then(registration => {
      console.log('✅ Service Worker registered successfully:', registration.scope);
      
      // Update found
      registration.onupdatefound = () => {
        const installingWorker = registration.installing;
        if (installingWorker == null) {
          return;
        }
        
        installingWorker.onstatechange = () => {
          if (installingWorker.state === 'installed') {
            if (navigator.serviceWorker.controller) {
              // New content available
              console.log('🔄 New content is available; please refresh.');
              
              // Show Hebrew update notification
              showUpdateNotification(registration);
              
              if (config && config.onUpdate) {
                config.onUpdate(registration);
              }
            } else {
              // Content cached for offline use
              console.log('📦 Content is cached for offline use.');
              
              if (config && config.onSuccess) {
                config.onSuccess(registration);
              }
            }
          }
        };
      };
    })
    .catch(error => {
      console.error('❌ Error during service worker registration:', error);
    });
}

function checkValidServiceWorker(swUrl, config) {
  fetch(swUrl, {
    headers: { 'Service-Worker': 'script' },
  })
    .then(response => {
      const contentType = response.headers.get('content-type');
      if (
        response.status === 404 ||
        (contentType != null && contentType.indexOf('javascript') === -1)
      ) {
        navigator.serviceWorker.ready.then(registration => {
          registration.unregister().then(() => {
            window.location.reload();
          });
        });
      } else {
        registerValidSW(swUrl, config);
      }
    })
    .catch(() => {
      console.log('❌ No internet connection found. App is running in offline mode.');
    });
}

function showUpdateNotification(registration) {
  // Create Hebrew update notification
  const notification = document.createElement('div');
  notification.innerHTML = `
    <div style="
      position: fixed;
      top: 20px;
      right: 20px;
      background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
      color: white;
      padding: 1rem 1.5rem;
      border-radius: 12px;
      box-shadow: 0 10px 25px rgba(0,0,0,0.15);
      z-index: 10000;
      font-family: Assistant, Arial, sans-serif;
      direction: rtl;
      max-width: 300px;
    ">
      <div style="font-weight: 600; margin-bottom: 0.5rem;">עדכון זמין</div>
      <div style="font-size: 0.9rem; margin-bottom: 1rem;">גרסה חדשה של המערכת זמינה</div>
      <div style="display: flex; gap: 0.5rem;">
        <button onclick="this.parentElement.parentElement.parentElement.remove(); window.location.reload();" style="
          background: rgba(255,255,255,0.2);
          border: none;
          color: white;
          padding: 0.5rem 1rem;
          border-radius: 6px;
          cursor: pointer;
          font-size: 0.85rem;
        ">עדכן עכשיו</button>
        <button onclick="this.parentElement.parentElement.parentElement.remove();" style="
          background: transparent;
          border: 1px solid rgba(255,255,255,0.3);
          color: white;
          padding: 0.5rem 1rem;
          border-radius: 6px;
          cursor: pointer;
          font-size: 0.85rem;
        ">מאוחר יותר</button>
      </div>
    </div>
  `;
  
  document.body.appendChild(notification);
  
  // Auto-hide after 30 seconds
  setTimeout(() => {
    if (notification.parentNode) {
      notification.parentNode.removeChild(notification);
    }
  }, 30000);
}

export function unregister() {
  if ('serviceWorker' in navigator) {
    navigator.serviceWorker.ready
      .then(registration => {
        registration.unregister();
        console.log('🗑️ Service Worker unregistered');
      })
      .catch(error => {
        console.error('❌ Error unregistering service worker:', error.message);
      });
  }
}

// Request notification permissions
export function requestNotificationPermission() {
  if ('Notification' in window && Notification.permission === 'default') {
    Notification.requestPermission().then(permission => {
      if (permission === 'granted') {
        console.log('✅ Notification permission granted');
        // Show test notification
        new Notification('AgentLocator CRM', {
          body: 'התראות פעילות במערכת פעילות',
          icon: '/logo-192.png',
          dir: 'rtl',
          lang: 'he'
        });
      }
    });
  }
}

// Check if app can be installed
export function checkInstallPrompt() {
  let deferredPrompt;
  
  window.addEventListener('beforeinstallprompt', (e) => {
    e.preventDefault();
    deferredPrompt = e;
    
    // Show custom install prompt
    showInstallPrompt(deferredPrompt);
  });
  
  window.addEventListener('appinstalled', () => {
    console.log('✅ AgentLocator v42 PWA installed successfully');
    deferredPrompt = null;
  });
}

function showInstallPrompt(deferredPrompt) {
  const installBanner = document.createElement('div');
  installBanner.innerHTML = `
    <div style="
      position: fixed;
      bottom: 20px;
      right: 20px;
      background: white;
      border: 1px solid #e2e8f0;
      padding: 1rem 1.5rem;
      border-radius: 12px;
      box-shadow: 0 10px 25px rgba(0,0,0,0.15);
      z-index: 10000;
      font-family: Assistant, Arial, sans-serif;
      direction: rtl;
      max-width: 320px;
    ">
      <div style="font-weight: 600; margin-bottom: 0.5rem; color: #1e293b;">התקן את האפליקציה</div>
      <div style="font-size: 0.9rem; margin-bottom: 1rem; color: #64748b;">קבל גישה מהירה ליכולות מתקדמות</div>
      <div style="display: flex; gap: 0.5rem;">
        <button onclick="installApp()" style="
          background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
          border: none;
          color: white;
          padding: 0.75rem 1.5rem;
          border-radius: 8px;
          cursor: pointer;
          font-size: 0.9rem;
          font-weight: 500;
        ">התקן</button>
        <button onclick="this.parentElement.parentElement.parentElement.remove();" style="
          background: transparent;
          border: 1px solid #e2e8f0;
          color: #64748b;
          padding: 0.75rem 1rem;
          border-radius: 8px;
          cursor: pointer;
          font-size: 0.9rem;
        ">לא תודה</button>
      </div>
    </div>
  `;
  
  // Add install function to window
  window.installApp = () => {
    if (deferredPrompt) {
      deferredPrompt.prompt();
      deferredPrompt.userChoice.then((choiceResult) => {
        if (choiceResult.outcome === 'accepted') {
          console.log('✅ User accepted the install prompt');
        }
        deferredPrompt = null;
      });
    }
    installBanner.remove();
  };
  
  document.body.appendChild(installBanner);
  
  // Auto-hide after 60 seconds
  setTimeout(() => {
    if (installBanner.parentNode) {
      installBanner.parentNode.removeChild(installBanner);
    }
  }, 60000);
}

// Initialize all PWA features
export function initializePWA() {
  // Register service worker
  register({
    onSuccess: () => {
      console.log('✅ AgentLocator v42 PWA ready for offline use');
    },
    onUpdate: (registration) => {
      console.log('🔄 New version available, prompting user to update');
    }
  });
  
  // Request notification permissions
  setTimeout(requestNotificationPermission, 3000);
  
  // Check for install prompt
  checkInstallPrompt();
  
  // Initialize background sync if supported
  if ('serviceWorker' in navigator && 'sync' in window.ServiceWorkerRegistration.prototype) {
    console.log('✅ Background sync supported');
  }
  
  console.log('🚀 AgentLocator v42 PWA initialization complete');
}