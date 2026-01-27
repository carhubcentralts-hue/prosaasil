/**
 * Lead Tabs Configuration Modal
 * Allows inline editing of tabs directly from the lead detail page
 */
import React, { useState, useEffect } from 'react';
import { X, Plus, Save, RotateCcw, Settings as SettingsIcon, GripVertical } from 'lucide-react';
import { Button } from '../../../shared/components/ui/Button';

// All available tabs with descriptions
const ALL_TABS = [
  { key: 'activity', label: 'פעילות', description: 'ציר זמן של כל הפעילויות' },
  { key: 'reminders', label: 'משימות', description: 'משימות ותזכורות' },
  { key: 'documents', label: 'מסמכים', description: 'חוזים והערות עם קבצים' },
  { key: 'overview', label: 'סקירה', description: 'פרטי הליד המלאים' },
  { key: 'whatsapp', label: 'וואטסאפ', description: 'שליחת הודעות וסיכום שיחות' },
  { key: 'calls', label: 'שיחות טלפון', description: 'היסטוריית שיחות טלפון' },
  { key: 'email', label: 'מייל', description: 'שליחת מיילים ללידים' },
  { key: 'contracts', label: 'חוזים', description: 'ניהול וחתימה על חוזים' },
  { key: 'appointments', label: 'פגישות', description: 'פגישות מתוזמנות' },
  { key: 'ai_notes', label: 'שירות לקוחות AI', description: 'הערות AI אוטומטיות' },
  { key: 'notes', label: 'הערות חופשיות', description: 'הערות ידניות' },
];

interface LeadTabsConfigModalProps {
  isOpen: boolean;
  onClose: () => void;
  currentPrimary: string[];
  currentSecondary: string[];
  onSave: (primary: string[], secondary: string[]) => Promise<void>;
}

