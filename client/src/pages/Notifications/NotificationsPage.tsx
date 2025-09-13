import { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { Bell, Clock, Phone, MessageSquare, CheckCircle2, AlertCircle, User } from 'lucide-react';
import { Button } from '../../shared/components/ui/Button';
import { Card } from '../../shared/components/ui/Card';
import { Badge } from '../../shared/components/Badge';
import { http } from '../../services/http';

interface DueReminder {
  id: number;
  lead_id: number;
  lead_name: string;
  lead_phone?: string;
  due_at: string;
  note?: string;
  channel: 'ui' | 'email' | 'whatsapp';
  overdue_minutes: number;
  created_at: string;
}

interface DueRemindersResponse {
  reminders: DueReminder[];
  total_count: number;
  overdue_count: number;
}

export function NotificationsPage() {
  const navigate = useNavigate();
  const [remindersData, setRemindersData] = useState<DueRemindersResponse | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [completingReminders, setCompletingReminders] = useState<Set<number>>(new Set());

  // Fetch due reminders
  const fetchReminders = async () => {
    try {
      setIsLoading(true);
      setError(null);
      const response = await http.get<DueRemindersResponse>('/api/reminders/due');
      setRemindersData(response);
    } catch (err) {
      console.error('Failed to fetch reminders:', err);
      setError('שגיאה בטעינת התזכורות');
    } finally {
      setIsLoading(false);
    }
  };

  // Load reminders on mount and set up polling
  useEffect(() => {
    fetchReminders();
    const interval = setInterval(fetchReminders, 30000); // Refresh every 30 seconds
    return () => clearInterval(interval);
  }, []);

  // Complete reminder function
  const handleCompleteReminder = async (reminderId: number, leadId: number) => {
    try {
      setCompletingReminders(prev => new Set([...prev, reminderId]));
      await http.patch(`/api/leads/${leadId}/reminders/${reminderId}`, { completed: true });
      // Refresh the reminders list
      await fetchReminders();
    } catch (err) {
      console.error('Failed to complete reminder:', err);
    } finally {
      setCompletingReminders(prev => {
        const newSet = new Set(prev);
        newSet.delete(reminderId);
        return newSet;
      });
    }
  };

  const formatTimeAgo = (dateString: string) => {
    const now = new Date();
    const date = new Date(dateString);
    const diffMs = now.getTime() - date.getTime();
    const diffMinutes = Math.floor(diffMs / (1000 * 60));
    const diffHours = Math.floor(diffMinutes / 60);
    const diffDays = Math.floor(diffHours / 24);

    if (diffMinutes < 60) {
      return `לפני ${diffMinutes} דקות`;
    } else if (diffHours < 24) {
      return `לפני ${diffHours} שעות`;
    } else {
      return `לפני ${diffDays} ימים`;
    }
  };

  const getChannelIcon = (channel: string) => {
    switch (channel) {
      case 'whatsapp':
        return <MessageSquare className="w-4 h-4 text-green-600" />;
      case 'email':
        return <Bell className="w-4 h-4 text-blue-600" />;
      default:
        return <Bell className="w-4 h-4 text-purple-600" />;
    }
  };

  const getChannelLabel = (channel: string) => {
    switch (channel) {
      case 'whatsapp':
        return 'וואטסאפ';
      case 'email':
        return 'אימייל';
      default:
        return 'מערכת';
    }
  };


  const handleGoToLead = (leadId: number) => {
    navigate(`/app/leads/${leadId}`);
  };

  if (isLoading) {
    return (
      <div className="min-h-screen bg-gray-50">
        <div className="max-w-4xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
          <div className="animate-pulse">
            <div className="h-8 bg-gray-200 rounded w-64 mb-6"></div>
            <div className="space-y-4">
              {[1, 2, 3].map((i) => (
                <div key={i} className="h-24 bg-gray-200 rounded"></div>
              ))}
            </div>
          </div>
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="min-h-screen bg-gray-50">
        <div className="max-w-4xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
          <Card className="p-6 text-center">
            <AlertCircle className="w-12 h-12 text-red-500 mx-auto mb-4" />
            <h3 className="text-lg font-medium text-gray-900 mb-2">שגיאה בטעינת התזכורות</h3>
            <p className="text-gray-600">אנא נסה שוב מאוחר יותר</p>
          </Card>
        </div>
      </div>
    );
  }

  const reminders = remindersData?.reminders || [];
  const overdueCount = remindersData?.overdue_count || 0;

  return (
    <div className="min-h-screen bg-gray-50">
      <div className="max-w-4xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
        {/* Header */}
        <div className="mb-8">
          <div className="flex items-center justify-between">
            <div>
              <h1 className="text-2xl font-bold text-gray-900 flex items-center gap-3">
                <Bell className="w-7 h-7 text-blue-600" />
                תזכורות "חזור אליי"
              </h1>
              <p className="text-gray-600 mt-1">
                {reminders.length > 0 
                  ? `יש לך ${reminders.length} תזכורות ממתינות`
                  : 'אין תזכורות ממתינות'
                }
                {overdueCount > 0 && (
                  <span className="text-red-600 font-medium mr-2">
                    ({overdueCount} באיחור)
                  </span>
                )}
              </p>
            </div>
            <Button
              onClick={() => navigate('/app/leads')}
              variant="secondary"
              data-testid="button-back-to-leads"
            >
              חזור ללידים
            </Button>
          </div>
        </div>

        {/* Reminders List */}
        {reminders.length === 0 ? (
          <Card className="p-12 text-center">
            <CheckCircle2 className="w-16 h-16 text-green-500 mx-auto mb-4" />
            <h3 className="text-xl font-medium text-gray-900 mb-2">כל התזכורות טופלו! 🎉</h3>
            <p className="text-gray-600 mb-6">אין תזכורות ממתינות כרגע</p>
            <Button
              onClick={() => navigate('/app/leads')}
              data-testid="button-go-to-leads"
            >
              עבור ללידים
            </Button>
          </Card>
        ) : (
          <div className="space-y-4">
            {reminders.map((reminder) => (
              <Card 
                key={reminder.id} 
                className={`p-6 ${reminder.overdue_minutes > 0 ? 'border-red-200 bg-red-50' : 'border-gray-200'}`}
              >
                <div className="flex items-start justify-between">
                  <div className="flex-1">
                    <div className="flex items-center gap-3 mb-3">
                      <User className="w-5 h-5 text-gray-500" />
                      <h3 className="text-lg font-medium text-gray-900">
                        {reminder.lead_name}
                      </h3>
                      {reminder.lead_phone && (
                        <span className="text-sm text-gray-500">
                          {reminder.lead_phone}
                        </span>
                      )}
                      <Badge 
                        variant={reminder.overdue_minutes > 0 ? 'error' : 'warning'}
                        className="flex items-center gap-1"
                      >
                        <Clock className="w-3 h-3" />
                        {reminder.overdue_minutes > 0 
                          ? `באיחור ${reminder.overdue_minutes} דק'`
                          : 'מתוזמן עכשיו'
                        }
                      </Badge>
                    </div>

                    {reminder.note && (
                      <p className="text-gray-700 mb-3 bg-white p-3 rounded-md">
                        "{reminder.note}"
                      </p>
                    )}

                    <div className="flex items-center gap-4 text-sm text-gray-500">
                      <div className="flex items-center gap-1">
                        {getChannelIcon(reminder.channel)}
                        {getChannelLabel(reminder.channel)}
                      </div>
                      <span>תוזמן ל-{formatTimeAgo(reminder.due_at)}</span>
                    </div>
                  </div>

                  <div className="flex gap-2 ml-4">
                    <Button
                      size="sm"
                      variant="secondary"
                      onClick={() => handleGoToLead(reminder.lead_id)}
                      data-testid={`button-go-to-lead-${reminder.id}`}
                    >
                      <Phone className="w-4 h-4 mr-1" />
                      פתח ליד
                    </Button>
                    <Button
                      size="sm"
                      onClick={() => handleCompleteReminder(reminder.id, reminder.lead_id)}
                      disabled={completingReminders.has(reminder.id)}
                      className="bg-green-600 hover:bg-green-700"
                      data-testid={`button-complete-reminder-${reminder.id}`}
                    >
                      <CheckCircle2 className="w-4 h-4 mr-1" />
                      {completingReminders.has(reminder.id) ? 'מסיים...' : 'סיימתי'}
                    </Button>
                  </div>
                </div>
              </Card>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}