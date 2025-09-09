import React, { useState, useCallback, useMemo } from 'react';
import { 
  Bell, 
  X, 
  Clock, 
  User, 
  Phone, 
  MessageCircle, 
  Calendar, 
  AlertTriangle,
  CheckCircle,
  Info,
  DollarSign,
  Building2
} from 'lucide-react';
import { cn } from '../../utils/cn';
import { useAuth } from '../../../features/auth/hooks';

export interface Notification {
  id: string;
  type: 'call' | 'whatsapp' | 'lead' | 'meeting' | 'payment' | 'system' | 'urgent';
  title: string;
  message: string;
  timestamp: Date;
  read: boolean;
  businessId?: number;
  userId?: number;
  metadata?: {
    clientName?: string;
    clientPhone?: string;
    amount?: number;
    leadType?: string;
    callDuration?: string;
    priority?: 'low' | 'medium' | 'high' | 'urgent';
    actionRequired?: boolean;
    relatedId?: string;
  };
}

// Mock notification data - In real app, this would come from API
function generateNotifications(userRole: string, businessId?: number): Notification[] {
  const baseNotifications: Notification[] = [
    {
      id: '1',
      type: 'call',
      title: 'שיחה חדשה',
      message: 'שיחה נכנסת מ-054-123-4567',
      timestamp: new Date(Date.now() - 2 * 60 * 1000), // 2 minutes ago
      read: false,
      businessId: 1,
      metadata: {
        clientPhone: '054-123-4567',
        callDuration: '3:45',
        priority: 'high',
        actionRequired: true
      }
    },
    {
      id: '2',
      type: 'whatsapp',
      title: 'הודעת WhatsApp',
      message: 'הודעה חדשה מלאה בן דוד - מעוניין בדירה',
      timestamp: new Date(Date.now() - 5 * 60 * 1000), // 5 minutes ago
      read: false,
      businessId: 1,
      metadata: {
        clientName: 'לאה בן דוד',
        clientPhone: '052-999-8888',
        priority: 'medium',
        leadType: 'דירה'
      }
    },
    {
      id: '3',
      type: 'lead',
      title: 'ליד חדש',
      message: 'ליד חדש נוסף למערכת - משה כהן',
      timestamp: new Date(Date.now() - 15 * 60 * 1000), // 15 minutes ago
      read: true,
      businessId: 1,
      metadata: {
        clientName: 'משה כהן',
        clientPhone: '053-777-6666',
        leadType: 'משרד',
        priority: 'medium'
      }
    },
    {
      id: '4',
      type: 'meeting',
      title: 'פגישה נקבעה',
      message: 'פגישה נקבעה עם שרה לוי ליום ראשון 16:00',
      timestamp: new Date(Date.now() - 25 * 60 * 1000), // 25 minutes ago
      read: true,
      businessId: 1,
      metadata: {
        clientName: 'שרה לוי',
        priority: 'high',
        actionRequired: true
      }
    },
    {
      id: '5',
      type: 'payment',
      title: 'תשלום חדש',
      message: 'תשלום בסך 15,000 ₪ התקבל מדוד גרין',
      timestamp: new Date(Date.now() - 45 * 60 * 1000), // 45 minutes ago
      read: true,
      businessId: 1,
      metadata: {
        clientName: 'דוד גרין',
        amount: 15000,
        priority: 'low'
      }
    }
  ];

  // Add admin notifications
  if (userRole === 'admin' || userRole === 'manager') {
    baseNotifications.push(
      {
        id: '6',
        type: 'system',
        title: 'עדכון מערכת',
        message: 'שדרוג מערכת הושלם בהצלחה',
        timestamp: new Date(Date.now() - 60 * 60 * 1000), // 1 hour ago
        read: false,
        metadata: {
          priority: 'low',
          actionRequired: false
        }
      },
      {
        id: '7',
        type: 'urgent',
        title: 'בעיה טכנית',
        message: 'שגיאה בחיבור ל-Twilio - נדרשת פעולה',
        timestamp: new Date(Date.now() - 90 * 60 * 1000), // 1.5 hours ago
        read: false,
        metadata: {
          priority: 'urgent',
          actionRequired: true
        }
      }
    );
  }

  // Filter by business if user is business role
  if (userRole === 'business' && businessId) {
    return baseNotifications.filter(n => n.businessId === businessId);
  }

  return baseNotifications;
}

interface NotificationItemProps {
  notification: Notification;
  onClick: () => void;
}

