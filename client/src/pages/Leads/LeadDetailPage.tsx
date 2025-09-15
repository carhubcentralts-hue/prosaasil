import { useState, useEffect, useMemo } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { ArrowLeft, Phone, Mail, MessageSquare, Clock, Activity, CheckCircle2, Circle, User, Tag, Calendar, Plus } from 'lucide-react';
import WhatsAppChat from './components/WhatsAppChat';
import { ReminderModal } from './components/ReminderModal';
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
  { key: 'invoices', label: 'חשבוניות', icon: Calendar },
  { key: 'contracts', label: 'חוזים', icon: Tag },
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
  const [whatsappChatOpen, setWhatsappChatOpen] = useState(false);
  const [reminderModalOpen, setReminderModalOpen] = useState(false);
  
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
      <div className="bg-white border-b border-gray-200 sticky top-[env(safe-area-inset-top)] z-10">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          {/* Desktop Header */}
          <div className="hidden sm:flex items-center justify-between h-16">
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
              <Button 
                size="sm" 
                onClick={() => window.location.href = `tel:${lead.phone_e164 || lead.phone || ''}`}
                data-testid="button-call"
              >
                <Phone className="w-4 h-4 mr-2" />
                התקשר
              </Button>
              <Button 
                size="sm" 
                variant="secondary" 
                onClick={() => {
                  if (lead.phone_e164 || lead.phone) {
                    const cleanPhone = (lead.phone_e164 || lead.phone || '').replace(/[^0-9]/g, '');
                    window.open(`https://wa.me/${cleanPhone}`, '_blank');
                  } else {
                    setWhatsappChatOpen(true);
                  }
                }}
                data-testid="button-whatsapp"
              >
                <MessageSquare className="w-4 h-4 mr-2" />
                וואטסאפ
              </Button>
            </div>
          </div>
          
          {/* Mobile Header */}
          <div className="sm:hidden py-4">
            <div className="flex items-center justify-between mb-3">
              <Button
                variant="ghost"
                size="sm"
                onClick={() => navigate('/app/leads')}
                data-testid="button-back-mobile"
              >
                <ArrowLeft className="w-4 h-4 mr-2" />
                חזור
              </Button>
              <StatusBadge status={lead.status} />
            </div>
            <div className="text-center mb-4">
              <h1 className="text-lg font-semibold text-gray-900" data-testid="text-lead-name-mobile">
                {lead.full_name || `${lead.first_name || ''} ${lead.last_name || ''}`.trim() || 'ללא שם'}
              </h1>
              <p className="text-sm text-gray-500" data-testid="text-lead-phone-mobile">
                {lead.phone_e164}
              </p>
            </div>
            <div className="flex gap-2">
              <Button 
                size="sm" 
                className="flex-1" 
                onClick={() => window.location.href = `tel:${lead.phone_e164 || lead.phone || ''}`}
                data-testid="button-call-mobile"
              >
                <Phone className="w-4 h-4 mr-2" />
                התקשר
              </Button>
              <Button 
                size="sm" 
                variant="secondary" 
                className="flex-1"
                onClick={() => {
                  if (lead.phone_e164 || lead.phone) {
                    const cleanPhone = (lead.phone_e164 || lead.phone || '').replace(/[^0-9]/g, '');
                    window.open(`https://wa.me/${cleanPhone}`, '_blank');
                  } else {
                    setWhatsappChatOpen(true);
                  }
                }}
                data-testid="button-whatsapp-mobile"
              >
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
          {/* Desktop Tabs */}
          <nav className="hidden sm:flex space-x-8" aria-label="Tabs">
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
          
          {/* Mobile Tabs - Scrollable */}
          <div className="sm:hidden overflow-x-auto">
            <nav className="flex space-x-6 py-3" aria-label="Mobile Tabs">
              {TABS.map((tab) => {
                const Icon = tab.icon;
                const isActive = activeTab === tab.key;
                return (
                  <button
                    key={tab.key}
                    onClick={() => setActiveTab(tab.key)}
                    className={`${
                      isActive
                        ? 'bg-blue-100 text-blue-600'
                        : 'text-gray-500 hover:text-gray-700'
                    } whitespace-nowrap px-3 py-2 rounded-lg font-medium text-sm flex items-center flex-shrink-0`}
                    data-testid={`tab-mobile-${tab.key}`}
                  >
                    <Icon className="w-4 h-4 mr-2" />
                    {tab.label}
                  </button>
                );
              })}
            </nav>
          </div>
        </div>
      </div>

      {/* Content */}
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-4 sm:py-8">
        {activeTab === 'overview' && <OverviewTab lead={lead} reminders={reminders} onOpenReminder={() => setReminderModalOpen(true)} />}
        {activeTab === 'conversation' && <ConversationTab conversations={conversations} onOpenWhatsApp={() => setWhatsappChatOpen(true)} />}
        {activeTab === 'calls' && <CallsTab calls={calls} />}
        {activeTab === 'tasks' && <TasksTab tasks={tasks} />}
        {activeTab === 'invoices' && <InvoicesTab leadId={lead.id} />}
        {activeTab === 'contracts' && <ContractsTab leadId={lead.id} />}
        {activeTab === 'activity' && <ActivityTab activities={activities} />}
      </div>

      {/* WhatsApp Chat Modal */}
      {lead && (
        <WhatsAppChat 
          lead={lead} 
          isOpen={whatsappChatOpen} 
          onClose={() => setWhatsappChatOpen(false)} 
        />
      )}

      {/* Reminder Modal */}
      {lead && (
        <ReminderModal
          lead={lead}
          isOpen={reminderModalOpen}
          onClose={() => setReminderModalOpen(false)}
          onSuccess={fetchLead}
        />
      )}
    </div>
  );
}

