import React, { useState, useEffect } from 'react';
import { Send, Users, MessageSquare, Filter, Upload, RefreshCw, CheckCircle, XCircle, Clock, AlertTriangle } from 'lucide-react';
import { http } from '../../services/http';

// UI Components
const Card = ({ children, className = "" }: { children: React.ReactNode; className?: string }) => (
  <div className={`border border-gray-200 rounded-lg bg-white shadow-sm ${className}`}>{children}</div>
);

const Button = ({ children, className = "", variant = "default", size = "default", disabled = false, ...props }: {
  children: React.ReactNode;
  className?: string;
  variant?: "default" | "outline" | "ghost" | "destructive" | "success";
  size?: "default" | "sm" | "lg";
  disabled?: boolean;
  [key: string]: any;
}) => {
  const baseClasses = "px-4 py-2 rounded-md font-medium transition-colors disabled:opacity-50 disabled:cursor-not-allowed inline-flex items-center justify-center";
  const variantClasses = {
    default: "bg-blue-600 text-white hover:bg-blue-700",
    success: "bg-green-600 text-white hover:bg-green-700",
    outline: "border border-gray-300 bg-white text-gray-700 hover:bg-gray-50",
    ghost: "text-gray-700 hover:bg-gray-100",
    destructive: "bg-red-600 text-white hover:bg-red-700"
  };
  const sizeClasses = {
    default: "px-4 py-2",
    sm: "px-3 py-1.5 text-sm",
    lg: "px-6 py-3 text-lg"
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
  variant?: "default" | "success" | "warning" | "destructive" | "info";
}) => {
  const variantClasses = {
    default: "bg-gray-100 text-gray-800",
    success: "bg-green-100 text-green-800",
    warning: "bg-yellow-100 text-yellow-800",
    destructive: "bg-red-100 text-red-800",
    info: "bg-blue-100 text-blue-800"
  };
  return (
    <span className={`px-2 py-1 text-xs rounded-full ${variantClasses[variant]} ${className}`}>
      {children}
    </span>
  );
};

interface Template {
  id: string;
  name: string;
  status: 'APPROVED' | 'PENDING' | 'REJECTED';
  language: string;
  category: string;
  components?: any[];
}

interface BroadcastCampaign {
  id: number;
  name: string;
  provider: 'meta' | 'baileys';
  template_id?: string;
  message_text?: string;
  total_recipients: number;
  sent_count: number;
  failed_count: number;
  status: 'pending' | 'running' | 'completed' | 'failed' | 'paused';
  created_at: string;
  created_by: string;
}

