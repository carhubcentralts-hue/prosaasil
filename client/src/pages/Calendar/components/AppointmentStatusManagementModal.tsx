import React, { useState, useEffect } from 'react';
import { Plus, Edit2, Trash2, X, Check, AlertTriangle } from 'lucide-react';
import { Button } from '../../../shared/components/ui/Button';
import { Input } from '../../../shared/components/ui/Input';
import { Card } from '../../../shared/components/ui/Card';
import { Badge } from '../../../shared/components/Badge';
import { useAppointmentStatuses } from '../../../features/calendar/hooks/useAppointmentStatuses';
import { AppointmentStatusConfig } from '../../../shared/types/status';

interface AppointmentStatusManagementModalProps {
  isOpen: boolean;
  onClose: () => void;
  onStatusChange?: () => void;
}

interface StatusFormData {
  key: string;
  label: string;
  color: string;
}

const TEXTS = {
  title: 'ניהול סטטוסי פגישות',
  subtitle: 'צור, ערוך ומחק את סטטוסי הפגישות של העסק',
  existing: 'סטטוסים קיימים',
  newStatus: 'סטטוס חדש',
  loading: 'טוען סטטוסים...',
  edit: 'עריכת סטטוס',
  create: 'יצירת סטטוס חדש',
  keyLabel: 'מפתח פנימי',
  keyPlaceholder: 'לדוגמה: confirmed, cancelled...',
  displayLabel: 'שם הסטטוס',
  displayPlaceholder: 'לדוגמה: מאושר, בוטל...',
  colorLabel: 'צבע',
  save: 'שמור סטטוס',
  cancel: 'ביטול',
  update: 'עדכן סטטוס',
  confirmDelete: 'מחיקת סטטוס',
  deleteConfirmText: 'האם אתה בטוח שברצונך למחוק את הסטטוס',
  deleteWarning: 'פעולה זו לא ניתנת לביטול',
  deleteError: 'שגיאה במחיקת הסטטוס',
  saveError: 'שגיאה בשמירת הסטטוס',
  emptyLabel: 'נא להזין שם לסטטוס',
  emptyKey: 'נא להזין מפתח לסטטוס',
  clickToEdit: 'לחץ לעריכה',
  deleteBtn: 'מחק',
  editBtn: 'ערוך',
  selectStatus: 'בחר סטטוס לעריכה',
  orCreateNew: 'או לחץ על "סטטוס חדש" ליצירה',
};

const COLOR_OPTIONS = [
  { value: 'blue', label: 'כחול' },
  { value: 'yellow', label: 'צהוב' },
  { value: 'purple', label: 'סגול' },
  { value: 'green', label: 'ירוק' },
  { value: 'red', label: 'אדום' },
  { value: 'gray', label: 'אפור' },
  { value: 'orange', label: 'כתום' },
  { value: 'pink', label: 'ורוד' },
  { value: 'indigo', label: 'אינדיגו' },
  { value: 'teal', label: 'טורקיז' },
  { value: 'cyan', label: 'תכלת' },
];

function getColorClasses(colorName: string): string {
  const colorMap: Record<string, string> = {
    blue: 'bg-blue-100 text-blue-800',
    yellow: 'bg-yellow-100 text-yellow-800',
    purple: 'bg-purple-100 text-purple-800',
    green: 'bg-green-100 text-green-800',
    red: 'bg-red-100 text-red-800',
    gray: 'bg-gray-100 text-gray-800',
    orange: 'bg-orange-100 text-orange-800',
    pink: 'bg-pink-100 text-pink-800',
    indigo: 'bg-indigo-100 text-indigo-800',
    teal: 'bg-teal-100 text-teal-800',
    cyan: 'bg-cyan-100 text-cyan-800',
  };
  return colorMap[colorName] || colorMap.blue;
}

function getColorPreview(colorName: string): string {
  const colorMap: Record<string, string> = {
    blue: 'bg-blue-500',
    yellow: 'bg-yellow-500',
    purple: 'bg-purple-500',
    green: 'bg-green-500',
    red: 'bg-red-500',
    gray: 'bg-gray-500',
    orange: 'bg-orange-500',
    pink: 'bg-pink-500',
    indigo: 'bg-indigo-500',
    teal: 'bg-teal-500',
    cyan: 'bg-cyan-500',
  };
  return colorMap[colorName] || colorMap.blue;
}

