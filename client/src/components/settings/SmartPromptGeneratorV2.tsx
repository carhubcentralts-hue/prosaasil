/**
 * Smart Prompt Generator v2 - Structured Template-Based Prompt Builder
 * 
 * Key Features:
 * - Structured questionnaire (not free-form)
 * - Rigid template enforcement
 * - Quality gate validation
 * - Provider selection (OpenAI/Gemini)
 * - Preview mode with warnings
 * - Read-only generated prompt display
 */
import React, { useState, useEffect } from 'react';
import { 
  Wand2, 
  X, 
  Loader2,
  Save,
  AlertTriangle,
  CheckCircle2,
  Edit3,
  RefreshCw,
  Sparkles,
  Shield
} from 'lucide-react';
import { http } from '../../services/http';

// Types
interface Field {
  id: string;
  label: string;
  type: 'text' | 'textarea' | 'select' | 'tags';
  required: boolean;
  placeholder?: string;
  maxLength?: number;
  maxItems?: number;
  options?: { value: string; label: string }[];
}

interface InputSchema {
  fields: Field[];
}

interface Provider {
  id: string;
  name: string;
  default: boolean;
  models: string[];
  description: string;
  available: boolean;
}

interface GenerateResult {
  success: boolean;
  prompt_text: string;
  provider: string;
  model: string;
  length: number;
  validation: {
    passed: boolean;
    sections_found: string[];
  };
  error?: string;
  validation_error?: string;
  suggestion?: string;
}

interface SmartPromptGeneratorProps {
  isOpen: boolean;
  onClose: () => void;
  onSave: (promptText: string, channel: 'calls' | 'whatsapp', metadata: any) => void;
  initialChannel?: 'calls' | 'whatsapp';
}

