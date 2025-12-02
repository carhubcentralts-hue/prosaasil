import React, { useState, useEffect, useCallback } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { ArrowLeft, Phone, Mail, MessageSquare, Clock, Activity, CheckCircle2, Circle, User, Tag, Calendar, Plus, Pencil, Save, X, Loader2, ChevronDown } from 'lucide-react';
import WhatsAppChat from './components/WhatsAppChat';
import { ReminderModal } from './components/ReminderModal';
import { Button } from '../../shared/components/ui/Button';
import { Card } from '../../shared/components/ui/Card';
import { Badge } from '../../shared/components/Badge';
import { Input } from '../../shared/components/ui/Input';
import { Lead, LeadActivity, LeadReminder, LeadCall, LeadAppointment } from './types';
import { http } from '../../services/http';
import { formatDate } from '../../shared/utils/format';
import { useStatuses, LeadStatus } from '../../features/statuses/hooks';
import { getStatusColor, getStatusLabel } from '../../shared/utils/status';

interface LeadDetailPageProps {}

const TABS = [
  { key: 'overview', label: 'סקירה', icon: User },
  { key: 'conversation', label: 'וואטסאפ', icon: MessageSquare },
  { key: 'calls', label: 'שיחות טלפון', icon: Phone },
  { key: 'appointments', label: 'פגישות', icon: Calendar },
  { key: 'reminders', label: 'משימות', icon: CheckCircle2 },
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
  const [editingReminder, setEditingReminder] = useState<LeadReminder | null>(null);
  
  // Edit mode state
  const [isEditing, setIsEditing] = useState(false);
  const [isSaving, setIsSaving] = useState(false);
  const [editForm, setEditForm] = useState({
    first_name: '',
    last_name: '',
    phone_e164: '',
    email: ''
  });
  
  // Status management - use shared hook for consistent statuses
  const { statuses, refreshStatuses } = useStatuses();
  const [statusDropdownOpen, setStatusDropdownOpen] = useState(false);
  const [statusSaving, setStatusSaving] = useState(false);
  
  // Data for each tab
  const [activities, setActivities] = useState<LeadActivity[]>([]);
  const [reminders, setReminders] = useState<LeadReminder[]>([]);
  const [calls, setCalls] = useState<LeadCall[]>([]);
  const [appointments, setAppointments] = useState<LeadAppointment[]>([]);
  const [loadingCalls, setLoadingCalls] = useState(false);
  const [loadingAppointments, setLoadingAppointments] = useState(false);

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
      
      // Immediately hide loading state - lead is loaded
      setLoading(false);
      
      // Fire calls and appointments fetches independently (each has its own error handling)
      if (response.phone_e164) {
        fetchCalls(response.phone_e164);
        fetchAppointments(response.phone_e164);
      }
    } catch (err) {
      console.error('Failed to fetch lead:', err);
      setError('שגיאה בטעינת פרטי הליד');
      setLoading(false);
    }
  };

  const fetchCalls = async (phone: string) => {
    try {
      setLoadingCalls(true);
      const response = await http.get<{ success: boolean; calls: any[] }>(`/api/calls?search=${encodeURIComponent(phone)}`);
      if (response.success && response.calls) {
        const leadCalls: LeadCall[] = response.calls.map((call: any) => ({
          id: call.call_sid || call.id,
          lead_id: parseInt(id || '0'),
          call_type: (call.direction === 'inbound' ? 'incoming' : 'outgoing') as 'incoming' | 'outgoing',
          duration: call.duration || 0,
          recording_url: call.recording_url,
          notes: call.transcription || '',
          summary: call.summary || '',
          created_at: call.created_at,
          status: call.status
        }));
        setCalls(leadCalls);
      }
    } catch (err) {
      console.error('Failed to fetch calls:', err);
      setCalls([]);
    } finally {
      setLoadingCalls(false);
    }
  };

  const fetchAppointments = async (phone: string) => {
    try {
      setLoadingAppointments(true);
      const response = await http.get<{ appointments: any[] }>(`/api/calendar/appointments?search=${encodeURIComponent(phone)}`);
      if (response.appointments) {
        const leadAppointments: LeadAppointment[] = response.appointments.map((appt: any) => ({
          id: appt.id,
          title: appt.title,
          start_time: appt.start_time,
          end_time: appt.end_time,
          status: appt.status,
          contact_name: appt.contact_name,
          notes: appt.notes,
          call_summary: appt.call_summary
        }));
        setAppointments(leadAppointments);
      }
    } catch (err) {
      console.error('Failed to fetch appointments:', err);
      setAppointments([]);
    } finally {
      setLoadingAppointments(false);
    }
  };

  // Refresh statuses when component mounts
  useEffect(() => {
    refreshStatuses();
  }, [refreshStatuses]);

  const startEditing = () => {
    if (lead) {
      setEditForm({
        first_name: lead.first_name || '',
        last_name: lead.last_name || '',
        phone_e164: lead.phone_e164 || '',
        email: lead.email || ''
      });
      setIsEditing(true);
    }
  };

  const cancelEditing = () => {
    setIsEditing(false);
    setEditForm({
      first_name: '',
      last_name: '',
      phone_e164: '',
      email: ''
    });
  };

  const saveLead = async () => {
    if (!lead) return;
    
    setIsSaving(true);
    try {
      const response = await http.patch<{ lead: Lead }>(`/api/leads/${lead.id}`, editForm);
      if (response.lead) {
        setLead({ ...lead, ...response.lead });
      }
      setIsEditing(false);
    } catch (err) {
      console.error('Failed to save lead:', err);
    } finally {
      setIsSaving(false);
    }
  };

  const updateLeadStatus = async (newStatus: string) => {
    if (!lead) return;
    
    setStatusSaving(true);
    try {
      await http.post(`/api/leads/${lead.id}/status`, { status: newStatus });
      setLead({ ...lead, status: newStatus });
      setStatusDropdownOpen(false);
    } catch (err) {
      console.error('Failed to update status:', err);
    } finally {
      setStatusSaving(false);
    }
  };



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

  const StatusDropdown = () => (
    <div className="relative">
      <button
        onClick={() => setStatusDropdownOpen(!statusDropdownOpen)}
        disabled={statusSaving}
        className={`flex items-center gap-2 px-3 py-1.5 rounded-full text-sm font-medium ${getStatusColor(lead.status, statuses)} hover:opacity-80 transition-opacity`}
        data-testid="status-dropdown-trigger"
      >
        {statusSaving ? (
          <Loader2 className="w-3 h-3 animate-spin" />
        ) : null}
        {getStatusLabel(lead.status, statuses)}
        <ChevronDown className="w-3 h-3" />
      </button>
      
      {statusDropdownOpen && (
        <>
          <div 
            className="fixed inset-0 z-10" 
            onClick={() => setStatusDropdownOpen(false)}
          />
          <div className="absolute top-full left-0 mt-2 w-48 bg-white rounded-lg shadow-lg border border-gray-200 py-1 z-20" data-testid="status-dropdown-menu">
            {statuses.length > 0 ? (
              statuses.map((status) => (
                <button
                  key={status.id}
                  onClick={() => updateLeadStatus(status.name)}
                  className={`w-full px-4 py-2 text-sm text-right hover:bg-gray-50 flex items-center gap-2 ${
                    status.name.toLowerCase() === lead.status.toLowerCase() ? 'bg-gray-50' : ''
                  }`}
                  data-testid={`status-option-${status.name}`}
                >
                  <span 
                    className="w-3 h-3 rounded-full" 
                    style={{ backgroundColor: status.color || '#gray' }}
                  />
                  {status.label}
                </button>
              ))
            ) : (
              <div className="px-4 py-2 text-sm text-gray-500">טוען סטטוסים...</div>
            )}
          </div>
        </>
      )}
    </div>
  );

  return (
    <div className="min-h-screen bg-gray-50">
      {/* Header - sticky at top for both mobile and desktop */}
      <div className="bg-white border-b border-gray-200 sticky top-0 z-20">
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
              <StatusDropdown />
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
              <StatusDropdown />
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
        {activeTab === 'overview' && (
          <OverviewTab 
            lead={lead} 
            reminders={reminders} 
            onOpenReminder={() => { setEditingReminder(null); setReminderModalOpen(true); }}
            isEditing={isEditing}
            isSaving={isSaving}
            editForm={editForm}
            setEditForm={setEditForm}
            startEditing={startEditing}
            cancelEditing={cancelEditing}
            saveLead={saveLead}
          />
        )}
        {activeTab === 'conversation' && <ConversationTab lead={lead} onOpenWhatsApp={() => setWhatsappChatOpen(true)} />}
        {activeTab === 'calls' && <CallsTab calls={calls} loading={loadingCalls} />}
        {activeTab === 'appointments' && <AppointmentsTab appointments={appointments} loading={loadingAppointments} lead={lead} onRefresh={fetchLead} />}
        {activeTab === 'reminders' && <RemindersTab reminders={reminders} onOpenReminder={() => { setEditingReminder(null); setReminderModalOpen(true); }} onEditReminder={(reminder) => { setEditingReminder(reminder); setReminderModalOpen(true); }} />}
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
          reminder={editingReminder}
          isOpen={reminderModalOpen}
          onClose={() => {
            setReminderModalOpen(false);
            setEditingReminder(null);
          }}
          onSuccess={fetchLead}
        />
      )}
    </div>
  );
}

