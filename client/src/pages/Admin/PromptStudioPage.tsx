/**
 * PromptStudioPage - AI Prompt Management Studio
 * Provides prompt creation, testing, voice configuration, and queue settings
 */
import React, { useState, useEffect } from 'react';
import { useSearchParams } from 'react-router-dom';
import { 
  Bot, 
  Wand2, 
  Mic, 
  AlertCircle,
  Settings,
  Sparkles
} from 'lucide-react';
import { http } from '../../services/http';
import { useAuth } from '../../features/auth/hooks';
import { PromptBuilderChat } from '../../components/settings/PromptBuilderChat';
import { BusinessAISettings } from '../../components/settings/BusinessAISettings';

// Temporary UI components
const Card = ({ children, className = "" }: any) => (
  <div className={`border border-gray-200 rounded-lg bg-white ${className}`}>{children}</div>
);

interface AppointmentSettings {
  slot_size_min: number;
  allow_24_7: boolean;
  booking_window_days: number;
  min_notice_min: number;
  opening_hours_json?: Record<string, string[][]>;
}

export function PromptStudioPage() {
  const { user } = useAuth();
  // ✅ URL-based tab navigation for search and refresh persistence
  const [searchParams, setSearchParams] = useSearchParams();
  const tabFromUrl = searchParams.get('tab') as 'prompts' | 'builder' | 'appointments' | null;
  const [activeTab, setActiveTab] = useState<'prompts' | 'builder' | 'appointments'>(tabFromUrl || 'prompts');
  const [showChatBuilder, setShowChatBuilder] = useState(false);
  const [smartGenChannel, setSmartGenChannel] = useState<'calls' | 'whatsapp'>('calls');
  const [saving, setSaving] = useState(false);
  
  // ✅ Sync activeTab with URL
  useEffect(() => {
    if (tabFromUrl && tabFromUrl !== activeTab) {
      setActiveTab(tabFromUrl);
    }
  }, [tabFromUrl]);
  
  // ✅ Update URL when tab changes
  const handleTabChange = (tab: 'prompts' | 'builder' | 'appointments') => {
    setActiveTab(tab);
    setSearchParams({ tab });
  };
  
  // Appointment settings state
  const [appointmentSettings, setAppointmentSettings] = useState<AppointmentSettings>({
    slot_size_min: 60,
    allow_24_7: false,
    booking_window_days: 30,
    min_notice_min: 0
  });
  
  const [workingDays, setWorkingDays] = useState({
    sun: true,
    mon: true,
    tue: true,
    wed: true,
    thu: true,
    fri: true,
    sat: true
  });
  
  const [defaultHours, setDefaultHours] = useState({
    opening: '09:00',
    closing: '18:00'
  });
  
  // Load appointment settings
  useEffect(() => {
    loadAppointmentSettings();
  }, []);
  
  const loadAppointmentSettings = async () => {
    try {
      const data = await http.get<any>('/api/business/current');
      if (data) {
        setAppointmentSettings({
          slot_size_min: data.slot_size_min || 60,
          allow_24_7: data.allow_24_7 || false,
          booking_window_days: data.booking_window_days || 30,
          min_notice_min: data.min_notice_min || 0,
          opening_hours_json: data.opening_hours_json
        });
        
        // Load working days and hours if available
        if (data.opening_hours_json) {
          const newWorkingDays: any = {};
          Object.keys(data.opening_hours_json).forEach(day => {
            newWorkingDays[day] = data.opening_hours_json[day].length > 0;
          });
          setWorkingDays({ ...workingDays, ...newWorkingDays });
        }
      }
    } catch (err) {
      console.error('Failed to load appointment settings:', err);
    }
  };

  const handleSaveGeneratedPrompt = async (promptText: string, channel: 'calls' | 'whatsapp', metadata: any) => {
    setSaving(true);
    try {
      await http.post('/api/ai/smart_prompt_generator/save', {
        prompt_text: promptText,
        channel,
        metadata
      });
      alert('הפרומפט נשמר בהצלחה!');
    } catch (err) {
      console.error('Failed to save prompt:', err);
      alert('שגיאה בשמירת הפרומפט');
    } finally {
      setSaving(false);
    }
  };
  
  const saveAppointmentSettings = async () => {
    try {
      const opening_hours_json: Record<string, string[][]> = {};
      const selectedHours = [[defaultHours.opening, defaultHours.closing]];
      
      Object.keys(workingDays).forEach((day) => {
        if (workingDays[day as keyof typeof workingDays]) {
          opening_hours_json[day] = selectedHours;
        } else {
          opening_hours_json[day] = [];
        }
      });
      
      const payload = {
        ...appointmentSettings,
        opening_hours_json: appointmentSettings.allow_24_7 ? undefined : opening_hours_json
      };
      
      await http.put('/api/business/current', payload);
      alert('הגדרות תורים נשמרו בהצלחה');
    } catch (err) {
      console.error('Failed to save appointment settings:', err);
      alert('שגיאה בשמירת הגדרות');
    }
  };

  return (
    <div className="p-6 max-w-6xl mx-auto" dir="rtl">
      {/* Header */}
      <div className="mb-6">
        <div className="flex items-center gap-3 mb-2">
          <Bot className="h-7 w-7 text-purple-600" />
          <h1 className="text-2xl font-bold text-slate-900">סטודיו פרומפטים</h1>
        </div>
        <p className="text-slate-600">יצירה, עריכה ובדיקת פרומפטים לסוכן AI</p>
      </div>

      {/* Tabs */}
      <div className="flex border-b border-slate-200 mb-6">
        <button
          onClick={() => handleTabChange('prompts')}
          className={`px-4 py-3 text-sm font-medium border-b-2 transition-colors ${
            activeTab === 'prompts'
              ? 'border-purple-600 text-purple-600'
              : 'border-transparent text-slate-500 hover:text-slate-700'
          }`}
        >
          עריכת פרומפטים
        </button>
        <button
          onClick={() => handleTabChange('builder')}
          className={`px-4 py-3 text-sm font-medium border-b-2 transition-colors ${
            activeTab === 'builder'
              ? 'border-purple-600 text-purple-600'
              : 'border-transparent text-slate-500 hover:text-slate-700'
          }`}
        >
          מחולל פרומפטים
        </button>
        <button
          onClick={() => handleTabChange('appointments')}
          className={`px-4 py-3 text-sm font-medium border-b-2 transition-colors flex items-center gap-2 ${
            activeTab === 'appointments'
              ? 'border-purple-600 text-purple-600'
              : 'border-transparent text-slate-500 hover:text-slate-700'
          }`}
        >
          <Settings className="h-4 w-4" />
          הגדרות תורים
        </button>
      </div>

      {/* Tab Content */}
      {activeTab === 'prompts' && (
        <div className="space-y-6">
          {/* Full Prompt Editing Interface */}
          <BusinessAISettings />
        </div>
      )}

      {activeTab === 'builder' && (
        <div className="space-y-6">
          <div className="bg-white rounded-xl shadow-sm border border-slate-200 p-6">
            <div className="text-center py-12">
              <Sparkles className="h-16 w-16 text-purple-300 mx-auto mb-4" />
              <h3 className="text-xl font-semibold text-slate-900 mb-2">מחולל פרומפטים חכם</h3>
              <p className="text-slate-600 mb-6 max-w-md mx-auto">
                ענה על מספר שאלות קצרות על העסק שלך, והמערכת תיצור פרומפט מקצועי מובנה עם תבנית נוקשה.
              </p>
              <button
                onClick={() => {
                  setSmartGenChannel('calls');
                  setShowChatBuilder(true);
                }}
                className="flex items-center gap-2 px-6 py-3 bg-gradient-to-r from-purple-600 to-blue-600 text-white rounded-lg hover:from-purple-700 hover:to-blue-700 transition-all shadow-lg mx-auto min-h-[48px]"
              >
                <Sparkles className="h-5 w-5" />
                התחל ליצור פרומפט
              </button>
            </div>
          </div>
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
                  className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-purple-500"
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
                  />
                  <div className="w-11 h-6 bg-gray-200 peer-focus:outline-none peer-focus:ring-4 peer-focus:ring-purple-300 rounded-full peer peer-checked:after:translate-x-full peer-checked:after:border-white after:content-[''] after:absolute after:top-[2px] after:left-[2px] after:bg-white after:border-gray-300 after:border after:rounded-full after:h-5 after:w-5 after:transition-all peer-checked:bg-purple-600"></div>
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
                  className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-purple-500"
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
                  className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-purple-500"
                />
                <p className="mt-1 text-sm text-gray-500">
                  כמה זמן מראש לקוח צריך להודיע לפני תור (0 = ניתן לקבוע מיידית)
                </p>
              </div>

              {!appointmentSettings.allow_24_7 && (
                <div className="border-t pt-4 mt-6">
                  <h4 className="font-medium text-gray-900 mb-4">שעות פעילות</h4>
                  <p className="text-sm text-gray-500 mb-4">
                    בחרו את שעות הפעילות המוגדרות ברירת מחדל לכל הימים.
                  </p>
                  
                  <div className="grid grid-cols-2 gap-4">
                    <div>
                      <label className="block text-sm font-medium text-gray-700 mb-1">שעת פתיחה</label>
                      <select 
                        className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-purple-500"
                        value={defaultHours.opening}
                        onChange={(e) => setDefaultHours({...defaultHours, opening: e.target.value})}
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
                        className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-purple-500"
                        value={defaultHours.closing}
                        onChange={(e) => setDefaultHours({...defaultHours, closing: e.target.value})}
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
                            className="rounded text-purple-600 focus:ring-purple-500"
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
              
              <div className="pt-4">
                <button
                  onClick={saveAppointmentSettings}
                  className="w-full px-4 py-2 bg-purple-600 text-white rounded-lg hover:bg-purple-700 transition-colors"
                >
                  שמור הגדרות
                </button>
              </div>
            </div>
          </Card>
        </div>
      )}

      {/* Prompt Builder Chat Modal */}
      <PromptBuilderChat
        isOpen={showChatBuilder}
        onClose={() => setShowChatBuilder(false)}
        onSave={handleSaveGeneratedPrompt}
        initialChannel={smartGenChannel}
      />
    </div>
  );
}

export default PromptStudioPage;
