import React from 'react';
import React, { useState, useEffect } from 'react';
import { 
  Headphones, 
  MessageCircle, 
  Phone,
  Settings, 
  Save,
  Loader2,
  CheckCircle,
  AlertCircle
} from 'lucide-react';
import { Card } from '../../shared/components/ui/Card';
import { useNavigate } from 'react-router-dom';
import { useAuth } from '../../features/auth/hooks';
import { useSupportPrompt, useSupportPhones } from '../../features/admin/hooks';
import { adminApi } from '../../features/admin/api';

export function AdminSupportPage() {
  const navigate = useNavigate();
  const { user } = useAuth();
  const [activeTab, setActiveTab] = useState<'prompt' | 'phones'>('prompt');
  const [saving, setSaving] = useState(false);
  const [saveStatus, setSaveStatus] = useState<'success' | 'error' | null>(null);

  // Fetch real data from API
  const { data: promptApiData, isLoading: promptLoading, error: promptError, refetch: refetchPrompt } = useSupportPrompt();
  const { data: phonesApiData, isLoading: phonesLoading, error: phonesError, refetch: refetchPhones } = useSupportPhones();

  // Local state for editing
  const [promptData, setPromptData] = useState({
    prompt: '',
    model: 'gpt-4o-mini',
    maxTokens: 150,
    temperature: 0.7
  });

  const [phoneSettings, setPhoneSettings] = useState({
    phone_e164: '',
    whatsapp_number: '',
    whatsapp_enabled: false,
    working_hours: '08:00-18:00',
    voice_message: ''
  });

  // Update local state when API data loads
  useEffect(() => {
    if (promptApiData) {
      setPromptData({
        prompt: promptApiData.ai_prompt || 'אני לאה, נציגת התמיכה של מערכת ניהול הנדל"ן שלנו. אני כאן לעזור לכם עם כל שאלה או בעיה טכנית שיש לכם במערכת.',
        model: promptApiData.model || 'gpt-4o-mini',
        maxTokens: promptApiData.max_tokens || 150,
        temperature: promptApiData.temperature || 0.7
      });
    }
  }, [promptApiData]);

  useEffect(() => {
    if (phonesApiData) {
      setPhoneSettings({
        phone_e164: phonesApiData.phone_e164 || '',
        whatsapp_number: phonesApiData.whatsapp_number || '',
        whatsapp_enabled: phonesApiData.whatsapp_enabled || false,
        working_hours: phonesApiData.working_hours || '08:00-18:00',
        voice_message: phonesApiData.voice_message || 'שלום, הגעתם לתמיכה הטכנית של מערכת ניהול הנדל"ן. אנחנו כאן לעזור לכם.'
      });
    }
  }, [phonesApiData]);

  const handleSavePrompt = async () => {
    setSaving(true);
    setSaveStatus(null);
    
    try {
      await adminApi.updateSupportPrompt({
        ai_prompt: promptData.prompt,
        model: promptData.model,
        max_tokens: promptData.maxTokens,
        temperature: promptData.temperature
      });
      setSaveStatus('success');
      refetchPrompt(); // Refresh data from server
    } catch (error) {
      setSaveStatus('error');
      console.error('Failed to save prompt:', error);
    } finally {
      setSaving(false);
      // Clear status after 3 seconds
      setTimeout(() => setSaveStatus(null), 3000);
    }
  };

  const handleSavePhones = async () => {
    setSaving(true);
    setSaveStatus(null);
    
    try {
      await adminApi.updateSupportPhones({
        phone_e164: phoneSettings.phone_e164,
        whatsapp_number: phoneSettings.whatsapp_number,
        whatsapp_enabled: phoneSettings.whatsapp_enabled,
        working_hours: phoneSettings.working_hours,
        voice_message: phoneSettings.voice_message
      });
      setSaveStatus('success');
      refetchPhones(); // Refresh data from server
    } catch (error) {
      setSaveStatus('error');
      console.error('Failed to save phone settings:', error);
    } finally {
      setSaving(false);
      // Clear status after 3 seconds
      setTimeout(() => setSaveStatus(null), 3000);
    }
  };

  return (
    <div className="min-h-screen bg-slate-50 p-4 md:p-6" dir="rtl">
      <div className="max-w-5xl mx-auto">
        {/* Page Header */}
        <div className="mb-6">
          <div className="flex items-center gap-3 mb-2">
            <button
              onClick={() => navigate('/app/admin/overview')}
              className="text-blue-600 hover:text-blue-700 text-sm font-medium flex items-center gap-1"
            >
              ← חזור לדף הבית
            </button>
          </div>
          <h1 className="text-2xl md:text-3xl font-semibold text-slate-900 flex items-center gap-3">
            <Headphones className="h-8 w-8 text-blue-600" />
            ניהול תמיכה
          </h1>
          <p className="text-slate-600 mt-2">
            נהלו את הפרומפט והטלפונים שלכם לתמיכה בלקוחות
          </p>
        </div>

        {/* Tab Navigation */}
        <div className="mb-6">
          <nav className="flex space-x-8" dir="ltr">
            <button
              onClick={() => setActiveTab('prompt')}
              className={`py-2 px-1 border-b-2 font-medium text-sm flex items-center gap-2 ${
                activeTab === 'prompt'
                  ? 'border-blue-500 text-blue-600'
                  : 'border-transparent text-slate-500 hover:text-slate-700 hover:border-slate-300'
              }`}
            >
              <MessageCircle className="h-4 w-4" />
              פרומפט AI
            </button>
            <button
              onClick={() => setActiveTab('phones')}
              className={`py-2 px-1 border-b-2 font-medium text-sm flex items-center gap-2 ${
                activeTab === 'phones'
                  ? 'border-blue-500 text-blue-600'
                  : 'border-transparent text-slate-500 hover:text-slate-700 hover:border-slate-300'
              }`}
            >
              <Phone className="h-4 w-4" />
              הגדרות טלפון
            </button>
          </nav>
        </div>

        {/* Prompt Tab */}
        {activeTab === 'prompt' && (
          <Card className="p-6" data-testid="card-admin-prompt">
            {promptLoading ? (
              <div className="flex items-center justify-center py-12">
                <Loader2 className="h-6 w-6 animate-spin text-slate-400" />
                <span className="text-slate-600 mr-2">טוען הגדרות פרומפט...</span>
              </div>
            ) : promptError ? (
              <div className="mb-4 p-3 bg-red-50 border border-red-200 rounded-lg">
                <div className="flex items-center gap-2 text-red-700">
                  <AlertCircle className="h-4 w-4" />
                  <span className="text-sm">שגיאה בטעינת פרומפט: {promptError.message}</span>
                </div>
              </div>
            ) : (
            <div>
            <div className="flex items-center justify-between mb-6">
              <h2 className="text-lg font-semibold text-slate-900">פרומפט תמיכה</h2>
              <div className="flex items-center gap-2">
                {saveStatus === 'success' && (
                  <div className="flex items-center gap-1 text-green-600 text-sm">
                    <CheckCircle className="h-4 w-4" />
                    נשמר בהצלחה
                  </div>
                )}
                {saveStatus === 'error' && (
                  <div className="flex items-center gap-1 text-red-600 text-sm">
                    <AlertCircle className="h-4 w-4" />
                    שגיאה בשמירה
                  </div>
                )}
              </div>
            </div>

            <div className="space-y-6">
              {/* Prompt Text */}
              <div>
                <label className="block text-sm font-medium text-slate-700 mb-2">
                  טקסט הפרומפט
                </label>
                <textarea
                  value={promptData.prompt}
                  onChange={(e) => setPromptData(prev => ({ ...prev, prompt: e.target.value }))}
                  className="w-full h-32 px-3 py-2 border border-slate-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent resize-none text-sm"
                  placeholder="הכנסו את הפרומפט לתמיכה..."
                  data-testid="textarea-admin-prompt"
                />
              </div>

              {/* AI Settings Grid */}
              <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                <div>
                  <label className="block text-sm font-medium text-slate-700 mb-1">
                    מודל AI
                  </label>
                  <select
                    value={promptData.model}
                    onChange={(e) => setPromptData(prev => ({ ...prev, model: e.target.value }))}
                    className="w-full px-3 py-2 border border-slate-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent text-sm"
                    data-testid="select-admin-model"
                  >
                    <option value="gpt-4o-mini">GPT-4o Mini</option>
                    <option value="gpt-4o">GPT-4o</option>
                    <option value="gpt-3.5-turbo">GPT-3.5 Turbo</option>
                  </select>
                </div>

                <div>
                  <label className="block text-sm font-medium text-slate-700 mb-1">
                    מקס טוקנים
                  </label>
                  <input
                    type="number"
                    value={promptData.maxTokens}
                    onChange={(e) => setPromptData(prev => ({ ...prev, maxTokens: parseInt(e.target.value) || 150 }))}
                    className="w-full px-3 py-2 border border-slate-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent text-sm"
                    min="50"
                    max="4000"
                    data-testid="input-admin-max-tokens"
                  />
                </div>

                <div>
                  <label className="block text-sm font-medium text-slate-700 mb-1">
                    טמפרטורה
                  </label>
                  <input
                    type="number"
                    value={promptData.temperature}
                    onChange={(e) => setPromptData(prev => ({ ...prev, temperature: parseFloat(e.target.value) || 0.7 }))}
                    className="w-full px-3 py-2 border border-slate-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent text-sm"
                    min="0"
                    max="2"
                    step="0.1"
                    data-testid="input-admin-temperature"
                  />
                </div>
              </div>

              {/* Save Button */}
              <div className="flex justify-end">
                <button
                  onClick={handleSavePrompt}
                  disabled={saving}
                  className="flex items-center gap-2 px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed transition-colors text-sm font-medium"
                  data-testid="button-save-prompt"
                >
                  {saving ? (
                    <Loader2 className="h-4 w-4 animate-spin" />
                  ) : (
                    <Save className="h-4 w-4" />
                  )}
                  {saving ? 'שומר...' : 'שמור פרומפט'}
                </button>
              </div>
            </div>
          </div>
          )}
          </Card>
        )}

        {/* Phones Tab */}
        {activeTab === 'phones' && (
          <Card className="p-6" data-testid="card-admin-phones">
            <div className="flex items-center justify-between mb-6">
              <h2 className="text-lg font-semibold text-slate-900">הגדרות טלפון</h2>
              <div className="flex items-center gap-2">
                {saveStatus === 'success' && (
                  <div className="flex items-center gap-1 text-green-600 text-sm">
                    <CheckCircle className="h-4 w-4" />
                    נשמר בהצלחה
                  </div>
                )}
                {saveStatus === 'error' && (
                  <div className="flex items-center gap-1 text-red-600 text-sm">
                    <AlertCircle className="h-4 w-4" />
                    שגיאה בשמירה
                  </div>
                )}
              </div>
            </div>

            <div className="space-y-6">
              {/* Phone Numbers Grid */}
              <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                <div>
                  <label className="block text-sm font-medium text-slate-700 mb-2">
                    מספר טלפון ראשי
                  </label>
                  <input
                    type="tel"
                    value={phoneSettings.phone_e164}
                    onChange={(e) => setPhoneSettings(prev => ({ ...prev, phone_e164: e.target.value }))}
                    className="w-full px-3 py-2 border border-slate-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent text-sm"
                    placeholder="+972-XX-XXX-XXXX"
                    data-testid="input-phone-e164"
                  />
                </div>

                <div>
                  <label className="block text-sm font-medium text-slate-700 mb-2">
                    מספר ווצאפ
                  </label>
                  <input
                    type="tel"
                    value={phoneSettings.whatsapp_number}
                    onChange={(e) => setPhoneSettings(prev => ({ ...prev, whatsapp_number: e.target.value }))}
                    className="w-full px-3 py-2 border border-slate-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent text-sm"
                    placeholder="+972-XX-XXX-XXXX"
                    data-testid="input-whatsapp-number"
                  />
                </div>

                <div>
                  <label className="block text-sm font-medium text-slate-700 mb-2">
                    ווצאפ מופעל
                  </label>
                  <div className="flex items-center h-10">
                    <label className="flex items-center cursor-pointer">
                      <input
                        type="checkbox"
                        checked={phoneSettings.whatsapp_enabled}
                        onChange={(e) => setPhoneSettings(prev => ({ ...prev, whatsapp_enabled: e.target.checked }))}
                        className="sr-only"
                        data-testid="checkbox-whatsapp-enabled"
                      />
                      <div className={`relative inline-block h-6 w-11 rounded-full transition-colors duration-300 ${phoneSettings.whatsapp_enabled ? 'bg-blue-600' : 'bg-gray-300'}`}>
                        <span className={`absolute inline-block h-4 w-4 transform rounded-full bg-white transition-transform duration-300 ${phoneSettings.whatsapp_enabled ? 'translate-x-6' : 'translate-x-1'} top-1`}></span>
                      </div>
                      <span className="mr-3 text-sm text-slate-700">{phoneSettings.whatsapp_enabled ? 'מופעל' : 'כבוי'}</span>
                    </label>
                  </div>
                </div>
              </div>

              {/* Working Hours */}
              <div>
                <label className="block text-sm font-medium text-slate-700 mb-2">
                  שעות פעילות תמיכה
                </label>
                <input
                  type="text"
                  value={phoneSettings.working_hours}
                  onChange={(e) => setPhoneSettings(prev => ({ ...prev, working_hours: e.target.value }))}
                  className="w-full px-3 py-2 border border-slate-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent text-sm"
                  placeholder="08:00-18:00"
                  data-testid="input-working-hours"
                />
              </div>

              {/* Voice Message */}
              <div>
                <label className="block text-sm font-medium text-slate-700 mb-2">
                  הודעה קולית
                </label>
                <textarea
                  value={phoneSettings.voice_message}
                  onChange={(e) => setPhoneSettings(prev => ({ ...prev, voice_message: e.target.value }))}
                  className="w-full h-24 px-3 py-2 border border-slate-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent resize-none text-sm"
                  placeholder="הכנסו הודעה קולית לתמיכה..."
                  data-testid="textarea-voice-message"
                />
              </div>

              {/* Save Button */}
              <div className="flex justify-end">
                <button
                  onClick={handleSavePhones}
                  disabled={saving}
                  className="flex items-center gap-2 px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed transition-colors text-sm font-medium"
                  data-testid="button-save-phones"
                >
                  {saving ? (
                    <Loader2 className="h-4 w-4 animate-spin" />
                  ) : (
                    <Save className="h-4 w-4" />
                  )}
                  {saving ? 'שומר...' : 'שמור הגדרות'}
                </button>
              </div>
            </div>
          </Card>
        )}

        {/* Info Card */}
        <Card className="p-4 mt-6 bg-blue-50 border-blue-200">
          <div className="flex items-start gap-3">
            <Settings className="h-5 w-5 text-blue-600 mt-0.5" />
            <div>
              <h4 className="text-sm font-medium text-blue-900 mb-1">
                אודות ניהול התמיכה
              </h4>
              <p className="text-sm text-blue-700">
                כאן תוכלו לנהל את הפרומפט של לאה (הבוט לתמיכה) ואת הגדרות הטלפון שלכם. 
                השינויים ייכנסו לתוקף מיד לאחר השמירה.
              </p>
            </div>
          </div>
        </Card>
      </div>
    </div>
  );
}