import React, { useState, useEffect } from 'react';
import { 
  Phone, 
  MessageSquare, 
  Save, 
  RefreshCw,
  AlertCircle
} from 'lucide-react';
import { http } from '../../services/http';
import { useAuth } from '../../features/auth/hooks';

interface PromptData {
  calls_prompt: string;
  whatsapp_prompt: string;
  greeting_message: string;
  whatsapp_greeting: string;
  last_updated: string;
  version: number;
}

export function BusinessAISettings() {
  const { user } = useAuth();
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState<{ calls: boolean; whatsapp: boolean }>({
    calls: false,
    whatsapp: false
  });
  const [prompts, setPrompts] = useState<PromptData>({
    calls_prompt: '',
    whatsapp_prompt: '',
    greeting_message: '',
    whatsapp_greeting: '',
    last_updated: '',
    version: 1
  });
  const [businessName, setBusinessName] = useState<string>('');

  // Load prompts and business info
  useEffect(() => {
    const loadData = async () => {
      try {
        setLoading(true);
        
        // Load business info and prompts
        const [businessData, promptsData] = await Promise.all([
          http.get<{ name: string }>(`/api/business/current`),
          http.get<PromptData>(`/api/business/current/prompt`)
        ]);
        
        setBusinessName(businessData.name);
        setPrompts(promptsData);
        
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
  const savePrompt = async (channel: 'calls' | 'whatsapp') => {
    setSaving(prev => ({ ...prev, [channel]: true }));
    
    try {
      const result = await http.put<{ success: boolean; version: number; message?: string; updated_at?: string }>(
        `/api/business/current/prompt`, 
        channel === 'calls' 
          ? { 
              calls_prompt: prompts.calls_prompt, 
              whatsapp_prompt: prompts.whatsapp_prompt,
              greeting_message: prompts.greeting_message,
              whatsapp_greeting: prompts.whatsapp_greeting
            }
          : { 
              calls_prompt: prompts.calls_prompt, 
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
        
        alert(channel === 'calls' 
          ? '✅ פרומפט שיחות נשמר בהצלחה!' 
          : '✅ פרומפט WhatsApp נשמר בהצלחה!'
        );
      }
    } catch (err) {
      console.error(`❌ Failed to save ${channel} prompt:`, err);
      alert(`שגיאה בשמירת פרומפט ${channel === 'calls' ? 'שיחות' : 'WhatsApp'}`);
    } finally {
      setSaving(prev => ({ ...prev, [channel]: false }));
    }
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

        {/* WhatsApp Prompt */}
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
      </div>

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
