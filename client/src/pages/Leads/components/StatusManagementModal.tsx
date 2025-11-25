import React, { useState, useEffect } from 'react';
import { Plus, Edit, Trash2, X } from 'lucide-react';
import { Button } from '../../../shared/components/ui/Button';
import { Input } from '../../../shared/components/ui/Input';
import { Card } from '../../../shared/components/ui/Card';
import { Badge } from '../../../shared/components/Badge';
import { useStatuses, LeadStatus } from '../../../features/statuses/hooks';

interface StatusManagementModalProps {
  isOpen: boolean;
  onClose: () => void;
  onStatusChange?: () => void;
}

interface StatusFormData {
  label: string;
  color: string;
  description: string;
  is_default: boolean;
}

const TEXTS = {
  title: 'ניהול סטטוסי לידים',
  existing: 'סטטוסים קיימים',
  newStatus: 'סטטוס חדש',
  loading: 'טוען סטטוסים...',
  edit: 'ערוך סטטוס',
  create: 'צור סטטוס חדש',
  displayLabel: 'שם הסטטוס',
  displayPlaceholder: 'לדוגמה: מחכה לתשובה, בטיפול...',
  colorLabel: 'צבע',
  descLabel: 'תיאור (אופציונלי)',
  descPlaceholder: 'תיאור נוסף על הסטטוס',
  defaultLabel: 'קבע כברירת מחדל ללידים חדשים',
  save: 'שמור',
  cancel: 'ביטול',
  update: 'עדכן',
  defaultBadge: 'ברירת מחדל',
  systemBadge: 'מערכת',
  cannotDeleteSystem: 'לא ניתן למחוק סטטוס מערכת',
  confirmDelete: 'האם אתה בטוח שברצונך למחוק את הסטטוס',
  deleteError: 'שגיאה במחיקת הסטטוס',
  saveError: 'שגיאה בשמירת הסטטוס',
  emptyLabel: 'נא להזין שם לסטטוס',
};

const COLOR_OPTIONS = [
  { value: 'bg-blue-100 text-blue-800', label: 'כחול' },
  { value: 'bg-yellow-100 text-yellow-800', label: 'צהוב' },
  { value: 'bg-purple-100 text-purple-800', label: 'סגול' },
  { value: 'bg-green-100 text-green-800', label: 'ירוק' },
  { value: 'bg-emerald-100 text-emerald-800', label: 'ירוק כהה' },
  { value: 'bg-red-100 text-red-800', label: 'אדום' },
  { value: 'bg-gray-100 text-gray-800', label: 'אפור' },
  { value: 'bg-orange-100 text-orange-800', label: 'כתום' },
  { value: 'bg-pink-100 text-pink-800', label: 'ורוד' },
];

function generateInternalName(label: string): string {
  const timestamp = Date.now().toString(36);
  const sanitized = label
    .toLowerCase()
    .replace(/[^\u0590-\u05FFa-z0-9\s]/g, '')
    .trim()
    .replace(/\s+/g, '_');
  
  if (!sanitized) {
    return `status_${timestamp}`;
  }
  
  return `custom_${timestamp}`;
}

