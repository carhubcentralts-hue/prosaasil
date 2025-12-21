import React, { useState, useEffect } from 'react';
import { 
  Brain, 
  Save, 
  RefreshCw, 
  Plus,
  Edit,
  Trash2,
  AlertCircle,
  Tag
} from 'lucide-react';
import { http } from '../../services/http';

interface AISettings {
  embedding_enabled: boolean;
  embedding_threshold: number;
  embedding_top_k: number;
  auto_tag_leads: boolean;
  auto_tag_calls: boolean;
  auto_tag_whatsapp: boolean;
}

interface Topic {
  id: number;
  name: string;
  synonyms: string[];
  is_active: boolean;
  created_at?: string;
  updated_at?: string;
}

export function TopicClassificationSection() {
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [rebuilding, setRebuilding] = useState(false);
  const [settings, setSettings] = useState<AISettings>({
    embedding_enabled: false,
    embedding_threshold: 0.78,
    embedding_top_k: 3,
    auto_tag_leads: true,
    auto_tag_calls: true,
    auto_tag_whatsapp: false
  });
  const [topics, setTopics] = useState<Topic[]>([]);
  const [showTopicModal, setShowTopicModal] = useState(false);
  const [editingTopic, setEditingTopic] = useState<Topic | null>(null);
  const [topicForm, setTopicForm] = useState({ name: '', synonyms: '' });

  // Load settings and topics
  useEffect(() => {
    loadData();
  }, []);

  const loadData = async () => {
    try {
      setLoading(true);
      const [aiSettings, topicsData] = await Promise.all([
        http.get<AISettings>('/api/business/ai-settings'),
        http.get<{ topics: Topic[] }>('/api/business/topics')
      ]);
      
      setSettings(aiSettings);
      setTopics(topicsData.topics);
    } catch (err) {
      console.error('Failed to load AI settings:', err);
      alert('שגיאה בטעינת הגדרות AI');
    } finally {
      setLoading(false);
    }
  };

  const saveSettings = async () => {
    setSaving(true);
    try {
      await http.put('/api/business/ai-settings', settings);
      alert('✅ הגדרות סיווג תחומים נשמרו בהצלחה!');
    } catch (err) {
      console.error('Failed to save settings:', err);
      alert('שגיאה בשמירת ההגדרות');
    } finally {
      setSaving(false);
    }
  };

  const rebuildEmbeddings = async () => {
    if (!confirm('האם לבנות מחדש את כל ה-embeddings? זה עשוי לקחת מספר שניות.')) {
      return;
    }

    setRebuilding(true);
    try {
      const result = await http.post<{ success: boolean; topics_updated: number; message: string }>(
        '/api/business/topics/rebuild-embeddings'
      );
      
      if (result.success) {
        alert(`✅ ${result.message}`);
      } else {
        alert(`❌ ${result.message}`);
      }
    } catch (err) {
      console.error('Failed to rebuild embeddings:', err);
      alert('שגיאה בבניית embeddings');
    } finally {
      setRebuilding(false);
    }
  };

  const openTopicModal = (topic?: Topic) => {
    if (topic) {
      setEditingTopic(topic);
      setTopicForm({
        name: topic.name,
        synonyms: topic.synonyms.join(', ')
      });
    } else {
      setEditingTopic(null);
      setTopicForm({ name: '', synonyms: '' });
    }
    setShowTopicModal(true);
  };

  const closeTopicModal = () => {
    setShowTopicModal(false);
    setEditingTopic(null);
    setTopicForm({ name: '', synonyms: '' });
  };

  const saveTopic = async () => {
    if (!topicForm.name.trim()) {
      alert('שם התחום הוא שדה חובה');
      return;
    }

    try {
      const synonyms = topicForm.synonyms
        .split(',')
        .map(s => s.trim())
        .filter(s => s);

      if (editingTopic) {
        // Update existing topic
        await http.put(`/api/business/topics/${editingTopic.id}`, {
          name: topicForm.name,
          synonyms
        });
      } else {
        // Create new topic
        await http.post('/api/business/topics', {
          name: topicForm.name,
          synonyms
        });
      }

      await loadData();
      closeTopicModal();
      alert(editingTopic ? '✅ תחום עודכן בהצלחה!' : '✅ תחום נוסף בהצלחה!');
    } catch (err: any) {
      console.error('Failed to save topic:', err);
      const errorMsg = err?.response?.data?.error || 'שגיאה בשמירת התחום';
      alert(`❌ ${errorMsg}`);
    }
  };

  const deleteTopic = async (topic: Topic) => {
    if (!confirm(`האם למחוק את התחום "${topic.name}"?`)) {
      return;
    }

    try {
      await http.delete(`/api/business/topics/${topic.id}`);
      await loadData();
      alert('✅ תחום הוסר בהצלחה!');
    } catch (err) {
      console.error('Failed to delete topic:', err);
      alert('שגיאה במחיקת התחום');
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
    <>
      {/* Topic Classification Settings */}
      <div className="bg-white rounded-xl shadow-sm border border-slate-200 p-6">
        <div className="flex items-center gap-3 mb-6">
          <div className="w-10 h-10 bg-indigo-100 rounded-lg flex items-center justify-center">
            <Tag className="h-5 w-5 text-indigo-600" />
          </div>
          <div>
            <h3 className="text-lg font-semibold text-slate-900">סיווג תחומים (Embedding)</h3>
            <p className="text-sm text-slate-500">זיהוי אוטומטי של תחום השיחה לפי תוכן</p>
          </div>
        </div>

        <div className="space-y-6">
          {/* Enable Toggle */}
          <div className="flex items-center justify-between p-4 bg-indigo-50 rounded-lg border border-indigo-200">
            <div>
              <h4 className="font-medium text-slate-900">🤖 הפעל סיווג תחומים</h4>
              <p className="text-sm text-slate-600 mt-1">
                זיהוי אוטומטי של תחום השיחה (למשל: "פורץ מנעולים", "קוסמטיקה")
              </p>
            </div>
            <label className="relative inline-flex items-center cursor-pointer">
              <input
                type="checkbox"
                checked={settings.embedding_enabled}
                onChange={(e) => setSettings(prev => ({ ...prev, embedding_enabled: e.target.checked }))}
                className="sr-only peer"
              />
              <div className="w-11 h-6 bg-gray-200 peer-focus:outline-none peer-focus:ring-4 peer-focus:ring-indigo-300 rounded-full peer peer-checked:after:translate-x-full peer-checked:after:border-white after:content-[''] after:absolute after:top-[2px] after:left-[2px] after:bg-white after:border-gray-300 after:border after:rounded-full after:h-5 after:w-5 after:transition-all peer-checked:bg-indigo-600"></div>
            </label>
          </div>

          {/* Settings Grid */}
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            {/* Threshold Slider */}
            <div>
              <label className="block text-sm font-medium text-slate-700 mb-2">
                סף ביטחון (Threshold)
              </label>
              <div className="flex items-center gap-3">
                <input
                  type="range"
                  min="0.5"
                  max="0.95"
                  step="0.01"
                  value={settings.embedding_threshold}
                  onChange={(e) => setSettings(prev => ({ ...prev, embedding_threshold: parseFloat(e.target.value) }))}
                  className="w-full h-2 bg-slate-200 rounded-lg appearance-none cursor-pointer accent-indigo-600"
                />
                <span className="text-sm font-medium text-slate-700 min-w-[60px] text-center">
                  {settings.embedding_threshold.toFixed(2)}
                </span>
              </div>
              <p className="text-xs text-slate-500 mt-1">
                ציון מינימלי לזיהוי תחום (0.5-0.95)
              </p>
            </div>

            {/* Top K Input */}
            <div>
              <label className="block text-sm font-medium text-slate-700 mb-2">
                Top K (כמה התאמות)
              </label>
              <input
                type="number"
                min="1"
                max="10"
                value={settings.embedding_top_k}
                onChange={(e) => setSettings(prev => ({ ...prev, embedding_top_k: parseInt(e.target.value) || 3 }))}
                className="w-full px-3 py-2 border border-slate-300 rounded-lg focus:ring-2 focus:ring-indigo-500 focus:border-indigo-500"
              />
              <p className="text-xs text-slate-500 mt-1">
                כמה תחומים מובילים לשמור (לצפייה)
              </p>
            </div>
          </div>

          {/* Auto-tag Checkboxes */}
          <div className="space-y-3">
            <div className="flex items-center gap-2">
              <input
                type="checkbox"
                id="auto_tag_calls"
                checked={settings.auto_tag_calls}
                onChange={(e) => setSettings(prev => ({ ...prev, auto_tag_calls: e.target.checked }))}
                className="w-4 h-4 text-indigo-600 rounded focus:ring-indigo-500"
              />
              <label htmlFor="auto_tag_calls" className="text-sm text-slate-700">
                תייג שיחות אוטומטית
              </label>
            </div>

            <div className="flex items-center gap-2">
              <input
                type="checkbox"
                id="auto_tag_leads"
                checked={settings.auto_tag_leads}
                onChange={(e) => setSettings(prev => ({ ...prev, auto_tag_leads: e.target.checked }))}
                className="w-4 h-4 text-indigo-600 rounded focus:ring-indigo-500"
              />
              <label htmlFor="auto_tag_leads" className="text-sm text-slate-700">
                תייג לידים אוטומטית
              </label>
            </div>
            <div className="flex items-center gap-2">
              <input
                type="checkbox"
                id="auto_tag_whatsapp"
                checked={settings.auto_tag_whatsapp}
                onChange={(e) => setSettings(prev => ({ ...prev, auto_tag_whatsapp: e.target.checked }))}
                className="w-4 h-4 text-indigo-600 rounded focus:ring-indigo-500"
              />
              <label htmlFor="auto_tag_whatsapp" className="text-sm text-slate-700">
                תייג WhatsApp אוטומטית
              </label>
            </div>
          </div>

          {/* Rebuild Button */}
          <div className="flex items-center gap-3">
            <button
              onClick={rebuildEmbeddings}
              disabled={rebuilding || !settings.embedding_enabled}
              className="flex items-center gap-2 px-4 py-2 bg-slate-600 text-white rounded-lg hover:bg-slate-700 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
            >
              {rebuilding ? (
                <RefreshCw className="h-4 w-4 animate-spin" />
              ) : (
                <RefreshCw className="h-4 w-4" />
              )}
              {rebuilding ? 'בונה...' : 'בנה Embeddings מחדש'}
            </button>
          </div>

          {/* Info Box */}
          <div className="bg-indigo-50 border border-indigo-200 rounded-lg p-4">
            <div className="flex items-start gap-3">
              <AlertCircle className="h-5 w-5 text-indigo-600 flex-shrink-0 mt-0.5" />
              <div className="text-indigo-800">
                <p className="font-medium">איך זה עובד?</p>
                <p className="text-sm mt-1">
                  הסיווג רץ אוטומטית אחרי כל שיחה (לא בזמן אמת). המערכת משווה את התמלול לתחומים שהוגדרו ומזהה את התחום הכי קרוב במשמעות.
                </p>
              </div>
            </div>
          </div>

          {/* Save Button */}
          <div className="flex justify-end pt-4 border-t border-slate-200">
            <button
              onClick={saveSettings}
              disabled={saving}
              className="flex items-center gap-2 px-4 py-2 bg-indigo-600 text-white rounded-lg hover:bg-indigo-700 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
            >
              {saving ? (
                <RefreshCw className="h-4 w-4 animate-spin" />
              ) : (
                <Save className="h-4 w-4" />
              )}
              {saving ? 'שומר...' : 'שמור הגדרות'}
            </button>
          </div>
        </div>
      </div>

      {/* Topics Management */}
      <div className="bg-white rounded-xl shadow-sm border border-slate-200 p-6">
        <div className="flex items-center justify-between mb-6">
          <div>
            <h3 className="text-lg font-semibold text-slate-900">ניהול תחומים</h3>
            <p className="text-sm text-slate-500">הגדר עד 200 תחומים לעסק שלך</p>
          </div>
          <button
            onClick={() => openTopicModal()}
            className="flex items-center gap-2 px-4 py-2 bg-indigo-600 text-white rounded-lg hover:bg-indigo-700 transition-colors"
          >
            <Plus className="h-4 w-4" />
            הוסף תחום
          </button>
        </div>

        {/* Topics Table */}
        {topics.length === 0 ? (
          <div className="text-center py-12 text-slate-500">
            <Tag className="h-12 w-12 mx-auto mb-4 text-slate-300" />
            <p>עדיין לא הוגדרו תחומים</p>
            <p className="text-sm mt-2">לחץ על "הוסף תחום" כדי להתחיל</p>
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full">
              <thead className="bg-slate-50 border-b border-slate-200">
                <tr>
                  <th className="text-right px-4 py-3 text-sm font-medium text-slate-700">שם תחום</th>
                  <th className="text-right px-4 py-3 text-sm font-medium text-slate-700">מילים נרדפות</th>
                  <th className="text-right px-4 py-3 text-sm font-medium text-slate-700">סטטוס</th>
                  <th className="text-left px-4 py-3 text-sm font-medium text-slate-700">פעולות</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-200">
                {topics.map(topic => (
                  <tr key={topic.id} className="hover:bg-slate-50">
                    <td className="px-4 py-3 text-sm text-slate-900">{topic.name}</td>
                    <td className="px-4 py-3 text-sm text-slate-600">
                      {topic.synonyms.length > 0 ? topic.synonyms.join(', ') : '-'}
                    </td>
                    <td className="px-4 py-3 text-sm">
                      <span className={`inline-flex px-2 py-1 text-xs rounded-full ${
                        topic.is_active 
                          ? 'bg-green-100 text-green-800' 
                          : 'bg-gray-100 text-gray-800'
                      }`}>
                        {topic.is_active ? 'פעיל' : 'לא פעיל'}
                      </span>
                    </td>
                    <td className="px-4 py-3 text-sm text-left">
                      <div className="flex items-center gap-2">
                        <button
                          onClick={() => openTopicModal(topic)}
                          className="p-1 text-blue-600 hover:bg-blue-50 rounded"
                          title="ערוך"
                        >
                          <Edit className="h-4 w-4" />
                        </button>
                        <button
                          onClick={() => deleteTopic(topic)}
                          className="p-1 text-red-600 hover:bg-red-50 rounded"
                          title="מחק"
                        >
                          <Trash2 className="h-4 w-4" />
                        </button>
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>

      {/* Topic Modal */}
      {showTopicModal && (
        <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50 p-4">
          <div className="bg-white rounded-lg shadow-xl max-w-md w-full p-6">
            <h3 className="text-lg font-semibold text-slate-900 mb-4">
              {editingTopic ? 'ערוך תחום' : 'הוסף תחום חדש'}
            </h3>

            <div className="space-y-4">
              <div>
                <label className="block text-sm font-medium text-slate-700 mb-2">
                  שם תחום *
                </label>
                <input
                  type="text"
                  value={topicForm.name}
                  onChange={(e) => setTopicForm(prev => ({ ...prev, name: e.target.value }))}
                  placeholder='למשל: "פורץ מנעולים"'
                  className="w-full px-3 py-2 border border-slate-300 rounded-lg focus:ring-2 focus:ring-indigo-500 focus:border-indigo-500"
                  dir="rtl"
                />
              </div>

              <div>
                <label className="block text-sm font-medium text-slate-700 mb-2">
                  מילים נרדפות (אופציונלי)
                </label>
                <textarea
                  value={topicForm.synonyms}
                  onChange={(e) => setTopicForm(prev => ({ ...prev, synonyms: e.target.value }))}
                  placeholder='למשל: "פריצת דלת, פתיחת מנעול"'
                  className="w-full px-3 py-2 border border-slate-300 rounded-lg resize-none focus:ring-2 focus:ring-indigo-500 focus:border-indigo-500"
                  rows={3}
                  dir="rtl"
                />
                <p className="text-xs text-slate-500 mt-1">
                  הפרד מילים נרדפות בפסיק
                </p>
              </div>
            </div>

            <div className="flex justify-end gap-3 mt-6">
              <button
                onClick={closeTopicModal}
                className="px-4 py-2 text-slate-700 hover:bg-slate-100 rounded-lg transition-colors"
              >
                ביטול
              </button>
              <button
                onClick={saveTopic}
                className="px-4 py-2 bg-indigo-600 text-white rounded-lg hover:bg-indigo-700 transition-colors"
              >
                {editingTopic ? 'עדכן' : 'הוסף'}
              </button>
            </div>
          </div>
        </div>
      )}
    </>
  );
}