export default function AppointmentStatusManagementModal({ 
  isOpen, 
  onClose, 
  onStatusChange 
}: AppointmentStatusManagementModalProps) {
  const { statuses, loading, error, refreshStatuses, updateStatuses } = useAppointmentStatuses();

  const [editingIndex, setEditingIndex] = useState<number | null>(null);
  const [isCreating, setIsCreating] = useState(false);
  const [saving, setSaving] = useState(false);
  const [formError, setFormError] = useState<string | null>(null);
  const [deleteConfirmIndex, setDeleteConfirmIndex] = useState<number | null>(null);
  const [formData, setFormData] = useState<StatusFormData>({
    key: '',
    label: '',
    color: 'blue',
  });

  useEffect(() => {
    if (isOpen) {
      refreshStatuses();
    }
  }, [isOpen, refreshStatuses]);

  const resetForm = () => {
    setFormData({
      key: '',
      label: '',
      color: 'blue',
    });
    setEditingIndex(null);
    setIsCreating(false);
    setFormError(null);
  };

  const handleEdit = (status: AppointmentStatusConfig, index: number) => {
    setFormData({
      key: status.key,
      label: status.label,
      color: status.color,
    });
    setEditingIndex(index);
    setIsCreating(false);
    setFormError(null);
    setDeleteConfirmIndex(null);
  };

  const handleStartCreate = () => {
    resetForm();
    setIsCreating(true);
    setDeleteConfirmIndex(null);
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setFormError(null);
    
    if (!formData.label.trim()) {
      setFormError(TEXTS.emptyLabel);
      return;
    }
    
    if (!formData.key.trim()) {
      setFormError(TEXTS.emptyKey);
      return;
    }
    
    setSaving(true);
    try {
      const updatedStatuses = [...statuses];
      
      if (editingIndex !== null) {
        // Update existing
        updatedStatuses[editingIndex] = {
          key: formData.key.trim(),
          label: formData.label.trim(),
          color: formData.color,
        };
      } else {
        // Add new
        updatedStatuses.push({
          key: formData.key.trim(),
          label: formData.label.trim(),
          color: formData.color,
        });
      }
      
      await updateStatuses(updatedStatuses);
      resetForm();
      
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

  const handleDeleteClick = (index: number, e: React.MouseEvent) => {
    e.stopPropagation();
    setDeleteConfirmIndex(index);
    setEditingIndex(null);
    setIsCreating(false);
  };

  const handleDeleteConfirm = async () => {
    if (deleteConfirmIndex === null) return;
    
    setSaving(true);
    try {
      const updatedStatuses = statuses.filter((_, idx) => idx !== deleteConfirmIndex);
      await updateStatuses(updatedStatuses);
      setDeleteConfirmIndex(null);
      
      if (onStatusChange) {
        onStatusChange();
      }
    } catch (error) {
      console.error('Failed to delete status:', error);
      alert(TEXTS.deleteError);
    } finally {
      setSaving(false);
    }
  };

  const handleDeleteCancel = () => {
    setDeleteConfirmIndex(null);
  };

  if (!isOpen) return null;

  const statusToDelete = deleteConfirmIndex !== null ? statuses[deleteConfirmIndex] : null;

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
              {TEXTS.subtitle}
            </p>
          </div>
          <Button
            variant="ghost"
            size="sm"
            onClick={onClose}
            className="h-10 w-10 p-0 rounded-full hover:bg-gray-200 dark:hover:bg-gray-700"
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
                  {TEXTS.existing}
                  <span className="text-sm font-normal text-gray-500">({statuses.length})</span>
                </h3>
                <Button
                  onClick={handleStartCreate}
                  className="bg-blue-600 hover:bg-blue-700 text-white shadow-md hover:shadow-lg transition-all"
                  size="sm"
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
                  {statuses.map((status, index) => {
                    const isEditing = editingIndex === index;
                    const isDeleting = deleteConfirmIndex === index;
                    
                    return (
                      <div key={index}>
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
                                  onClick={handleDeleteConfirm}
                                  disabled={saving}
                                  className="bg-red-600 hover:bg-red-700 text-white flex-1 sm:flex-none min-h-[44px]"
                                >
                                  {saving ? (
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
                                  disabled={saving}
                                  className="flex-1 sm:flex-none min-h-[44px]"
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
                            onClick={() => handleEdit(status, index)}
                          >
                            <div className="p-3 sm:p-4">
                              <div className="flex items-center justify-between gap-3">
                                {/* Status Info */}
                                <div className="flex items-center gap-3 flex-1 min-w-0">
                                  <Badge className={`${getColorClasses(status.color)} text-sm px-3 py-1`}>
                                    {status.label}
                                  </Badge>
                                  <span className="text-xs text-gray-500">({status.key})</span>
                                </div>
                                
                                {/* Action Buttons */}
                                <div className="flex items-center gap-1 sm:gap-2 flex-shrink-0">
                                  <Button
                                    size="sm"
                                    variant="ghost"
                                    onClick={(e) => {
                                      e.stopPropagation();
                                      handleEdit(status, index);
                                    }}
                                    className={`min-h-[40px] min-w-[40px] sm:min-w-[auto] sm:px-3 rounded-lg transition-all ${
                                      isEditing 
                                        ? 'bg-blue-100 text-blue-700' 
                                        : 'hover:bg-blue-50 text-gray-600 hover:text-blue-600'
                                    }`}
                                  >
                                    <Edit2 className="w-4 h-4" />
                                    <span className="hidden sm:inline mr-1.5">{TEXTS.editBtn}</span>
                                  </Button>
                                  <Button
                                    size="sm"
                                    variant="ghost"
                                    onClick={(e) => handleDeleteClick(index, e)}
                                    className="min-h-[40px] min-w-[40px] sm:min-w-[auto] sm:px-3 rounded-lg text-gray-500 hover:text-red-600 hover:bg-red-50 transition-all"
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
              {(isCreating || editingIndex !== null) ? (
                <div className="sticky top-0">
                  <Card className="p-4 sm:p-5 bg-white dark:bg-gray-800 shadow-lg border-2 border-blue-100 dark:border-blue-900/50">
                    <h3 className="text-base sm:text-lg font-semibold text-gray-900 dark:text-white mb-4 flex items-center gap-2">
                      {editingIndex !== null ? (
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
                      {/* Key */}
                      <div>
                        <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">
                          {TEXTS.keyLabel} <span className="text-red-500">*</span>
                        </label>
                        <Input
                          value={formData.key}
                          onChange={(e) => setFormData(prev => ({ ...prev, key: e.target.value }))}
                          placeholder={TEXTS.keyPlaceholder}
                          required
                          className="text-right text-base min-h-[44px]"
                          disabled={editingIndex !== null}
                        />
                      </div>

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
                              title={option.label}
                            >
                              <div className={`w-6 h-6 rounded-full ${getColorPreview(option.value)}`} />
                              {formData.color === option.value && (
                                <Check className="w-3 h-3 text-white absolute" />
                              )}
                            </button>
                          ))}
                        </div>
                        {/* Preview */}
                        <div className="mt-3 p-3 bg-gray-50 dark:bg-gray-900/50 rounded-lg">
                          <p className="text-xs text-gray-500 mb-2">תצוגה מקדימה:</p>
                          <Badge className={`${getColorClasses(formData.color)} text-sm px-3 py-1`}>
                            {formData.label || 'שם הסטטוס'}
                          </Badge>
                        </div>
                      </div>

                      {/* Form Actions */}
                      <div className="flex items-center gap-3 pt-2">
                        <Button
                          type="submit"
                          className="flex-1 bg-blue-600 hover:bg-blue-700 text-white min-h-[48px] text-base font-medium shadow-md hover:shadow-lg transition-all"
                          disabled={saving}
                        >
                          {saving ? (
                            <div className="animate-spin rounded-full h-5 w-5 border-b-2 border-white" />
                          ) : (
                            <>
                              <Check className="w-5 h-5 ml-2" />
                              {editingIndex !== null ? TEXTS.update : TEXTS.save}
                            </>
                          )}
                        </Button>
                        <Button
                          type="button"
                          variant="secondary"
                          onClick={resetForm}
                          disabled={saving}
                          className="min-h-[48px] px-6"
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
                      {TEXTS.selectStatus}
                    </p>
                    <p className="text-sm text-gray-400 dark:text-gray-500">
                      {TEXTS.orCreateNew}
                    </p>
                  </Card>
                </div>
              )}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