// Tab Components
interface OverviewTabProps {
  lead: Lead;
  reminders: LeadReminder[];
  onOpenReminder: () => void;
  isEditing: boolean;
  isSaving: boolean;
  editForm: {
    first_name: string;
    last_name: string;
    phone_e164: string;
    email: string;
  };
  setEditForm: React.Dispatch<React.SetStateAction<{
    first_name: string;
    last_name: string;
    phone_e164: string;
    email: string;
  }>>;
  startEditing: () => void;
  cancelEditing: () => void;
  saveLead: () => void;
}

function OverviewTab({ lead, reminders, onOpenReminder, isEditing, isSaving, editForm, setEditForm, startEditing, cancelEditing, saveLead }: OverviewTabProps) {
  return (
    <div className="flex flex-col lg:grid lg:grid-cols-3 gap-6">
      {/* Lead Info */}
      <div className="lg:col-span-2">
        <Card className="p-4 sm:p-6">
          <div className="flex items-center justify-between mb-4">
            <h3 className="text-lg font-medium text-gray-900">פרטי קשר</h3>
            {!isEditing ? (
              <Button
                onClick={startEditing}
                size="sm"
                variant="secondary"
                data-testid="button-edit-lead"
              >
                <Pencil className="w-4 h-4 mr-2" />
                ערוך
              </Button>
            ) : (
              <div className="flex gap-2">
                <Button
                  onClick={cancelEditing}
                  size="sm"
                  variant="ghost"
                  disabled={isSaving}
                  data-testid="button-cancel-edit"
                >
                  <X className="w-4 h-4 mr-2" />
                  ביטול
                </Button>
                <Button
                  onClick={saveLead}
                  size="sm"
                  disabled={isSaving}
                  data-testid="button-save-lead"
                >
                  {isSaving ? (
                    <Loader2 className="w-4 h-4 mr-2 animate-spin" />
                  ) : (
                    <Save className="w-4 h-4 mr-2" />
                  )}
                  שמור
                </Button>
              </div>
            )}
          </div>
          
          {isEditing ? (
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-4 sm:gap-6">
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">שם פרטי</label>
                <Input
                  value={editForm.first_name}
                  onChange={(e) => setEditForm(prev => ({ ...prev, first_name: e.target.value }))}
                  className="w-full"
                  data-testid="input-first-name"
                />
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">שם משפחה</label>
                <Input
                  value={editForm.last_name}
                  onChange={(e) => setEditForm(prev => ({ ...prev, last_name: e.target.value }))}
                  className="w-full"
                  data-testid="input-last-name"
                />
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">טלפון</label>
                <Input
                  value={editForm.phone_e164}
                  onChange={(e) => setEditForm(prev => ({ ...prev, phone_e164: e.target.value }))}
                  className="w-full"
                  data-testid="input-phone"
                />
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">אימייל</label>
                <Input
                  value={editForm.email}
                  onChange={(e) => setEditForm(prev => ({ ...prev, email: e.target.value }))}
                  type="email"
                  className="w-full"
                  data-testid="input-email"
                />
              </div>
            </div>
          ) : (
            <>
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
              
              {lead.whatsapp_last_summary && (
                <div className="mt-4 bg-green-50 p-4 rounded-lg border border-green-200">
                  <div className="flex items-center gap-2 mb-2">
                    <MessageSquare className="w-4 h-4 text-green-600" />
                    <label className="block text-sm font-medium text-green-800">סיכום שיחת וואטסאפ אחרונה</label>
                    {lead.whatsapp_last_summary_at && (
                      <span className="text-xs text-green-600 mr-auto">
                        {formatDate(lead.whatsapp_last_summary_at)}
                      </span>
                    )}
                  </div>
                  <p className="text-sm text-green-900 whitespace-pre-wrap" data-testid="text-whatsapp-summary">{lead.whatsapp_last_summary}</p>
                </div>
              )}
            </>
          )}
          
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
          
          {/* Notes Section */}
          <NotesSection lead={lead} />
        </Card>
      </div>

      {/* Tasks */}
      <div className="order-first lg:order-last">
        <Card className="p-4 sm:p-6">
          <div className="flex items-center justify-between mb-4">
            <h3 className="text-lg font-medium text-gray-900">משימות קרובות</h3>
            <Button
              onClick={onOpenReminder}
              size="sm"
              className="bg-blue-600 hover:bg-blue-700 text-white"
              data-testid="button-create-reminder"
            >
              <Clock className="w-4 h-4 mr-2" />
              צור משימה
            </Button>
          </div>
          {reminders.length === 0 ? (
            <div className="text-center py-8">
              <Clock className="w-12 h-12 text-gray-300 mx-auto mb-4" />
              <p className="text-sm text-gray-500 mb-4">אין משימות</p>
              <Button
                onClick={onOpenReminder}
                size="sm"
                className="bg-blue-600 hover:bg-blue-700 text-white"
              >
                <Clock className="w-4 h-4 mr-2" />
                צור משימה ראשונה
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

function ConversationTab({ lead, onOpenWhatsApp }: { lead: Lead; onOpenWhatsApp: () => void }) {
  const hasSummary = !!lead.whatsapp_last_summary;
  
  return (
    <Card className="p-4 sm:p-6">
      <div className="flex items-center justify-between mb-4">
        <h3 className="text-lg font-medium text-gray-900">סיכום שיחת וואטסאפ</h3>
        <Button 
          onClick={onOpenWhatsApp} 
          size="sm"
          className="bg-green-500 hover:bg-green-600 text-white"
          data-testid="button-open-whatsapp-chat"
        >
          <MessageSquare className="w-4 h-4 mr-2" />
          פתח שיחה
        </Button>
      </div>
      
      {hasSummary ? (
        <div className="bg-green-50 border border-green-200 rounded-lg p-4">
          <div className="flex items-start gap-3">
            <div className="w-10 h-10 rounded-full bg-green-500 flex items-center justify-center flex-shrink-0">
              <MessageSquare className="w-5 h-5 text-white" />
            </div>
            <div className="flex-1">
              <div className="flex items-center justify-between mb-2">
                <span className="text-sm font-medium text-green-800">סיכום שיחה אחרון</span>
                {lead.whatsapp_last_summary_at && (
                  <span className="text-xs text-green-600">
                    {formatDate(lead.whatsapp_last_summary_at)}
                  </span>
                )}
              </div>
              <p className="text-sm text-gray-700 whitespace-pre-wrap leading-relaxed">
                {lead.whatsapp_last_summary}
              </p>
            </div>
          </div>
        </div>
      ) : (
        <div className="text-center py-8">
          <MessageSquare className="w-12 h-12 text-gray-300 mx-auto mb-4" />
          <p className="text-sm text-gray-500 mb-2">אין סיכום שיחה עדיין</p>
          <p className="text-xs text-gray-400 mb-4">
            סיכום נוצר אוטומטית אחרי 15 דקות ללא פעילות מהלקוח
          </p>
          <Button 
            onClick={onOpenWhatsApp}
            size="sm"
            className="bg-green-500 hover:bg-green-600 text-white"
          >
            <MessageSquare className="w-4 h-4 mr-2" />
            התחל שיחה
          </Button>
        </div>
      )}
    </Card>
  );
}

function CallsTab({ calls, loading }: { calls: LeadCall[]; loading?: boolean }) {
  return (
    <Card className="p-4 sm:p-6">
      <h3 className="text-lg font-medium text-gray-900 mb-4">היסטוריית שיחות טלפון</h3>
      {loading ? (
        <div className="flex items-center justify-center py-8">
          <Loader2 className="w-6 h-6 animate-spin text-gray-400" />
          <span className="text-sm text-gray-500 mr-2">טוען שיחות...</span>
        </div>
      ) : calls.length === 0 ? (
        <p className="text-sm text-gray-500">אין שיחות טלפון</p>
      ) : (
        <div className="space-y-4">
          {calls.map((call) => (
            <div key={call.id} className="p-4 bg-gray-50 rounded-lg" data-testid={`call-${call.id}`}>
              <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3 sm:gap-0 mb-3">
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
                  <p className="text-sm text-gray-900">{call.duration} שניות</p>
                </div>
              </div>
              {call.summary && (
                <div className="mt-2 p-3 bg-blue-50 rounded-lg border border-blue-100">
                  <p className="text-xs font-medium text-blue-800 mb-1">סיכום שיחה:</p>
                  <p className="text-sm text-blue-900">{call.summary}</p>
                </div>
              )}
            </div>
          ))}
        </div>
      )}
    </Card>
  );
}

function NotesSection({ lead }: { lead: Lead }) {
  const [isEditing, setIsEditing] = useState(false);
  const [notes, setNotes] = useState(lead.notes || '');
  const [saving, setSaving] = useState(false);

  const handleSave = async () => {
    try {
      setSaving(true);
      await http.patch(`/api/leads/${lead.id}`, { notes });
      setIsEditing(false);
    } catch (err) {
      console.error('Error saving notes:', err);
      alert('שגיאה בשמירת ההערות');
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="mt-6 border-t pt-6">
      <div className="flex items-center justify-between mb-3">
        <label className="block text-sm font-medium text-gray-700">הערות</label>
        {!isEditing ? (
          <Button
            size="sm"
            variant="ghost"
            onClick={() => setIsEditing(true)}
            data-testid="button-edit-notes"
          >
            <Pencil className="w-4 h-4 ml-1" />
            ערוך
          </Button>
        ) : (
          <div className="flex gap-2">
            <Button size="sm" variant="ghost" onClick={() => { setIsEditing(false); setNotes(lead.notes || ''); }} disabled={saving}>
              <X className="w-4 h-4" />
            </Button>
            <Button size="sm" onClick={handleSave} disabled={saving} data-testid="button-save-notes">
              {saving ? <Loader2 className="w-4 h-4 animate-spin" /> : <Save className="w-4 h-4 ml-1" />}
              {saving ? '' : 'שמור'}
            </Button>
          </div>
        )}
      </div>
      
      {isEditing ? (
        <textarea
          className="w-full p-3 border border-gray-300 rounded-lg min-h-[120px] text-sm"
          value={notes}
          onChange={(e) => setNotes(e.target.value)}
          placeholder="הוסף הערות על הלקוח..."
          data-testid="input-lead-notes"
        />
      ) : notes ? (
        <div className="p-3 bg-gray-50 rounded-lg">
          <p className="text-sm text-gray-700 whitespace-pre-wrap" data-testid="text-lead-notes">{notes}</p>
        </div>
      ) : (
        <div className="text-center py-6 bg-gray-50 rounded-lg">
          <p className="text-sm text-gray-500 mb-2">אין הערות</p>
          <Button size="sm" variant="secondary" onClick={() => setIsEditing(true)} data-testid="button-add-notes">
            <Plus className="w-4 h-4 ml-1" />
            הוסף הערה
          </Button>
        </div>
      )}
    </div>
  );
}

const APPOINTMENT_TYPES = {
  viewing: { label: 'צפייה', color: 'bg-blue-100 text-blue-800' },
  meeting: { label: 'פגישה', color: 'bg-green-100 text-green-800' },
  signing: { label: 'חתימה', color: 'bg-purple-100 text-purple-800' },
  call_followup: { label: 'מעקב שיחה', color: 'bg-orange-100 text-orange-800' },
  phone_call: { label: 'שיחה טלפונית', color: 'bg-cyan-100 text-cyan-800' }
};

function AppointmentsTab({ appointments, loading, lead, onRefresh }: { appointments: LeadAppointment[]; loading?: boolean; lead?: Lead; onRefresh?: () => void }) {
  const [showModal, setShowModal] = useState(false);
  const [saving, setSaving] = useState(false);
  const [formData, setFormData] = useState({
    title: '',
    appointment_type: 'meeting' as string,
    start_time: '',
    end_time: '',
    notes: ''
  });

  const formatDateTime = (dateStr: string) => {
    const date = new Date(dateStr);
    return date.toLocaleString('he-IL', {
      weekday: 'short',
      day: 'numeric',
      month: 'short',
      hour: '2-digit',
      minute: '2-digit'
    });
  };

  const getStatusBadge = (status: string) => {
    const statusMap: Record<string, { label: string; className: string }> = {
      'scheduled': { label: 'מתוכנן', className: 'bg-yellow-100 text-yellow-800' },
      'confirmed': { label: 'מאושר', className: 'bg-green-100 text-green-800' },
      'paid': { label: 'שולם', className: 'bg-blue-100 text-blue-800' },
      'unpaid': { label: 'לא שולם', className: 'bg-red-100 text-red-800' },
      'cancelled': { label: 'בוטל', className: 'bg-gray-100 text-gray-800' },
    };
    const config = statusMap[status] || { label: status, className: 'bg-gray-100 text-gray-800' };
    return <Badge className={config.className}>{config.label}</Badge>;
  };

  const handleCreateAppointment = async () => {
    if (!formData.title || !formData.start_time || !formData.end_time) {
      alert('נא למלא כותרת, תאריך התחלה ותאריך סיום');
      return;
    }

    try {
      setSaving(true);
      await http.post('/api/calendar/appointments', {
        title: formData.title,
        appointment_type: formData.appointment_type,
        start_time: formData.start_time,
        end_time: formData.end_time,
        notes: formData.notes,
        contact_name: lead ? `${lead.first_name || ''} ${lead.last_name || ''}`.trim() : '',
        contact_phone: lead?.phone_e164 || '',
        status: 'scheduled',
        priority: 'medium'
      });
      
      setShowModal(false);
      setFormData({ title: '', appointment_type: 'meeting', start_time: '', end_time: '', notes: '' });
      onRefresh?.();
    } catch (err) {
      console.error('Error creating appointment:', err);
      alert('שגיאה ביצירת הפגישה');
    } finally {
      setSaving(false);
    }
  };

  const openNewAppointment = () => {
    const now = new Date();
    now.setMinutes(Math.ceil(now.getMinutes() / 30) * 30);
    const startTime = now.toISOString().slice(0, 16);
    now.setHours(now.getHours() + 1);
    const endTime = now.toISOString().slice(0, 16);
    
    setFormData({
      title: lead ? `פגישה עם ${lead.first_name || ''} ${lead.last_name || ''}`.trim() : 'פגישה חדשה',
      appointment_type: 'meeting',
      start_time: startTime,
      end_time: endTime,
      notes: ''
    });
    setShowModal(true);
  };

  return (
    <Card className="p-4 sm:p-6">
      <div className="flex items-center justify-between mb-4">
        <h3 className="text-lg font-medium text-gray-900">פגישות</h3>
        <Button 
          size="sm" 
          onClick={openNewAppointment}
          data-testid="button-add-appointment"
        >
          <Plus className="w-4 h-4 ml-2" />
          פגישה חדשה
        </Button>
      </div>

      {showModal && (
        <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50" data-testid="appointment-modal">
          <Card className="w-full max-w-md mx-4">
            <div className="p-6">
              <div className="flex items-center justify-between mb-4">
                <h3 className="text-lg font-medium">תאם פגישה חדשה</h3>
                <Button variant="ghost" size="sm" onClick={() => setShowModal(false)} data-testid="button-close-appointment-modal">
                  <X className="w-4 h-4" />
                </Button>
              </div>
              
              <div className="space-y-4">
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">כותרת</label>
                  <Input
                    value={formData.title}
                    onChange={(e) => setFormData({ ...formData, title: e.target.value })}
                    placeholder="נושא הפגישה"
                    data-testid="input-appointment-title"
                  />
                </div>
                
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">סוג פגישה</label>
                  <select
                    className="w-full p-2 border border-gray-300 rounded-md"
                    value={formData.appointment_type}
                    onChange={(e) => setFormData({ ...formData, appointment_type: e.target.value })}
                    data-testid="select-appointment-type"
                  >
                    {Object.entries(APPOINTMENT_TYPES).map(([key, { label }]) => (
                      <option key={key} value={key}>{label}</option>
                    ))}
                  </select>
                </div>
                
                <div className="grid grid-cols-2 gap-3">
                  <div>
                    <label className="block text-sm font-medium text-gray-700 mb-1">התחלה</label>
                    <Input
                      type="datetime-local"
                      value={formData.start_time}
                      onChange={(e) => setFormData({ ...formData, start_time: e.target.value })}
                      data-testid="input-appointment-start"
                    />
                  </div>
                  <div>
                    <label className="block text-sm font-medium text-gray-700 mb-1">סיום</label>
                    <Input
                      type="datetime-local"
                      value={formData.end_time}
                      onChange={(e) => setFormData({ ...formData, end_time: e.target.value })}
                      data-testid="input-appointment-end"
                    />
                  </div>
                </div>
                
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">הערות</label>
                  <textarea
                    className="w-full p-2 border border-gray-300 rounded-md min-h-[80px]"
                    value={formData.notes}
                    onChange={(e) => setFormData({ ...formData, notes: e.target.value })}
                    placeholder="הערות נוספות..."
                    data-testid="input-appointment-notes"
                  />
                </div>
                
                <div className="flex gap-2 pt-2">
                  <Button onClick={handleCreateAppointment} disabled={saving} className="flex-1" data-testid="button-save-appointment">
                    {saving ? <Loader2 className="w-4 h-4 animate-spin ml-2" /> : null}
                    {saving ? 'שומר...' : 'שמור פגישה'}
                  </Button>
                  <Button variant="secondary" onClick={() => setShowModal(false)} className="flex-1">
                    ביטול
                  </Button>
                </div>
              </div>
            </div>
          </Card>
        </div>
      )}

      {loading ? (
        <div className="flex items-center justify-center py-8">
          <Loader2 className="w-6 h-6 animate-spin text-gray-400" />
          <span className="text-sm text-gray-500 mr-2">טוען פגישות...</span>
        </div>
      ) : appointments.length === 0 ? (
        <div className="text-center py-8">
          <Calendar className="w-12 h-12 text-gray-300 mx-auto mb-4" />
          <p className="text-sm text-gray-500 mb-3">אין פגישות</p>
          <Button size="sm" variant="secondary" onClick={openNewAppointment} data-testid="button-add-first-appointment">
            <Plus className="w-4 h-4 ml-2" />
            תאם פגישה ראשונה
          </Button>
        </div>
      ) : (
        <div className="space-y-4">
          {appointments.map((appointment) => (
            <div key={appointment.id} className="p-4 bg-gray-50 rounded-lg" data-testid={`appointment-${appointment.id}`}>
              <div className="flex flex-col sm:flex-row sm:items-start sm:justify-between gap-3">
                <div className="flex-1">
                  <div className="flex items-center gap-2 mb-2">
                    <Calendar className="w-4 h-4 text-blue-500" />
                    <p className="text-sm font-medium text-gray-900">{appointment.title}</p>
                    {getStatusBadge(appointment.status)}
                  </div>
                  <p className="text-sm text-gray-600 mb-1">
                    {formatDateTime(appointment.start_time)} - {formatDateTime(appointment.end_time)}
                  </p>
                  {appointment.contact_name && (
                    <p className="text-xs text-gray-500">איש קשר: {appointment.contact_name}</p>
                  )}
                </div>
              </div>
              {appointment.notes && (
                <div className="mt-3 p-3 bg-white rounded border">
                  <p className="text-xs font-medium text-gray-700 mb-1">הערות:</p>
                  <p className="text-sm text-gray-600 whitespace-pre-wrap">{appointment.notes}</p>
                </div>
              )}
              {appointment.call_summary && (
                <div className="mt-2 p-3 bg-blue-50 rounded-lg border border-blue-100">
                  <p className="text-xs font-medium text-blue-800 mb-1">סיכום שיחה:</p>
                  <p className="text-sm text-blue-900">{appointment.call_summary}</p>
                </div>
              )}
            </div>
          ))}
        </div>
      )}
    </Card>
  );
}

function RemindersTab({ reminders, onOpenReminder, onEditReminder }: { reminders: LeadReminder[]; onOpenReminder: () => void; onEditReminder: (reminder: LeadReminder) => void }) {
  return (
    <Card className="p-4 sm:p-6">
      <div className="flex items-center justify-between mb-4">
        <h3 className="text-lg font-medium text-gray-900">משימות</h3>
        <Button 
          size="sm" 
          onClick={onOpenReminder}
          data-testid="button-add-reminder"
        >
          <Plus className="w-4 h-4 ml-2" />
          משימה חדשה
        </Button>
      </div>
      {reminders.length === 0 ? (
        <p className="text-sm text-gray-500">אין משימות</p>
      ) : (
        <div className="space-y-3">
          {reminders.map((reminder) => (
            <div key={reminder.id} className="flex items-center space-x-3 p-3 bg-gray-50 rounded-lg">
              {reminder.completed_at ? (
                <CheckCircle2 className="w-5 h-5 text-green-500" />
              ) : (
                <Circle className="w-5 h-5 text-gray-400" />
              )}
              <div className="flex-1 min-w-0">
                <p className={`text-sm ${reminder.completed_at ? 'line-through text-gray-500' : 'text-gray-900'}`}>
                  {reminder.note}
                </p>
                {reminder.due_at && (
                  <p className="text-xs text-gray-500">
                    <Clock className="w-3 h-3 inline mr-1" />
                    {formatDate(reminder.due_at)}
                  </p>
                )}
              </div>
              <button
                onClick={() => onEditReminder(reminder)}
                className="p-2 hover:bg-gray-200 rounded-lg transition-colors"
                data-testid={`button-edit-reminder-${reminder.id}`}
              >
                <Pencil className="w-4 h-4 text-gray-600" />
              </button>
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
  const [invoiceForm, setInvoiceForm] = useState({
    amount: '',
    description: ''
  });

  useEffect(() => {
    loadInvoices();
  }, [leadId]);

  const loadInvoices = async () => {
    try {
      setLoading(true);
      const response = await http.get('/api/receipts') as any;
      const allInvoices = response?.invoices || [];
      const leadInvoices = allInvoices.filter((inv: any) => inv.lead_id === leadId);
      setInvoices(leadInvoices);
    } catch (error) {
      console.error('Error loading invoices:', error);
      setInvoices([]);
    } finally {
      setLoading(false);
    }
  };

  const handleCreateInvoice = async () => {
    try {
      if (!invoiceForm.amount || !invoiceForm.description) {
        alert('נא למלא את כל השדות');
        return;
      }

      setLoading(true);
      const response = await http.post('/api/receipts', {
        lead_id: leadId,
        amount: parseFloat(invoiceForm.amount),
        description: invoiceForm.description,
        customer_name: 'לקוח'
      }) as any;

      if (response.success) {
        alert(`חשבונית ${response.invoice_number} נוצרה בהצלחה!`);
        setShowInvoiceModal(false);
        setInvoiceForm({ amount: '', description: '' });
        loadInvoices();
      } else {
        alert('שגיאה ביצירת החשבונית');
      }
    } catch (error) {
      console.error('Error creating invoice:', error);
      alert('שגיאה ביצירת החשבונית');
    } finally {
      setLoading(false);
    }
  };

  const formatCurrency = (amount: number) => {
    return new Intl.NumberFormat('he-IL', {
      style: 'currency',
      currency: 'ILS'
    }).format(amount);
  };

  return (
    <Card className="p-4 sm:p-6">
      <div className="flex items-center justify-between mb-4">
        <h3 className="text-lg font-medium text-gray-900">חשבוניות</h3>
        <Button 
          size="sm" 
          className="bg-blue-600 hover:bg-blue-700 text-white" 
          data-testid="button-create-invoice"
          onClick={() => setShowInvoiceModal(true)}
        >
          <Plus className="w-4 h-4 ml-2" />
          חשבונית חדשה
        </Button>
      </div>
      
      {showInvoiceModal && (
        <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50" data-testid="invoice-modal">
          <Card className="w-full max-w-md mx-4">
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
              
              <div className="space-y-4">
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">סכום</label>
                  <Input
                    type="number"
                    placeholder="0.00"
                    value={invoiceForm.amount}
                    onChange={(e) => setInvoiceForm({ ...invoiceForm, amount: e.target.value })}
                    data-testid="input-invoice-amount"
                  />
                </div>
                
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">תיאור</label>
                  <Input
                    type="text"
                    placeholder="תיאור החשבונית"
                    value={invoiceForm.description}
                    onChange={(e) => setInvoiceForm({ ...invoiceForm, description: e.target.value })}
                    data-testid="input-invoice-description"
                  />
                </div>
                
                <div className="flex gap-2 pt-4">
                  <Button
                    onClick={handleCreateInvoice}
                    disabled={loading}
                    className="flex-1"
                    data-testid="button-submit-invoice"
                  >
                    {loading ? 'יוצר...' : 'צור חשבונית'}
                  </Button>
                  <Button
                    variant="secondary"
                    onClick={() => setShowInvoiceModal(false)}
                    className="flex-1"
                  >
                    ביטול
                  </Button>
                </div>
              </div>
            </div>
          </Card>
        </div>
      )}

      {loading && invoices.length === 0 ? (
        <div className="text-center py-8">
          <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-blue-600 mx-auto mb-4"></div>
          <p className="text-sm text-gray-500">טוען חשבוניות...</p>
        </div>
      ) : invoices.length === 0 ? (
        <div className="text-center py-8">
          <Calendar className="w-12 h-12 text-gray-300 mx-auto mb-4" />
          <p className="text-sm text-gray-500 mb-4">אין חשבוניות עדיין</p>
        </div>
      ) : (
        <div className="space-y-3">
          {invoices.map((invoice) => (
            <div key={invoice.id} className="p-4 bg-gray-50 rounded-lg" data-testid={`invoice-${invoice.id}`}>
              <div className="flex justify-between items-start mb-2">
                <div>
                  <p className="text-sm font-medium text-gray-900">{invoice.description}</p>
                  <p className="text-xs text-gray-500">מספר: {invoice.invoice_number}</p>
                </div>
                <p className="text-lg font-bold text-gray-900">{formatCurrency(invoice.total || invoice.amount)}</p>
              </div>
              <div className="flex justify-between items-center text-xs text-gray-500">
                <span>{formatDate(invoice.created_at)}</span>
                <Badge className={invoice.status === 'paid' ? 'bg-green-100 text-green-800' : 'bg-yellow-100 text-yellow-800'}>
                  {invoice.status === 'paid' ? 'שולם' : 'ממתין'}
                </Badge>
              </div>
            </div>
          ))}
        </div>
      )}
    </Card>
  );
}

function ContractsTab({ leadId }: { leadId: number }) {
  const [contracts, setContracts] = useState<any[]>([]);
  const [showContractModal, setShowContractModal] = useState(false);
  const [loading, setLoading] = useState(false);
  const [contractForm, setContractForm] = useState({
    title: '',
    type: 'sale'
  });

  useEffect(() => {
    loadContracts();
  }, [leadId]);

  const loadContracts = async () => {
    try {
      setLoading(true);
      const response = await http.get('/api/contracts') as any;
      const allContracts = response?.contracts || [];
      const leadContracts = allContracts.filter((contract: any) => contract.lead_id === leadId);
      setContracts(leadContracts);
    } catch (error) {
      console.error('Error loading contracts:', error);
      setContracts([]);
    } finally {
      setLoading(false);
    }
  };

  const handleCreateContract = async () => {
    try {
      if (!contractForm.title || !contractForm.type) {
        alert('נא למלא את כל השדות');
        return;
      }

      setLoading(true);
      const response = await http.post('/api/contracts', {
        lead_id: leadId,
        type: contractForm.type,
        title: contractForm.title
      }) as any;

      if (response.success) {
        alert(`חוזה נוצר בהצלחה! מספר: ${response.contract_id}`);
        setShowContractModal(false);
        setContractForm({ title: '', type: 'sale' });
        loadContracts();
      } else {
        alert('שגיאה ביצירת החוזה');
      }
    } catch (error) {
      console.error('Error creating contract:', error);
      alert('שגיאה ביצירת החוזה');
    } finally {
      setLoading(false);
    }
  };

  const getContractTypeLabel = (type: string) => {
    const types: Record<string, string> = {
      'sale': 'מכר',
      'rent': 'שכירות',
      'mediation': 'תיווך',
      'management': 'ניהול',
      'custom': 'מותאם אישית'
    };
    return types[type] || type;
  };

  return (
    <Card className="p-4 sm:p-6">
      <div className="flex items-center justify-between mb-4">
        <h3 className="text-lg font-medium text-gray-900">חוזים ומסמכים</h3>
        <Button 
          size="sm" 
          className="bg-green-600 hover:bg-green-700 text-white" 
          data-testid="button-create-contract"
          onClick={() => setShowContractModal(true)}
        >
          <Plus className="w-4 h-4 ml-2" />
          חוזה חדש
        </Button>
      </div>
      
      {showContractModal && (
        <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50" data-testid="contract-modal">
          <Card className="w-full max-w-md mx-4">
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
              
              <div className="space-y-4">
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">כותרת החוזה</label>
                  <Input
                    type="text"
                    placeholder="לדוגמה: חוזה מכר דירה"
                    value={contractForm.title}
                    onChange={(e) => setContractForm({ ...contractForm, title: e.target.value })}
                    data-testid="input-contract-title"
                  />
                </div>
                
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">סוג החוזה</label>
                  <select
                    className="w-full p-2 border border-gray-300 rounded-md"
                    value={contractForm.type}
                    onChange={(e) => setContractForm({ ...contractForm, type: e.target.value })}
                    data-testid="select-contract-type"
                  >
                    <option value="sale">מכר</option>
                    <option value="rent">שכירות</option>
                    <option value="mediation">תיווך</option>
                    <option value="management">ניהול</option>
                    <option value="custom">מותאם אישית</option>
                  </select>
                </div>
                
                <div className="flex gap-2 pt-4">
                  <Button
                    onClick={handleCreateContract}
                    disabled={loading}
                    className="flex-1"
                    data-testid="button-submit-contract"
                  >
                    {loading ? 'יוצר...' : 'צור חוזה'}
                  </Button>
                  <Button
                    variant="secondary"
                    onClick={() => setShowContractModal(false)}
                    className="flex-1"
                  >
                    ביטול
                  </Button>
                </div>
              </div>
            </div>
          </Card>
        </div>
      )}

      {loading && contracts.length === 0 ? (
        <div className="text-center py-8">
          <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-blue-600 mx-auto mb-4"></div>
          <p className="text-sm text-gray-500">טוען חוזים...</p>
        </div>
      ) : contracts.length === 0 ? (
        <div className="text-center py-8">
          <Tag className="w-12 h-12 text-gray-300 mx-auto mb-4" />
          <p className="text-sm text-gray-500 mb-4">אין חוזים עדיין</p>
        </div>
      ) : (
        <div className="space-y-3">
          {contracts.map((contract) => (
            <div key={contract.id} className="p-4 bg-gray-50 rounded-lg" data-testid={`contract-${contract.id}`}>
              <div className="flex justify-between items-start mb-2">
                <div>
                  <p className="text-sm font-medium text-gray-900">{contract.title}</p>
                  <p className="text-xs text-gray-500">מספר: {contract.id}</p>
                </div>
                <Badge className="bg-blue-100 text-blue-800">
                  {getContractTypeLabel(contract.type)}
                </Badge>
              </div>
              <div className="flex justify-between items-center text-xs text-gray-500">
                <span>{formatDate(contract.created_at)}</span>
                <Badge className={contract.status === 'active' ? 'bg-green-100 text-green-800' : 'bg-gray-100 text-gray-800'}>
                  {contract.status === 'active' ? 'פעיל' : contract.status}
                </Badge>
              </div>
            </div>
          ))}
        </div>
      )}
    </Card>
  );
}

function ActivityTab({ activities }: { activities: LeadActivity[] }) {
  const getActivityInfo = (activity: LeadActivity) => {
    const typeMap: Record<string, { label: string; icon: typeof Activity; color: string; bgColor: string }> = {
      'status_change': { label: 'שינוי סטטוס', icon: Activity, color: 'text-white', bgColor: 'bg-purple-500' },
      'call': { label: 'שיחת טלפון', icon: Phone, color: 'text-white', bgColor: 'bg-blue-500' },
      'call_incoming': { label: 'שיחה נכנסת', icon: Phone, color: 'text-white', bgColor: 'bg-green-500' },
      'call_outgoing': { label: 'שיחה יוצאת', icon: Phone, color: 'text-white', bgColor: 'bg-blue-500' },
      'whatsapp': { label: 'הודעת וואטסאפ', icon: MessageSquare, color: 'text-white', bgColor: 'bg-green-600' },
      'whatsapp_in': { label: 'הודעה נכנסת', icon: MessageSquare, color: 'text-white', bgColor: 'bg-green-600' },
      'whatsapp_out': { label: 'הודעה יוצאת', icon: MessageSquare, color: 'text-white', bgColor: 'bg-green-500' },
      'appointment': { label: 'פגישה', icon: Calendar, color: 'text-white', bgColor: 'bg-indigo-500' },
      'reminder': { label: 'משימה', icon: CheckCircle2, color: 'text-white', bgColor: 'bg-yellow-500' },
      'note': { label: 'הערה', icon: Activity, color: 'text-white', bgColor: 'bg-gray-500' },
      'created': { label: 'ליד נוצר', icon: User, color: 'text-white', bgColor: 'bg-emerald-500' },
      'email': { label: 'אימייל', icon: Mail, color: 'text-white', bgColor: 'bg-red-500' },
    };
    return typeMap[activity.type] || { label: activity.type, icon: Activity, color: 'text-white', bgColor: 'bg-gray-500' };
  };

  const getActivityDescription = (activity: LeadActivity) => {
    const payload = activity.payload || {};
    
    if (activity.type === 'status_change') {
      return `סטטוס שונה מ"${payload.from || 'לא ידוע'}" ל"${payload.to || 'לא ידוע'}"`;
    }
    if (activity.type === 'call' || activity.type === 'call_incoming' || activity.type === 'call_outgoing') {
      const duration = payload.duration ? ` (${payload.duration} שניות)` : '';
      return `${payload.summary || 'שיחה התבצעה'}${duration}`;
    }
    if (activity.type === 'whatsapp' || activity.type === 'whatsapp_in' || activity.type === 'whatsapp_out') {
      return payload.message?.substring(0, 100) || 'הודעה נשלחה/התקבלה';
    }
    if (activity.type === 'appointment') {
      return payload.title || 'פגישה נקבעה';
    }
    if (activity.type === 'reminder') {
      return payload.note || 'משימה נוספה';
    }
    if (activity.type === 'created') {
      return `ליד נוסף למערכת מ${payload.source || 'מקור לא ידוע'}`;
    }
    
    return payload.message || payload.note || payload.description || 'פעילות';
  };

  return (
    <Card className="p-4 sm:p-6">
      <h3 className="text-lg font-medium text-gray-900 mb-4">פעילות אחרונה</h3>
      {activities.length === 0 ? (
        <div className="text-center py-8">
          <Activity className="w-12 h-12 text-gray-300 mx-auto mb-4" />
          <p className="text-sm text-gray-500 mb-2">אין פעילות עדיין</p>
          <p className="text-xs text-gray-400">פעילויות כמו שיחות, הודעות ושינויי סטטוס יופיעו כאן</p>
        </div>
      ) : (
        <div className="flow-root">
          <ul className="-mb-8">
            {activities.map((activity, activityIdx) => {
              const info = getActivityInfo(activity);
              const IconComponent = info.icon;
              return (
                <li key={activity.id} data-testid={`activity-${activity.id}`}>
                  <div className="relative pb-8">
                    {activityIdx !== activities.length - 1 ? (
                      <span className="absolute top-4 right-4 -mr-px h-full w-0.5 bg-gray-200" aria-hidden="true" />
                    ) : null}
                    <div className="relative flex gap-3">
                      <div>
                        <span className={`h-8 w-8 rounded-full ${info.bgColor} flex items-center justify-center ring-4 ring-white`}>
                          <IconComponent className={`w-4 h-4 ${info.color}`} />
                        </span>
                      </div>
                      <div className="min-w-0 flex-1 pt-0.5">
                        <div className="flex items-center justify-between gap-2 mb-1">
                          <span className="text-sm font-medium text-gray-900">{info.label}</span>
                          <span className="text-xs text-gray-500 whitespace-nowrap">
                            {formatDate(activity.at)}
                          </span>
                        </div>
                        <p className="text-sm text-gray-600">
                          {getActivityDescription(activity)}
                        </p>
                      </div>
                    </div>
                  </div>
                </li>
              );
            })}
          </ul>
        </div>
      )}
    </Card>
  );
}