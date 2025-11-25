import React, { createContext, useContext, useState, useCallback, useEffect } from 'react';
import { http } from '../../services/http';

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
  refreshNotifications: () => Promise<void>;
  setNotificationCountCallback: (callback: (count: number) => void) => void;
}

const NotificationContext = createContext<NotificationContextType | null>(null);

// Convert API notification to Notification type
function convertApiNotification(apiNotif: any): Notification {
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
  const [countCallback, setCountCallback] = useState<((count: number) => void) | null>(null);
  const [isRefreshing, setIsRefreshing] = useState(false);

  const refreshNotifications = useCallback(async () => {
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
        
        // Update count callback
        const unreadCount = converted.filter((n: Notification) => !n.read).length;
        if (countCallback) {
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
  }, [countCallback]);

  const setNotificationCountCallback = useCallback((callback: (count: number) => void) => {
    setCountCallback(() => callback);
  }, []);

  // Auto-fetch notifications on mount
  useEffect(() => {
    refreshNotifications();
  }, [refreshNotifications]);

  const unreadCount = notifications.filter(n => !n.read).length;

  return (
    <NotificationContext.Provider value={{ 
      notifications, 
      unreadCount, 
      refreshNotifications, 
      setNotificationCountCallback 
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