export default function StatusManagementModal({ isOpen, onClose, onStatusChange }: StatusManagementModalProps) {
  const { statuses, loading, error, refreshStatuses, createStatus, updateStatus, deleteStatus } = useStatuses();

  const [editingStatus, setEditingStatus] = useState<LeadStatus | null>(null);
  const [isCreating, setIsCreating] = useState(false);
  const [saving, setSaving] = useState(false);
  const [formError, setFormError] = useState<string | null>(null);
  const [formData, setFormData] = useState<StatusFormData>({
    label: '',
    color: 'bg-blue-100 text-blue-800',
    description: '',
    is_default: false,
  });

  useEffect(() => {
    if (isOpen) {
      refreshStatuses();
    }
  }, [isOpen, refreshStatuses]);

  const resetForm = () => {
    setFormData({
      label: '',
      color: 'bg-blue-100 text-blue-800',
      description: '',
      is_default: false,
    });
    setEditingStatus(null);
    setIsCreating(false);
    setFormError(null);
  };

  const handleEdit = (status: LeadStatus) => {
    setFormData({
      label: status.label,
      color: status.color,
      description: status.description || '',
      is_default: status.is_default,
    });
    setEditingStatus(status);
    setIsCreating(false);
    setFormError(null);
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setFormError(null);
    
    if (!formData.label.trim()) {
      setFormError(TEXTS.emptyLabel);
      return;
    }
    
    setSaving(true);
    try {
      if (editingStatus) {
        await updateStatus(editingStatus.id, {
          label: formData.label.trim(),
          color: formData.color,
          description: formData.description.trim(),
          is_default: formData.is_default,
        });
      } else {
        const internalName = generateInternalName(formData.label);
        await createStatus({
          name: internalName,
          label: formData.label.trim(),
          color: formData.color,
          description: formData.description.trim(),
          is_default: formData.is_default,
        });
      }
      
      resetForm();
      await refreshStatuses();
      if (onStatusChange) {
        onStatusChange();
      }
    } catch (error: any) {
      console.error('Failed to save status:', error);
      const errorMsg = error?.message || error?.error || TEXTS.saveError;
      setFormError(typeof errorMsg === 'string' ? errorMsg : TEXTS.saveError);
    } finally {
      setSaving(false);
    }
  };

  const handleDelete = async (status: LeadStatus) => {
    if (status.is_system) {
      alert(TEXTS.cannotDeleteSystem);
      return;
    }

    const confirmed = window.confirm(`${TEXTS.confirmDelete} "${status.label}"?`);
    if (!confirmed) return;

    try {
      await deleteStatus(status.id);
      await refreshStatuses();
      if (onStatusChange) {
        onStatusChange();
      }
    } catch (error) {
      console.error('Failed to delete status:', error);
      alert(TEXTS.deleteError);
    }
  };

  if (!isOpen) return null;

  return (
    <div 
      className="fixed inset-0 bg-black/50 z-50 overflow-y-auto overscroll-contain" 
      dir="rtl"
      onClick={(e) => e.target === e.currentTarget && onClose()}
    >
      <div className="min-h-full flex items-start sm:items-center justify-center p-0 sm:p-4">
        <div className="bg-white dark:bg-gray-800 sm:rounded-lg rounded-none w-full sm:max-w-4xl sm:my-8 shadow-xl flex flex-col max-h-screen sm:max-h-[90vh]">
          {/* Header - Fixed */}
          <div className="flex-shrink-0 flex items-center justify-between p-4 sm:p-6 border-b border-gray-200 dark:border-gray-700 bg-gradient-to-r from-blue-50 to-indigo-50 dark:from-blue-900/20 dark:to-indigo-900/20">
            <div>
              <h2 className="text-xl font-semibold text-gray-900 dark:text-white">
                {TEXTS.title}
              </h2>
              <p className="text-sm text-gray-600 dark:text-gray-400 mt-1">
                צור, ערוך ונהל את סטטוסי הלידים של העסק
              </p>
            </div>
            <div className="flex items-center gap-2">
              <Button
                variant="secondary"
                size="sm"
                onClick={onClose}
                className="border-gray-300 hover:bg-gray-50"
                data-testid="button-close-status-modal"
              >
                <X className="w-4 h-4 ml-2" />
                סגור
              </Button>
            </div>
          </div>

          {/* Content - Scrollable */}
          <div className="flex-1 overflow-y-auto p-4 sm:p-6 overscroll-contain">
          {error && (
            <div className="bg-red-50 border border-red-200 rounded-lg p-4 mb-6">
              <p className="text-red-600 text-sm">{error}</p>
            </div>
          )}

          <div className="grid grid-cols-1 lg:grid-cols-2 gap-4 lg:gap-6">
            {/* Status List */}
            <div>
              <div className="flex items-center justify-between mb-4">
                <h3 className="text-lg font-medium text-gray-900 dark:text-white">
                  {TEXTS.existing}
                </h3>
                <Button
                  onClick={() => {
                    resetForm();
                    setIsCreating(true);
                  }}
                  className="bg-blue-600 hover:bg-blue-700 text-white"
                  size="sm"
                  data-testid="button-create-status"
                >
                  <Plus className="w-4 h-4 ml-2" />
                  {TEXTS.newStatus}
                </Button>
              </div>

              {loading ? (
                <div className="text-center py-8">
                  <div className="inline-block animate-spin rounded-full h-6 w-6 border-b-2 border-blue-600"></div>
                  <p className="text-gray-600 dark:text-gray-400 mt-2">{TEXTS.loading}</p>
                </div>
              ) : statuses.length === 0 ? (
                <div className="text-center py-8 bg-gray-50 rounded-lg">
                  <p className="text-gray-500 mb-4">אין סטטוסים עדיין</p>
                  <Button
                    onClick={() => {
                      resetForm();
                      setIsCreating(true);
                    }}
                    className="bg-blue-600 hover:bg-blue-700 text-white"
                    size="sm"
                  >
                    <Plus className="w-4 h-4 ml-2" />
                    צור סטטוס ראשון
                  </Button>
                </div>
              ) : (
                <div className="space-y-3">
                  {statuses.map((status) => (
                    <Card
                      key={status.id}
                      className={`p-4 ${editingStatus?.id === status.id ? 'ring-2 ring-blue-500' : ''}`}
                    >
                      <div className="flex items-center justify-between">
                        <div className="flex items-center gap-3">
                          <div>
                            <div className="flex items-center gap-2 flex-wrap">
                              <Badge className={status.color}>
                                {status.label}
                              </Badge>
                              {status.is_default && (
                                <Badge className="bg-blue-50 text-blue-700 text-xs">
                                  {TEXTS.defaultBadge}
                                </Badge>
                              )}
                              {status.is_system && (
                                <Badge className="bg-gray-50 text-gray-700 text-xs">
                                  {TEXTS.systemBadge}
                                </Badge>
                              )}
                            </div>
                            {status.description && (
                              <p className="text-sm text-gray-500 mt-1">
                                {status.description}
                              </p>
                            )}
                          </div>
                        </div>
                        
                        <div className="flex items-center gap-1">
                          <Button
                            size="sm"
                            variant="ghost"
                            onClick={() => handleEdit(status)}
                            className="h-8 w-8 p-0 touch-target-44 hover:bg-gray-100"
                            data-testid={`button-edit-status-${status.id}`}
                            title="ערוך סטטוס"
                          >
                            <Edit className="w-4 h-4" />
                          </Button>
                          {!status.is_system && (
                            <Button
                              size="sm"
                              variant="ghost"
                              onClick={() => handleDelete(status)}
                              className="h-8 w-8 p-0 text-red-600 hover:text-red-700 hover:bg-red-50 touch-target-44"
                              data-testid={`button-delete-status-${status.id}`}
                              title="מחק סטטוס"
                            >
                              <Trash2 className="w-4 h-4" />
                            </Button>
                          )}
                        </div>
                      </div>
                    </Card>
                  ))}
                </div>
              )}
            </div>

            {/* Form */}
            {(isCreating || editingStatus) && (
              <div>
                <h3 className="text-lg font-medium text-gray-900 dark:text-white mb-4">
                  {editingStatus ? TEXTS.edit : TEXTS.create}
                </h3>

                {formError && (
                  <div className="bg-red-50 border border-red-200 rounded-lg p-3 mb-4">
                    <p className="text-red-600 text-sm">{formError}</p>
                  </div>
                )}

                <form onSubmit={handleSubmit} className="space-y-4">
                  <div>
                    <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">
                      {TEXTS.displayLabel} *
                    </label>
                    <Input
                      value={formData.label}
                      onChange={(e) => setFormData(prev => ({ ...prev, label: e.target.value }))}
                      placeholder={TEXTS.displayPlaceholder}
                      required
                      className="text-right"
                      data-testid="input-status-label"
                    />
                  </div>

                  <div>
                    <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">
                      {TEXTS.colorLabel}
                    </label>
                    <div className="grid grid-cols-3 gap-2">
                      {COLOR_OPTIONS.map((option) => (
                        <button
                          key={option.value}
                          type="button"
                          onClick={() => setFormData(prev => ({ ...prev, color: option.value }))}
                          className={`p-3 rounded-lg border-2 text-sm touch-target-44 transition-colors ${
                            formData.color === option.value
                              ? 'border-blue-500 bg-blue-50'
                              : 'border-gray-200 hover:border-gray-300 hover:bg-gray-50'
                          }`}
                          data-testid={`button-color-${option.value}`}
                        >
                          <Badge className={option.value}>
                            {option.label}
                          </Badge>
                        </button>
                      ))}
                    </div>
                  </div>

                  <div>
                    <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">
                      {TEXTS.descLabel}
                    </label>
                    <textarea
                      value={formData.description}
                      onChange={(e) => setFormData(prev => ({ ...prev, description: e.target.value }))}
                      placeholder={TEXTS.descPlaceholder}
                      rows={2}
                      className="w-full px-3 py-2 border border-gray-200 rounded-lg text-sm text-right"
                      data-testid="textarea-status-description"
                    />
                  </div>

                  {!editingStatus?.is_system && (
                    <div className="flex items-center gap-2">
                      <input
                        type="checkbox"
                        id="is_default"
                        checked={formData.is_default}
                        onChange={(e) => setFormData(prev => ({ ...prev, is_default: e.target.checked }))}
                        className="rounded"
                        data-testid="checkbox-is-default"
                      />
                      <label htmlFor="is_default" className="text-sm text-gray-700 dark:text-gray-300">
                        {TEXTS.defaultLabel}
                      </label>
                    </div>
                  )}

                  <div className="flex items-center gap-3 pt-4">
                    <Button
                      type="submit"
                      className="bg-blue-600 hover:bg-blue-700 text-white"
                      disabled={saving}
                      data-testid="button-save-status"
                    >
                      {saving ? 'שומר...' : (editingStatus ? TEXTS.update : TEXTS.save)}
                    </Button>
                    <Button
                      type="button"
                      variant="secondary"
                      onClick={resetForm}
                      disabled={saving}
                      data-testid="button-cancel-status"
                    >
                      {TEXTS.cancel}
                    </Button>
                  </div>
                </form>
              </div>
            )}
          </div>
        </div>
        
          {/* Footer */}
          <div className="flex-shrink-0 px-4 sm:px-6 py-4 border-t border-gray-200 dark:border-gray-700 bg-gray-50 dark:bg-gray-900/50 flex flex-col sm:flex-row items-center justify-between gap-3 sm:gap-0">
            <div className="text-sm text-gray-600 dark:text-gray-400">
              💡 טיפ: לחץ על סטטוס ללידים בטבלה כדי לשנות אותו
            </div>
            <Button
              variant="secondary"
              onClick={onClose}
              data-testid="button-close-status-modal-footer"
              className="bg-white border border-gray-300 hover:bg-gray-50"
            >
              סגור וחזור ללידים
            </Button>
          </div>
        </div>
      </div>
    </div>
  );
}
