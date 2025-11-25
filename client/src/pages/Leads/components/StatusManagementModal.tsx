import React, { useState, useEffect } from 'react';
import { Plus, Edit2, Trash2, X, Check, AlertTriangle, GripVertical } from 'lucide-react';
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
  edit: 'עריכת סטטוס',
  create: 'יצירת סטטוס חדש',
  displayLabel: 'שם הסטטוס',
  displayPlaceholder: 'לדוגמה: מחכה לתשובה, בטיפול...',
  colorLabel: 'צבע',
  descLabel: 'תיאור (אופציונלי)',
  descPlaceholder: 'תיאור נוסף על הסטטוס',
  defaultLabel: 'קבע כברירת מחדל ללידים חדשים',
  save: 'שמור סטטוס',
  cancel: 'ביטול',
  update: 'עדכן סטטוס',
  defaultBadge: 'ברירת מחדל',
  systemBadge: 'מערכת',
  cannotDeleteSystem: 'לא ניתן למחוק סטטוס מערכת',
  confirmDelete: 'מחיקת סטטוס',
  deleteConfirmText: 'האם אתה בטוח שברצונך למחוק את הסטטוס',
  deleteWarning: 'פעולה זו לא ניתנת לביטול',
  deleteError: 'שגיאה במחיקת הסטטוס',
  saveError: 'שגיאה בשמירת הסטטוס',
  emptyLabel: 'נא להזין שם לסטטוס',
  clickToEdit: 'לחץ לעריכה',
  deleteBtn: 'מחק',
  editBtn: 'ערוך',
};

