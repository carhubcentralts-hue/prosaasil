import React, { useState, useEffect } from 'react';
import { 
  Plus, Edit2, Trash2, X, Check, AlertTriangle, Power, 
  MessageSquare, Clock, Tag, Zap, Eye, Play, Sparkles, Calendar as CalendarIcon
} from 'lucide-react';
import { Button } from '../../../shared/components/ui/Button';
import { Input } from '../../../shared/components/ui/Input';
import { Card } from '../../../shared/components/ui/Card';
import { Badge } from '../../../shared/components/Badge';
import { useAppointmentAutomations, AppointmentAutomation } from '../../../features/calendar/hooks/useAppointmentAutomations';
import { useAppointmentStatuses } from '../../../features/calendar/hooks/useAppointmentStatuses';
import { useBusinessCalendars } from '../../../features/calendar/hooks/useBusinessCalendars';
import { useAppointmentTypes } from '../../../features/calendar/hooks/useAppointmentTypes';

interface AppointmentAutomationModalProps {
  isOpen: boolean;
  onClose: () => void;
}

interface AutomationFormData {
  name: string;
  enabled: boolean;
  trigger_status_ids: string[];
  calendar_ids?: number[] | null;
  appointment_type_keys?: string[] | null;
  schedule_offsets: Array<{
    type: 'immediate' | 'before' | 'after';
    minutes?: number;
  }>;
  message_template: string;
  cancel_on_status_exit: boolean;
}

const TEXTS = {
  title: 'ניהול אוטומציות אישורי פגישות',
  subtitle: 'שלח הודעות WhatsApp אוטומטיות על בסיס סטטוס הפגישה ותזמון',
  existing: 'אוטומציות קיימות',
  newAutomation: 'אוטומציה חדשה',
  loading: 'טוען אוטומציות...',
  edit: 'עריכת אוטומציה',
  create: 'יצירת אוטומציה חדשה',
  nameLabel: 'שם האוטומציה',
  namePlaceholder: 'לדוגמה: תזכורת יום לפני',
  statusesLabel: 'סטטוסים שמפעילים',
  statusesPlaceholder: 'בחר סטטוסים',
  calendarsLabel: 'לוחות שנה (אופציונלי)',
  calendarsPlaceholder: 'כל הלוחות',
  appointmentTypesLabel: 'סוגי פגישות (אופציונלי)',
  appointmentTypesPlaceholder: 'כל הסוגים',
  timingLabel: 'תזמון שליחה',
  messageLabel: 'תבנית הודעה',
  messagePlaceholder: 'היי {first_name} 👋\n\nתזכורת לפגישה...',
  save: 'שמור אוטומציה',
  cancel: 'ביטול',
  update: 'עדכן אוטומציה',
  delete: 'מחק',
  enabled: 'פעיל',
  disabled: 'כבוי',
  preview: 'תצוגה מקדימה',
  testPreview: 'בדוק הודעה',
  setupDefaults: 'יצירת תבניות ברירת מחדל',
  useTemplate: 'השתמש בתבנית',
  templates: 'תבניות מוכנות',
  immediate: 'מיידי',
  before: 'לפני',
  after: 'אחרי',
  minutes: 'דקות',
  hours: 'שעות',
  days: 'ימים',
  addTiming: 'הוסף תזמון',
  removeTiming: 'הסר',
  variables: 'משתנים זמינים',
  cancelOnExit: 'בטל שליחה אם הסטטוס משתנה',
  selectStatus: 'בחר אוטומציה לעריכה',
  orCreateNew: 'או לחץ על "אוטומציה חדשה" ליצירה',
};

const AVAILABLE_VARIABLES = [
  { key: '{first_name}', label: 'שם פרטי' },
  { key: '{business_name}', label: 'שם העסק' },
  { key: '{appointment_date}', label: 'תאריך הפגישה' },
  { key: '{appointment_time}', label: 'שעת הפגישה' },
  { key: '{appointment_location}', label: 'מיקום' },
  { key: '{rep_name}', label: 'שם הנציג' },
];

