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
  
  // Default task notification handling
  const priority = apiNotif.category === 'overdue' ? 'urgent' : 
                  apiNotif.category === 'today' ? 'high' : 'medium';
  
  const actionRequired = apiNotif.category === 'overdue';
  
  let message = apiNotif.title;
  if (apiNotif.lead_name) {
    message = `${apiNotif.lead_name}: ${apiNotif.title}`;
  }
  
  return {
    id: apiNotif.id,
    type: 'task',
    title: apiNotif.category === 'overdue' ? '⚠️ באיחור!' : 
           apiNotif.category === 'today' ? '📅 מיועד להיום' : '⏰ בקרוב',
    message: message,
    timestamp: new Date(apiNotif.due_date),
    read: false,
    metadata: {
      clientName: apiNotif.lead_name,
      clientPhone: apiNotif.phone,
      priority: priority,
      actionRequired: actionRequired,
      relatedId: apiNotif.lead_id?.toString(),
      dueAt: apiNotif.due_date
    }
  };
}

export function NotificationProvider({ children }: { children: React.ReactNode }) {
  const [notifications, setNotifications] = useState<Notification[]>([]);
  const [dismissedUrgent, setDismissedUrgent] = useState<Set<string>>(new Set());
  const [countCallback, setCountCallback] = useState<((count: number) => void) | null>(null);
  const countCallbackRef = useRef<((count: number) => void) | null>(null);
  const [isRefreshing, setIsRefreshing] = useState(false);
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
    
    // Prevent concurrent refreshes
    if (isRefreshing) {
      console.log('[NotificationContext] Refresh already in progress, skipping');
      return;
    }

    setIsRefreshing(true);
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
      console.error('Error fetching notifications:', error);
      setNotifications([]);
    } finally {
      setIsRefreshing(false);
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
  
  // Compute urgent notifications (today's meetings, overdue, high priority, system alerts)
  const urgentNotifications = notifications.filter(n => {
    // Skip if already dismissed
    if (dismissedUrgent.has(n.id)) return false;
    
    // System notifications (like WhatsApp disconnect)
    if (n.type === 'system' || n.type === 'urgent') return true;
    
    // Overdue notifications
    if (n.metadata?.priority === 'urgent') return true;
    
    // Today's meetings/tasks with high priority
    if (n.metadata?.priority === 'high' && n.metadata?.dueAt) {
      const dueDate = new Date(n.metadata.dueAt);
      const today = new Date();
      if (dueDate.toDateString() === today.toDateString()) {
        return true;
      }
    }
    
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
