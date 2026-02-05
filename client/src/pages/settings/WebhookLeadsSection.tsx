import React, { useState } from 'react';
import { useQuery, useMutation } from '@tanstack/react-query';
import { queryClient, apiRequest } from '@/lib/queryClient';
import { Copy, RefreshCw, Trash2, Plus, Power, PowerOff, CheckCircle2, Link2 } from 'lucide-react';

interface LeadWebhook {
  id: number;
  name: string;
  secret: string;
  status_id: number;
  status_name: string;
  is_active: boolean;
  created_at: string;
}

interface StatusOption {
  id: number;
  label: string;
  name: string;
}

const WEBHOOK_LIMIT = 3;

// Simple UI Components matching SettingsPage style
const Card = ({ children, className = "" }: any) => (
  <div className={`border border-gray-200 rounded-lg bg-white ${className}`}>{children}</div>
);

const Button = ({ children, className = "", variant = "default", size = "default", ...props }: {
  children: React.ReactNode;
  className?: string;
  variant?: "default" | "outline" | "ghost" | "destructive";
  size?: "default" | "sm";
  [key: string]: any;
}) => {
  const baseClasses = "px-4 py-2 rounded-md font-medium transition-colors inline-flex items-center";
  const variantClasses = {
    default: "bg-blue-600 text-white hover:bg-blue-700",
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
      {...props}
    >
      {children}
    </button>
  );
};

const Badge = ({ children, className = "", variant = "default" }: {
  children: React.ReactNode;
  className?: string;
  variant?: "default" | "success" | "warning" | "destructive";
}) => {
  const variantClasses = {
    default: "bg-gray-100 text-gray-800",
    success: "bg-green-100 text-green-800",
    warning: "bg-yellow-100 text-yellow-800",
    destructive: "bg-red-100 text-red-800"
  };
  return (
    <span className={`px-2 py-1 text-xs rounded-full ${variantClasses[variant]} ${className}`}>
      {children}
    </span>
  );
};

