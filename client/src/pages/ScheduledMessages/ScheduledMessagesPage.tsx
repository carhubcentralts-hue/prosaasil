import React, { useState, useEffect } from 'react';
import { Clock, Plus, Play, Pause, Trash2, Edit2, Eye, CheckCircle, XCircle, AlertCircle, Calendar, Zap, List, GripVertical, X } from 'lucide-react';
import * as scheduledMessagesApi from '../../services/scheduledMessages';
import { http } from '../../services/http';

// Temporary UI components
const Card = ({ children, className = "" }: { children: React.ReactNode; className?: string }) => (
  <div className={`border border-gray-200 rounded-lg bg-white shadow-sm ${className}`}>{children}</div>
);

const Button = ({ children, className = "", variant = "default", size = "default", disabled = false, ...props }: {
  children: React.ReactNode;
  className?: string;
  variant?: "default" | "outline" | "ghost" | "destructive";
  size?: "default" | "sm";
  disabled?: boolean;
  [key: string]: any;
}) => {
  const baseClasses = "px-4 py-2 rounded-md font-medium transition-colors disabled:opacity-50 disabled:cursor-not-allowed";
  const variantClasses = {
    default: "bg-blue-600 text-white hover:bg-blue-700 disabled:hover:bg-blue-600",
    outline: "border border-gray-300 bg-white text-gray-700 hover:bg-gray-50",
    ghost: "text-gray-700 hover:bg-gray-100",
    destructive: "bg-red-600 text-white hover:bg-red-700"
  };
  const sizeClasses = {
    default: "px-4 py-2",
    sm: "px-3 py-1 text-sm"
  };
  return (
    <button 
      className={`${baseClasses} ${variantClasses[variant]} ${sizeClasses[size]} ${className}`} 
      disabled={disabled}
      {...props}
    >
      {children}
    </button>
  );
};

const Badge = ({ children, className = "", variant = "default" }: {
  children: React.ReactNode;
  className?: string;
  variant?: "default" | "secondary" | "destructive" | "success" | "warning";
}) => {
  const variantClasses = {
    default: "bg-gray-100 text-gray-800",
    secondary: "bg-gray-100 text-gray-800", 
    destructive: "bg-red-100 text-red-800",
    success: "bg-green-100 text-green-800",
    warning: "bg-yellow-100 text-yellow-800"
  };
  return (
    <span className={`px-2 py-1 text-xs rounded-full ${variantClasses[variant]} ${className}`}>
      {children}
    </span>
  );
};

interface LeadStatus {
  id: number;
  name: string;
  label: string;
  color?: string;
}

