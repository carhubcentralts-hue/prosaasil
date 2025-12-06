import React, { useState, useEffect } from 'react';
import { 
  Phone, 
  PhoneOutgoing,
  MessageSquare, 
  Save, 
  RefreshCw,
  AlertCircle,
  Timer,
  Brain,
  User
} from 'lucide-react';
import { http } from '../../services/http';
import { useAuth } from '../../features/auth/hooks';

interface PromptData {
  calls_prompt: string;
  outbound_calls_prompt: string;  // 🔥 BUILD 174: Separate outbound calls prompt
  whatsapp_prompt: string;
  greeting_message: string;
  whatsapp_greeting: string;
  last_updated: string;
  version: number;
}

interface CallControlSettings {
  silence_timeout_sec: number;
  silence_max_warnings: number;
  smart_hangup_enabled: boolean;
  required_lead_fields: string[];
  bot_speaks_first: boolean;
  auto_end_after_lead_capture: boolean;
  auto_end_on_goodbye: boolean;
  // 🔥 BUILD 310: SIMPLE_MODE - call_goal replaces enable_calendar_scheduling
  // call_goal 'appointment' = enable_calendar_scheduling true
  // call_goal 'lead_only' = enable_calendar_scheduling false
  call_goal: 'lead_only' | 'appointment';  // Call objective (also controls calendar scheduling)
  confirm_before_hangup: boolean;  // Require user confirmation before hanging up
}

// 🔥 BUILD 310: STT Vocabulary removed - using OpenAI Realtime native transcription

