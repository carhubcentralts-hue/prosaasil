import { useState, useEffect, useMemo } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { ArrowLeft, Phone, Mail, MessageSquare, Clock, Activity, CheckCircle2, Circle, User, Tag, Calendar } from 'lucide-react';
import { Button } from '../../shared/components/ui/Button';
import { Card } from '../../shared/components/ui/Card';
import { Badge } from '../../shared/components/Badge';
import { Input } from '../../shared/components/ui/Input';
import { Lead, LeadActivity, LeadReminder, LeadCall, LeadConversation, LeadTask } from './types';
import { http } from '../../services/http';
import { formatDate } from '../../shared/utils/format';

interface LeadDetailPageProps {}

const TABS = [
  { key: 'overview', label: 'סקירה', icon: User },
  { key: 'conversation', label: 'שיחות', icon: MessageSquare },
  { key: 'calls', label: 'שיחות טלפון', icon: Phone },
  { key: 'tasks', label: 'משימות', icon: CheckCircle2 },
  { key: 'activity', label: 'פעילות', icon: Activity },
] as const;

type TabKey = typeof TABS[number]['key'];

export default function LeadDetailPage({}: LeadDetailPageProps) {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  
  const [lead, setLead] = useState<Lead | null>(null);
  const [activeTab, setActiveTab] = useState<TabKey>('overview');
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  
  // Data for each tab
  const [activities, setActivities] = useState<LeadActivity[]>([]);
  const [reminders, setReminders] = useState<LeadReminder[]>([]);

  useEffect(() => {
    if (id) {
      fetchLead();
    }
  }, [id]);

  const fetchLead = async () => {
    try {
      setLoading(true);
      const response = await http.get<Lead & { reminders: LeadReminder[]; activity: LeadActivity[] }>(`/api/leads/${id}`);
      setLead(response);
      setActivities(response.activity || []);
      setReminders(response.reminders || []);
    } catch (err) {
      console.error('Failed to fetch lead:', err);
      setError('שגיאה בטעינת פרטי הליד');
    } finally {
      setLoading(false);
    }
  };

  // Derive data from activities and reminders using useMemo
  const calls = useMemo<LeadCall[]>(() => {
    return activities
      .filter(activity => 
        activity.type === 'call' || activity.type === 'call_incoming'
      )
      .map(activity => ({
        id: activity.id,
        lead_id: activity.lead_id,
        call_type: activity.type === 'call_incoming' ? 'incoming' : 'outgoing',
        duration: 0, // TODO: Add duration to schema
        recording_url: undefined, // TODO: Add recording to schema
        notes: (activity.payload && typeof activity.payload === 'object' && activity.payload.note) ? activity.payload.note : '',
        created_at: activity.at,
        status: 'completed'
      }));
  }, [activities]);

  const conversations = useMemo<LeadConversation[]>(() => {
    return activities
      .filter(activity => 
        activity.type === 'whatsapp_sent' || activity.type === 'whatsapp_received'
      )
      .map(activity => ({
        id: activity.id,
        lead_id: activity.lead_id,
        platform: 'whatsapp' as const,
        direction: activity.type === 'whatsapp_received' ? 'incoming' : 'outgoing',
        message: (activity.payload && typeof activity.payload === 'object' && activity.payload.message) ? activity.payload.message : '',
        created_at: activity.at,
        read: true
      }));
  }, [activities]);

  const tasks = useMemo<LeadTask[]>(() => {
    return reminders.map(reminder => ({
      id: reminder.id,
      lead_id: reminder.lead_id,
      title: reminder.note || 'משימה',
      description: reminder.note,
      due_date: reminder.due_at,
      completed: !!reminder.completed_at,
      created_at: reminder.due_at, // Use due_at as fallback since created_at not in schema
      priority: 'medium' as const
    }));
  }, [reminders]);

  if (loading) {
    return (
      <div className="min-h-screen bg-gray-50 flex items-center justify-center">
        <div className="text-center">
          <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-blue-600 mx-auto mb-4"></div>
          <p className="text-gray-600">טוען פרטי ליד...</p>
        </div>
      </div>
    );
  }

  if (error || !lead) {
    return (
      <div className="min-h-screen bg-gray-50 flex items-center justify-center">
        <div className="text-center">
          <p className="text-red-600 mb-4">{error || 'ליד לא נמצא'}</p>
          <Button onClick={() => navigate('/app/leads')} variant="secondary">
            חזור לרשימת הלידים
          </Button>
        </div>
      </div>
    );
  }

  const StatusBadge = ({ status }: { status: string }) => {
    const statusColors = {
      'New': 'bg-blue-100 text-blue-800',
      'Attempting': 'bg-yellow-100 text-yellow-800',
      'Contacted': 'bg-green-100 text-green-800',
      'Qualified': 'bg-purple-100 text-purple-800',
      'Won': 'bg-emerald-100 text-emerald-800',
      'Lost': 'bg-red-100 text-red-800',
      'Unqualified': 'bg-gray-100 text-gray-800',
    };
    
    return (
      <Badge className={statusColors[status as keyof typeof statusColors] || 'bg-gray-100 text-gray-800'}>
        {status}
      </Badge>
    );
  };

  return (
    <div className="min-h-screen bg-gray-50">
      {/* Header */}
      <div className="bg-white border-b border-gray-200 sticky top-0 z-10">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="flex items-center justify-between h-16">
            <div className="flex items-center">
              <Button
                variant="ghost"
                size="sm"
                onClick={() => navigate('/app/leads')}
                className="mr-4"
                data-testid="button-back"
              >
                <ArrowLeft className="w-4 h-4 mr-2" />
                חזור לרשימת הלידים
              </Button>
              <div>
                <h1 className="text-xl font-semibold text-gray-900" data-testid="text-lead-name">
                  {lead.full_name || `${lead.first_name || ''} ${lead.last_name || ''}`.trim() || 'ללא שם'}
                </h1>
                <p className="text-sm text-gray-500" data-testid="text-lead-phone">
                  {lead.phone_e164}
                </p>
              </div>
            </div>
            <div className="flex items-center space-x-3">
              <StatusBadge status={lead.status} />
              <Button size="sm" data-testid="button-call">
                <Phone className="w-4 h-4 mr-2" />
                התקשר
              </Button>
              <Button size="sm" variant="secondary" data-testid="button-whatsapp">
                <MessageSquare className="w-4 h-4 mr-2" />
                וואטסאפ
              </Button>
            </div>
          </div>
        </div>
      </div>

      {/* Tabs */}
      <div className="bg-white border-b border-gray-200">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <nav className="flex space-x-8" aria-label="Tabs">
            {TABS.map((tab) => {
              const Icon = tab.icon;
              const isActive = activeTab === tab.key;
              return (
                <button
                  key={tab.key}
                  onClick={() => setActiveTab(tab.key)}
                  className={`${
                    isActive
                      ? 'border-blue-500 text-blue-600'
                      : 'border-transparent text-gray-500 hover:text-gray-700 hover:border-gray-300'
                  } whitespace-nowrap py-4 px-1 border-b-2 font-medium text-sm flex items-center`}
                  data-testid={`tab-${tab.key}`}
                >
                  <Icon className="w-4 h-4 mr-2" />
                  {tab.label}
                </button>
              );
            })}
          </nav>
        </div>
      </div>

      {/* Content */}
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
        {activeTab === 'overview' && <OverviewTab lead={lead} reminders={reminders} />}
        {activeTab === 'conversation' && <ConversationTab conversations={conversations} />}
        {activeTab === 'calls' && <CallsTab calls={calls} />}
        {activeTab === 'tasks' && <TasksTab tasks={tasks} />}
        {activeTab === 'activity' && <ActivityTab activities={activities} />}
      </div>
    </div>
  );
}