export function WebhookLeadsSection() {
  const [creatingNew, setCreatingNew] = useState(false);
  const [editingId, setEditingId] = useState<number | null>(null);
  const [formData, setFormData] = useState({ name: '', status_id: 0 });
  const [copiedItem, setCopiedItem] = useState<string | null>(null);

  // Fetch webhooks
  const { data: webhooks = [], isLoading: loadingWebhooks } = useQuery<LeadWebhook[]>({
    queryKey: ['lead-webhooks'],
    queryFn: async () => {
      const response = await apiRequest('/leads/webhooks', { method: 'GET' });
      return response;
    }
  });

  // Fetch statuses
  const { data: statuses = [] } = useQuery<StatusOption[]>({
    queryKey: ['lead-statuses'],
    queryFn: async () => {
      const response = await apiRequest('/crm/statuses', { method: 'GET' });
      return response;
    }
  });

  // Create webhook mutation
  const createMutation = useMutation({
    mutationFn: async (data: { name: string; status_id: number }) => {
      return await apiRequest('/leads/webhooks', {
        method: 'POST',
        body: JSON.stringify(data)
      });
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['lead-webhooks'] });
      setCreatingNew(false);
      setFormData({ name: '', status_id: 0 });
    }
  });

  // Update webhook mutation
  const updateMutation = useMutation({
    mutationFn: async ({ id, data }: { id: number; data: any }) => {
      return await apiRequest(`/leads/webhooks/${id}`, {
        method: 'PATCH',
        body: JSON.stringify(data)
      });
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['lead-webhooks'] });
      setEditingId(null);
    }
  });

  // Delete webhook mutation
  const deleteMutation = useMutation({
    mutationFn: async (id: number) => {
      return await apiRequest(`/leads/webhooks/${id}`, { method: 'DELETE' });
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['lead-webhooks'] });
    }
  });

  const handleCopyToClipboard = async (text: string, itemKey: string) => {
    try {
      await navigator.clipboard.writeText(text);
      setCopiedItem(itemKey);
      setTimeout(() => setCopiedItem(null), 2000);
    } catch (err) {
      console.error('Copy failed:', err);
    }
  };

  const handleToggleActive = (webhook: LeadWebhook) => {
    updateMutation.mutate({
      id: webhook.id,
      data: { is_active: !webhook.is_active }
    });
  };

  const handleRegenerateSecret = (webhookId: number) => {
    if (confirm('האם לייצר secret חדש? ה-URL הישן יפסיק לעבוד.')) {
      updateMutation.mutate({
        id: webhookId,
        data: { regenerate_secret: true }
      });
    }
  };

  const handleDelete = (webhookId: number) => {
    if (confirm('האם למחוק webhook זה? פעולה זו בלתי הפיכה.')) {
      deleteMutation.mutate(webhookId);
    }
  };

  const handleCreateSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (!formData.name.trim() || !formData.status_id) return;
    createMutation.mutate(formData);
  };

  const canAddMore = webhooks.length < WEBHOOK_LIMIT;
  const baseUrl = window.location.origin;

  return (
    <Card className="p-6">
      <div className="flex items-center gap-3 mb-4">
        <Link2 className="w-6 h-6 text-purple-600" />
        <h3 className="text-lg font-semibold text-gray-900">Webhooks ללידים</h3>
        <Badge variant={webhooks.length > 0 ? 'success' : 'default'}>
          {webhooks.length}/{WEBHOOK_LIMIT}
        </Badge>
      </div>
      
      <p className="text-sm text-gray-600 mb-6">
        קבלת לידים מ-Make, Zapier ומקורות חיצוניים אחרים. כל webhook יוצר לידים בסטטוס שתבחר.
      </p>

      {/* Create form */}
      {creatingNew && (
        <div className="border border-blue-200 bg-blue-50 rounded-lg p-6">
          <h4 className="font-semibold text-gray-900 mb-4">Webhook חדש</h4>
          <form onSubmit={handleCreateSubmit} className="space-y-4">
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-2">
                שם תיאורי
              </label>
              <input
                type="text"
                value={formData.name}
                onChange={(e) => setFormData({ ...formData, name: e.target.value })}
                placeholder='לדוגמה: "מקור Make 1" או "טופס Facebook"'
                className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent"
                required
              />
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-2">
                סטטוס יעד ללידים
              </label>
              <select
                value={formData.status_id}
                onChange={(e) => setFormData({ ...formData, status_id: parseInt(e.target.value) })}
                className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent"
                required
              >
                <option value={0}>-- בחר סטטוס --</option>
                {statuses.map((status) => (
                  <option key={status.id} value={status.id}>
                    {status.label}
                  </option>
                ))}
              </select>
            </div>
            <div className="flex gap-3">
              <button
                type="submit"
                disabled={createMutation.isPending}
                className="px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 disabled:opacity-50"
              >
                {createMutation.isPending ? 'יוצר...' : 'צור'}
              </button>
              <button
                type="button"
                onClick={() => {
                  setCreatingNew(false);
                  setFormData({ name: '', status_id: 0 });
                }}
                className="px-4 py-2 border border-gray-300 text-gray-700 rounded-lg hover:bg-gray-50"
              >
                ביטול
              </button>
            </div>
          </form>
        </div>
      )}

      {/* Webhooks list or empty state */}
      {loadingWebhooks ? (
        <div className="text-center py-4 text-gray-500">טוען...</div>
      ) : webhooks.length === 0 ? (
        <div className="text-center py-6">
          <p className="text-gray-600 mb-4">אין webhooks עדיין. צור את הראשון כדי להתחיל לקבל לידים.</p>
          {!creatingNew && (
            <Button onClick={() => setCreatingNew(true)}>
              <Plus className="w-4 h-4 mr-2" />
              צור Webhook ראשון
            </Button>
          )}
        </div>
      ) : (
        <>
          {canAddMore && !creatingNew && (
            <div className="mb-4">
              <Button variant="outline" onClick={() => setCreatingNew(true)} className="w-full justify-center">
                <Plus className="w-4 h-4 mr-2" />
                הוסף Webhook ({webhooks.length}/{WEBHOOK_LIMIT})
              </Button>
            </div>
          )}
          
          <div className="space-y-4">{webhooks.map((webhook) => (
            <div
              key={webhook.id}
              className={`border rounded-lg p-6 ${
                webhook.is_active ? 'bg-white border-gray-200' : 'bg-gray-50 border-gray-300'
              }`}
            >
              {/* Header row */}
              <div className="flex items-start justify-between mb-4">
                <div className="flex items-center gap-3">
                  <h4 className="text-lg font-semibold text-gray-900">{webhook.name}</h4>
                  {webhook.is_active ? (
                    <span className="inline-flex items-center gap-1 px-2 py-1 bg-green-100 text-green-800 text-xs rounded-full">
                      <Power className="w-3 h-3" />
                      פעיל
                    </span>
                  ) : (
                    <span className="inline-flex items-center gap-1 px-2 py-1 bg-gray-200 text-gray-600 text-xs rounded-full">
                      <PowerOff className="w-3 h-3" />
                      כבוי
                    </span>
                  )}
                </div>
                <div className="flex gap-2">
                  <button
                    onClick={() => handleToggleActive(webhook)}
                    className="p-2 text-gray-600 hover:bg-gray-100 rounded-lg transition-colors"
                    title={webhook.is_active ? 'השבת' : 'הפעל'}
                  >
                    {webhook.is_active ? <PowerOff className="w-4 h-4" /> : <Power className="w-4 h-4" />}
                  </button>
                  <button
                    onClick={() => handleDelete(webhook.id)}
                    className="p-2 text-red-600 hover:bg-red-50 rounded-lg transition-colors"
                    title="מחק"
                  >
                    <Trash2 className="w-4 h-4" />
                  </button>
                </div>
              </div>

              {/* Details grid */}
              <div className="space-y-3">
                {/* Webhook URL */}
                <div>
                  <label className="block text-xs font-medium text-gray-500 mb-1">
                    Webhook URL
                  </label>
                  <div className="flex gap-2">
                    <input
                      type="text"
                      readOnly
                      value={`${baseUrl}/api/webhooks/leads/${webhook.id}`}
                      className="flex-1 px-3 py-2 bg-gray-50 border border-gray-200 rounded-lg text-sm font-mono"
                      dir="ltr"
                    />
                    <button
                      onClick={() =>
                        handleCopyToClipboard(
                          `${baseUrl}/api/webhooks/leads/${webhook.id}`,
                          `url-${webhook.id}`
                        )
                      }
                      className="px-3 py-2 border border-gray-300 rounded-lg hover:bg-gray-50 transition-colors"
                      title="העתק URL"
                    >
                      {copiedItem === `url-${webhook.id}` ? (
                        <CheckCircle2 className="w-4 h-4 text-green-600" />
                      ) : (
                        <Copy className="w-4 h-4" />
                      )}
                    </button>
                  </div>
                </div>

                {/* Secret */}
                <div>
                  <label className="block text-xs font-medium text-gray-500 mb-1">
                    Secret (Header: X-Webhook-Secret)
                  </label>
                  <div className="flex gap-2">
                    <input
                      type="text"
                      readOnly
                      value={webhook.secret}
                      className="flex-1 px-3 py-2 bg-gray-50 border border-gray-200 rounded-lg text-sm font-mono"
                      dir="ltr"
                    />
                    <button
                      onClick={() => handleCopyToClipboard(webhook.secret, `secret-${webhook.id}`)}
                      className="px-3 py-2 border border-gray-300 rounded-lg hover:bg-gray-50 transition-colors"
                      title="העתק Secret"
                    >
                      {copiedItem === `secret-${webhook.id}` ? (
                        <CheckCircle2 className="w-4 h-4 text-green-600" />
                      ) : (
                        <Copy className="w-4 h-4" />
                      )}
                    </button>
                    <button
                      onClick={() => handleRegenerateSecret(webhook.id)}
                      className="px-3 py-2 border border-gray-300 rounded-lg hover:bg-gray-50 transition-colors"
                      title="צור Secret חדש"
                    >
                      <RefreshCw className="w-4 h-4" />
                    </button>
                  </div>
                </div>

                {/* Target status */}
                <div>
                  <label className="block text-xs font-medium text-gray-500 mb-1">
                    סטטוס יעד ללידים חדשים
                  </label>
                  {editingId === webhook.id ? (
                    <div className="flex gap-2">
                      <select
                        defaultValue={webhook.status_id}
                        className="flex-1 px-3 py-2 border border-gray-300 rounded-lg"
                        onChange={(e) => {
                          updateMutation.mutate({
                            id: webhook.id,
                            data: { status_id: parseInt(e.target.value) }
                          });
                        }}
                      >
                        {statuses.map((status) => (
                          <option key={status.id} value={status.id}>
                            {status.label}
                          </option>
                        ))}
                      </select>
                      <button
                        onClick={() => setEditingId(null)}
                        className="px-3 py-2 border border-gray-300 rounded-lg hover:bg-gray-50"
                      >
                        סגור
                      </button>
                    </div>
                  ) : (
                    <div className="flex gap-2">
                      <div className="flex-1 px-3 py-2 bg-gray-50 border border-gray-200 rounded-lg text-sm">
                        {webhook.status_name}
                      </div>
                      <button
                        onClick={() => setEditingId(webhook.id)}
                        className="px-3 py-2 border border-gray-300 rounded-lg hover:bg-gray-50"
                      >
                        שנה
                      </button>
                    </div>
                  )}
                </div>
              </div>
            </div>
          ))}
          </div>
        </>
      )}

      {/* Usage instructions */}
      {webhooks.length > 0 && (
        <div className="mt-6 p-4 bg-purple-50 rounded-lg border border-purple-200">
          <h4 className="font-semibold text-purple-900 mb-3">💡 איך להשתמש:</h4>
          <ol className="space-y-2 text-sm text-purple-800">
            <li className="flex gap-2">
              <span className="font-semibold">1.</span>
              <span>העתק את ה-URL וה-Secret מהלמעלה</span>
            </li>
            <li className="flex gap-2">
              <span className="font-semibold">2.</span>
              <span>הגדר ב-Make/Zapier: HTTP Request עם Method POST</span>
            </li>
            <li className="flex gap-2">
              <span className="font-semibold">3.</span>
              <span>הוסף Header: <code className="px-1 py-0.5 bg-white rounded font-mono text-xs">X-Webhook-Secret</code> עם ערך ה-Secret</span>
            </li>
            <li className="flex gap-2">
              <span className="font-semibold">4.</span>
              <span>שלח JSON עם: name, phone, email (לפחות אחד מ-phone/email נדרש)</span>
            </li>
            <li className="flex gap-2">
              <span className="font-semibold">5.</span>
              <span>הליד ייווצר אוטומטית בסטטוס שבחרת ✨</span>
            </li>
          </ol>
        </div>
      )}
    </Card>
  );
}
