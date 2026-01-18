import React, { useState, useEffect } from 'react';
import { formatDate, formatDateOnly, formatTimeOnly, formatRelativeTime } from '../../shared/utils/format';
import { Send, Users, MessageSquare, Filter, Upload, RefreshCw, CheckCircle, XCircle, Clock, AlertTriangle, Plus, Edit2, Trash2, FileText, X } from 'lucide-react';
import { http } from '../../services/http';
import { AttachmentPicker } from '../../shared/components/AttachmentPicker';

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

// Manual/Custom template that users can create themselves
interface ManualTemplate {
  id: number;
  name: string;
  message_text: string;
  created_at: string;
  updated_at?: string;
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
  status: 'pending' | 'running' | 'completed' | 'failed' | 'paused' | 'stopped' | 'partial';
  created_at: string;
  created_by: string;
  stopped_by?: string;
}

// Hebrew status labels
const STATUS_LABELS: Record<string, string> = {
  'pending': 'ממתין',
  'running': 'רץ',
  'completed': 'הושלם',
  'failed': 'נכשל',
  'paused': 'מושהה',
  'stopped': 'נעצר',
  'partial': 'חלקי'
};

// Status badge variants
const STATUS_VARIANTS: Record<string, 'default' | 'success' | 'warning' | 'destructive' | 'info'> = {
  'pending': 'warning',
  'running': 'info',
  'completed': 'success',
  'failed': 'destructive',
  'paused': 'warning',
  'stopped': 'default',
  'partial': 'warning'
};