// Tab Components
function OverviewTab({ lead, reminders }: { lead: Lead; reminders: LeadReminder[] }) {
  return (
    <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
      {/* Lead Info */}
      <div className="lg:col-span-2">
        <Card className="p-6">
          <h3 className="text-lg font-medium text-gray-900 mb-4">פרטי קשר</h3>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">שם פרטי</label>
              <p className="text-sm text-gray-900">{lead.first_name}</p>
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">שם משפחה</label>
              <p className="text-sm text-gray-900">{lead.last_name}</p>
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">טלפון</label>
              <p className="text-sm text-gray-900">{lead.phone_e164}</p>
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">אימייל</label>
              <p className="text-sm text-gray-900">{lead.email || 'לא צוין'}</p>
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">מקור</label>
              <p className="text-sm text-gray-900">{lead.source}</p>
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">תאריך יצירה</label>
              <p className="text-sm text-gray-900">{formatDate(lead.created_at)}</p>
            </div>
          </div>
          
          {lead.tags && lead.tags.length > 0 && (
            <div className="mt-6">
              <label className="block text-sm font-medium text-gray-700 mb-2">תגיות</label>
              <div className="flex flex-wrap gap-2">
                {lead.tags.map((tag, index) => (
              <Badge key={index} variant="info">
                    <Tag className="w-3 h-3 mr-1" />
                    {tag}
                  </Badge>
                ))}
              </div>
            </div>
          )}
          
          {lead.notes && (
            <div className="mt-6">
              <label className="block text-sm font-medium text-gray-700 mb-2">הערות</label>
              <p className="text-sm text-gray-900 bg-gray-50 p-3 rounded-md">{lead.notes}</p>
            </div>
          )}
        </Card>
      </div>

      {/* Reminders */}
      <div>
        <Card className="p-6">
          <h3 className="text-lg font-medium text-gray-900 mb-4">תזכורות קרובות</h3>
          {reminders.length === 0 ? (
            <p className="text-sm text-gray-500">אין תזכורות</p>
          ) : (
            <div className="space-y-3">
              {reminders.slice(0, 5).map((reminder) => (
                <div key={reminder.id} className="flex items-start space-x-3">
                  <Clock className="w-4 h-4 text-gray-400 mt-0.5" />
                  <div className="flex-1 min-w-0">
                    <p className="text-sm text-gray-900">{reminder.note}</p>
                    <p className="text-xs text-gray-500">{formatDate(reminder.due_at)}</p>
                  </div>
                </div>
              ))}
            </div>
          )}
        </Card>
      </div>
    </div>
  );
}

