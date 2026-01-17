/**
 * Business Page Permissions Manager
 * הנחיית-על: ניהול הרשאות דפים לעסקים
 * 
 * Allows system_admin to manage which pages/modules are enabled for each business
 */
import React, { useState, useEffect } from 'react';
import { Check, X, Search, CheckSquare, Square } from 'lucide-react';

interface PageInfo {
  key: string;
  title: string;
  enabled: boolean;
  min_role: string;
  icon?: string;
  description?: string;
}

interface PagesByCategory {
  [category: string]: PageInfo[];
}

interface BusinessPagesManagerProps {
  businessId: number;
  businessName: string;
  onClose?: () => void;
  onSave?: () => void;
}

const CATEGORY_NAMES: Record<string, string> = {
  dashboard: 'סקירה כללית',
  crm: 'CRM - לידים ולקוחות',
  calls: 'שיחות',
  whatsapp: 'WhatsApp',
  communications: 'תקשורת',
  calendar: 'לוח שנה',
  reports: 'דוחות וסטטיסטיקות',
  finance: 'כספים',
  settings: 'הגדרות וניהול',
};

export function BusinessPagesManager({ 
  businessId, 
  businessName,
  onClose,
  onSave 
}: BusinessPagesManagerProps) {
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [pagesByCategory, setPagesByCategory] = useState<PagesByCategory>({});
  const [searchQuery, setSearchQuery] = useState('');
  const [enabledPages, setEnabledPages] = useState<string[]>([]);

  useEffect(() => {
    fetchBusinessPages();
  }, [businessId]);

  const fetchBusinessPages = async () => {
    try {
      setLoading(true);
      setError(null);

      const response = await fetch(`/api/admin/businesses/${businessId}/pages`, {
        credentials: 'include',
      });

      if (!response.ok) {
        throw new Error('Failed to fetch business pages');
      }

      const data = await response.json();
      setPagesByCategory(data.pages_by_category || {});
      setEnabledPages(data.enabled_pages || []);
    } catch (err) {
      console.error('Error fetching business pages:', err);
      setError(err instanceof Error ? err.message : 'Unknown error');
    } finally {
      setLoading(false);
    }
  };

  const handleTogglePage = (pageKey: string) => {
    setEnabledPages(prev => {
      if (prev.includes(pageKey)) {
        return prev.filter(k => k !== pageKey);
      } else {
        return [...prev, pageKey];
      }
    });
  };

  const handleSelectAll = () => {
    const allPageKeys = Object.values(pagesByCategory)
      .flat()
      .map(page => page.key);
    setEnabledPages(allPageKeys);
  };

  const handleDeselectAll = () => {
    setEnabledPages([]);
  };

  const handleSave = async () => {
    try {
      setSaving(true);
      setError(null);

      const response = await fetch(`/api/admin/businesses/${businessId}/pages`, {
        method: 'PATCH',
        headers: {
          'Content-Type': 'application/json',
        },
        credentials: 'include',
        body: JSON.stringify({
          enabled_pages: enabledPages,
        }),
      });

      if (!response.ok) {
        const errorData = await response.json();
        throw new Error(errorData.error || 'Failed to update pages');
      }

      if (onSave) {
        onSave();
      }
    } catch (err) {
      console.error('Error saving business pages:', err);
      setError(err instanceof Error ? err.message : 'Unknown error');
    } finally {
      setSaving(false);
    }
  };

  const filterPages = (pages: PageInfo[]) => {
    if (!searchQuery.trim()) return pages;
    
    const query = searchQuery.toLowerCase();
    return pages.filter(page => 
      page.title.includes(query) ||
      (page.description && page.description.includes(query))
    );
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center p-8">
        <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-blue-600"></div>
      </div>
    );
  }

  return (
    <div className="bg-white rounded-xl border border-slate-200 overflow-hidden">
      {/* Header */}
      <div className="px-6 py-4 bg-slate-50 border-b border-slate-200">
        <div className="flex items-center justify-between mb-4">
          <div>
            <h2 className="text-xl font-bold text-slate-900">
              ניהול הרשאות דפים
            </h2>
            <p className="text-sm text-slate-600 mt-1">
              {businessName}
            </p>
          </div>
          {onClose && (
            <button
              onClick={onClose}
              className="p-2 hover:bg-slate-200 rounded-lg transition-colors"
            >
              <X className="w-5 h-5" />
            </button>
          )}
        </div>

        {/* Search and Bulk Actions */}
        <div className="flex flex-col sm:flex-row gap-3">
          <div className="flex-1 relative">
            <Search className="absolute right-3 top-1/2 transform -translate-y-1/2 w-4 h-4 text-slate-400" />
            <input
              type="text"
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              placeholder="חיפוש דפים..."
              className="w-full pr-10 pl-4 py-2 border border-slate-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
            />
          </div>
          <div className="flex gap-2">
            <button
              onClick={handleSelectAll}
              className="px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 transition-colors font-medium whitespace-nowrap"
            >
              <CheckSquare className="w-4 h-4 inline ml-2" />
              בחר הכל
            </button>
            <button
              onClick={handleDeselectAll}
              className="px-4 py-2 bg-slate-200 text-slate-700 rounded-lg hover:bg-slate-300 transition-colors font-medium whitespace-nowrap"
            >
              <Square className="w-4 h-4 inline ml-2" />
              נקה הכל
            </button>
          </div>
        </div>
      </div>

      {/* Error Message */}
      {error && (
        <div className="mx-6 mt-4 p-4 bg-red-50 border border-red-200 rounded-lg">
          <p className="text-red-700">{error}</p>
        </div>
      )}

      {/* Pages by Category */}
      <div className="p-6 max-h-[600px] overflow-y-auto">
        <div className="space-y-6">
          {Object.entries(pagesByCategory).map(([category, pages]) => {
            const filteredPages = filterPages(pages);
            if (filteredPages.length === 0) return null;

            return (
              <div key={category} className="border border-slate-200 rounded-lg overflow-hidden">
                <div className="bg-slate-100 px-4 py-2 border-b border-slate-200">
                  <h3 className="font-semibold text-slate-900">
                    {CATEGORY_NAMES[category] || category}
                  </h3>
                </div>
                <div className="divide-y divide-slate-100">
                  {filteredPages.map(page => (
                    <label
                      key={page.key}
                      className="flex items-start p-4 hover:bg-slate-50 cursor-pointer transition-colors"
                    >
                      <input
                        type="checkbox"
                        checked={enabledPages.includes(page.key)}
                        onChange={() => handleTogglePage(page.key)}
                        className="mt-1 h-5 w-5 text-blue-600 rounded border-slate-300 focus:ring-blue-500"
                      />
                      <div className="mr-3 flex-1">
                        <div className="flex items-center gap-2">
                          <span className="font-medium text-slate-900">
                            {page.title}
                          </span>
                          <span className="text-xs px-2 py-1 bg-slate-200 text-slate-700 rounded">
                            {page.min_role}
                          </span>
                        </div>
                        {page.description && (
                          <p className="text-sm text-slate-600 mt-1">
                            {page.description}
                          </p>
                        )}
                      </div>
                    </label>
                  ))}
                </div>
              </div>
            );
          })}
        </div>
      </div>

      {/* Footer with Save Button */}
      <div className="px-6 py-4 bg-slate-50 border-t border-slate-200 flex justify-between items-center">
        <div className="text-sm text-slate-600">
          {enabledPages.length} מתוך{' '}
          {Object.values(pagesByCategory).flat().length} דפים נבחרו
        </div>
        <div className="flex gap-3">
          {onClose && (
            <button
              onClick={onClose}
              disabled={saving}
              className="px-6 py-2 bg-white border border-slate-300 text-slate-700 rounded-lg hover:bg-slate-50 transition-colors font-medium"
            >
              ביטול
            </button>
          )}
          <button
            onClick={handleSave}
            disabled={saving}
            className="px-6 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 transition-colors font-medium flex items-center gap-2 disabled:opacity-50 disabled:cursor-not-allowed"
          >
            {saving ? (
              <>
                <div className="animate-spin rounded-full h-4 w-4 border-2 border-white border-t-transparent" />
                שומר...
              </>
            ) : (
              <>
                <Check className="w-4 h-4" />
                שמור שינויים
              </>
            )}
          </button>
        </div>
      </div>
    </div>
  );
}