export function SmartPromptGeneratorV2({ 
  isOpen, 
  onClose, 
  onSave, 
  initialChannel = 'calls' 
}: SmartPromptGeneratorProps) {
  const [schema, setSchema] = useState<InputSchema | null>(null);
  const [providers, setProviders] = useState<Provider[]>([]);
  const [questionnaire, setQuestionnaire] = useState<Record<string, any>>({});
  const [selectedProvider, setSelectedProvider] = useState<string>('openai');
  const [loading, setLoading] = useState(true);
  const [generating, setGenerating] = useState(false);
  const [generatedPrompt, setGeneratedPrompt] = useState('');
  const [generationMetadata, setGenerationMetadata] = useState<any>(null);
  const [step, setStep] = useState<'questionnaire' | 'preview'>('questionnaire');
  const [selectedChannel, setSelectedChannel] = useState<'calls' | 'whatsapp'>(initialChannel);
  const [error, setError] = useState('');
  const [validationError, setValidationError] = useState('');

  useEffect(() => {
    if (isOpen) {
      loadSchemaAndProviders();
    }
  }, [isOpen]);

  const loadSchemaAndProviders = async () => {
    try {
      setLoading(true);
      setError('');
      
      const [schemaData, providersData] = await Promise.all([
        http.get<InputSchema>('/api/ai/smart_prompt_generator/schema'),
        http.get<{ providers: Provider[]; default_provider: string }>('/api/ai/smart_prompt_generator/providers')
      ]);
      
      setSchema(schemaData);
      setProviders(providersData.providers);
      setSelectedProvider(providersData.default_provider);
    } catch (err: any) {
      console.error('Failed to load schema/providers:', err);
      setError('שגיאה בטעינת השאלון');
    } finally {
      setLoading(false);
    }
  };

  const handleFieldChange = (fieldId: string, value: any) => {
    setQuestionnaire(prev => ({ ...prev, [fieldId]: value }));
  };

  const handleTagsChange = (fieldId: string, value: string) => {
    if (!value.trim()) return;
    
    const currentTags = questionnaire[fieldId] || [];
    const field = schema?.fields.find(f => f.id === fieldId);
    const maxItems = field?.maxItems || 10;
    
    if (currentTags.length < maxItems && !currentTags.includes(value)) {
      handleFieldChange(fieldId, [...currentTags, value]);
    }
  };

  const handleRemoveTag = (fieldId: string, tag: string) => {
    const currentTags = questionnaire[fieldId] || [];
    handleFieldChange(fieldId, currentTags.filter((t: string) => t !== tag));
  };

  const validateForm = (): boolean => {
    if (!schema) return false;
    
    for (const field of schema.fields) {
      if (field.required && !questionnaire[field.id]) {
        setError(`שדה חובה: ${field.label}`);
        return false;
      }
    }
    
    return true;
  };

  const handleGenerate = async () => {
    if (!validateForm()) return;
    
    setGenerating(true);
    setError('');
    setValidationError('');
    
    try {
      const result = await http.post<GenerateResult>(
        '/api/ai/smart_prompt_generator/generate',
        { 
          questionnaire,
          provider: selectedProvider
        }
      );
      
      if (result.success) {
        setGeneratedPrompt(result.prompt_text);
        setGenerationMetadata({
          provider: result.provider,
          model: result.model,
          length: result.length,
          validation: result.validation
        });
        setStep('preview');
      } else {
        setError(result.error || 'שגיאה ביצירת הפרומפט');
        if (result.validation_error) {
          setValidationError(result.validation_error);
        }
      }
    } catch (err: any) {
      console.error('Failed to generate prompt:', err);
      setError(err.message || 'שגיאה ביצירת הפרומפט');
    } finally {
      setGenerating(false);
    }
  };

  const handleSave = async () => {
    try {
      const result = await http.post('/api/ai/smart_prompt_generator/save', {
        prompt_text: generatedPrompt,
        channel: selectedChannel,
        metadata: generationMetadata
      });
      
      if (result.success) {
        onSave(generatedPrompt, selectedChannel, generationMetadata);
        handleClose();
      }
    } catch (err: any) {
      console.error('Failed to save prompt:', err);
      setError(err.message || 'שגיאה בשמירת הפרומפט');
    }
  };

  const handleManualEdit = () => {
    // Allow editing by enabling the textarea
    setStep('preview');
  };

  const handleClose = () => {
    onClose();
    // Reset state
    setStep('questionnaire');
    setQuestionnaire({});
    setGeneratedPrompt('');
    setError('');
    setValidationError('');
  };

  if (!isOpen) return null;

  if (loading) {
    return (
      <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50">
        <div className="bg-white rounded-xl p-8 max-w-3xl w-full mx-4" dir="rtl">
          <div className="flex items-center justify-center">
            <Loader2 className="h-8 w-8 animate-spin text-purple-600" />
            <span className="mr-3 text-slate-600">טוען מחולל פרומפטים חכם...</span>
          </div>
        </div>
      </div>
    );
  }

  const currentProvider = providers.find(p => p.id === selectedProvider);
  const availableProviders = providers.filter(p => p.available);

  return (
    <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50 p-4" dir="rtl">
      <div className="bg-white rounded-xl max-w-4xl w-full max-h-[90vh] overflow-hidden flex flex-col shadow-2xl">
        {/* Header */}
        <div className="flex items-center justify-between p-5 border-b border-slate-200 bg-gradient-to-l from-purple-50 via-blue-50 to-white">
          <div className="flex items-center gap-3">
            <div className="w-12 h-12 bg-gradient-to-br from-purple-500 to-blue-500 rounded-xl flex items-center justify-center shadow-lg">
              <Sparkles className="h-6 w-6 text-white" />
            </div>
            <div>
              <h2 className="text-xl font-bold text-slate-900 flex items-center gap-2">
                מחולל פרומפטים חכם v2
                <span className="text-xs bg-purple-100 text-purple-700 px-2 py-0.5 rounded-full font-medium">
                  חדש
                </span>
              </h2>
              <p className="text-sm text-slate-600">
                {step === 'questionnaire' 
                  ? 'ענה על השאלון ליצירת פרומפט מובנה' 
                  : 'סקור ושמור את הפרומפט'}
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

        {/* Error Messages */}
        {error && (
          <div className="mx-6 mt-4 p-3 bg-red-50 border border-red-200 rounded-lg">
            <div className="flex items-start gap-2">
              <AlertTriangle className="h-5 w-5 text-red-600 flex-shrink-0 mt-0.5" />
              <div className="flex-1">
                <p className="text-red-700 text-sm font-medium">{error}</p>
                {validationError && (
                  <p className="text-red-600 text-xs mt-1">פירוט: {validationError}</p>
                )}
              </div>
            </div>
          </div>
        )}

        {/* Content */}
        <div className="flex-1 overflow-y-auto p-6">
          {step === 'questionnaire' ? (
            <div className="space-y-6">
              {/* Provider Selection */}
              <div className="bg-gradient-to-br from-slate-50 to-blue-50 border border-slate-200 rounded-xl p-4">
                <label className="block text-sm font-semibold text-slate-700 mb-3">
                  בחר ספק AI:
                </label>
                <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
                  {availableProviders.map((provider) => (
                    <label 
                      key={provider.id}
                      className={`
                        flex items-start gap-3 p-3 border-2 rounded-lg cursor-pointer transition-all
                        ${selectedProvider === provider.id 
                          ? 'border-purple-500 bg-white shadow-sm' 
                          : 'border-slate-200 hover:border-slate-300 bg-white/50'}
                      `}
                    >
                      <input
                        type="radio"
                        name="provider"
                        value={provider.id}
                        checked={selectedProvider === provider.id}
                        onChange={(e) => setSelectedProvider(e.target.value)}
                        className="mt-1 w-4 h-4 text-purple-600"
                      />
                      <div className="flex-1">
                        <div className="font-medium text-slate-900 flex items-center gap-2">
                          {provider.name}
                          {provider.default && (
                            <span className="text-xs bg-green-100 text-green-700 px-1.5 py-0.5 rounded">
                              ברירת מחדל
                            </span>
                          )}
                        </div>
                        <p className="text-xs text-slate-600 mt-0.5">{provider.description}</p>
                      </div>
                    </label>
                  ))}
                </div>
              </div>

              {/* Questionnaire Fields */}
              <div className="space-y-5">
                {schema?.fields.map((field) => (
                  <div key={field.id} className="space-y-2">
                    <label className="block text-sm font-medium text-slate-700">
                      {field.label}
                      {field.required && <span className="text-red-500 mr-1">*</span>}
                    </label>
                    
                    {field.type === 'select' ? (
                      <select
                        value={questionnaire[field.id] || ''}
                        onChange={(e) => handleFieldChange(field.id, e.target.value)}
                        className="w-full p-3 border border-slate-300 rounded-lg focus:ring-2 focus:ring-purple-500 focus:border-purple-500 bg-white"
                      >
                        <option value="">בחר...</option>
                        {field.options?.map((opt) => (
                          <option key={opt.value} value={opt.value}>{opt.label}</option>
                        ))}
                      </select>
                    ) : field.type === 'textarea' ? (
                      <textarea
                        value={questionnaire[field.id] || ''}
                        onChange={(e) => handleFieldChange(field.id, e.target.value)}
                        placeholder={field.placeholder}
                        maxLength={field.maxLength}
                        className="w-full p-3 border border-slate-300 rounded-lg resize-none h-20 focus:ring-2 focus:ring-purple-500 focus:border-purple-500"
                      />
                    ) : field.type === 'tags' ? (
                      <div>
                        <div className="flex gap-2 mb-2 flex-wrap">
                          {(questionnaire[field.id] || []).map((tag: string) => (
                            <span 
                              key={tag}
                              className="inline-flex items-center gap-1 px-2 py-1 bg-purple-100 text-purple-700 rounded-md text-sm"
                            >
                              {tag}
                              <button
                                onClick={() => handleRemoveTag(field.id, tag)}
                                className="hover:text-purple-900"
                              >
                                <X className="h-3 w-3" />
                              </button>
                            </span>
                          ))}
                        </div>
                        <input
                          type="text"
                          placeholder={field.placeholder}
                          onKeyDown={(e) => {
                            if (e.key === 'Enter') {
                              e.preventDefault();
                              handleTagsChange(field.id, e.currentTarget.value);
                              e.currentTarget.value = '';
                            }
                          }}
                          className="w-full p-3 border border-slate-300 rounded-lg focus:ring-2 focus:ring-purple-500 focus:border-purple-500"
                        />
                        <p className="text-xs text-slate-500 mt-1">
                          הקלד והקש Enter להוספה (עד {field.maxItems} פריטים)
                        </p>
                      </div>
                    ) : (
                      <input
                        type="text"
                        value={questionnaire[field.id] || ''}
                        onChange={(e) => handleFieldChange(field.id, e.target.value)}
                        placeholder={field.placeholder}
                        maxLength={field.maxLength}
                        className="w-full p-3 border border-slate-300 rounded-lg focus:ring-2 focus:ring-purple-500 focus:border-purple-500"
                      />
                    )}
                  </div>
                ))}
              </div>
            </div>
          ) : (
            <div className="space-y-5">
              {/* Success Banner */}
              <div className="bg-gradient-to-r from-green-50 to-emerald-50 border border-green-200 rounded-xl p-4">
                <div className="flex items-start gap-3">
                  <CheckCircle2 className="h-6 w-6 text-green-600 flex-shrink-0" />
                  <div className="flex-1">
                    <h3 className="font-semibold text-green-900">פרומפט נוצר בהצלחה!</h3>
                    <p className="text-sm text-green-700 mt-1">
                      נוצר בעזרת {generationMetadata?.provider === 'gemini' ? 'Google Gemini' : 'OpenAI'} • 
                      {' '}{generationMetadata?.length} תווים • 
                      {' '}עבר בדיקת איכות ✓
                    </p>
                  </div>
                </div>
              </div>

              {/* Warning about System Prompt */}
              <div className="bg-gradient-to-r from-amber-50 to-yellow-50 border border-amber-200 rounded-xl p-4">
                <div className="flex items-start gap-3">
                  <Shield className="h-5 w-5 text-amber-600 flex-shrink-0 mt-0.5" />
                  <div className="flex-1">
                    <h4 className="font-semibold text-amber-900 text-sm">⚠️ זהו פרומפט SYSTEM</h4>
                    <p className="text-xs text-amber-700 mt-1">
                      שינוי לא זהיר עלול לפגוע בשיחה. מומלץ לשמור כפי שנוצר או לערוך בזהירות.
                    </p>
                  </div>
                </div>
              </div>
              
              {/* Generated Prompt - Read Only Initially */}
              <div>
                <label className="block text-sm font-medium text-slate-700 mb-2">
                  הפרומפט שנוצר (תצוגה מקדימה):
                </label>
                <textarea
                  value={generatedPrompt}
                  readOnly
                  className="w-full p-4 border-2 border-slate-300 rounded-lg resize-none h-64 text-sm leading-relaxed font-mono bg-slate-50 text-slate-700"
                  dir="rtl"
                />
                <div className="flex items-center gap-2 mt-2">
                  <button
                    onClick={() => {
                      // Copy to clipboard
                      navigator.clipboard.writeText(generatedPrompt);
                    }}
                    className="text-xs text-purple-600 hover:text-purple-700 flex items-center gap-1"
                  >
                    📋 העתק
                  </button>
                  <span className="text-xs text-slate-400">•</span>
                  <span className="text-xs text-slate-500">
                    {generatedPrompt.length} תווים
                  </span>
                </div>
              </div>
              
              {/* Channel Selection */}
              <div className="bg-slate-50 border border-slate-200 rounded-xl p-4">
                <label className="block text-sm font-medium text-slate-700 mb-3">
                  שמור עבור ערוץ:
                </label>
                <div className="grid grid-cols-2 gap-3">
                  <label className={`
                    flex items-center gap-2 cursor-pointer p-3 border-2 rounded-lg transition-all
                    ${selectedChannel === 'calls' 
                      ? 'border-purple-500 bg-white shadow-sm' 
                      : 'border-slate-200 hover:border-slate-300 bg-white'}
                  `}>
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
                  <label className={`
                    flex items-center gap-2 cursor-pointer p-3 border-2 rounded-lg transition-all
                    ${selectedChannel === 'whatsapp' 
                      ? 'border-purple-500 bg-white shadow-sm' 
                      : 'border-slate-200 hover:border-slate-300 bg-white'}
                  `}>
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
        <div className="flex items-center justify-between p-5 border-t border-slate-200 bg-gradient-to-l from-slate-50 to-white">
          {step === 'questionnaire' ? (
            <>
              <button
                onClick={handleClose}
                className="px-5 py-2.5 text-slate-600 hover:text-slate-800 hover:bg-slate-100 rounded-lg transition-colors"
              >
                ביטול
              </button>
              <button
                onClick={handleGenerate}
                disabled={generating || !questionnaire.business_name || !questionnaire.business_type}
                className="flex items-center gap-2 px-6 py-3 bg-gradient-to-r from-purple-600 to-blue-600 text-white rounded-lg hover:from-purple-700 hover:to-blue-700 disabled:opacity-50 disabled:cursor-not-allowed transition-all shadow-lg disabled:shadow-none min-h-[44px] font-medium"
              >
                {generating ? (
                  <>
                    <Loader2 className="h-5 w-5 animate-spin" />
                    מייצר פרומפט חכם...
                  </>
                ) : (
                  <>
                    <Sparkles className="h-5 w-5" />
                    צור פרומפט מובנה
                  </>
                )}
              </button>
            </>
          ) : (
            <>
              <div className="flex items-center gap-2">
                <button
                  onClick={() => setStep('questionnaire')}
                  className="flex items-center gap-2 px-4 py-2.5 text-slate-600 hover:text-slate-800 hover:bg-slate-100 rounded-lg transition-colors"
                >
                  <RefreshCw className="h-4 w-4" />
                  חזרה לשאלון
                </button>
              </div>
              <div className="flex items-center gap-2">
                <button
                  onClick={handleSave}
                  className="flex items-center gap-2 px-6 py-3 bg-gradient-to-r from-green-600 to-emerald-600 text-white rounded-lg hover:from-green-700 hover:to-emerald-700 transition-all shadow-lg min-h-[44px] font-medium"
                >
                  <Save className="h-5 w-5" />
                  שמור פרומפט
                </button>
              </div>
            </>
          )}
        </div>
      </div>
    </div>
  );
}

export default SmartPromptGeneratorV2;
