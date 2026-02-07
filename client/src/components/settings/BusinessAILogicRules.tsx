/**
 * BusinessAILogicRules - AI Logic Rules Editor for Business
 * Allows business owners to write rules in Hebrew and test them
 */
import React, { useState, useEffect } from 'react';
import { 
  BookOpen, 
  Save, 
  Play, 
  AlertCircle, 
  CheckCircle, 
  Loader2,
  Info
} from 'lucide-react';
import { http } from '../../services/http';

interface CompiledRule {
  id: string;
  priority: number;
  when: Record<string, unknown>;
  action: string;
  effects?: Record<string, unknown>;
}

interface CompiledLogic {
  rules: CompiledRule[];
  constraints: Record<string, unknown>;
  entities_schema: Record<string, unknown>;
}

interface TestResult {
  action: string;
  confidence: number;
  rule_hits: string[];
  reply: string;
  next_question: string | null;
  missing: string[];
  proposed_status: { label: string; confidence: number } | null;
  latency_ms: number;
}

const EXAMPLE_RULES = `• מעל 2 חדרים → לתאם פגישה
• עד 2 חדרים → לאסוף פרטים
• אם לא צוין חדרים → לשאול "כמה חדרים?"
• תמיד שאלה אחת בכל פעם
• אם הסטטוס "חדש" → לאסוף פרטים
• אם הסטטוס "נסגרה הובלה" → לענות רק על שאלות, לא לאסוף פרטים
• אם הסטטוס "נשלחה הצעה" → להתנהג כאיש מכירות רגוע ולנסות לסגור`;

