import React, { useState, useEffect, useCallback, useRef } from 'react';
import { useParams, useNavigate, useLocation } from 'react-router-dom';
import { ArrowLeft, Phone, Mail, MessageSquare, Clock, Activity, CheckCircle2, Circle, User, Tag, Calendar, Plus, Pencil, Save, X, Loader2, ChevronDown, Trash2, MapPin, FileText, Upload, Image as ImageIcon, File } from 'lucide-react';
import WhatsAppChat from './components/WhatsAppChat';
import { ReminderModal } from './components/ReminderModal';
import { Button } from '../../shared/components/ui/Button';
import { Card } from '../../shared/components/ui/Card';
import { Badge } from '../../shared/components/Badge';
import { Input } from '../../shared/components/ui/Input';
import { StatusDropdown } from '../../shared/components/ui/StatusDropdown';
import { AudioPlayer } from '../../shared/components/AudioPlayer';
import { LeadNavigationArrows } from '../../shared/components/LeadNavigationArrows';
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
  { key: 'email', label: 'מייל', icon: Mail },
  { key: 'appointments', label: 'פגישות', icon: Calendar },
  { key: 'reminders', label: 'משימות', icon: CheckCircle2 },
  { key: 'ai_notes', label: 'שירות לקוחות AI', icon: Phone },  // AI-generated call summaries for customer service
  { key: 'notes', label: 'הערות חופשיות', icon: FileText },  // Manual free-text notes
] as const;

type TabKey = typeof TABS[number]['key'];