function ConversationTab({ conversations }: { conversations: LeadConversation[] }) {
  return (
    <Card className="p-6">
      <h3 className="text-lg font-medium text-gray-900 mb-4">היסטוריית שיחות</h3>
      {conversations.length === 0 ? (
        <p className="text-sm text-gray-500">אין שיחות</p>
      ) : (
        <div className="space-y-4">
          {conversations.map((conversation) => (
            <div key={conversation.id} className={`flex ${conversation.direction === 'outgoing' ? 'justify-end' : 'justify-start'}`}>
              <div className={`max-w-xs lg:max-w-md px-4 py-2 rounded-lg ${
                conversation.direction === 'outgoing' 
                  ? 'bg-blue-500 text-white' 
                  : 'bg-gray-100 text-gray-900'
              }`}>
                <p className="text-sm">{conversation.message}</p>
                <p className={`text-xs mt-1 ${
                  conversation.direction === 'outgoing' ? 'text-blue-100' : 'text-gray-500'
                }`}>
                  {formatDate(conversation.created_at)}
                </p>
              </div>
            </div>
          ))}
        </div>
      )}
    </Card>
  );
}

function CallsTab({ calls }: { calls: LeadCall[] }) {
  return (
    <Card className="p-6">
      <h3 className="text-lg font-medium text-gray-900 mb-4">היסטוריית שיחות טלפון</h3>
      {calls.length === 0 ? (
        <p className="text-sm text-gray-500">אין שיחות טלפון</p>
      ) : (
        <div className="space-y-4">
          {calls.map((call) => (
            <div key={call.id} className="flex items-center justify-between p-4 bg-gray-50 rounded-lg">
              <div className="flex items-center space-x-3">
                <Phone className={`w-5 h-5 ${call.call_type === 'incoming' ? 'text-green-500' : 'text-blue-500'}`} />
                <div>
                  <p className="text-sm font-medium text-gray-900">
                    {call.call_type === 'incoming' ? 'שיחה נכנסת' : 'שיחה יוצאת'}
                  </p>
                  <p className="text-xs text-gray-500">{formatDate(call.created_at)}</p>
                </div>
              </div>
              <div className="text-right">
                <p className="text-sm text-gray-900">{call.duration}s</p>
                {call.notes && <p className="text-xs text-gray-500">{call.notes}</p>}
              </div>
            </div>
          ))}
        </div>
      )}
    </Card>
  );
}