const TIMING_PRESETS = [
  { id: 'immediate', type: 'immediate' as const, minutes: undefined, label: 'מיידי' },
  { id: 'day_before', type: 'before' as const, minutes: 1440, label: 'יום לפני' },
  { id: 'same_day', type: 'before' as const, minutes: 180, label: 'באותו יום (3 שעות לפני)' },
];

function formatTimingLabel(offset: { type: string; minutes?: number }): string {
  if (offset.type === 'immediate') return 'מיידי';
  
  const minutes = offset.minutes || 0;
  
  // Check if it matches a preset
  const preset = TIMING_PRESETS.find(p => 
    p.type === offset.type && p.minutes === offset.minutes
  );
  
  if (preset) {
    return preset.label;
  }
  
  // Fallback to dynamic formatting (for legacy data)
  const hours = Math.floor(minutes / 60);
  const days = Math.floor(hours / 24);
  
  if (days > 0) {
    return `${days} ${days === 1 ? 'יום' : 'ימים'} ${offset.type === 'before' ? 'לפני' : 'אחרי'}`;
  } else if (hours > 0) {
    return `${hours} ${hours === 1 ? 'שעה' : 'שעות'} ${offset.type === 'before' ? 'לפני' : 'אחרי'}`;
  } else {
    return `${minutes} דקות ${offset.type === 'before' ? 'לפני' : 'אחרי'}`;
  }
}

function getPresetIdFromOffset(offset: { type: string; minutes?: number }): string {
  const preset = TIMING_PRESETS.find(p => 
    p.type === offset.type && p.minutes === offset.minutes
  );
  
  if (!preset) {
    console.warn('[AppointmentAutomationModal] No preset found for offset:', offset, 'defaulting to immediate');
  }
  
  return preset?.id || 'immediate';
}