export function BusinessAILogicRules() {
  const [logicText, setLogicText] = useState('');
  const [compiledLogic, setCompiledLogic] = useState<CompiledLogic | null>(null);
  const [compileError, setCompileError] = useState<string | null>(null);
  const [compileVersion, setCompileVersion] = useState(0);
  const [compiledAt, setCompiledAt] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);
  const [loading, setLoading] = useState(true);
  
  // Test sandbox
  const [testMessage, setTestMessage] = useState('');
  const [testStatus, setTestStatus] = useState('');
  const [testResult, setTestResult] = useState<TestResult | null>(null);
  const [testing, setTesting] = useState(false);

  useEffect(() => {
    loadLogic();
  }, []);

  const loadLogic = async () => {
    try {
      setLoading(true);
      const data = await http.get<any>('/api/business/current/ai-logic');
      if (data) {
        setLogicText(data.ai_logic_text || '');
        setCompiledLogic(data.ai_logic_compiled || null);
        setCompileError(data.ai_logic_compile_error || null);
        setCompileVersion(data.ai_logic_compile_version || 0);
        setCompiledAt(data.ai_logic_compiled_at || null);
      }
    } catch (err) {
      console.error('Failed to load AI logic:', err);
    } finally {
      setLoading(false);
    }
  };

  const handleSave = async () => {
    if (!logicText.trim()) return;
    
    setSaving(true);
    setCompileError(null);
    try {
      const data = await http.put<any>('/api/business/current/ai-logic', {
        ai_logic_text: logicText
      });
      
      if (data.ok) {
        setCompiledLogic(data.compiled);
        setCompileVersion(data.compile_version);
        setCompiledAt(new Date().toISOString());
        setCompileError(null);
      } else {
        setCompileError(data.error || 'שגיאה בהידור');
      }
    } catch (err: any) {
      const errorData = err?.response?.data || err?.data;
      setCompileError(errorData?.error || 'שגיאה בשמירה');
    } finally {
      setSaving(false);
    }
  };

  const handleTest = async () => {
    if (!testMessage.trim()) return;
    
    setTesting(true);
    setTestResult(null);
    try {
      const data = await http.post<any>('/api/business/current/ai-logic/test', {
        message: testMessage,
        status_label: testStatus || undefined
      });
      
      if (data.ok) {
        setTestResult(data);
      }
    } catch (err) {
      console.error('Test failed:', err);
    } finally {
      setTesting(false);
    }
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center py-12">
        <Loader2 className="h-6 w-6 animate-spin text-purple-600" />
        <span className="mr-2 text-slate-600">טוען חוקים...</span>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {/* Rules Editor */}
      <div className="bg-white rounded-xl shadow-sm border border-slate-200 p-6">
        <div className="flex items-center gap-3 mb-4">
          <BookOpen className="h-5 w-5 text-purple-600" />
          <h3 className="text-lg font-semibold text-slate-900">חוקים / לוגיקה</h3>
        </div>
        
        <p className="text-sm text-slate-600 mb-4">
          כתבו בעברית את הלוגיקה העסקית שלכם. הבוט יפעל לפי החוקים האלה בוואטסאפ ובשיחות טלפון.
        </p>

        {/* Example hint */}
        <div className="bg-blue-50 border border-blue-200 rounded-lg p-4 mb-4">
          <div className="flex items-start gap-2">
            <Info className="h-4 w-4 text-blue-600 mt-0.5 flex-shrink-0" />
            <div>
              <p className="text-sm font-medium text-blue-800 mb-1">דוגמה לכתיבת חוקים:</p>
              <pre className="text-xs text-blue-700 whitespace-pre-wrap font-sans">{EXAMPLE_RULES}</pre>
            </div>
          </div>
        </div>
        
        <textarea
          value={logicText}
          onChange={(e) => setLogicText(e.target.value)}
          placeholder="כתבו כאן את החוקים שלכם בעברית..."
          className="w-full h-48 px-4 py-3 border border-slate-300 rounded-lg resize-y text-sm focus:outline-none focus:ring-2 focus:ring-purple-500 focus:border-transparent"
          dir="rtl"
          maxLength={10000}
        />
        
        <div className="flex items-center justify-between mt-3">
          <span className="text-xs text-slate-400">
            {logicText.length}/10,000 תווים
          </span>
          <button
            onClick={handleSave}
            disabled={saving || !logicText.trim()}
            className="flex items-center gap-2 px-5 py-2.5 bg-purple-600 text-white rounded-lg hover:bg-purple-700 transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
          >
            {saving ? (
              <Loader2 className="h-4 w-4 animate-spin" />
            ) : (
              <Save className="h-4 w-4" />
            )}
            שמור והדר
          </button>
        </div>

        {/* Compile status */}
        {compileError && (
          <div className="mt-4 bg-red-50 border border-red-200 rounded-lg p-4">
            <div className="flex items-start gap-2">
              <AlertCircle className="h-5 w-5 text-red-600 mt-0.5 flex-shrink-0" />
              <div>
                <p className="text-sm font-medium text-red-800">שגיאה בהידור:</p>
                <p className="text-sm text-red-700 mt-1">{compileError}</p>
              </div>
            </div>
          </div>
        )}

        {compiledLogic && !compileError && (
          <div className="mt-4 bg-green-50 border border-green-200 rounded-lg p-4">
            <div className="flex items-start gap-2">
              <CheckCircle className="h-5 w-5 text-green-600 mt-0.5 flex-shrink-0" />
              <div>
                <p className="text-sm font-medium text-green-800">
                  הידור הצליח! גרסה {compileVersion}
                </p>
                <p className="text-xs text-green-600 mt-1">
                  {compiledLogic.rules?.length || 0} כללים הודרו בהצלחה
                  {compiledAt && ` • ${new Date(compiledAt).toLocaleString('he-IL')}`}
                </p>
              </div>
            </div>
          </div>
        )}
      </div>

      {/* Test Sandbox */}
      <div className="bg-white rounded-xl shadow-sm border border-slate-200 p-6">
        <div className="flex items-center gap-3 mb-4">
          <Play className="h-5 w-5 text-blue-600" />
          <h3 className="text-lg font-semibold text-slate-900">בדיקת חוקים</h3>
        </div>
        
        <p className="text-sm text-slate-600 mb-4">
          כתבו הודעת לקוח לדוגמה כדי לראות איך הבוט יגיב לפי החוקים שהגדרתם.
        </p>

        <div className="grid grid-cols-1 md:grid-cols-2 gap-4 mb-4">
          <div>
            <label className="block text-sm font-medium text-slate-700 mb-1">הודעת לקוח</label>
            <input
              type="text"
              value={testMessage}
              onChange={(e) => setTestMessage(e.target.value)}
              placeholder='לדוגמה: "צריך הובלה ל-3 חדרים"'
              className="w-full px-3 py-2 border border-slate-300 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
              dir="rtl"
            />
          </div>
          <div>
            <label className="block text-sm font-medium text-slate-700 mb-1">סטטוס ליד (אופציונלי)</label>
            <input
              type="text"
              value={testStatus}
              onChange={(e) => setTestStatus(e.target.value)}
              placeholder='לדוגמה: "חדש" או "נסגרה הובלה"'
              className="w-full px-3 py-2 border border-slate-300 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
              dir="rtl"
            />
          </div>
        </div>

        <button
          onClick={handleTest}
          disabled={testing || !testMessage.trim()}
          className="flex items-center gap-2 px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
        >
          {testing ? (
            <Loader2 className="h-4 w-4 animate-spin" />
          ) : (
            <Play className="h-4 w-4" />
          )}
          בדוק
        </button>

        {/* Test results */}
        {testResult && (
          <div className="mt-4 bg-slate-50 border border-slate-200 rounded-lg p-4">
            <h4 className="text-sm font-medium text-slate-800 mb-3">תוצאת הבדיקה:</h4>
            <div className="space-y-2 text-sm">
              <div className="flex items-center gap-2">
                <span className="font-medium text-slate-600 min-w-[80px]">פעולה:</span>
                <span className="px-2 py-0.5 bg-purple-100 text-purple-700 rounded text-xs font-mono">
                  {testResult.action}
                </span>
              </div>
              <div className="flex items-center gap-2">
                <span className="font-medium text-slate-600 min-w-[80px]">ביטחון:</span>
                <span className={`text-xs font-medium ${
                  testResult.confidence >= 0.65 ? 'text-green-600' : 'text-amber-600'
                }`}>
                  {(testResult.confidence * 100).toFixed(0)}%
                </span>
              </div>
              {testResult.rule_hits && testResult.rule_hits.length > 0 && (
                <div className="flex items-center gap-2">
                  <span className="font-medium text-slate-600 min-w-[80px]">כללים:</span>
                  <span className="text-xs text-slate-700">
                    {testResult.rule_hits.join(', ')}
                  </span>
                </div>
              )}
              {testResult.reply && (
                <div>
                  <span className="font-medium text-slate-600">תשובה:</span>
                  <div className="mt-1 px-3 py-2 bg-white border border-slate-200 rounded text-slate-800" dir="rtl">
                    {testResult.reply}
                  </div>
                </div>
              )}
              {testResult.missing && testResult.missing.length > 0 && (
                <div className="flex items-center gap-2">
                  <span className="font-medium text-slate-600 min-w-[80px]">חסר:</span>
                  <span className="text-xs text-amber-700">
                    {testResult.missing.join(', ')}
                  </span>
                </div>
              )}
              <div className="flex items-center gap-2">
                <span className="font-medium text-slate-600 min-w-[80px]">זמן:</span>
                <span className="text-xs text-slate-500">
                  {testResult.latency_ms}ms
                </span>
              </div>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}

export default BusinessAILogicRules;