function TasksTab({ tasks }: { tasks: LeadTask[] }) {
  return (
    <Card className="p-6">
      <h3 className="text-lg font-medium text-gray-900 mb-4">משימות</h3>
      {tasks.length === 0 ? (
        <p className="text-sm text-gray-500">אין משימות</p>
      ) : (
        <div className="space-y-3">
          {tasks.map((task) => (
            <div key={task.id} className="flex items-center space-x-3 p-3 bg-gray-50 rounded-lg">
              {task.completed ? (
                <CheckCircle2 className="w-5 h-5 text-green-500" />
              ) : (
                <Circle className="w-5 h-5 text-gray-400" />
              )}
              <div className="flex-1 min-w-0">
                <p className={`text-sm ${task.completed ? 'line-through text-gray-500' : 'text-gray-900'}`}>
                  {task.title}
                </p>
                {task.due_date && (
                  <p className="text-xs text-gray-500">
                    <Calendar className="w-3 h-3 inline mr-1" />
                    {formatDate(task.due_date)}
                  </p>
                )}
              </div>
              <Badge variant={task.priority === 'high' ? 'error' : task.priority === 'medium' ? 'warning' : 'info'}>
                {task.priority}
              </Badge>
            </div>
          ))}
        </div>
      )}
    </Card>
  );
}

function ActivityTab({ activities }: { activities: LeadActivity[] }) {
  return (
    <Card className="p-6">
      <h3 className="text-lg font-medium text-gray-900 mb-4">פעילות אחרונה</h3>
      {activities.length === 0 ? (
        <p className="text-sm text-gray-500">אין פעילות</p>
      ) : (
        <div className="flow-root">
          <ul className="-mb-8">
            {activities.map((activity, activityIdx) => (
              <li key={activity.id}>
                <div className="relative pb-8">
                  {activityIdx !== activities.length - 1 ? (
                    <span className="absolute top-4 left-4 -ml-px h-full w-0.5 bg-gray-200" aria-hidden="true" />
                  ) : null}
                  <div className="relative flex space-x-3">
                    <div>
                      <span className="h-8 w-8 rounded-full bg-blue-500 flex items-center justify-center ring-8 ring-white">
                        <Activity className="w-4 h-4 text-white" />
                      </span>
                    </div>
                    <div className="min-w-0 flex-1 pt-1.5 flex justify-between space-x-4">
                      <div>
                        <p className="text-sm text-gray-500">
                          {activity.type} - {activity.payload?.message || activity.payload?.note || 'פעילות'}
                        </p>
                      </div>
                      <div className="text-right text-sm whitespace-nowrap text-gray-500">
                        {formatDate(activity.at)}
                      </div>
                    </div>
                  </div>
                </div>
              </li>
            ))}
          </ul>
        </div>
      )}
    </Card>
  );
}