export default function AppointmentAutomationModal({
  isOpen,
  onClose,
}: AppointmentAutomationModalProps) {
  const {
    automations,
    templates,
    loading,
    error,
    createAutomation,
    updateAutomation,
    deleteAutomation,
    testAutomationPreview,
    createFromTemplate,
    setupDefaultAutomations,
  } = useAppointmentAutomations();
  
  const { statuses } = useAppointmentStatuses();
  const { calendars } = useBusinessCalendars();
  const { types: appointmentTypes } = useAppointmentTypes();
  
  const [editingAutomation, setEditingAutomation] = useState<AppointmentAutomation | null>(null);
  const [formData, setFormData] = useState<AutomationFormData>({
    name: '',
    enabled: true,
    trigger_status_ids: [],
    calendar_ids: null,
    appointment_type_keys: null,
    schedule_offsets: [{ type: 'immediate' }],
    message_template: '',
    cancel_on_status_exit: true,
  });
  const [showForm, setShowForm] = useState(false);
  const [saving, setSaving] = useState(false);
  const [previewText, setPreviewText] = useState<string>('');
  const [showPreview, setShowPreview] = useState(false);
  const [showTemplates, setShowTemplates] = useState(false);

  // Reset form when closing
  useEffect(() => {
    if (!isOpen) {
      setShowForm(false);
      setEditingAutomation(null);
      setPreviewText('');
      setShowPreview(false);
      setShowTemplates(false);
    }
  }, [isOpen]);

  const handleNewAutomation = () => {
    setEditingAutomation(null);
    setFormData({
      name: '',
      enabled: true,
      trigger_status_ids: [],
      calendar_ids: null,
      appointment_type_keys: null,
      schedule_offsets: [{ type: 'immediate' }],
      message_template: '',
      cancel_on_status_exit: true,
    });
    setShowForm(true);
    setShowTemplates(false);
  };

  const handleEditAutomation = (automation: AppointmentAutomation) => {
    setEditingAutomation(automation);
    setFormData({
      name: automation.name,
      enabled: automation.enabled,
      trigger_status_ids: automation.trigger_status_ids,
      calendar_ids: automation.calendar_ids || null,
      appointment_type_keys: automation.appointment_type_keys || null,
      schedule_offsets: automation.schedule_offsets,
      message_template: automation.message_template,
      cancel_on_status_exit: automation.cancel_on_status_exit,
    });
    setShowForm(true);
    setShowTemplates(false);
  };

  const handleSave = async () => {
    try {
      setSaving(true);
      
      if (editingAutomation) {
        await updateAutomation(editingAutomation.id, formData);
      } else {
        await createAutomation(formData);
      }
      
      setShowForm(false);
      setEditingAutomation(null);
    } catch (err: any) {
      console.error('Failed to save automation:', err);
      alert(err.message || 'שגיאה בשמירת האוטומציה');
    } finally {
      setSaving(false);
    }
  };

  const handleDelete = async (id: number) => {
    if (!window.confirm('האם אתה בטוח שברצונך למחוק אוטומציה זו?')) {
      return;
    }
    
    try {
      await deleteAutomation(id);
    } catch (err: any) {
      console.error('Failed to delete automation:', err);
      alert(err.message || 'שגיאה במחיקת האוטומציה');
    }
  };

  const handleToggleEnabled = async (automation: AppointmentAutomation) => {
    try {
      await updateAutomation(automation.id, { enabled: !automation.enabled });
    } catch (err: any) {
      console.error('Failed to toggle automation:', err);
      alert(err.message || 'שגיאה בעדכון האוטומציה');
    }
  };

  const handlePreview = async (automationId: number) => {
    try {
      const result = await testAutomationPreview(automationId);
      setPreviewText(result.preview);
      setShowPreview(true);
    } catch (err: any) {
      console.error('Failed to get preview:', err);
      alert(err.message || 'שגיאה בתצוגה מקדימה');
    }
  };

  const handleUseTemplate = async (templateKey: string) => {
    try {
      setSaving(true);
      await createFromTemplate(templateKey, undefined, false);
      setShowTemplates(false);
    } catch (err: any) {
      console.error('Failed to create from template:', err);
      alert(err.message || 'שגיאה ביצירת אוטומציה מתבנית');
    } finally {
      setSaving(false);
    }
  };

  const handleSetupDefaults = async () => {
    if (!window.confirm('פעולה זו תיצור 5 תבניות אוטומציה מוכנות. האם להמשיך?')) {
      return;
    }
    
    try {
      setSaving(true);
      const count = await setupDefaultAutomations();
      alert(`נוצרו ${count} תבניות אוטומציה בהצלחה!`);
    } catch (err: any) {
      console.error('Failed to setup defaults:', err);
      alert(err.message || 'שגיאה ביצירת תבניות ברירת מחדל');
    } finally {
      setSaving(false);
    }
  };

  const addTimingOffset = () => {
    // Add a new timing with the first preset (immediate)
    const firstPreset = TIMING_PRESETS[0];
    setFormData({
      ...formData,
      schedule_offsets: [
        ...formData.schedule_offsets,
        { type: firstPreset.type, minutes: firstPreset.minutes }
      ]
    });
  };

  const removeTimingOffset = (index: number) => {
    setFormData({
      ...formData,
      schedule_offsets: formData.schedule_offsets.filter((_, i) => i !== index)
    });
  };

  const updateTimingOffset = (index: number, offset: { type: 'immediate' | 'before' | 'after'; minutes?: number }) => {
    const newOffsets = [...formData.schedule_offsets];
    newOffsets[index] = offset;
    setFormData({
      ...formData,
      schedule_offsets: newOffsets
    });
  };

  const insertVariable = (variable: string) => {
    setFormData({
      ...formData,
      message_template: formData.message_template + variable
    });
  };

  if (!isOpen) return null;

  return (
    <div className="fixed inset-0 bg-black bg-opacity-50 z-50 flex items-center justify-center p-4">
      <div className="bg-white rounded-xl shadow-2xl max-w-6xl w-full max-h-[90vh] overflow-y-auto">
        {/* Header */}
        <div className="sticky top-0 bg-white border-b border-slate-200 px-6 py-4 flex items-center justify-between z-10">
          <div>
            <h2 className="text-2xl font-bold text-slate-900">{TEXTS.title}</h2>
            <p className="text-sm text-slate-600 mt-1">{TEXTS.subtitle}</p>
          </div>
          <button
            onClick={onClose}
            className="text-slate-400 hover:text-slate-600 transition-colors"
          >
            <X className="h-6 w-6" />
          </button>
        </div>

        {/* Content */}
        <div className="p-6">
          {loading && !automations.length ? (
            <div className="text-center py-12">
              <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-blue-600 mx-auto"></div>
              <p className="text-slate-600 mt-4">{TEXTS.loading}</p>
            </div>
          ) : showForm ? (
            /* Form View */
            <div className="space-y-6">
              <div className="flex items-center justify-between">
                <h3 className="text-lg font-semibold text-slate-900">
                  {editingAutomation ? TEXTS.edit : TEXTS.create}
                </h3>
                <Button
                  variant="ghost"
                  onClick={() => {
                    setShowForm(false);
                    setEditingAutomation(null);
                  }}
                >
                  <X className="h-4 w-4 ml-2" />
                  {TEXTS.cancel}
                </Button>
              </div>

              {/* Name */}
              <div>
                <label className="block text-sm font-medium text-slate-700 mb-2">
                  {TEXTS.nameLabel}
                </label>
                <Input
                  value={formData.name}
                  onChange={(e) => setFormData({ ...formData, name: e.target.value })}
                  placeholder={TEXTS.namePlaceholder}
                  className="w-full"
                />
              </div>

              {/* Enabled */}
              <div className="flex items-center gap-3">
                <input
                  type="checkbox"
                  id="enabled"
                  checked={formData.enabled}
                  onChange={(e) => setFormData({ ...formData, enabled: e.target.checked })}
                  className="h-4 w-4 text-blue-600 focus:ring-blue-500 border-slate-300 rounded"
                />
                <label htmlFor="enabled" className="text-sm font-medium text-slate-700">
                  {TEXTS.enabled}
                </label>
              </div>

              {/* Trigger Statuses */}
              <div>
                <label className="block text-sm font-medium text-slate-700 mb-2">
                  {TEXTS.statusesLabel}
                </label>
                <div className="flex flex-wrap gap-2">
                  {statuses.map((status) => (
                    <button
                      key={status.key}
                      onClick={() => {
                        const newStatuses = formData.trigger_status_ids.includes(status.key)
                          ? formData.trigger_status_ids.filter(s => s !== status.key)
                          : [...formData.trigger_status_ids, status.key];
                        setFormData({ ...formData, trigger_status_ids: newStatuses });
                      }}
                      className={`px-3 py-1 rounded-full text-sm font-medium transition-all ${
                        formData.trigger_status_ids.includes(status.key)
                          ? 'bg-blue-600 text-white'
                          : 'bg-slate-100 text-slate-700 hover:bg-slate-200'
                      }`}
                    >
                      {status.label}
                    </button>
                  ))}
                </div>
              </div>

              {/* Calendar Filter */}
              <div>
                <label className="block text-sm font-medium text-slate-700 mb-2 flex items-center gap-2">
                  <CalendarIcon className="h-4 w-4" />
                  {TEXTS.calendarsLabel}
                </label>
                <div className="flex flex-wrap gap-2">
                  <button
                    onClick={() => {
                      setFormData({ ...formData, calendar_ids: null });
                    }}
                    className={`px-3 py-1 rounded-full text-sm font-medium transition-all ${
                      formData.calendar_ids === null
                        ? 'bg-purple-600 text-white'
                        : 'bg-slate-100 text-slate-700 hover:bg-slate-200'
                    }`}
                  >
                    {TEXTS.calendarsPlaceholder}
                  </button>
                  {calendars.map((calendar) => (
                    <button
                      key={calendar.id}
                      onClick={() => {
                        const currentIds = formData.calendar_ids || [];
                        const newIds = currentIds.includes(calendar.id)
                          ? currentIds.filter(id => id !== calendar.id)
                          : [...currentIds, calendar.id];
                        setFormData({ ...formData, calendar_ids: newIds.length > 0 ? newIds : null });
                      }}
                      className={`px-3 py-1 rounded-full text-sm font-medium transition-all ${
                        formData.calendar_ids && formData.calendar_ids.includes(calendar.id)
                          ? 'bg-purple-600 text-white'
                          : 'bg-slate-100 text-slate-700 hover:bg-slate-200'
                      }`}
                    >
                      {calendar.name}
                    </button>
                  ))}
                </div>
                <p className="text-xs text-slate-500 mt-1">
                  בחירה ריקה = האוטומציה תחול על כל הלוחות
                </p>
              </div>

              {/* Appointment Type Filter */}
              <div>
                <label className="block text-sm font-medium text-slate-700 mb-2 flex items-center gap-2">
                  <Tag className="h-4 w-4" />
                  {TEXTS.appointmentTypesLabel}
                </label>
                <div className="flex flex-wrap gap-2">
                  <button
                    onClick={() => {
                      setFormData({ ...formData, appointment_type_keys: null });
                    }}
                    className={`px-3 py-1 rounded-full text-sm font-medium transition-all ${
                      formData.appointment_type_keys === null
                        ? 'bg-green-600 text-white'
                        : 'bg-slate-100 text-slate-700 hover:bg-slate-200'
                    }`}
                  >
                    {TEXTS.appointmentTypesPlaceholder}
                  </button>
                  {appointmentTypes.map((type) => (
                    <button
                      key={type.key}
                      onClick={() => {
                        const currentKeys = formData.appointment_type_keys || [];
                        const newKeys = currentKeys.includes(type.key)
                          ? currentKeys.filter(k => k !== type.key)
                          : [...currentKeys, type.key];
                        setFormData({ ...formData, appointment_type_keys: newKeys.length > 0 ? newKeys : null });
                      }}
                      className={`px-3 py-1 rounded-full text-sm font-medium transition-all ${
                        formData.appointment_type_keys && formData.appointment_type_keys.includes(type.key)
                          ? 'bg-green-600 text-white'
                          : 'bg-slate-100 text-slate-700 hover:bg-slate-200'
                      }`}
                    >
                      {type.label}
                    </button>
                  ))}
                </div>
                <p className="text-xs text-slate-500 mt-1">
                  בחירה ריקה = האוטומציה תחול על כל סוגי הפגישות
                </p>
              </div>

              {/* Schedule Offsets */}
              <div>
                <label className="block text-sm font-medium text-slate-700 mb-2">
                  {TEXTS.timingLabel}
                </label>
                <div className="space-y-2">
                  {formData.schedule_offsets.map((offset, index) => (
                    <div key={index} className="flex items-center gap-2">
                      <select
                        value={getPresetIdFromOffset(offset)}
                        onChange={(e) => {
                          const selectedPreset = TIMING_PRESETS.find(p => p.id === e.target.value);
                          if (selectedPreset) {
                            updateTimingOffset(index, {
                              type: selectedPreset.type,
                              minutes: selectedPreset.minutes
                            });
                          }
                        }}
                        className="flex-1 border border-slate-300 rounded-lg px-3 py-2"
                      >
                        {TIMING_PRESETS.map((preset) => (
                          <option key={preset.id} value={preset.id}>
                            {preset.label}
                          </option>
                        ))}
                      </select>
                      
                      <Button
                        variant="ghost"
                        size="sm"
                        onClick={() => removeTimingOffset(index)}
                        disabled={formData.schedule_offsets.length === 1}
                      >
                        <Trash2 className="h-4 w-4" />
                      </Button>
                    </div>
                  ))}
                  <Button
                    variant="outline"
                    size="sm"
                    onClick={addTimingOffset}
                  >
                    <Plus className="h-4 w-4 ml-2" />
                    {TEXTS.addTiming}
                  </Button>
                </div>
              </div>

              {/* Cancel on Status Exit */}
              <div className="flex items-center gap-3">
                <input
                  type="checkbox"
                  id="cancelOnExit"
                  checked={formData.cancel_on_status_exit}
                  onChange={(e) => setFormData({ ...formData, cancel_on_status_exit: e.target.checked })}
                  className="h-4 w-4 text-blue-600 focus:ring-blue-500 border-slate-300 rounded"
                />
                <label htmlFor="cancelOnExit" className="text-sm font-medium text-slate-700">
                  {TEXTS.cancelOnExit}
                </label>
              </div>

              {/* Message Template */}
              <div>
                <label className="block text-sm font-medium text-slate-700 mb-2">
                  {TEXTS.messageLabel}
                </label>
                <textarea
                  value={formData.message_template}
                  onChange={(e) => setFormData({ ...formData, message_template: e.target.value })}
                  placeholder={TEXTS.messagePlaceholder}
                  className="w-full border border-slate-300 rounded-lg px-3 py-2 min-h-[150px] font-mono text-sm"
                  dir="rtl"
                />
                
                {/* Available Variables */}
                <div className="mt-2">
                  <p className="text-xs text-slate-600 mb-2">{TEXTS.variables}:</p>
                  <div className="flex flex-wrap gap-2">
                    {AVAILABLE_VARIABLES.map((variable) => (
                      <button
                        key={variable.key}
                        onClick={() => insertVariable(variable.key)}
                        className="px-2 py-1 bg-slate-100 hover:bg-slate-200 rounded text-xs font-mono"
                      >
                        {variable.key} - {variable.label}
                      </button>
                    ))}
                  </div>
                </div>
              </div>

              {/* Save Button */}
              <div className="flex justify-end gap-3">
                <Button
                  variant="outline"
                  onClick={() => {
                    setShowForm(false);
                    setEditingAutomation(null);
                  }}
                >
                  {TEXTS.cancel}
                </Button>
                <Button
                  onClick={handleSave}
                  disabled={saving || !formData.name || !formData.message_template || formData.trigger_status_ids.length === 0}
                >
                  {saving ? 'שומר...' : (editingAutomation ? TEXTS.update : TEXTS.save)}
                </Button>
              </div>
            </div>
          ) : showTemplates ? (
            /* Templates View */
            <div className="space-y-4">
              <div className="flex items-center justify-between">
                <h3 className="text-lg font-semibold text-slate-900">{TEXTS.templates}</h3>
                <Button
                  variant="ghost"
                  onClick={() => setShowTemplates(false)}
                >
                  <X className="h-4 w-4 ml-2" />
                  סגור
                </Button>
              </div>
              
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                {templates.map((template) => (
                  <Card key={template.key} className="p-4">
                    <div className="flex items-start justify-between">
                      <div>
                        <h4 className="font-semibold text-slate-900">{template.name}</h4>
                        <p className="text-sm text-slate-600 mt-1">{template.description}</p>
                      </div>
                      <Button
                        size="sm"
                        onClick={() => handleUseTemplate(template.key)}
                        disabled={saving}
                      >
                        <Sparkles className="h-4 w-4 ml-2" />
                        השתמש
                      </Button>
                    </div>
                  </Card>
                ))}
              </div>
            </div>
          ) : (
            /* List View */
            <div className="space-y-4">
              {/* Action Buttons */}
              <div className="flex flex-wrap gap-3">
                <Button onClick={handleNewAutomation}>
                  <Plus className="h-4 w-4 ml-2" />
                  {TEXTS.newAutomation}
                </Button>
                <Button
                  variant="outline"
                  onClick={() => setShowTemplates(true)}
                >
                  <Sparkles className="h-4 w-4 ml-2" />
                  {TEXTS.useTemplate}
                </Button>
                <Button
                  variant="outline"
                  onClick={handleSetupDefaults}
                  disabled={saving}
                >
                  <Zap className="h-4 w-4 ml-2" />
                  {TEXTS.setupDefaults}
                </Button>
              </div>

              {/* Automations List */}
              {automations.length === 0 ? (
                <Card className="p-8 text-center">
                  <MessageSquare className="h-12 w-12 text-slate-300 mx-auto mb-4" />
                  <p className="text-slate-600">{TEXTS.selectStatus}</p>
                  <p className="text-sm text-slate-500 mt-2">{TEXTS.orCreateNew}</p>
                </Card>
              ) : (
                <div className="space-y-3">
                  {automations.map((automation) => (
                    <Card key={automation.id} className="p-4">
                      <div className="flex items-start justify-between">
                        <div className="flex-1">
                          <div className="flex items-center gap-3 mb-2">
                            <h4 className="font-semibold text-slate-900">{automation.name}</h4>
                            <Badge variant={automation.enabled ? 'success' : 'secondary'}>
                              {automation.enabled ? TEXTS.enabled : TEXTS.disabled}
                            </Badge>
                          </div>
                          
                          <div className="flex flex-wrap gap-2 mb-2">
                            <div className="flex items-center gap-1 text-sm text-slate-600">
                              <Tag className="h-4 w-4" />
                              <span>{automation.trigger_status_ids.length} סטטוסים</span>
                            </div>
                            <div className="flex items-center gap-1 text-sm text-slate-600">
                              <Clock className="h-4 w-4" />
                              <span>{automation.schedule_offsets.length} תזמונים</span>
                            </div>
                          </div>
                          
                          <div className="flex flex-wrap gap-2">
                            {automation.schedule_offsets.map((offset, idx) => (
                              <Badge key={idx} variant="outline">
                                {formatTimingLabel(offset)}
                              </Badge>
                            ))}
                          </div>
                        </div>
                        
                        <div className="flex items-center gap-2">
                          <Button
                            size="sm"
                            variant="ghost"
                            onClick={() => handleToggleEnabled(automation)}
                            title={automation.enabled ? 'השבת' : 'הפעל'}
                          >
                            <Power className={`h-4 w-4 ${automation.enabled ? 'text-green-600' : 'text-slate-400'}`} />
                          </Button>
                          <Button
                            size="sm"
                            variant="ghost"
                            onClick={() => handlePreview(automation.id)}
                            title="תצוגה מקדימה"
                          >
                            <Eye className="h-4 w-4" />
                          </Button>
                          <Button
                            size="sm"
                            variant="ghost"
                            onClick={() => handleEditAutomation(automation)}
                            title="ערוך"
                          >
                            <Edit2 className="h-4 w-4" />
                          </Button>
                          <Button
                            size="sm"
                            variant="ghost"
                            onClick={() => handleDelete(automation.id)}
                            title="מחק"
                          >
                            <Trash2 className="h-4 w-4 text-red-600" />
                          </Button>
                        </div>
                      </div>
                    </Card>
                  ))}
                </div>
              )}
            </div>
          )}
        </div>

        {/* Preview Modal */}
        {showPreview && (
          <div className="fixed inset-0 bg-black bg-opacity-50 z-50 flex items-center justify-center p-4">
            <div className="bg-white rounded-xl shadow-2xl max-w-2xl w-full p-6">
              <div className="flex items-center justify-between mb-4">
                <h3 className="text-lg font-semibold text-slate-900">תצוגה מקדימה</h3>
                <button
                  onClick={() => setShowPreview(false)}
                  className="text-slate-400 hover:text-slate-600"
                >
                  <X className="h-5 w-5" />
                </button>
              </div>
              <div className="bg-slate-50 rounded-lg p-4 whitespace-pre-wrap font-sans text-sm" dir="rtl">
                {previewText}
              </div>
              <div className="mt-4 flex justify-end">
                <Button onClick={() => setShowPreview(false)}>
                  סגור
                </Button>
              </div>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
