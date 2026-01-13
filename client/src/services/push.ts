/**
 * Push Notifications Service
 * 
 * Manages Web Push subscription lifecycle:
 * - Check browser support
 * - Request notification permission
 * - Subscribe to push notifications
 * - Unsubscribe from push notifications
 */

import { http } from './http';

// Types
export interface PushStatus {
  supported: boolean;
  permission: NotificationPermission | 'unsupported';
  subscribed: boolean;
  configured: boolean;
}

interface VapidKeyResponse {
  success: boolean;
  publicKey?: string;
  error?: string;
}

interface SubscribeResponse {
  success: boolean;
  message?: string;
  error?: string;
}

interface StatusResponse {
  success: boolean;
  configured: boolean;
  subscriptionCount: number;
  enabled: boolean;
}

interface TestResponse {
  success: boolean;
  message?: string;
  error?: string;
  result?: {
    total: number;
    successful: number;
    failed: number;
    deactivated: number;
  };
}

// Check if push notifications are supported
export function isPushSupported(): boolean {
  return (
    'serviceWorker' in navigator &&
    'PushManager' in window &&
    'Notification' in window
  );
}

// Get current permission status
export function getPermissionStatus(): NotificationPermission | 'unsupported' {
  if (!isPushSupported()) {
    return 'unsupported';
  }
  return Notification.permission;
}

// Check if running on iOS (needs special handling)
export function isIOS(): boolean {
  return /iPad|iPhone|iPod/.test(navigator.userAgent);
}

// Check if running as PWA (standalone mode)
export function isPWA(): boolean {
  return window.matchMedia('(display-mode: standalone)').matches ||
    (window.navigator as any).standalone === true;
}

// Get push notification status
export async function getPushStatus(): Promise<PushStatus> {
  const supported = isPushSupported();
  const permission = getPermissionStatus();
  
  let subscribed = false;
  let configured = false;
  
  if (supported && permission === 'granted') {
    try {
      const response = await http.get<StatusResponse>('/api/push/status');
      subscribed = response.enabled;
      configured = response.configured;
    } catch (error) {
      console.error('Error checking push status:', error);
    }
  }
  
  return { supported, permission, subscribed, configured };
}

// Register service worker
async function registerServiceWorker(): Promise<ServiceWorkerRegistration | null> {
  if (!('serviceWorker' in navigator)) {
    return null;
  }
  
  try {
    const registration = await navigator.serviceWorker.register('/sw.js');
    console.log('[Push] Service worker registered:', registration.scope);
    return registration;
  } catch (error) {
    console.error('[Push] Service worker registration failed:', error);
    return null;
  }
}

// Convert base64 string to Uint8Array (for applicationServerKey)
function urlBase64ToUint8Array(base64String: string): Uint8Array {
  const padding = '='.repeat((4 - (base64String.length % 4)) % 4);
  const base64 = (base64String + padding)
    .replace(/-/g, '+')
    .replace(/_/g, '/');
  
  const rawData = window.atob(base64);
  const outputArray = new Uint8Array(rawData.length);
  
  for (let i = 0; i < rawData.length; ++i) {
    outputArray[i] = rawData.charCodeAt(i);
  }
  
  return outputArray;
}

// Subscribe to push notifications
export async function subscribeToPush(): Promise<{ success: boolean; message: string }> {
  if (!isPushSupported()) {
    return { success: false, message: 'התראות לא נתמכות בדפדפן זה' };
  }
  
  // Request notification permission
  const permission = await Notification.requestPermission();
  if (permission !== 'granted') {
    return { 
      success: false, 
      message: permission === 'denied' 
        ? 'ההתראות חסומות בהגדרות הדפדפן' 
        : 'ההרשאה נדחתה' 
    };
  }
  
  try {
    // Get VAPID public key
    const vapidResponse = await http.get<VapidKeyResponse>('/api/push/vapid-public-key');
    if (!vapidResponse.success || !vapidResponse.publicKey) {
      return { success: false, message: 'השרת אינו מוגדר לשליחת התראות' };
    }
    
    // Register service worker
    const registration = await registerServiceWorker();
    if (!registration) {
      return { success: false, message: 'שגיאה ברישום Service Worker' };
    }
    
    // Wait for service worker to be ready
    await navigator.serviceWorker.ready;
    
    // Subscribe to push
    const applicationServerKey = urlBase64ToUint8Array(vapidResponse.publicKey);
    const subscription = await registration.pushManager.subscribe({
      userVisibleOnly: true,
      applicationServerKey: applicationServerKey as BufferSource
    });
    
    // Send subscription to server
    const subscriptionJson = subscription.toJSON();
    const response = await http.post<SubscribeResponse>('/api/push/subscribe', {
      subscription: subscriptionJson,
      deviceInfo: navigator.userAgent
    });
    
    if (response.success) {
      return { success: true, message: 'ההתראות הופעלו בהצלחה!' };
    } else {
      return { success: false, message: response.error || 'שגיאה בהפעלת התראות' };
    }
    
  } catch (error) {
    console.error('[Push] Subscribe error:', error);
    return { success: false, message: 'שגיאה בהפעלת התראות' };
  }
}

// Unsubscribe from push notifications
export async function unsubscribeFromPush(): Promise<{ success: boolean; message: string }> {
  if (!isPushSupported()) {
    return { success: false, message: 'התראות לא נתמכות' };
  }
  
  try {
    const registration = await navigator.serviceWorker.ready;
    const subscription = await registration.pushManager.getSubscription();
    
    if (subscription) {
      const endpoint = subscription.endpoint;
      
      // Unsubscribe locally
      await subscription.unsubscribe();
      
      // Notify server
      await http.post<SubscribeResponse>('/api/push/unsubscribe', { endpoint });
    }
    
    return { success: true, message: 'ההתראות בוטלו' };
    
  } catch (error) {
    console.error('[Push] Unsubscribe error:', error);
    return { success: false, message: 'שגיאה בביטול התראות' };
  }
}

// Send test notification
export async function sendTestNotification(): Promise<TestResponse> {
  try {
    const response = await http.post<TestResponse>('/api/push/test', {});
    return response;
  } catch (error) {
    console.error('[Push] Test notification error:', error);
    return { success: false, error: 'שגיאה בשליחת הודעת בדיקה' };
  }
}
