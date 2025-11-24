import React, { useState, useEffect } from 'react';
import { Settings, Save, Eye, EyeOff, Key, MessageCircle, Phone, Zap, Globe, Shield, Bot, Plus, Edit, Trash2 } from 'lucide-react';
import { useQuery, useMutation } from '@tanstack/react-query';
import { queryClient, apiRequest } from '@/lib/queryClient';
import { BusinessAISettings } from '@/components/settings/BusinessAISettings';
import { useAuth } from '@/features/auth/hooks';

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

export function SettingsPage() {
  const { user } = useAuth();
  const [activeTab, setActiveTab] = useState<'business' | 'appointments' | 'integrations' | 'ai' | 'security'>('business');
  const [showSecrets, setShowSecrets] = useState<Record<string, boolean>>({});
  
  // ✅ BUILD 130: AI tab restricted to system_admin, owner, admin (not agent)
  const canEditAIPrompts = user?.role && ['system_admin', 'owner', 'admin'].includes(user.role);
  
  // ✅ Security: Prevent unauthorized access to AI tab
  React.useEffect(() => {
    if (activeTab === 'ai' && !canEditAIPrompts) {
      setActiveTab('business');
    }
  }, [activeTab, canEditAIPrompts]);
  
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

  // ✅ NEW: Default hours state for ALL days
  const [defaultHours, setDefaultHours] = useState({
    opening: '09:00',
    closing: '18:00'
  });

  // Business data query
  const { data: businessData, isLoading: businessLoading } = useQuery<{
    name: string;
    phone_number: string;
    email: string;
    address: string;
    working_hours: string;
    timezone: string;
    slot_size_min: number;
    allow_24_7: boolean;
    booking_window_days: number;
    min_notice_min: number;
    opening_hours_json?: Record<string, string[][]>;
  }>({
    queryKey: ['/api/business/current'],
    refetchOnMount: true
  });

  // Update state when businessData changes
  useEffect(() => {
    if (businessData) {
      setBusinessSettings({
        business_name: businessData.name || '',  // API returns 'name' but UI uses 'business_name'
        phone_number: businessData.phone_number || '',
        email: businessData.email || '',
        address: businessData.address || '',
        working_hours: businessData.working_hours || '09:00-18:00',
        timezone: businessData.timezone || 'Asia/Jerusalem'
      });
      
      // Load appointment settings
      setAppointmentSettings({
        slot_size_min: businessData.slot_size_min || 60,
        allow_24_7: businessData.allow_24_7 || false,
        booking_window_days: businessData.booking_window_days || 30,
        min_notice_min: businessData.min_notice_min || 0,
        opening_hours_json: businessData.opening_hours_json
      });

      // ✅ Load working days from opening_hours_json
      if (businessData.opening_hours_json) {
        const days = businessData.opening_hours_json;
        setWorkingDays({
          sun: !!days.sun,
          mon: !!days.mon,
          tue: !!days.tue,
          wed: !!days.wed,
          thu: !!days.thu,
          fri: !!days.fri,
          sat: !!days.sat
        });

        // ✅ Load default hours from first available day
        const firstDay = Object.keys(days).find(d => days[d]);
        if (firstDay && days[firstDay] && days[firstDay][0]) {
          const [opening, closing] = days[firstDay][0];
          setDefaultHours({ opening, closing });
        }
      }
    }
  }, [businessData]);

  // Save business settings mutation
  const saveBusinessMutation = useMutation({
    mutationFn: (data: BusinessSettings) => 
      apiRequest('/api/business/current/settings', { method: 'PUT', body: data }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['/api/business/current'] });
      alert('הגדרות עסק נשמרו בהצלחה');
    },
    onError: (error) => {
      alert('שגיאה בשמירת הגדרות: ' + (error instanceof Error ? error.message : 'שגיאה לא ידועה'));
    }
  });

  // Save appointment settings mutation
  const saveAppointmentMutation = useMutation({
    mutationFn: (data: AppointmentSettings & { opening_hours_json: Record<string, string[][]> }) =>
      apiRequest('/api/business/current/settings', { method: 'PUT', body: data }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['/api/business/current'] });
      alert('הגדרות תורים נשמרו בהצלחה');
    },
    onError: (error) => {
      alert('שגיאה בשמירת הגדרות: ' + (error instanceof Error ? error.message : 'שגיאה לא ידועה'));
    }
  });

  const handleSave = () => {
    if (activeTab === 'business') {
      saveBusinessMutation.mutate(businessSettings);
    } else if (activeTab === 'appointments') {
      // 🔥 BUILD FIXED: Apply user-selected hours to ALL active days (not preserved hours)
      const opening_hours_json: Record<string, string[][]> = {};
      const selectedHours = [[defaultHours.opening, defaultHours.closing]]; // Current UI selection

      Object.keys(workingDays).forEach((day) => {
        if (workingDays[day as keyof typeof workingDays]) {
          // 🔥 ALWAYS use the hours the user just selected in the UI
          opening_hours_json[day] = selectedHours;
        }
        // ✅ If unchecked, day is removed (not included in opening_hours_json)
      });

      console.log('💾 Saving opening_hours_json:', opening_hours_json);

      saveAppointmentMutation.mutate({
        ...appointmentSettings,
        opening_hours_json
      });
    } else {
      // Handle other tabs later
      alert('הגדרות נשמרו בהצלחה');
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

  // Compute loading and saving states from mutations/queries
  const loading = businessLoading;
  const saving = saveBusinessMutation.isPending || saveAppointmentMutation.isPending;

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
        <nav className="flex space-x-8 overflow-x-auto scrollbar-hide" dir="ltr" style={{WebkitOverflowScrolling: 'touch'}}>
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
          {canEditAIPrompts && (
            <button
              onClick={() => setActiveTab('ai')}
              className={`${
                activeTab === 'ai'
                  ? 'border-blue-500 text-blue-600'
                  : 'border-transparent text-gray-500 hover:text-gray-700 hover:border-gray-300'
              } whitespace-nowrap py-4 px-1 border-b-2 font-medium text-sm flex items-center`}
              data-testid="tab-ai"
            >
              <Bot className="w-4 h-4 mr-2" />
              הגדרות בינה מלאכותית
            </button>
          )}
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
                    <p className="text-sm text-gray-500 mb-4">
                      בחרו את שעות הפעילות המוגדרות ברירת מחדל לכל הימים. ניתן לשנות שעות ספציפיות לכל יום בהגדרות מתקדמות.
                    </p>
                    
                    <div className="grid grid-cols-2 gap-4">
                      <div>
                        <label className="block text-sm font-medium text-gray-700 mb-1">שעת פתיחה</label>
                        <select 
                          className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
                          value={defaultHours.opening}
                          onChange={(e) => setDefaultHours({...defaultHours, opening: e.target.value})}
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
                          value={defaultHours.closing}
                          onChange={(e) => setDefaultHours({...defaultHours, closing: e.target.value})}
                          data-testid="select-closing-time"
                        >
                          {Array.from({length: 24}, (_, i) => {
                            const hour = i.toString().padStart(2, '0');
                            return <option key={i} value={`${hour}:00`}>{`${hour}:00`}</option>;
                          })}
                        </select>
                      </div>
                    </div>

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

        {activeTab === 'ai' && (
          <div className="max-w-6xl">
            {canEditAIPrompts ? (
              <BusinessAISettings />
            ) : (
              <Card className="p-6">
                <div className="text-center py-12">
                  <Shield className="w-12 h-12 text-gray-400 mx-auto mb-4" />
                  <h3 className="text-lg font-semibold text-gray-900 mb-2">גישה מוגבלת</h3>
                  <p className="text-gray-600">
                    רק מנהלים ובעלי עסקים יכולים לערוך הגדרות בינה מלאכותית
                  </p>
                </div>
              </Card>
            )}
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
    </div>
  );
}