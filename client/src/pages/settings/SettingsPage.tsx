import React from 'react';
import React, { useState, useEffect } from 'react';
import { Settings, Save, Eye, EyeOff, Key, MessageCircle, Phone, Zap, Globe, Shield, Bot, Plus, Edit, Trash2 } from 'lucide-react';
import { useQuery, useMutation } from '@tanstack/react-query';
import { queryClient, apiRequest } from '@/lib/queryClient';

// Temporary UI components
const Card = ({ children, className = "" }: any) => (
  <div className={`border border-gray-200 rounded-lg bg-white ${className}`}>{children}</div>
);

const Button = ({ children, className = "", variant = "default", size = "default", ...props }: {
  children: React.ReactNode;
  className?: string;
  variant?: "default" | "outline" | "ghost" | "destructive";
  size?: "default" | "sm";
  [key: string]: any;
}) => {
  const baseClasses = "px-4 py-2 rounded-md font-medium transition-colors inline-flex items-center";
  const variantClasses = {
    default: "bg-blue-600 text-white hover:bg-blue-700",
    outline: "border border-gray-300 bg-white text-gray-700 hover:bg-gray-50",
    ghost: "text-gray-700 hover:bg-gray-100",
    destructive: "bg-red-600 text-white hover:bg-red-700"
  };
  const sizeClasses = {
    default: "px-4 py-2",
    sm: "px-3 py-1 text-sm"
  };
  return (
    <button 
      className={`${baseClasses} ${variantClasses[variant]} ${sizeClasses[size]} ${className}`} 
      {...props}
    >
      {children}
    </button>
  );
};

const Badge = ({ children, className = "", variant = "default" }: {
  children: React.ReactNode;
  className?: string;
  variant?: "default" | "success" | "warning" | "destructive";
}) => {
  const variantClasses = {
    default: "bg-gray-100 text-gray-800",
    success: "bg-green-100 text-green-800",
    warning: "bg-yellow-100 text-yellow-800",
    destructive: "bg-red-100 text-red-800"
  };
  return (
    <span className={`px-2 py-1 text-xs rounded-full ${variantClasses[variant]} ${className}`}>
      {children}
    </span>
  );
};

// Settings interfaces
interface BusinessSettings {
  business_name: string;
  phone_number: string;
  email: string;
  address: string;
  working_hours: string;
  timezone: string;
}

interface AppointmentSettings {
  slot_size_min: number;
  allow_24_7: boolean;
  booking_window_days: number;
  min_notice_min: number;
  opening_hours_json?: Record<string, string[][]>;
}

interface DayHours {
  enabled: boolean;
  hours: string[][];  // [["09:00", "17:00"], ["19:00", "22:00"]]
}

interface IntegrationSettings {
  twilio_enabled: boolean;
  twilio_account_sid?: string;
  twilio_auth_token?: string;
  whatsapp_enabled: boolean;
  whatsapp_provider: 'twilio' | 'baileys';
  openai_enabled: boolean;
  openai_api_key?: string;
  google_stt_enabled: boolean;
  google_tts_enabled: boolean;
}

interface AISettings {
  model: string;
  max_tokens: number;
  temperature: number;
  system_prompt: string;
  response_limit: number;
  language: string;
}

interface FAQ {
  id: number;
  question: string;
  answer: string;
  intent_key?: string | null;
  patterns_json?: string[] | null;
  channels?: string;
  priority?: number;
  lang?: string;
  order_index: number;
  created_at?: string;
}