export function WhatsAppBroadcastPage() {
  const [activeTab, setActiveTab] = useState<'send' | 'history' | 'templates'>('send');
  
  // Template state
  const [templates, setTemplates] = useState<Template[]>([]);
  const [loadingTemplates, setLoadingTemplates] = useState(false);
  const [selectedTemplate, setSelectedTemplate] = useState<Template | null>(null);
  
  // Broadcast state
  const [messageType, setMessageType] = useState<'template' | 'freetext'>('template');
  const [provider, setProvider] = useState<'meta' | 'baileys'>('meta');
  const [messageText, setMessageText] = useState('');
  const [selectedStatuses, setSelectedStatuses] = useState<string[]>([]);
  const [csvFile, setCsvFile] = useState<File | null>(null);
  const [sending, setSending] = useState(false);
  
  // NEW: Audience source selection
  const [audienceSource, setAudienceSource] = useState<'leads' | 'import-list' | 'csv'>('leads');
  const [selectedLeadIds, setSelectedLeadIds] = useState<number[]>([]);
  const [selectedImportListId, setSelectedImportListId] = useState<number | null>(null);
  const [importLists, setImportLists] = useState<Array<{id: number; name: string; current_leads: number}>>([]);
  const [loadingImportLists, setLoadingImportLists] = useState(false);
  
  // NEW: Lead selection with search/filters
  const [leadSearchTerm, setLeadSearchTerm] = useState('');
  const [leads, setLeads] = useState<Array<{id: number; name: string; phone: string; status: string}>>([]);
  const [loadingLeads, setLoadingLeads] = useState(false);
  const [recipientCount, setRecipientCount] = useState(0);
  
  // Campaign history
  const [campaigns, setCampaigns] = useState<BroadcastCampaign[]>([]);
  const [loadingCampaigns, setLoadingCampaigns] = useState(false);
  
  // Status options from CRM
  const [availableStatuses, setAvailableStatuses] = useState<string[]>([]);

  useEffect(() => {
    loadTemplates();
    loadCampaigns();
    loadStatuses();
    loadImportLists();
  }, []);

  const loadTemplates = async () => {
    try {
      setLoadingTemplates(true);
      const response = await http.get<{ templates: Template[] }>('/api/whatsapp/templates');
      setTemplates(response.templates || []);
    } catch (error) {
      console.error('Error loading templates:', error);
    } finally {
      setLoadingTemplates(false);
    }
  };

  const loadCampaigns = async () => {
    try {
      setLoadingCampaigns(true);
      const response = await http.get<{ campaigns: BroadcastCampaign[] }>('/api/whatsapp/broadcasts');
      setCampaigns(response.campaigns || []);
    } catch (error) {
      console.error('Error loading campaigns:', error);
    } finally {
      setLoadingCampaigns(false);
    }
  };

  const loadStatuses = async () => {
    try {
      const response = await http.get<{ items: Array<{ name: string; label: string }> }>('/api/statuses');
      // Use items array from the response (standard format)
      const statusList = response.items || [];
      setAvailableStatuses(statusList.map(s => s.name));
    } catch (error) {
      console.error('Error loading statuses:', error);
      // Fallback to common statuses
      setAvailableStatuses(['new', 'contacted', 'qualified', 'won']);
    }
  };

  // NEW: Load import lists
  const loadImportLists = async () => {
    try {
      setLoadingImportLists(true);
      const response = await http.get<{ lists: Array<{id: number; name: string; current_leads: number}> }>('/api/outbound/import-lists');
      setImportLists(response.lists || []);
    } catch (error) {
      console.error('Error loading import lists:', error);
      setImportLists([]);
    } finally {
      setLoadingImportLists(false);
    }
  };

  // NEW: Load leads with filters
  const loadLeads = async () => {
    try {
      setLoadingLeads(true);
      
      // Build query parameters properly
      const params = new URLSearchParams();
      params.append('page', '1');
      params.append('pageSize', '1000'); // Get all leads
      
      if (selectedStatuses.length > 0) {
        // Add each status as a separate parameter
        selectedStatuses.forEach(status => {
          params.append('status', status);
        });
      }
      if (leadSearchTerm.trim()) {
        params.append('q', leadSearchTerm.trim());
      }
      
      const queryString = params.toString();
      const url = `/api/leads${queryString ? `?${queryString}` : ''}`;
      
      const response = await http.get<{ leads: Array<{id: number; name: string; phone_e164: string; status: string}> }>(url);
      const loadedLeads = response.leads || [];
      setLeads(loadedLeads.map(l => ({ id: l.id, name: l.name, phone: l.phone_e164, status: l.status })));
      
      // Calculate recipient count based on audience source
      updateRecipientCount(loadedLeads.length);
    } catch (error) {
      console.error('Error loading leads:', error);
      setLeads([]);
    } finally {
      setLoadingLeads(false);
    }
  };

  // NEW: Update recipient count based on audience source
  const updateRecipientCount = (count?: number) => {
    if (audienceSource === 'leads') {
      setRecipientCount(selectedLeadIds.length || count || 0);
    } else if (audienceSource === 'import-list' && selectedImportListId) {
      const list = importLists.find(l => l.id === selectedImportListId);
      setRecipientCount(list?.current_leads || 0);
    } else if (audienceSource === 'csv' && csvFile) {
      // CSV count would need parsing, for now show as 1
      setRecipientCount(1);
    } else {
      setRecipientCount(0);
    }
  };

  // Load leads when filters change
  useEffect(() => {
    if (audienceSource === 'leads') {
      loadLeads();
    }
  }, [selectedStatuses, leadSearchTerm, audienceSource]);

  // Update recipient count when selection changes
  useEffect(() => {
    updateRecipientCount();
  }, [selectedLeadIds, selectedImportListId, csvFile, audienceSource, importLists]);

  const handleSendBroadcast = async () => {
    if (messageType === 'template' && !selectedTemplate) {
      alert('יש לבחור תבנית');
      return;
    }
    
    if (messageType === 'freetext' && !messageText.trim()) {
      alert('יש להזין הודעה');
      return;
    }
    
    // NEW: Validate audience source
    if (audienceSource === 'leads' && selectedLeadIds.length === 0) {
      alert('יש לבחור לפחות ליד אחד');
      return;
    }
    if (audienceSource === 'import-list' && !selectedImportListId) {
      alert('יש לבחור רשימת ייבוא');
      return;
    }
    if (audienceSource === 'csv' && !csvFile) {
      alert('יש להעלות קובץ CSV');
      return;
    }

    try {
      setSending(true);
      
      const formData = new FormData();
      formData.append('provider', provider);
      formData.append('message_type', messageType);
      formData.append('audience_source', audienceSource);
      
      if (messageType === 'template' && selectedTemplate) {
        formData.append('template_id', selectedTemplate.id);
        formData.append('template_name', selectedTemplate.name);
      } else {
        formData.append('message_text', messageText);
      }
      
      // NEW: Add audience data based on source
      if (audienceSource === 'leads') {
        formData.append('lead_ids', JSON.stringify(selectedLeadIds));
      } else if (audienceSource === 'import-list') {
        formData.append('import_list_id', String(selectedImportListId));
      } else if (audienceSource === 'csv' && csvFile) {
        formData.append('csv_file', csvFile);
      }
      
      // Legacy: Keep status filter for backward compatibility
      if (selectedStatuses.length > 0) {
        formData.append('statuses', JSON.stringify(selectedStatuses));
      }
      
      if (csvFile) {
        formData.append('csv_file', csvFile);
      }
      
      const response = await http.post<{ success: boolean; broadcast_id: number; message?: string }>('/api/whatsapp/broadcasts', formData);
      
      if (response.success) {
        alert(`תפוצה נוצרה בהצלחה! מזהה: ${response.broadcast_id}`);
        // Reset form
        setSelectedTemplate(null);
        setMessageText('');
        setSelectedStatuses([]);
        setCsvFile(null);
        // Switch to history tab
        setActiveTab('history');
        // Reload campaigns
        await loadCampaigns();
      } else {
        alert('שגיאה ביצירת תפוצה: ' + (response.message || 'שגיאה לא ידועה'));
      }
    } catch (error: any) {
      console.error('Error sending broadcast:', error);
      alert('שגיאה בשליחת תפוצה: ' + (error.message || 'שגיאה לא ידועה'));
    } finally {
      setSending(false);
    }
  };

  const toggleStatus = (status: string) => {
    if (selectedStatuses.includes(status)) {
      setSelectedStatuses(selectedStatuses.filter(s => s !== status));
    } else {
      setSelectedStatuses([...selectedStatuses, status]);
    }
  };

  return (
    <div className="space-y-6" dir="rtl">
      {/* Header */}
      <div className="flex justify-between items-center">
        <div>
          <h1 className="text-2xl font-bold text-slate-900">תפוצה WhatsApp</h1>
          <p className="text-slate-600 mt-1">שלח הודעות המוניות ללקוחות באמצעות WhatsApp</p>
        </div>
        <Button variant="outline" onClick={loadCampaigns}>
          <RefreshCw className="h-4 w-4 ml-2" />
          רענן
        </Button>
      </div>

      {/* Tabs */}
      <div className="border-b border-slate-200">
        <nav className="-mb-px flex space-x-reverse space-x-8">
          <button
            onClick={() => setActiveTab('send')}
            className={`py-2 px-1 border-b-2 font-medium text-sm ${
              activeTab === 'send'
                ? 'border-blue-500 text-blue-600'
                : 'border-transparent text-slate-500 hover:text-slate-700 hover:border-slate-300'
            }`}
          >
            <Send className="h-4 w-4 inline ml-2" />
            שליחת תפוצה
          </button>
          <button
            onClick={() => setActiveTab('history')}
            className={`py-2 px-1 border-b-2 font-medium text-sm ${
              activeTab === 'history'
                ? 'border-blue-500 text-blue-600'
                : 'border-transparent text-slate-500 hover:text-slate-700 hover:border-slate-300'
            }`}
          >
            <Clock className="h-4 w-4 inline ml-2" />
            היסטוריה
          </button>
          <button
            onClick={() => setActiveTab('templates')}
            className={`py-2 px-1 border-b-2 font-medium text-sm ${
              activeTab === 'templates'
                ? 'border-blue-500 text-blue-600'
                : 'border-transparent text-slate-500 hover:text-slate-700 hover:border-slate-300'
            }`}
          >
            <MessageSquare className="h-4 w-4 inline ml-2" />
            תבניות
          </button>
        </nav>
      </div>

      {/* Send Broadcast Tab */}
      {activeTab === 'send' && (
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
          {/* Left Column - Configuration */}
          <div className="lg:col-span-2 space-y-6">
            {/* Provider Selection */}
            <Card className="p-6">
              <h2 className="text-lg font-semibold mb-4">ספק שליחה</h2>
              <div className="space-y-3">
                <label className="flex items-center cursor-pointer">
                  <input
                    type="radio"
                    name="provider"
                    value="meta"
                    checked={provider === 'meta'}
                    onChange={() => {
                      setProvider('meta');
                      setMessageType('template');
                    }}
                    className="ml-2"
                  />
                  <div>
                    <div className="font-medium">Meta Cloud API (מומלץ)</div>
                    <div className="text-sm text-slate-500">שימוש בתבניות מאושרות - מוגן מחסימות</div>
                  </div>
                </label>
                <label className="flex items-center cursor-pointer">
                  <input
                    type="radio"
                    name="provider"
                    value="baileys"
                    checked={provider === 'baileys'}
                    onChange={() => setProvider('baileys')}
                    className="ml-2"
                  />
                  <div>
                    <div className="font-medium">Baileys</div>
                    <div className="text-sm text-slate-500">טקסט חופשי - עם throttling</div>
                  </div>
                </label>
              </div>
            </Card>

            {/* Message Type */}
            <Card className="p-6">
              <h2 className="text-lg font-semibold mb-4">סוג הודעה</h2>
              <div className="space-y-3">
                {provider === 'meta' && (
                  <div className="p-3 bg-blue-50 border border-blue-200 rounded-lg">
                    <p className="text-sm text-blue-800">
                      <strong>שים לב:</strong> Meta Cloud API דורש שימוש בתבניות מאושרות בלבד
                    </p>
                  </div>
                )}
                
                <label className="flex items-center cursor-pointer">
                  <input
                    type="radio"
                    name="messageType"
                    value="template"
                    checked={messageType === 'template'}
                    onChange={() => setMessageType('template')}
                    disabled={provider === 'meta'} // Meta always uses templates
                    className="ml-2"
                  />
                  <div>
                    <div className="font-medium">תבנית מאושרת</div>
                    <div className="text-sm text-slate-500">שימוש בתבנית קיימת מ-Meta</div>
                  </div>
                </label>
                
                {provider === 'baileys' && (
                  <label className="flex items-center cursor-pointer">
                    <input
                      type="radio"
                      name="messageType"
                      value="freetext"
                      checked={messageType === 'freetext'}
                      onChange={() => setMessageType('freetext')}
                      className="ml-2"
                    />
                    <div>
                      <div className="font-medium">טקסט חופשי</div>
                      <div className="text-sm text-slate-500">כתוב הודעה בעצמך</div>
                    </div>
                  </label>
                )}
              </div>
              
              {messageType === 'template' ? (
                <div className="mt-4">
                  <label className="block text-sm font-medium mb-2">בחר תבנית</label>
                  <select
                    value={selectedTemplate?.id || ''}
                    onChange={(e) => {
                      const template = templates.find(t => t.id === e.target.value);
                      setSelectedTemplate(template || null);
                    }}
                    className="w-full px-3 py-2 border border-slate-300 rounded-md"
                  >
                    <option value="">-- בחר תבנית --</option>
                    {templates.filter(t => t.status === 'APPROVED').map(template => (
                      <option key={template.id} value={template.id}>
                        {template.name} ({template.language})
                      </option>
                    ))}
                  </select>
                  {templates.filter(t => t.status === 'APPROVED').length === 0 && (
                    <p className="text-sm text-amber-600 mt-2">
                      אין תבניות מאושרות. יש ליצור תבניות ב-Meta Business Manager.
                    </p>
                  )}
                </div>
              ) : (
                <div className="mt-4">
                  <label className="block text-sm font-medium mb-2">תוכן ההודעה</label>
                  <textarea
                    value={messageText}
                    onChange={(e) => setMessageText(e.target.value)}
                    className="w-full px-3 py-2 border border-slate-300 rounded-md"
                    rows={4}
                    placeholder="כתוב את תוכן ההודעה..."
                    dir="rtl"
                  />
                </div>
              )}
            </Card>

            {/* Audience Selection */}
            <Card className="p-6">
              <h2 className="text-lg font-semibold mb-4">בחירת קהל</h2>
              
              {/* NEW: Audience Source Selector */}
              <div className="space-y-4 mb-6">
                <label className="block text-sm font-medium mb-2">מקור הקהל</label>
                <div className="grid grid-cols-3 gap-2">
                  <button
                    onClick={() => setAudienceSource('leads')}
                    className={`px-4 py-3 rounded-lg text-sm font-medium transition-colors ${
                      audienceSource === 'leads'
                        ? 'bg-blue-600 text-white'
                        : 'bg-slate-100 text-slate-700 hover:bg-slate-200'
                    }`}
                  >
                    <Users className="h-4 w-4 inline ml-1" />
                    לידים מהמערכת
                  </button>
                  <button
                    onClick={() => setAudienceSource('import-list')}
                    className={`px-4 py-3 rounded-lg text-sm font-medium transition-colors ${
                      audienceSource === 'import-list'
                        ? 'bg-blue-600 text-white'
                        : 'bg-slate-100 text-slate-700 hover:bg-slate-200'
                    }`}
                  >
                    <Filter className="h-4 w-4 inline ml-1" />
                    רשימת ייבוא
                  </button>
                  <button
                    onClick={() => setAudienceSource('csv')}
                    className={`px-4 py-3 rounded-lg text-sm font-medium transition-colors ${
                      audienceSource === 'csv'
                        ? 'bg-blue-600 text-white'
                        : 'bg-slate-100 text-slate-700 hover:bg-slate-200'
                    }`}
                  >
                    <Upload className="h-4 w-4 inline ml-1" />
                    העלאת CSV
                  </button>
                </div>
              </div>

              {/* Leads from System */}
              {audienceSource === 'leads' && (
                <div className="space-y-4">
                  {/* Search */}
                  <div>
                    <label className="block text-sm font-medium mb-2">חיפוש לידים</label>
                    <input
                      type="text"
                      placeholder="חפש לפי שם או טלפון..."
                      value={leadSearchTerm}
                      onChange={(e) => setLeadSearchTerm(e.target.value)}
                      className="w-full px-3 py-2 border border-slate-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500"
                    />
                  </div>

                  {/* Status Filters */}
                  <div>
                    <label className="block text-sm font-medium mb-2">
                      <Filter className="h-4 w-4 inline ml-1" />
                      סנן לפי סטטוסים
                    </label>
                    <div className="flex flex-wrap gap-2">
                      {availableStatuses.map(status => (
                        <button
                          key={status}
                          onClick={() => toggleStatus(status)}
                          className={`px-3 py-1.5 rounded-full text-sm font-medium transition-colors ${
                            selectedStatuses.includes(status)
                              ? 'bg-blue-600 text-white'
                              : 'bg-slate-100 text-slate-700 hover:bg-slate-200'
                          }`}
                        >
                          {status}
                        </button>
                      ))}
                    </div>
                  </div>

                  {/* Lead Selection */}
                  <div className="border-t pt-4">
                    <div className="flex justify-between items-center mb-2">
                      <label className="text-sm font-medium">לידים זמינים</label>
                      <div className="flex gap-2">
                        <button
                          onClick={() => setSelectedLeadIds(leads.map(l => l.id))}
                          className="text-xs text-blue-600 hover:text-blue-700"
                        >
                          בחר הכל
                        </button>
                        <button
                          onClick={() => setSelectedLeadIds([])}
                          className="text-xs text-slate-600 hover:text-slate-700"
                        >
                          נקה בחירה
                        </button>
                      </div>
                    </div>
                    {loadingLeads ? (
                      <div className="text-center py-4">
                        <RefreshCw className="h-5 w-5 animate-spin mx-auto text-slate-400" />
                      </div>
                    ) : leads.length === 0 ? (
                      <p className="text-sm text-slate-500 py-4 text-center">לא נמצאו לידים</p>
                    ) : (
                      <div className="max-h-60 overflow-y-auto border border-slate-200 rounded-lg">
                        {leads.slice(0, 50).map(lead => (
                          <label key={lead.id} className="flex items-center p-2 hover:bg-slate-50 cursor-pointer border-b last:border-b-0">
                            <input
                              type="checkbox"
                              checked={selectedLeadIds.includes(lead.id)}
                              onChange={(e) => {
                                if (e.target.checked) {
                                  setSelectedLeadIds([...selectedLeadIds, lead.id]);
                                } else {
                                  setSelectedLeadIds(selectedLeadIds.filter(id => id !== lead.id));
                                }
                              }}
                              className="ml-2"
                            />
                            <div className="flex-1">
                              <div className="text-sm font-medium">{lead.name}</div>
                              <div className="text-xs text-slate-500">{lead.phone} • {lead.status}</div>
                            </div>
                          </label>
                        ))}
                        {leads.length > 50 && (
                          <div className="p-2 text-xs text-slate-500 text-center">
                            מציג 50 מתוך {leads.length} לידים. השתמש בסינון לצמצם את התוצאות.
                          </div>
                        )}
                      </div>
                    )}
                  </div>
                </div>
              )}

              {/* Import List Selection */}
              {audienceSource === 'import-list' && (
                <div className="space-y-4">
                  <div>
                    <label className="block text-sm font-medium mb-2">בחר רשימת ייבוא</label>
                    {loadingImportLists ? (
                      <div className="text-center py-4">
                        <RefreshCw className="h-5 w-5 animate-spin mx-auto text-slate-400" />
                      </div>
                    ) : importLists.length === 0 ? (
                      <p className="text-sm text-slate-500 py-4 text-center">אין רשימות ייבוא זמינות</p>
                    ) : (
                      <select
                        value={selectedImportListId || ''}
                        onChange={(e) => setSelectedImportListId(e.target.value ? Number(e.target.value) : null)}
                        className="w-full px-3 py-2 border border-slate-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500"
                      >
                        <option value="">בחר רשימה...</option>
                        {importLists.map(list => (
                          <option key={list.id} value={list.id}>
                            {list.name} ({list.current_leads} לידים)
                          </option>
                        ))}
                      </select>
                    )}
                  </div>
                </div>
              )}

              {/* CSV Upload */}
              {audienceSource === 'csv' && (
                <div className="space-y-4">
                  <div>
                    <label className="block text-sm font-medium mb-2">
                      <Upload className="h-4 w-4 inline ml-1" />
                      העלה קובץ CSV
                    </label>
                    <input
                      type="file"
                      accept=".csv"
                      onChange={(e) => setCsvFile(e.target.files?.[0] || null)}
                      className="block w-full text-sm text-slate-500
                        file:mr-4 file:py-2 file:px-4
                        file:rounded-md file:border-0
                        file:text-sm file:font-semibold
                        file:bg-blue-50 file:text-blue-700
                        hover:file:bg-blue-100"
                    />
                    <p className="text-xs text-slate-500 mt-1">
                      קובץ CSV עם עמודת "phone" לכל מספר טלפון
                    </p>
                  </div>
                </div>
              )}

              {/* Recipient Counter */}
              <div className="mt-6 p-4 bg-blue-50 border border-blue-200 rounded-lg">
                <div className="flex justify-between items-center">
                  <span className="text-sm font-medium text-blue-900">נמענים נבחרו:</span>
                  <span className="text-lg font-bold text-blue-600">{recipientCount}</span>
                </div>
              </div>
            </Card>
          </div>

          {/* Right Column - Preview & Send */}
          <div className="space-y-6">
            <Card className="p-6">
              <h2 className="text-lg font-semibold mb-4">תצוגה מקדימה</h2>
              <div className="bg-slate-50 p-4 rounded-lg min-h-[200px]">
                {messageType === 'template' && selectedTemplate ? (
                  <div>
                    <Badge variant="info" className="mb-2">{selectedTemplate.name}</Badge>
                    <p className="text-sm text-slate-700">
                      תבנית זו תשלח עם הפרמטרים המוגדרים
                    </p>
                  </div>
                ) : messageText ? (
                  <div className="whitespace-pre-wrap text-sm text-slate-700">
                    {messageText}
                  </div>
                ) : (
                  <p className="text-sm text-slate-400">בחר תבנית או כתוב הודעה כדי לראות תצוגה מקדימה</p>
                )}
              </div>
            </Card>

            <Card className="p-6">
              <h2 className="text-lg font-semibold mb-4">סטטיסטיקה משוערת</h2>
              <div className="space-y-2 text-sm">
                <div className="flex justify-between">
                  <span className="text-slate-600">מקור קהל:</span>
                  <span className="font-medium">
                    {audienceSource === 'leads' ? 'לידים מהמערכת' : 
                     audienceSource === 'import-list' ? 'רשימת ייבוא' : 'CSV'}
                  </span>
                </div>
                <div className="flex justify-between">
                  <span className="text-slate-600">נמענים:</span>
                  <span className="font-medium text-blue-600">{recipientCount}</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-slate-600">ספק:</span>
                  <span className="font-medium">{provider === 'meta' ? 'Meta' : 'Baileys'}</span>
                </div>
              </div>
              
              <Button
                variant="success"
                size="lg"
                className="w-full mt-6"
                onClick={handleSendBroadcast}
                disabled={sending}
              >
                {sending ? (
                  <>
                    <RefreshCw className="h-4 w-4 ml-2 animate-spin" />
                    שולח...
                  </>
                ) : (
                  <>
                    <Send className="h-4 w-4 ml-2" />
                    שלח תפוצה
                  </>
                )}
              </Button>
            </Card>
          </div>
        </div>
      )}

      {/* Campaign History Tab */}
      {activeTab === 'history' && (
        <Card className="p-6">
          <h2 className="text-lg font-semibold mb-4">היסטוריית תפוצות</h2>
          {loadingCampaigns ? (
            <div className="text-center py-8">
              <RefreshCw className="h-8 w-8 animate-spin mx-auto text-slate-400" />
              <p className="text-sm text-slate-500 mt-2">טוען תפוצות...</p>
            </div>
          ) : campaigns.length === 0 ? (
            <div className="text-center py-8 text-slate-500">
              <MessageSquare className="h-12 w-12 mx-auto mb-3 text-slate-300" />
              <p>אין תפוצות עדיין</p>
            </div>
          ) : (
            <div className="space-y-3">
              {campaigns.map(campaign => (
                <div key={campaign.id} className="border border-slate-200 rounded-lg p-4">
                  <div className="flex justify-between items-start mb-2">
                    <div>
                      <h3 className="font-medium text-slate-900">תפוצה #{campaign.id}</h3>
                      <p className="text-sm text-slate-500">
                        {new Date(campaign.created_at).toLocaleDateString('he-IL', {
                          day: 'numeric',
                          month: 'short',
                          year: 'numeric',
                          hour: '2-digit',
                          minute: '2-digit'
                        })}
                      </p>
                    </div>
                    <Badge 
                      variant={
                        campaign.status === 'completed' ? 'success' :
                        campaign.status === 'running' ? 'info' :
                        campaign.status === 'failed' ? 'destructive' :
                        'warning'
                      }
                    >
                      {campaign.status}
                    </Badge>
                  </div>
                  
                  <div className="grid grid-cols-3 gap-4 mt-4 text-sm">
                    <div>
                      <span className="text-slate-500">סה"כ:</span>
                      <span className="font-medium mr-2">{campaign.total_recipients}</span>
                    </div>
                    <div>
                      <span className="text-green-600">נשלחו:</span>
                      <span className="font-medium mr-2">{campaign.sent_count}</span>
                    </div>
                    <div>
                      <span className="text-red-600">נכשלו:</span>
                      <span className="font-medium mr-2">{campaign.failed_count}</span>
                    </div>
                  </div>
                  
                  {campaign.total_recipients > 0 && (
                    <div className="mt-3">
                      <div className="w-full bg-slate-200 rounded-full h-2">
                        <div
                          className="bg-green-600 h-2 rounded-full"
                          style={{ width: `${(campaign.sent_count / campaign.total_recipients) * 100}%` }}
                        />
                      </div>
                    </div>
                  )}
                </div>
              ))}
            </div>
          )}
        </Card>
      )}

      {/* Templates Tab */}
      {activeTab === 'templates' && (
        <Card className="p-6">
          <div className="flex justify-between items-center mb-4">
            <h2 className="text-lg font-semibold">תבניות Meta</h2>
            <Button variant="outline" onClick={loadTemplates} disabled={loadingTemplates}>
              <RefreshCw className={`h-4 w-4 ml-2 ${loadingTemplates ? 'animate-spin' : ''}`} />
              סנכרן מ-Meta
            </Button>
          </div>
          
          {loadingTemplates ? (
            <div className="text-center py-8">
              <RefreshCw className="h-8 w-8 animate-spin mx-auto text-slate-400" />
              <p className="text-sm text-slate-500 mt-2">טוען תבניות...</p>
            </div>
          ) : templates.length === 0 ? (
            <div className="text-center py-8 text-slate-500">
              <MessageSquare className="h-12 w-12 mx-auto mb-3 text-slate-300" />
              <p>אין תבניות</p>
              <p className="text-sm mt-2">יש ליצור תבניות ב-Meta Business Manager</p>
            </div>
          ) : (
            <div className="space-y-3">
              {templates.map(template => (
                <div key={template.id} className="border border-slate-200 rounded-lg p-4">
                  <div className="flex justify-between items-start">
                    <div>
                      <h3 className="font-medium text-slate-900">{template.name}</h3>
                      <p className="text-sm text-slate-500">
                        {template.language} • {template.category}
                      </p>
                    </div>
                    <Badge 
                      variant={
                        template.status === 'APPROVED' ? 'success' :
                        template.status === 'PENDING' ? 'warning' :
                        'destructive'
                      }
                    >
                      {template.status}
                    </Badge>
                  </div>
                </div>
              ))}
            </div>
          )}
        </Card>
      )}
    </div>
  );
}