export function WhatsAppBroadcastPage() {
  const [activeTab, setActiveTab] = useState<'send' | 'history' | 'templates'>('send');
  
  // Template state
  const [templates, setTemplates] = useState<Template[]>([]);
  const [loadingTemplates, setLoadingTemplates] = useState(false);
  const [selectedTemplate, setSelectedTemplate] = useState<Template | null>(null);
  
  // Manual templates state
  const [templateSubTab, setTemplateSubTab] = useState<'meta' | 'manual'>('meta');
  const [manualTemplates, setManualTemplates] = useState<ManualTemplate[]>([]);
  const [loadingManualTemplates, setLoadingManualTemplates] = useState(false);
  const [showCreateManualTemplate, setShowCreateManualTemplate] = useState(false);
  const [editingManualTemplate, setEditingManualTemplate] = useState<ManualTemplate | null>(null);
  const [newTemplateName, setNewTemplateName] = useState('');
  const [newTemplateText, setNewTemplateText] = useState('');
  const [savingManualTemplate, setSavingManualTemplate] = useState(false);
  
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
  
  // Attachment state
  const [attachmentId, setAttachmentId] = useState<number | null>(null);
  const [showAttachmentPicker, setShowAttachmentPicker] = useState(false);
  
  // Campaign history
  const [campaigns, setCampaigns] = useState<BroadcastCampaign[]>([]);
  const [loadingCampaigns, setLoadingCampaigns] = useState(false);
  const [selectedCampaign, setSelectedCampaign] = useState<number | null>(null);
  const [campaignDetails, setCampaignDetails] = useState<any>(null);
  const [loadingDetails, setLoadingDetails] = useState(false);
  const [stoppingCampaign, setStoppingCampaign] = useState<number | null>(null);
  
  // ✅ FIX: Auto-refresh for running campaigns
  const [autoRefresh, setAutoRefresh] = useState(false);
  
  // Status options from CRM - store full status objects for labels
  const [availableStatuses, setAvailableStatuses] = useState<Array<{ name: string; label: string }>>([]);

  useEffect(() => {
    loadTemplates();
    loadManualTemplates();
    loadCampaigns();
    loadStatuses();
    loadImportLists();
    // 🔥 FIX: Load ALL leads on initial page load (no filters)
    loadLeads();
  }, []);
  
  // ✅ FIX: Auto-refresh campaigns when on history tab with running campaigns
  useEffect(() => {
    if (activeTab === 'history') {
      // Check if there are any running or pending campaigns
      const hasActiveCampaigns = campaigns.some(c => c.status === 'running' || c.status === 'pending');
      setAutoRefresh(hasActiveCampaigns);
      
      if (hasActiveCampaigns) {
        const interval = setInterval(() => {
          loadCampaigns();
        }, 5000); // Refresh every 5 seconds
        
        return () => clearInterval(interval);
      }
    }
  }, [activeTab, campaigns]);

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

  // Manual templates CRUD functions
  const loadManualTemplates = async () => {
    try {
      setLoadingManualTemplates(true);
      const response = await http.get<{ templates: ManualTemplate[] }>('/api/whatsapp/manual-templates');
      setManualTemplates(response.templates || []);
    } catch (error) {
      console.error('Error loading manual templates:', error);
      // Initialize with empty array if endpoint doesn't exist yet
      setManualTemplates([]);
    } finally {
      setLoadingManualTemplates(false);
    }
  };

  const handleSaveManualTemplate = async () => {
    if (!newTemplateName.trim() || !newTemplateText.trim()) {
      alert('נא למלא שם תבנית ותוכן');
      return;
    }

    try {
      setSavingManualTemplate(true);
      
      if (editingManualTemplate) {
        // Update existing template
        await http.patch(`/api/whatsapp/manual-templates/${editingManualTemplate.id}`, {
          name: newTemplateName,
          message_text: newTemplateText
        });
        alert('תבנית עודכנה בהצלחה');
      } else {
        // Create new template
        await http.post('/api/whatsapp/manual-templates', {
          name: newTemplateName,
          message_text: newTemplateText
        });
        alert('תבנית נוצרה בהצלחה');
      }
      
      // Reset form
      setNewTemplateName('');
      setNewTemplateText('');
      setEditingManualTemplate(null);
      setShowCreateManualTemplate(false);
      
      // Reload templates
      loadManualTemplates();
    } catch (error: any) {
      console.error('Error saving manual template:', error);
      alert('שגיאה בשמירת התבנית: ' + (error.message || 'שגיאה לא ידועה'));
    } finally {
      setSavingManualTemplate(false);
    }
  };

  const handleEditManualTemplate = (template: ManualTemplate) => {
    setEditingManualTemplate(template);
    setNewTemplateName(template.name);
    setNewTemplateText(template.message_text);
    setShowCreateManualTemplate(true);
  };

  const handleDeleteManualTemplate = async (templateId: number) => {
    if (!confirm('האם אתה בטוח שברצונך למחוק תבנית זו?')) {
      return;
    }

    try {
      await http.delete(`/api/whatsapp/manual-templates/${templateId}`);
      alert('תבנית נמחקה בהצלחה');
      loadManualTemplates();
    } catch (error: any) {
      console.error('Error deleting manual template:', error);
      alert('שגיאה במחיקת התבנית');
    }
  };

  const handleUseManualTemplate = (template: ManualTemplate) => {
    // Set the message text to the template content and switch to send tab
    setMessageText(template.message_text);
    setMessageType('freetext');
    setProvider('baileys');
    setActiveTab('send');
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

  const loadCampaignDetails = async (campaignId: number) => {
    try {
      setLoadingDetails(true);
      const response = await http.get<any>(`/api/whatsapp/broadcasts/${campaignId}`);
      setCampaignDetails(response);
    } catch (error) {
      console.error('Error loading campaign details:', error);
    } finally {
      setLoadingDetails(false);
    }
  };

  const handleStopCampaign = async (campaignId: number) => {
    if (!confirm('האם אתה בטוח שברצונך לעצור את התפוצה?')) {
      return;
    }

    try {
      setStoppingCampaign(campaignId);
      const response = await http.post<any>(`/api/whatsapp/broadcasts/${campaignId}/stop`, {});
      
      if (response.success) {
        alert(`התפוצה נעצרה בהצלחה!\n\nנשלחו: ${response.sent_count}\nנכשלו: ${response.failed_count}\nנותרו: ${response.remaining}`);
        // Reload campaigns to show updated status
        await loadCampaigns();
      } else {
        alert('שגיאה בעצירת התפוצה: ' + (response.message || 'שגיאה לא ידועה'));
      }
    } catch (error: any) {
      console.error('Error stopping campaign:', error);
      alert('שגיאה בעצירת התפוצה: ' + (error.message || 'שגיאה לא ידועה'));
    } finally {
      setStoppingCampaign(null);
    }
  };

  const loadStatuses = async () => {
    try {
      const response = await http.get<{ items: Array<{ name: string; label: string }> }>('/api/statuses');
      // Use items array from the response (standard format) - keep full objects for labels
      const statusList = response.items || [];
      setAvailableStatuses(statusList);
    } catch (error) {
      console.error('Error loading statuses:', error);
      // Fallback to common statuses with Hebrew labels
      setAvailableStatuses([
        { name: 'new', label: 'חדש' },
        { name: 'contacted', label: 'יצרנו קשר' },
        { name: 'qualified', label: 'מתאים' },
        { name: 'won', label: 'נצחנו' }
      ]);
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
      
      // Add multiple statuses using statuses[] parameter (backend expects this format)
      if (selectedStatuses.length > 0) {
        selectedStatuses.forEach(status => {
          params.append('statuses[]', status);
        });
      }
      
      // Add search query using 'q' parameter (backend uses this)
      if (leadSearchTerm.trim()) {
        params.append('q', leadSearchTerm.trim());
      }
      
      const queryString = params.toString();
      const url = `/api/leads${queryString ? `?${queryString}` : ''}`;
      
      // 🔥 FIX: Support both 'items' (regular endpoint) and 'leads' (admin endpoint) formats
      const response = await http.get<{ items?: Array<{id: number; full_name: string; phone_e164: string; status: string}>; leads?: Array<{id: number; full_name: string; phone_e164: string; status: string}> }>(url);
      const loadedLeads = response.items || response.leads || [];
      
      // 🔥 FIX: Only include leads with valid phone numbers (E.164 format)
      const leadsWithPhone = loadedLeads.filter(l => l.phone_e164 && l.phone_e164.trim());
      
      setLeads(leadsWithPhone.map(l => ({ id: l.id, name: l.full_name, phone: l.phone_e164, status: l.status })));
      
      // Calculate recipient count based on audience source
      updateRecipientCount(leadsWithPhone.length);
      
      console.log(`📊 Loaded ${leadsWithPhone.length} leads with phones out of ${loadedLeads.length} total`);
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
    
    // NEW: Validate audience source with better error messages and debugging
    console.log('🔍 Validation check:', {
      audienceSource,
      selectedLeadIds: selectedLeadIds.length,
      leads: leads.length,
      recipientCount
    });
    
    if (audienceSource === 'leads' && selectedLeadIds.length === 0) {
      console.error('❌ No leads selected! Current state:', {
        selectedLeadIds,
        leads: leads.slice(0, 3), // First 3 for debugging
        recipientCount
      });
      alert(`יש לבחור לפחות ליד אחד לשליחה.\n\nכרגע יש ${leads.length} לידים זמינים, אך לא נבחר אף אחד.\nאנא סמן לידים מהרשימה או לחץ "בחר הכל".`);
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

    // Additional validation - ensure recipient count is > 0
    if (recipientCount === 0) {
      alert('אין נמענים לשליחה. אנא בחר לידים, רשימת ייבוא או העלה קובץ CSV.');
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
      
      // NEW: Add attachment if selected
      if (attachmentId) {
        formData.append('attachment_id', String(attachmentId));
        console.log('📎 Adding attachment_id:', attachmentId);
      }
      
      // NEW: Add audience data based on source
      if (audienceSource === 'leads') {
        console.log('📋 Adding lead_ids to FormData:', selectedLeadIds);
        formData.append('lead_ids', JSON.stringify(selectedLeadIds));
        console.log('✅ lead_ids added. Count:', selectedLeadIds.length);
      } else if (audienceSource === 'import-list') {
        formData.append('import_list_id', String(selectedImportListId));
      } else if (audienceSource === 'csv' && csvFile) {
        formData.append('csv_file', csvFile);
      }
      
      // Legacy: Keep status filter for backward compatibility
      if (selectedStatuses.length > 0) {
        formData.append('statuses', JSON.stringify(selectedStatuses));
      }
      
      // 🔥 FIX: Remove duplicate CSV append (was causing issues)
      // The CSV is already added above at line 332
      
      // ✅ FIX BUILD 200+: Frontend console logging per requirements
      // Log the payload being sent for debugging
      const payloadDebug = {
        provider,
        message_type: messageType,
        audience_source: audienceSource,
        lead_ids_count: selectedLeadIds.length,
        selected_statuses: selectedStatuses,
        has_csv: !!csvFile,
        has_attachment: !!attachmentId,
        recipient_count: recipientCount
      };
      console.log('📤 Sending broadcast:', payloadDebug);
      console.log('📋 Full payload keys:', Array.from(formData.keys()));
      
      // 🔥 NEW: Debug FormData content
      console.log('🔍 FormData debug:');
      for (const [key, value] of formData.entries()) {
        if (key === 'csv_file') {
          console.log(`  ${key}: [File: ${(value as File).name}]`);
        } else {
          console.log(`  ${key}: ${value}`);
        }
      }
      
      const response = await http.post<{ 
        success?: boolean;
        ok?: boolean;
        broadcast_id: number; 
        queued_count?: number;
        sent_count?: number;
        job_id?: string;
        message?: string;
        error?: string;
        error_code?: string;
        details?: any;
      }>('/api/whatsapp/broadcasts', formData);
      
      console.log('✅ Broadcast response:', response);
      
      // Handle both 'success' and 'ok' fields for backwards compatibility
      const isSuccess = response.success || response.ok;
      
      if (isSuccess) {
        // ✅ FIX: Show proof of queuing with actual count
        const queuedMsg = response.queued_count 
          ? `נשלח לתור: ${response.queued_count} נמענים` 
          : `תפוצה נוצרה בהצלחה!`;
        
        alert(`${queuedMsg}\n\nמזהה תפוצה: ${response.broadcast_id}\n\nהתפוצה תישלח ברקע. תוכל לעקוב אחרי ההתקדמות בלשונית "היסטוריה".`);
        
        // Reset form
        setSelectedTemplate(null);
        setMessageText('');
        setSelectedStatuses([]);
        setSelectedLeadIds([]);
        setSelectedImportListId(null);
        setCsvFile(null);
        
        // Switch to history tab
        setActiveTab('history');
        // Reload campaigns
        await loadCampaigns();
      } else {
        // ✅ FIX: Show detailed error message
        let errorMsg = response.error || response.message || 'שגיאה לא ידועה';
        
        console.error('❌ Broadcast error:', response);
        
        // If we have detailed diagnostics, show them
        if (response.details) {
          const details = response.details;
          console.error('Broadcast error details:', details);
          
          if (details.missing_field === 'lead_ids') {
            errorMsg += `\n\nנבחרו ${details.selection_count} לידים אך לא נמצאו מספרי טלפון תקינים.`;
            errorMsg += '\n\nוודא שללידים שבחרת יש מספרי טלפון מלאים.';
          } else if (details.missing_field === 'import_list_id') {
            errorMsg += '\n\nרשימת הייבוא ריקה או שאין בה מספרי טלפון.';
          } else if (details.missing_field === 'csv_file') {
            errorMsg += '\n\nקובץ ה-CSV לא מכיל מספרי טלפון תקינים בעמודת "phone".';
          }
        }
        
        alert('שגיאה ביצירת תפוצה:\n\n' + errorMsg);
      }
    } catch (error: any) {
      console.error('❌ Error sending broadcast:', error);
      let errorMsg = 'שגיאה בשליחת תפוצה';
      
      if (error.message) {
        errorMsg += ':\n\n' + error.message;
      }
      
      // If error response has detailed info
      if (error.response?.data) {
        const data = error.response.data;
        console.error('Error response data:', data);
        if (data.error || data.message) {
          errorMsg += '\n\n' + (data.error || data.message);
        }
        if (data.details) {
          console.error('Error details:', data.details);
        }
      }
      
      alert(errorMsg);
    } finally {
      setSending(false);
    }
  };

  const toggleStatus = (statusName: string) => {
    if (selectedStatuses.includes(statusName)) {
      setSelectedStatuses(selectedStatuses.filter(s => s !== statusName));
    } else {
      setSelectedStatuses([...selectedStatuses, statusName]);
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
                <div className="mt-4 space-y-4">
                  {/* 🔥 NEW: Manual Template Quick Select for Baileys freetext */}
                  {manualTemplates.length > 0 && (
                    <div className="bg-purple-50 border border-purple-200 rounded-lg p-4">
                      <label className="block text-sm font-medium text-purple-900 mb-2 flex items-center gap-2">
                        <FileText className="h-4 w-4" />
                        טען מתבנית ידנית
                      </label>
                      <select
                        value=""
                        onChange={(e) => {
                          const template = manualTemplates.find(t => t.id === parseInt(e.target.value));
                          if (template) {
                            setMessageText(template.message_text);
                          }
                        }}
                        className="w-full px-3 py-2 border border-purple-300 rounded-md bg-white text-sm"
                      >
                        <option value="">-- בחר תבנית לטעינה --</option>
                        {manualTemplates.map(template => (
                          <option key={template.id} value={template.id}>
                            {template.name}
                          </option>
                        ))}
                      </select>
                      <p className="text-xs text-purple-600 mt-1">
                        בחר תבנית כדי לטעון את התוכן שלה לתיבת הטקסט
                      </p>
                    </div>
                  )}
                  
                  <div>
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
                  
                  {/* Attachment Picker */}
                  <div className="mt-4">
                    <button
                      type="button"
                      onClick={() => setShowAttachmentPicker(!showAttachmentPicker)}
                      className="flex items-center gap-2 px-4 py-2 text-sm text-blue-600 hover:text-blue-700 hover:bg-blue-50 rounded-md transition-colors"
                    >
                      <Upload className="w-4 h-4" />
                      {attachmentId ? 'שנה קובץ מצורף' : 'צרף קובץ'}
                    </button>
                    
                    {showAttachmentPicker && (
                      <div className="mt-3 p-4 border border-slate-200 rounded-lg bg-slate-50">
                        <AttachmentPicker
                          channel="broadcast"
                          mode="single"
                          onAttachmentSelect={(id) => {
                            if (typeof id === 'number') {
                              setAttachmentId(id);
                            } else {
                              setAttachmentId(null);
                            }
                          }}
                          selectedAttachmentId={attachmentId}
                        />
                      </div>
                    )}
                    
                    {attachmentId && (
                      <div className="mt-2 p-3 bg-green-50 border border-green-200 rounded-md">
                        <p className="text-sm text-green-800">
                          ✅ קובץ מצורף - יישלח לכל הנמענים
                        </p>
                      </div>
                    )}
                  </div>
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
                          key={status.name}
                          onClick={() => toggleStatus(status.name)}
                          className={`px-3 py-1.5 rounded-full text-sm font-medium transition-colors ${
                            selectedStatuses.includes(status.name)
                              ? 'bg-blue-600 text-white'
                              : 'bg-slate-100 text-slate-700 hover:bg-slate-200'
                          }`}
                        >
                          {status.label}
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
                      <div className="text-center py-6 px-4">
                        <p className="text-sm text-slate-600 mb-2">לא נמצאו לידים עם מספרי טלפון</p>
                        <p className="text-xs text-slate-500">
                          נסה לסנן לפי סטטוס אחר או נקה את החיפוש
                        </p>
                      </div>
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
                <div className="flex justify-between items-center mb-2">
                  <span className="text-sm font-medium text-blue-900">נמענים נבחרו:</span>
                  <span className="text-lg font-bold text-blue-600">{recipientCount}</span>
                </div>
                {audienceSource === 'leads' && (
                  <div className="text-xs text-blue-700 mt-1">
                    {selectedLeadIds.length > 0 ? (
                      <>נבחרו {selectedLeadIds.length} לידים מתוך {leads.length} זמינים</>
                    ) : (
                      <span className="text-orange-600 font-medium">⚠️ לא נבחרו לידים - לחץ על תיבות הסימון למעלה</span>
                    )}
                  </div>
                )}
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
          <div className="flex justify-between items-center mb-4">
            <h2 className="text-lg font-semibold">היסטוריית תפוצות</h2>
            {autoRefresh && (
              <div className="flex items-center gap-2 text-sm text-blue-600">
                <RefreshCw className="h-4 w-4 animate-spin" />
                <span>מתעדכן אוטומטית</span>
              </div>
            )}
          </div>
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
                    <div className="flex-1">
                      <div className="flex items-center gap-2">
                        <h3 className="font-medium text-slate-900">תפוצה #{campaign.id}</h3>
                        <Badge 
                          variant={STATUS_VARIANTS[campaign.status] || 'default'}
                        >
                          {STATUS_LABELS[campaign.status] || campaign.status}
                        </Badge>
                      </div>
                      <p className="text-sm text-slate-500">
                        {new Date(campaign.created_at).toLocaleDateString('he-IL', {
                          day: 'numeric',
                          month: 'short',
                          year: 'numeric',
                          hour: '2-digit',
                          minute: '2-digit',
                          timeZone: 'Asia/Jerusalem'
                        })}
                      </p>
                      {campaign.stopped_by && (
                        <p className="text-xs text-orange-600 mt-1">
                          נעצר על ידי {campaign.stopped_by}
                        </p>
                      )}
                    </div>
                    <div className="flex gap-2">
                      {(campaign.status === 'running' || campaign.status === 'pending') && (
                        <Button
                          variant="destructive"
                          size="sm"
                          onClick={() => handleStopCampaign(campaign.id)}
                          disabled={stoppingCampaign === campaign.id}
                        >
                          {stoppingCampaign === campaign.id ? (
                            <>
                              <RefreshCw className="h-3 w-3 ml-1 animate-spin" />
                              עוצר...
                            </>
                          ) : (
                            'עצור תפוצה'
                          )}
                        </Button>
                      )}
                      <Button
                        variant="outline"
                        size="sm"
                        onClick={() => {
                          setSelectedCampaign(campaign.id);
                          loadCampaignDetails(campaign.id);
                        }}
                      >
                        פרטים
                      </Button>
                    </div>
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

      {/* Campaign Details Modal */}
      {selectedCampaign && (
        <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center p-4 z-50" onClick={() => setSelectedCampaign(null)}>
          <div className="bg-white rounded-lg max-w-4xl w-full max-h-[90vh] overflow-hidden" onClick={(e) => e.stopPropagation()}>
            <div className="p-6 border-b border-slate-200">
              <div className="flex justify-between items-center">
                <h2 className="text-xl font-semibold">פרטי תפוצה #{selectedCampaign}</h2>
                <button
                  onClick={() => setSelectedCampaign(null)}
                  className="text-slate-500 hover:text-slate-700"
                >
                  <XCircle className="h-6 w-6" />
                </button>
              </div>
            </div>
            
            <div className="p-6 overflow-y-auto max-h-[calc(90vh-120px)]">
              {loadingDetails ? (
                <div className="text-center py-8">
                  <RefreshCw className="h-8 w-8 animate-spin mx-auto text-slate-400" />
                  <p className="text-sm text-slate-500 mt-2">טוען פרטים...</p>
                </div>
              ) : campaignDetails ? (
                <div className="space-y-6">
                  {/* Summary */}
                  <div className="grid grid-cols-3 gap-4">
                    <Card className="p-4">
                      <div className="text-sm text-slate-500">סה"כ נמענים</div>
                      <div className="text-2xl font-bold text-slate-900">{campaignDetails.total_recipients}</div>
                    </Card>
                    <Card className="p-4">
                      <div className="text-sm text-green-600">נשלחו בהצלחה</div>
                      <div className="text-2xl font-bold text-green-600">{campaignDetails.sent_count}</div>
                    </Card>
                    <Card className="p-4">
                      <div className="text-sm text-red-600">נכשלו</div>
                      <div className="text-2xl font-bold text-red-600">{campaignDetails.failed_count}</div>
                    </Card>
                  </div>

                  {/* Recipient Filters */}
                  <div className="flex gap-2 border-b border-slate-200 pb-2">
                    <button
                      className={`px-4 py-2 rounded-md text-sm font-medium ${
                        !campaignDetails.status_filter
                          ? 'bg-blue-600 text-white'
                          : 'bg-slate-100 text-slate-700 hover:bg-slate-200'
                      }`}
                      onClick={async () => {
                        setLoadingDetails(true);
                        try {
                          const response = await http.get<any>(`/api/whatsapp/broadcasts/${selectedCampaign}`);
                          setCampaignDetails(response);
                        } catch (error) {
                          console.error('Error loading all recipients:', error);
                        } finally {
                          setLoadingDetails(false);
                        }
                      }}
                    >
                      הכל ({campaignDetails.total_recipients})
                    </button>
                    <button
                      className="px-4 py-2 rounded-md text-sm font-medium bg-green-100 text-green-700 hover:bg-green-200"
                      onClick={async () => {
                        setLoadingDetails(true);
                        try {
                          const response = await http.get<any>(`/api/whatsapp/broadcasts/${selectedCampaign}?status=sent`);
                          setCampaignDetails(response);
                        } catch (error) {
                          console.error('Error loading sent recipients:', error);
                        } finally {
                          setLoadingDetails(false);
                        }
                      }}
                    >
                      נשלחו ({campaignDetails.sent_count})
                    </button>
                    <button
                      className="px-4 py-2 rounded-md text-sm font-medium bg-red-100 text-red-700 hover:bg-red-200"
                      onClick={async () => {
                        setLoadingDetails(true);
                        try {
                          const response = await http.get<any>(`/api/whatsapp/broadcasts/${selectedCampaign}?status=failed`);
                          setCampaignDetails(response);
                        } catch (error) {
                          console.error('Error loading failed recipients:', error);
                        } finally {
                          setLoadingDetails(false);
                        }
                      }}
                    >
                      נכשלו ({campaignDetails.failed_count})
                    </button>
                  </div>

                  {/* Recipients List */}
                  <div>
                    <h3 className="font-semibold mb-3">רשימת נמענים</h3>
                    <div className="border border-slate-200 rounded-lg overflow-hidden">
                      <table className="min-w-full divide-y divide-slate-200">
                        <thead className="bg-slate-50">
                          <tr>
                            <th className="px-4 py-3 text-right text-xs font-medium text-slate-500 uppercase">טלפון</th>
                            <th className="px-4 py-3 text-right text-xs font-medium text-slate-500 uppercase">שם</th>
                            <th className="px-4 py-3 text-right text-xs font-medium text-slate-500 uppercase">סטטוס</th>
                            <th className="px-4 py-3 text-right text-xs font-medium text-slate-500 uppercase">שגיאה</th>
                            <th className="px-4 py-3 text-right text-xs font-medium text-slate-500 uppercase">נשלח</th>
                          </tr>
                        </thead>
                        <tbody className="bg-white divide-y divide-slate-200">
                          {campaignDetails.recipients && campaignDetails.recipients.length > 0 ? (
                            campaignDetails.recipients.map((recipient: any, idx: number) => (
                              <tr key={idx}>
                                <td className="px-4 py-3 text-sm text-slate-900">{recipient.phone}</td>
                                <td className="px-4 py-3 text-sm text-slate-600">{recipient.lead_name || '-'}</td>
                                <td className="px-4 py-3">
                                  <Badge
                                    variant={
                                      recipient.status === 'sent' || recipient.status === 'delivered' ? 'success' :
                                      recipient.status === 'failed' ? 'destructive' :
                                      'warning'
                                    }
                                  >
                                    {recipient.status === 'sent' ? 'נשלח' :
                                     recipient.status === 'delivered' ? 'נמסר' :
                                     recipient.status === 'failed' ? 'נכשל' :
                                     recipient.status === 'queued' ? 'בתור' : recipient.status}
                                  </Badge>
                                </td>
                                <td className="px-4 py-3 text-sm text-red-600">
                                  {recipient.error ? (
                                    <span className="truncate max-w-xs block" title={recipient.error}>
                                      {recipient.error}
                                    </span>
                                  ) : '-'}
                                </td>
                                <td className="px-4 py-3 text-sm text-slate-500">
                                  {recipient.sent_at ? new Date(recipient.sent_at).toLocaleTimeString('he-IL', {
                                    hour: '2-digit',
                                    minute: '2-digit'
                                  }) : '-'}
                                </td>
                              </tr>
                            ))
                          ) : (
                            <tr>
                              <td colSpan={5} className="px-4 py-8 text-center text-slate-500">
                                אין נמענים להצגה
                              </td>
                            </tr>
                          )}
                        </tbody>
                      </table>
                    </div>

                    {/* Pagination info */}
                    {campaignDetails.pagination && campaignDetails.pagination.total > campaignDetails.pagination.per_page && (
                      <div className="mt-4 text-sm text-slate-500 text-center">
                        מציג {Math.min(campaignDetails.pagination.per_page, campaignDetails.pagination.total)} מתוך {campaignDetails.pagination.total} נמענים
                      </div>
                    )}
                  </div>
                </div>
              ) : (
                <div className="text-center py-8 text-slate-500">
                  שגיאה בטעינת הפרטים
                </div>
              )}
            </div>
          </div>
        </div>
      )}

      {/* Templates Tab */}
      {activeTab === 'templates' && (
        <div className="space-y-6">
          {/* Template Sub-tabs */}
          <div className="flex items-center gap-4 border-b border-slate-200">
            <button
              onClick={() => setTemplateSubTab('meta')}
              className={`py-3 px-1 border-b-2 font-medium text-sm transition-colors ${
                templateSubTab === 'meta'
                  ? 'border-blue-500 text-blue-600'
                  : 'border-transparent text-slate-500 hover:text-slate-700 hover:border-slate-300'
              }`}
            >
              <MessageSquare className="h-4 w-4 inline ml-2" />
              תבניות Meta ({templates.filter(t => t.status === 'APPROVED').length})
            </button>
            <button
              onClick={() => setTemplateSubTab('manual')}
              className={`py-3 px-1 border-b-2 font-medium text-sm transition-colors ${
                templateSubTab === 'manual'
                  ? 'border-blue-500 text-blue-600'
                  : 'border-transparent text-slate-500 hover:text-slate-700 hover:border-slate-300'
              }`}
            >
              <FileText className="h-4 w-4 inline ml-2" />
              תבניות ידניות ({manualTemplates.length})
            </button>
          </div>

          {/* Meta Templates Sub-tab */}
          {templateSubTab === 'meta' && (
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

          {/* Manual Templates Sub-tab */}
          {templateSubTab === 'manual' && (
            <Card className="p-6">
              <div className="flex justify-between items-center mb-4">
                <div>
                  <h2 className="text-lg font-semibold">תבניות ידניות</h2>
                  <p className="text-sm text-slate-500 mt-1">צור תבניות מותאמות אישית לשימוש עם Baileys</p>
                </div>
                <Button onClick={() => {
                  setEditingManualTemplate(null);
                  setNewTemplateName('');
                  setNewTemplateText('');
                  setShowCreateManualTemplate(true);
                }}>
                  <Plus className="h-4 w-4 ml-2" />
                  תבנית חדשה
                </Button>
              </div>
              
              {loadingManualTemplates ? (
                <div className="text-center py-8">
                  <RefreshCw className="h-8 w-8 animate-spin mx-auto text-slate-400" />
                  <p className="text-sm text-slate-500 mt-2">טוען תבניות...</p>
                </div>
              ) : manualTemplates.length === 0 ? (
                <div className="text-center py-8 text-slate-500">
                  <FileText className="h-12 w-12 mx-auto mb-3 text-slate-300" />
                  <p>אין תבניות ידניות</p>
                  <p className="text-sm mt-2">לחץ על "תבנית חדשה" כדי ליצור את התבנית הראשונה שלך</p>
                </div>
              ) : (
                <div className="space-y-3">
                  {manualTemplates.map(template => (
                    <div key={template.id} className="border border-slate-200 rounded-lg p-4 hover:border-blue-300 transition-colors">
                      <div className="flex justify-between items-start">
                        <div className="flex-1">
                          <h3 className="font-medium text-slate-900">{template.name}</h3>
                          <p className="text-sm text-slate-600 mt-2 whitespace-pre-wrap overflow-hidden" style={{ display: '-webkit-box', WebkitLineClamp: 3, WebkitBoxOrient: 'vertical' }}>
                            {template.message_text}
                          </p>
                          <p className="text-xs text-slate-400 mt-2">
                            נוצר: {formatDate(template.created_at)}
                          </p>
                        </div>
                        <div className="flex items-center gap-2 mr-4">
                          <Button
                            variant="outline"
                            size="sm"
                            onClick={() => handleUseManualTemplate(template)}
                          >
                            <Send className="h-3 w-3 ml-1" />
                            השתמש
                          </Button>
                          <Button
                            variant="ghost"
                            size="sm"
                            onClick={() => handleEditManualTemplate(template)}
                          >
                            <Edit2 className="h-3 w-3" />
                          </Button>
                          <Button
                            variant="ghost"
                            size="sm"
                            onClick={() => handleDeleteManualTemplate(template.id)}
                            className="text-red-600 hover:bg-red-50"
                          >
                            <Trash2 className="h-3 w-3" />
                          </Button>
                        </div>
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </Card>
          )}

          {/* Create/Edit Manual Template Modal */}
          {showCreateManualTemplate && (
            <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center p-4 z-50" onClick={() => setShowCreateManualTemplate(false)}>
              <div className="bg-white rounded-lg max-w-2xl w-full max-h-[90vh] overflow-hidden" onClick={(e) => e.stopPropagation()}>
                <div className="p-6 border-b border-slate-200">
                  <div className="flex justify-between items-center">
                    <h2 className="text-xl font-semibold">
                      {editingManualTemplate ? 'ערוך תבנית' : 'תבנית חדשה'}
                    </h2>
                    <button
                      onClick={() => setShowCreateManualTemplate(false)}
                      className="text-slate-500 hover:text-slate-700"
                    >
                      <X className="h-6 w-6" />
                    </button>
                  </div>
                </div>
                
                <div className="p-6 space-y-4">
                  <div>
                    <label className="block text-sm font-medium text-slate-700 mb-2">
                      שם התבנית *
                    </label>
                    <input
                      type="text"
                      value={newTemplateName}
                      onChange={(e) => setNewTemplateName(e.target.value)}
                      className="w-full px-3 py-2 border border-slate-300 rounded-md focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
                      placeholder="לדוגמה: הודעת ברכה ללקוח חדש"
                    />
                  </div>
                  
                  <div>
                    <label className="block text-sm font-medium text-slate-700 mb-2">
                      תוכן ההודעה *
                    </label>
                    <textarea
                      value={newTemplateText}
                      onChange={(e) => setNewTemplateText(e.target.value)}
                      className="w-full px-3 py-2 border border-slate-300 rounded-md focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
                      rows={6}
                      placeholder="כתוב כאן את תוכן ההודעה..."
                      dir="rtl"
                    />
                    <p className="text-xs text-slate-500 mt-1">
                      תבנית זו תשמש לשליחת הודעות דרך Baileys (טקסט חופשי)
                    </p>
                  </div>
                  
                  <div className="flex justify-end gap-3 pt-4 border-t border-slate-200">
                    <Button
                      variant="outline"
                      onClick={() => setShowCreateManualTemplate(false)}
                    >
                      ביטול
                    </Button>
                    <Button
                      onClick={handleSaveManualTemplate}
                      disabled={savingManualTemplate || !newTemplateName.trim() || !newTemplateText.trim()}
                    >
                      {savingManualTemplate ? (
                        <>
                          <RefreshCw className="h-4 w-4 ml-2 animate-spin" />
                          שומר...
                        </>
                      ) : (
                        <>
                          <CheckCircle className="h-4 w-4 ml-2" />
                          {editingManualTemplate ? 'עדכן תבנית' : 'צור תבנית'}
                        </>
                      )}
                    </Button>
                  </div>
                </div>
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
