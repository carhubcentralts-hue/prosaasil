/**
 * StatusChangePromptEditor - Custom Status Change Behavior Manager
 * Allows businesses to define how AI should change lead statuses
 */
import React, { useState, useEffect } from 'react';
import { AlertCircle, CheckCircle, Loader2, Save, RotateCcw } from 'lucide-react';
import { http } from '../../services/http';

interface StatusChangePromptEditorProps {
  businessId?: number;
  onSave?: (version: number) => void;
}

export function StatusChangePromptEditor({ businessId, onSave }: StatusChangePromptEditorProps) {
  const [promptText, setPromptText] = useState('');
  const [originalPrompt, setOriginalPrompt] = useState('');
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [hasCustomPrompt, setHasCustomPrompt] = useState(false);
  const [version, setVersion] = useState(0);
  const [error, setError] = useState('');
  const [success, setSuccess] = useState('');
  const [isDirty, setIsDirty] = useState(false);

  useEffect(() => {
    loadPrompt();
  }, [businessId]);

  useEffect(() => {
    setIsDirty(promptText !== originalPrompt);
  }, [promptText, originalPrompt]);

  const loadPrompt = async () => {
    setLoading(true);
    setError('');
    try {
      const response = await http.get('/api/ai/status_change_prompt/get');
      if (response.data.success) {
        setPromptText(response.data.prompt);
        setOriginalPrompt(response.data.prompt);
        setHasCustomPrompt(response.data.has_custom_prompt);
        setVersion(response.data.version);
      }
    } catch (err: any) {
      setError(err.response?.data?.error || 'שגיאה בטעינת הפרומפט');
      console.error('Error loading status change prompt:', err);
    } finally {
      setLoading(false);
    }
  };

  const handleSave = async () => {
    if (!promptText.trim()) {
      setError('טקסט הפרומפט לא יכול להיות ריק');
      return;
    }

    setSaving(true);
    setError('');
    setSuccess('');

    try {
      const response = await http.post('/api/ai/status_change_prompt/save', {
        prompt_text: promptText
      });

      if (response.data.success) {
        setSuccess(response.data.message);
        setVersion(response.data.version);
        setOriginalPrompt(promptText);
        setHasCustomPrompt(true);
        setIsDirty(false);

        if (onSave) {
          onSave(response.data.version);
        }

        // Clear success message after 3 seconds
        setTimeout(() => setSuccess(''), 3000);
      }
    } catch (err: any) {
      setError(err.response?.data?.error || 'שגיאה בשמירת הפרומפט');
      console.error('Error saving status change prompt:', err);
    } finally {
      setSaving(false);
    }
  };

  const handleReset = () => {
    setPromptText(originalPrompt);
    setError('');
    setSuccess('');
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center py-12">
        <Loader2 className="h-8 w-8 animate-spin text-blue-500" />
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="bg-gradient-to-r from-purple-50 to-blue-50 border border-purple-200 rounded-lg p-6">
        <h2 className="text-xl font-semibold text-gray-900 mb-2">
          🎯 פרומפט לשינוי סטטוסים אוטומטי
        </h2>
        <p className="text-gray-700 text-sm mb-4">
          הגדר כיצד ה-AI צריך לשנות סטטוסים של לידים במהלך שיחות וצ'אטים.
          הפרומפט הזה יחול על כל הערוצים: שיחות טלפון, WhatsApp, ועוד.
        </p>
        
        {hasCustomPrompt ? (
          <div className="flex items-center gap-2 text-sm text-green-700 bg-green-50 px-3 py-2 rounded-md">
            <CheckCircle className="h-4 w-4" />
            <span>פרומפט מותאם אישית פעיל (גרסה {version})</span>
          </div>
        ) : (
          <div className="flex items-center gap-2 text-sm text-blue-700 bg-blue-50 px-3 py-2 rounded-md">
            <AlertCircle className="h-4 w-4" />
            <span>משתמש בפרומפט ברירת מחדל. ניתן להתאים אישית למטה.</span>
          </div>
        )}
      </div>

      {/* Instructions */}
      <div className="bg-amber-50 border border-amber-200 rounded-lg p-4">
        <h3 className="font-semibold text-gray-900 mb-2 flex items-center gap-2">
          <AlertCircle className="h-5 w-5 text-amber-600" />
          💡 טיפים לכתיבת פרומפט אפקטיבי
        </h3>
        <ul className="text-sm text-gray-700 space-y-1 mr-6">
          <li>• הגדר בבירור <strong>מתי</strong> לשנות כל סטטוס (דוגמאות קונקרטיות)</li>
          <li>• ציין רמת ביטחון (confidence) נדרשת לכל שינוי</li>
          <li>• הוסף מגבלות ברורות - <strong>מתי לא</strong> לשנות סטטוס</li>
          <li>• התאם את הסטטוסים הספציפיים לעסק שלך</li>
          <li>• כלול דוגמאות מהחיים האמיתיים</li>
        </ul>
      </div>

      {/* Error/Success Messages */}
      {error && (
        <div className="bg-red-50 border border-red-200 rounded-lg p-4 flex items-start gap-3">
          <AlertCircle className="h-5 w-5 text-red-500 flex-shrink-0 mt-0.5" />
          <div className="text-sm text-red-700">{error}</div>
        </div>
      )}

      {success && (
        <div className="bg-green-50 border border-green-200 rounded-lg p-4 flex items-start gap-3">
          <CheckCircle className="h-5 w-5 text-green-500 flex-shrink-0 mt-0.5" />
          <div className="text-sm text-green-700">{success}</div>
        </div>
      )}

      {/* Editor */}
      <div className="space-y-3">
        <label className="block text-sm font-medium text-gray-700">
          הוראות לשינוי סטטוסים
        </label>
        <textarea
          value={promptText}
          onChange={(e) => setPromptText(e.target.value)}
          className="w-full min-h-[500px] p-4 border border-gray-300 rounded-lg font-mono text-sm 
                     focus:ring-2 focus:ring-blue-500 focus:border-transparent
                     resize-y"
          placeholder="הגדר כיצד ה-AI צריך לשנות סטטוסים..."
          dir="rtl"
        />
        <div className="flex items-center justify-between text-xs text-gray-500">
          <span>{promptText.length} / 5000 תווים</span>
          {isDirty && <span className="text-amber-600 font-medium">* שינויים שלא נשמרו</span>}
        </div>
      </div>

      {/* Actions */}
      <div className="flex items-center justify-between border-t pt-6">
        <button
          onClick={handleReset}
          disabled={!isDirty || saving}
          className="px-4 py-2 text-sm font-medium text-gray-700 bg-white border border-gray-300 rounded-lg
                     hover:bg-gray-50 disabled:opacity-50 disabled:cursor-not-allowed
                     flex items-center gap-2"
        >
          <RotateCcw className="h-4 w-4" />
          בטל שינויים
        </button>

        <button
          onClick={handleSave}
          disabled={!isDirty || saving || promptText.length > 5000}
          className="px-6 py-2 text-sm font-medium text-white bg-blue-600 rounded-lg
                     hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed
                     flex items-center gap-2"
        >
          {saving ? (
            <>
              <Loader2 className="h-4 w-4 animate-spin" />
              שומר...
            </>
          ) : (
            <>
              <Save className="h-4 w-4" />
              שמור פרומפט
            </>
          )}
        </button>
      </div>

      {/* Preview Section */}
      <div className="bg-gray-50 border border-gray-200 rounded-lg p-6">
        <h3 className="font-semibold text-gray-900 mb-3">🔍 איך זה עובד?</h3>
        <div className="space-y-3 text-sm text-gray-700">
          <p>
            <strong>1. שיחה/צ'אט מתחילים:</strong> ה-AI מקבל את הפרומפט הזה כחלק מההנחיות שלו
          </p>
          <p>
            <strong>2. במהלך השיחה:</strong> ה-AI מנתח את תגובות הלקוח ומזהה אינדיקציות לשינוי סטטוס
          </p>
          <p>
            <strong>3. שינוי אוטומטי:</strong> כשהתנאים מתקיימים, ה-AI משנה את הסטטוס ורושם סיבה
          </p>
          <p>
            <strong>4. מעקב:</strong> כל שינוי סטטוס נרשם ב-lead_status_history עם מידע מלא
          </p>
        </div>
      </div>
    </div>
  );
}