// Tab Components
function OverviewTab({ lead, reminders, onOpenReminder }: { lead: Lead; reminders: LeadReminder[]; onOpenReminder: () => void }) {
  return (
    <div className="flex flex-col lg:grid lg:grid-cols-3 gap-6">
      {/* Lead Info */}
      <div className="lg:col-span-2">
        <Card className="p-4 sm:p-6">
          <h3 className="text-lg font-medium text-gray-900 mb-4">פרטי קשר</h3>
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4 sm:gap-6">
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
      <div className="order-first lg:order-last">
        <Card className="p-4 sm:p-6">
          <div className="flex items-center justify-between mb-4">
            <h3 className="text-lg font-medium text-gray-900">תזכורות קרובות</h3>
            <Button
              onClick={onOpenReminder}
              size="sm"
              className="bg-blue-600 hover:bg-blue-700 text-white"
              data-testid="button-create-reminder"
            >
              <Clock className="w-4 h-4 mr-2" />
              צור תזכורת
            </Button>
          </div>
          {reminders.length === 0 ? (
            <div className="text-center py-8">
              <Clock className="w-12 h-12 text-gray-300 mx-auto mb-4" />
              <p className="text-sm text-gray-500 mb-4">אין תזכורות</p>
              <Button
                onClick={onOpenReminder}
                size="sm"
                className="bg-blue-600 hover:bg-blue-700 text-white"
              >
                <Clock className="w-4 h-4 mr-2" />
                צור תזכורת ראשונה
              </Button>
            </div>
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

function ConversationTab({ conversations, onOpenWhatsApp }: { conversations: LeadConversation[]; onOpenWhatsApp: () => void }) {
  return (
    <Card className="p-4 sm:p-6">
      <div className="flex items-center justify-between mb-4">
        <h3 className="text-lg font-medium text-gray-900">היסטוריית שיחות</h3>
        <Button 
          onClick={onOpenWhatsApp} 
          size="sm"
          className="bg-green-500 hover:bg-green-600 text-white"
          data-testid="button-open-whatsapp-chat"
        >
          <MessageSquare className="w-4 h-4 mr-2" />
          פתח וואטסאפ
        </Button>
      </div>
      {conversations.length === 0 ? (
        <div className="text-center py-8">
          <MessageSquare className="w-12 h-12 text-gray-300 mx-auto mb-4" />
          <p className="text-sm text-gray-500 mb-4">אין שיחות</p>
          <Button 
            onClick={onOpenWhatsApp}
            size="sm"
            className="bg-green-500 hover:bg-green-600 text-white"
          >
            התחל שיחה
          </Button>
        </div>
      ) : (
        <div className="space-y-4">
          {conversations.map((conversation) => (
            <div key={conversation.id} className={`flex ${conversation.direction === 'outgoing' ? 'justify-end' : 'justify-start'}`}>
              <div className={`max-w-xs sm:max-w-sm lg:max-w-md px-4 py-2 rounded-lg ${
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
    <Card className="p-4 sm:p-6">
      <h3 className="text-lg font-medium text-gray-900 mb-4">היסטוריית שיחות טלפון</h3>
      {calls.length === 0 ? (
        <p className="text-sm text-gray-500">אין שיחות טלפון</p>
      ) : (
        <div className="space-y-4">
          {calls.map((call) => (
            <div key={call.id} className="flex flex-col sm:flex-row sm:items-center sm:justify-between p-4 bg-gray-50 rounded-lg gap-3 sm:gap-0">
              <div className="flex items-center space-x-3">
                <Phone className={`w-5 h-5 ${call.call_type === 'incoming' ? 'text-green-500' : 'text-blue-500'}`} />
                <div>
                  <p className="text-sm font-medium text-gray-900">
                    {call.call_type === 'incoming' ? 'שיחה נכנסת' : 'שיחה יוצאת'}
                  </p>
                  <p className="text-xs text-gray-500">{formatDate(call.created_at)}</p>
                </div>
              </div>
              <div className="text-right sm:text-left">
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
    <Card className="p-4 sm:p-6">
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

function InvoicesTab({ leadId }: { leadId: number }) {
  const [invoices, setInvoices] = useState<any[]>([]);
  const [loading, setLoading] = useState(false);
  const [showInvoiceModal, setShowInvoiceModal] = useState(false);

  const handleCreateInvoice = () => {
    setShowInvoiceModal(true);
  };

  return (
    <Card className="p-4 sm:p-6">
      <div className="flex items-center justify-between mb-4">
        <h3 className="text-lg font-medium text-gray-900">חשבוניות</h3>
        <Button 
          size="sm" 
          className="bg-blue-600 hover:bg-blue-700 text-white" 
          data-testid="button-create-invoice"
          onClick={handleCreateInvoice}
        >
          <Plus className="w-4 h-4 ml-2" />
          חשבונית חדשה
        </Button>
      </div>
      
      {/* Invoice Modal */}
      {showInvoiceModal && (
        <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50" data-testid="invoice-modal">
          <Card className="w-full max-w-lg">
            <div className="p-6">
              <div className="flex items-center justify-between mb-4">
                <h3 className="text-lg font-medium">צור חשבונית חדשה</h3>
                <Button 
                  variant="ghost" 
                  size="sm"
                  onClick={() => setShowInvoiceModal(false)}
                  data-testid="button-close-invoice-modal"
                >
                  ✕
                </Button>
              </div>
              
              <div className="grid grid-cols-1 gap-4">
                <Button 
                  className="p-4 bg-blue-50 hover:bg-blue-100 text-blue-900 text-right"
                  onClick={async () => {
                    try {
                      setLoading(true);
                      // Call invoice API
                      const response = await http.post<{success: boolean; message?: string}>('/api/invoices', {
                        lead_id: leadId,
                        type: 'quote',
                        title: 'הצעת מחיר',
                        items: [
                          { description: 'שירותי תיווך נדל"ן', amount: 15000, quantity: 1 }
                        ]
                      });
                      
                      if (response.success) {
                        alert('הצעת מחיר נוצרה בהצלחה!');
                        // Refresh invoices list here if needed
                      } else {
                        alert('שגיאה ביצירת הצעת מחיר');
                      }
                    } catch (err) {
                      console.error('Invoice creation failed:', err);
                      alert('יוצר הצעת מחיר לליד #' + leadId + ' (מצב דמו)');
                    } finally {
                      setLoading(false);
                      setShowInvoiceModal(false);
                    }
                  }}
                  data-testid="button-invoice-quote"
                >
                  <div>
                    <h4 className="font-medium">הצעת מחיר</h4>
                    <p className="text-sm opacity-75">הכן הצעת מחיר מקצועית ללקוח</p>
                  </div>
                </Button>
                
                <Button 
                  className="p-4 bg-green-50 hover:bg-green-100 text-green-900 text-right"
                  onClick={async () => {
                    try {
                      setLoading(true);
                      const response = await http.post<{success: boolean; message?: string}>('/api/invoices', {
                        lead_id: leadId,
                        type: 'tax_invoice',
                        title: 'חשבונית מס',
                        tax_rate: 17,
                        items: [
                          { description: 'שירותי תיווך נדל"ן', amount: 15000, quantity: 1 }
                        ]
                      });
                      
                      if (response.success) {
                        alert('חשבונית מס נוצרה בהצלחה!');
                      } else {
                        alert('שגיאה ביצירת חשבונית מס');
                      }
                    } catch (err) {
                      console.error('Tax invoice creation failed:', err);
                      alert('יוצר חשבונית מס לליד #' + leadId + ' (מצב דמו)');
                    } finally {
                      setLoading(false);
                      setShowInvoiceModal(false);
                    }
                  }}
                  data-testid="button-invoice-tax"
                >
                  <div>
                    <h4 className="font-medium">חשבונית מס</h4>
                    <p className="text-sm opacity-75">הפק חשבונית מס רשמית</p>
                  </div>
                </Button>
                
                <Button 
                  className="p-4 bg-purple-50 hover:bg-purple-100 text-purple-900 text-right"
                  onClick={async () => {
                    try {
                      setLoading(true);
                      const response = await http.post<{success: boolean; message?: string}>('/api/receipts', {
                        lead_id: leadId,
                        amount: 15000,
                        description: 'תשלום עבור שירותי תיווך נדל"ן',
                        payment_method: 'bank_transfer'
                      });
                      
                      if (response.success) {
                        alert('קבלה נוצרה בהצלחה!');
                      } else {
                        alert('שגיאה ביצירת קבלה');
                      }
                    } catch (err) {
                      console.error('Receipt creation failed:', err);
                      alert('יוצר קבלה לליד #' + leadId + ' (מצב דמו)');
                    } finally {
                      setLoading(false);
                      setShowInvoiceModal(false);
                    }
                  }}
                  data-testid="button-invoice-receipt"
                >
                  <div>
                    <h4 className="font-medium">קבלה</h4>
                    <p className="text-sm opacity-75">הפק קבלה על תשלום</p>
                  </div>
                </Button>
              </div>
            </div>
          </Card>
        </div>
      )}
      {invoices.length === 0 ? (
        <div className="text-center py-8">
          <Calendar className="w-12 h-12 text-gray-300 mx-auto mb-4" />
          <p className="text-sm text-gray-500 mb-4">אין חשבוניות עדיין</p>
          <div className="grid grid-cols-1 md:grid-cols-3 gap-4 text-right">
            <div className="p-4 bg-blue-50 rounded-lg">
              <h4 className="font-medium text-blue-900">יצירת הצעת מחיר</h4>
              <p className="text-sm text-blue-600 mt-1">הכן הצעת מחיר מקצועית ללקוח</p>
            </div>
            <div className="p-4 bg-green-50 rounded-lg">
              <h4 className="font-medium text-green-900">חשבונית מס</h4>
              <p className="text-sm text-green-600 mt-1">הפק חשבונית מס רשמית</p>
            </div>
            <div className="p-4 bg-purple-50 rounded-lg">
              <h4 className="font-medium text-purple-900">קבלה</h4>
              <p className="text-sm text-purple-600 mt-1">הפק קבלה על תשלום</p>
            </div>
          </div>
        </div>
      ) : (
        <div className="space-y-4">
          {/* Invoice list will be here */}
        </div>
      )}
    </Card>
  );
}

function ContractsTab({ leadId }: { leadId: number }) {
  const [contracts, setContracts] = useState<any[]>([]);
  const [showContractModal, setShowContractModal] = useState(false);
  const [customContractName, setCustomContractName] = useState('');
  const [loading, setLoading] = useState(false);

  const handleCreateContract = () => {
    setShowContractModal(true);
  };

  return (
    <Card className="p-6">
      <div className="flex items-center justify-between mb-4">
        <h3 className="text-lg font-medium text-gray-900">חוזים ומסמכים</h3>
        <Button 
          size="sm" 
          className="bg-green-600 hover:bg-green-700 text-white" 
          data-testid="button-create-contract"
          onClick={handleCreateContract}
        >
          <Plus className="w-4 h-4 ml-2" />
          חוזה חדש
        </Button>
      </div>
      
      {/* Contract Modal */}
      {showContractModal && (
        <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50" data-testid="contract-modal">
          <Card className="w-full max-w-lg">
            <div className="p-6">
              <div className="flex items-center justify-between mb-4">
                <h3 className="text-lg font-medium">צור חוזה חדש</h3>
                <Button 
                  variant="ghost" 
                  size="sm"
                  onClick={() => setShowContractModal(false)}
                  data-testid="button-close-contract-modal"
                >
                  ✕
                </Button>
              </div>
              
              <div className="grid grid-cols-1 gap-4">
                {/* Custom Contract Input */}
                <div className="mb-4">
                  <label className="block text-sm font-medium text-gray-700 mb-2">
                    שם החוזה המותאם
                  </label>
                  <input
                    type="text"
                    className="w-full p-2 border border-gray-300 rounded-md"
                    placeholder="הכנס שם חוזה (לדוגמה: חוזה ייעוץ, חוזה ניהול, וכו')"
                    value={customContractName}
                    onChange={(e) => setCustomContractName(e.target.value)}
                    data-testid="input-custom-contract-name"
                  />
                </div>
                
                <Button 
                  className="p-4 bg-purple-50 hover:bg-purple-100 text-purple-900 text-right"
                  onClick={async () => {
                    const contractName = customContractName.trim() || 'חוזה מותאם אישית';
                    try {
                      setLoading(true);
                      const response = await http.post<{success: boolean; message?: string}>('/api/contracts', {
                        lead_id: leadId,
                        type: 'custom',
                        title: contractName,
                        custom_details: {
                          created_by: 'user',
                          contract_category: 'custom'
                        }
                      });
                      
                      if (response.success) {
                        alert(`${contractName} נוצר בהצלחה!`);
                      } else {
                        alert(`שגיאה ביצירת ${contractName}`);
                      }
                    } catch (err) {
                      console.error('Custom contract creation failed:', err);
                      alert(`יוצר ${contractName} לליד #${leadId} (מצב דמו)`);
                    } finally {
                      setLoading(false);
                      setShowContractModal(false);
                      setCustomContractName('');
                    }
                  }}
                  data-testid="button-contract-custom"
                  disabled={!customContractName.trim()}
                >
                  <div>
                    <h4 className="font-medium">חוזה מותאם אישית</h4>
                    <p className="text-sm opacity-75">צור חוזה לפי הצרכים שלך</p>
                  </div>
                </Button>
                
                <Button 
                  className="p-4 bg-indigo-50 hover:bg-indigo-100 text-indigo-900 text-right"
                  onClick={async () => {
                    try {
                      setLoading(true);
                      const response = await http.post<{success: boolean; message?: string}>('/api/contracts', {
                        lead_id: leadId,
                        type: 'sale',
                        title: 'חוזה מכר נדל"ן',
                        property_type: 'apartment',
                        terms: {
                          payment_schedule: 'installments',
                          warranty_period: '12_months'
                        }
                      });
                      
                      if (response.success) {
                        alert('חוזה מכר נוצר בהצלחה!');
                      } else {
                        alert('שגיאה ביצירת חוזה מכר');
                      }
                    } catch (err) {
                      console.error('Contract creation failed:', err);
                      alert('יוצר חוזה מכר לליד #' + leadId + ' (מצב דמו)');
                    } finally {
                      setLoading(false);
                      setShowContractModal(false);
                    }
                  }}
                  data-testid="button-contract-sale"
                >
                  <div>
                    <h4 className="font-medium">חוזה מכר</h4>
                    <p className="text-sm opacity-75">חוזה רכישת נדל"ן רשמי</p>
                  </div>
                </Button>
                
                <Button 
                  className="p-4 bg-orange-50 hover:bg-orange-100 text-orange-900 text-right"
                  onClick={async () => {
                    try {
                      setLoading(true);
                      const response = await http.post<{success: boolean; message?: string}>('/api/contracts', {
                        lead_id: leadId,
                        type: 'rent',
                        title: 'חוזה שכירות',
                        rental_terms: {
                          duration: '12_months',
                          deposit_amount: 12000,
                          monthly_rent: 4000
                        }
                      });
                      
                      if (response.success) {
                        alert('חוזה שכירות נוצר בהצלחה!');
                      } else {
                        alert('שגיאה ביצירת חוזה שכירות');
                      }
                    } catch (err) {
                      console.error('Rental contract creation failed:', err);
                      alert('יוצר חוזה שכירות לליד #' + leadId + ' (מצב דמו)');
                    } finally {
                      setLoading(false);
                      setShowContractModal(false);
                    }
                  }}
                  data-testid="button-contract-rent"
                >
                  <div>
                    <h4 className="font-medium">חוזה שכירות</h4>
                    <p className="text-sm opacity-75">חוזה שכירות מפורט</p>
                  </div>
                </Button>
                
                <Button 
                  className="p-4 bg-yellow-50 hover:bg-yellow-100 text-yellow-900 text-right"
                  onClick={async () => {
                    try {
                      setLoading(true);
                      const response = await http.post<{success: boolean; message?: string}>('/api/contracts', {
                        lead_id: leadId,
                        type: 'mediation',
                        title: 'הסכם תיווך נדל"ן',
                        commission_rate: 2.5,
                        exclusivity_period: '3_months'
                      });
                      
                      if (response.success) {
                        alert('הסכם תיווך נוצר בהצלחה!');
                      } else {
                        alert('שגיאה ביצירת הסכם תיווך');
                      }
                    } catch (err) {
                      console.error('Mediation contract creation failed:', err);
                      alert('יוצר הסכם תיווך לליד #' + leadId + ' (מצב דמו)');
                    } finally {
                      setLoading(false);
                      setShowContractModal(false);
                    }
                  }}
                  data-testid="button-contract-mediation"
                >
                  <div>
                    <h4 className="font-medium">הסכם תיווך</h4>
                    <p className="text-sm opacity-75">הסכם תיווך נדל"ן</p>
                  </div>
                </Button>
              </div>
            </div>
          </Card>
        </div>
      )}
      {contracts.length === 0 ? (
        <div className="text-center py-8">
          <Tag className="w-12 h-12 text-gray-300 mx-auto mb-4" />
          <p className="text-sm text-gray-500 mb-4">אין חוזים עדיין</p>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4 text-right">
            <div className="p-4 bg-indigo-50 rounded-lg">
              <h4 className="font-medium text-indigo-900">חוזה מכר</h4>
              <p className="text-sm text-indigo-600 mt-1">חוזה רכישת נדל"ן רשמי</p>
            </div>
            <div className="p-4 bg-orange-50 rounded-lg">
              <h4 className="font-medium text-orange-900">חוזה שכירות</h4>
              <p className="text-sm text-orange-600 mt-1">חוזה שכירות מפורט</p>
            </div>
          </div>
        </div>
      ) : (
        <div className="space-y-4">
          {/* Contract list will be here */}
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