const COLOR_OPTIONS = [
  { value: 'bg-blue-100 text-blue-800', label: 'כחול', preview: 'bg-blue-500' },
  { value: 'bg-yellow-100 text-yellow-800', label: 'צהוב', preview: 'bg-yellow-500' },
  { value: 'bg-purple-100 text-purple-800', label: 'סגול', preview: 'bg-purple-500' },
  { value: 'bg-green-100 text-green-800', label: 'ירוק', preview: 'bg-green-500' },
  { value: 'bg-emerald-100 text-emerald-800', label: 'ירוק כהה', preview: 'bg-emerald-500' },
  { value: 'bg-red-100 text-red-800', label: 'אדום', preview: 'bg-red-500' },
  { value: 'bg-gray-100 text-gray-800', label: 'אפור', preview: 'bg-gray-500' },
  { value: 'bg-orange-100 text-orange-800', label: 'כתום', preview: 'bg-orange-500' },
  { value: 'bg-pink-100 text-pink-800', label: 'ורוד', preview: 'bg-pink-500' },
  { value: 'bg-indigo-100 text-indigo-800', label: 'אינדיגו', preview: 'bg-indigo-500' },
  { value: 'bg-teal-100 text-teal-800', label: 'טורקיז', preview: 'bg-teal-500' },
  { value: 'bg-cyan-100 text-cyan-800', label: 'תכלת', preview: 'bg-cyan-500' },
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
  const [deleteConfirmId, setDeleteConfirmId] = useState<number | null>(null);
  const [deleting, setDeleting] = useState(false);
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
    setDeleteConfirmId(null);
  };

  const handleStartCreate = () => {
    resetForm();
    setIsCreating(true);
    setDeleteConfirmId(null);
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

  const handleDeleteClick = (status: LeadStatus, e: React.MouseEvent) => {
    e.stopPropagation();
    // BUILD 147: Removed is_system restriction - users can delete any status
    setDeleteConfirmId(status.id);
    setEditingStatus(null);
    setIsCreating(false);
  };

  const handleDeleteConfirm = async (status: LeadStatus) => {
    setDeleting(true);
    try {
      await deleteStatus(status.id);
      setDeleteConfirmId(null);
      await refreshStatuses();
      if (onStatusChange) {
        onStatusChange();
      }
    } catch (error) {
      console.error('Failed to delete status:', error);
      alert(TEXTS.deleteError);
    } finally {
      setDeleting(false);
    }
  };

  const handleDeleteCancel = () => {
    setDeleteConfirmId(null);
  };

  if (!isOpen) return null;

  const statusToDelete = statuses.find(s => s.id === deleteConfirmId);

  return (
    <div 
      className="fixed inset-0 z-50 flex items-start justify-center bg-black/50 backdrop-blur-sm" 
      dir="rtl"
      onClick={(e) => e.target === e.currentTarget && onClose()}
    >
      <div 
        className="w-full sm:max-w-5xl bg-white dark:bg-gray-800 sm:rounded-xl sm:my-4 shadow-2xl flex flex-col"
        style={{ 
          maxHeight: '100dvh',
          height: '100dvh',
          touchAction: 'pan-y'
        }}
        onClick={(e) => e.stopPropagation()}
      >
        {/* Header */}
        <div className="flex-shrink-0 flex items-center justify-between p-4 sm:p-5 border-b border-gray-200 dark:border-gray-700 bg-gradient-to-r from-blue-50 to-indigo-50 dark:from-blue-900/20 dark:to-indigo-900/20">
          <div>
            <h2 className="text-lg sm:text-xl font-bold text-gray-900 dark:text-white">
              {TEXTS.title}
            </h2>
            <p className="text-sm text-gray-600 dark:text-gray-400 mt-0.5">
              צור, ערוך ומחק את סטטוסי הלידים של העסק
            </p>
          </div>
          <Button
            variant="ghost"
            size="sm"
            onClick={onClose}
            className="h-10 w-10 p-0 rounded-full hover:bg-gray-200 dark:hover:bg-gray-700"
            data-testid="button-close-status-modal"
          >
            <X className="w-5 h-5" />
          </Button>
        </div>

        {/* Content */}
        <div className="flex-1 overflow-y-auto p-4 sm:p-5 overscroll-contain">
          {error && (
            <div className="bg-red-50 border border-red-200 rounded-lg p-4 mb-4 flex items-center gap-3">
              <AlertTriangle className="w-5 h-5 text-red-500 flex-shrink-0" />
              <p className="text-red-600 text-sm">{error}</p>
            </div>
          )}

          <div className="grid grid-cols-1 lg:grid-cols-5 gap-4 lg:gap-6">
            {/* Status List - 3 columns on desktop */}
            <div className="lg:col-span-3">
              <div className="flex items-center justify-between mb-4">
                <h3 className="text-base sm:text-lg font-semibold text-gray-900 dark:text-white flex items-center gap-2">
                  <GripVertical className="w-5 h-5 text-gray-400" />
                  {TEXTS.existing}
                  <span className="text-sm font-normal text-gray-500">({statuses.length})</span>
                </h3>
                <Button
                  onClick={handleStartCreate}
                  className="bg-blue-600 hover:bg-blue-700 text-white shadow-md hover:shadow-lg transition-all"
                  size="sm"
                  data-testid="button-create-status"
                >
                  <Plus className="w-4 h-4 ml-1.5" />
                  {TEXTS.newStatus}
                </Button>
              </div>

              {loading ? (
                <div className="text-center py-12">
                  <div className="inline-block animate-spin rounded-full h-8 w-8 border-b-2 border-blue-600"></div>
                  <p className="text-gray-600 dark:text-gray-400 mt-3">{TEXTS.loading}</p>
                </div>
              ) : statuses.length === 0 ? (
                <div className="text-center py-12 bg-gray-50 dark:bg-gray-900/50 rounded-xl border-2 border-dashed border-gray-200 dark:border-gray-700">
                  <div className="w-16 h-16 mx-auto mb-4 bg-blue-100 dark:bg-blue-900/30 rounded-full flex items-center justify-center">
                    <Plus className="w-8 h-8 text-blue-600" />
                  </div>
                  <p className="text-gray-500 mb-4 text-lg">אין סטטוסים עדיין</p>
                  <Button
                    onClick={handleStartCreate}
                    className="bg-blue-600 hover:bg-blue-700 text-white"
                  >
                    <Plus className="w-4 h-4 ml-2" />
                    צור סטטוס ראשון
                  </Button>
                </div>
              ) : (
                <div className="space-y-2">
                  {statuses.map((status) => {
                    const isEditing = editingStatus?.id === status.id;
                    const isDeleting = deleteConfirmId === status.id;
                    
                    return (
                      <div key={status.id}>
                        {/* Delete Confirmation */}
                        {isDeleting && statusToDelete && (
                          <Card className="p-4 bg-red-50 dark:bg-red-900/20 border-red-200 dark:border-red-800 animate-in slide-in-from-top-2 duration-200">
                            <div className="flex flex-col sm:flex-row sm:items-center gap-3">
                              <div className="flex items-center gap-3 flex-1">
                                <div className="w-10 h-10 bg-red-100 dark:bg-red-900/50 rounded-full flex items-center justify-center flex-shrink-0">
                                  <AlertTriangle className="w-5 h-5 text-red-600" />
                                </div>
                                <div>
                                  <p className="font-medium text-gray-900 dark:text-white">
                                    {TEXTS.confirmDelete}
                                  </p>
                                  <p className="text-sm text-gray-600 dark:text-gray-400">
                                    {TEXTS.deleteConfirmText} "<strong>{statusToDelete.label}</strong>"?
                                  </p>
                                  <p className="text-xs text-red-600 mt-1">
                                    {TEXTS.deleteWarning}
                                  </p>
                                </div>
                              </div>
                              <div className="flex gap-2 sm:flex-shrink-0">
                                <Button
                                  onClick={() => handleDeleteConfirm(statusToDelete)}
                                  disabled={deleting}
                                  className="bg-red-600 hover:bg-red-700 text-white flex-1 sm:flex-none min-h-[44px]"
                                  data-testid="button-confirm-delete"
                                >
                                  {deleting ? (
                                    <div className="animate-spin rounded-full h-4 w-4 border-b-2 border-white" />
                                  ) : (
                                    <>
                                      <Trash2 className="w-4 h-4 ml-1.5" />
                                      מחק
                                    </>
                                  )}
                                </Button>
                                <Button
                                  onClick={handleDeleteCancel}
                                  variant="secondary"
                                  disabled={deleting}
                                  className="flex-1 sm:flex-none min-h-[44px]"
                                  data-testid="button-cancel-delete"
                                >
                                  ביטול
                                </Button>
                              </div>
                            </div>
                          </Card>
                        )}
                        
                        {/* Status Card */}
                        {!isDeleting && (
                          <Card
                            className={`group transition-all duration-200 cursor-pointer hover:shadow-md ${
                              isEditing 
                                ? 'ring-2 ring-blue-500 bg-blue-50 dark:bg-blue-900/20' 
                                : 'hover:bg-gray-50 dark:hover:bg-gray-700/50'
                            }`}
                            onClick={() => handleEdit(status)}
                            data-testid={`status-card-${status.id}`}
                          >
                            <div className="p-3 sm:p-4">
                              <div className="flex items-center justify-between gap-3">
                                {/* Status Info */}
                                <div className="flex items-center gap-3 flex-1 min-w-0">
                                  <div className="flex flex-col gap-1.5">
                                    <div className="flex items-center gap-2 flex-wrap">
                                      <Badge className={`${status.color} text-sm px-3 py-1`}>
                                        {status.label}
                                      </Badge>
                                      {status.is_default && (
                                        <Badge className="bg-blue-100 text-blue-700 text-xs px-2 py-0.5">
                                          {TEXTS.defaultBadge}
                                        </Badge>
                                      )}
                                      {status.is_system && (
                                        <Badge className="bg-gray-100 text-gray-600 text-xs px-2 py-0.5">
                                          {TEXTS.systemBadge}
                                        </Badge>
                                      )}
                                    </div>
                                    {status.description && (
                                      <p className="text-sm text-gray-500 dark:text-gray-400 truncate max-w-xs">
                                        {status.description}
                                      </p>
                                    )}
                                  </div>
                                </div>
                                
                                {/* Action Buttons */}
                                <div className="flex items-center gap-1 sm:gap-2 flex-shrink-0">
                                  <Button
                                    size="sm"
                                    variant="ghost"
                                    onClick={(e) => {
                                      e.stopPropagation();
                                      handleEdit(status);
                                    }}
                                    className={`min-h-[40px] min-w-[40px] sm:min-w-[auto] sm:px-3 rounded-lg transition-all ${
                                      isEditing 
                                        ? 'bg-blue-100 text-blue-700' 
                                        : 'hover:bg-blue-50 text-gray-600 hover:text-blue-600'
                                    }`}
                                    data-testid={`button-edit-status-${status.id}`}
                                  >
                                    <Edit2 className="w-4 h-4" />
                                    <span className="hidden sm:inline mr-1.5">{TEXTS.editBtn}</span>
                                  </Button>
                                  {/* BUILD 147: Show delete button for all statuses (removed is_system restriction) */}
                                  <Button
                                    size="sm"
                                    variant="ghost"
                                    onClick={(e) => handleDeleteClick(status, e)}
                                    className="min-h-[40px] min-w-[40px] sm:min-w-[auto] sm:px-3 rounded-lg text-gray-500 hover:text-red-600 hover:bg-red-50 transition-all"
                                    data-testid={`button-delete-status-${status.id}`}
                                  >
                                    <Trash2 className="w-4 h-4" />
                                    <span className="hidden sm:inline mr-1.5">{TEXTS.deleteBtn}</span>
                                  </Button>
                                </div>
                              </div>
                            </div>
                          </Card>
                        )}
                      </div>
                    );
                  })}
                </div>
              )}
            </div>

            {/* Form - 2 columns on desktop */}
            <div className="lg:col-span-2">
              {(isCreating || editingStatus) ? (
                <div className="sticky top-0">
                  <Card className="p-4 sm:p-5 bg-white dark:bg-gray-800 shadow-lg border-2 border-blue-100 dark:border-blue-900/50">
                    <h3 className="text-base sm:text-lg font-semibold text-gray-900 dark:text-white mb-4 flex items-center gap-2">
                      {editingStatus ? (
                        <>
                          <Edit2 className="w-5 h-5 text-blue-600" />
                          {TEXTS.edit}
                        </>
                      ) : (
                        <>
                          <Plus className="w-5 h-5 text-blue-600" />
                          {TEXTS.create}
                        </>
                      )}
                    </h3>

                    {formError && (
                      <div className="bg-red-50 border border-red-200 rounded-lg p-3 mb-4 flex items-center gap-2">
                        <AlertTriangle className="w-4 h-4 text-red-500 flex-shrink-0" />
                        <p className="text-red-600 text-sm">{formError}</p>
                      </div>
                    )}

                    <form onSubmit={handleSubmit} className="space-y-4">
                      {/* Label */}
                      <div>
                        <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">
                          {TEXTS.displayLabel} <span className="text-red-500">*</span>
                        </label>
                        <Input
                          value={formData.label}
                          onChange={(e) => setFormData(prev => ({ ...prev, label: e.target.value }))}
                          placeholder={TEXTS.displayPlaceholder}
                          required
                          className="text-right text-base min-h-[44px]"
                          data-testid="input-status-label"
                          autoFocus
                        />
                      </div>

                      {/* Color Picker */}
                      <div>
                        <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">
                          {TEXTS.colorLabel}
                        </label>
                        <div className="grid grid-cols-4 sm:grid-cols-6 gap-2">
                          {COLOR_OPTIONS.map((option) => (
                            <button
                              key={option.value}
                              type="button"
                              onClick={() => setFormData(prev => ({ ...prev, color: option.value }))}
                              className={`aspect-square rounded-lg border-2 transition-all flex items-center justify-center ${
                                formData.color === option.value
                                  ? 'border-blue-500 ring-2 ring-blue-200 scale-105'
                                  : 'border-gray-200 hover:border-gray-300 hover:scale-102'
                              }`}
                              data-testid={`button-color-${option.label}`}
                              title={option.label}
                            >
                              <div className={`w-6 h-6 rounded-full ${option.preview}`} />
                              {formData.color === option.value && (
                                <Check className="w-3 h-3 text-white absolute" />
                              )}
                            </button>
                          ))}
                        </div>
                        {/* Preview */}
                        <div className="mt-3 p-3 bg-gray-50 dark:bg-gray-900/50 rounded-lg">
                          <p className="text-xs text-gray-500 mb-2">תצוגה מקדימה:</p>
                          <Badge className={`${formData.color} text-sm px-3 py-1`}>
                            {formData.label || 'שם הסטטוס'}
                          </Badge>
                        </div>
                      </div>

                      {/* Description */}
                      <div>
                        <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">
                          {TEXTS.descLabel}
                        </label>
                        <textarea
                          value={formData.description}
                          onChange={(e) => setFormData(prev => ({ ...prev, description: e.target.value }))}
                          placeholder={TEXTS.descPlaceholder}
                          rows={2}
                          className="w-full px-3 py-2.5 border border-gray-200 dark:border-gray-600 rounded-lg text-sm text-right bg-white dark:bg-gray-700 min-h-[60px] resize-none"
                          data-testid="textarea-status-description"
                        />
                      </div>

                      {/* Default Checkbox */}
                      {!editingStatus?.is_system && (
                        <label className="flex items-center gap-3 p-3 bg-gray-50 dark:bg-gray-900/50 rounded-lg cursor-pointer hover:bg-gray-100 dark:hover:bg-gray-900 transition-colors">
                          <input
                            type="checkbox"
                            checked={formData.is_default}
                            onChange={(e) => setFormData(prev => ({ ...prev, is_default: e.target.checked }))}
                            className="w-5 h-5 rounded border-gray-300 text-blue-600 focus:ring-blue-500"
                            data-testid="checkbox-is-default"
                          />
                          <span className="text-sm text-gray-700 dark:text-gray-300">
                            {TEXTS.defaultLabel}
                          </span>
                        </label>
                      )}

                      {/* Form Actions */}
                      <div className="flex items-center gap-3 pt-2">
                        <Button
                          type="submit"
                          className="flex-1 bg-blue-600 hover:bg-blue-700 text-white min-h-[48px] text-base font-medium shadow-md hover:shadow-lg transition-all"
                          disabled={saving}
                          data-testid="button-save-status"
                        >
                          {saving ? (
                            <div className="animate-spin rounded-full h-5 w-5 border-b-2 border-white" />
                          ) : (
                            <>
                              <Check className="w-5 h-5 ml-2" />
                              {editingStatus ? TEXTS.update : TEXTS.save}
                            </>
                          )}
                        </Button>
                        <Button
                          type="button"
                          variant="secondary"
                          onClick={resetForm}
                          disabled={saving}
                          className="min-h-[48px] px-6"
                          data-testid="button-cancel-status"
                        >
                          {TEXTS.cancel}
                        </Button>
                      </div>
                    </form>
                  </Card>
                </div>
              ) : (
                <div className="hidden lg:block">
                  <Card className="p-6 bg-gray-50 dark:bg-gray-900/50 border-2 border-dashed border-gray-200 dark:border-gray-700 text-center">
                    <div className="w-12 h-12 mx-auto mb-3 bg-blue-100 dark:bg-blue-900/30 rounded-full flex items-center justify-center">
                      <Edit2 className="w-6 h-6 text-blue-600" />
                    </div>
                    <p className="text-gray-500 dark:text-gray-400 mb-1">
                      בחר סטטוס לעריכה
                    </p>
                    <p className="text-sm text-gray-400 dark:text-gray-500">
                      או לחץ על "סטטוס חדש" ליצירה
                    </p>
                  </Card>
                </div>
              )}
            </div>
          </div>
        </div>
        
        {/* Footer */}
        <div className="flex-shrink-0 px-4 sm:px-5 py-3 sm:py-4 border-t border-gray-200 dark:border-gray-700 bg-gray-50 dark:bg-gray-900/50">
          <div className="flex flex-col sm:flex-row items-center justify-between gap-3">
            <div className="text-sm text-gray-600 dark:text-gray-400 text-center sm:text-right">
              💡 <strong>טיפ:</strong> לחץ על סטטוס בטבלת הלידים כדי לשנות אותו במהירות
            </div>
            <Button
              variant="secondary"
              onClick={onClose}
              data-testid="button-close-status-modal-footer"
              className="w-full sm:w-auto bg-white dark:bg-gray-800 border border-gray-300 dark:border-gray-600 hover:bg-gray-50 dark:hover:bg-gray-700 min-h-[44px]"
            >
              סגור וחזור ללידים
            </Button>
          </div>
        </div>
      </div>
    </div>
  );
}
