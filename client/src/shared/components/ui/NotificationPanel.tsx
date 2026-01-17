import React, { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import {
  Bell,
  X,
  Check,
  User,
  Phone,
  MessageCircle,
  Calendar,
  DollarSign,
  Clock,
  Info,
  AlertTriangle,
  Building2,
  Wifi,
  WifiOff,
  Settings,
  CheckCircle,
  Trash2
} from 'lucide-react';
import { cn } from '../../utils/cn';
import { useAuth } from '../../../features/auth/hooks';
import { useNotifications, type Notification } from '../../contexts/NotificationContext';

// Re-export for backward compatibility
export type { Notification } from '../../contexts/NotificationContext';

interface NotificationItemProps {
  notification: Notification;
  onClick: () => void;
  onMarkComplete?: (id: string) => Promise<void>;
}

function NotificationItem({ notification, onClick, onMarkComplete }: NotificationItemProps) {
  const [isCompleting, setIsCompleting] = useState(false);
  // BUILD 151: Check if this is a WhatsApp disconnect notification
  const isWhatsAppDisconnect = notification.metadata?.reminderType === 'system_whatsapp_disconnect';
  
  const getIcon = () => {
    // BUILD 151: Special icon for WhatsApp disconnect
    if (isWhatsAppDisconnect) {
      return <WifiOff className="h-4 w-4" />;
    }
    
    switch (notification.type) {
      case 'call': return <Phone className="h-4 w-4" />;
      case 'whatsapp': return <MessageCircle className="h-4 w-4" />;
      case 'lead': return <User className="h-4 w-4" />;
      case 'task': return <Clock className="h-4 w-4" />;
      case 'meeting': return <Calendar className="h-4 w-4" />;
      case 'payment': return <DollarSign className="h-4 w-4" />;
      case 'system': return <Settings className="h-4 w-4" />;
      case 'urgent': return <AlertTriangle className="h-4 w-4" />;
      default: return <Bell className="h-4 w-4" />;
    }
  };

  const getIconColor = () => {
    // BUILD 151: Red icon for WhatsApp disconnect
    if (isWhatsAppDisconnect) {
      return 'text-red-600';
    }
    
    switch (notification.type) {
      case 'call': return 'text-blue-600';
      case 'whatsapp': return 'text-green-600';
      case 'lead': return 'text-purple-600';
      case 'task': return 'text-amber-600';
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

    // 🔥 FIX: Show "in the future" or "in the past" correctly
    if (diffMs < 0) {
      // Future time - show "in X minutes/hours"
      // Calculate absolute values directly from diffMs for efficiency
      const absMins = Math.floor(Math.abs(diffMs) / 60000);
      const absHours = Math.floor(absMins / 60);
      const absDays = Math.floor(absHours / 24);
      
      if (absMins < 60) return `עוד ${absMins} דקות`;
      if (absHours < 24) return `עוד ${absHours} שעות`;
      return `עוד ${absDays} ימים`;
    }
    
    // Past time - show "ago"
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
            <div className="flex items-center gap-2">
              {notification.metadata?.actionRequired && (
                <span className="text-xs bg-red-100 text-red-700 px-2 py-0.5 rounded-full">
                  נדרשת פעולה
                </span>
              )}
              {onMarkComplete && (
                <button
                  onClick={(e) => {
                    e.stopPropagation();
                    setIsCompleting(true);
                    onMarkComplete(notification.id).finally(() => setIsCompleting(false));
                  }}
                  disabled={isCompleting}
                  className="text-xs bg-green-100 text-green-700 px-2 py-0.5 rounded-full hover:bg-green-200 transition-colors flex items-center gap-1"
                  data-testid={`button-quick-complete-${notification.id}`}
                >
                  {isCompleting ? (
                    <div className="animate-spin rounded-full h-3 w-3 border-b border-green-700" />
                  ) : (
                    <CheckCircle className="h-3 w-3" />
                  )}
                  סמן כהושלם
                </button>
              )}
            </div>
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
  onMarkComplete: (id: string) => Promise<void>;
  onDelete: (id: string) => Promise<void>;
}

function NotificationDetailModal({ notification, isOpen, onClose, onMarkComplete, onDelete }: NotificationDetailModalProps) {
  const [isCompleting, setIsCompleting] = useState(false);
  const [isDeleting, setIsDeleting] = useState(false);

  if (!isOpen || !notification) return null;

  const handleMarkComplete = async () => {
    setIsCompleting(true);
    try {
      await onMarkComplete(notification.id);
      onClose();
    } catch (error) {
      console.error('Error marking as complete:', error);
      alert('שגיאה בסימון ההתראה כהושלמה');
    } finally {
      setIsCompleting(false);
    }
  };

  const handleDelete = async () => {
    if (!confirm('האם אתה בטוח שברצונך למחוק את ההתראה?')) return;
    setIsDeleting(true);
    try {
      await onDelete(notification.id);
      onClose();
    } catch (error) {
      console.error('Error deleting notification:', error);
      alert('שגיאה במחיקת ההתראה');
    } finally {
      setIsDeleting(false);
    }
  };

  const formatTime = (date: Date) => {
    // 🔥 FIX: Use timeZone: 'Asia/Jerusalem' directly - it handles the offset automatically
    // No manual +2 hours needed! That causes double offset when combined with timeZone setting
    return date.toLocaleString('he-IL', {
      weekday: 'long',
      year: 'numeric',
      month: 'long',
      day: 'numeric',
      hour: '2-digit',
      minute: '2-digit',
      timeZone: 'Asia/Jerusalem'
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
                     notification.type === 'task' ? 'משימה' :
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
                {notification.metadata?.dueAt && (
                  <div className="flex justify-between">
                    <span className="text-slate-600">תאריך יעד:</span>
                    <span className="font-medium">
                      {(() => {
                        const date = new Date(notification.metadata.dueAt);
                        // 🔥 FIX: No manual +2 hours - timeZone handles it automatically
                        return date.toLocaleString('he-IL', {
                          timeZone: 'Asia/Jerusalem'
                        });
                      })()}
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
          <div className="flex gap-3 justify-between">
            <div className="flex gap-2">
              <button
                onClick={handleMarkComplete}
                disabled={isCompleting || isDeleting}
                className="px-4 py-2 bg-green-600 text-white rounded-lg hover:bg-green-700 transition-colors flex items-center gap-2 disabled:opacity-50"
                data-testid="button-mark-complete"
              >
                {isCompleting ? (
                  <div className="animate-spin rounded-full h-4 w-4 border-b-2 border-white" />
                ) : (
                  <CheckCircle className="h-4 w-4" />
                )}
                סמן כהושלם
              </button>
              <button
                onClick={handleDelete}
                disabled={isCompleting || isDeleting}
                className="px-4 py-2 bg-red-600 text-white rounded-lg hover:bg-red-700 transition-colors flex items-center gap-2 disabled:opacity-50"
                data-testid="button-delete-notification"
              >
                {isDeleting ? (
                  <div className="animate-spin rounded-full h-4 w-4 border-b-2 border-white" />
                ) : (
                  <Trash2 className="h-4 w-4" />
                )}
                מחק
              </button>
            </div>
            <button
              onClick={onClose}
              className="px-4 py-2 bg-slate-600 text-white rounded-lg hover:bg-slate-700 transition-colors"
            >
              סגור
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
  const navigate = useNavigate();
  const { user } = useAuth();
  const { notifications, refreshNotifications, setNotificationCountCallback, markAsComplete, deleteNotification } = useNotifications();
  const [selectedNotification, setSelectedNotification] = useState<Notification | null>(null);
  const [isDetailModalOpen, setIsDetailModalOpen] = useState(false);
  const [loading, setLoading] = useState(false);
  const [filterMode, setFilterMode] = useState<'all' | 'overdue'>('all');  // 🔥 NEW: Filter mode

  // Fetch notifications when panel opens
  useEffect(() => {
    if (isOpen) {
      setLoading(true);
      refreshNotifications().finally(() => setLoading(false));
    }
  }, [isOpen, refreshNotifications]);

  // Register callback to update parent's unread count
  useEffect(() => {
    if (onUnreadCountChange) {
      setNotificationCountCallback(onUnreadCountChange);
    }
  }, [onUnreadCountChange, setNotificationCountCallback]);

  // Calculate unread count from context
  const unreadCount = notifications.filter(n => !n.read).length;

  // 🔥 NEW: Filter notifications based on filter mode
  const filteredNotifications = filterMode === 'overdue' 
    ? notifications.filter(n => {
        // Show only overdue (past due date and not completed)
        if (!n.metadata?.dueAt) return false;
        const dueDate = new Date(n.metadata.dueAt);
        const now = new Date();
        return dueDate < now; // Past due date
      })
    : notifications; // Show all

  const overdueCount = notifications.filter(n => {
    if (!n.metadata?.dueAt) return false;
    const dueDate = new Date(n.metadata.dueAt);
    const now = new Date();
    return dueDate < now;
  }).length;

  if (!isOpen) return null;

  const handleNotificationClick = (notification: Notification) => {
    // BUILD 151: Handle navigation for system notifications
    if (notification.metadata?.navigateTo) {
      onClose(); // Close the panel
      navigate(notification.metadata.navigateTo);
      return;
    }
    
    // Default: show detail modal
    setSelectedNotification(notification);
    setIsDetailModalOpen(true);
  };

  const handleDetailModalClose = () => {
    setIsDetailModalOpen(false);
    setSelectedNotification(null);
  };

  return (
    <>
      <div className="fixed inset-0 bg-black bg-opacity-25 z-40" onClick={onClose} />
      
      <div className="fixed top-16 left-4 right-4 md:left-auto md:right-4 md:w-96 bg-white rounded-xl shadow-xl border border-slate-200 z-50 max-h-[80vh] flex flex-col">
        {/* Header */}
        <div className="flex flex-col p-4 border-b border-slate-200">
          <div className="flex items-center justify-between mb-3">
            <div className="flex items-center gap-2">
              <Bell className="h-5 w-5 text-slate-600" />
              <h2 className="text-lg font-semibold text-slate-900">התראות</h2>
              {unreadCount > 0 && (
                <span className="px-2 py-0.5 bg-red-500 text-white text-xs font-medium rounded-full">
                  {unreadCount}
                </span>
              )}
            </div>
            <button
              onClick={onClose}
              className="p-2 hover:bg-slate-100 rounded-lg transition-colors"
              data-testid="button-close-notifications"
            >
              <X className="h-5 w-5" />
            </button>
          </div>
          
          {/* 🔥 NEW: Filter buttons */}
          <div className="flex gap-2">
            <button
              onClick={() => setFilterMode('all')}
              className={cn(
                "flex-1 px-3 py-2 rounded-lg text-sm font-medium transition-colors",
                filterMode === 'all'
                  ? "bg-blue-100 text-blue-700"
                  : "bg-slate-100 text-slate-600 hover:bg-slate-200"
              )}
            >
              כל ההתראות ({notifications.length})
            </button>
            <button
              onClick={() => setFilterMode('overdue')}
              className={cn(
                "flex-1 px-3 py-2 rounded-lg text-sm font-medium transition-colors",
                filterMode === 'overdue'
                  ? "bg-red-100 text-red-700"
                  : "bg-slate-100 text-slate-600 hover:bg-slate-200"
              )}
            >
              באיחור ({overdueCount})
            </button>
          </div>
        </div>

        {/* Notifications List - ACTUALLY Fixed scrolling */}
        <div className="overflow-y-scroll" style={{ height: '400px' }}>
          {loading ? (
            <div className="flex items-center justify-center h-32">
              <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-blue-600" />
            </div>
          ) : filteredNotifications.length === 0 ? (
            <div className="p-8 text-center text-slate-500">
              {filterMode === 'overdue' ? (
                <>
                  <Clock className="h-12 w-12 mx-auto mb-3 text-slate-300" />
                  <p className="text-sm">אין משימות באיחור</p>
                  <p className="text-xs mt-1">כל המשימות מטופלות בזמן! 🎉</p>
                </>
              ) : (
                <>
                  <Bell className="h-12 w-12 mx-auto mb-3 text-slate-300" />
                  <p className="text-sm">אין התראות חדשות</p>
                  <p className="text-xs mt-1">נעדכן אותך כשיהיו עדכונים</p>
                </>
              )}
            </div>
          ) : (
            <div className="divide-y divide-slate-100">
              {filteredNotifications.map((notification) => (
                <NotificationItem
                  key={notification.id}
                  notification={notification}
                  onClick={() => handleNotificationClick(notification)}
                  onMarkComplete={async (id) => {
                    await markAsComplete(id);
                    await refreshNotifications();
                  }}
                />
              ))}
            </div>
          )}
        </div>

        {/* Footer - Read-only notifications from API */}
        <div className="p-4 border-t border-slate-200 bg-slate-50">
          <p className="text-xs text-slate-500 text-center">
            {unreadCount > 0 ? `${unreadCount} התראות פעילות` : 'אין התראות פעילות'}
          </p>
        </div>
      </div>

      {/* Detail Modal */}
      <NotificationDetailModal
        notification={selectedNotification}
        isOpen={isDetailModalOpen}
        onClose={handleDetailModalClose}
        onMarkComplete={markAsComplete}
        onDelete={deleteNotification}
      />
    </>
  );
}

// Urgent Notification Popup - Shows for important notifications that need immediate attention
interface UrgentNotificationPopupProps {
  notification: Notification | null;
  onDismiss: () => void;
  onCloseAll: () => void;
  onMarkComplete: () => void;
}

export function UrgentNotificationPopup({ notification, onDismiss, onCloseAll, onMarkComplete }: UrgentNotificationPopupProps) {
  const [isCompleting, setIsCompleting] = useState(false);
  
  if (!notification) return null;
  
  const handleComplete = async () => {
    setIsCompleting(true);
    try {
      await onMarkComplete();
    } finally {
      setIsCompleting(false);
    }
  };
  
  const getIcon = () => {
    switch (notification.type) {
      case 'meeting': return <Calendar className="h-8 w-8" />;
      case 'task': return <Clock className="h-8 w-8" />;
      case 'system': return <AlertTriangle className="h-8 w-8" />;
      case 'urgent': return <AlertTriangle className="h-8 w-8" />;
      default: return <Bell className="h-8 w-8" />;
    }
  };
  
  const getBgColor = () => {
    if (notification.metadata?.priority === 'urgent') return 'bg-red-50 border-red-300';
    if (notification.type === 'system') return 'bg-amber-50 border-amber-300';
    return 'bg-blue-50 border-blue-300';
  };
  
  const getIconColor = () => {
    if (notification.metadata?.priority === 'urgent') return 'text-red-600';
    if (notification.type === 'system') return 'text-amber-600';
    return 'text-blue-600';
  };

  return (
    <div className="fixed inset-0 flex items-center justify-center z-[60] p-4" dir="rtl">
      <div className="fixed inset-0 bg-black bg-opacity-40" onClick={onCloseAll} />
      
      <div className={cn(
        "relative bg-white rounded-2xl shadow-2xl border-2 p-6 max-w-md w-full animate-in zoom-in-95 fade-in duration-300",
        getBgColor()
      )}>
        {/* Close button - closes ALL urgent popups */}
        <button
          onClick={onCloseAll}
          className="absolute top-3 left-3 p-2 hover:bg-slate-100 rounded-full transition-colors"
          data-testid="button-close-urgent"
        >
          <X className="h-5 w-5 text-slate-500" />
        </button>
        
        {/* Icon */}
        <div className={cn("flex justify-center mb-4", getIconColor())}>
          {getIcon()}
        </div>
        
        {/* Title */}
        <h2 className="text-xl font-bold text-center text-slate-900 mb-2">
          {notification.title}
        </h2>
        
        {/* Message */}
        <p className="text-center text-slate-700 mb-4">
          {notification.message}
        </p>
        
        {/* Due time if available */}
        {notification.metadata?.dueAt && (
          <div className="text-center mb-4 p-3 bg-white rounded-lg border border-slate-200">
            <p className="text-sm text-slate-600">מיועד ל:</p>
            <p className="text-lg font-semibold text-slate-900">
              {(() => {
                const date = new Date(notification.metadata.dueAt);
                // 🔥 FIX: No manual +2 hours - timeZone handles it automatically
                return date.toLocaleString('he-IL', {
                  dateStyle: 'short',
                  timeStyle: 'short',
                  timeZone: 'Asia/Jerusalem'
                });
              })()}
            </p>
          </div>
        )}
        
        {/* Client info if available */}
        {notification.metadata?.clientName && (
          <div className="text-center mb-4">
            <span className="inline-flex items-center gap-2 px-3 py-1 bg-white rounded-full border border-slate-200">
              <User className="h-4 w-4 text-slate-600" />
              <span className="text-slate-700">{notification.metadata.clientName}</span>
            </span>
          </div>
        )}
        
        {/* Actions */}
        <div className="flex gap-3 justify-center mt-6">
          <button
            onClick={handleComplete}
            disabled={isCompleting}
            className="flex-1 px-4 py-3 bg-green-600 text-white rounded-xl hover:bg-green-700 transition-colors font-medium flex items-center justify-center gap-2 disabled:opacity-50"
            data-testid="button-urgent-complete"
          >
            {isCompleting ? (
              <div className="animate-spin rounded-full h-5 w-5 border-b-2 border-white" />
            ) : (
              <CheckCircle className="h-5 w-5" />
            )}
            סמן כהושלם
          </button>
          <button
            onClick={onDismiss}
            className="px-4 py-3 bg-slate-600 text-white rounded-xl hover:bg-slate-700 transition-colors font-medium"
            data-testid="button-urgent-dismiss"
          >
            אישור
          </button>
        </div>
      </div>
    </div>
  );
}