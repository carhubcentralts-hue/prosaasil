import React, { createContext, useContext, useState, useCallback, useEffect, useRef } from 'react';
import { http } from '../../services/http';
import { useAuth } from '../../features/auth/hooks';

const POLLING_INTERVAL = 30000; // Check for new notifications every 30 seconds

export interface Notification {
  id: string;
  type: 'call' | 'whatsapp' | 'lead' | 'task' | 'meeting' | 'payment' | 'system' | 'urgent';
  title: string;
  message: string;
  timestamp: Date;
  read: boolean;
  metadata?: {
    dueAt?: string;
    priority?: 'low' | 'medium' | 'high' | 'urgent';
    actionRequired?: boolean;
    [key: string]: any;
  };
}

interface NotificationContextType {
  notifications: Notification[];
  unreadCount: number;
  urgentNotifications: Notification[];
  refreshNotifications: () => Promise<void>;
  setNotificationCountCallback: (callback: (count: number) => void) => void;
  markAsComplete: (notificationId: string) => Promise<void>;
  deleteNotification: (notificationId: string) => Promise<void>;
  dismissUrgent: (notificationId: string) => void;
}

const NotificationContext = createContext<NotificationContextType | null>(null);

// Convert API notification to Notification type
function convertApiNotification(apiNotif: any): Notification {
  // BUILD 151: Handle system notifications (like WhatsApp disconnect)
  if (apiNotif.reminder_type === 'system_whatsapp_disconnect') {
    return {
      id: apiNotif.id,
      type: 'system',
      title: '⚠️ חיבור WhatsApp נותק',
      message: apiNotif.description || apiNotif.title || 'יש להתחבר מחדש להגדרות WhatsApp',
      timestamp: new Date(apiNotif.due_date),
      read: false,
      metadata: {
        priority: apiNotif.priority || 'high',
        actionRequired: true,
        reminderType: 'system_whatsapp_disconnect',
        navigateTo: '/app/settings',  // Navigation target for settings page (must be under /app)
        dueAt: apiNotif.due_date
      }
    };
  }
  
  // FIX: Handle appointment notifications
  if (apiNotif.reminder_type === 'system_appointment_created') {
    return {
      id: apiNotif.id,
      type: 'meeting',
      title: apiNotif.title || '📅 פגישה חדשה',
      message: apiNotif.description || apiNotif.title || 'נקבעה פגישה חדשה',
      timestamp: new Date(apiNotif.due_date),
      read: false,
      metadata: {
        priority: apiNotif.priority || 'medium',
        actionRequired: false,
        reminderType: 'system_appointment_created',
        navigateTo: '/app/calendar',
        dueAt: apiNotif.due_date
      }
    };
  }
  
  // Handle other system notifications generically
  if (apiNotif.reminder_type?.startsWith('system_')) {
    return {
      id: apiNotif.id,
      type: 'system',
      title: apiNotif.title || '🔔 התראת מערכת',
      message: apiNotif.description || apiNotif.title || 'התראה חדשה',
      timestamp: new Date(apiNotif.due_date),
      read: false,
      metadata: {
        priority: apiNotif.priority || 'medium',
        actionRequired: false,
        reminderType: apiNotif.reminder_type,
        dueAt: apiNotif.due_date
      }
    };
  }
  
  // Default task notification handling - supports all categories
  const getCategoryInfo = (category: string) => {
    switch (category) {
      case 'overdue':
        return { priority: 'urgent' as const, title: '⚠️ באיחור!', actionRequired: true };
      case 'today':
        return { priority: 'high' as const, title: '📅 מיועד להיום', actionRequired: false };
      case 'soon':
        return { priority: 'high' as const, title: '⏰ בקרוב', actionRequired: false };
      case 'tomorrow':
        return { priority: 'medium' as const, title: '📆 מחר', actionRequired: false };
      case 'system':
        return { priority: 'medium' as const, title: '🔔 התראה', actionRequired: false };
      case 'upcoming':
      default:
        return { priority: 'low' as const, title: '📋 משימה קרובה', actionRequired: false };
    }
  };
  
  const categoryInfo = getCategoryInfo(apiNotif.category);
  
  let message = apiNotif.title;
  if (apiNotif.lead_name) {
    message = `${apiNotif.lead_name}: ${apiNotif.title}`;
  }
  
  return {
    id: apiNotif.id,
    type: 'task',
    title: categoryInfo.title,
    message: message,
    timestamp: new Date(apiNotif.due_date),
    read: false,
    metadata: {
      clientName: apiNotif.lead_name,
      clientPhone: apiNotif.phone,
      priority: categoryInfo.priority,
      actionRequired: categoryInfo.actionRequired,
      relatedId: apiNotif.lead_id?.toString(),
      dueAt: apiNotif.due_date,
      category: apiNotif.category
    }
  };
}

