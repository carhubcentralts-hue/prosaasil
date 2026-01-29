import React, { useState, useEffect } from 'react';
import { Clock, Plus, Play, Pause, Trash2, Edit2, Eye, CheckCircle, XCircle, AlertCircle, Calendar } from 'lucide-react';
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
      const [rulesData, statusesData] = await Promise.all([
        scheduledMessagesApi.getRules(),
        http.get('/api/statuses').then(r => r.data.items || [])
      ]);
      setRules(rulesData);
      setStatuses(statusesData);
      setError(null);
    } catch (err: any) {
      setError(err.message || 'Failed to load data');
      console.error('Error loading data:', err);
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
                    עיכוב (דקות)
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
                {rules.length === 0 ? (
                  <tr>
                    <td colSpan={5} className="px-6 py-12 text-center text-gray-500">
                      <Clock className="w-12 h-12 mx-auto mb-4 text-gray-300" />
                      <p className="text-lg font-medium mb-2">אין חוקי תזמון</p>
                      <p className="text-sm">צור חוק חדש כדי להתחיל לשלוח הודעות מתוזמנות</p>
                    </td>
                  </tr>
                ) : (
                  rules.map((rule) => (
                    <tr key={rule.id} className="hover:bg-gray-50">
                      <td className="px-6 py-4 whitespace-nowrap">
                        <div className="text-sm font-medium text-gray-900">{rule.name}</div>
                        <div className="text-xs text-gray-500 mt-1 truncate max-w-xs">
                          {rule.message_text}
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
                        {rule.delay_minutes} דקות
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
  onClose,
  onSave
}: {
  rule: scheduledMessagesApi.ScheduledRule | null;
  statuses: LeadStatus[];
  onClose: () => void;
  onSave: () => void;
}) {
  const [formData, setFormData] = useState({
    name: rule?.name || '',
    message_text: rule?.message_text || '',
    status_ids: rule?.statuses.map(s => s.id) || [],
    delay_minutes: rule?.delay_minutes || 15,
    is_active: rule?.is_active ?? true
  });
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    
    if (!formData.name.trim()) {
      setError('שם החוק הוא שדה חובה');
      return;
    }
    
    if (!formData.message_text.trim()) {
      setError('תוכן ההודעה הוא שדה חובה');
      return;
    }
    
    if (formData.status_ids.length === 0) {
      setError('יש לבחור לפחות סטטוס אחד');
      return;
    }
    
    if (formData.delay_minutes < 1 || formData.delay_minutes > 43200) {
      setError('העיכוב חייב להיות בין 1 ל-43200 דקות (30 יום)');
      return;
    }
    
    try {
      setSaving(true);
      setError(null);
      
      if (rule) {
        await scheduledMessagesApi.updateRule(rule.id, formData);
      } else {
        await scheduledMessagesApi.createRule(formData as scheduledMessagesApi.CreateRuleRequest);
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
                {statuses.map((status) => (
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
            
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-2">
                תוכן ההודעה *
              </label>
              <textarea
                value={formData.message_text}
                onChange={(e) => setFormData({ ...formData, message_text: e.target.value })}
                rows={4}
                className="w-full px-3 py-2 border border-gray-300 rounded-md"
                placeholder="הודעת WhatsApp שתישלח ללקוח..."
              />
            </div>
            
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-2">
                עיכוב בדקות * (1-43200)
              </label>
              <input
                type="number"
                min="1"
                max="43200"
                value={formData.delay_minutes}
                onChange={(e) => setFormData({ ...formData, delay_minutes: parseInt(e.target.value) || 1 })}
                className="w-full px-3 py-2 border border-gray-300 rounded-md"
              />
              <p className="text-xs text-gray-500 mt-1">
                ההודעה תישלח {formData.delay_minutes} דקות אחרי מעבר לסטטוס
              </p>
            </div>
            
            <div className="flex items-center gap-2">
              <input
                type="checkbox"
                checked={formData.is_active}
                onChange={(e) => setFormData({ ...formData, is_active: e.target.checked })}
                className="rounded"
              />
              <label className="text-sm font-medium text-gray-700">
                הפעל את החוק מיד
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