export function SettingsPage() {
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [activeTab, setActiveTab] = useState<'business' | 'appointments' | 'faqs' | 'integrations' | 'ai' | 'security'>('business');
  const [showSecrets, setShowSecrets] = useState<Record<string, boolean>>({});
  const [faqModalOpen, setFaqModalOpen] = useState(false);
  const [editingFaq, setEditingFaq] = useState<FAQ | null>(null);
  
  // FAQ Query
  const { data: faqs = [], isLoading: faqsLoading, error: faqsError } = useQuery<FAQ[]>({
    queryKey: ['/api/business/faqs'],
    enabled: activeTab === 'faqs'
  });
  
  // FAQ Mutations
  const createFaqMutation = useMutation({
    mutationFn: (data: Partial<FAQ>) =>
      apiRequest('/api/business/faqs', { method: 'POST', body: data }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['/api/business/faqs'] });
      setFaqModalOpen(false);
      alert('שאלה נוצרה בהצלחה!');
    },
    onError: (error) => {
      alert(`שגיאה ביצירת שאלה: ${error}`);
    }
  });
  
  const updateFaqMutation = useMutation({
    mutationFn: ({ id, data }: { id: number; data: Partial<FAQ> }) =>
      apiRequest(`/api/business/faqs/${id}`, { method: 'PUT', body: data }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['/api/business/faqs'] });
      setFaqModalOpen(false);
      setEditingFaq(null);
      alert('שאלה עודכנה בהצלחה!');
    },
    onError: (error) => {
      alert(`שגיאה בעדכון שאלה: ${error}`);
    }
  });
  
  const deleteFaqMutation = useMutation({
    mutationFn: (id: number) =>
      apiRequest(`/api/business/faqs/${id}`, { method: 'DELETE' }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['/api/business/faqs'] });
      alert('שאלה נמחקה בהצלחה!');
    },
    onError: (error) => {
      alert(`שגיאה במחיקת שאלה: ${error}`);
    }
  });
  
  // Settings state
  const [businessSettings, setBusinessSettings] = useState<BusinessSettings>({
    business_name: 'שי דירות ומשרדים בע״מ',
    phone_number: '+972-58-7654321',
    email: 'office@shai-realestate.co.il',
    address: 'רחוב דיזנגוף 100, תל אביב',
    working_hours: '09:00-18:00',
    timezone: 'Asia/Jerusalem'
  });

  const [integrationSettings, setIntegrationSettings] = useState<IntegrationSettings>({
    twilio_enabled: true,
    twilio_account_sid: 'AC***************************',
    twilio_auth_token: '********************************',
    whatsapp_enabled: true,
    whatsapp_provider: 'twilio',
    openai_enabled: true,
    openai_api_key: 'sk-***************************',
    google_stt_enabled: true,
    google_tts_enabled: true
  });

  const [aiSettings, setAISettings] = useState<AISettings>({
    model: 'gpt-4o-mini',
    max_tokens: 150,
    temperature: 0.7,
    system_prompt: 'אתה ליאה, סוכנת נדל"ן ישראלית מומחית בעברית. תמיד תענה בעברית בצורה קצרה ומקצועית.',
    response_limit: 15,
    language: 'he-IL'
  });

  const [appointmentSettings, setAppointmentSettings] = useState<AppointmentSettings>({
    slot_size_min: 60,
    allow_24_7: false,
    booking_window_days: 30,
    min_notice_min: 0
  });

  // ✅ NEW: Working days state (controlled checkboxes)
  const [workingDays, setWorkingDays] = useState({
    sun: true,
    mon: true,
    tue: true,
    wed: true,
    thu: true,
    fri: true,
    sat: true
  });

  useEffect(() => {
    loadSettings();
  }, []);

  const loadSettings = async () => {
    try {
      setLoading(true);
      
      // Load business settings from API
      const response = await fetch('/api/business/current', {
        credentials: 'include'
      });
      
      if (response.ok) {
        const data = await response.json();
        setBusinessSettings({
          business_name: data.name || '',
          phone_number: data.phone_number || '',
          email: data.email || '',
          address: data.address || '',
          working_hours: data.working_hours || '09:00-18:00',
          timezone: data.timezone || 'Asia/Jerusalem'
        });
        
        // Load appointment settings
        setAppointmentSettings({
          slot_size_min: data.slot_size_min || 60,
          allow_24_7: data.allow_24_7 || false,
          booking_window_days: data.booking_window_days || 30,
          min_notice_min: data.min_notice_min || 0,
          opening_hours_json: data.opening_hours_json
        });

        // ✅ NEW: Load working days from opening_hours_json
        if (data.opening_hours_json) {
          const days = data.opening_hours_json;
          setWorkingDays({
            sun: !!days.sun,
            mon: !!days.mon,
            tue: !!days.tue,
            wed: !!days.wed,
            thu: !!days.thu,
            fri: !!days.fri,
            sat: !!days.sat
          });
        }
      } else {
        console.error('Failed to load business settings');
      }
    } catch (error) {
      console.error('Error loading settings:', error);
    } finally {
      setLoading(false);
    }
  };

  const saveBusinessSettings = async () => {
    try {
      setSaving(true);
      
      const response = await fetch('/api/business/current/settings', {
        method: 'PUT',
        headers: {
          'Content-Type': 'application/json',
        },
        credentials: 'include',
        body: JSON.stringify(businessSettings)
      });
      
      if (response.ok) {
        // Show success message
        alert('הגדרות עסק נשמרו בהצלחה');
      } else {
        const error = await response.json();
        alert('שגיאה בשמירת הגדרות: ' + (error.message || 'שגיאה לא ידועה'));
      }
    } catch (error) {
      console.error('Error saving settings:', error);
      alert('שגיאה בשמירת הגדרות');
    } finally {
      setSaving(false);
    }
  };

  const saveAppointmentSettings = async () => {
    try {
      setSaving(true);

      // ✅ FIXED: Preserve existing hours, only add/remove days
      const opening_hours_json: Record<string, string[][]> = {};
      const existingHours = appointmentSettings.opening_hours_json || {};
      const defaultHours = [["09:00", "18:00"]]; // Fallback for new days

      Object.keys(workingDays).forEach((day) => {
        if (workingDays[day as keyof typeof workingDays]) {
          // ✅ Use existing hours if available, otherwise use default
          opening_hours_json[day] = existingHours[day] || defaultHours;
        }
        // ✅ If unchecked, day is removed (not included in opening_hours_json)
      });
      
      const response = await fetch('/api/business/current/settings', {
        method: 'PUT',
        headers: {
          'Content-Type': 'application/json',
        },
        credentials: 'include',
        body: JSON.stringify({
          ...appointmentSettings,
          opening_hours_json  // ✅ Include working days!
        })
      });
      
      if (response.ok) {
        alert('הגדרות תורים נשמרו בהצלחה');
      } else {
        const error = await response.json();
        alert('שגיאה בשמירת הגדרות: ' + (error.message || 'שגיאה לא ידועה'));
      }
    } catch (error) {
      console.error('Error saving appointment settings:', error);
      alert('שגיאה בשמירת הגדרות');
    } finally {
      setSaving(false);
    }
  };

  const handleSave = async () => {
    if (activeTab === 'business') {
      await saveBusinessSettings();
    } else if (activeTab === 'appointments') {
      await saveAppointmentSettings();
    } else {
      // Handle other tabs later
      setSaving(true);
      setTimeout(() => {
        setSaving(false);
        alert('הגדרות נשמרו בהצלחה');
      }, 1000);
    }
  };

  const toggleSecret = (key: string) => {
    setShowSecrets(prev => ({
      ...prev,
      [key]: !prev[key]
    }));
  };

  const maskSecret = (value: string) => {
    if (!value) return '';
    return value.substring(0, 6) + '*'.repeat(Math.max(0, value.length - 6));
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="text-center">
          <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-gray-900 mx-auto mb-4"></div>
          <p>טוען הגדרות...</p>
        </div>
      </div>
    );
  }

  return (
    <div className="flex flex-col h-[calc(100vh-4rem)] bg-gray-50">
      {/* Header */}
      <div className="bg-white border-b border-gray-200 px-6 py-4">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            <Settings className="w-6 h-6 text-gray-600" />
            <h1 className="text-2xl font-bold text-gray-900">הגדרות מערכת</h1>
          </div>
          
          <div className="flex items-center gap-3">
            <Button 
              onClick={handleSave}
              disabled={saving}
            >
              <Save className="w-4 h-4 mr-2" />
              {saving ? 'שומר...' : 'שמור הגדרות'}
            </Button>
          </div>
        </div>
      </div>

      {/* Tabs */}
      <div className="bg-white border-b border-gray-200 px-6">
        <nav className="flex space-x-8" dir="ltr">
          <button
            onClick={() => setActiveTab('business')}
            className={`${
              activeTab === 'business'
                ? 'border-blue-500 text-blue-600'
                : 'border-transparent text-gray-500 hover:text-gray-700 hover:border-gray-300'
            } whitespace-nowrap py-4 px-1 border-b-2 font-medium text-sm flex items-center`}
          >
            <Globe className="w-4 h-4 mr-2" />
            הגדרות עסק
          </button>
          <button
            onClick={() => setActiveTab('appointments')}
            className={`${
              activeTab === 'appointments'
                ? 'border-blue-500 text-blue-600'
                : 'border-transparent text-gray-500 hover:text-gray-700 hover:border-gray-300'
            } whitespace-nowrap py-4 px-1 border-b-2 font-medium text-sm flex items-center`}
            data-testid="tab-appointments"
          >
            <Settings className="w-4 h-4 mr-2" />
            הגדרות תורים
          </button>
          <button
            onClick={() => setActiveTab('faqs')}
            className={`${
              activeTab === 'faqs'
                ? 'border-blue-500 text-blue-600'
                : 'border-transparent text-gray-500 hover:text-gray-700 hover:border-gray-300'
            } whitespace-nowrap py-4 px-1 border-b-2 font-medium text-sm flex items-center`}
            data-testid="tab-faqs"
          >
            <MessageCircle className="w-4 h-4 mr-2" />
            שאלות נפוצות (FAQ)
          </button>
          <button
            onClick={() => setActiveTab('integrations')}
            className={`${
              activeTab === 'integrations'
                ? 'border-blue-500 text-blue-600'
                : 'border-transparent text-gray-500 hover:text-gray-700 hover:border-gray-300'
            } whitespace-nowrap py-4 px-1 border-b-2 font-medium text-sm flex items-center`}
          >
            <Zap className="w-4 h-4 mr-2" />
            אינטגרציות
          </button>
          <button
            onClick={() => setActiveTab('security')}
            className={`${
              activeTab === 'security'
                ? 'border-blue-500 text-blue-600'
                : 'border-transparent text-gray-500 hover:text-gray-700 hover:border-gray-300'
            } whitespace-nowrap py-4 px-1 border-b-2 font-medium text-sm flex items-center`}
          >
            <Shield className="w-4 h-4 mr-2" />
            אבטחה
          </button>
        </nav>
      </div>

      {/* Content */}
      <div className="flex-1 overflow-y-auto p-6">
        {activeTab === 'business' && (
          <div className="max-w-2xl space-y-6">
            <Card className="p-6">
              <h3 className="text-lg font-semibold text-gray-900 mb-4">פרטי עסק</h3>
              <div className="space-y-4">
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">שם העסק</label>
                  <input
                    type="text"
                    value={businessSettings.business_name}
                    onChange={(e) => setBusinessSettings({...businessSettings, business_name: e.target.value})}
                    className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
                  />
                </div>
                
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">מספר טלפון</label>
                  <input
                    type="tel"
                    value={businessSettings.phone_number}
                    onChange={(e) => setBusinessSettings({...businessSettings, phone_number: e.target.value})}
                    className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
                    dir="ltr"
                  />
                </div>
                
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">אימייל</label>
                  <input
                    type="email"
                    value={businessSettings.email}
                    onChange={(e) => setBusinessSettings({...businessSettings, email: e.target.value})}
                    className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
                    dir="ltr"
                  />
                </div>
                
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">כתובת</label>
                  <input
                    type="text"
                    value={businessSettings.address}
                    onChange={(e) => setBusinessSettings({...businessSettings, address: e.target.value})}
                    className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
                  />
                </div>
                
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">שעות פעילות</label>
                  <input
                    type="text"
                    value={businessSettings.working_hours}
                    onChange={(e) => setBusinessSettings({...businessSettings, working_hours: e.target.value})}
                    className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
                    placeholder="09:00-18:00"
                  />
                </div>
              </div>
            </Card>
          </div>
        )}

        {activeTab === 'appointments' && (
          <div className="max-w-2xl space-y-6">
            <Card className="p-6">
              <h3 className="text-lg font-semibold text-gray-900 mb-4">הגדרות קביעת תורים</h3>
              <div className="space-y-4">
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">מרווח זמן בין תורים</label>
                  <select
                    value={appointmentSettings.slot_size_min}
                    onChange={(e) => setAppointmentSettings({...appointmentSettings, slot_size_min: parseInt(e.target.value)})}
                    className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
                    data-testid="select-slot-size"
                  >
                    <option value="15">כל 15 דקות (רבע שעה)</option>
                    <option value="30">כל 30 דקות (חצי שעה)</option>
                    <option value="45">כל 45 דקות (שלושת רבעי שעה)</option>
                    <option value="60">כל שעה</option>
                    <option value="75">כל שעה ורבע (75 דקות)</option>
                    <option value="90">כל שעה וחצי (90 דקות)</option>
                    <option value="105">כל שעה ושלושת רבעי (105 דקות)</option>
                    <option value="120">כל שעתיים (120 דקות)</option>
                  </select>
                  <p className="mt-1 text-sm text-gray-500">
                    קובע כל כמה זמן ניתן לקבוע תור חדש
                  </p>
                </div>

                <div className="flex items-center justify-between p-4 bg-gray-50 rounded-lg">
                  <div>
                    <h4 className="font-medium text-gray-900">פתוח 24/7</h4>
                    <p className="text-sm text-gray-600">אפשר קביעת תורים בכל שעה ביום</p>
                  </div>
                  <label className="relative inline-flex items-center cursor-pointer">
                    <input
                      type="checkbox"
                      checked={appointmentSettings.allow_24_7}
                      onChange={(e) => setAppointmentSettings({...appointmentSettings, allow_24_7: e.target.checked})}
                      className="sr-only peer"
                      data-testid="checkbox-247"
                    />
                    <div className="w-11 h-6 bg-gray-200 peer-focus:outline-none peer-focus:ring-4 peer-focus:ring-blue-300 rounded-full peer peer-checked:after:translate-x-full peer-checked:after:border-white after:content-[''] after:absolute after:top-[2px] after:left-[2px] after:bg-white after:border-gray-300 after:border after:rounded-full after:h-5 after:w-5 after:transition-all peer-checked:bg-blue-600"></div>
                  </label>
                </div>

                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">חלון הזמנה (ימים קדימה)</label>
                  <input
                    type="number"
                    min="1"
                    max="365"
                    value={appointmentSettings.booking_window_days}
                    onChange={(e) => setAppointmentSettings({...appointmentSettings, booking_window_days: parseInt(e.target.value)})}
                    className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
                    data-testid="input-booking-window"
                  />
                  <p className="mt-1 text-sm text-gray-500">
                    כמה ימים קדימה לקוחות יכולים לקבוע תורים
                  </p>
                </div>

                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">הודעה מוקדמת מינימלית (דקות)</label>
                  <input
                    type="number"
                    min="0"
                    max="1440"
                    value={appointmentSettings.min_notice_min}
                    onChange={(e) => setAppointmentSettings({...appointmentSettings, min_notice_min: parseInt(e.target.value)})}
                    className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
                    data-testid="input-min-notice"
                  />
                  <p className="mt-1 text-sm text-gray-500">
                    כמה זמן מראש לקוח צריך להודיע לפני תור (0 = ניתן לקבוע מיידית)
                  </p>
                </div>

                {!appointmentSettings.allow_24_7 && (
                  <div className="border-t pt-4 mt-6">
                    <h4 className="font-medium text-gray-900 mb-4">שעות פעילות</h4>
                    <div className="grid grid-cols-2 gap-4">
                      <div>
                        <label className="block text-sm font-medium text-gray-700 mb-1">שעת פתיחה</label>
                        <select 
                          className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
                          defaultValue="09:00"
                          data-testid="select-opening-time"
                        >
                          {Array.from({length: 24}, (_, i) => {
                            const hour = i.toString().padStart(2, '0');
                            return <option key={i} value={`${hour}:00`}>{`${hour}:00`}</option>;
                          })}
                        </select>
                      </div>
                      <div>
                        <label className="block text-sm font-medium text-gray-700 mb-1">שעת סגירה</label>
                        <select 
                          className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
                          defaultValue="18:00"
                          data-testid="select-closing-time"
                        >
                          {Array.from({length: 24}, (_, i) => {
                            const hour = i.toString().padStart(2, '0');
                            return <option key={i} value={`${hour}:00`}>{`${hour}:00`}</option>;
                          })}
                        </select>
                      </div>
                    </div>
                    <p className="mt-2 text-sm text-gray-500">
                      שעות אלה יחולו על כל ימות השבוע. לשעות מפורטות לפי יום, השתמש במצב פתוח 24/7 והגדר בהגדרות מתקדמות.
                    </p>

                    <div className="mt-4">
                      <label className="block text-sm font-medium text-gray-700 mb-2">ימי פעילות</label>
                      <div className="grid grid-cols-4 gap-2">
                        {[
                          { name: 'ראשון', value: 'sun' },
                          { name: 'שני', value: 'mon' },
                          { name: 'שלישי', value: 'tue' },
                          { name: 'רביעי', value: 'wed' },
                          { name: 'חמישי', value: 'thu' },
                          { name: 'שישי', value: 'fri' },
                          { name: 'שבת', value: 'sat' }
                        ].map((day) => (
                          <label key={day.value} className="flex items-center space-x-2 space-x-reverse cursor-pointer p-2 border rounded hover:bg-gray-50">
                            <input
                              type="checkbox"
                              checked={workingDays[day.value as keyof typeof workingDays]}
                              onChange={(e) => setWorkingDays({
                                ...workingDays,
                                [day.value]: e.target.checked
                              })}
                              className="rounded text-blue-600 focus:ring-blue-500"
                              data-testid={`checkbox-day-${day.value}`}
                            />
                            <span className="text-sm text-gray-700">{day.name}</span>
                          </label>
                        ))}
                      </div>
                      <p className="mt-2 text-sm text-gray-500">
                        בחר את הימים שבהם העסק פעיל לקביעת תורים
                      </p>
                    </div>
                  </div>
                )}

                <div className="border-t pt-4 mt-6">
                  <h4 className="font-medium text-gray-900 mb-2">סיכום הגדרות</h4>
                  <div className="space-y-2 text-sm text-gray-600">
                    <p>• תורים כל <strong>{appointmentSettings.slot_size_min}</strong> דקות</p>
                    <p>• פתוח <strong>{appointmentSettings.allow_24_7 ? '24/7' : 'בשעות מוגדרות'}</strong></p>
                    <p>• ניתן לקבוע עד <strong>{appointmentSettings.booking_window_days}</strong> ימים קדימה</p>
                    <p>• הודעה מוקדמת: <strong>{appointmentSettings.min_notice_min === 0 ? 'לא נדרשת' : `${appointmentSettings.min_notice_min} דקות`}</strong></p>
                  </div>
                </div>
              </div>
            </Card>
          </div>
        )}

        {activeTab === 'faqs' && (
          <div className="max-w-4xl space-y-6">
            <Card className="p-6">
              <div className="flex items-center justify-between mb-6">
                <div>
                  <h3 className="text-lg font-semibold text-gray-900">שאלות נפוצות (FAQ)</h3>
                  <p className="text-sm text-gray-600 mt-1">
                    הגדר שאלות ותשובות נפוצות שהסוכן יענה עליהן מהר (פחות משנייה וחצי)
                  </p>
                </div>
                <Button 
                  onClick={() => {
                    setEditingFaq(null);
                    setFaqModalOpen(true);
                  }}
                  variant="outline"
                  data-testid="button-add-faq"
                >
                  <Plus className="w-4 h-4 mr-2" />
                  הוסף שאלה
                </Button>
              </div>

              <div className="space-y-4">
                <div className="bg-blue-50 border border-blue-200 rounded-lg p-4">
                  <h4 className="font-medium text-blue-900 mb-2">איך זה עובד?</h4>
                  <ul className="text-sm text-blue-800 space-y-1">
                    <li>• כאשר לקוח שואל שאלה, המערכת מחפשת התאמה ב-FAQs שלך</li>
                    <li>• אם נמצאה התאמה - תגיב מיידית (פחות משנייה וחצי)</li>
                    <li>• אם לא - הסוכן המלא יטפל בשאלה (4-5 שניות)</li>
                    <li>• שאלות טובות: מחיר, כתובת, שעות פעילות, מתקנים זמינים</li>
                  </ul>
                </div>

                <div className="border-t pt-4">
                  <div className="flex items-center justify-between mb-3">
                    <h4 className="font-medium text-gray-900">השאלות הנפוצות שלך</h4>
                    {faqs.length > 0 && (
                      <span className="text-sm text-gray-500">{faqs.length} שאלות</span>
                    )}
                  </div>

                  {faqsLoading && (
                    <div className="text-center py-8 text-gray-500">טוען...</div>
                  )}

                  {faqsError && (
                    <div className="bg-red-50 border border-red-200 rounded-lg p-4 text-red-800">
                      שגיאה בטעינת שאלות נפוצות
                    </div>
                  )}

                  {!faqsLoading && !faqsError && faqs.length === 0 && (
                    <div className="text-center py-8">
                      <MessageCircle className="w-12 h-12 text-gray-300 mx-auto mb-3" />
                      <p className="text-gray-500">עדיין לא הוספת שאלות נפוצות</p>
                      <p className="text-sm text-gray-400 mt-1">לחץ על "הוסף שאלה" כדי להתחיל</p>
                    </div>
                  )}

                  {!faqsLoading && !faqsError && faqs.length > 0 && (
                    <div className="space-y-3">
                      {faqs.map((faq) => (
                        <div key={faq.id} className="border rounded-lg p-4" data-testid={`faq-item-${faq.id}`}>
                          <div className="flex items-start justify-between">
                            <div className="flex-1">
                              <p className="font-medium text-gray-900" data-testid={`faq-question-${faq.id}`}>
                                {faq.question}
                              </p>
                              <p className="text-sm text-gray-600 mt-1" data-testid={`faq-answer-${faq.id}`}>
                                {faq.answer}
                              </p>
                            </div>
                            <div className="flex items-center gap-2 mr-2">
                              <button 
                                onClick={() => {
                                  setEditingFaq(faq);
                                  setFaqModalOpen(true);
                                }}
                                className="text-blue-600 hover:text-blue-700 p-1"
                                data-testid={`button-edit-faq-${faq.id}`}
                              >
                                <Edit className="w-4 h-4" />
                              </button>
                              <button 
                                onClick={() => {
                                  if (confirm(`למחוק את השאלה "${faq.question}"?`)) {
                                    deleteFaqMutation.mutate(faq.id);
                                  }
                                }}
                                className="text-red-600 hover:text-red-700 p-1"
                                disabled={deleteFaqMutation.isPending}
                                data-testid={`button-delete-faq-${faq.id}`}
                              >
                                <Trash2 className="w-4 h-4" />
                              </button>
                            </div>
                          </div>
                        </div>
                      ))}
                    </div>
                  )}
                </div>
              </div>
            </Card>
          </div>
        )}

        {activeTab === 'integrations' && (
          <div className="max-w-4xl space-y-6">
            {/* Twilio */}
            <Card className="p-6">
              <div className="flex items-center justify-between mb-4">
                <div className="flex items-center gap-3">
                  <Phone className="w-6 h-6 text-blue-600" />
                  <h3 className="text-lg font-semibold text-gray-900">Twilio</h3>
                  <Badge variant={integrationSettings.twilio_enabled ? 'success' : 'default'}>
                    {integrationSettings.twilio_enabled ? 'פעיל' : 'לא פעיל'}
                  </Badge>
                </div>
                <label className="relative inline-flex items-center cursor-pointer">
                  <input
                    type="checkbox"
                    checked={integrationSettings.twilio_enabled}
                    onChange={(e) => setIntegrationSettings({...integrationSettings, twilio_enabled: e.target.checked})}
                    className="sr-only peer"
                  />
                  <div className="w-11 h-6 bg-gray-200 peer-focus:outline-none peer-focus:ring-4 peer-focus:ring-blue-300 rounded-full peer peer-checked:after:translate-x-full peer-checked:after:border-white after:content-[''] after:absolute after:top-[2px] after:left-[2px] after:bg-white after:border-gray-300 after:border after:rounded-full after:h-5 after:w-5 after:transition-all peer-checked:bg-blue-600"></div>
                </label>
              </div>
              
              {integrationSettings.twilio_enabled && (
                <div className="space-y-4">
                  <div>
                    <label className="block text-sm font-medium text-gray-700 mb-1">Account SID</label>
                    <div className="relative">
                      <input
                        type={showSecrets.twilio_sid ? "text" : "password"}
                        value={integrationSettings.twilio_account_sid}
                        onChange={(e) => setIntegrationSettings({...integrationSettings, twilio_account_sid: e.target.value})}
                        className="w-full px-3 py-2 pr-10 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
                        dir="ltr"
                      />
                      <button
                        type="button"
                        onClick={() => toggleSecret('twilio_sid')}
                        className="absolute inset-y-0 right-0 pr-3 flex items-center"
                      >
                        {showSecrets.twilio_sid ? <EyeOff className="w-4 h-4" /> : <Eye className="w-4 h-4" />}
                      </button>
                    </div>
                  </div>
                  
                  <div>
                    <label className="block text-sm font-medium text-gray-700 mb-1">Auth Token</label>
                    <div className="relative">
                      <input
                        type={showSecrets.twilio_token ? "text" : "password"}
                        value={integrationSettings.twilio_auth_token}
                        onChange={(e) => setIntegrationSettings({...integrationSettings, twilio_auth_token: e.target.value})}
                        className="w-full px-3 py-2 pr-10 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
                        dir="ltr"
                      />
                      <button
                        type="button"
                        onClick={() => toggleSecret('twilio_token')}
                        className="absolute inset-y-0 right-0 pr-3 flex items-center"
                      >
                        {showSecrets.twilio_token ? <EyeOff className="w-4 h-4" /> : <Eye className="w-4 h-4" />}
                      </button>
                    </div>
                  </div>
                </div>
              )}
            </Card>

            {/* WhatsApp */}
            <Card className="p-6">
              <div className="flex items-center justify-between mb-4">
                <div className="flex items-center gap-3">
                  <MessageCircle className="w-6 h-6 text-green-600" />
                  <h3 className="text-lg font-semibold text-gray-900">WhatsApp</h3>
                  <Badge variant={integrationSettings.whatsapp_enabled ? 'success' : 'default'}>
                    {integrationSettings.whatsapp_enabled ? 'פעיל' : 'לא פעיל'}
                  </Badge>
                </div>
                <label className="relative inline-flex items-center cursor-pointer">
                  <input
                    type="checkbox"
                    checked={integrationSettings.whatsapp_enabled}
                    onChange={(e) => setIntegrationSettings({...integrationSettings, whatsapp_enabled: e.target.checked})}
                    className="sr-only peer"
                  />
                  <div className="w-11 h-6 bg-gray-200 peer-focus:outline-none peer-focus:ring-4 peer-focus:ring-blue-300 rounded-full peer peer-checked:after:translate-x-full peer-checked:after:border-white after:content-[''] after:absolute after:top-[2px] after:left-[2px] after:bg-white after:border-gray-300 after:border after:rounded-full after:h-5 after:w-5 after:transition-all peer-checked:bg-blue-600"></div>
                </label>
              </div>
              
              {integrationSettings.whatsapp_enabled && (
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">ספק</label>
                  <select
                    value={integrationSettings.whatsapp_provider}
                    onChange={(e) => setIntegrationSettings({...integrationSettings, whatsapp_provider: e.target.value as 'twilio' | 'baileys'})}
                    className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
                  >
                    <option value="twilio">Twilio WhatsApp API</option>
                    <option value="baileys">Baileys (WhatsApp Web)</option>
                  </select>
                </div>
              )}
            </Card>

            {/* OpenAI */}
            <Card className="p-6">
              <div className="flex items-center justify-between mb-4">
                <div className="flex items-center gap-3">
                  <Bot className="w-6 h-6 text-purple-600" />
                  <h3 className="text-lg font-semibold text-gray-900">OpenAI</h3>
                  <Badge variant={integrationSettings.openai_enabled ? 'success' : 'default'}>
                    {integrationSettings.openai_enabled ? 'פעיל' : 'לא פעיל'}
                  </Badge>
                </div>
                <label className="relative inline-flex items-center cursor-pointer">
                  <input
                    type="checkbox"
                    checked={integrationSettings.openai_enabled}
                    onChange={(e) => setIntegrationSettings({...integrationSettings, openai_enabled: e.target.checked})}
                    className="sr-only peer"
                  />
                  <div className="w-11 h-6 bg-gray-200 peer-focus:outline-none peer-focus:ring-4 peer-focus:ring-blue-300 rounded-full peer peer-checked:after:translate-x-full peer-checked:after:border-white after:content-[''] after:absolute after:top-[2px] after:left-[2px] after:bg-white after:border-gray-300 after:border after:rounded-full after:h-5 after:w-5 after:transition-all peer-checked:bg-blue-600"></div>
                </label>
              </div>
              
              {integrationSettings.openai_enabled && (
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">API Key</label>
                  <div className="relative">
                    <input
                      type={showSecrets.openai_key ? "text" : "password"}
                      value={integrationSettings.openai_api_key}
                      onChange={(e) => setIntegrationSettings({...integrationSettings, openai_api_key: e.target.value})}
                      className="w-full px-3 py-2 pr-10 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
                      dir="ltr"
                    />
                    <button
                      type="button"
                      onClick={() => toggleSecret('openai_key')}
                      className="absolute inset-y-0 right-0 pr-3 flex items-center"
                    >
                      {showSecrets.openai_key ? <EyeOff className="w-4 h-4" /> : <Eye className="w-4 h-4" />}
                    </button>
                  </div>
                </div>
              )}
            </Card>
          </div>
        )}

        {activeTab === 'security' && (
          <div className="max-w-2xl space-y-6">
            <Card className="p-6">
              <h3 className="text-lg font-semibold text-gray-900 mb-4">הגדרות אבטחה</h3>
              <div className="space-y-6">
                <div className="flex items-center justify-between p-4 bg-gray-50 rounded-lg">
                  <div>
                    <h4 className="font-medium text-gray-900">CSRF Protection</h4>
                    <p className="text-sm text-gray-600">הגנה מפני התקפות Cross-Site Request Forgery</p>
                  </div>
                  <Badge variant="success">פעיל</Badge>
                </div>
                
                <div className="flex items-center justify-between p-4 bg-gray-50 rounded-lg">
                  <div>
                    <h4 className="font-medium text-gray-900">Session Security</h4>
                    <p className="text-sm text-gray-600">הגנה על sessions עם HTTP-only cookies</p>
                  </div>
                  <Badge variant="success">פעיל</Badge>
                </div>
                
                <div className="flex items-center justify-between p-4 bg-gray-50 rounded-lg">
                  <div>
                    <h4 className="font-medium text-gray-900">Role-Based Access</h4>
                    <p className="text-sm text-gray-600">בקרת גישה מבוססת תפקידים</p>
                  </div>
                  <Badge variant="success">פעיל</Badge>
                </div>
                
                <div className="border-t pt-4">
                  <h4 className="font-medium text-gray-900 mb-2">פעולות אבטחה</h4>
                  <div className="space-y-2">
                    <Button variant="outline" className="w-full justify-center">
                      <Key className="w-4 h-4 mr-2" />
                      רענן מפתחות API
                    </Button>
                    <Button variant="outline" className="w-full justify-center">
                      <Shield className="w-4 h-4 mr-2" />
                      בדוק אבטחת מערכת
                    </Button>
                  </div>
                </div>
              </div>
            </Card>
          </div>
        )}
      </div>

      {/* FAQ Modal */}
      {faqModalOpen && (
        <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50 p-4">
          <div className="bg-white rounded-lg max-w-2xl w-full p-6 max-h-[90vh] overflow-y-auto">
            <h3 className="text-lg font-semibold text-gray-900 mb-4">
              {editingFaq ? 'עריכת שאלה נפוצה' : 'הוספת שאלה נפוצה'}
            </h3>
            
            <form
              onSubmit={(e) => {
                e.preventDefault();
                const formData = new FormData(e.currentTarget);
                const question = formData.get('question') as string;
                const answer = formData.get('answer') as string;
                const intent_key = formData.get('intent_key') as string;
                const patterns = formData.get('patterns') as string;
                const channels = formData.get('channels') as string;
                const priority = formData.get('priority') as string;
                const lang = formData.get('lang') as string;
                
                if (!question?.trim() || !answer?.trim()) {
                  alert('נא למלא את כל השדות');
                  return;
                }
                
                const data = {
                  question: question.trim(),
                  answer: answer.trim(),
                  intent_key: intent_key?.trim() || null,
                  patterns_json: patterns?.trim() ? patterns.split('\n').map(p => p.trim()).filter(Boolean) : null,
                  channels: channels || 'voice',
                  priority: priority ? parseInt(priority) : 0,
                  lang: lang || 'he-IL'
                };
                
                if (editingFaq) {
                  updateFaqMutation.mutate({ id: editingFaq.id, data });
                } else {
                  createFaqMutation.mutate(data);
                }
              }}
              className="space-y-4"
            >
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">
                  שאלה <span className="text-red-500">*</span>
                </label>
                <input
                  type="text"
                  name="question"
                  defaultValue={editingFaq?.question || ''}
                  placeholder="למשל: מה המחיר?"
                  className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
                  maxLength={200}
                  required
                  data-testid="input-faq-question"
                />
                <p className="text-xs text-gray-500 mt-1">מקסימום 200 תווים</p>
              </div>

              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">
                  תשובה <span className="text-red-500">*</span>
                </label>
                <textarea
                  name="answer"
                  defaultValue={editingFaq?.answer || ''}
                  placeholder="למשל: המחיר מתחיל מ-500,000 ש״ח"
                  className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500 min-h-[100px]"
                  maxLength={2000}
                  required
                  data-testid="input-faq-answer"
                />
                <p className="text-xs text-gray-500 mt-1">מקסימום 2000 תווים</p>
              </div>

              {/* Advanced Fields */}
              <div className="border-t pt-4 space-y-3">
                <h4 className="text-sm font-semibold text-gray-700">הגדרות מתקדמות (אופציונלי)</h4>
                
                <div className="grid grid-cols-2 gap-3">
                  <div>
                    <label className="block text-xs font-medium text-gray-600 mb-1">מזהה כוונה</label>
                    <input
                      type="text"
                      name="intent_key"
                      defaultValue={editingFaq?.intent_key || ''}
                      placeholder="price, hours, location"
                      className="w-full px-2 py-1 text-sm border border-gray-300 rounded-md"
                      data-testid="input-faq-intent"
                    />
                  </div>
                  
                  <div>
                    <label className="block text-xs font-medium text-gray-600 mb-1">עדיפות</label>
                    <input
                      type="number"
                      name="priority"
                      defaultValue={editingFaq?.priority ?? 0}
                      min="0"
                      max="10"
                      className="w-full px-2 py-1 text-sm border border-gray-300 rounded-md"
                      data-testid="input-faq-priority"
                    />
                  </div>
                </div>

                <div className="grid grid-cols-2 gap-3">
                  <div>
                    <label className="block text-xs font-medium text-gray-600 mb-1">ערוצים</label>
                    <select
                      name="channels"
                      defaultValue={editingFaq?.channels || 'voice'}
                      className="w-full px-2 py-1 text-sm border border-gray-300 rounded-md"
                      data-testid="select-faq-channels"
                    >
                      <option value="voice">טלפון בלבד</option>
                      <option value="whatsapp">WhatsApp בלבד</option>
                      <option value="both">שניהם</option>
                    </select>
                  </div>
                  
                  <div>
                    <label className="block text-xs font-medium text-gray-600 mb-1">שפה</label>
                    <select
                      name="lang"
                      defaultValue={editingFaq?.lang || 'he-IL'}
                      className="w-full px-2 py-1 text-sm border border-gray-300 rounded-md"
                      data-testid="select-faq-lang"
                    >
                      <option value="he-IL">עברית</option>
                      <option value="en-US">אנגלית</option>
                      <option value="ar">ערבית</option>
                    </select>
                  </div>
                </div>

                <div>
                  <label className="block text-xs font-medium text-gray-600 mb-1">תבניות מילות מפתח (שורה לכל תבנית)</label>
                  <textarea
                    name="patterns"
                    defaultValue={editingFaq?.patterns_json?.join('\n') || ''}
                    placeholder="מחיר&#10;כמה עולה&#10;\\bמחיר\\b"
                    className="w-full px-2 py-1 text-sm border border-gray-300 rounded-md min-h-[60px] font-mono"
                    data-testid="input-faq-patterns"
                  />
                  <p className="text-xs text-gray-500 mt-1">תומך ב-regex (למשל: \bמילה\b)</p>
                </div>
              </div>

              <div className="flex gap-2 justify-end pt-4 border-t">
                <Button
                  type="button"
                  variant="outline"
                  onClick={() => {
                    setFaqModalOpen(false);
                    setEditingFaq(null);
                  }}
                  disabled={createFaqMutation.isPending || updateFaqMutation.isPending}
                  data-testid="button-cancel-faq"
                >
                  ביטול
                </Button>
                <Button
                  type="submit"
                  disabled={createFaqMutation.isPending || updateFaqMutation.isPending}
                  data-testid="button-save-faq"
                >
                  {createFaqMutation.isPending || updateFaqMutation.isPending ? 'שומר...' : 'שמור'}
                </Button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
}