export function NotificationProvider({ children }: { children: React.ReactNode }) {
  const [notifications, setNotifications] = useState<Notification[]>([]);
  const [dismissedUrgent, setDismissedUrgent] = useState<Set<string>>(new Set());
  const [countCallback, setCountCallback] = useState<((count: number) => void) | null>(null);
  const countCallbackRef = useRef<((count: number) => void) | null>(null);
  // FIX: Use ref instead of state to prevent stale closure issues and ensure proper locking
  const isRefreshingRef = useRef<boolean>(false);
  const pollingRef = useRef<NodeJS.Timeout | null>(null);
  const lastCountRef = useRef<number>(0);
  
  // BUILD 144: Get auth state to only fetch when logged in
  const { user, isAuthenticated } = useAuth();
  
  // Keep callback ref in sync
  useEffect(() => {
    countCallbackRef.current = countCallback;
  }, [countCallback]);

  const refreshNotifications = useCallback(async () => {
    // BUILD 144: Don't fetch if not authenticated - prevents 401 spam
    if (!isAuthenticated || !user) {
      setNotifications([]);
      return;
    }
    
    // FIX: Use ref for lock check to prevent stale closure issues
    if (isRefreshingRef.current) {
      console.log('[NotificationContext] Refresh already in progress, skipping');
      return;
    }

    // Set lock immediately using ref
    isRefreshingRef.current = true;
    try {
      // BUILD 143: Use http.get() instead of raw fetch - ensures CSRF and credentials
      const data = await http.get<{ success?: boolean; notifications?: any[] }>('/api/notifications');
      
      if (data.notifications) {
        const converted = data.notifications.map(convertApiNotification);
        setNotifications(converted);
        
        // Update count callback immediately using ref (ensures callback even if not yet registered)
        const unreadCount = converted.filter((n: Notification) => !n.read).length;
        if (countCallbackRef.current) {
          countCallbackRef.current(unreadCount);
        } else if (countCallback) {
          countCallback(unreadCount);
        }
      } else {
        setNotifications([]);
      }
    } catch (error) {
      console.error('[NotificationContext] Error fetching notifications:', error);
      // IMPORTANT: Preserve last good state on error rather than clearing notifications.
      // This prevents the bell from showing 0 during temporary network issues.
      // The next successful refresh will update the state with fresh data.
    } finally {
      // FIX: Always release the lock in finally block to prevent deadlocks
      isRefreshingRef.current = false;
    }
  }, [countCallback, isAuthenticated, user]);

  const setNotificationCountCallback = useCallback((callback: (count: number) => void) => {
    setCountCallback(() => callback);
  }, []);

  // Mark notification as complete (set completed_at on reminder)
  const markAsComplete = useCallback(async (notificationId: string) => {
    try {
      // Notifications are based on reminders - complete the reminder using PATCH with completed: true
      await http.patch(`/api/reminders/${notificationId}`, { completed: true });
      
      // Remove from local state and update count from the new filtered list
      setNotifications(prev => {
        const newList = prev.filter(n => n.id !== notificationId);
        // Update count callback with the new count
        if (countCallback) {
          const newCount = newList.filter(n => !n.read).length;
          countCallback(newCount);
        }
        return newList;
      });
    } catch (error) {
      console.error('Error marking notification as complete:', error);
      throw error;
    }
  }, [countCallback]);

  // Delete notification (delete the reminder)
  const deleteNotification = useCallback(async (notificationId: string) => {
    try {
      await http.delete(`/api/reminders/${notificationId}`);
      
      // Remove from local state and update count from the new filtered list
      setNotifications(prev => {
        const newList = prev.filter(n => n.id !== notificationId);
        // Update count callback with the new count
        if (countCallback) {
          const newCount = newList.filter(n => !n.read).length;
          countCallback(newCount);
        }
        return newList;
      });
    } catch (error) {
      console.error('Error deleting notification:', error);
      throw error;
    }
  }, [countCallback]);

  // BUILD 144: Auto-fetch notifications + POLLING for real-time updates
  useEffect(() => {
    if (isAuthenticated && user) {
      // Initial fetch
      refreshNotifications();
      
      // Start polling for new notifications every 30 seconds
      pollingRef.current = setInterval(() => {
        refreshNotifications();
      }, POLLING_INTERVAL);
      
      console.log('🔔 Notification polling started (every 30s)');
    }
    
    // Cleanup on unmount or when user logs out
    return () => {
      if (pollingRef.current) {
        clearInterval(pollingRef.current);
        pollingRef.current = null;
        console.log('🔔 Notification polling stopped');
      }
    };
  }, [isAuthenticated, user]); // Don't include refreshNotifications to avoid re-creating interval

  const unreadCount = notifications.filter(n => !n.read).length;
  
  // Compute urgent notifications - only show when time has arrived or is imminent (within 30 minutes)
  const urgentNotifications = notifications.filter(n => {
    // Skip if already dismissed
    if (dismissedUrgent.has(n.id)) return false;
    
    // System notifications (like WhatsApp disconnect) - show immediately
    if (n.type === 'system' || n.type === 'urgent') return true;
    
    // For notifications with dueAt, only show popup when time has arrived or is imminent
    if (n.metadata?.dueAt) {
      const dueDate = new Date(n.metadata.dueAt);
      const now = new Date();
      const thirtyMinutesFromNow = new Date(now.getTime() + 30 * 60 * 1000);
      
      // 🔥 FIX: Only show urgent popup if:
      // 1. Overdue (past due date), OR
      // 2. Due within the next 30 minutes (covers 30, 15, and 5 minute warnings)
      if (dueDate <= thirtyMinutesFromNow) {
        // It's time or almost time - show the popup
        return n.metadata?.priority === 'urgent' || n.metadata?.priority === 'high';
      }
      // Not yet time - don't show popup even if high priority
      return false;
    }
    
    // Notifications without dueAt but marked as urgent priority - show immediately
    if (n.metadata?.priority === 'urgent') return true;
    
    return false;
  });
  
  // Dismiss urgent notification (hide from popup but keep in list)
  const dismissUrgent = useCallback((notificationId: string) => {
    setDismissedUrgent(prev => new Set([...prev, notificationId]));
  }, []);
  
  // BUILD 144: Notify when new notifications arrive
  useEffect(() => {
    if (unreadCount > lastCountRef.current && lastCountRef.current > 0) {
      // New notifications arrived - could add browser notification here
      console.log(`🔔 ${unreadCount - lastCountRef.current} new notifications!`);
    }
    lastCountRef.current = unreadCount;
  }, [unreadCount]);

  return (
    <NotificationContext.Provider value={{ 
      notifications, 
      unreadCount, 
      urgentNotifications,
      refreshNotifications, 
      setNotificationCountCallback,
      markAsComplete,
      deleteNotification,
      dismissUrgent
    }}>
      {children}
    </NotificationContext.Provider>
  );
}

export function useNotifications() {
  const context = useContext(NotificationContext);
  if (!context) {
    throw new Error('useNotifications must be used within NotificationProvider');
  }
  return context;
}
