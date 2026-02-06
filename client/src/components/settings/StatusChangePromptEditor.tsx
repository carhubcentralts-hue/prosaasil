/**
 * StatusChangePromptEditor - Custom Status Change Behavior Manager
 * Allows businesses to define how AI should change lead statuses
 * 
 * ✅ FIX: Proper state management (loading/loaded/error)
 * ✅ FIX: Update UI from save response
 * ✅ FIX: Retry on network errors
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

  const loadPrompt = async (retryCount = 0) => {
    // ✅ FIX: Reset error before load
    setError('');
    setLoading(true);
    
    try {
      console.log('[StatusPrompt] Loading prompt...');
      const data = await http.get<any>('/api/ai/status_change_prompt/get');
      
      // ✅ FIX: Handle both "ok" and "success" fields for compatibility
      console.log(`[StatusPrompt] Loaded: version=${data.version}, has_custom=${data.has_custom_prompt || data.exists}`);
      
      if (data.ok || data.success) {
        setPromptText(data.prompt || '');
        setOriginalPrompt(data.prompt || '');
        setHasCustomPrompt(data.has_custom_prompt || data.exists || false);
        setVersion(data.version || 0);
        setLoading(false);
      } else {
        throw new Error(data.details || data.error || 'Unknown error');
      }
    } catch (err: any) {
      // Note: err.status is from our http client, err.response?.status is for raw fetch errors
      const errorCode = err.status || err.response?.status;
      const isNetworkError = !errorCode || errorCode === 502 || errorCode === 504 || errorCode === 0;
      
      // ✅ FIX: Retry once on network errors (mobile support)
      if (isNetworkError && retryCount === 0) {
        console.log('[StatusPrompt] Network error, retrying in 500ms...');
        setTimeout(() => loadPrompt(1), 500);
        return;
      }
      
      // ✅ FIX: Extract error message from new format and provide context
      let errorMsg = err.error || err.message || 'שגיאה בטעינת הפרומפט';
      
      // Add more context for common errors
      if (errorCode === 400 && errorMsg.includes('לא נמצא')) {
        errorMsg = 'לא נמצא מזהה עסק. נא להתחבר מחדש או לרענן את הדף.';
      } else if (errorCode === 401 || errorCode === 403) {
        errorMsg = 'אין הרשאה לצפות בפרומפט. נא לוודא שאתה מחובר כמנהל.';
      } else if (errorCode === 500) {
        errorMsg = `שגיאת שרת: ${errorMsg}. אנא נסה שוב או פנה לתמיכה.`;
      }
      
      setError(errorMsg);
      setLoading(false);
      console.error('[StatusPrompt] Error loading prompt:', {
        status: errorCode,
        message: errorMsg,
        details: err.error,
        fullError: err
      });
    }
  };

  const handleSave = async (isRetry = false) => {
    if (!promptText.trim()) {
      setError('טקסט הפרומפט לא יכול להיות ריק');
      return;
    }

    // 🔥 DEFENSIVE CHECK: If we have a custom prompt but version is 0, reload first
    // Only do this check on the first attempt, not on retry, to prevent infinite loops
    if (!isRetry && hasCustomPrompt && version === 0) {
      console.warn('[StatusPrompt] Has custom prompt but version is 0. Reloading...');
      setError('טוען גרסה עדכנית...');
      try {
        await loadPrompt();
        setError('');
        // Retry save after reload completes
        await handleSave(true);
      } catch (err) {
        console.error('[StatusPrompt] Failed to reload:', err);
        setError('שגיאה בטעינת הגרסה העדכנית. אנא רענן את הדף.');
      }
      return;
    }

    setSaving(true);
    setError('');
    setSuccess('');

    try {
      console.log(`[StatusPrompt] Saving with version=${version}${isRetry ? ' (retry)' : ''}`);
      const data = await http.post<any>('/api/ai/status_change_prompt/save', {
        prompt_text: promptText,
        version: version  // ✅ FIX: Send version for optimistic locking
      });
      
      // ✅ FIX: Update UI from response (not assumptions)
      if (data.ok || data.success) {
        // Update state with response data
        const newVersion = data.version;
        const newPrompt = data.prompt || promptText;
        const updatedAt = data.updated_at;
        
        console.log(`[StatusPrompt] Save successful! New version=${newVersion}`);
        
        setVersion(newVersion);
        setPromptText(newPrompt);
        setOriginalPrompt(newPrompt);
        setHasCustomPrompt(true);
        setIsDirty(false);
        setSuccess(data.message || `פרומפט נשמר בהצלחה (גרסה ${newVersion})`);

        if (onSave) {
          onSave(newVersion);
        }

        // Clear success message after 3 seconds
        setTimeout(() => setSuccess(''), 3000);
      } else {
        throw new Error(data.details || data.error || 'Unknown error');
      }
    } catch (err: any) {
      // Note: err.status is from our http client, err.response?.status is for raw fetch errors
      const errorCode = err.status || err.response?.status;
      
      // ✅ FIX: Handle 409 Conflict (someone saved before us)
      if (errorCode === 409) {
        console.warn(`[StatusPrompt] Version conflict! Server has newer version. Reloading...`);
        
        // On conflict, reload the latest prompt from server
        try {
          await loadPrompt();
          setError('מישהו שמר שינויים לפני רגע. הפרומפט עודכן לגרסה החדשה ביותר.');
        } catch (reloadErr) {
          console.error('[StatusPrompt] Failed to reload after conflict:', reloadErr);
          setError('גרסה התיישנה. אנא רענן את הדף.');
        }
      } else {
        // Other errors - provide more context
        let errorMsg = err.error || err.message || 'שגיאה בשמירת הפרומפט';
        
        // Add context for common errors
        if (errorCode === 400) {
          if (errorMsg.includes('EMPTY_PROMPT')) {
            errorMsg = 'טקסט הפרומפט לא יכול להיות ריק';
          } else if (errorMsg.includes('PROMPT_TOO_LONG')) {
            errorMsg = 'הפרומפט ארוך מדי (מקסימום 5000 תווים)';
          } else if (errorMsg.includes('BUSINESS_CONTEXT_REQUIRED')) {
            errorMsg = 'לא נמצא מזהה עסק. נא להתחבר מחדש.';
          }
        } else if (errorCode === 401 || errorCode === 403) {
          errorMsg = 'אין הרשאה לשמור פרומפט. נא לוודא שאתה מחובר כמנהל.';
        } else if (errorCode === 500) {
          errorMsg = `שגיאת שרת: ${errorMsg}. אנא נסה שוב או פנה לתמיכה.`;
        }
        
        setError(errorMsg);
      }
      
      console.error('[StatusPrompt] Error saving prompt:', {
        status: errorCode,
        error: err.error,
        fullError: err
      });
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
          onClick={() => handleSave()}
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