function NotificationItem({ notification, onClick }: NotificationItemProps) {
  const getIcon = () => {
    switch (notification.type) {
      case 'call': return <Phone className="h-4 w-4" />;
      case 'whatsapp': return <MessageCircle className="h-4 w-4" />;
      case 'lead': return <User className="h-4 w-4" />;
      case 'meeting': return <Calendar className="h-4 w-4" />;
      case 'payment': return <DollarSign className="h-4 w-4" />;
      case 'system': return <Info className="h-4 w-4" />;
      case 'urgent': return <AlertTriangle className="h-4 w-4" />;
      default: return <Bell className="h-4 w-4" />;
    }
  };

  const getIconColor = () => {
    switch (notification.type) {
      case 'call': return 'text-blue-600';
      case 'whatsapp': return 'text-green-600';
      case 'lead': return 'text-purple-600';
      case 'meeting': return 'text-orange-600';
      case 'payment': return 'text-emerald-600';
      case 'system': return 'text-gray-600';
      case 'urgent': return 'text-red-600';
      default: return 'text-gray-600';
    }
  };

  const getBadgeColor = () => {
    switch (notification.metadata?.priority) {
      case 'urgent': return 'bg-red-100 text-red-800';
      case 'high': return 'bg-orange-100 text-orange-800';
      case 'medium': return 'bg-yellow-100 text-yellow-800';
      case 'low': return 'bg-green-100 text-green-800';
      default: return 'bg-gray-100 text-gray-800';
    }
  };

  const timeAgo = (date: Date) => {
    const now = new Date();
    const diffMs = now.getTime() - date.getTime();
    const diffMins = Math.floor(diffMs / 60000);
    const diffHours = Math.floor(diffMins / 60);
    const diffDays = Math.floor(diffHours / 24);

    if (diffMins < 1) return 'עכשיו';
    if (diffMins < 60) return `לפני ${diffMins} דקות`;
    if (diffHours < 24) return `לפני ${diffHours} שעות`;
    return `לפני ${diffDays} ימים`;
  };

  return (
    <div 
      className={cn(
        'p-4 hover:bg-slate-50 transition-colors cursor-pointer border-r-4',
        !notification.read ? 'bg-blue-50 border-r-blue-500' : 'border-r-transparent'
      )}
      onClick={onClick}
    >
      <div className="flex items-start gap-3">
        <div className={cn('mt-1', getIconColor())}>
          {getIcon()}
        </div>
        <div className="flex-1 min-w-0">
          <div className="flex items-center justify-between mb-1">
            <h4 className={cn(
              'text-sm font-medium truncate',
              !notification.read ? 'text-slate-900' : 'text-slate-700'
            )}>
              {notification.title}
            </h4>
            {notification.metadata?.priority && (
              <span className={cn(
                'text-xs px-2 py-0.5 rounded-full font-medium',
                getBadgeColor()
              )}>
                {notification.metadata.priority === 'urgent' ? 'דחוף' :
                 notification.metadata.priority === 'high' ? 'גבוה' :
                 notification.metadata.priority === 'medium' ? 'בינוני' : 'נמוך'}
              </span>
            )}
          </div>
          <p className="text-sm text-slate-600 mb-2 line-clamp-2">
            {notification.message}
          </p>
          <div className="flex items-center justify-between">
            <span className="text-xs text-slate-500 flex items-center gap-1">
              <Clock className="h-3 w-3" />
              {timeAgo(notification.timestamp)}
            </span>
            {notification.metadata?.actionRequired && (
              <span className="text-xs bg-red-100 text-red-700 px-2 py-0.5 rounded-full">
                נדרשת פעולה
              </span>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}

interface NotificationDetailModalProps {
  notification: Notification | null;
  isOpen: boolean;
  onClose: () => void;
  onMarkAsRead?: (id: string) => void;
}

function NotificationDetailModal({ notification, isOpen, onClose, onMarkAsRead }: NotificationDetailModalProps) {
  if (!isOpen || !notification) return null;

  const formatTime = (date: Date) => {
    return date.toLocaleString('he-IL', {
      weekday: 'long',
      year: 'numeric',
      month: 'long',
      day: 'numeric',
      hour: '2-digit',
      minute: '2-digit'
    });
  };

  return (
    <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50 p-4">
      <div className="bg-white rounded-xl max-w-lg w-full max-h-[80vh] shadow-xl flex flex-col">
        {/* Header */}
        <div className="flex items-center justify-between p-6 border-b border-slate-200 flex-shrink-0">
          <h2 className="text-lg font-semibold text-slate-900">פרטי התראה</h2>
          <button
            onClick={onClose}
            className="p-2 hover:bg-slate-100 rounded-lg transition-colors"
          >
            <X className="h-5 w-5" />
          </button>
        </div>

        {/* Content - NOW with proper scrolling */}
        <div className="p-6 overflow-y-scroll flex-1" style={{ maxHeight: 'calc(80vh - 100px)' }}>
          <div className="space-y-4">
            <div>
              <h3 className="font-medium text-slate-900 mb-1">{notification.title}</h3>
              <p className="text-slate-600">{notification.message}</p>
            </div>

            <div className="bg-slate-50 rounded-lg p-4">
              <h4 className="font-medium text-slate-900 mb-3">פרטים נוספים</h4>
              <div className="space-y-2 text-sm">
                <div className="flex justify-between">
                  <span className="text-slate-600">זמן:</span>
                  <span className="font-medium">{formatTime(notification.timestamp)}</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-slate-600">סוג:</span>
                  <span className="font-medium">
                    {notification.type === 'call' ? 'שיחה' :
                     notification.type === 'whatsapp' ? 'WhatsApp' :
                     notification.type === 'lead' ? 'ליד' :
                     notification.type === 'meeting' ? 'פגישה' :
                     notification.type === 'payment' ? 'תשלום' :
                     notification.type === 'system' ? 'מערכת' : 'דחוף'}
                  </span>
                </div>
                {notification.metadata?.clientName && (
                  <div className="flex justify-between">
                    <span className="text-slate-600">שם לקוח:</span>
                    <span className="font-medium">{notification.metadata.clientName}</span>
                  </div>
                )}
                {notification.metadata?.clientPhone && (
                  <div className="flex justify-between">
                    <span className="text-slate-600">טלפון:</span>
                    <span className="font-medium direction-ltr">{notification.metadata.clientPhone}</span>
                  </div>
                )}
                {notification.metadata?.amount && (
                  <div className="flex justify-between">
                    <span className="text-slate-600">סכום:</span>
                    <span className="font-medium">{notification.metadata.amount.toLocaleString()} ₪</span>
                  </div>
                )}
                {notification.metadata?.callDuration && (
                  <div className="flex justify-between">
                    <span className="text-slate-600">משך שיחה:</span>
                    <span className="font-medium">{notification.metadata.callDuration}</span>
                  </div>
                )}
                {notification.metadata?.leadType && (
                  <div className="flex justify-between">
                    <span className="text-slate-600">סוג נכס:</span>
                    <span className="font-medium">{notification.metadata.leadType}</span>
                  </div>
                )}
                {notification.metadata?.priority && (
                  <div className="flex justify-between">
                    <span className="text-slate-600">עדיפות:</span>
                    <span className={cn(
                      'font-medium',
                      notification.metadata.priority === 'urgent' ? 'text-red-600' :
                      notification.metadata.priority === 'high' ? 'text-orange-600' :
                      notification.metadata.priority === 'medium' ? 'text-yellow-600' : 'text-green-600'
                    )}>
                      {notification.metadata.priority === 'urgent' ? 'דחוף' :
                       notification.metadata.priority === 'high' ? 'גבוה' :
                       notification.metadata.priority === 'medium' ? 'בינוני' : 'נמוך'}
                    </span>
                  </div>
                )}
              </div>
            </div>

            {notification.metadata?.actionRequired && (
              <div className="bg-red-50 border border-red-200 rounded-lg p-4">
                <div className="flex items-center gap-2 text-red-800">
                  <AlertTriangle className="h-4 w-4" />
                  <span className="font-medium">נדרשת פעולה</span>
                </div>
                <p className="text-red-700 text-sm mt-1">
                  התראה זו דורשת טיפול או מעקב נוסף.
                </p>
              </div>
            )}
          </div>
        </div>

        {/* Actions */}
        <div className="p-6 border-t border-slate-200 bg-slate-50">
          <div className="flex gap-3 justify-end">
            <button
              onClick={onClose}
              className="px-4 py-2 text-slate-600 hover:text-slate-800 transition-colors"
            >
              סגור
            </button>
            <button
              onClick={() => {
                if (notification && !notification.read && onMarkAsRead) {
                  onMarkAsRead(notification.id);
                }
                onClose();
              }}
              className="px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 transition-colors"
            >
              {notification?.read ? 'סגור' : 'סמן כנקרא'}
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}

interface NotificationPanelProps {
  isOpen: boolean;
  onClose: () => void;
  onUnreadCountChange?: (count: number) => void;
}

export function NotificationPanel({ isOpen, onClose, onUnreadCountChange }: NotificationPanelProps) {
  const { user } = useAuth();
  const [selectedNotification, setSelectedNotification] = useState<Notification | null>(null);
  const [isDetailModalOpen, setIsDetailModalOpen] = useState(false);
  const [notifications, setNotifications] = useState<Notification[]>([]);

  // Memoized callback to prevent unnecessary rerenders - FIXED: Handle undefined case
  const memoizedOnUnreadCountChange = useCallback(
    onUnreadCountChange || (() => {}), 
    [onUnreadCountChange]
  );

  // Initialize notifications when component mounts or user changes - optimized
  React.useEffect(() => {
    const newNotifications = generateNotifications(user?.role || 'business', user?.business_id);
    setNotifications(newNotifications);
    const initialUnreadCount = newNotifications.filter(n => !n.read).length;
    console.log('🔔 NotificationPanel מאתחל עם', initialUnreadCount, 'התראות לא נקראות');
    memoizedOnUnreadCountChange?.(initialUnreadCount);
  }, [user?.role, user?.business_id, memoizedOnUnreadCountChange]);

  // Memoized unread count to prevent recalculation on every render
  const unreadCount = useMemo(() => notifications.filter(n => !n.read).length, [notifications]);

  // Update parent count whenever unread count changes - debounced
  React.useEffect(() => {
    const timeoutId = setTimeout(() => {
      console.log('🔄 NotificationPanel שולח עדכון:', unreadCount);
      memoizedOnUnreadCountChange?.(unreadCount);
    }, 50); // 50ms debounce to prevent rapid fire updates

    return () => clearTimeout(timeoutId);
  }, [unreadCount, memoizedOnUnreadCountChange]);

  if (!isOpen) return null;

  // Remove duplicate calculation - we already have memoized unread count above

  // Memoized handlers to prevent unnecessary rerenders of child components
  const handleNotificationClick = useCallback((notification: Notification) => {
    setSelectedNotification(notification);
    setIsDetailModalOpen(true);
    // Auto mark as read when opening detail
    markAsRead(notification.id);
  }, []);

  const markAsRead = useCallback((notificationId: string) => {
    setNotifications(prev => {
      const updated = prev.map(n => 
        n.id === notificationId ? { ...n, read: true } : n
      );
      return updated;
    });
  }, []);

  const markAllAsRead = useCallback(() => {
    setNotifications(prev => {
      const updated = prev.map(n => ({ ...n, read: true }));
      return updated;
    });
  }, []);

  const handleDetailModalClose = useCallback(() => {
    setIsDetailModalOpen(false);
    setSelectedNotification(null);
  }, []);

  return (
    <>
      <div className="fixed inset-0 bg-black bg-opacity-25 z-40" onClick={onClose} />
      
      <div className="fixed top-16 left-4 right-4 md:left-auto md:right-4 md:w-96 bg-white rounded-xl shadow-xl border border-slate-200 z-50 max-h-[80vh] flex flex-col">
        {/* Header */}
        <div className="flex items-center justify-between p-4 border-b border-slate-200">
          <div className="flex items-center gap-2">
            <Bell className="h-5 w-5 text-slate-600" />
            <h2 className="text-lg font-semibold text-slate-900">התראות</h2>
            {unreadCount > 0 && (
              <span 
                className="bg-red-500 text-white text-xs rounded-full px-2 py-0.5 font-medium"
                data-testid="unread-count-panel"
              >
                {unreadCount}
              </span>
            )}
          </div>
          <button
            onClick={onClose}
            className="p-2 hover:bg-slate-100 rounded-lg transition-colors"
          >
            <X className="h-4 w-4" />
          </button>
        </div>

        {/* Notifications List - ACTUALLY Fixed scrolling */}
        <div className="overflow-y-scroll" style={{ height: '400px' }}>
          {notifications.length === 0 ? (
            <div className="p-8 text-center text-slate-500">
              <Bell className="h-12 w-12 mx-auto mb-3 text-slate-300" />
              <p>אין התראות חדשות</p>
            </div>
          ) : (
            <div className="divide-y divide-slate-100">
              {notifications.map((notification) => (
                <NotificationItem
                  key={notification.id}
                  notification={notification}
                  onClick={() => handleNotificationClick(notification)}
                />
              ))}
            </div>
          )}
        </div>

        {/* Footer */}
        <div className="p-4 border-t border-slate-200 bg-slate-50">
          <div className="flex justify-between items-center">
            <button 
              onClick={markAllAsRead}
              className="text-sm text-blue-600 hover:text-blue-800 transition-colors"
              disabled={unreadCount === 0}
              data-testid="button-mark-all-read"
            >
              סמן הכל כנקרא ({unreadCount})
            </button>
            <button 
              onClick={() => {
                // Mark first unread notification as read for testing
                const firstUnread = notifications.find(n => !n.read);
                if (firstUnread) {
                  markAsRead(firstUnread.id);
                }
              }}
              className="text-sm text-slate-600 hover:text-slate-800 transition-colors"
              disabled={unreadCount === 0}
              data-testid="button-mark-one-read"
            >
              סמן אחד כנקרא
            </button>
          </div>
        </div>
      </div>

      {/* Detail Modal */}
      <NotificationDetailModal
        notification={selectedNotification}
        isOpen={isDetailModalOpen}
        onClose={handleDetailModalClose}
        onMarkAsRead={markAsRead}
      />
    </>
  );
}