export function LeadTabsConfigModal({
  isOpen,
  onClose,
  currentPrimary,
  currentSecondary,
  onSave,
}: LeadTabsConfigModalProps) {
  const [primaryTabs, setPrimaryTabs] = useState<string[]>(currentPrimary);
  const [secondaryTabs, setSecondaryTabs] = useState<string[]>(currentSecondary);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Update local state when props change
  useEffect(() => {
    setPrimaryTabs(currentPrimary);
    setSecondaryTabs(currentSecondary);
  }, [currentPrimary, currentSecondary]);

  const handleSave = async () => {
    try {
      setSaving(true);
      setError(null);

      // Validate
      if (primaryTabs.length === 0) {
        setError('חובה לבחור לפחות טאב אחד ראשי');
        setSaving(false);
        return;
      }

      if (primaryTabs.length > 3) {
        setError('ניתן לבחור עד 3 טאבים ראשיים');
        setSaving(false);
        return;
      }

      if (secondaryTabs.length > 3) {
        setError('ניתן לבחור עד 3 טאבים משניים');
        setSaving(false);
        return;
      }

      await onSave(primaryTabs, secondaryTabs);
      onClose();
    } catch (err) {
      setError('שגיאה בשמירת ההגדרות');
      setSaving(false);
    }
  };

  const handleReset = () => {
    setPrimaryTabs(['activity', 'reminders', 'documents']);
    setSecondaryTabs(['overview', 'whatsapp', 'calls', 'email', 'contracts', 'appointments', 'ai_notes', 'notes']);
  };

  const addToPrimary = (tabKey: string) => {
    if (primaryTabs.length < 3 && !primaryTabs.includes(tabKey)) {
      setPrimaryTabs([...primaryTabs, tabKey]);
      setSecondaryTabs(secondaryTabs.filter(k => k !== tabKey));
    }
  };

  const addToSecondary = (tabKey: string) => {
    if (secondaryTabs.length < 3 && !secondaryTabs.includes(tabKey)) {
      setSecondaryTabs([...secondaryTabs, tabKey]);
      setPrimaryTabs(primaryTabs.filter(k => k !== tabKey));
    }
  };

  const removeFromPrimary = (tabKey: string) => {
    setPrimaryTabs(primaryTabs.filter(k => k !== tabKey));
  };

  const removeFromSecondary = (tabKey: string) => {
    setSecondaryTabs(secondaryTabs.filter(k => k !== tabKey));
  };

  const getAvailableTabs = () => {
    const used = [...primaryTabs, ...secondaryTabs];
    return ALL_TABS.filter(tab => !used.includes(tab.key));
  };

  if (!isOpen) return null;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black bg-opacity-50 p-4" onClick={onClose}>
      <div 
        className="bg-white rounded-lg shadow-xl max-w-4xl w-full max-h-[90vh] overflow-y-auto"
        onClick={(e) => e.stopPropagation()}
        style={{ direction: 'rtl' }}
      >
        {/* Header */}
        <div className="sticky top-0 bg-white border-b border-gray-200 px-6 py-4 flex items-center justify-between">
          <div className="flex items-center gap-3">
            <SettingsIcon className="w-6 h-6 text-blue-600" />
            <div>
              <h2 className="text-xl font-bold text-gray-900">הגדרות טאבים</h2>
              <p className="text-sm text-gray-500">התאם אישית את הטאבים בדף הליד</p>
            </div>
          </div>
          <button
            onClick={onClose}
            className="p-2 hover:bg-gray-100 rounded-lg transition-colors"
          >
            <X className="w-5 h-5 text-gray-500" />
          </button>
        </div>

        {/* Error Message */}
        {error && (
          <div className="mx-6 mt-4 bg-red-50 border border-red-200 text-red-700 px-4 py-3 rounded-lg">
            ❌ {error}
          </div>
        )}

        {/* Content */}
        <div className="p-6 space-y-6">
          {/* Primary and Secondary Tabs */}
          <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
            {/* Primary Tabs */}
            <div className="border border-gray-200 rounded-lg p-4">
              <div className="mb-4">
                <h3 className="text-lg font-semibold text-gray-900 mb-1">
                  טאבים ראשיים ({primaryTabs.length}/3)
                </h3>
                <p className="text-sm text-gray-500">
                  מוצגים תמיד בדף הליד
                </p>
              </div>

              <div className="space-y-2 min-h-[150px]">
                {primaryTabs.map((tabKey) => {
                  const tab = ALL_TABS.find(t => t.key === tabKey);
                  if (!tab) return null;

                  return (
                    <div
                      key={tabKey}
                      className="flex items-center gap-3 p-3 bg-blue-50 border border-blue-200 rounded-lg"
                    >
                      <GripVertical className="w-4 h-4 text-gray-400 flex-shrink-0" />
                      <div className="flex-1 min-w-0">
                        <div className="font-medium text-gray-900 truncate">{tab.label}</div>
                        <div className="text-xs text-gray-500 truncate">{tab.description}</div>
                      </div>
                      <button
                        onClick={() => removeFromPrimary(tabKey)}
                        className="p-1 hover:bg-red-100 rounded transition-colors flex-shrink-0"
                        title="הסר"
                      >
                        <X className="w-4 h-4 text-red-600" />
                      </button>
                    </div>
                  );
                })}

                {primaryTabs.length === 0 && (
                  <div className="text-center py-8 text-gray-400 border-2 border-dashed border-gray-200 rounded-lg">
                    לחץ + בטאבים הזמינים למטה
                  </div>
                )}
              </div>
            </div>

            {/* Secondary Tabs */}
            <div className="border border-gray-200 rounded-lg p-4">
              <div className="mb-4">
                <h3 className="text-lg font-semibold text-gray-900 mb-1">
                  טאבים משניים ({secondaryTabs.length}/3)
                </h3>
                <p className="text-sm text-gray-500">
                  מוצגים בתפריט "עוד"
                </p>
              </div>

              <div className="space-y-2 min-h-[150px]">
                {secondaryTabs.map((tabKey) => {
                  const tab = ALL_TABS.find(t => t.key === tabKey);
                  if (!tab) return null;

                  return (
                    <div
                      key={tabKey}
                      className="flex items-center gap-3 p-3 bg-gray-50 border border-gray-200 rounded-lg"
                    >
                      <GripVertical className="w-4 h-4 text-gray-400 flex-shrink-0" />
                      <div className="flex-1 min-w-0">
                        <div className="font-medium text-gray-900 truncate">{tab.label}</div>
                        <div className="text-xs text-gray-500 truncate">{tab.description}</div>
                      </div>
                      <button
                        onClick={() => removeFromSecondary(tabKey)}
                        className="p-1 hover:bg-red-100 rounded transition-colors flex-shrink-0"
                        title="הסר"
                      >
                        <X className="w-4 h-4 text-red-600" />
                      </button>
                    </div>
                  );
                })}

                {secondaryTabs.length === 0 && (
                  <div className="text-center py-8 text-gray-400 border-2 border-dashed border-gray-200 rounded-lg">
                    לחץ + בטאבים הזמינים למטה
                  </div>
                )}
              </div>
            </div>
          </div>

          {/* Available Tabs */}
          {getAvailableTabs().length > 0 && (
            <div className="border border-gray-200 rounded-lg p-4">
              <h3 className="text-lg font-semibold text-gray-900 mb-4">
                טאבים זמינים
              </h3>
              <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
                {getAvailableTabs().map((tab) => (
                  <div
                    key={tab.key}
                    className="flex items-center gap-3 p-3 bg-white border border-gray-200 rounded-lg hover:border-blue-300 transition-colors"
                  >
                    <div className="flex-1 min-w-0">
                      <div className="font-medium text-gray-900 truncate">{tab.label}</div>
                      <div className="text-xs text-gray-500 truncate">{tab.description}</div>
                    </div>
                    <div className="flex gap-1 flex-shrink-0">
                      {primaryTabs.length < 3 && (
                        <button
                          onClick={() => addToPrimary(tab.key)}
                          className="p-2 hover:bg-blue-100 rounded transition-colors"
                          title="הוסף לטאבים ראשיים"
                        >
                          <Plus className="w-4 h-4 text-blue-600" />
                        </button>
                      )}
                      {secondaryTabs.length < 3 && (
                        <button
                          onClick={() => addToSecondary(tab.key)}
                          className="p-2 hover:bg-gray-100 rounded transition-colors"
                          title="הוסף לטאבים משניים"
                        >
                          <Plus className="w-4 h-4 text-gray-600" />
                        </button>
                      )}
                    </div>
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* Help Text */}
          <div className="bg-blue-50 border border-blue-200 rounded-lg p-4">
            <h4 className="font-semibold text-blue-900 mb-2">💡 טיפים</h4>
            <ul className="text-sm text-blue-800 space-y-1">
              <li>• טאבים ראשיים מוצגים תמיד בדף הליד</li>
              <li>• טאבים משניים זמינים דרך כפתור "עוד"</li>
              <li>• מקסימום 3 טאבים ראשיים ו-3 משניים (6 סה"כ)</li>
              <li>• כפתור כחול + מוסיף לראשיים, כפתור אפור + לטאבים משניים</li>
            </ul>
          </div>
        </div>

        {/* Footer Actions */}
        <div className="sticky bottom-0 bg-gray-50 border-t border-gray-200 px-6 py-4 flex items-center justify-between gap-4">
          <Button
            variant="outline"
            onClick={handleReset}
            disabled={saving}
          >
            <RotateCcw className="w-4 h-4 ml-2" />
            אפס לברירת מחדל
          </Button>

          <div className="flex gap-3">
            <Button
              variant="outline"
              onClick={onClose}
              disabled={saving}
            >
              ביטול
            </Button>
            <Button
              onClick={handleSave}
              disabled={saving}
              className="bg-blue-600 hover:bg-blue-700 text-white"
            >
              {saving ? (
                <>
                  <div className="w-4 h-4 ml-2 border-2 border-white border-t-transparent rounded-full animate-spin" />
                  שומר...
                </>
              ) : (
                <>
                  <Save className="w-4 h-4 ml-2" />
                  שמור שינויים
                </>
              )}
            </Button>
          </div>
        </div>
      </div>
    </div>
  );
}