export default function LeadDetailPage({}: LeadDetailPageProps) {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const location = useLocation();
  const searchParams = new URLSearchParams(location.search);
  const fromParam = searchParams.get('from');

  const handleBack = useCallback(() => {
    const fromToPath: Record<string, string> = {
      outbound_calls: '/app/outbound-calls',
      inbound_calls: '/app/calls',
      recent_calls: '/app/calls',
      whatsapp: '/app/whatsapp',
      leads: '/app/leads',
      // Legacy support
      outbound: '/app/outbound-calls',
      inbound: '/app/calls',
    };
    const target = fromParam ? fromToPath[fromParam] : undefined;
    if (target) {
      // Preserve tab and filters when going back
      const backParams = new URLSearchParams();
      
      // Preserve tab
      const tab = searchParams.get('tab');
      if (tab) backParams.set('tab', tab);
      
      // Preserve filters
      const filterStatus = searchParams.get('filterStatus');
      const filterSource = searchParams.get('filterSource');
      const filterDirection = searchParams.get('filterDirection');
      const filterOutboundList = searchParams.get('filterOutboundList');
      const filterSearch = searchParams.get('filterSearch');
      const filterDateFrom = searchParams.get('filterDateFrom');
      const filterDateTo = searchParams.get('filterDateTo');
      const filterStatuses = searchParams.get('filterStatuses');
      
      if (filterStatus) backParams.set('filterStatus', filterStatus);
      if (filterSource) backParams.set('filterSource', filterSource);
      if (filterDirection) backParams.set('filterDirection', filterDirection);
      if (filterOutboundList) backParams.set('filterOutboundList', filterOutboundList);
      if (filterSearch) backParams.set('filterSearch', filterSearch);
      if (filterDateFrom) backParams.set('filterDateFrom', filterDateFrom);
      if (filterDateTo) backParams.set('filterDateTo', filterDateTo);
      if (filterStatuses) backParams.set('filterStatuses', filterStatuses);
      
      const targetUrl = backParams.toString() ? `${target}?${backParams.toString()}` : target;
      navigate(targetUrl);
      return;
    }
    // Prefer browser back if we have history, otherwise fallback to leads list
    if (window.history.length > 1) {
      navigate(-1);
      return;
    }
    navigate('/app/leads');
  }, [fromParam, navigate, location.search]);
  
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
    email: '',
    gender: ''  // 'male', 'female', or empty
  });
  
  // Status management - use shared hook for consistent statuses
  const { statuses, refreshStatuses } = useStatuses();
  
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
      fetchCalls(id);
      fetchAppointments(id);
    } catch (err) {
      console.error('Failed to fetch lead:', err);
      setError('שגיאה בטעינת פרטי הליד');
      setLoading(false);
    }
  };

  const fetchCalls = async (leadId: string) => {
    try {
      setLoadingCalls(true);
      // Use lead_id filter for more accurate results
      const response = await http.get<{ success: boolean; calls: any[] }>(`/api/calls?lead_id=${leadId}`);
      if (response.success && response.calls) {
        const leadCalls: LeadCall[] = response.calls.map((call: any) => ({
          id: call.call_sid || call.sid || call.id,  // Use call_sid as primary id
          call_sid: call.call_sid || call.sid,  // Store explicit call_sid
          lead_id: parseInt(leadId),
          call_type: (call.direction === 'inbound' ? 'incoming' : 'outgoing') as 'incoming' | 'outgoing',
          duration: call.duration || 0,
          recording_url: call.recording_url,
          // 🔥 FIX: Use final_transcript (high-quality Whisper) first, fallback to transcription (realtime)
          notes: call.final_transcript || call.transcript || call.transcription || '',
          summary: call.summary || '',
          created_at: call.created_at || call.at,
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

  const fetchAppointments = async (leadId: string) => {
    try {
      setLoadingAppointments(true);
      const response = await http.get<{ appointments: any[] }>(`/api/calendar/appointments?lead_id=${leadId}`);
      if (response.appointments) {
        const leadAppointments: LeadAppointment[] = response.appointments.map((appt: any) => ({
          id: appt.id,
          title: appt.title || '',
          description: appt.description || '',
          start_time: appt.start_time,
          end_time: appt.end_time,
          location: appt.location || '',
          status: appt.status || 'scheduled',
          appointment_type: appt.appointment_type || 'meeting',
          priority: appt.priority || 'medium',
          contact_name: appt.contact_name || '',
          contact_phone: appt.contact_phone || '',
          notes: appt.notes || '',
          call_summary: appt.call_summary || ''
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
        email: lead.email || '',
        gender: lead.gender || ''
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
      email: '',
      gender: ''
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
    
    try {
      await http.post(`/api/leads/${lead.id}/status`, { status: newStatus });
      setLead({ ...lead, status: newStatus });
    } catch (err) {
      console.error('Failed to update status:', err);
      throw err; // Re-throw so StatusDropdown can handle it
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
          <Button onClick={handleBack} variant="secondary">
            חזור לרשימת הלידים
          </Button>
        </div>
      </div>
    );
  }


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
                onClick={handleBack}
                className="mr-4"
                data-testid="button-back"
              >
                <ArrowLeft className="w-4 h-4 mr-2" />
                חזור לרשימת הלידים
              </Button>
              <div>
                <h1 className="text-xl font-semibold text-gray-900 flex items-center gap-2" data-testid="text-lead-name">
                  {lead.full_name || `${lead.first_name || ''} ${lead.last_name || ''}`.trim() || 'ללא שם'}
                  {/* Desktop navigation arrows */}
                  <LeadNavigationArrows currentLeadId={parseInt(id!)} variant="desktop" />
                </h1>
                <p className="text-sm text-gray-500" data-testid="text-lead-phone">
                  {lead.phone_e164}
                </p>
              </div>
            </div>
            <div className="flex items-center space-x-3">
              <StatusDropdown
                currentStatus={lead.status}
                statuses={statuses}
                onStatusChange={updateLeadStatus}
                data-testid="status-dropdown"
              />
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
                onClick={handleBack}
                data-testid="button-back-mobile"
              >
                <ArrowLeft className="w-4 h-4 mr-2" />
                חזור
              </Button>
              <StatusDropdown
                currentStatus={lead.status}
                statuses={statuses}
                onStatusChange={updateLeadStatus}
                size="sm"
                data-testid="status-dropdown-mobile"
              />
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
        {activeTab === 'calls' && <CallsTab calls={calls} loading={loadingCalls} leadId={parseInt(id!)} onRefresh={fetchLead} />}
        {activeTab === 'email' && <EmailTab lead={lead} />}
        {activeTab === 'appointments' && <AppointmentsTab appointments={appointments} loading={loadingAppointments} lead={lead} onRefresh={fetchLead} />}
        {activeTab === 'reminders' && <RemindersTab reminders={reminders} onOpenReminder={() => { setEditingReminder(null); setReminderModalOpen(true); }} onEditReminder={(reminder) => { setEditingReminder(reminder); setReminderModalOpen(true); }} leadId={parseInt(id!)} onRefresh={fetchLead} />}
        {activeTab === 'ai_notes' && <AINotesTab lead={lead} onUpdate={fetchLead} />}
        {activeTab === 'notes' && <NotesTab lead={lead} onUpdate={fetchLead} />}
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
      
      {/* Mobile navigation arrows - floating in bottom-right */}
      <div className="sm:hidden">
        <LeadNavigationArrows currentLeadId={parseInt(id!)} variant="mobile" />
      </div>
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
  const navigate = useNavigate();

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
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">מין</label>
                <select
                  value={editForm.gender}
                  onChange={(e) => setEditForm(prev => ({ ...prev, gender: e.target.value }))}
                  className="w-full px-3 py-2 border border-gray-300 rounded-md shadow-sm focus:outline-none focus:ring-blue-500 focus:border-blue-500"
                  data-testid="select-gender"
                >
                  <option value="">לא ידוע</option>
                  <option value="male">זכר</option>
                  <option value="female">נקבה</option>
                </select>
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
                  <label className="block text-sm font-medium text-gray-700 mb-1">מין</label>
                  <p className="text-sm text-gray-900">
                    {lead.gender === 'male' ? 'זכר' : lead.gender === 'female' ? 'נקבה' : 'לא ידוע'}
                  </p>
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

              {/* Quick navigation tiles */}
              <div className="mt-6">
                <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
                  <button
                    type="button"
                    onClick={() => navigate('/app/whatsapp')}
                    className="text-right rounded-lg border border-gray-200 bg-white p-4 hover:bg-gray-50 transition-colors"
                    data-testid="tile-whatsapp"
                  >
                    <div className="flex items-center gap-2 mb-1">
                      <MessageSquare className="w-4 h-4 text-green-600" />
                      <span className="font-medium text-gray-900">WhatsApp</span>
                    </div>
                    <p className="text-sm text-gray-500">פתח/י שיחות לפי ליד</p>
                  </button>

                  <button
                    type="button"
                    onClick={() => navigate('/app/calls')}
                    className="text-right rounded-lg border border-gray-200 bg-white p-4 hover:bg-gray-50 transition-colors"
                    data-testid="tile-inbound-calls"
                  >
                    <div className="flex items-center gap-2 mb-1">
                      <Phone className="w-4 h-4 text-green-600" />
                      <span className="font-medium text-gray-900">שיחות נכנסות</span>
                    </div>
                    <p className="text-sm text-gray-500">מעבר לליסט השיחות הנכנסות</p>
                  </button>

                  <button
                    type="button"
                    onClick={() => navigate('/app/outbound-calls')}
                    className="text-right rounded-lg border border-gray-200 bg-white p-4 hover:bg-gray-50 transition-colors"
                    data-testid="tile-outbound-calls"
                  >
                    <div className="flex items-center gap-2 mb-1">
                      <Phone className="w-4 h-4 text-blue-600" />
                      <span className="font-medium text-gray-900">שיחות יוצאות</span>
                    </div>
                    <p className="text-sm text-gray-500">מעבר לליסט השיחות היוצאות</p>
                  </button>
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

function CallsTab({ calls, loading, leadId, onRefresh }: { calls: LeadCall[]; loading?: boolean; leadId: number; onRefresh: () => void }) {
  const [expandedCallId, setExpandedCallId] = useState<string | null>(null);
  const [deleting, setDeleting] = useState<string | null>(null);
  const [directionFilter, setDirectionFilter] = useState<'all' | 'incoming' | 'outgoing'>('all');  // 🔥 NEW: Direction filter
  const [recordingUrls, setRecordingUrls] = useState<Record<string, string>>({});  // 🔥 FIX: Store blob URLs for authenticated audio playback
  const [loadingRecording, setLoadingRecording] = useState<string | null>(null);  // 🔥 FIX: Track which recording is loading
  const recordingUrlsRef = useRef<Record<string, string>>({});  // 🔥 FIX: Track URLs for cleanup

  // Helper to get consistent call identifier
  const getCallId = (call: LeadCall) => call.call_sid || call.id;

  const formatDuration = (seconds: number) => {
    if (seconds < 60) return `${seconds} שניות`;
    const minutes = Math.floor(seconds / 60);
    const remainingSeconds = seconds % 60;
    return `${minutes}:${remainingSeconds.toString().padStart(2, '0')} דקות`;
  };

  // 🔥 FIX: Load recording as blob with authentication when call is expanded
  const loadRecordingBlob = async (callId: string) => {
    // Skip if already loaded or currently loading (check ref for source of truth)
    if (recordingUrlsRef.current[callId] || loadingRecording === callId) return;
    
    setLoadingRecording(callId);
    try {
      const response = await fetch(`/api/calls/${callId}/download`, {
        method: 'GET',
        credentials: 'include'
      });
      
      if (!response.ok) {
        throw new Error('Failed to load recording');
      }
      
      const blob = await response.blob();
      const url = window.URL.createObjectURL(blob);
      recordingUrlsRef.current[callId] = url;  // Track in ref for cleanup
      setRecordingUrls(prev => ({ ...prev, [callId]: url }));
    } catch (error) {
      console.error('Error loading recording:', error);
      // Don't set URL in ref on error - allow retry
    } finally {
      setLoadingRecording(null);
    }
  };

  // 🔥 FIX: Cleanup blob URLs when component unmounts
  useEffect(() => {
    return () => {
      // Revoke all blob URLs to prevent memory leaks
      Object.values(recordingUrlsRef.current).forEach(url => {
        window.URL.revokeObjectURL(url);
      });
    };
  }, []); // Only run on mount/unmount

  // 🔥 FIX: Load recording when call is expanded
  const handleToggleExpand = (callId: string, hasRecording: boolean) => {
    const isExpanding = expandedCallId !== callId;
    setExpandedCallId(isExpanding ? callId : null);
    
    // Load recording blob when expanding
    if (isExpanding && hasRecording) {
      loadRecordingBlob(callId);
    }
  };

  // 🔥 NEW: Filter calls by direction
  const filteredCalls = directionFilter === 'all' 
    ? calls 
    : calls.filter(call => call.call_type === directionFilter);

  const handleDownload = async (callId: string) => {
    try {
      // Use the download endpoint with proper auth
      const response = await fetch(`/api/calls/${callId}/download`, {
        method: 'GET',
        credentials: 'include'
      });
      
      if (!response.ok) {
        throw new Error('Failed to download recording');
      }
      
      const blob = await response.blob();
      const url = window.URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = `recording-${callId}.mp3`;
      document.body.appendChild(a);
      a.click();
      window.URL.revokeObjectURL(url);
      document.body.removeChild(a);
    } catch (error) {
      console.error('Error downloading recording:', error);
      alert('שגיאה בהורדת ההקלטה');
    }
  };

  const handleDeleteCall = async (callId: string) => {
    if (!confirm('האם אתה בטוח שברצונך למחוק שיחה זו? פעולה זו תמחק גם את ההקלטה והתמליל.')) return;
    
    try {
      setDeleting(callId);
      await http.delete(`/api/calls/${callId}`);
      onRefresh();
      alert('השיחה נמחקה בהצלחה');
    } catch (err) {
      console.error('Failed to delete call:', err);
      alert('שגיאה במחיקת השיחה');
    } finally {
      setDeleting(null);
    }
  };

  return (
    <Card className="p-4 sm:p-6">
      <div className="flex items-center justify-between mb-4">
        <h3 className="text-lg font-medium text-gray-900">היסטוריית שיחות טלפון</h3>
        
        {/* 🔥 NEW: Direction Filter */}
        <div className="flex items-center gap-2">
          <label className="text-sm text-gray-600">סנן לפי:</label>
          <select
            value={directionFilter}
            onChange={(e) => setDirectionFilter(e.target.value as 'all' | 'incoming' | 'outgoing')}
            className="px-3 py-1.5 text-sm border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
            data-testid="filter-call-direction"
          >
            <option value="all">כל השיחות</option>
            <option value="incoming">שיחות נכנסות</option>
            <option value="outgoing">שיחות יוצאות</option>
          </select>
        </div>
      </div>
      
      {loading ? (
        <div className="flex items-center justify-center py-8">
          <Loader2 className="w-6 h-6 animate-spin text-gray-400" />
          <span className="text-sm text-gray-500 mr-2">טוען שיחות...</span>
        </div>
      ) : filteredCalls.length === 0 ? (
        <div className="text-center py-8">
          <Phone className="w-12 h-12 text-gray-300 mx-auto mb-3" />
          <p className="text-sm text-gray-500">
            {directionFilter === 'all' 
              ? 'אין שיחות טלפון עדיין'
              : directionFilter === 'incoming'
              ? 'אין שיחות נכנסות'
              : 'אין שיחות יוצאות'
            }
          </p>
        </div>
      ) : (
        <div className="space-y-3">
          {filteredCalls.map((call) => {
            const callId = getCallId(call);
            const isExpanded = expandedCallId === callId;
            const hasRecording = Boolean(call.recording_url);
            const hasTranscript = Boolean(call.notes?.trim());
            const hasSummary = Boolean(call.summary?.trim());

            return (
              <div key={call.id} className="border border-gray-200 rounded-lg overflow-hidden" data-testid={`call-${call.id}`}>
                {/* Call Header - Clickable */}
                <div 
                  className="p-4 bg-gray-50 hover:bg-gray-100 transition-colors cursor-pointer"
                  onClick={() => handleToggleExpand(callId, hasRecording)}
                  role="button"
                  tabIndex={0}
                  aria-expanded={isExpanded}
                  aria-label={`שיחה ${call.call_type === 'incoming' ? 'נכנסת' : 'יוצאת'} מתאריך ${formatDate(call.created_at)}`}
                  onKeyDown={(e) => {
                    if (e.key === 'Enter' || e.key === ' ') {
                      e.preventDefault();
                      handleToggleExpand(callId, hasRecording);
                    }
                  }}
                >
                  <div className="flex items-center justify-between">
                    <div className="flex items-center gap-3 flex-1">
                      <div className={`p-2 rounded-full ${call.call_type === 'incoming' ? 'bg-green-100' : 'bg-blue-100'}`}>
                        <Phone className={`w-4 h-4 ${call.call_type === 'incoming' ? 'text-green-600' : 'text-blue-600'}`} />
                      </div>
                      <div className="flex-1">
                        <p className="text-sm font-medium text-gray-900">
                          {call.call_type === 'incoming' ? 'שיחה נכנסת' : 'שיחה יוצאת'}
                        </p>
                        <p className="text-xs text-gray-500">{formatDate(call.created_at)}</p>
                      </div>
                      <div className="text-left">
                        <p className="text-sm font-medium text-gray-700">{formatDuration(call.duration)}</p>
                        <div className="flex gap-1 mt-1 flex-wrap">
                          <span className={`text-xs px-2 py-0.5 rounded font-medium ${hasRecording ? 'bg-blue-100 text-blue-700' : 'bg-gray-100 text-gray-400'}`}>
                            🎧 הקלטה
                          </span>
                          <span className={`text-xs px-2 py-0.5 rounded font-medium ${hasTranscript ? 'bg-purple-100 text-purple-700' : 'bg-gray-100 text-gray-400'}`}>
                            📝 תמליל
                          </span>
                          <span className={`text-xs px-2 py-0.5 rounded font-medium ${hasSummary ? 'bg-green-100 text-green-700' : 'bg-gray-100 text-gray-400'}`}>
                            📋 סיכום
                          </span>
                        </div>
                        {(hasRecording || hasTranscript || hasSummary) && (
                          <p className="text-xs text-blue-600 mt-1 font-medium">
                            👆 לחץ להצגה
                          </p>
                        )}
                      </div>
                    </div>
                    <div className="flex items-center gap-2 flex-shrink-0">
                      <button
                        onClick={(e) => {
                          e.stopPropagation();
                          handleDeleteCall(getCallId(call));
                        }}
                        disabled={deleting === getCallId(call)}
                        className="p-2 hover:bg-red-100 rounded-full transition-colors touch-manipulation"
                        data-testid={`button-delete-call-${call.id}`}
                        title="מחק שיחה"
                        aria-label="מחק שיחה"
                      >
                        {deleting === getCallId(call) ? (
                          <Loader2 className="w-4 h-4 animate-spin text-red-500" />
                        ) : (
                          <Trash2 className="w-4 h-4 text-red-500" />
                        )}
                      </button>
                      <button
                        onClick={() => handleToggleExpand(callId, hasRecording)}
                        className="p-2 sm:p-2.5 hover:bg-blue-100 active:bg-blue-200 rounded-full transition-colors touch-manipulation min-w-[40px] min-h-[40px] flex items-center justify-center"
                        data-testid={`button-expand-call-${call.id}`}
                        title={isExpanded ? 'סגור פרטים' : 'הצג הקלטה, תמליל וסיכום'}
                        aria-label={isExpanded ? 'סגור פרטים' : 'הצג הקלטה, תמליל וסיכום'}
                        aria-expanded={isExpanded}
                      >
                        <ChevronDown className={`w-5 h-5 sm:w-4 sm:h-4 text-blue-600 transition-transform ${isExpanded ? 'rotate-180' : ''}`} />
                      </button>
                    </div>
                  </div>
                </div>

                {/* Expanded Details */}
                {isExpanded && (
                  <div className="p-4 space-y-4 bg-white border-t border-gray-200">
                    {/* Recording Player */}
                    {hasRecording ? (
                      <div className="space-y-2">
                        <div className="flex items-center justify-between">
                          <p className="text-sm font-medium text-gray-700">הקלטת שיחה</p>
                          <button
                            onClick={() => handleDownload(getCallId(call))}
                            className="text-xs text-blue-600 hover:text-blue-700 flex items-center gap-1"
                          >
                            <svg className="w-3 h-3" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-4l-4 4m0 0l-4-4m4 4V4" />
                            </svg>
                            הורד
                          </button>
                        </div>
                        {/* Audio Player with playback speed controls */}
                        {recordingUrls[getCallId(call)] ? (
                          <AudioPlayer
                            src={recordingUrls[getCallId(call)]}
                            loading={loadingRecording === getCallId(call)}
                          />
                        ) : loadingRecording === getCallId(call) ? (
                          <div className="flex items-center justify-center py-4">
                            <Loader2 className="w-5 h-5 animate-spin text-blue-500" />
                            <span className="text-sm text-gray-500 mr-2">טוען הקלטה...</span>
                          </div>
                        ) : (
                          <div className="p-3 bg-yellow-50 border border-yellow-200 rounded-lg">
                            <p className="text-sm text-yellow-800">שגיאה בטעינת ההקלטה</p>
                          </div>
                        )}
                      </div>
                    ) : (
                      <div className="p-3 bg-yellow-50 border border-yellow-200 rounded-lg">
                        <p className="text-sm text-yellow-800">הקלטה לא זמינה</p>
                      </div>
                    )}

                    {/* Summary - Always visible when expanded if exists */}
                    {hasSummary ? (
                      <div className="p-4 bg-blue-50 rounded-lg border border-blue-200">
                        <p className="text-sm font-semibold text-blue-900 mb-2">סיכום שיחה</p>
                        <p className="text-sm text-blue-800 whitespace-pre-wrap">{call.summary}</p>
                      </div>
                    ) : (
                      <div className="p-3 bg-gray-50 border border-gray-200 rounded-lg">
                        <p className="text-sm text-gray-600">אין סיכום שיחה</p>
                      </div>
                    )}

                    {/* Transcript - Always visible when expanded if exists */}
                    {hasTranscript ? (
                      <div>
                        <details className="group" open>
                          <summary className="cursor-pointer text-sm font-semibold text-gray-900 hover:text-gray-700 flex items-center gap-2 mb-2">
                            <ChevronDown className="w-4 h-4 group-open:rotate-180 transition-transform" />
                            תמליל מלא
                          </summary>
                          <div className="mt-2 p-4 bg-gray-50 rounded-lg border border-gray-200">
                            <p className="text-sm text-gray-700 whitespace-pre-wrap">{call.notes}</p>
                          </div>
                        </details>
                      </div>
                    ) : (
                      <div className="p-3 bg-gray-50 border border-gray-200 rounded-lg">
                        <p className="text-sm text-gray-600">אין תמליל</p>
                      </div>
                    )}
                  </div>
                )}
              </div>
            );
          })}
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

const STATUS_TYPES = {
  scheduled: { label: 'מתוכנן', color: 'bg-gray-100 text-gray-800' },
  confirmed: { label: 'מאושר', color: 'bg-blue-100 text-blue-800' },
  paid: { label: 'שילם', color: 'bg-green-100 text-green-800' },
  unpaid: { label: 'לא שילם', color: 'bg-yellow-100 text-yellow-800' },
  cancelled: { label: 'בוטל', color: 'bg-red-100 text-red-800' }
};

interface AppointmentFormData {
  title: string;
  appointment_type: string;
  start_time: string;
  end_time: string;
  status: string;
  location: string;
  contact_name: string;
  contact_phone: string;
}

function AppointmentsTab({ appointments, loading, lead, onRefresh }: { appointments: LeadAppointment[]; loading?: boolean; lead?: Lead; onRefresh?: () => void }) {
  const [showModal, setShowModal] = useState(false);
  const [editingAppointment, setEditingAppointment] = useState<LeadAppointment | null>(null);
  const [saving, setSaving] = useState(false);
  const [deleting, setDeleting] = useState<number | null>(null);
  const [formData, setFormData] = useState<AppointmentFormData>({
    title: '',
    appointment_type: 'meeting',
    start_time: '',
    end_time: '',
    status: 'scheduled',
    location: '',
    contact_name: '',
    contact_phone: ''
  });

  const formatDateTime = (dateStr: string) => {
    // 🔥 FIX: Use timeZone: 'Asia/Jerusalem' directly - it handles the offset automatically
    // No manual +2 hours needed! That causes double offset when combined with timeZone setting
    const date = new Date(dateStr);
    return date.toLocaleString('he-IL', {
      weekday: 'short',
      day: 'numeric',
      month: 'short',
      hour: '2-digit',
      minute: '2-digit',
      timeZone: 'Asia/Jerusalem'
    });
  };

  const formatDatetimeLocal = (isoString: string) => {
    if (!isoString) return '';
    
    // 🔥 FIX: Parse the datetime string without timezone conversion
    // The server sends Israel time with timezone info (e.g., "2024-01-15T14:00:00+02:00")
    // We need to extract the date and time parts directly without letting JavaScript
    // convert to browser's local timezone
    
    // Remove timezone info and milliseconds, parse the date/time parts directly
    const dateTimePart = isoString.split('+')[0].split('Z')[0].split('.')[0];
    
    // If the string contains 'T', it's in ISO format
    if (dateTimePart.includes('T')) {
      const [datePart, timePart] = dateTimePart.split('T');
      const [hours, minutes] = timePart.split(':');
      // Return in datetime-local format (YYYY-MM-DDTHH:MM)
      return `${datePart}T${hours}:${minutes}`;
    }
    
    // Fallback to original behavior if format is unexpected
    const date = new Date(isoString);
    const year = date.getFullYear();
    const month = String(date.getMonth() + 1).padStart(2, '0');
    const day = String(date.getDate()).padStart(2, '0');
    const hours = String(date.getHours()).padStart(2, '0');
    const minutes = String(date.getMinutes()).padStart(2, '0');
    return `${year}-${month}-${day}T${hours}:${minutes}`;
  };

  // Helper to format current local time for datetime-local input
  const formatCurrentLocalTime = (date: Date) => {
    const year = date.getFullYear();
    const month = String(date.getMonth() + 1).padStart(2, '0');
    const day = String(date.getDate()).padStart(2, '0');
    const hours = String(date.getHours()).padStart(2, '0');
    const minutes = String(date.getMinutes()).padStart(2, '0');
    return `${year}-${month}-${day}T${hours}:${minutes}`;
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

  const handleSaveAppointment = async () => {
    if (!formData.title || !formData.start_time || !formData.end_time) {
      alert('נא למלא כותרת, תאריך התחלה ותאריך סיום');
      return;
    }

    try {
      setSaving(true);
      
      // 🔥 FIX: Convert datetime-local values WITHOUT timezone conversion
      // The datetime-local input is already in local Israel time
      const dataToSend = {
        title: formData.title,
        appointment_type: formData.appointment_type,
        start_time: formData.start_time ? `${formData.start_time}:00` : formData.start_time,
        end_time: formData.end_time ? `${formData.end_time}:00` : formData.end_time,
        status: formData.status,
        location: formData.location,
        contact_name: formData.contact_name || (lead ? `${lead.first_name || ''} ${lead.last_name || ''}`.trim() : ''),
        contact_phone: formData.contact_phone || lead?.phone_e164 || '',
        priority: 'medium',
        // 🔥 FIX: Include lead_id when creating from lead page
        lead_id: lead?.id
      };

      console.log('Saving appointment:', dataToSend);
      
      if (editingAppointment) {
        const result = await http.patch(`/api/calendar/appointments/${editingAppointment.id}`, dataToSend);
        console.log('Update result:', result);
      } else {
        const result = await http.post('/api/calendar/appointments', dataToSend);
        console.log('Create result:', result);
      }
      
      // Success feedback
      alert(editingAppointment ? 'הפגישה עודכנה בהצלחה!' : 'הפגישה נוצרה בהצלחה!');
      closeModal();
      onRefresh?.();
    } catch (err: any) {
      console.error('Error saving appointment:', err);
      const errorMsg = err?.error || err?.message || (editingAppointment ? 'שגיאה בעדכון הפגישה' : 'שגיאה ביצירת הפגישה');
      alert(`${errorMsg}. אנא נסה שוב או פנה לתמיכה.`);
    } finally {
      setSaving(false);
    }
  };

  const handleDeleteAppointment = async (appointmentId: number) => {
    if (!confirm('האם אתה בטוח שברצונך למחוק פגישה זו?')) return;
    
    try {
      setDeleting(appointmentId);
      console.log('Deleting appointment:', appointmentId);
      const result = await http.delete(`/api/calendar/appointments/${appointmentId}`);
      console.log('Delete result:', result);
      alert('הפגישה נמחקה בהצלחה!');
      onRefresh?.();
    } catch (err: any) {
      console.error('Error deleting appointment:', err);
      const errorMsg = err?.error || err?.message || 'שגיאה במחיקת הפגישה';
      alert(`${errorMsg}. אנא נסה שוב או פנה לתמיכה.`);
    } finally {
      setDeleting(null);
    }
  };

  const openNewAppointment = () => {
    const now = new Date();
    now.setMinutes(Math.ceil(now.getMinutes() / 30) * 30);
    const startTime = formatCurrentLocalTime(now);
    now.setHours(now.getHours() + 1);
    const endTime = formatCurrentLocalTime(now);
    
    setEditingAppointment(null);
    setFormData({
      title: lead ? `פגישה עם ${lead.first_name || ''} ${lead.last_name || ''}`.trim() : 'פגישה חדשה',
      appointment_type: 'meeting',
      start_time: startTime,
      end_time: endTime,
      status: 'scheduled',
      location: '',
      contact_name: lead ? `${lead.first_name || ''} ${lead.last_name || ''}`.trim() : '',
      contact_phone: lead?.phone_e164 || ''
    });
    setShowModal(true);
  };

  const openEditAppointment = (appointment: LeadAppointment) => {
    setEditingAppointment(appointment);
    setFormData({
      title: appointment.title,
      appointment_type: (appointment as any).appointment_type || 'meeting',
      start_time: formatDatetimeLocal(appointment.start_time),
      end_time: formatDatetimeLocal(appointment.end_time),
      status: appointment.status,
      location: (appointment as any).location || '',
      contact_name: appointment.contact_name || '',
      contact_phone: (appointment as any).contact_phone || ''
    });
    setShowModal(true);
  };

  const closeModal = () => {
    setShowModal(false);
    setEditingAppointment(null);
    setFormData({
      title: '',
      appointment_type: 'meeting',
      start_time: '',
      end_time: '',
      status: 'scheduled',
      location: '',
      contact_name: '',
      contact_phone: ''
    });
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
          <Card className="w-full max-w-lg mx-4 max-h-[90vh] overflow-y-auto">
            <div className="p-6">
              <div className="flex items-center justify-between mb-4">
                <h3 className="text-lg font-medium">
                  {editingAppointment ? 'עריכת פגישה' : 'תאם פגישה חדשה'}
                </h3>
                <Button variant="ghost" size="sm" onClick={closeModal} data-testid="button-close-appointment-modal">
                  <X className="w-4 h-4" />
                </Button>
              </div>
              
              <div className="space-y-4">
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">כותרת הפגישה</label>
                  <Input
                    value={formData.title}
                    onChange={(e) => setFormData({ ...formData, title: e.target.value })}
                    placeholder="נושא הפגישה"
                    data-testid="input-appointment-title"
                  />
                </div>
                
                <div className="grid grid-cols-2 gap-3">
                  <div>
                    <label className="block text-sm font-medium text-gray-700 mb-1">תאריך ושעת התחלה</label>
                    <Input
                      type="datetime-local"
                      value={formData.start_time}
                      onChange={(e) => setFormData({ ...formData, start_time: e.target.value })}
                      data-testid="input-appointment-start"
                    />
                  </div>
                  <div>
                    <label className="block text-sm font-medium text-gray-700 mb-1">תאריך ושעת סיום</label>
                    <Input
                      type="datetime-local"
                      value={formData.end_time}
                      onChange={(e) => setFormData({ ...formData, end_time: e.target.value })}
                      data-testid="input-appointment-end"
                    />
                  </div>
                </div>
                
                <div className="grid grid-cols-2 gap-3">
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
                  <div>
                    <label className="block text-sm font-medium text-gray-700 mb-1">סטטוס</label>
                    <select
                      className="w-full p-2 border border-gray-300 rounded-md"
                      value={formData.status}
                      onChange={(e) => setFormData({ ...formData, status: e.target.value })}
                      data-testid="select-appointment-status"
                    >
                      {Object.entries(STATUS_TYPES).map(([key, { label }]) => (
                        <option key={key} value={key}>{label}</option>
                      ))}
                    </select>
                  </div>
                </div>

                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">מיקום</label>
                  <Input
                    value={formData.location}
                    onChange={(e) => setFormData({ ...formData, location: e.target.value })}
                    placeholder="כתובת או מיקום הפגישה"
                    data-testid="input-appointment-location"
                  />
                </div>

                <div className="grid grid-cols-2 gap-3">
                  <div>
                    <label className="block text-sm font-medium text-gray-700 mb-1">שם איש קשר</label>
                    <Input
                      value={formData.contact_name}
                      onChange={(e) => setFormData({ ...formData, contact_name: e.target.value })}
                      placeholder="שם מלא"
                      data-testid="input-appointment-contact-name"
                    />
                  </div>
                  <div>
                    <label className="block text-sm font-medium text-gray-700 mb-1">טלפון איש קשר</label>
                    <Input
                      value={formData.contact_phone}
                      onChange={(e) => setFormData({ ...formData, contact_phone: e.target.value })}
                      placeholder="מספר טלפון"
                      data-testid="input-appointment-contact-phone"
                    />
                  </div>
                </div>
                
                <div className="flex gap-2 pt-2">
                  <Button onClick={handleSaveAppointment} disabled={saving} className="flex-1" data-testid="button-save-appointment">
                    {saving ? <Loader2 className="w-4 h-4 animate-spin ml-2" /> : null}
                    {saving ? 'שומר...' : (editingAppointment ? 'עדכן פגישה' : 'שמור פגישה')}
                  </Button>
                  <Button variant="secondary" onClick={closeModal} className="flex-1">
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
                  {(appointment as any).location && (
                    <p className="text-xs text-gray-500 flex items-center gap-1 mt-1">
                      <MapPin className="w-3 h-3" />
                      {(appointment as any).location}
                    </p>
                  )}
                </div>
                <div className="flex gap-2">
                  <Button
                    variant="ghost"
                    size="sm"
                    onClick={() => openEditAppointment(appointment)}
                    data-testid={`button-edit-appointment-${appointment.id}`}
                  >
                    <Pencil className="w-4 h-4 text-gray-600" />
                  </Button>
                  <Button
                    variant="ghost"
                    size="sm"
                    onClick={() => handleDeleteAppointment(appointment.id)}
                    disabled={deleting === appointment.id}
                    data-testid={`button-delete-appointment-${appointment.id}`}
                  >
                    {deleting === appointment.id ? (
                      <Loader2 className="w-4 h-4 animate-spin text-red-500" />
                    ) : (
                      <Trash2 className="w-4 h-4 text-red-500" />
                    )}
                  </Button>
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

function RemindersTab({ reminders, onOpenReminder, onEditReminder, leadId, onRefresh }: { reminders: LeadReminder[]; onOpenReminder: () => void; onEditReminder: (reminder: LeadReminder) => void; leadId: number; onRefresh: () => void }) {
  const [completing, setCompleting] = useState<number | null>(null);
  const [deleting, setDeleting] = useState<number | null>(null);

  const handleCompleteReminder = async (reminderId: number) => {
    try {
      setCompleting(reminderId);
      await http.patch(`/api/leads/${leadId}/reminders/${reminderId}`, {
        completed_at: new Date().toISOString()
      });
      onRefresh();
    } catch (err) {
      console.error('Failed to complete reminder:', err);
      alert('שגיאה בסימון התזכורת כהושלמה');
    } finally {
      setCompleting(null);
    }
  };

  const handleDeleteReminder = async (reminderId: number) => {
    if (!confirm('האם אתה בטוח שברצונך למחוק תזכורת זו?')) return;
    
    try {
      setDeleting(reminderId);
      await http.delete(`/api/leads/${leadId}/reminders/${reminderId}`);
      onRefresh();
    } catch (err) {
      console.error('Failed to delete reminder:', err);
      alert('שגיאה במחיקת התזכורת');
    } finally {
      setDeleting(null);
    }
  };

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
              <button
                onClick={() => !reminder.completed_at && handleCompleteReminder(reminder.id)}
                disabled={completing === reminder.id || !!reminder.completed_at}
                className="flex-shrink-0"
                data-testid={`button-complete-reminder-${reminder.id}`}
              >
                {completing === reminder.id ? (
                  <Loader2 className="w-5 h-5 animate-spin text-gray-400" />
                ) : reminder.completed_at ? (
                  <CheckCircle2 className="w-5 h-5 text-green-500" />
                ) : (
                  <Circle className="w-5 h-5 text-gray-400 hover:text-green-500 transition-colors cursor-pointer" />
                )}
              </button>
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
              <div className="flex gap-1">
                <button
                  onClick={() => onEditReminder(reminder)}
                  className="p-2 hover:bg-gray-200 rounded-lg transition-colors"
                  data-testid={`button-edit-reminder-${reminder.id}`}
                >
                  <Pencil className="w-4 h-4 text-gray-600" />
                </button>
                <button
                  onClick={() => handleDeleteReminder(reminder.id)}
                  disabled={deleting === reminder.id}
                  className="p-2 hover:bg-red-100 rounded-lg transition-colors"
                  data-testid={`button-delete-reminder-${reminder.id}`}
                >
                  {deleting === reminder.id ? (
                    <Loader2 className="w-4 h-4 animate-spin text-red-500" />
                  ) : (
                    <Trash2 className="w-4 h-4 text-red-500" />
                  )}
                </button>
              </div>
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

// ✅ AI Customer Service Notes Tab - Shows AI-generated call summaries only (no file uploads)
interface AINotesTabProps {
  lead: Lead;
  onUpdate: () => void;
}

function AINotesTab({ lead, onUpdate }: AINotesTabProps) {
  const [notes, setNotes] = useState<LeadNoteItem[]>([]);
  const [newNoteContent, setNewNoteContent] = useState('');
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [editingId, setEditingId] = useState<number | null>(null);
  const [editContent, setEditContent] = useState('');

  /**
   * Extracts the clean summary text from a formatted call_summary note.
   * 
   * The backend saves call_summary notes with format:
   * ```
   * 📞 סיכום לשירות לקוחות - DD/MM/YYYY HH:MM
   *
   * 💬 [actual summary text]
   * 🎯 [optional intent]
   * 📋 המשך: [optional next action]
   * 😊 סנטימנט: [optional sentiment]
   *
   * ⏱️ X שניות
   * ```
   * 
   * This function extracts only the line(s) starting with 💬, which contains
   * the actual summary text, removing all metadata and formatting.
   * 
   * @param content - The formatted call_summary note content
   * @returns The clean summary text without formatting. If no summary marker (💬) is found,
   *          returns the original content unchanged for backward compatibility with legacy data.
   * 
   * @example
   * // Input:
   * "📞 סיכום לשירות לקוחות - 18/01/2026 17:30\n\n💬 הלקוח ביקש פגישה למחר בשעה 10\n🎯 רוצה לקבוע פגישה\n\n⏱️ 120 שניות"
   * 
   * // Output:
   * "הלקוח ביקש פגישה למחר בשעה 10"
   */
  const extractCleanSummary = (content: string): string => {
    // Define metadata emoji prefixes used in the format
    const METADATA_EMOJIS = ['🎯', '📋', '😊', '😟', '⏱️', '📞'];
    
    // 🔥 FIX: Also exclude "תמלול:" lines (transcript snippets from old summaries)
    const TRANSCRIPT_PREFIX = 'תמלול:';
    
    // Split into lines and process
    const lines = content.split('\n');
    const summaryLines: string[] = [];
    let inSummaryBlock = false;
    
    for (const line of lines) {
      const trimmed = line.trim();
      
      // Start of summary block (line starts with 💬)
      if (trimmed.startsWith('💬 ')) {
        summaryLines.push(trimmed.substring(2).trim()); // Remove "💬 " prefix
        inSummaryBlock = true;
        continue;
      }
      
      // If we're in a summary block, continue adding lines until we hit another emoji prefix
      if (inSummaryBlock) {
        // 🔥 FIX: Skip lines starting with "תמלול:" (transcript snippets)
        // but continue processing remaining lines (don't break the loop)
        if (trimmed.startsWith(TRANSCRIPT_PREFIX)) {
          // Skip this line but continue to next line - there might be more summary content
          continue;
        }
        
        // Check if this line starts with a metadata emoji
        const startsWithMetadataEmoji = METADATA_EMOJIS.some(emoji => trimmed.startsWith(emoji));
        
        // Empty line or metadata line ends the summary block
        if (!trimmed || startsWithMetadataEmoji) {
          inSummaryBlock = false;
          break;
        }
        
        // Otherwise, it's a continuation of the summary
        summaryLines.push(trimmed);
      }
    }
    
    // If we found a summary, return it (join multi-line summaries with newlines)
    if (summaryLines.length > 0) {
      return summaryLines.join('\n');
    }
    
    // Fallback: if no 💬 prefix found, return content as-is
    // This handles legacy data or different formats for backward compatibility
    return content;
  };

  useEffect(() => {
    fetchAINotes();
  }, [lead.id]);

  const fetchAINotes = async () => {
    try {
      setLoading(true);
      const response = await http.get<{ success: boolean; notes: LeadNoteItem[] }>(`/api/leads/${lead.id}/notes`);
      if (response.success) {
        // Migration 75: Show call_summary, system notes, AND customer_service_ai notes (for AI context)
        // customer_service_ai = manual notes added specifically for AI customer service visibility
        // This allows businesses to add context notes that the AI will read during customer service calls
        const aiNotes = response.notes.filter(note => 
          note.note_type === 'call_summary' || 
          note.note_type === 'system' ||
          note.note_type === 'customer_service_ai'
        );
        
        // 🆕 CRITICAL: Sort notes to always show latest first (newest at top)
        // This ensures the most recent/accurate information is prioritized as requested
        // Per requirements: "תתייחס להערה האחרונה שנרשמה כפיסת אמת הכי נכונה"
        const sortedNotes = aiNotes.sort((a, b) => {
          // First priority: notes marked as is_latest in structured_data
          const aIsLatest = a.structured_data?.is_latest === true;
          const bIsLatest = b.structured_data?.is_latest === true;
          if (aIsLatest && !bIsLatest) return -1;
          if (!aIsLatest && bIsLatest) return 1;
          
          // Second priority: sort by created_at timestamp (newest first)
          const aTime = a.created_at ? new Date(a.created_at).getTime() : 0;
          const bTime = b.created_at ? new Date(b.created_at).getTime() : 0;
          return bTime - aTime;
        });
        
        setNotes(sortedNotes);
      }
    } catch (error) {
      console.error('Failed to fetch AI notes:', error);
    } finally {
      setLoading(false);
    }
  };

  const handleSaveNewNote = async () => {
    if (!newNoteContent.trim()) return;
    
    setSaving(true);
    try {
      // Migration 75: Use note_type='customer_service_ai' for notes in AI Customer Service tab
      // This ensures they are visible to AI but separate from free notes
      const response = await http.post<{ success: boolean; note: LeadNoteItem }>(`/api/leads/${lead.id}/notes`, {
        content: newNoteContent.trim(),
        note_type: 'customer_service_ai'  // Mark as AI customer service note
      });
      
      if (response.success) {
        await fetchAINotes();  // Refresh to get updated list
        setNewNoteContent('');
      }
    } catch (error) {
      console.error('Failed to save note:', error);
      alert('שגיאה בשמירת ההערה');
    } finally {
      setSaving(false);
    }
  };

  const handleUpdateNote = async (noteId: number) => {
    if (!editContent.trim()) return;
    
    try {
      const response = await http.patch<{ success: boolean; note: LeadNoteItem }>(`/api/leads/${lead.id}/notes/${noteId}`, {
        content: editContent.trim()
      });
      if (response.success) {
        setNotes(notes.map(n => n.id === noteId ? response.note : n));
        setEditingId(null);
        setEditContent('');
      }
    } catch (error) {
      console.error('Failed to update note:', error);
      alert('שגיאה בעדכון ההערה');
    }
  };

  const handleDeleteNote = async (noteId: number) => {
    if (!confirm('האם למחוק את ההערה?')) return;
    
    try {
      await http.delete(`/api/leads/${lead.id}/notes/${noteId}`);
      setNotes(notes.filter(n => n.id !== noteId));
    } catch (error) {
      console.error('Failed to delete note:', error);
      alert('שגיאה במחיקת ההערה');
    }
  };

  const startEditing = (note: LeadNoteItem) => {
    setEditingId(note.id);
    setEditContent(note.content);
  };

  const cancelEditing = () => {
    setEditingId(null);
    setEditContent('');
  };

  return (
    <Card className="p-4 sm:p-6">
      <div className="flex flex-col gap-2 mb-4">
        <div className="flex items-center justify-between">
          <h3 className="text-lg font-medium text-gray-900 flex items-center gap-2">
            <Phone className="w-5 h-5 text-blue-600" />
            שירות לקוחות AI
          </h3>
        </div>
        <p className="text-xs text-gray-600 bg-blue-50 p-2 rounded border border-blue-200">
          💡 <strong>הערות כאן גלויות ל-AI</strong> - סיכומי שיחות אוטומטיים + הערות שלך שה-AI ידע עליהן (ללא קבצים)
        </p>
      </div>

      {/* New note input - Text only, no file uploads */}
      <div className="mb-6 p-4 bg-gradient-to-br from-blue-50 to-green-50 rounded-lg border-2 border-blue-300">
        <div className="flex items-center gap-2 mb-2">
          <span className="text-sm font-bold text-blue-900">✍️ הוסף הערה לשירות לקוחות</span>
          <span className="text-xs text-blue-700 bg-blue-100 px-2 py-0.5 rounded">AI יראה את זה</span>
        </div>
        <textarea
          value={newNoteContent}
          onChange={(e) => setNewNoteContent(e.target.value)}
          placeholder="לדוגמה: לקוח מעדיף פגישות בבוקר, VIP - טיפול מיוחד, אלרגיה לחתולים..."
          className="w-full h-24 p-3 border-2 border-blue-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500 resize-y text-right bg-white"
          dir="rtl"
          data-testid="textarea-new-ai-note"
        />
        
        <div className="flex items-center justify-end mt-3">
          <Button
            onClick={handleSaveNewNote}
            disabled={saving || !newNoteContent.trim()}
            size="sm"
            data-testid="button-save-new-ai-note"
          >
            {saving ? (
              <>
                <Loader2 className="w-4 h-4 ml-2 animate-spin" />
                שומר...
              </>
            ) : (
              <>
                <Plus className="w-4 h-4 ml-2" />
                הוסף הערה
              </>
            )}
          </Button>
        </div>
      </div>

      {/* Notes list */}
      {loading ? (
        <div className="flex items-center justify-center py-8">
          <Loader2 className="w-6 h-6 animate-spin text-gray-400" />
        </div>
      ) : notes.length === 0 ? (
        <div className="text-center py-8 text-gray-500">
          <Phone className="w-12 h-12 mx-auto mb-2 text-gray-300" />
          <p>אין סיכומי שיחות עדיין</p>
          <p className="text-xs mt-2">סיכומים נוצרים אוטומטית אחרי כל שיחה</p>
        </div>
      ) : (
        <div className="space-y-4">
          {notes.map((note, index) => {
            const isCallSummary = note.note_type === 'call_summary';
            const isSystemNote = note.note_type === 'system';
            const isCustomerServiceAI = note.note_type === 'customer_service_ai';
            const isManualNote = note.note_type === 'manual' || !note.note_type;
            // 🆕 Check if this is the latest note (most accurate source of truth)
            const isLatestNote = note.structured_data?.is_latest === true || index === 0;
            
            const noteClasses = isCallSummary 
              ? "p-4 bg-blue-50 border-2 border-blue-200 rounded-lg" 
              : isSystemNote 
                ? "p-4 bg-gray-100 border-2 border-gray-300 rounded-lg"
                : "p-4 bg-green-50 border-2 border-green-300 rounded-lg";  // Customer service AI & manual notes in green
            
            return (
            <div 
              key={note.id} 
              className={noteClasses}
              data-testid={`ai-note-${note.id}`}
            >
              {/* Note type badge */}
              {isCallSummary && (
                <div className="flex items-center gap-2 mb-2 pb-2 border-b border-blue-200">
                  <Phone className="w-4 h-4 text-blue-600" />
                  <span className="text-xs font-medium text-blue-700 bg-blue-100 px-2 py-0.5 rounded">סיכום שיחה (AI)</span>
                  {/* 🆕 Show "Latest" badge for the most recent note */}
                  {isLatestNote && (
                    <span className="text-xs font-bold text-green-700 bg-green-100 px-2 py-0.5 rounded">
                      ⭐ אחרון
                    </span>
                  )}
                  {note.structured_data?.outcome && (
                    <span className="text-xs text-blue-600">
                      תוצאה: {note.structured_data.outcome}
                    </span>
                  )}
                </div>
              )}
              {isSystemNote && (
                <div className="flex items-center gap-2 mb-2 pb-2 border-b border-gray-300">
                  <span className="text-xs font-medium text-gray-600 bg-gray-200 px-2 py-0.5 rounded">הערת מערכת</span>
                </div>
              )}
              {isCustomerServiceAI && (
                <div className="flex items-center gap-2 mb-2 pb-2 border-b border-green-300">
                  <span className="text-xs font-bold text-green-700 bg-green-100 px-2 py-0.5 rounded">📝 הערה ידנית (גלויה ל-AI)</span>
                </div>
              )}
              {/* Legacy manual notes should not appear here after migration, but handle for safety */}
              {isManualNote && !isCustomerServiceAI && (
                <div className="flex items-center gap-2 mb-2 pb-2 border-b border-green-300">
                  <span className="text-xs font-bold text-green-700 bg-green-100 px-2 py-0.5 rounded">📝 הערה ידנית (גלויה ל-AI)</span>
                </div>
              )}
              
              {editingId === note.id ? (
                <div>
                  <textarea
                    value={editContent}
                    onChange={(e) => setEditContent(e.target.value)}
                    className="w-full h-24 p-3 border border-gray-200 rounded-lg focus:ring-2 focus:ring-blue-500 resize-y text-right"
                    dir="rtl"
                    data-testid={`textarea-edit-ai-note-${note.id}`}
                  />
                  <div className="flex items-center gap-2 mt-2 justify-end">
                    <Button size="sm" variant="secondary" onClick={cancelEditing}>
                      ביטול
                    </Button>
                    <Button size="sm" onClick={() => handleUpdateNote(note.id)}>
                      <Save className="w-4 h-4 ml-2" />
                      שמור
                    </Button>
                  </div>
                </div>
              ) : (
                <>
                  <div className="flex items-start justify-between gap-2">
                    <div className="flex items-center gap-2">
                      {/* Allow editing customer service AI notes (manual notes for AI context) */}
                      {isCustomerServiceAI && (
                        <button
                          onClick={() => startEditing(note)}
                          className="p-1.5 text-gray-400 hover:text-green-600 hover:bg-green-50 rounded transition-colors"
                          title="ערוך"
                          data-testid={`button-edit-ai-note-${note.id}`}
                        >
                          <Pencil className="w-4 h-4" />
                        </button>
                      )}
                      {/* All notes can be deleted - including AI-generated */}
                      <button
                        onClick={() => handleDeleteNote(note.id)}
                        className="p-1.5 text-gray-400 hover:text-red-600 hover:bg-red-50 rounded transition-colors"
                        title="מחק"
                        data-testid={`button-delete-ai-note-${note.id}`}
                      >
                        <Trash2 className="w-4 h-4" />
                      </button>
                    </div>
                    <span className="text-xs text-gray-400">
                      {note.created_at ? formatDate(note.created_at) : ''}
                    </span>
                  </div>
                  <p className="mt-2 text-gray-700 whitespace-pre-wrap text-right" dir="rtl">
                    {isCallSummary ? extractCleanSummary(note.content) : note.content}
                  </p>
                </>
              )}
            </div>
          );
          })}
        </div>
      )}

      <p className="mt-4 text-xs text-gray-400 text-center">
        סיכומי שיחות נוצרים אוטומטית ומיועדים לשירות לקוחות מהיר ומדויק
      </p>
    </Card>
  );
}

// ✅ BUILD 172: Notes Tab - Permanent notes with edit/delete and file attachments
interface NotesTabProps {
  lead: Lead;
  onUpdate: () => void;
}

interface NoteAttachment {
  id: string | number;
  filename?: string;  // For new API format
  name?: string;      // Legacy format
  content_type?: string;
  size_bytes?: number;
  size?: number;      // Legacy format
  download_url?: string;
  url?: string;       // Legacy format
  type?: 'image' | 'file';
  created_at?: string;
}

interface LeadNoteItem {
  id: number;
  content: string;
  note_type?: 'manual' | 'call_summary' | 'system' | 'customer_service_ai';  // Migration 75: Added customer_service_ai
  call_id?: number;  // Link to call for call_summary notes
  structured_data?: {
    sentiment?: string;
    outcome?: string;
    next_step_date?: string;
  };
  attachments: NoteAttachment[];
  created_at: string | null;
  updated_at: string | null;
}

const MAX_FILE_SIZE = 10 * 1024 * 1024; // 10MB

function NotesTab({ lead, onUpdate }: NotesTabProps) {
  const [notes, setNotes] = useState<LeadNoteItem[]>([]);
  const [newNoteContent, setNewNoteContent] = useState('');
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [editingId, setEditingId] = useState<number | null>(null);
  const [editContent, setEditContent] = useState('');
  const [pendingFiles, setPendingFiles] = useState<File[]>([]);
  const fileInputRef = React.useRef<HTMLInputElement>(null);

  useEffect(() => {
    fetchNotes();
  }, [lead.id]);

  const fetchNotes = async () => {
    try {
      setLoading(true);
      const response = await http.get<{ success: boolean; notes: LeadNoteItem[] }>(`/api/leads/${lead.id}/notes`);
      if (response.success) {
        // Filter to show only manual notes (user-created)
        const manualNotes = response.notes.filter(note => 
          !note.note_type || note.note_type === 'manual'
        );
        setNotes(manualNotes);
      }
    } catch (error) {
      console.error('Failed to fetch notes:', error);
    } finally {
      setLoading(false);
    }
  };

  const handleSaveNewNote = async () => {
    // 🔥 FIX: Allow saving if there's content OR files (not just content)
    if (!newNoteContent.trim() && pendingFiles.length === 0) return;
    
    setSaving(true);
    try {
      // First, create the note (use placeholder text if only files, no text)
      const noteContent = newNoteContent.trim() || '📎 קבצים מצורפים';
      const response = await http.post<{ success: boolean; note: LeadNoteItem }>(`/api/leads/${lead.id}/notes`, {
        content: noteContent
      });
      
      if (response.success) {
        const newNote = response.note;
        
        // Then upload any pending files to the note
        if (pendingFiles.length > 0) {
          const uploadResults: { file: File; success: boolean }[] = [];
          
          for (const file of pendingFiles) {
            try {
              const fd = new FormData();
              fd.append('file', file);
              
              await http.request<any>(`/api/leads/${lead.id}/notes/${newNote.id}/upload`, {
                method: 'POST',
                body: fd
              });
              uploadResults.push({ file, success: true });
            } catch (error) {
              console.error(`Failed to upload file ${file.name}:`, error);
              uploadResults.push({ file, success: false });
            }
          }
          
          // Check for failed uploads
          const failedUploads = uploadResults.filter(r => !r.success);
          if (failedUploads.length > 0) {
            const failedNames = failedUploads.map(r => r.file.name).join(', ');
            alert(`שגיאה בהעלאת קבצים: ${failedNames}`);
          }
          
          // Refresh notes to get updated attachments
          await fetchNotes();
        } else {
          setNotes([newNote, ...notes]);
        }
        
        setNewNoteContent('');
        setPendingFiles([]);
      }
    } catch (error) {
      console.error('Failed to save note:', error);
      alert('שגיאה בשמירת ההערה');
    } finally {
      setSaving(false);
    }
  };

  const handleUpdateNote = async (noteId: number) => {
    if (!editContent.trim()) return;
    
    try {
      const response = await http.patch<{ success: boolean; note: LeadNoteItem }>(`/api/leads/${lead.id}/notes/${noteId}`, {
        content: editContent.trim()
      });
      if (response.success) {
        setNotes(notes.map(n => n.id === noteId ? response.note : n));
        setEditingId(null);
        setEditContent('');
      }
    } catch (error) {
      console.error('Failed to update note:', error);
      alert('שגיאה בעדכון ההערה');
    }
  };

  const handleDeleteNote = async (noteId: number) => {
    if (!confirm('האם למחוק את ההערה?')) return;
    
    try {
      await http.delete(`/api/leads/${lead.id}/notes/${noteId}`);
      setNotes(notes.filter(n => n.id !== noteId));
    } catch (error) {
      console.error('Failed to delete note:', error);
      alert('שגיאה במחיקת ההערה');
    }
  };

  const handleFileSelect = (e: React.ChangeEvent<HTMLInputElement>) => {
    const files = e.target.files;
    if (!files || files.length === 0) return;

    const file = files[0];
    
    if (file.size > MAX_FILE_SIZE) {
      alert('הקובץ גדול מדי. הגודל המקסימלי הוא 10MB');
      e.target.value = '';
      return;
    }

    // Validate file name length and characters
    const fileName = file.name;
    if (fileName.length > 100) {
      alert('שם הקובץ ארוך מדי (מקסימום 100 תווים)');
      e.target.value = '';
      return;
    }

    // Add file to pending files (will be uploaded when note is saved)
    setPendingFiles(prev => [...prev, file]);
    
    // Clear the input
    e.target.value = '';
  };
  
  const handleRemovePendingFile = (index: number) => {
    setPendingFiles(prev => prev.filter((_, i) => i !== index));
  };

  const startEditing = (note: LeadNoteItem) => {
    setEditingId(note.id);
    setEditContent(note.content);
  };

  const cancelEditing = () => {
    setEditingId(null);
    setEditContent('');
  };

  const formatFileSize = (bytes?: number) => {
    if (!bytes) return '';
    if (bytes < 1024) return `${bytes} B`;
    if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
    return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
  };

  const getAttachmentUrl = (att: NoteAttachment) => {
    return att.download_url || att.url || '';
  };

  const getAttachmentName = (att: NoteAttachment) => {
    return att.filename || att.name || 'קובץ';
  };

  const getAttachmentSize = (att: NoteAttachment) => {
    return att.size_bytes || att.size || 0;
  };

  const handleDownloadFile = async (url: string, filename: string, e?: React.MouseEvent) => {
    // Prevent default link behavior
    if (e) {
      e.preventDefault();
      e.stopPropagation();
    }
    
    try {
      // Fetch the file with proper auth
      const response = await fetch(url, {
        method: 'GET',
        credentials: 'include'
      });
      
      if (!response.ok) {
        throw new Error('Failed to download file');
      }
      
      // Create blob and download
      const blob = await response.blob();
      const downloadUrl = window.URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = downloadUrl;
      a.download = filename;
      document.body.appendChild(a);
      a.click();
      window.URL.revokeObjectURL(downloadUrl);
      document.body.removeChild(a);
    } catch (error) {
      console.error('Error downloading file:', error);
      alert('שגיאה בהורדת הקובץ');
    }
  };

  const handleDeleteAttachment = async (attachmentId: string | number, noteId: number) => {
    if (!confirm('האם למחוק את הקובץ?')) return;
    
    try {
      // Use the correct endpoint for note attachments (supports UUID IDs)
      await http.delete(`/api/leads/${lead.id}/notes/${noteId}/attachments/${attachmentId}`);
      // Refresh notes to get updated attachments
      await fetchNotes();
      alert('הקובץ נמחק בהצלחה');
    } catch (error) {
      console.error('Failed to delete attachment:', error);
      alert('שגיאה במחיקת הקובץ');
    }
  };

  const getFileIcon = (contentType?: string) => {
    if (!contentType) return File;
    if (contentType.startsWith('image/')) return ImageIcon;
    if (contentType.startsWith('audio/')) return FileText;
    if (contentType.startsWith('video/')) return FileText;
    if (contentType.includes('pdf')) return FileText;
    return File;
  };

  const isAudioFile = (contentType?: string) => {
    return contentType?.startsWith('audio/') || false;
  };

  const isImageFile = (contentType?: string) => {
    return contentType?.startsWith('image/') || false;
  };

  return (
    <Card className="p-4 sm:p-6">
      <div className="flex items-center justify-between mb-4">
        <h3 className="text-lg font-medium text-gray-900 flex items-center gap-2">
          <FileText className="w-5 h-5 text-gray-500" />
          הערות חופשיות
        </h3>
      </div>

      {/* New note input */}
      <div className="mb-6 p-4 bg-gray-50 rounded-lg border border-gray-200">
        <textarea
          value={newNoteContent}
          onChange={(e) => setNewNoteContent(e.target.value)}
          placeholder="הוסף הערה חדשה..."
          className="w-full h-24 p-3 border border-gray-200 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500 resize-y text-right bg-white"
          dir="rtl"
          data-testid="textarea-new-note"
        />
        
        {/* Show pending files */}
        {pendingFiles.length > 0 && (
          <div className="mt-2 space-y-1">
            {pendingFiles.map((file, index) => (
              <div key={index} className="flex items-center justify-between bg-blue-50 p-2 rounded text-sm">
                <div className="flex items-center gap-2">
                  <File className="w-4 h-4 text-blue-600" />
                  <span className="text-blue-900">{file.name}</span>
                  <span className="text-blue-600 text-xs">({(file.size / 1024).toFixed(1)} KB)</span>
                </div>
                <button
                  onClick={() => handleRemovePendingFile(index)}
                  className="text-red-500 hover:text-red-700"
                  title="הסר קובץ"
                >
                  <X className="w-4 h-4" />
                </button>
              </div>
            ))}
          </div>
        )}
        
        <div className="flex items-center justify-between mt-3">
          <div className="flex items-center gap-2">
            <button
              onClick={() => fileInputRef.current?.click()}
              className="p-2 text-gray-500 hover:text-blue-600 hover:bg-blue-100 rounded-lg transition-colors"
              title="הוסף קובץ (עד 10MB)"
              data-testid="button-add-file"
            >
              <Upload className="w-5 h-5" />
            </button>
            <span className="text-xs text-gray-400">מקסימום 10MB לקובץ</span>
          </div>
          <Button
            onClick={handleSaveNewNote}
            disabled={saving || (!newNoteContent.trim() && pendingFiles.length === 0)}
            size="sm"
            data-testid="button-save-new-note"
          >
            {saving ? (
              <>
                <Loader2 className="w-4 h-4 ml-2 animate-spin" />
                שומר...
              </>
            ) : (
              <>
                <Plus className="w-4 h-4 ml-2" />
                הוסף הערה
              </>
            )}
          </Button>
        </div>
      </div>

      <input
        ref={fileInputRef}
        type="file"
        className="hidden"
        onChange={(e) => handleFileSelect(e)}
        data-testid="input-file-upload"
      />

      {/* Notes list */}
      {loading ? (
        <div className="flex items-center justify-center py-8">
          <Loader2 className="w-6 h-6 animate-spin text-gray-400" />
        </div>
      ) : notes.length === 0 ? (
        <div className="text-center py-8 text-gray-500">
          <FileText className="w-12 h-12 mx-auto mb-2 text-gray-300" />
          <p>אין הערות עדיין</p>
        </div>
      ) : (
        <div className="space-y-4">
          {notes.map((note) => {
            // All notes in this tab are manual notes (with attachments allowed)
            return (
            <div 
              key={note.id} 
              className="p-4 bg-white border border-gray-200 rounded-lg"
              data-testid={`note-${note.id}`}
            >
              {editingId === note.id ? (
                <div>
                  <textarea
                    value={editContent}
                    onChange={(e) => setEditContent(e.target.value)}
                    className="w-full h-24 p-3 border border-gray-200 rounded-lg focus:ring-2 focus:ring-blue-500 resize-y text-right"
                    dir="rtl"
                    data-testid={`textarea-edit-note-${note.id}`}
                  />
                  <div className="flex items-center gap-2 mt-2 justify-end">
                    <Button size="sm" variant="secondary" onClick={cancelEditing}>
                      ביטול
                    </Button>
                    <Button size="sm" onClick={() => handleUpdateNote(note.id)}>
                      <Save className="w-4 h-4 ml-2" />
                      שמור
                    </Button>
                  </div>
                </div>
              ) : (
                <>
                  <div className="flex items-start justify-between gap-2">
                    <div className="flex items-center gap-2">
                      {/* All notes in Free Notes tab can be edited/deleted */}
                      <button
                        onClick={() => startEditing(note)}
                        className="p-1.5 text-gray-400 hover:text-blue-600 hover:bg-blue-50 rounded transition-colors"
                        title="ערוך"
                        data-testid={`button-edit-note-${note.id}`}
                      >
                        <Pencil className="w-4 h-4" />
                      </button>
                      <button
                        onClick={() => handleDeleteNote(note.id)}
                        className="p-1.5 text-gray-400 hover:text-red-600 hover:bg-red-50 rounded transition-colors"
                        title="מחק"
                        data-testid={`button-delete-note-${note.id}`}
                      >
                        <Trash2 className="w-4 h-4" />
                      </button>
                    </div>
                    <span className="text-xs text-gray-400">
                      {note.created_at ? formatDate(note.created_at) : ''}
                    </span>
                  </div>
                  <p className="mt-2 text-gray-700 whitespace-pre-wrap text-right" dir="rtl">
                    {note.content}
                  </p>
                  
                  {note.attachments && note.attachments.length > 0 && (
                    <div className="mt-3 pt-3 border-t">
                      <p className="text-xs font-medium text-gray-500 mb-2">קבצים מצורפים:</p>
                      <div className="flex flex-col gap-3">
                        {note.attachments.map((att) => {
                          const FileIconComponent = getFileIcon(att.content_type);
                          const url = getAttachmentUrl(att);
                          const name = getAttachmentName(att);
                          const size = getAttachmentSize(att);
                          
                          // Render audio files with player
                          if (isAudioFile(att.content_type)) {
                            return (
                              <div key={att.id} className="bg-gray-50 rounded-lg p-3 border border-gray-200">
                                <div className="flex items-center justify-between mb-2">
                                  <div className="flex items-center gap-2">
                                    <FileIconComponent className="w-4 h-4 text-gray-500" />
                                    <span className="text-sm font-medium text-gray-700">{name}</span>
                                    {size > 0 && (
                                      <span className="text-xs text-gray-400">({formatFileSize(size)})</span>
                                    )}
                                  </div>
                                  <button
                                    onClick={() => handleDeleteAttachment(att.id, note.id)}
                                    className="p-1 text-red-500 hover:text-red-700 hover:bg-red-50 rounded transition-colors"
                                    title="מחק קובץ"
                                  >
                                    <Trash2 className="w-3 h-3" />
                                  </button>
                                </div>
                                <audio 
                                  controls 
                                  className="w-full h-10"
                                  preload="metadata"
                                  aria-label={`הקלטה: ${name}`}
                                  onClick={(e) => e.stopPropagation()}
                                >
                                  <source src={url} type={att.content_type} />
                                  הדפדפן שלך אינו תומך בנגן שמע.
                                </audio>
                                <div className="flex gap-2 mt-2">
                                  <button
                                    onClick={(e) => handleDownloadFile(url, name, e)}
                                    className="text-xs text-blue-600 hover:text-blue-700 flex items-center gap-1 px-2 py-1 bg-blue-50 hover:bg-blue-100 rounded"
                                  >
                                    <svg className="w-3 h-3" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-4l-4 4m0 0l-4-4m4 4V4" />
                                    </svg>
                                    הורד
                                  </button>
                                </div>
                              </div>
                            );
                          }
                          
                          // Render images with preview
                          if (isImageFile(att.content_type)) {
                            return (
                              <div key={att.id} className="bg-gray-50 rounded-lg p-3 border border-gray-200">
                                <div className="flex items-center justify-between mb-2">
                                  <div className="flex items-center gap-2">
                                    <ImageIcon className="w-4 h-4 text-gray-500" />
                                    <span className="text-sm font-medium text-gray-700">{name}</span>
                                    {size > 0 && (
                                      <span className="text-xs text-gray-400">({formatFileSize(size)})</span>
                                    )}
                                  </div>
                                  <button
                                    onClick={() => handleDeleteAttachment(att.id, note.id)}
                                    className="p-1 text-red-500 hover:text-red-700 hover:bg-red-50 rounded transition-colors"
                                    title="מחק קובץ"
                                  >
                                    <Trash2 className="w-3 h-3" />
                                  </button>
                                </div>
                                <div className="relative">
                                  <img 
                                    src={url} 
                                    alt={name}
                                    className="max-w-full h-auto rounded border border-gray-300 cursor-pointer"
                                    style={{ maxHeight: '300px' }}
                                    onClick={(e) => {
                                      e.preventDefault();
                                      e.stopPropagation();
                                      window.open(url, '_blank', 'noopener,noreferrer');
                                    }}
                                  />
                                  <div className="flex gap-2 mt-2">
                                    <button
                                      onClick={(e) => {
                                        e.preventDefault();
                                        e.stopPropagation();
                                        window.open(url, '_blank', 'noopener,noreferrer');
                                      }}
                                      className="text-xs text-blue-600 hover:text-blue-700 flex items-center gap-1 px-2 py-1 bg-blue-50 hover:bg-blue-100 rounded"
                                    >
                                      <svg className="w-3 h-3" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M10 6H6a2 2 0 00-2 2v10a2 2 0 002 2h10a2 2 0 002-2v-4M14 4h6m0 0v6m0-6L10 14" />
                                      </svg>
                                      פתח
                                    </button>
                                    <button
                                      onClick={(e) => handleDownloadFile(url, name, e)}
                                      className="text-xs text-gray-600 hover:text-gray-700 flex items-center gap-1 px-2 py-1 bg-gray-50 hover:bg-gray-100 rounded"
                                    >
                                      <svg className="w-3 h-3" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-4l-4 4m0 0l-4-4m4 4V4" />
                                      </svg>
                                      הורד
                                    </button>
                                  </div>
                                </div>
                              </div>
                            );
                          }
                          
                          // Render other files as download links
                          return (
                            <div
                              key={att.id}
                              className="flex items-center gap-2 px-3 py-2 bg-gray-100 rounded-lg transition-colors group"
                            >
                              <div className="flex items-center gap-2 text-sm text-gray-700 flex-1">
                                <FileIconComponent className="w-4 h-4 flex-shrink-0" />
                                <span className="max-w-[150px] truncate">{name}</span>
                                {size > 0 && (
                                  <span className="text-xs text-gray-400">({formatFileSize(size)})</span>
                                )}
                              </div>
                              <div className="flex gap-1">
                                <button
                                  onClick={(e) => {
                                    e.preventDefault();
                                    e.stopPropagation();
                                    window.open(url, '_blank', 'noopener,noreferrer');
                                  }}
                                  className="p-1 text-blue-500 hover:text-blue-700 hover:bg-blue-50 rounded transition-colors"
                                  title="פתח קובץ"
                                >
                                  <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M10 6H6a2 2 0 00-2 2v10a2 2 0 002 2h10a2 2 0 002-2v-4M14 4h6m0 0v6m0-6L10 14" />
                                  </svg>
                                </button>
                                <button
                                  onClick={(e) => handleDownloadFile(url, name, e)}
                                  className="p-1 text-gray-500 hover:text-gray-700 hover:bg-gray-50 rounded transition-colors"
                                  title="הורד קובץ"
                                >
                                  <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-4l-4 4m0 0l-4-4m4 4V4" />
                                  </svg>
                                </button>
                                <button
                                  onClick={() => handleDeleteAttachment(att.id, note.id)}
                                  className="opacity-0 group-hover:opacity-100 p-1 text-red-500 hover:text-red-700 transition-opacity"
                                  title="מחק קובץ"
                                >
                                  <Trash2 className="w-3 h-3" />
                                </button>
                              </div>
                            </div>
                          );
                        })}
                      </div>
                    </div>
                  )}
                </>
              )}
            </div>
          );
          })}
        </div>
      )}

      <p className="mt-4 text-xs text-gray-400 text-center">
        הערות חופשיות נשמרות לצמיתות על הליד ויכולות לכלול קבצים מצורפים
      </p>
    </Card>
  );
}

// Email Tab Component
interface EmailTabProps {
  lead: Lead;
}

interface LuxuryTheme {
  id: string;
  name: string;
  description: string;
  preview_thumbnail?: string;
  default_fields?: {
    subject: string;
    greeting: string;
    body: string;
    cta_text: string;
    cta_url: string;
    footer: string;
  };
}

function EmailTab({ lead }: EmailTabProps) {
  const [emails, setEmails] = useState<any[]>([]);
  const [availableThemes, setAvailableThemes] = useState<LuxuryTheme[]>([]);
  const [selectedThemeId, setSelectedThemeId] = useState('classic_blue');
  const [themesLoading, setThemesLoading] = useState(false);
  const [themesError, setThemesError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [sending, setSending] = useState(false);
  const [showCompose, setShowCompose] = useState(false);
  
  // Text templates for quick content
  const [textTemplates, setTextTemplates] = useState<{id: number; name: string; category: string; subject_line: string; body_text: string}[]>([]);
  
  // Saved template settings
  const [savedTemplateSettings, setSavedTemplateSettings] = useState({
    theme_id: 'classic_blue',
    default_greeting: `שלום ${lead.first_name || ''},`,
    cta_default_text: '',
    cta_default_url: '',
    footer_text: 'אם אינך מעוניין לקבל הודעות נוספות, אנא לחץ כאן להסרה מהרשימה.\n\n© {{business.name}} | כל הזכויות שמורות'
  });
  
  // Theme fields - editable each time
  const [themeFields, setThemeFields] = useState({
    subject: '',
    greeting: `שלום ${lead.first_name || ''},`,
    body: '',
    cta_text: '',
    cta_url: '',
    footer: 'אם אינך מעוניין לקבל הודעות נוספות, אנא לחץ כאן להסרה מהרשימה.\n\n© {{business.name}} | כל הזכויות שמורות'
  });
  
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);

  useEffect(() => {
    loadEmails();
    loadThemes();
    loadTemplateSettings();
    loadTextTemplates();
  }, [lead.id]);
  
  const loadTextTemplates = async () => {
    try {
      const response = await http.get<{templates: {id: number; name: string; category: string; subject_line: string; body_text: string}[]}>('/api/email/text-templates');
      setTextTemplates(response.templates || []);
    } catch (err) {
      console.error('Failed to load text templates:', err);
      setTextTemplates([]);
    }
  };
  
  const loadTemplateSettings = async () => {
    try {
      const response = await http.get('/api/email/settings');
      if (response.settings) {
        const s = response.settings;
        setSavedTemplateSettings({
          theme_id: s.theme_id || 'classic_blue',
          default_greeting: s.default_greeting || `שלום ${lead.first_name || ''},`,
          cta_default_text: s.cta_default_text || '',
          cta_default_url: s.cta_default_url || '',
          footer_text: s.footer_text || 'אם אינך מעוניין לקבל הודעות נוספות, אנא לחץ כאן להסרה מהרשימה.\n\n© {{business.name}} | כל הזכויות שמורות'
        });
      }
    } catch (err) {
      console.error('Failed to load template settings:', err);
    }
  };
  
  const loadFromTemplate = () => {
    setSelectedThemeId(savedTemplateSettings.theme_id);
    setThemeFields(prev => ({
      ...prev,
      greeting: savedTemplateSettings.default_greeting,
      cta_text: savedTemplateSettings.cta_default_text,
      cta_url: savedTemplateSettings.cta_default_url,
      footer: savedTemplateSettings.footer_text
    }));
    setSuccess('הגדרות התבנית נטענו! ניתן לערוך לפני שליחה');
    setTimeout(() => setSuccess(null), 3000);
  };
  
  const loadThemes = async () => {
    setThemesLoading(true);
    setThemesError(null);
    try {
      console.log('[LEAD_EMAIL] Fetching catalog...');
      const response = await http.get('/api/email/template-catalog');
      
      console.log('[LEAD_EMAIL] status', response.status || 200, 'data', response);
      
      // 🔥 FIX: Handle both response formats (themes at root or nested)
      const raw = response;
      const themes = raw?.themes ?? raw ?? [];
      
      console.log('[LEAD_EMAIL] Parsed themes count:', Array.isArray(themes) ? themes.length : 0);
      
      // 🔥 FIX: Always ensure we have an array
      if (Array.isArray(themes) && themes.length > 0) {
        setAvailableThemes(themes);
        // Set default theme if not already selected
        if (!selectedThemeId || selectedThemeId === 'classic_blue') {
          setSelectedThemeId(themes[0].id);
        }
        console.log('[LEAD_EMAIL] ✅ Loaded', themes.length, 'themes');
      } else {
        setAvailableThemes([]);
        setThemesError('No themes available');
        console.error('[LEAD_EMAIL] ❌ No themes returned, raw response:', raw);
      }
    } catch (err: any) {
      setAvailableThemes([]);
      const errorMsg = err?.message || 'Failed to load themes';
      setThemesError(errorMsg);
      console.error('[LEAD_EMAIL] ❌ Failed to load themes:', {
        error: errorMsg,
        err
      });
    } finally {
      setThemesLoading(false);
    }
  };

  const loadEmails = async () => {
    try {
      setLoading(true);
      const response = await http.get(`/api/leads/${lead.id}/emails`);
      setEmails(response.data.emails || []);
    } catch (err) {
      console.error('Failed to load emails:', err);
    } finally {
      setLoading(false);
    }
  };
  
  const handleThemeChange = (themeId: string) => {
    setSelectedThemeId(themeId);
    const theme = availableThemes.find(t => t.id === themeId);
    if (theme && theme.default_fields) {
      // Load default fields from theme
      setThemeFields(prev => ({
        ...prev,
        greeting: theme.default_fields?.greeting || prev.greeting,
        body: theme.default_fields?.body || prev.body,
        cta_text: theme.default_fields?.cta_text || prev.cta_text,
        cta_url: theme.default_fields?.cta_url || prev.cta_url,
        footer: theme.default_fields?.footer || prev.footer
      }));
    }
  };

  const handleSendEmail = async (e: React.FormEvent) => {
    e.preventDefault();
    
    if (!selectedThemeId) {
      setError('נא לבחור תבנית עיצוב');
      return;
    }
    
    if (!themeFields.subject.trim() || !themeFields.body.trim()) {
      setError('נא למלא לפחות נושא ותוכן המייל');
      return;
    }
    
    if (!lead.email) {
      setError('אין כתובת מייל לליד זה');
      return;
    }
    
    setSending(true);
    setError(null);
    setSuccess(null);
    
    try {
      console.log('[LEAD_EMAIL] Rendering theme:', selectedThemeId, 'for lead:', lead.id);
      
      // First, render the theme with user fields
      const renderResponse = await http.post('/api/email/render-theme', {
        theme_id: selectedThemeId,
        fields: themeFields,
        lead_id: lead.id
      });
      
      // 🔥 FIX: Support both response formats
      if (renderResponse.ok === false || renderResponse.success === false) {
        throw new Error(renderResponse.error || 'Render failed');
      }
      
      const rendered = renderResponse.rendered || renderResponse;
      
      if (!rendered || !rendered.html) {
        throw new Error('No HTML returned from render');
      }
      
      console.log('[LEAD_EMAIL] ✅ Render successful, sending email...');
      
      // Then send the rendered email
      await http.post(`/api/leads/${lead.id}/email`, {
        to_email: lead.email,
        subject: rendered.subject,
        html: rendered.html,
        body_html: rendered.html,
        text: rendered.text,
        body_text: rendered.text
      });
      
      console.log('[LEAD_EMAIL] ✅ Email sent successfully');
      setSuccess('המייל נשלח בהצלחה!');
      setThemeFields({
        subject: '',
        greeting: `שלום ${lead.first_name || ''},`,
        body: '',
        cta_text: '',
        cta_url: '',
        footer: 'אם אינך מעוניין לקבל הודעות נוספות, אנא לחץ כאן להסרה מהרשימה.\n\n© {{business.name}} | כל הזכויות שמורות'
      });
      setShowCompose(false);
      await loadEmails();
    } catch (err: any) {
      console.error('[LEAD_EMAIL] ❌ Failed:', err);
      const errorMsg = err.response?.data?.message || err.response?.data?.error || err.message || 'שגיאה בשליחת המייל';
      setError(errorMsg);
    } finally {
      setSending(false);
    }
  };

  const getStatusBadge = (status: string) => {
    const config: Record<string, { color: string; label: string }> = {
      queued: { color: 'bg-gray-100 text-gray-800', label: 'בתור' },
      sent: { color: 'bg-green-100 text-green-800', label: 'נשלח' },
      failed: { color: 'bg-red-100 text-red-800', label: 'נכשל' },
      delivered: { color: 'bg-blue-100 text-blue-800', label: 'נמסר' },
    };
    const { color, label } = config[status] || config.queued;
    return <span className={`px-2 py-1 rounded-full text-xs font-medium ${color}`}>{label}</span>;
  };

  return (
    <Card>
      <div className="mb-4 flex justify-between items-center">
        <h3 className="text-lg font-semibold">מיילים</h3>
        {lead.email && (
          <Button
            onClick={() => setShowCompose(!showCompose)}
            variant="primary"
            size="sm"
          >
            <Mail className="w-4 h-4 ml-2" />
            {showCompose ? 'ביטול' : 'שלח מייל'}
          </Button>
        )}
      </div>

      {!lead.email && (
        <div className="text-center py-8 text-gray-500">
          <Mail className="w-12 h-12 mx-auto mb-2 text-gray-400" />
          <p>אין כתובת מייל לליד זה</p>
        </div>
      )}

      {error && (
        <div className="mb-4 bg-red-50 border border-red-200 rounded-lg p-3 text-sm text-red-800">
          {error}
        </div>
      )}

      {success && (
        <div className="mb-4 bg-green-50 border border-green-200 rounded-lg p-3 text-sm text-green-800">
          {success}
        </div>
      )}

      {showCompose && lead.email && (
        <div className="mb-6 border-2 border-blue-200 rounded-xl p-5 bg-gradient-to-br from-blue-50 to-white shadow-sm">
          {/* Load Template Button - At the top */}
          <div className="mb-4 bg-gradient-to-r from-purple-50 to-blue-50 border-2 border-purple-200 rounded-lg p-3 shadow-sm">
            <div className="flex flex-col sm:flex-row sm:items-center gap-2">
              <div className="flex-1">
                <h4 className="text-sm font-bold text-purple-900 flex items-center gap-2">
                  <span className="text-lg">📋</span>
                  <span>טען הגדרות מהתבנית</span>
                </h4>
                <p className="text-xs text-purple-700 mt-0.5">
                  טען ברכה, פוטר וכפתור CTA מהתבנית השמורה
                </p>
              </div>
              <button
                type="button"
                onClick={loadFromTemplate}
                className="px-4 py-2 bg-purple-600 text-white rounded-lg hover:bg-purple-700 transition-colors font-medium flex items-center gap-2 whitespace-nowrap text-sm"
              >
                <span>📥</span>
                <span>טען תבנית</span>
              </button>
            </div>
          </div>

          <form onSubmit={handleSendEmail} className="space-y-4">
            {/* Theme Selector - Separated Section */}
            <div className="bg-gradient-to-br from-purple-50 to-blue-50 border-2 border-purple-200 rounded-lg p-4 shadow-sm">
              <label className="block text-sm font-bold text-purple-900 mb-2 flex items-center gap-2">
                <span className="text-xl">🎨</span>
                <span>בחר עיצוב יוקרתי (Theme)</span>
              </label>
              
              {themesLoading ? (
                <div className="text-sm text-gray-600 flex items-center gap-2">
                  <div className="animate-spin rounded-full h-4 w-4 border-b-2 border-purple-600"></div>
                  <span>טוען עיצובים...</span>
                </div>
              ) : themesError ? (
                <div className="text-sm text-red-600 bg-red-50 p-3 rounded-lg border border-red-200">
                  ⚠️ שגיאה בטעינת עיצובים: {themesError}
                  <button
                    type="button"
                    onClick={loadThemes}
                    className="mr-2 text-red-700 underline hover:text-red-900"
                  >
                    נסה שוב
                  </button>
                </div>
              ) : availableThemes.length === 0 ? (
                <div className="text-sm text-amber-600 bg-amber-50 p-3 rounded-lg border border-amber-200">
                  ⚠️ לא נמצאו עיצובים זמינים
                  <button
                    type="button"
                    onClick={loadThemes}
                    className="mr-2 text-amber-700 underline hover:text-amber-900"
                  >
                    טען מחדש
                  </button>
                </div>
              ) : (
                <select
                  value={selectedThemeId}
                  onChange={(e) => handleThemeChange(e.target.value)}
                  className="w-full px-4 py-3 border-2 border-purple-300 rounded-lg focus:ring-4 focus:ring-purple-200 focus:border-purple-500 bg-white font-medium shadow-sm"
                >
                  {availableThemes.map((theme) => (
                    <option key={theme.id} value={theme.id}>
                      {theme.name} - {theme.description}
                    </option>
                  ))}
                </select>
              )}
            </div>

            {/* Content Section - Subject and Body Together */}
            <div className="space-y-4 bg-white border-2 border-gray-200 rounded-lg p-4">
              <div className="border-b border-gray-200 pb-2 mb-3">
                <h4 className="font-bold text-gray-900 flex items-center gap-2">
                  <span className="text-xl">✍️</span>
                  <span>תוכן ההודעה</span>
                </h4>
                <p className="text-xs text-gray-600 mt-1">מה אני רוצה לרשום לליד הזה</p>
              </div>

              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">
                  אל
                </label>
                <input
                  type="text"
                  value={lead.email}
                  disabled
                  className="w-full px-3 py-2 border border-gray-300 rounded-lg bg-gray-50 text-gray-600"
                />
              </div>

              <div>
                <label className="block text-sm font-bold text-gray-900 mb-1 flex items-center gap-2">
                  <span className="text-lg">📧</span>
                  <span>נושא *</span>
                </label>
                <input
                  type="text"
                  value={themeFields.subject}
                  onChange={(e) => setThemeFields({...themeFields, subject: e.target.value})}
                  placeholder="נושא המייל"
                  className="w-full px-3 py-2.5 border-2 border-gray-300 rounded-lg focus:ring-4 focus:ring-blue-200 focus:border-blue-500 shadow-sm"
                  required
                />
              </div>

              <div>
                <label className="block text-sm font-bold text-gray-900 mb-1 flex items-center gap-2">
                  <span className="text-lg">👋</span>
                  <span>ברכה פותחת</span>
                </label>
                <input
                  type="text"
                  value={themeFields.greeting}
                  onChange={(e) => setThemeFields({...themeFields, greeting: e.target.value})}
                  placeholder={`שלום ${lead.first_name || ''},`}
                  className="w-full px-3 py-2.5 border-2 border-gray-300 rounded-lg focus:ring-4 focus:ring-blue-200 focus:border-blue-500 shadow-sm"
                />
              </div>

              <div>
                <label className="block text-sm font-bold text-gray-900 mb-1 flex items-center gap-2">
                  <span className="text-lg">📝</span>
                  <span>תוכן *</span>
                </label>
                
                {/* 🔥 NEW: Text Template Quick Select */}
                {textTemplates.length > 0 && (
                  <div className="bg-green-50 border border-green-200 rounded-lg p-3 mb-2">
                    <label className="block text-xs font-medium text-green-800 mb-1.5 flex items-center gap-1">
                      <FileText className="w-3.5 h-3.5" />
                      טען מתבנית טקסט
                    </label>
                    <select
                      value=""
                      onChange={(e) => {
                        const template = textTemplates.find(t => t.id === parseInt(e.target.value));
                        if (template) {
                          setThemeFields(prev => ({
                            ...prev,
                            subject: template.subject_line || prev.subject,
                            body: template.body_text
                          }));
                          setSuccess(`תבנית "${template.name}" נטענה!`);
                          setTimeout(() => setSuccess(null), 3000);
                        }
                      }}
                      className="w-full px-3 py-2 border border-green-300 rounded-lg bg-white text-sm focus:ring-2 focus:ring-green-200 focus:border-green-500"
                    >
                      <option value="">-- בחר תבנית טקסט לטעינה --</option>
                      {textTemplates.map(template => (
                        <option key={template.id} value={template.id}>
                          {template.name} {template.category ? `(${template.category === 'quote' ? 'הצעת מחיר' : template.category === 'greeting' ? 'ברכה' : template.category === 'pricing' ? 'מחירים' : 'כללי'})` : ''}
                        </option>
                      ))}
                    </select>
                  </div>
                )}
                
                <textarea
                  value={themeFields.body}
                  onChange={(e) => setThemeFields({...themeFields, body: e.target.value})}
                  placeholder="תוכן המייל..."
                  rows={6}
                  className="w-full px-3 py-2.5 border-2 border-gray-300 rounded-lg focus:ring-4 focus:ring-blue-200 focus:border-blue-500 shadow-sm resize-none"
                  required
                />
              </div>

              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="block text-xs font-bold text-gray-900 mb-1">
                    🔘 טקסט כפתור
                  </label>
                  <input
                    type="text"
                    value={themeFields.cta_text}
                    onChange={(e) => setThemeFields({...themeFields, cta_text: e.target.value})}
                    placeholder="צור קשר"
                    className="w-full px-3 py-2 border-2 border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-200 focus:border-blue-500 shadow-sm"
                  />
                </div>
                <div>
                  <label className="block text-xs font-bold text-gray-900 mb-1">
                    🔗 קישור
                  </label>
                  <input
                    type="url"
                    value={themeFields.cta_url}
                    onChange={(e) => setThemeFields({...themeFields, cta_url: e.target.value})}
                    placeholder="https://..."
                    className="w-full px-3 py-2 border-2 border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-200 focus:border-blue-500 shadow-sm"
                  />
                </div>
              </div>

              <div className="bg-yellow-50 border-2 border-yellow-300 rounded-lg p-3">
                <label className="block text-xs font-bold text-yellow-900 mb-1 flex items-center gap-1">
                  <span className="text-lg">⚠️</span>
                  <span>פוטר *</span>
                </label>
                <textarea
                  value={themeFields.footer}
                  onChange={(e) => setThemeFields({...themeFields, footer: e.target.value})}
                  placeholder="פוטר המייל..."
                  rows={2}
                  className="w-full px-3 py-2 border-2 border-yellow-400 rounded-lg focus:ring-2 focus:ring-yellow-200 focus:border-yellow-500 text-xs shadow-sm resize-none"
                  required
                />
              </div>
            </div>

            <div className="flex gap-2 pt-2">
              <Button
                type="submit"
                variant="primary"
                disabled={sending}
                className="flex-1"
              >
                {sending ? 'שולח...' : '✉️ שלח מייל'}
              </Button>
              <Button
                type="button"
                variant="secondary"
                onClick={() => setShowCompose(false)}
              >
                ביטול
              </Button>
            </div>
          </form>
        </div>
      )}

      {/* Email History */}
      {loading ? (
        <div className="text-center py-8">
          <Loader2 className="w-6 h-6 animate-spin mx-auto text-gray-400" />
          <p className="text-sm text-gray-500 mt-2">טוען...</p>
        </div>
      ) : emails.length === 0 ? (
        <div className="text-center py-8 text-gray-500">
          <Mail className="w-12 h-12 mx-auto mb-2 text-gray-400" />
          <p>עדיין לא נשלחו מיילים לליד זה</p>
        </div>
      ) : (
        <div className="space-y-3">
          {emails.map((email) => (
            <div key={email.id} className="border border-gray-200 rounded-lg p-4 hover:bg-gray-50 transition-colors">
              <div className="flex justify-between items-start mb-2">
                <div className="flex-1">
                  <h4 className="font-medium text-gray-900">{email.subject}</h4>
                  <p className="text-sm text-gray-600 mt-1">אל: {email.to_email}</p>
                </div>
                <div>{getStatusBadge(email.status)}</div>
              </div>
              <div className="flex items-center justify-between text-xs text-gray-500 mt-2">
                <span>
                  {email.created_by?.name || 'מערכת'} • {new Date(email.created_at).toLocaleString('he-IL')}
                </span>
                {email.sent_at && (
                  <span>
                    נשלח: {new Date(email.sent_at).toLocaleString('he-IL')}
                  </span>
                )}
              </div>
              {email.error && (
                <div className="mt-2 text-xs text-red-600 bg-red-50 p-2 rounded">
                  שגיאה: {email.error}
                </div>
              )}
            </div>
          ))}
        </div>
      )}
    </Card>
  );
}