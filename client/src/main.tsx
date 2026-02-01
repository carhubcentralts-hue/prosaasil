import React, { StrictMode } from 'react' // ✅ CRITICAL: Explicit React import for classic JSX
import { createRoot } from 'react-dom/client'
import { App } from './app/App'
import './index.css'

// 🛡️ CLIENT GUARD: Auto-reload on chunk load errors (deploy race condition)
// This handles the case where user has old HTML cached pointing to non-existent chunks
(function () {
  const KEY = "chunk_reload_once";
  window.addEventListener("error", (e) => {
    // Only process ErrorEvent with a message
    if (!(e instanceof ErrorEvent) || !e.message) return;
    
    const msg = e.message;
    if (msg.includes("Failed to fetch dynamically imported module") ||
        msg.includes("Loading chunk") ||
        msg.includes("ChunkLoadError")) {
      console.warn('[CHUNK-GUARD] Detected chunk load error, reloading once...', msg);
      if (!sessionStorage.getItem(KEY)) {
        sessionStorage.setItem(KEY, "1");
        location.reload(); // Hard reload once only (prevents infinite loop)
      } else {
        console.error('[CHUNK-GUARD] Already reloaded once, not reloading again to prevent loop');
      }
    }
  });
})();

// 🔔 SERVICE WORKER REGISTRATION FOR PUSH NOTIFICATIONS
// Register SW early on app load (production/HTTPS only)
function registerServiceWorker() {
  if ('serviceWorker' in navigator) {
    // Only register in production (HTTPS) or local development
    const hostname = window.location.hostname;
    const isLocalDev = hostname === 'localhost' || 
                       hostname === '127.0.0.1' ||
                       hostname.startsWith('192.168.') ||
                       hostname.endsWith('.local');
    const isSecure = window.location.protocol === 'https:' || isLocalDev;
    
    if (isSecure) {
      navigator.serviceWorker.register('/sw.js')
        .then((registration) => {
          console.log('🔔 [SW] Service Worker registered:', registration.scope);
        })
        .catch((error) => {
          console.warn('🔔 [SW] Registration failed (non-critical):', error);
        });
    } else {
      console.log('🔔 [SW] Skipped: not HTTPS');
    }
  }
}

// Register SW after DOM is ready
if (document.readyState === 'loading') {
  document.addEventListener('DOMContentLoaded', registerServiceWorker);
} else {
  registerServiceWorker();
}

// 🚨 ERROR VISIBILITY - Catch and display runtime errors
function showError(msg: string, stack?: string) {
  console.error('[BOOT ERROR]', msg, stack);
  const root = document.getElementById('root');
  if (root) {
    root.innerHTML = `
      <div style="padding: 20px; font-family: monospace; background: #fee; color: #c00; white-space: pre-wrap;">
        <h2>❌ שגיאת טעינה</h2>
        <p><strong>הודעה:</strong> ${msg}</p>
        ${stack ? `<details><summary>Stack Trace</summary>${stack}</details>` : ''}
        <p style="margin-top: 20px; font-size: 12px;">נסה: Cmd/Ctrl+Shift+R (Hard Refresh)</p>
      </div>
    `;
  }
}

window.onerror = (msg, source, lineno, colno, error) => {
  showError(String(msg), error?.stack);
  return true;
};

window.onunhandledrejection = (event) => {
  showError(String(event.reason?.message || event.reason), event.reason?.stack);
};

// 🚀 SAFE MOUNT with error handling
try {
  const rootElement = document.getElementById('root');
  if (!rootElement) {
    showError('#root element not found in index.html');
  } else {
    // 🔍 PROBE: Verify React is not null (critical for Safari)
    console.log('[BOOT] React version:', React?.version, 'useEffect?', !!React?.useEffect);
    
    if (!React || !React.useEffect) {
      throw new Error('React object is null or missing useEffect - bundle problem!');
    }
    
    const root = createRoot(rootElement);
    root.render(
      <StrictMode>
        <App />
      </StrictMode>
    );
    console.log('✅ [BOOT] App mounted successfully');
  }
} catch (error: any) {
  console.error('[BOOT] Mount failed:', error);
  showError('Failed to mount React app', error?.stack || String(error));
}