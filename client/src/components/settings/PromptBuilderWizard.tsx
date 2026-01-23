/**
 * PromptBuilderWizard Component
 * Short questionnaire that generates high-quality AI prompts for businesses
 * Can be used standalone or embedded in BusinessAISettings
 */
import React, { useState, useEffect } from 'react';
import { 
  Wand2, 
  X, 
  Loader2,
  Save,
  ChevronRight,
  ChevronLeft
} from 'lucide-react';
import { http } from '../../services/http';

// Types
interface Question {
  id: string;
  question: string;
  placeholder: string;
  required: boolean;
  type: 'text' | 'textarea' | 'select';
  options?: { value: string; label: string }[];
}

interface PromptBuilderProps {
  isOpen: boolean;
  onClose: () => void;
  onSave: (promptText: string, channel: 'calls' | 'whatsapp') => void;
  initialChannel?: 'calls' | 'whatsapp';
}

export function PromptBuilderWizard({ isOpen, onClose, onSave, initialChannel = 'calls' }: PromptBuilderProps) {
  const [questions, setQuestions] = useState<Question[]>([]);
  const [answers, setAnswers] = useState<Record<string, string>>({});
  const [loading, setLoading] = useState(true);
  const [generating, setGenerating] = useState(false);
  const [generatedPrompt, setGeneratedPrompt] = useState('');
  const [promptTitle, setPromptTitle] = useState('');
  const [promptSummary, setPromptSummary] = useState('');
  const [step, setStep] = useState<'questions' | 'preview'>('questions');
  const [selectedChannel, setSelectedChannel] = useState<'calls' | 'whatsapp'>(initialChannel);
  const [error, setError] = useState('');

  useEffect(() => {
    if (isOpen) {
      loadQuestions();
    }
  }, [isOpen]);

  const loadQuestions = async () => {
    try {
      setLoading(true);
      setError('');
      const data = await http.get<{ questions: Question[] }>('/api/ai/prompt_builder/questions');
      setQuestions(data.questions || []);
    } catch (err: any) {
      console.error('Failed to load questions:', err);
      setError('שגיאה בטעינת השאלון');
    } finally {
      setLoading(false);
    }
  };

  const handleGenerate = async () => {
    setGenerating(true);
    setError('');
    try {
      const result = await http.post<{ 
        success: boolean; 
        prompt_text: string; 
        title: string; 
        summary: string;
        error?: string;
      }>(
        '/api/ai/prompt_builder/generate',
        { answers }
      );
      
      if (result.success) {
        setGeneratedPrompt(result.prompt_text);
        setPromptTitle(result.title);
        setPromptSummary(result.summary);
        setStep('preview');
      } else {
        setError(result.error || 'שגיאה ביצירת הפרומפט');
      }
    } catch (err: any) {
      console.error('Failed to generate prompt:', err);
      setError(err.message || 'שגיאה ביצירת הפרומפט');
    } finally {
      setGenerating(false);
    }
  };

  const handleSave = () => {
    onSave(generatedPrompt, selectedChannel);
    onClose();
    // Reset state for next use
    setStep('questions');
    setAnswers({});
    setGeneratedPrompt('');
  };

  const handleClose = () => {
    onClose();
    // Reset state
    setStep('questions');
    setError('');
  };

  if (!isOpen) return null;

  if (loading) {
    return (
      <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50">
        <div className="bg-white rounded-xl p-8 max-w-2xl w-full mx-4" dir="rtl">
          <div className="flex items-center justify-center">
            <Loader2 className="h-8 w-8 animate-spin text-purple-600" />
            <span className="mr-3 text-slate-600">טוען שאלון...</span>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50 p-4" dir="rtl">
      <div className="bg-white rounded-xl max-w-2xl w-full max-h-[90vh] overflow-hidden flex flex-col shadow-xl">
        {/* Header */}
        <div className="flex items-center justify-between p-4 border-b border-slate-200 bg-gradient-to-l from-purple-50 to-white">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 bg-purple-100 rounded-lg flex items-center justify-center">
              <Wand2 className="h-5 w-5 text-purple-600" />
            </div>
            <div>
              <h2 className="text-lg font-bold text-slate-900">מחולל פרומפטים אוטומטי</h2>
              <p className="text-sm text-slate-500">
                {step === 'questions' ? 'ענה על השאלות ליצירת פרומפט מותאם' : 'סקור ושמור את הפרומפט'}
              </p>
            </div>
          </div>
          <button 
            onClick={handleClose} 
            className="p-2 hover:bg-slate-100 rounded-lg transition-colors"
          >
            <X className="h-5 w-5 text-slate-500" />
          </button>
        </div>

        {/* Error Message */}
        {error && (
          <div className="mx-6 mt-4 p-3 bg-red-50 border border-red-200 rounded-lg text-red-700 text-sm">
            {error}
          </div>
        )}

        {/* Content */}
        <div className="flex-1 overflow-y-auto p-6">
          {step === 'questions' ? (
            <div className="space-y-5">
              {questions.map((q) => (
                <div key={q.id} className="space-y-2">
                  <label className="block text-sm font-medium text-slate-700">
                    {q.question}
                    {q.required && <span className="text-red-500 mr-1">*</span>}
                  </label>
                  
                  {q.type === 'select' ? (
                    <select
                      value={answers[q.id] || ''}
                      onChange={(e) => setAnswers(prev => ({ ...prev, [q.id]: e.target.value }))}
                      className="w-full p-3 border border-slate-300 rounded-lg focus:ring-2 focus:ring-purple-500 focus:border-purple-500 bg-white"
                    >
                      <option value="">בחר...</option>
                      {q.options?.map((opt) => (
                        <option key={opt.value} value={opt.value}>{opt.label}</option>
                      ))}
                    </select>
                  ) : q.type === 'textarea' ? (
                    <textarea
                      value={answers[q.id] || ''}
                      onChange={(e) => setAnswers(prev => ({ ...prev, [q.id]: e.target.value }))}
                      placeholder={q.placeholder}
                      maxLength={500}
                      className="w-full p-3 border border-slate-300 rounded-lg resize-none h-20 focus:ring-2 focus:ring-purple-500 focus:border-purple-500"
                    />
                  ) : (
                    <input
                      type="text"
                      value={answers[q.id] || ''}
                      onChange={(e) => setAnswers(prev => ({ ...prev, [q.id]: e.target.value }))}
                      placeholder={q.placeholder}
                      maxLength={500}
                      className="w-full p-3 border border-slate-300 rounded-lg focus:ring-2 focus:ring-purple-500 focus:border-purple-500"
                    />
                  )}
                </div>
              ))}
            </div>
          ) : (
            <div className="space-y-5">
              {/* Summary Card */}
              <div className="bg-purple-50 border border-purple-200 rounded-lg p-4">
                <h3 className="font-semibold text-purple-900 mb-1">{promptTitle}</h3>
                <p className="text-purple-700 text-sm">{promptSummary}</p>
              </div>
              
              {/* Generated Prompt */}
              <div>
                <label className="block text-sm font-medium text-slate-700 mb-2">
                  הפרומפט שנוצר (ניתן לעריכה):
                </label>
                <textarea
                  value={generatedPrompt}
                  onChange={(e) => setGeneratedPrompt(e.target.value)}
                  className="w-full p-4 border border-slate-300 rounded-lg resize-none h-56 text-sm leading-relaxed focus:ring-2 focus:ring-purple-500 focus:border-purple-500 font-mono"
                />
              </div>
              
              {/* Channel Selection */}
              <div className="bg-slate-50 border border-slate-200 rounded-lg p-4">
                <label className="block text-sm font-medium text-slate-700 mb-3">
                  שמור עבור ערוץ:
                </label>
                <div className="flex gap-4">
                  <label className="flex items-center gap-2 cursor-pointer p-3 border rounded-lg hover:bg-white transition-colors flex-1">
                    <input
                      type="radio"
                      name="channel"
                      value="calls"
                      checked={selectedChannel === 'calls'}
                      onChange={() => setSelectedChannel('calls')}
                      className="w-4 h-4 text-purple-600"
                    />
                    <span className="text-slate-700">📞 שיחות טלפון</span>
                  </label>
                  <label className="flex items-center gap-2 cursor-pointer p-3 border rounded-lg hover:bg-white transition-colors flex-1">
                    <input
                      type="radio"
                      name="channel"
                      value="whatsapp"
                      checked={selectedChannel === 'whatsapp'}
                      onChange={() => setSelectedChannel('whatsapp')}
                      className="w-4 h-4 text-purple-600"
                    />
                    <span className="text-slate-700">💬 WhatsApp</span>
                  </label>
                </div>
              </div>
            </div>
          )}
        </div>

        {/* Footer */}
        <div className="flex items-center justify-between p-4 border-t border-slate-200 bg-slate-50">
          {step === 'questions' ? (
            <>
              <button
                onClick={handleClose}
                className="px-4 py-2 text-slate-600 hover:text-slate-800 transition-colors"
              >
                ביטול
              </button>
              <button
                onClick={handleGenerate}
                disabled={generating || !answers.business_area}
                className="flex items-center gap-2 px-6 py-2.5 bg-purple-600 text-white rounded-lg hover:bg-purple-700 disabled:opacity-50 disabled:cursor-not-allowed transition-colors min-h-[44px]"
              >
                {generating ? (
                  <>
                    <Loader2 className="h-4 w-4 animate-spin" />
                    מייצר פרומפט...
                  </>
                ) : (
                  <>
                    <Wand2 className="h-4 w-4" />
                    צור פרומפט
                    <ChevronLeft className="h-4 w-4" />
                  </>
                )}
              </button>
            </>
          ) : (
            <>
              <button
                onClick={() => setStep('questions')}
                className="flex items-center gap-2 px-4 py-2 text-slate-600 hover:text-slate-800 transition-colors"
              >
                <ChevronRight className="h-4 w-4" />
                חזרה לשאלון
              </button>
              <button
                onClick={handleSave}
                className="flex items-center gap-2 px-6 py-2.5 bg-green-600 text-white rounded-lg hover:bg-green-700 transition-colors min-h-[44px]"
              >
                <Save className="h-4 w-4" />
                שמור פרומפט
              </button>
            </>
          )}
        </div>
      </div>
    </div>
  );
}

export default PromptBuilderWizard;