export function ScheduledMessagesPage() {
  const [rules, setRules] = useState<scheduledMessagesApi.ScheduledRule[]>([]);
  const [statuses, setStatuses] = useState<LeadStatus[]>([]);
  const [templates, setTemplates] = useState<scheduledMessagesApi.ManualTemplate[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [showCreateModal, setShowCreateModal] = useState(false);
  const [selectedRule, setSelectedRule] = useState<scheduledMessagesApi.ScheduledRule | null>(null);
  const [showQueueView, setShowQueueView] = useState<number | null>(null);

  // Load rules and statuses
  useEffect(() => {
    loadData();
  }, []);

  const loadData = async () => {
    try {
      setLoading(true);
      const [rulesData, statusesResponse, templatesData] = await Promise.all([
        scheduledMessagesApi.getRules(),
        http.get<any>('/api/statuses'),
        scheduledMessagesApi.getManualTemplates()
      ]);
      
      // Guard: ensure rulesData is an array
      const rules = Array.isArray(rulesData) ? rulesData : [];
      // http.get returns JSON directly - check for items property
      const statusesData = statusesResponse?.items || statusesResponse || [];
      const statuses = Array.isArray(statusesData) ? statusesData : [];
      const templates = Array.isArray(templatesData) ? templatesData : [];
      
      setRules(rules);
      setStatuses(statuses);
      setTemplates(templates);
      setError(null);
    } catch (err: any) {
      setError(err.message || 'Failed to load data');
      console.error('Error loading data:', err);
      // Set empty arrays to prevent crashes
      setRules([]);
      setStatuses([]);
      setTemplates([]);
    } finally {
      setLoading(false);
    }
  };

  const handleToggleActive = async (ruleId: number, isActive: boolean) => {
    try {
      await scheduledMessagesApi.updateRule(ruleId, { is_active: !isActive });
      await loadData();
    } catch (err: any) {
      alert('Failed to update rule: ' + (err.message || 'Unknown error'));
    }
  };

  const handleDeleteRule = async (ruleId: number) => {
    if (!confirm('Are you sure you want to delete this rule? This will also delete all pending messages.')) {
      return;
    }
    
    try {
      await scheduledMessagesApi.deleteRule(ruleId);
      await loadData();
    } catch (err: any) {
      alert('Failed to delete rule: ' + (err.message || 'Unknown error'));
    }
  };

  const handleCancelPending = async (ruleId: number) => {
    if (!confirm('Are you sure you want to cancel all pending messages for this rule?')) {
      return;
    }
    
    try {
      const result = await scheduledMessagesApi.cancelPendingForRule(ruleId);
      alert(`Cancelled ${result.cancelled_count} pending message(s)`);
      await loadData();
    } catch (err: any) {
      alert('Failed to cancel pending messages: ' + (err.message || 'Unknown error'));
    }
  };

  if (loading) {
    return (
      <div className="min-h-screen bg-gray-50 p-6 rtl">
        <div className="max-w-7xl mx-auto">
          <div className="text-center py-12">
            <p className="text-gray-500">טוען...</p>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-gray-50 p-6 rtl">
      <div className="max-w-7xl mx-auto">
        {/* Header */}
        <div className="mb-8">
          <div className="flex items-center justify-between mb-2">
            <div className="flex items-center gap-3">
              <Clock className="w-8 h-8 text-blue-600" />
              <h1 className="text-3xl font-bold text-gray-900">תזמון הודעות WhatsApp</h1>
            </div>
            <Button onClick={() => setShowCreateModal(true)}>
              <Plus className="w-4 h-4 ml-2" />
              חוק חדש
            </Button>
          </div>
          <p className="text-gray-600">
            צור חוקים לשליחת הודעות WhatsApp אוטומטית כאשר לידים משנים סטטוס
          </p>
        </div>

        {error && (
          <div className="mb-6 p-4 bg-red-50 border border-red-200 rounded-lg text-red-700">
            {error}
          </div>
        )}

        {/* Rules Table */}
        <Card className="overflow-hidden">
          <div className="overflow-x-auto">
            <table className="min-w-full divide-y divide-gray-200">
              <thead className="bg-gray-50">
                <tr>
                  <th className="px-6 py-3 text-right text-xs font-medium text-gray-500 uppercase tracking-wider">
                    שם החוק
                  </th>
                  <th className="px-6 py-3 text-right text-xs font-medium text-gray-500 uppercase tracking-wider">
                    סטטוסים
                  </th>
                  <th className="px-6 py-3 text-right text-xs font-medium text-gray-500 uppercase tracking-wider">
                    ספק
                  </th>
                  <th className="px-6 py-3 text-right text-xs font-medium text-gray-500 uppercase tracking-wider">
                    סטטוס
                  </th>
                  <th className="px-6 py-3 text-right text-xs font-medium text-gray-500 uppercase tracking-wider">
                    פעולות
                  </th>
                </tr>
              </thead>
              <tbody className="bg-white divide-y divide-gray-200">
                {(!rules || rules.length === 0) ? (
                  <tr>
                    <td colSpan={6} className="px-6 py-12 text-center text-gray-500">
                      <Clock className="w-12 h-12 mx-auto mb-4 text-gray-300" />
                      <p className="text-lg font-medium mb-2">אין חוקי תזמון</p>
                      <p className="text-sm">צור חוק חדש כדי להתחיל לשלוח הודעות מתוזמנות</p>
                    </td>
                  </tr>
                ) : (
                  rules.map((rule) => (
                    <tr key={rule.id} className="hover:bg-gray-50">
                       <td className="px-6 py-4 whitespace-nowrap">
                        <div className="flex items-center gap-2">
                          <div className="text-sm font-medium text-gray-900">{rule.name}</div>
                          {rule.send_immediately_on_enter && (
                            <Zap className="w-4 h-4 text-yellow-500" title="שולח מיד בעת כניסה לסטטוס" />
                          )}
                          {rule.steps && rule.steps.length > 0 && (
                            <Badge variant="secondary" className="flex items-center gap-1">
                              <List className="w-3 h-3" />
                              {rule.steps.length} שלבים
                            </Badge>
                          )}
                        </div>
                      </td>
                      <td className="px-6 py-4">
                        <div className="flex flex-wrap gap-1">
                          {rule.statuses.map((status) => (
                            <Badge key={status.id} variant="default">
                              {status.label}
                            </Badge>
                          ))}
                        </div>
                      </td>
                      <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-900">
                        <Badge variant={rule.provider === 'baileys' ? 'default' : rule.provider === 'meta' ? 'secondary' : 'warning'}>
                          {rule.provider === 'baileys' ? 'Baileys' : rule.provider === 'meta' ? 'Meta' : rule.provider || 'Baileys'}
                        </Badge>
                      </td>
                      <td className="px-6 py-4 whitespace-nowrap">
                        <button
                          onClick={() => handleToggleActive(rule.id, rule.is_active)}
                          className="flex items-center gap-2"
                        >
                          {rule.is_active ? (
                            <>
                              <CheckCircle className="w-4 h-4 text-green-600" />
                              <span className="text-sm text-green-600">פעיל</span>
                            </>
                          ) : (
                            <>
                              <XCircle className="w-4 h-4 text-gray-400" />
                              <span className="text-sm text-gray-400">מושהה</span>
                            </>
                          )}
                        </button>
                      </td>
                      <td className="px-6 py-4 whitespace-nowrap text-sm">
                        <div className="flex items-center gap-2">
                          <Button
                            size="sm"
                            variant="ghost"
                            onClick={() => setShowQueueView(rule.id)}
                          >
                            <Eye className="w-4 h-4" />
                          </Button>
                          <Button
                            size="sm"
                            variant="ghost"
                            onClick={() => handleCancelPending(rule.id)}
                          >
                            <AlertCircle className="w-4 h-4" />
                          </Button>
                          <Button
                            size="sm"
                            variant="ghost"
                            onClick={() => {
                              setSelectedRule(rule);
                              setShowCreateModal(true);
                            }}
                          >
                            <Edit2 className="w-4 h-4" />
                          </Button>
                          <Button
                            size="sm"
                            variant="ghost"
                            onClick={() => handleDeleteRule(rule.id)}
                          >
                            <Trash2 className="w-4 h-4 text-red-600" />
                          </Button>
                        </div>
                      </td>
                    </tr>
                  ))
                )}
              </tbody>
            </table>
          </div>
        </Card>

        {/* Create/Edit Modal */}
        {showCreateModal && (
          <CreateRuleModal
            rule={selectedRule}
            statuses={statuses}
            templates={templates}
            onClose={() => {
              setShowCreateModal(false);
              setSelectedRule(null);
            }}
            onSave={async () => {
              await loadData();
              setShowCreateModal(false);
              setSelectedRule(null);
            }}
          />
        )}

        {/* Queue View Modal */}
        {showQueueView && (
          <QueueViewModal
            ruleId={showQueueView}
            onClose={() => setShowQueueView(null)}
          />
        )}
      </div>
    </div>
  );
}

// Create/Edit Rule Modal Component
function CreateRuleModal({
  rule,
  statuses,
  templates,
  onClose,
  onSave
}: {
  rule: scheduledMessagesApi.ScheduledRule | null;
  statuses: LeadStatus[];
  templates: scheduledMessagesApi.ManualTemplate[];
  onClose: () => void;
  onSave: () => void;
}) {
  // UI-friendly step format
  type UIStep = {
    step_index: number;
    message_text: string;
    delay_value: number;
    delay_unit: 'minutes' | 'hours' | 'days';
    is_enabled: boolean;
  };
  
  // Convert API steps to UI format
  const convertApiStepsToUI = (apiSteps?: scheduledMessagesApi.RuleStep[]): UIStep[] => {
    if (!apiSteps) return [];
    return apiSteps.map(step => {
      const delayMinutes = Math.floor(step.delay_seconds / 60);
      let delay_value = delayMinutes;
      let delay_unit: 'minutes' | 'hours' | 'days' = 'minutes';
      
      // Try to convert to larger units if possible
      if (delayMinutes >= 1440 && delayMinutes % 1440 === 0) {
        delay_value = delayMinutes / 1440;
        delay_unit = 'days';
      } else if (delayMinutes >= 60 && delayMinutes % 60 === 0) {
        delay_value = delayMinutes / 60;
        delay_unit = 'hours';
      }
      
      return {
        step_index: step.step_index,
        message_text: step.message_template,
        delay_value,
        delay_unit,
        is_enabled: step.enabled
      };
    });
  };
  
  const [formData, setFormData] = useState({
    name: rule?.name || '',
    status_ids: rule?.statuses.map(s => s.id) || [],
    provider: rule?.provider || 'baileys',
    is_active: rule?.is_active ?? true,
    send_immediately_on_enter: rule?.send_immediately_on_enter ?? false,
    immediate_message: rule?.immediate_message || '',
    apply_mode: rule?.apply_mode || 'ON_ENTER_ONLY',
    steps: convertApiStepsToUI(rule?.steps)
  });
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [selectedTemplate, setSelectedTemplate] = useState<string>('');

  const getDelayInMinutes = (value: number, unit: 'minutes' | 'hours' | 'days'): number => {
    switch (unit) {
      case 'minutes': return value;
      case 'hours': return value * 60;
      case 'days': return value * 60 * 24;
      default: return value;
    }
  };
  
  const getDelayInSeconds = (value: number, unit: 'minutes' | 'hours' | 'days'): number => {
    return getDelayInMinutes(value, unit) * 60;
  };
  
  // Convert UI steps to API format
  const convertUIStepsToAPI = (uiSteps: UIStep[]) => {
    return uiSteps.map(step => ({
      step_index: step.step_index,
      message_template: step.message_text,
      delay_seconds: getDelayInSeconds(step.delay_value, step.delay_unit),
      enabled: step.is_enabled
    }));
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    
    if (!formData.name.trim()) {
      setError('שם החוק הוא שדה חובה');
      return;
    }
    
    if (formData.status_ids.length === 0) {
      setError('יש לבחור לפחות סטטוס אחד');
      return;
    }
    
    // Validate immediate message if send_immediately_on_enter is checked
    if (formData.send_immediately_on_enter && !formData.immediate_message.trim()) {
      setError('יש למלא הודעה מיידית כאשר "שלח מיד בעת כניסה לסטטוס" מסומן');
      return;
    }
    
    // Validate steps
    for (let i = 0; i < formData.steps.length; i++) {
      const step = formData.steps[i];
      if (step.is_enabled && !step.message_text.trim()) {
        setError(`שלב ${i + 1}: יש למלא תוכן הודעה`);
        return;
      }
      if (step.delay_value < 1) {
        setError(`שלב ${i + 1}: העיכוב חייב להיות לפחות 1`);
        return;
      }
    }
    
    try {
      setSaving(true);
      setError(null);
      
      // Convert UI data to API format
      const apiData = {
        name: formData.name,
        message_text: '',  // Empty string for backward compatibility
        status_ids: formData.status_ids,
        delay_minutes: 0,  // Set to 0 as it's not used
        delay_seconds: 0,  // Set to 0 as it's not used
        provider: formData.provider,
        is_active: formData.is_active,
        send_immediately_on_enter: formData.send_immediately_on_enter,
        immediate_message: formData.send_immediately_on_enter ? formData.immediate_message : undefined,
        apply_mode: formData.apply_mode,
        steps: convertUIStepsToAPI(formData.steps)
      };
      
      if (rule) {
        await scheduledMessagesApi.updateRule(rule.id, apiData);
      } else {
        await scheduledMessagesApi.createRule(apiData as scheduledMessagesApi.CreateRuleRequest);
      }
      
      onSave();
    } catch (err: any) {
      setError(err.message || 'שגיאה בשמירת החוק');
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center p-4 z-50">
      <Card className="w-full max-w-2xl max-h-[90vh] overflow-y-auto">
        <div className="p-6">
          <h2 className="text-2xl font-bold mb-6">
            {rule ? 'עריכת חוק' : 'חוק חדש'}
          </h2>
          
          {error && (
            <div className="mb-4 p-3 bg-red-50 border border-red-200 rounded text-red-700 text-sm">
              {error}
            </div>
          )}
          
          <form onSubmit={handleSubmit} className="space-y-4">
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-2">
                שם החוק *
              </label>
              <input
                type="text"
                value={formData.name}
                onChange={(e) => setFormData({ ...formData, name: e.target.value })}
                className="w-full px-3 py-2 border border-gray-300 rounded-md"
                placeholder="לדוגמה: הודעת ברוכים הבאים"
              />
            </div>
            
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-2">
                סטטוסים *
              </label>
              <div className="space-y-2 max-h-48 overflow-y-auto border border-gray-200 rounded-md p-3">
                {(statuses || []).map((status) => (
                  <label key={status.id} className="flex items-center gap-2">
                    <input
                      type="checkbox"
                      checked={formData.status_ids.includes(status.id)}
                      onChange={(e) => {
                        if (e.target.checked) {
                          setFormData({
                            ...formData,
                            status_ids: [...formData.status_ids, status.id]
                          });
                        } else {
                          setFormData({
                            ...formData,
                            status_ids: formData.status_ids.filter(id => id !== status.id)
                          });
                        }
                      }}
                      className="rounded"
                    />
                    <span className="text-sm">{status.label}</span>
                  </label>
                ))}
              </div>
            </div>
            
            {/* Send Immediately Section */}
            <div className="border-t pt-4">
              <div className="flex items-center gap-2 mb-4">
                <input
                  type="checkbox"
                  checked={formData.send_immediately_on_enter}
                  onChange={(e) => setFormData({ 
                    ...formData, 
                    send_immediately_on_enter: e.target.checked,
                    immediate_message: e.target.checked ? formData.immediate_message : ''
                  })}
                  className="rounded"
                />
                <label className="text-sm font-medium text-gray-700 flex items-center gap-2">
                  <Zap className="w-4 h-4 text-yellow-500" />
                  שלח מיד בעת כניסה לסטטוס
                </label>
              </div>
              
              {formData.send_immediately_on_enter && (
                <div className="mr-6">
                  <label className="block text-sm font-medium text-gray-700 mb-2">
                    הודעה מיידית *
                  </label>
                  <textarea
                    value={formData.immediate_message}
                    onChange={(e) => setFormData({ ...formData, immediate_message: e.target.value })}
                    rows={3}
                    className="w-full px-3 py-2 border border-gray-300 rounded-md"
                    placeholder="הודעה שתישלח מיד כאשר הליד נכנס לסטטוס..."
                  />
                  <p className="text-xs text-gray-500 mt-1">
                    משתנים זמינים: {'{lead_name}'}, {'{phone}'}, {'{business_name}'}, {'{status}'}
                  </p>
                </div>
              )}
            </div>
            
            {/* Apply Mode */}
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-2">
                אופן החלה *
              </label>
              <select
                value={formData.apply_mode}
                onChange={(e) => setFormData({ ...formData, apply_mode: e.target.value })}
                className="w-full px-3 py-2 border border-gray-300 rounded-md bg-white"
              >
                <option value="ON_ENTER_ONLY">רק בכניסה לסטטוס</option>
                <option value="WHILE_IN_STATUS">כל עוד בסטטוס</option>
              </select>
              <p className="text-xs text-gray-500 mt-1">
                {formData.apply_mode === 'ON_ENTER_ONLY' 
                  ? 'ההודעות יישלחו רק כאשר הליד נכנס לסטטוס' 
                  : 'ההודעות יישלחו כל עוד הליד נמצא בסטטוס'}
              </p>
            </div>
            
            {/* Multi-Step Messages */}
            <div className="border-t pt-4">
              <div className="flex items-center justify-between mb-4">
                <div>
                  <label className="text-sm font-medium text-gray-700 flex items-center gap-2">
                    <List className="w-4 h-4" />
                    שלבי הודעות מתוזמנות
                  </label>
                  <p className="text-xs text-gray-500 mt-1">
                    הודעות נוספות שיישלחו בהפרשי זמן שונים אחרי ההודעה הקודמת
                  </p>
                </div>
                <Button
                  type="button"
                  size="sm"
                  variant="outline"
                  onClick={() => {
                    const newStep = {
                      step_index: formData.steps.length + 1,  // 1-based indexing for API
                      message_text: '',
                      delay_value: 15,
                      delay_unit: 'minutes' as const,
                      is_enabled: true
                    };
                    setFormData({ ...formData, steps: [...formData.steps, newStep] });
                  }}
                >
                  <Plus className="w-4 h-4 ml-1" />
                  הוסף הודעה
                </Button>
              </div>
              
              {formData.steps.length === 0 ? (
                <div className="text-center py-8 text-gray-500 text-sm border-2 border-dashed border-gray-200 rounded-lg">
                  אין שלבים. לחץ על "הוסף הודעה" כדי להוסיף שלב ראשון
                </div>
              ) : (
                <div className="space-y-4">
                  {formData.steps.map((step, index) => (
                    <div key={index} className="border border-gray-200 rounded-lg p-4 bg-gray-50">
                      <div className="flex items-start gap-3">
                        <GripVertical className="w-5 h-5 text-gray-400 mt-2 cursor-move" />
                        
                        <div className="flex-1 space-y-3">
                          <div className="flex items-center justify-between">
                            <span className="text-sm font-medium text-gray-700">
                              הודעה #{index + 1}
                            </span>
                            <div className="flex items-center gap-2">
                              <label className="flex items-center gap-1 text-xs text-gray-600">
                                <input
                                  type="checkbox"
                                  checked={step.is_enabled}
                                  onChange={(e) => {
                                    const newSteps = [...formData.steps];
                                    newSteps[index].is_enabled = e.target.checked;
                                    setFormData({ ...formData, steps: newSteps });
                                  }}
                                  className="rounded"
                                />
                                פעיל
                              </label>
                              <button
                                type="button"
                                onClick={() => {
                                  const newSteps = formData.steps.filter((_, i) => i !== index);
                                  // Re-index remaining steps (1-based)
                                  newSteps.forEach((s, i) => s.step_index = i + 1);
                                  setFormData({ ...formData, steps: newSteps });
                                }}
                                className="text-red-600 hover:text-red-700"
                              >
                                <X className="w-4 h-4" />
                              </button>
                            </div>
                          </div>
                          
                          <div>
                            <textarea
                              value={step.message_text}
                              onChange={(e) => {
                                const newSteps = [...formData.steps];
                                newSteps[index].message_text = e.target.value;
                                setFormData({ ...formData, steps: newSteps });
                              }}
                              rows={2}
                              className="w-full px-3 py-2 border border-gray-300 rounded-md text-sm"
                              placeholder="תוכן ההודעה..."
                            />
                          </div>
                          
                          <div className="flex items-center gap-2">
                            <label className="text-xs text-gray-600">עיכוב מהודעה קודמת:</label>
                            <input
                              type="number"
                              min="1"
                              value={step.delay_value}
                              onChange={(e) => {
                                const newSteps = [...formData.steps];
                                newSteps[index].delay_value = parseInt(e.target.value) || 1;
                                setFormData({ ...formData, steps: newSteps });
                              }}
                              className="w-20 px-2 py-1 border border-gray-300 rounded-md text-sm"
                            />
                            <select
                              value={step.delay_unit}
                              onChange={(e) => {
                                const newSteps = [...formData.steps];
                                newSteps[index].delay_unit = e.target.value as 'minutes' | 'hours' | 'days';
                                setFormData({ ...formData, steps: newSteps });
                              }}
                              className="px-2 py-1 border border-gray-300 rounded-md text-sm bg-white"
                            >
                              <option value="minutes">דקות</option>
                              <option value="hours">שעות</option>
                              <option value="days">ימים</option>
                            </select>
                            <span className="text-xs text-gray-500">
                              (זמן המתנה: {getDelayInMinutes(step.delay_value, step.delay_unit)} דקות)
                            </span>
                          </div>
                        </div>
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </div>
            
            <div className="flex items-center gap-2">
              <input
                type="checkbox"
                checked={formData.is_active}
                onChange={(e) => setFormData({ ...formData, is_active: e.target.checked })}
                className="rounded"
              />
              <label className="text-sm font-medium text-gray-700">
                הפעל את החוק
              </label>
            </div>
            
            <div className="flex gap-3 justify-end pt-4">
              <Button type="button" variant="outline" onClick={onClose} disabled={saving}>
                ביטול
              </Button>
              <Button type="submit" disabled={saving}>
                {saving ? 'שומר...' : 'שמור'}
              </Button>
            </div>
          </form>
        </div>
      </Card>
    </div>
  );
}

// Queue View Modal Component
function QueueViewModal({
  ruleId,
  onClose
}: {
  ruleId: number;
  onClose: () => void;
}) {
  const [queue, setQueue] = useState<scheduledMessagesApi.QueueMessage[]>([]);
  const [stats, setStats] = useState<scheduledMessagesApi.StatsResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [statusFilter, setStatusFilter] = useState<string>('');

  useEffect(() => {
    loadQueue();
    loadStats();
  }, [ruleId, statusFilter]);

  const loadQueue = async () => {
    try {
      setLoading(true);
      const data = await scheduledMessagesApi.getQueue({
        rule_id: ruleId,
        status: statusFilter || undefined,
        per_page: 50
      });
      setQueue(data.items);
    } catch (err) {
      console.error('Error loading queue:', err);
    } finally {
      setLoading(false);
    }
  };

  const loadStats = async () => {
    try {
      const data = await scheduledMessagesApi.getStats(ruleId);
      setStats(data);
    } catch (err) {
      console.error('Error loading stats:', err);
    }
  };

  return (
    <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center p-4 z-50">
      <Card className="w-full max-w-6xl max-h-[90vh] overflow-y-auto">
        <div className="p-6">
          <div className="flex items-center justify-between mb-6">
            <h2 className="text-2xl font-bold">תור הודעות</h2>
            <Button variant="ghost" onClick={onClose}>
              <XCircle className="w-5 h-5" />
            </Button>
          </div>
          
          {/* Stats */}
          {stats && (
            <div className="grid grid-cols-4 gap-4 mb-6">
              <Card className="p-4">
                <div className="text-sm text-gray-500">ממתינות</div>
                <div className="text-2xl font-bold text-blue-600">{stats.pending}</div>
              </Card>
              <Card className="p-4">
                <div className="text-sm text-gray-500">נשלחו</div>
                <div className="text-2xl font-bold text-green-600">{stats.sent}</div>
              </Card>
              <Card className="p-4">
                <div className="text-sm text-gray-500">נכשלו</div>
                <div className="text-2xl font-bold text-red-600">{stats.failed}</div>
              </Card>
              <Card className="p-4">
                <div className="text-sm text-gray-500">בוטלו</div>
                <div className="text-2xl font-bold text-gray-600">{stats.canceled}</div>
              </Card>
            </div>
          )}
          
          {/* Filter */}
          <div className="mb-4">
            <select
              value={statusFilter}
              onChange={(e) => setStatusFilter(e.target.value)}
              className="px-3 py-2 border border-gray-300 rounded-md"
            >
              <option value="">כל הסטטוסים</option>
              <option value="pending">ממתינות</option>
              <option value="sent">נשלחו</option>
              <option value="failed">נכשלו</option>
              <option value="canceled">בוטלו</option>
            </select>
          </div>
          
          {/* Queue Table */}
          {loading ? (
            <div className="text-center py-8 text-gray-500">טוען...</div>
          ) : queue.length === 0 ? (
            <div className="text-center py-8 text-gray-500">אין הודעות להצגה</div>
          ) : (
            <div className="overflow-x-auto">
              <table className="min-w-full divide-y divide-gray-200">
                <thead className="bg-gray-50">
                  <tr>
                    <th className="px-4 py-3 text-right text-xs font-medium text-gray-500 uppercase">
                      ליד
                    </th>
                    <th className="px-4 py-3 text-right text-xs font-medium text-gray-500 uppercase">
                      מתוזמן ל
                    </th>
                    <th className="px-4 py-3 text-right text-xs font-medium text-gray-500 uppercase">
                      סטטוס
                    </th>
                    <th className="px-4 py-3 text-right text-xs font-medium text-gray-500 uppercase">
                      הודעה
                    </th>
                  </tr>
                </thead>
                <tbody className="bg-white divide-y divide-gray-200">
                  {queue.map((item) => (
                    <tr key={item.id} className="hover:bg-gray-50">
                      <td className="px-4 py-3 text-sm">
                        {item.lead_name || `ליד #${item.lead_id}`}
                      </td>
                      <td className="px-4 py-3 text-sm whitespace-nowrap">
                        {new Date(item.scheduled_for).toLocaleString('he-IL')}
                      </td>
                      <td className="px-4 py-3">
                        {item.status === 'pending' && <Badge variant="warning">ממתין</Badge>}
                        {item.status === 'sent' && <Badge variant="success">נשלח</Badge>}
                        {item.status === 'failed' && <Badge variant="destructive">נכשל</Badge>}
                        {item.status === 'canceled' && <Badge variant="secondary">בוטל</Badge>}
                      </td>
                      <td className="px-4 py-3 text-sm truncate max-w-xs">
                        {item.message_text}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>
      </Card>
    </div>
  );
}
