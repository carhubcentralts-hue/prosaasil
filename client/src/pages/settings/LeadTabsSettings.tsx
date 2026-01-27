/**
 * Lead Tabs Configuration Component
 * Allows businesses to customize which tabs appear in the lead detail page
 */
import React, { useState, useEffect } from 'react';
import { GripVertical, Plus, X, Save, RotateCcw, Settings, Eye, EyeOff } from 'lucide-react';
import { useLeadTabsConfig } from '../Leads/hooks/useLeadTabsConfig';
import { Card } from '../../shared/components/ui/Card';
import { Button } from '../../shared/components/ui/Button';

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

export function LeadTabsSettings() {
  const { tabsConfig, loading, updateTabsConfig } = useLeadTabsConfig();
  const [saving, setSaving] = useState(false);
  const [success, setSuccess] = useState(false);
  const [error, setError] = useState<string | null>(null);
  
  // Local state for editing
  const [primaryTabs, setPrimaryTabs] = useState<string[]>([]);
  const [secondaryTabs, setSecondaryTabs] = useState<string[]>([]);
  const [showPreview, setShowPreview] = useState(false);
  
  // Initialize from config
  useEffect(() => {
    if (tabsConfig) {
      setPrimaryTabs(tabsConfig.primary || ['activity', 'reminders', 'documents']);
      setSecondaryTabs(tabsConfig.secondary || ['overview', 'whatsapp', 'calls', 'email']);
    } else {
      // Default configuration
      setPrimaryTabs(['activity', 'reminders', 'documents']);
      setSecondaryTabs(['overview', 'whatsapp', 'calls', 'email', 'contracts', 'appointments', 'ai_notes', 'notes']);
    }
  }, [tabsConfig]);
  
  const handleSave = async () => {
    try {
      setSaving(true);
      setError(null);
      
      // Remove duplicates - ensure no tab appears in both lists
      const uniquePrimary = [...new Set(primaryTabs)];
      const uniqueSecondary = [...new Set(secondaryTabs.filter(tab => !uniquePrimary.includes(tab)))];
      
      // Validate
      if (uniquePrimary.length === 0) {
        setError('חובה לבחור לפחות טאב אחד ראשי');
        return;
      }
      
      if (uniquePrimary.length > 5) {
        setError('ניתן לבחור עד 5 טאבים ראשיים');
        return;
      }
      
      if (uniqueSecondary.length > 5) {
        setError('ניתן לבחור עד 5 טאבים משניים');
        return;
      }
      
      await updateTabsConfig({
        primary: uniquePrimary,
        secondary: uniqueSecondary
      });
      
      setSuccess(true);
      setTimeout(() => setSuccess(false), 3000);
    } catch (err) {
      setError('שגיאה בשמירת ההגדרות');
    } finally {
      setSaving(false);
    }
  };
  
  const handleReset = () => {
    setPrimaryTabs(['activity', 'reminders', 'documents']);
    setSecondaryTabs(['overview', 'whatsapp', 'calls', 'email', 'contracts', 'appointments', 'ai_notes', 'notes']);
  };
  
  const addToPrimary = (tabKey: string) => {
    if (primaryTabs.length < 5 && !primaryTabs.includes(tabKey)) {
      setPrimaryTabs([...primaryTabs, tabKey]);
      setSecondaryTabs(secondaryTabs.filter(k => k !== tabKey));
    }
  };
  
  const addToSecondary = (tabKey: string) => {
    if (secondaryTabs.length < 5 && !secondaryTabs.includes(tabKey)) {
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
  
  if (loading) {
    return (
      <Card className="p-6">
        <div className="text-center py-8">
          <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-blue-600 mx-auto"></div>
          <p className="mt-4 text-gray-500">טוען הגדרות...</p>
        </div>
      </Card>
    );
  }
  
  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-2xl font-bold text-gray-900 flex items-center gap-2">
            <Settings className="w-6 h-6" />
            הגדרות טאבים בדף ליד
          </h2>
          <p className="text-sm text-gray-500 mt-1">
            התאם אישית אילו טאבים יופיעו בדף פרטי הליד
          </p>
        </div>
        <Button
          variant="outline"
          size="sm"
          onClick={() => setShowPreview(!showPreview)}
        >
          {showPreview ? <EyeOff className="w-4 h-4 ml-2" /> : <Eye className="w-4 h-4 ml-2" />}
          {showPreview ? 'הסתר תצוגה מקדימה' : 'הצג תצוגה מקדימה'}
        </Button>
      </div>
      
      {/* Success/Error Messages */}
      {success && (
        <div className="bg-green-50 border border-green-200 text-green-700 px-4 py-3 rounded-lg">
          ✅ ההגדרות נשמרו בהצלחה!
        </div>
      )}
      
      {error && (
        <div className="bg-red-50 border border-red-200 text-red-700 px-4 py-3 rounded-lg">
          ❌ {error}
        </div>
      )}
      
      {/* Configuration */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Primary Tabs */}
        <Card className="p-6">
          <div className="mb-4">
            <h3 className="text-lg font-semibold text-gray-900 mb-1">
              טאבים ראשיים ({primaryTabs.length}/5)
            </h3>
            <p className="text-sm text-gray-500">
              מוצגים ישירות בדף הליד (עד 5)
            </p>
          </div>
          
          <div className="space-y-2 min-h-[200px]">
            {primaryTabs.map((tabKey) => {
              const tab = ALL_TABS.find(t => t.key === tabKey);
              if (!tab) return null;
              
              return (
                <div
                  key={tabKey}
                  className="flex items-center gap-3 p-3 bg-blue-50 border border-blue-200 rounded-lg"
                >
                  <GripVertical className="w-4 h-4 text-gray-400" />
                  <div className="flex-1">
                    <div className="font-medium text-gray-900">{tab.label}</div>
                    <div className="text-xs text-gray-500">{tab.description}</div>
                  </div>
                  <button
                    onClick={() => removeFromPrimary(tabKey)}
                    className="p-1 hover:bg-red-100 rounded transition-colors"
                    title="הסר"
                  >
                    <X className="w-4 h-4 text-red-600" />
                  </button>
                </div>
              );
            })}
            
            {primaryTabs.length === 0 && (
              <div className="text-center py-8 text-gray-400 border-2 border-dashed border-gray-200 rounded-lg">
                גרור טאבים לכאן או לחץ + בטאב זמין
              </div>
            )}
          </div>
        </Card>
        
        {/* Secondary Tabs */}
        <Card className="p-6">
          <div className="mb-4">
            <h3 className="text-lg font-semibold text-gray-900 mb-1">
              טאבים משניים ({secondaryTabs.length}/5)
            </h3>
            <p className="text-sm text-gray-500">
              מוצגים בתפריט "עוד" (עד 5)
            </p>
          </div>
          
          <div className="space-y-2 min-h-[200px]">
            {secondaryTabs.map((tabKey) => {
              const tab = ALL_TABS.find(t => t.key === tabKey);
              if (!tab) return null;
              
              return (
                <div
                  key={tabKey}
                  className="flex items-center gap-3 p-3 bg-gray-50 border border-gray-200 rounded-lg"
                >
                  <GripVertical className="w-4 h-4 text-gray-400" />
                  <div className="flex-1">
                    <div className="font-medium text-gray-900">{tab.label}</div>
                    <div className="text-xs text-gray-500">{tab.description}</div>
                  </div>
                  <button
                    onClick={() => removeFromSecondary(tabKey)}
                    className="p-1 hover:bg-red-100 rounded transition-colors"
                    title="הסר"
                  >
                    <X className="w-4 h-4 text-red-600" />
                  </button>
                </div>
              );
            })}
            
            {secondaryTabs.length === 0 && (
              <div className="text-center py-8 text-gray-400 border-2 border-dashed border-gray-200 rounded-lg">
                גרור טאבים לכאן או לחץ + בטאב זמין
              </div>
            )}
          </div>
        </Card>
      </div>
      
      {/* Available Tabs */}
      {getAvailableTabs().length > 0 && (
        <Card className="p-6">
          <h3 className="text-lg font-semibold text-gray-900 mb-4">
            טאבים זמינים
          </h3>
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-3">
            {getAvailableTabs().map((tab) => (
              <div
                key={tab.key}
                className="flex items-center gap-3 p-3 bg-white border border-gray-200 rounded-lg hover:border-blue-300 transition-colors"
              >
                <div className="flex-1">
                  <div className="font-medium text-gray-900">{tab.label}</div>
                  <div className="text-xs text-gray-500">{tab.description}</div>
                </div>
                <div className="flex gap-1">
                  {primaryTabs.length < 5 && (
                    <button
                      onClick={() => addToPrimary(tab.key)}
                      className="p-1 hover:bg-blue-100 rounded transition-colors"
                      title="הוסף לטאבים ראשיים"
                    >
                      <Plus className="w-4 h-4 text-blue-600" />
                    </button>
                  )}
                  {secondaryTabs.length < 5 && (
                    <button
                      onClick={() => addToSecondary(tab.key)}
                      className="p-1 hover:bg-gray-100 rounded transition-colors"
                      title="הוסף לטאבים משניים"
                    >
                      <Plus className="w-4 h-4 text-gray-600" />
                    </button>
                  )}
                </div>
              </div>
            ))}
          </div>
        </Card>
      )}
      
      {/* Preview */}
      {showPreview && (
        <Card className="p-6 bg-gray-50">
          <h3 className="text-lg font-semibold text-gray-900 mb-4">תצוגה מקדימה</h3>
          <div className="bg-white rounded-lg p-4 border border-gray-200">
            <div className="flex items-center gap-3">
              {/* Primary tabs preview */}
              <div className="flex items-center bg-gray-100 rounded-lg p-1 gap-1 flex-1">
                {primaryTabs.map((tabKey) => {
                  const tab = ALL_TABS.find(t => t.key === tabKey);
                  return tab ? (
                    <div key={tabKey} className="flex-1 text-center py-2 px-3 bg-white rounded text-sm font-medium text-blue-600 shadow-sm">
                      {tab.label}
                    </div>
                  ) : null;
                })}
              </div>
              
              {/* More button preview */}
              {secondaryTabs.length > 0 && (
                <div className="py-2 px-4 border border-gray-200 rounded-lg text-sm font-medium">
                  עוד ({secondaryTabs.length})
                </div>
              )}
            </div>
          </div>
        </Card>
      )}
      
      {/* Actions */}
      <div className="flex items-center justify-between gap-4">
        <Button
          variant="outline"
          onClick={handleReset}
        >
          <RotateCcw className="w-4 h-4 ml-2" />
          אפס לברירת מחדל
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
      
      {/* Help Text */}
      <div className="bg-blue-50 border border-blue-200 rounded-lg p-4">
        <h4 className="font-semibold text-blue-900 mb-2">💡 טיפים</h4>
        <ul className="text-sm text-blue-800 space-y-1">
          <li>• טאבים ראשיים מוצגים תמיד בדף הליד</li>
          <li>• טאבים משניים זמינים דרך כפתור "עוד"</li>
          <li>• מקסימום 5 טאבים ראשיים ו-5 משניים (10 סה"כ)</li>
          <li>• השינויים יופיעו מיד בכל דפי הליד</li>
        </ul>
      </div>
    </div>
  );
}
