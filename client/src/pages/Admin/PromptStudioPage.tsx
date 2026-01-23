/**
 * PromptStudioPage - AI Prompt Management Studio
 * Provides prompt creation, testing, and voice configuration
 */
import React, { useState } from 'react';
import { 
  Bot, 
  Wand2, 
  Mic, 
  AlertCircle
} from 'lucide-react';
import { http } from '../../services/http';
import { useAuth } from '../../features/auth/hooks';
import { PromptBuilderWizard } from '../../components/settings/PromptBuilderWizard';
import { VoiceTesterCard } from '../../components/settings/VoiceTesterCard';
import { BusinessAISettings } from '../../components/settings/BusinessAISettings';

export function PromptStudioPage() {
  const { user } = useAuth();
  const [activeTab, setActiveTab] = useState<'prompts' | 'builder' | 'tester'>('prompts');
  const [showBuilderWizard, setShowBuilderWizard] = useState(false);
  const [saving, setSaving] = useState(false);

  const handleSaveGeneratedPrompt = async (promptText: string, channel: 'calls' | 'whatsapp') => {
    setSaving(true);
    try {
      await http.post('/api/ai/prompt_builder/save', {
        prompt_text: promptText,
        channel,
        update_existing: true
      });
      alert('הפרומפט נשמר בהצלחה!');
    } catch (err) {
      console.error('Failed to save prompt:', err);
      alert('שגיאה בשמירת הפרומפט');
    } finally {
      setSaving(false);
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
          onClick={() => setActiveTab('prompts')}
          className={`px-4 py-3 text-sm font-medium border-b-2 transition-colors ${
            activeTab === 'prompts'
              ? 'border-purple-600 text-purple-600'
              : 'border-transparent text-slate-500 hover:text-slate-700'
          }`}
        >
          עריכת פרומפטים
        </button>
        <button
          onClick={() => setActiveTab('builder')}
          className={`px-4 py-3 text-sm font-medium border-b-2 transition-colors ${
            activeTab === 'builder'
              ? 'border-purple-600 text-purple-600'
              : 'border-transparent text-slate-500 hover:text-slate-700'
          }`}
        >
          מחולל פרומפטים
        </button>
        <button
          onClick={() => setActiveTab('tester')}
          className={`px-4 py-3 text-sm font-medium border-b-2 transition-colors ${
            activeTab === 'tester'
              ? 'border-purple-600 text-purple-600'
              : 'border-transparent text-slate-500 hover:text-slate-700'
          }`}
        >
          בדיקת שיחה חיה
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
              <Wand2 className="h-16 w-16 text-purple-300 mx-auto mb-4" />
              <h3 className="text-xl font-semibold text-slate-900 mb-2">מחולל פרומפטים חכם</h3>
              <p className="text-slate-600 mb-6 max-w-md mx-auto">
                ענה על מספר שאלות קצרות על העסק שלך, והמערכת תיצור פרומפט מקצועי מותאם אישית.
              </p>
              <button
                onClick={() => setShowBuilderWizard(true)}
                className="flex items-center gap-2 px-6 py-3 bg-purple-600 text-white rounded-lg hover:bg-purple-700 transition-colors mx-auto min-h-[48px]"
              >
                <Wand2 className="h-5 w-5" />
                התחל ליצור פרומפט
              </button>
            </div>
          </div>
        </div>
      )}

      {activeTab === 'tester' && (
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
          <VoiceTesterCard />
        </div>
      )}

      {/* Prompt Builder Wizard Modal */}
      <PromptBuilderWizard
        isOpen={showBuilderWizard}
        onClose={() => setShowBuilderWizard(false)}
        onSave={handleSaveGeneratedPrompt}
      />
    </div>
  );
}

export default PromptStudioPage;
