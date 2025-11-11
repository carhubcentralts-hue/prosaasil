import React from 'react';
import React, { useState, useEffect } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { 
  ArrowRight, 
  Bot, 
  Phone, 
  MessageSquare, 
  Save, 
  RefreshCw,
  AlertCircle,
  History
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

interface PromptRevision {
  id: number;
  channel: string;
  prompt_content: string;
  version: number;
  created_at: string;
  created_by: string;
}

export function AgentPromptsPage() {
  const { businessId: urlBusinessId } = useParams<{ businessId: string }>();
  const navigate = useNavigate();
  const { user } = useAuth();
  const [loading, setLoading] = useState(true);
  
  // Determine which business ID to use
  const businessId = user?.role === 'business' ? user.business_id?.toString() : urlBusinessId;
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
  const [revisions, setRevisions] = useState<PromptRevision[]>([]);
  const [showHistory, setShowHistory] = useState(false);
  const [businessName, setBusinessName] = useState<string>('');

  // Load prompts and business info
  useEffect(() => {
    if (!businessId) {
      // Redirect based on user role
      if (user?.role === 'business') {
        console.error('Business user has no business_id');
        return;
      }
      navigate('/app/admin/businesses');
      return;
    }

    const loadData = async () => {
      try {
        setLoading(true);
        
        // Load business info and prompts in parallel
        const isBusinessRole = user?.role === 'business';
        const [businessData, promptsData] = await Promise.all([
          http.get<{ name: string }>(isBusinessRole ? `/api/business/current` : `/api/admin/business/${businessId}`),
          http.get<PromptData>(isBusinessRole ? `/api/business/current/prompt` : `/api/admin/businesses/${businessId}/prompt`)
        ]);
        
        setBusinessName(businessData.name);
        setPrompts(promptsData);
        
        console.log('✅ Loaded AI prompts:', promptsData);
      } catch (err) {
        console.error('❌ Failed to load data:', err);
      } finally {
        setLoading(false);
      }
    };

    loadData();
  }, [businessId, navigate]);

  // Load history
  const loadHistory = async () => {
    try {
      const isBusinessRole = user?.role === 'business';
      const { history } = await http.get<{ history: PromptRevision[] }>(
        isBusinessRole 
          ? `/api/business/current/prompt/history` 
          : `/api/admin/businesses/${businessId}/prompt/history`
      );
      setRevisions(history);
    } catch (err) {
      console.error('❌ Failed to load history:', err);
    }
  };

  // Save prompt for specific channel
  const savePrompt = async (channel: 'calls' | 'whatsapp') => {
    setSaving(prev => ({ ...prev, [channel]: true }));
    
    try {
      const isBusinessRole = user?.role === 'business';
      
      const result = await http.put<{ success: boolean; version: number; message?: string; updated_at?: string }>(
        isBusinessRole 
          ? `/api/business/current/prompt` 
          : `/api/admin/businesses/${businessId}/prompt`, 
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
        // Update version and timestamp
        const timestamp = result.updated_at || new Date().toISOString();
        setPrompts(prev => ({ ...prev, version: result.version, last_updated: timestamp }));
        alert(`✅ פרומפט ${channel === 'calls' ? 'שיחות' : 'WhatsApp'} נשמר בהצלחה`);
      } else {
        alert(`❌ שגיאה בשמירת פרומפט: ${result.message}`);
      }
    } catch (err) {
      console.error(`❌ Failed to save ${channel} prompt:`, err);
      alert(`❌ שגיאה בשמירת פרומפט ${channel === 'calls' ? 'שיחות' : 'WhatsApp'}`);
    } finally {
      setSaving(prev => ({ ...prev, [channel]: false }));
    }
  };

  const formatDate = (dateStr: string) => {
    return new Date(dateStr).toLocaleDateString('he-IL', {
      year: 'numeric',
      month: 'short',
      day: 'numeric',
      hour: '2-digit',
      minute: '2-digit'
    });
  };

  if (loading) {
    return (
      <div className="p-6">
        <div className="flex items-center justify-center min-h-[400px]">
          <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-blue-600 ml-3"></div>
          <span className="text-slate-600">טוען הגדרות AI Agent...</span>
        </div>
      </div>
    );
  }

  return (
    <div className="p-6 max-w-6xl mx-auto">
      {/* Header */}
      <div className="mb-6">
        <div className="flex items-center gap-3 mb-4">
          {user?.role !== 'business' && (
            <button
              onClick={() => navigate('/app/admin/businesses')}
              className="p-2 text-slate-500 hover:text-slate-700 hover:bg-slate-100 rounded-lg transition-colors"
            >
              <ArrowRight className="h-5 w-5" />
            </button>
          )}
          <Bot className="h-6 w-6 text-purple-600" />
          <h1 className="text-2xl font-bold text-slate-900">הגדרות AI Agent</h1>
        </div>
        
        <div className="flex items-center justify-between">
          <div>
            <p className="text-slate-600">עסק: <span className="font-medium">{businessName}</span></p>
            <p className="text-sm text-slate-500">
              עדכון אחרון: {prompts.last_updated ? formatDate(prompts.last_updated) : 'לא עודכן'}
              {prompts.version > 1 && ` • גרסה ${prompts.version}`}
            </p>
          </div>
          
          <button
            onClick={() => {
              setShowHistory(!showHistory);
              if (!showHistory) loadHistory();
            }}
            className="flex items-center gap-2 px-4 py-2 text-slate-600 hover:text-slate-800 hover:bg-slate-100 rounded-lg transition-colors"
          >
            <History className="h-4 w-4" />
            היסטוריית שינויים
          </button>
        </div>
      </div>

      {/* Alerts */}
      <div className="space-y-4 mb-6">
        {/* Info Alert - Placeholders */}
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

      {/* History Panel */}
      {showHistory && (
        <div className="mt-6 bg-white rounded-xl shadow-sm border border-slate-200 p-6">
          <h3 className="text-lg font-semibold text-slate-900 mb-4 flex items-center gap-2">
            <History className="h-5 w-5 text-slate-600" />
            היסטוריית שינויים
          </h3>
          
          {revisions.length > 0 ? (
            <div className="space-y-3 max-h-60 overflow-y-auto">
              {revisions.map((revision) => (
                <div key={revision.id} className="flex items-start gap-4 p-3 bg-slate-50 rounded-lg">
                  <div className={`w-8 h-8 rounded-lg flex items-center justify-center ${
                    revision.channel === 'calls' 
                      ? 'bg-blue-100' 
                      : 'bg-green-100'
                  }`}>
                    {revision.channel === 'calls' ? (
                      <Phone className="h-4 w-4 text-blue-600" />
                    ) : (
                      <MessageSquare className="h-4 w-4 text-green-600" />
                    )}
                  </div>
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-2 mb-1">
                      <span className="font-medium text-slate-900">
                        {revision.channel === 'calls' ? 'שיחות' : 'WhatsApp'}
                      </span>
                      <span className="text-xs text-slate-500">גרסה {revision.version}</span>
                    </div>
                    <p className="text-sm text-slate-600 truncate">
                      {revision.prompt_content.substring(0, 100)}...
                    </p>
                    <p className="text-xs text-slate-500 mt-1">
                      {formatDate(revision.created_at)} • {revision.created_by}
                    </p>
                  </div>
                </div>
              ))}
            </div>
          ) : (
            <p className="text-slate-500 text-center py-8">אין היסטוריית שינויים</p>
          )}
        </div>
      )}
    </div>
  );
}