export function BusinessAISettings() {
  const { user } = useAuth();
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState<{ calls: boolean; outbound: boolean; whatsapp: boolean; callControl: boolean }>({
    calls: false,
    outbound: false,
    whatsapp: false,
    callControl: false
  });
  
  const [prompts, setPrompts] = useState<PromptData>({
    calls_prompt: '',
    outbound_calls_prompt: '',
    whatsapp_prompt: '',
    greeting_message: '',
    whatsapp_greeting: '',
    last_updated: '',
    version: 1
  });
  const [callControl, setCallControl] = useState<CallControlSettings>({
    silence_timeout_sec: 15,
    silence_max_warnings: 2,
    smart_hangup_enabled: true,
    required_lead_fields: ['name', 'phone'],
    bot_speaks_first: false,
    auto_end_after_lead_capture: false,
    auto_end_on_goodbye: false,
    // 🔥 BUILD 310: SIMPLE_MODE - call_goal controls calendar scheduling
    call_goal: 'lead_only',
    confirm_before_hangup: true
  });
  const [businessName, setBusinessName] = useState<string>('');

  // Load prompts and business info
  useEffect(() => {
    const loadData = async () => {
      try {
        setLoading(true);
        
        // Load business info, prompts, and call control settings
        const [businessData, promptsData] = await Promise.all([
          http.get<{ 
            name: string;
            silence_timeout_sec?: number;
            silence_max_warnings?: number;
            smart_hangup_enabled?: boolean;
            required_lead_fields?: string[];
            bot_speaks_first?: boolean;
            auto_end_after_lead_capture?: boolean;
            auto_end_on_goodbye?: boolean;
            enable_calendar_scheduling?: boolean;  // 🔥 BUILD 186
            // 🔥 BUILD 309: SIMPLE_MODE settings
            call_goal?: 'lead_only' | 'appointment';
            confirm_before_hangup?: boolean;
          }>(`/api/business/current`),
          http.get<PromptData>(`/api/business/current/prompt`)
        ]);
        
        setBusinessName(businessData.name);
        setPrompts(promptsData);
        
        // Set call control settings from business data
        // 🔥 BUILD 310: call_goal replaces enable_calendar_scheduling
        // If call_goal not set, derive from enable_calendar_scheduling for migration
        let derivedCallGoal: 'lead_only' | 'appointment' = businessData.call_goal ?? 'lead_only';
        if (!businessData.call_goal && businessData.enable_calendar_scheduling === true) {
          derivedCallGoal = 'appointment';  // Legacy migration: calendar enabled = appointment goal
        }
        
        setCallControl({
          silence_timeout_sec: businessData.silence_timeout_sec ?? 15,
          silence_max_warnings: businessData.silence_max_warnings ?? 2,
          smart_hangup_enabled: businessData.smart_hangup_enabled ?? true,
          required_lead_fields: businessData.required_lead_fields ?? ['name', 'phone'],
          bot_speaks_first: businessData.bot_speaks_first ?? false,
          auto_end_after_lead_capture: businessData.auto_end_after_lead_capture ?? false,
          auto_end_on_goodbye: businessData.auto_end_on_goodbye ?? false,
          // 🔥 BUILD 310: SIMPLE_MODE settings
          call_goal: derivedCallGoal,
          confirm_before_hangup: businessData.confirm_before_hangup !== false  // Default true
        });
        
        console.log('✅ Loaded AI prompts:', promptsData);
      } catch (err) {
        console.error('❌ Failed to load AI prompts:', err);
      } finally {
        setLoading(false);
      }
    };

    loadData();
  }, []);

  // Save prompt for specific channel
  const savePrompt = async (channel: 'calls' | 'outbound' | 'whatsapp') => {
    setSaving(prev => ({ ...prev, [channel]: true }));
    
    try {
      const result = await http.put<{ success: boolean; version: number; message?: string; updated_at?: string }>(
        `/api/business/current/prompt`, 
        { 
          calls_prompt: prompts.calls_prompt,
          outbound_calls_prompt: prompts.outbound_calls_prompt,
          whatsapp_prompt: prompts.whatsapp_prompt,
          greeting_message: prompts.greeting_message,
          whatsapp_greeting: prompts.whatsapp_greeting
        }
      );

      if (result.success) {
        setPrompts(prev => ({ 
          ...prev, 
          version: result.version || prev.version + 1,
          last_updated: result.updated_at || new Date().toISOString()
        }));
        
        const channelNames: Record<string, string> = {
          calls: '✅ פרומפט שיחות נכנסות נשמר בהצלחה!',
          outbound: '✅ פרומפט שיחות יוצאות נשמר בהצלחה!',
          whatsapp: '✅ פרומפט WhatsApp נשמר בהצלחה!'
        };
        alert(channelNames[channel]);
      }
    } catch (err) {
      console.error(`❌ Failed to save ${channel} prompt:`, err);
      const channelNames: Record<string, string> = {
        calls: 'שיחות נכנסות',
        outbound: 'שיחות יוצאות',
        whatsapp: 'WhatsApp'
      };
      alert(`שגיאה בשמירת פרומפט ${channelNames[channel]}`);
    } finally {
      setSaving(prev => ({ ...prev, [channel]: false }));
    }
  };

  // Save call control settings
  const saveCallControl = async () => {
    setSaving(prev => ({ ...prev, callControl: true }));
    
    try {
      // 🔥 BUILD 310: Derive enable_calendar_scheduling from call_goal
      // appointment = calendar enabled, lead_only = calendar disabled
      const enableCalendar = callControl.call_goal === 'appointment';
      
      await http.put(`/api/business/current/settings`, {
        silence_timeout_sec: callControl.silence_timeout_sec,
        silence_max_warnings: callControl.silence_max_warnings,
        smart_hangup_enabled: callControl.smart_hangup_enabled,
        required_lead_fields: callControl.required_lead_fields,
        bot_speaks_first: callControl.bot_speaks_first,
        auto_end_after_lead_capture: callControl.auto_end_after_lead_capture,
        auto_end_on_goodbye: callControl.auto_end_on_goodbye,
        enable_calendar_scheduling: enableCalendar,  // 🔥 BUILD 310: Derived from call_goal
        // 🔥 BUILD 310: SIMPLE_MODE settings
        call_goal: callControl.call_goal,
        confirm_before_hangup: callControl.confirm_before_hangup
      });
      
      alert('✅ הגדרות שליטת שיחה נשמרו בהצלחה!');
    } catch (err) {
      console.error('❌ Failed to save call control settings:', err);
      alert('שגיאה בשמירת הגדרות שליטת שיחה');
    } finally {
      setSaving(prev => ({ ...prev, callControl: false }));
    }
  };

  // 🔥 BUILD 310: STT Vocabulary functions removed - using OpenAI Realtime native transcription

  // Toggle required field
  const toggleRequiredField = (field: string) => {
    setCallControl(prev => {
      const fields = prev.required_lead_fields;
      if (fields.includes(field)) {
        return { ...prev, required_lead_fields: fields.filter(f => f !== field) };
      } else {
        return { ...prev, required_lead_fields: [...fields, field] };
      }
    });
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center p-12">
        <RefreshCw className="h-8 w-8 text-blue-500 animate-spin" />
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {/* Info Alerts */}
      <div className="space-y-4">
        {/* Placeholders Info */}
        <div className="bg-blue-50 border border-blue-200 rounded-lg p-4">
          <div className="flex items-start gap-3">
            <AlertCircle className="h-5 w-5 text-blue-600 flex-shrink-0 mt-0.5" />
            <div className="text-blue-800">
              <p className="font-medium">💡 שימוש ב-Placeholders דינמיים</p>
              <p className="text-sm mt-1">
                אתה יכול להשתמש ב-<code className="px-1.5 py-0.5 bg-blue-100 rounded">{'{{business_name}}'}</code> בפרומפט - המערכת תחליף אותו אוטומטית בשם העסק האמיתי!
              </p>
              <p className="text-xs mt-2 text-blue-700">
                דוגמה: "אתה סוכן נדל״ן מ-{'{{business_name}}'}" → "אתה סוכן נדל״ן מ-{businessName}"
              </p>
            </div>
          </div>
        </div>

        {/* Warning Alert */}
        <div className="bg-amber-50 border border-amber-200 rounded-lg p-4">
          <div className="flex items-start gap-3">
            <AlertCircle className="h-5 w-5 text-amber-600 flex-shrink-0 mt-0.5" />
            <div className="text-amber-800">
              <p className="font-medium">הערה חשובה</p>
              <p className="text-sm mt-1">
                שינויים בפרומפטים יחולו מיידית על כל השיחות וההודעות החדשות. 
                וודא שהטקסט ברור ומדויק לפני השמירה.
              </p>
            </div>
          </div>
        </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Calls Prompt */}
        <div className="bg-white rounded-xl shadow-sm border border-slate-200 p-6">
          <div className="flex items-center gap-3 mb-4">
            <div className="w-10 h-10 bg-blue-100 rounded-lg flex items-center justify-center">
              <Phone className="h-5 w-5 text-blue-600" />
            </div>
            <div>
              <h3 className="text-lg font-semibold text-slate-900">פרומפט שיחות טלפון</h3>
              <p className="text-sm text-slate-500">הנחיות ל-AI עבור שיחות נכנסות</p>
            </div>
          </div>
          
          {/* Greeting Message for Calls */}
          <div className="mb-4">
            <label className="block text-sm font-medium text-slate-700 mb-2">
              💬 הודעת פתיחה (ברכה ראשונית)
            </label>
            <input
              type="text"
              value={prompts.greeting_message}
              onChange={(e) => setPrompts(prev => ({ ...prev, greeting_message: e.target.value }))}
              placeholder='שלום! שמי שרה ואני העוזרת של {{business_name}}. במה אוכל לעזור?'
              className="w-full p-3 border border-slate-300 rounded-lg text-sm focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
              dir="rtl"
              data-testid="input-greeting-calls"
            />
            <p className="text-xs text-slate-500 mt-1">
              זה מה שהלקוח ישמע ברגע שהשיחה מתחילה. השתמש ב-{'{{business_name}}'} לשם העסק
            </p>
          </div>
          
          <textarea
            value={prompts.calls_prompt}
            onChange={(e) => setPrompts(prev => ({ ...prev, calls_prompt: e.target.value }))}
            placeholder="הכנס הנחיות עבור AI Agent בשיחות טלפון..."
            className="w-full h-64 p-4 border border-slate-300 rounded-lg resize-none text-sm leading-relaxed focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
            dir="rtl"
            data-testid="textarea-prompt-calls"
          />
          
          <div className="flex items-center justify-between mt-4 pt-4 border-t border-slate-200">
            <p className="text-xs text-slate-500">
              {prompts.calls_prompt.length} תווים
            </p>
            <button
              onClick={() => savePrompt('calls')}
              disabled={saving.calls}
              className="flex items-center gap-2 px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
              data-testid="button-save-calls-prompt"
            >
              {saving.calls ? (
                <RefreshCw className="h-4 w-4 animate-spin" />
              ) : (
                <Save className="h-4 w-4" />
              )}
              {saving.calls ? 'שומר...' : 'שמור פרומפט שיחות'}
            </button>
          </div>
        </div>

        {/* Outbound Calls Prompt - BUILD 174 */}
        <div className="bg-white rounded-xl shadow-sm border border-slate-200 p-6">
          <div className="flex items-center gap-3 mb-4">
            <div className="w-10 h-10 bg-orange-100 rounded-lg flex items-center justify-center">
              <PhoneOutgoing className="h-5 w-5 text-orange-600" />
            </div>
            <div>
              <h3 className="text-lg font-semibold text-slate-900">פרומפט שיחות יוצאות</h3>
              <p className="text-sm text-slate-500">הנחיות ל-AI עבור שיחות שאתה יוזם</p>
            </div>
          </div>
          
          <div className="mb-4">
            <p className="text-sm text-slate-600 mb-2">
              💡 פרומפט זה ישמש כאשר ה-AI מתקשר ללקוחות (שיחות יוצאות). 
              אם לא מוגדר, המערכת תשתמש בפרומפט השיחות הנכנסות.
            </p>
          </div>
          
          <textarea
            value={prompts.outbound_calls_prompt}
            onChange={(e) => setPrompts(prev => ({ ...prev, outbound_calls_prompt: e.target.value }))}
            placeholder="הכנס הנחיות עבור AI Agent בשיחות יוצאות... לדוגמה: 'אתה נציג מכירות שמתקשר ללקוח כדי להציע שירותים. היה אדיב וקצר, הצג את הערך ללקוח.'"
            className="w-full h-64 p-4 border border-slate-300 rounded-lg resize-none text-sm leading-relaxed focus:ring-2 focus:ring-orange-500 focus:border-orange-500"
            dir="rtl"
            data-testid="textarea-prompt-outbound"
          />
          
          <div className="flex items-center justify-between mt-4 pt-4 border-t border-slate-200">
            <p className="text-xs text-slate-500">
              {prompts.outbound_calls_prompt.length} תווים
            </p>
            <button
              onClick={() => savePrompt('outbound')}
              disabled={saving.outbound}
              className="flex items-center gap-2 px-4 py-2 bg-orange-600 text-white rounded-lg hover:bg-orange-700 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
              data-testid="button-save-outbound-prompt"
            >
              {saving.outbound ? (
                <RefreshCw className="h-4 w-4 animate-spin" />
              ) : (
                <Save className="h-4 w-4" />
              )}
              {saving.outbound ? 'שומר...' : 'שמור פרומפט יוצאות'}
            </button>
          </div>
        </div>
      </div>

      {/* WhatsApp Prompt - Full Width */}
      <div className="bg-white rounded-xl shadow-sm border border-slate-200 p-6">
        <div className="flex items-center gap-3 mb-4">
          <div className="w-10 h-10 bg-green-100 rounded-lg flex items-center justify-center">
            <MessageSquare className="h-5 w-5 text-green-600" />
          </div>
          <div>
            <h3 className="text-lg font-semibold text-slate-900">פרומפט WhatsApp</h3>
            <p className="text-sm text-slate-500">הנחיות ל-AI עבור הודעות WhatsApp</p>
          </div>
        </div>
        
        {/* Greeting Message for WhatsApp */}
        <div className="mb-4">
          <label className="block text-sm font-medium text-slate-700 mb-2">
            💬 הודעת פתיחה (ברכה ראשונית)
          </label>
          <input
            type="text"
            value={prompts.whatsapp_greeting}
            onChange={(e) => setPrompts(prev => ({ ...prev, whatsapp_greeting: e.target.value }))}
            placeholder='שלום! אני העוזרת של {{business_name}} ב-WhatsApp. איך אפשר לעזור?'
            className="w-full p-3 border border-slate-300 rounded-lg text-sm focus:ring-2 focus:ring-green-500 focus:border-green-500"
            dir="rtl"
            data-testid="input-greeting-whatsapp"
          />
          <p className="text-xs text-slate-500 mt-1">
            זו ההודעה הראשונה שהלקוח יקבל ב-WhatsApp. השתמש ב-{'{{business_name}}'} לשם העסק
          </p>
        </div>
        
        <textarea
          value={prompts.whatsapp_prompt}
          onChange={(e) => setPrompts(prev => ({ ...prev, whatsapp_prompt: e.target.value }))}
          placeholder="הכנס הנחיות עבור AI Agent בהודעות WhatsApp..."
          className="w-full h-64 p-4 border border-slate-300 rounded-lg resize-none text-sm leading-relaxed focus:ring-2 focus:ring-green-500 focus:border-green-500"
          dir="rtl"
          data-testid="textarea-prompt-whatsapp"
        />
        
        <div className="flex items-center justify-between mt-4 pt-4 border-t border-slate-200">
          <p className="text-xs text-slate-500">
            {prompts.whatsapp_prompt.length} תווים
          </p>
          <button
            onClick={() => savePrompt('whatsapp')}
            disabled={saving.whatsapp}
            className="flex items-center gap-2 px-4 py-2 bg-green-600 text-white rounded-lg hover:bg-green-700 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
            data-testid="button-save-whatsapp-prompt"
          >
            {saving.whatsapp ? (
              <RefreshCw className="h-4 w-4 animate-spin" />
            ) : (
              <Save className="h-4 w-4" />
            )}
            {saving.whatsapp ? 'שומר...' : 'שמור פרומפט WhatsApp'}
          </button>
        </div>
      </div>

      {/* Smart Call Control Settings - Step 2 Spec */}
      <div className="bg-white rounded-xl shadow-sm border border-slate-200 p-6">
        <div className="flex items-center gap-3 mb-6">
          <div className="w-10 h-10 bg-purple-100 rounded-lg flex items-center justify-center">
            <Brain className="h-5 w-5 text-purple-600" />
          </div>
          <div>
            <h3 className="text-lg font-semibold text-slate-900">הגדרות שליטת שיחה חכמה</h3>
            <p className="text-sm text-slate-500">הגדרות סיום שיחה וטיפול בשקט מבוסס AI</p>
          </div>
        </div>

        <div className="space-y-6">
          {/* Bot Speaks First Toggle */}
          <div className="flex items-center justify-between p-4 bg-blue-50 rounded-lg border border-blue-200">
            <div>
              <h4 className="font-medium text-slate-900">🎙️ ה-AI מדבר ראשון</h4>
              <p className="text-sm text-slate-600 mt-1">
                כאשר מופעל, ה-AI יפתח את השיחה עם הברכה ללא המתנה ללקוח. מומלץ לרוב העסקים.
              </p>
            </div>
            <label className="relative inline-flex items-center cursor-pointer">
              <input
                type="checkbox"
                checked={callControl.bot_speaks_first}
                onChange={(e) => setCallControl(prev => ({ ...prev, bot_speaks_first: e.target.checked }))}
                className="sr-only peer"
                data-testid="checkbox-bot-speaks-first"
              />
              <div className="w-11 h-6 bg-gray-200 peer-focus:outline-none peer-focus:ring-4 peer-focus:ring-blue-300 rounded-full peer peer-checked:after:translate-x-full peer-checked:after:border-white after:content-[''] after:absolute after:top-[2px] after:left-[2px] after:bg-white after:border-gray-300 after:border after:rounded-full after:h-5 after:w-5 after:transition-all peer-checked:bg-blue-600"></div>
            </label>
          </div>

          {/* Auto-End Settings */}
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            {/* Auto-End After Lead Capture */}
            <div className="flex items-center justify-between p-4 bg-green-50 rounded-lg border border-green-200">
              <div>
                <h4 className="font-medium text-slate-900">📋 סיום אוטומטי אחרי איסוף ליד</h4>
                <p className="text-sm text-slate-600 mt-1">
                  סיום השיחה אחרי שנאספו כל הפרטים הנדרשים
                </p>
              </div>
              <label className="relative inline-flex items-center cursor-pointer">
                <input
                  type="checkbox"
                  checked={callControl.auto_end_after_lead_capture}
                  onChange={(e) => setCallControl(prev => ({ ...prev, auto_end_after_lead_capture: e.target.checked }))}
                  className="sr-only peer"
                  data-testid="checkbox-auto-end-lead"
                />
                <div className="w-11 h-6 bg-gray-200 peer-focus:outline-none peer-focus:ring-4 peer-focus:ring-green-300 rounded-full peer peer-checked:after:translate-x-full peer-checked:after:border-white after:content-[''] after:absolute after:top-[2px] after:left-[2px] after:bg-white after:border-gray-300 after:border after:rounded-full after:h-5 after:w-5 after:transition-all peer-checked:bg-green-600"></div>
              </label>
            </div>

            {/* Auto-End On Goodbye */}
            <div className="flex items-center justify-between p-4 bg-amber-50 rounded-lg border border-amber-200">
              <div>
                <h4 className="font-medium text-slate-900">👋 סיום אוטומטי כשהלקוח נפרד</h4>
                <p className="text-sm text-slate-600 mt-1">
                  סיום כשהלקוח אומר "תודה", "ביי", "להתראות"
                </p>
              </div>
              <label className="relative inline-flex items-center cursor-pointer">
                <input
                  type="checkbox"
                  checked={callControl.auto_end_on_goodbye}
                  onChange={(e) => setCallControl(prev => ({ ...prev, auto_end_on_goodbye: e.target.checked }))}
                  className="sr-only peer"
                  data-testid="checkbox-auto-end-goodbye"
                />
                <div className="w-11 h-6 bg-gray-200 peer-focus:outline-none peer-focus:ring-4 peer-focus:ring-amber-300 rounded-full peer peer-checked:after:translate-x-full peer-checked:after:border-white after:content-[''] after:absolute after:top-[2px] after:left-[2px] after:bg-white after:border-gray-300 after:border after:rounded-full after:h-5 after:w-5 after:transition-all peer-checked:bg-amber-600"></div>
              </label>
            </div>
          </div>

          {/* Smart Hangup Toggle */}
          <div className="flex items-center justify-between p-4 bg-slate-50 rounded-lg">
            <div>
              <h4 className="font-medium text-slate-900">🧠 סיום שיחה חכם מבוסס AI</h4>
              <p className="text-sm text-slate-600 mt-1">
                ה-AI מחליט מתי לסיים שיחה על בסיס הקשר השיחה, לא על מילות מפתח בודדות כמו "לא צריך"
              </p>
            </div>
            <label className="relative inline-flex items-center cursor-pointer">
              <input
                type="checkbox"
                checked={callControl.smart_hangup_enabled}
                onChange={(e) => setCallControl(prev => ({ ...prev, smart_hangup_enabled: e.target.checked }))}
                className="sr-only peer"
                data-testid="checkbox-smart-hangup"
              />
              <div className="w-11 h-6 bg-gray-200 peer-focus:outline-none peer-focus:ring-4 peer-focus:ring-purple-300 rounded-full peer peer-checked:after:translate-x-full peer-checked:after:border-white after:content-[''] after:absolute after:top-[2px] after:left-[2px] after:bg-white after:border-gray-300 after:border after:rounded-full after:h-5 after:w-5 after:transition-all peer-checked:bg-purple-600"></div>
            </label>
          </div>

          {/* BUILD 309: Confirm Before Hangup Toggle */}
          <div className="flex items-center justify-between p-4 bg-teal-50 rounded-lg border border-teal-200">
            <div>
              <h4 className="font-medium text-slate-900">✅ אישור לפני ניתוק</h4>
              <p className="text-sm text-slate-600 mt-1">
                הבוט מבקש אישור מהלקוח לפני שמסיים את השיחה
              </p>
              <p className="text-xs text-teal-600 mt-1">
                מומלץ להפעיל כדי להבטיח שהלקוח מרוצה לפני ניתוק
              </p>
            </div>
            <label className="relative inline-flex items-center cursor-pointer">
              <input
                type="checkbox"
                checked={callControl.confirm_before_hangup}
                onChange={(e) => setCallControl(prev => ({ ...prev, confirm_before_hangup: e.target.checked }))}
                className="sr-only peer"
                data-testid="checkbox-confirm-before-hangup"
              />
              <div className="w-11 h-6 bg-gray-200 peer-focus:outline-none peer-focus:ring-4 peer-focus:ring-teal-300 rounded-full peer peer-checked:after:translate-x-full peer-checked:after:border-white after:content-[''] after:absolute after:top-[2px] after:left-[2px] after:bg-white after:border-gray-300 after:border after:rounded-full after:h-5 after:w-5 after:transition-all peer-checked:bg-teal-600"></div>
            </label>
          </div>

          {/* BUILD 309: Call Goal Selection */}
          <div className="p-4 bg-indigo-50 rounded-lg border border-indigo-200">
            <h4 className="font-medium text-slate-900 mb-2">🎯 מטרת השיחה</h4>
            <p className="text-sm text-slate-600 mb-3">
              מה הבוט צריך להשיג בסוף השיחה
            </p>
            <div className="flex gap-4">
              <label className="flex items-center gap-2 cursor-pointer">
                <input
                  type="radio"
                  name="call_goal"
                  value="lead_only"
                  checked={callControl.call_goal === 'lead_only'}
                  onChange={(e) => setCallControl(prev => ({ ...prev, call_goal: 'lead_only' }))}
                  className="w-4 h-4 text-indigo-600"
                  data-testid="radio-goal-lead-only"
                />
                <span className="text-sm">📋 איסוף פרטים בלבד</span>
              </label>
              <label className="flex items-center gap-2 cursor-pointer">
                <input
                  type="radio"
                  name="call_goal"
                  value="appointment"
                  checked={callControl.call_goal === 'appointment'}
                  onChange={(e) => setCallControl(prev => ({ ...prev, call_goal: 'appointment' }))}
                  className="w-4 h-4 text-indigo-600"
                  data-testid="radio-goal-appointment"
                />
                <span className="text-sm">📅 קביעת פגישה</span>
              </label>
            </div>
            <p className="text-xs text-indigo-600 mt-2">
              {callControl.call_goal === 'lead_only' 
                ? 'הבוט יאסוף את הפרטים הנדרשים ויסיים את השיחה' 
                : 'הבוט ינסה לקבוע פגישה עם הלקוח ביומן העסק'}
            </p>
          </div>

          {/* Silence Timeout */}
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div>
              <label className="block text-sm font-medium text-slate-700 mb-2">
                <Timer className="inline-block w-4 h-4 ml-1" />
                זמן שקט לפני שאילת "אתה עדיין שם?"
              </label>
              <div className="flex items-center gap-3">
                <input
                  type="range"
                  min="5"
                  max="30"
                  value={callControl.silence_timeout_sec}
                  onChange={(e) => setCallControl(prev => ({ ...prev, silence_timeout_sec: parseInt(e.target.value) }))}
                  className="w-full h-2 bg-slate-200 rounded-lg appearance-none cursor-pointer accent-purple-600"
                  data-testid="slider-silence-timeout"
                />
                <span className="text-sm font-medium text-slate-700 min-w-[60px] text-center">
                  {callControl.silence_timeout_sec} שניות
                </span>
              </div>
              <p className="text-xs text-slate-500 mt-1">
                אחרי כמה שניות של שקט ה-AI שואל אם הלקוח עדיין בקו
              </p>
            </div>

            <div>
              <label className="block text-sm font-medium text-slate-700 mb-2">
                מספר אזהרות שקט לפני סיום
              </label>
              <select
                value={callControl.silence_max_warnings}
                onChange={(e) => setCallControl(prev => ({ ...prev, silence_max_warnings: parseInt(e.target.value) }))}
                className="w-full px-3 py-2 border border-slate-300 rounded-lg focus:ring-2 focus:ring-purple-500 focus:border-purple-500"
                data-testid="select-silence-warnings"
              >
                <option value="1">אזהרה 1 - סיום מהיר</option>
                <option value="2">2 אזהרות - מאוזן (מומלץ)</option>
                <option value="3">3 אזהרות - סבלני</option>
              </select>
              <p className="text-xs text-slate-500 mt-1">
                כמה פעמים לשאול "אתה שם?" לפני סיום השיחה בנימוס
              </p>
            </div>
          </div>

          {/* Required Lead Fields */}
          <div>
            <label className="block text-sm font-medium text-slate-700 mb-3">
              <User className="inline-block w-4 h-4 ml-1" />
              פרטים נדרשים לאיסוף מהליד
            </label>
            <div className="flex flex-wrap gap-2">
              {[
                { key: 'name', label: 'שם מלא' },
                { key: 'phone', label: 'טלפון' },
                { key: 'email', label: 'אימייל' },
                { key: 'city', label: 'עיר' },
                { key: 'service_type', label: 'סוג שירות/תחום' },
                { key: 'budget', label: 'תקציב' },
                { key: 'preferred_time', label: 'זמן מועדף' },
                { key: 'notes', label: 'הערות/תיאור בעיה' }
              ].map(field => (
                <button
                  key={field.key}
                  type="button"
                  onClick={() => toggleRequiredField(field.key)}
                  className={`px-3 py-1.5 rounded-full text-sm font-medium transition-colors ${
                    callControl.required_lead_fields.includes(field.key)
                      ? 'bg-purple-100 text-purple-700 border-2 border-purple-300'
                      : 'bg-slate-100 text-slate-600 border-2 border-transparent hover:bg-slate-200'
                  }`}
                  data-testid={`toggle-field-${field.key}`}
                >
                  {callControl.required_lead_fields.includes(field.key) ? '✓ ' : ''}{field.label}
                </button>
              ))}
            </div>
            <p className="text-xs text-slate-500 mt-2">
              ה-AI יאסוף את הפרטים האלה לפני שמאפשר סיום שיחה. לחץ לבחירה/ביטול.
            </p>
          </div>

          {/* Info box about how it works */}
          <div className="bg-purple-50 border border-purple-200 rounded-lg p-4">
            <div className="flex items-start gap-3">
              <AlertCircle className="h-5 w-5 text-purple-600 flex-shrink-0 mt-0.5" />
              <div className="text-purple-800">
                <p className="font-medium">איך זה עובד?</p>
                <ul className="text-sm mt-2 space-y-1 list-disc list-inside">
                  <li>ה-AI מנתח את כל השיחה כדי להבין אם הלקוח באמת רוצה לסיים</li>
                  <li>לא מסיים שיחה רק בגלל "לא תודה" או "אין צורך" בודד</li>
                  <li>מוודא שכל הפרטים הנדרשים נאספו לפני סיום</li>
                  <li>מזהה שקט ממושך ושואל בנימוס אם הלקוח עדיין בקו</li>
                </ul>
                <p className="text-sm mt-3 font-medium text-purple-900">
                  📤 שים לב: הגדרות אלו חלות רק על שיחות נכנסות. שיחות יוצאות עוקבות רק אחרי הפרומפט שהוגדר בנפרד.
                </p>
              </div>
            </div>
          </div>

          {/* Save Button */}
          <div className="flex justify-end pt-4 border-t border-slate-200">
            <button
              onClick={saveCallControl}
              disabled={saving.callControl}
              className="flex items-center gap-2 px-4 py-2 bg-purple-600 text-white rounded-lg hover:bg-purple-700 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
              data-testid="button-save-call-control"
            >
              {saving.callControl ? (
                <RefreshCw className="h-4 w-4 animate-spin" />
              ) : (
                <Save className="h-4 w-4" />
              )}
              {saving.callControl ? 'שומר...' : 'שמור הגדרות שליטת שיחה'}
            </button>
          </div>
        </div>
      </div>

      {/* 🔥 BUILD 310: STT Vocabulary section removed - using OpenAI Realtime native transcription */}

      {/* Version Info */}
      {prompts.last_updated && (
        <div className="text-center text-sm text-slate-500">
          עדכון אחרון: {new Date(prompts.last_updated).toLocaleString('he-IL')}
          {prompts.version > 1 && ` • גרסה ${prompts.version}`}
        </div>
      )}
    </div>
  );
}
