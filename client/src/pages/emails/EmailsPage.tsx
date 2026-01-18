import React, { useState, useEffect } from 'react';
import { Mail, Send, Settings, AlertCircle, CheckCircle, Clock, XCircle, Plus, Eye, Search, X, RefreshCw, Pencil, Save, Edit2, Trash2, FileText } from 'lucide-react';
import { useAuth } from '../../features/auth/hooks';
import axios from 'axios';

// Email validation constants
const MIN_HTML_LENGTH_FRONTEND = 200; // Minimum HTML length for frontend validation (chars)

interface EmailMessage {
  id: number;
  to_email: string;
  subject: string;
  status: string;
  error?: string;
  from_email: string;
  from_name: string;
  reply_to?: string;
  sent_at?: string;
  created_at: string;
  lead_id?: number;
  lead_name?: string;
  created_by?: {
    name: string;
    email: string;
  };
}

interface Lead {
  id: number;
  first_name: string;
  last_name: string;
  email: string;
  phone_e164: string;
  status: string;
  source?: string;
  created_at?: string;
}

interface EmailTemplate {
  id: number;
  name: string;
  type: string;
  subject_template: string;
  html_template: string;
  text_template: string;
  is_active: boolean;
}

// Text templates for quick email content (quotes, greetings, pricing info)
interface EmailTextTemplate {
  id: number;
  name: string;
  category: string;
  subject_line: string;
  body_text: string;
  button_text?: string;
  button_link?: string;
  footer_text?: string;
  is_active: boolean;
  created_at: string;
  updated_at?: string;
}

interface EmailSettings {
  id: number;
  from_email: string;
  from_name: string;
  reply_to?: string;
  is_enabled: boolean;
  provider: string;
}

const StatusBadge: React.FC<{ status: string }> = ({ status }) => {
  const statusConfig = {
    queued: { icon: Clock, color: 'bg-gray-100 text-gray-800', label: 'בתור' },
    sent: { icon: CheckCircle, color: 'bg-green-100 text-green-800', label: 'נשלח' },
    failed: { icon: XCircle, color: 'bg-red-100 text-red-800', label: 'נכשל' },
    delivered: { icon: CheckCircle, color: 'bg-blue-100 text-blue-800', label: 'נמסר' },
  };
  
  const config = statusConfig[status as keyof typeof statusConfig] || statusConfig.queued;
  const Icon = config.icon;
  
  return (
    <span className={`inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium ${config.color}`}>
      <Icon className="w-3 h-3 ml-1" />
      {config.label}
    </span>
  );
};

export function EmailsPage() {
  const { user } = useAuth();
  const [emails, setEmails] = useState<EmailMessage[]>([]);
  const [settings, setSettings] = useState<EmailSettings | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [activeTab, setActiveTab] = useState<'all' | 'sent' | 'leads' | 'templates' | 'settings'>('all');
  const [statusFilter, setStatusFilter] = useState<string>('');
  const [searchQuery, setSearchQuery] = useState('');
  
  // Email settings state
  const [fromName, setFromName] = useState('');
  const [replyTo, setReplyTo] = useState('');
  const [isEnabled, setIsEnabled] = useState(true);
  const [testEmail, setTestEmail] = useState('');
  const [saveLoading, setSaveLoading] = useState(false);
  const [testLoading, setTestLoading] = useState(false);
  const [successMessage, setSuccessMessage] = useState<string | null>(null);
  const [configured, setConfigured] = useState(false);
  const [sendgridAvailable, setSendgridAvailable] = useState(true);
  
  // Compose email modal state
  const [showComposeModal, setShowComposeModal] = useState(false);
  const [selectedLead, setSelectedLead] = useState<Lead | null>(null);
  const [composeLoading, setComposeLoading] = useState(false);
  const [leadSearchQuery, setLeadSearchQuery] = useState('');
  const [leadSearchResults, setLeadSearchResults] = useState<Lead[]>([]);
  const [leadSearchLoading, setLeadSearchLoading] = useState(false);
  
  // 🎨 Luxury Theme Templates State
  const [availableThemes, setAvailableThemes] = useState<any[]>([]);
  const [selectedThemeId, setSelectedThemeId] = useState('classic_blue');
  const [themesLoading, setThemesLoading] = useState(false);
  const [themesError, setThemesError] = useState<string | null>(null);
  const [themeFields, setThemeFields] = useState({
    subject: '',
    greeting: '',
    body: '',
    cta_text: '',
    cta_url: '',
    footer: ''
  });
  const [showThemePreview, setShowThemePreview] = useState(false);
  const [themePreviewHtml, setThemePreviewHtml] = useState('');
  const [themePreviewLoading, setThemePreviewLoading] = useState(false);
  
  // Leads tab state
  const [allLeads, setAllLeads] = useState<Lead[]>([]);
  const [allLeadsLoading, setAllLeadsLoading] = useState(false);
  const [leadsFilter, setLeadsFilter] = useState('');
  const [leadsStatusFilter, setLeadsStatusFilter] = useState('');
  const [leadsPage, setLeadsPage] = useState(1);
  const [leadsHasMore, setLeadsHasMore] = useState(true);
  const [leadStatusUpdating, setLeadStatusUpdating] = useState<number | null>(null);
  
  // Templates state
  const [templates, setTemplates] = useState<EmailTemplate[]>([]);
  const [templatesLoading, setTemplatesLoading] = useState(false);
  const [showPreviewModal, setShowPreviewModal] = useState(false);
  const [previewTemplate, setPreviewTemplate] = useState<EmailTemplate | null>(null);
  const [previewHtml, setPreviewHtml] = useState('');
  const [previewSubject, setPreviewSubject] = useState('');
  const [previewLoading, setPreviewLoading] = useState(false);
  
  // Text Templates state (for quick content like quotes, greetings, pricing)
  const [templateSubTab, setTemplateSubTab] = useState<'design' | 'text'>('design');
  const [textTemplates, setTextTemplates] = useState<EmailTextTemplate[]>([]);
  const [textTemplatesLoading, setTextTemplatesLoading] = useState(false);
  const [showCreateTextTemplate, setShowCreateTextTemplate] = useState(false);
  const [editingTextTemplate, setEditingTextTemplate] = useState<EmailTextTemplate | null>(null);
  const [newTextTemplateName, setNewTextTemplateName] = useState('');
  const [newTextTemplateCategory, setNewTextTemplateCategory] = useState('general');
  const [newTextTemplateSubject, setNewTextTemplateSubject] = useState('');
  const [newTextTemplateBody, setNewTextTemplateBody] = useState('');
  const [newTextTemplateButtonText, setNewTextTemplateButtonText] = useState('');
  const [newTextTemplateButtonLink, setNewTextTemplateButtonLink] = useState('');
  const [newTextTemplateFooter, setNewTextTemplateFooter] = useState('');
  const [savingTextTemplate, setSavingTextTemplate] = useState(false);
  
  // Bulk selection state for Leads tab
  const [selectedLeadIds, setSelectedLeadIds] = useState<Set<number>>(new Set());
  const [showBulkComposeModal, setShowBulkComposeModal] = useState(false);
  const [bulkComposeLoading, setBulkComposeLoading] = useState(false);
  
  // Template settings state
  const [templateDefaultTheme, setTemplateDefaultTheme] = useState('classic_blue');
  const [templateDefaultGreeting, setTemplateDefaultGreeting] = useState('שלום {{lead.first_name}},');
  const [templateDefaultCtaText, setTemplateDefaultCtaText] = useState('');
  const [templateDefaultCtaUrl, setTemplateDefaultCtaUrl] = useState('');
  const [templateDefaultFooter, setTemplateDefaultFooter] = useState('אם אינך מעוניין לקבל הודעות נוספות, אנא לחץ כאן להסרה מהרשימה.\n\n© {{business.name}} | כל הזכויות שמורות');
  const [templateBrandColor, setTemplateBrandColor] = useState('#2563EB');
  
  useEffect(() => {
    loadSettings();
    loadEmailSettings(); // Load template settings
    loadTextTemplates(); // Load text templates on mount
    if (activeTab === 'all' || activeTab === 'sent') {
      loadEmails();
    } else if (activeTab === 'templates') {
      loadTemplates();
    } else if (activeTab === 'leads') {
      setLeadsPage(1);
      loadAllLeads(false);
    }
  }, [activeTab, statusFilter, searchQuery, leadsFilter, leadsStatusFilter]);
  
  // 🔥 FIX: Load themes once on mount, not dependent on modal
  useEffect(() => {
    loadLuxuryThemes();
  }, []);
  
  // Load templates when compose modal opens
  useEffect(() => {
    if (showComposeModal) {
      if (templates.length === 0) {
        loadTemplates();
      }
    }
  }, [showComposeModal]);
  
  // Debounced lead search
  useEffect(() => {
    if (leadSearchQuery.length >= 2) {
      const timer = setTimeout(() => {
        searchLeads();
      }, 300);
      return () => clearTimeout(timer);
    } else {
      setLeadSearchResults([]);
    }
  }, [leadSearchQuery]);
  
  const loadSettings = async () => {
    try {
      const response = await axios.get('/api/email/settings');
      setConfigured(response.data.configured);
      setSendgridAvailable(response.data.sendgrid_available);
      
      if (response.data.settings) {
        const s = response.data.settings;
        setSettings(s);
        setFromName(s.from_name);
        setReplyTo(s.reply_to || '');
        setIsEnabled(s.is_enabled);
      }
    } catch (err: any) {
      console.error('Failed to load email settings:', err);
    }
  };
  
  const loadEmailSettings = async () => {
    try {
      const response = await axios.get('/api/email/settings');
      if (response.data.settings) {
        const s = response.data.settings;
        setTemplateDefaultTheme(s.theme_id || 'classic_blue');
        setTemplateDefaultGreeting(s.default_greeting || 'שלום {{lead.first_name}},');
        setTemplateDefaultCtaText(s.cta_default_text || '');
        setTemplateDefaultCtaUrl(s.cta_default_url || '');
        setTemplateDefaultFooter(s.footer_text || 'אם אינך מעוניין לקבל הודעות נוספות, אנא לחץ כאן להסרה מהרשימה.\n\n© {{business.name}} | כל הזכויות שמורות');
        setTemplateBrandColor(s.brand_primary_color || '#2563EB');
      }
    } catch (err: any) {
      console.error('Failed to load email template settings:', err);
    }
  };
  
  const handleSaveTemplateSettings = async (e: React.FormEvent) => {
    e.preventDefault();
    
    try {
      setSaveLoading(true);
      setError(null);
      setSuccessMessage(null);
      
      await axios.post('/api/email/settings', {
        from_name: fromName,
        reply_to: replyTo,
        is_enabled: isEnabled,
        theme_id: templateDefaultTheme,
        default_greeting: templateDefaultGreeting,
        cta_default_text: templateDefaultCtaText,
        cta_default_url: templateDefaultCtaUrl,
        footer_text: templateDefaultFooter,
        brand_primary_color: templateBrandColor
      });
      
      setSuccessMessage('הגדרות התבנית נשמרו בהצלחה!');
      await loadEmailSettings();
      
      // Update theme fields with saved defaults
      setThemeFields(prev => ({
        ...prev,
        greeting: templateDefaultGreeting,
        cta_text: templateDefaultCtaText,
        cta_url: templateDefaultCtaUrl,
        footer: templateDefaultFooter
      }));
      setSelectedThemeId(templateDefaultTheme);
      
    } catch (err: any) {
      setError(err.response?.data?.error || 'שגיאה בשמירת הגדרות התבנית');
    } finally {
      setSaveLoading(false);
    }
  };
  
  const loadEmails = async () => {
    try {
      setLoading(true);
      const params = new URLSearchParams();
      if (statusFilter) params.append('status', statusFilter);
      if (searchQuery) params.append('q', searchQuery);
      if (activeTab === 'sent') params.append('status', 'sent');
      
      const response = await axios.get(`/api/email/messages?${params.toString()}`);
      setEmails(response.data.emails || []);
      setError(null);
    } catch (err: any) {
      console.error('Failed to load emails:', err);
      setError('שגיאה בטעינת מיילים');
    } finally {
      setLoading(false);
    }
  };
  
  const handleSaveSettings = async (e: React.FormEvent) => {
    e.preventDefault();
    
    if (!fromName.trim()) {
      setError('נא למלא שם שולח');
      return;
    }
    
    // Check admin permission
    if (!['system_admin', 'owner', 'admin'].includes(user?.role || '')) {
      setError('אין הרשאה לשנות הגדרות');
      return;
    }
    
    setSaveLoading(true);
    setError(null);
    setSuccessMessage(null);
    
    try {
      await axios.post('/api/email/settings', {
        from_name: fromName.trim(),
        reply_to: replyTo.trim() || null,
        is_enabled: isEnabled
      });
      
      setSuccessMessage('הגדרות המייל נשמרו בהצלחה');
      await loadSettings();
    } catch (err: any) {
      setError(err.response?.data?.error || 'שגיאה בשמירת הגדרות');
    } finally {
      setSaveLoading(false);
    }
  };
  
  const handleTestEmail = async () => {
    if (!testEmail.trim()) {
      setError('נא למלא כתובת מייל לבדיקה');
      return;
    }
    
    setTestLoading(true);
    setError(null);
    setSuccessMessage(null);
    
    try {
      await axios.post('/api/email/settings/test', {
        to_email: testEmail.trim()
      });
      
      setSuccessMessage('מייל בדיקה נשלח בהצלחה');
      setTestEmail('');
    } catch (err: any) {
      setError(err.response?.data?.message || 'שגיאה בשליחת מייל בדיקה');
    } finally {
      setTestLoading(false);
    }
  };
  
  const loadTemplates = async () => {
    try {
      setTemplatesLoading(true);
      const response = await axios.get('/api/email/templates');
      setTemplates(response.data.templates || []);
    } catch (err: any) {
      console.error('Failed to load templates:', err);
    } finally {
      setTemplatesLoading(false);
    }
  };
  
  // Load Text Templates (quick content templates)
  const loadTextTemplates = async () => {
    try {
      setTextTemplatesLoading(true);
      const response = await axios.get('/api/email/text-templates');
      setTextTemplates(response.data.templates || []);
    } catch (err: any) {
      console.error('Failed to load text templates:', err);
      setTextTemplates([]);
    } finally {
      setTextTemplatesLoading(false);
    }
  };

  const handleSaveTextTemplate = async () => {
    if (!newTextTemplateName.trim() || !newTextTemplateBody.trim()) {
      setError('נא למלא שם תבנית ותוכן');
      return;
    }

    try {
      setSavingTextTemplate(true);
      setError(null);
      
      if (editingTextTemplate) {
        // Update existing template
        await axios.patch(`/api/email/text-templates/${editingTextTemplate.id}`, {
          name: newTextTemplateName,
          category: newTextTemplateCategory,
          subject_line: newTextTemplateSubject,
          body_text: newTextTemplateBody,
          button_text: newTextTemplateButtonText || null,
          button_link: newTextTemplateButtonLink || null,
          footer_text: newTextTemplateFooter || null
        });
        setSuccessMessage('תבנית עודכנה בהצלחה');
      } else {
        // Create new template
        await axios.post('/api/email/text-templates', {
          name: newTextTemplateName,
          category: newTextTemplateCategory,
          subject_line: newTextTemplateSubject,
          body_text: newTextTemplateBody,
          button_text: newTextTemplateButtonText || null,
          button_link: newTextTemplateButtonLink || null,
          footer_text: newTextTemplateFooter || null
        });
        setSuccessMessage('תבנית נוצרה בהצלחה');
      }
      
      // Reset form
      setNewTextTemplateName('');
      setNewTextTemplateCategory('general');
      setNewTextTemplateSubject('');
      setNewTextTemplateBody('');
      setNewTextTemplateButtonText('');
      setNewTextTemplateButtonLink('');
      setNewTextTemplateFooter('');
      setEditingTextTemplate(null);
      setShowCreateTextTemplate(false);
      
      // Reload templates
      loadTextTemplates();
      setTimeout(() => setSuccessMessage(null), 3000);
    } catch (err: any) {
      console.error('Error saving text template:', err);
      setError(err.response?.data?.error || 'שגיאה בשמירת התבנית');
    } finally {
      setSavingTextTemplate(false);
    }
  };

  const handleEditTextTemplate = (template: EmailTextTemplate) => {
    setEditingTextTemplate(template);
    setNewTextTemplateName(template.name);
    setNewTextTemplateCategory(template.category);
    setNewTextTemplateSubject(template.subject_line || '');
    setNewTextTemplateBody(template.body_text);
    setNewTextTemplateButtonText(template.button_text || '');
    setNewTextTemplateButtonLink(template.button_link || '');
    setNewTextTemplateFooter(template.footer_text || '');
    setShowCreateTextTemplate(true);
  };

  const handleDeleteTextTemplate = async (templateId: number) => {
    if (!confirm('האם אתה בטוח שברצונך למחוק תבנית זו?')) {
      return;
    }

    try {
      await axios.delete(`/api/email/text-templates/${templateId}`);
      setSuccessMessage('תבנית נמחקה בהצלחה');
      loadTextTemplates();
      setTimeout(() => setSuccessMessage(null), 3000);
    } catch (err: any) {
      console.error('Error deleting text template:', err);
      setError('שגיאה במחיקת התבנית');
    }
  };

  const handleUseTextTemplate = (template: EmailTextTemplate) => {
    // Set the email fields from the template and switch to compose
    setThemeFields(prev => ({
      ...prev,
      subject: template.subject_line || prev.subject,
      body: template.body_text
    }));
    setActiveTab('leads');
    setSuccessMessage(`תבנית "${template.name}" נטענה - בחר ליד כדי לשלוח`);
    setTimeout(() => setSuccessMessage(null), 3000);
  };
  
  // 🎨 Load Luxury Theme Templates - 🔥 FIX: Robust loading with proper error handling
  const loadLuxuryThemes = async () => {
    setThemesLoading(true);
    setThemesError(null);
    try {
      console.log('[THEMES] Fetching catalog...');
      const response = await axios.get('/api/email/template-catalog');
      
      console.log('[THEMES] status', response.status, 'data', response.data);
      
      // 🔥 FIX: Handle both response formats (themes at root or nested)
      const raw = response.data;
      const themes = raw?.themes ?? raw ?? [];
      
      console.log('[THEMES] Parsed themes count:', themes.length);
      
      // 🔥 FIX: Always ensure we have an array (never undefined or null)
      if (Array.isArray(themes) && themes.length > 0) {
        setAvailableThemes(themes);
        
        // Set default theme and fields
        const defaultTheme = themes[0];
        setSelectedThemeId(defaultTheme.id);
        if (defaultTheme.default_fields) {
          setThemeFields(defaultTheme.default_fields);
        }
        console.log('[THEMES] ✅ Loaded', themes.length, 'themes, default:', defaultTheme.id);
      } else {
        // No themes received - set empty array and error
        setAvailableThemes([]);
        setThemesError('No themes available');
        console.error('[THEMES] ❌ No themes returned from API, raw response:', raw);
      }
    } catch (err: any) {
      // 🔥 FIX: On error, set empty array (not undefined) and show error
      setAvailableThemes([]);
      const errorMsg = err?.response?.data?.error || err?.message || 'Failed to load themes';
      setThemesError(errorMsg);
      console.error('[THEMES] ❌ Failed to load luxury themes:', {
        status: err?.response?.status,
        statusText: err?.response?.statusText,
        error: errorMsg,
        data: err?.response?.data
      });
    } finally {
      setThemesLoading(false);
    }
  };
  
  // 🎨 Handle Theme Selection Change - 🔥 FIX: Safe theme lookup
  const handleThemeChange = (themeId: string) => {
    setSelectedThemeId(themeId);
    const theme = availableThemes.find(t => t.id === themeId);
    if (theme && theme.default_fields) {
      setThemeFields(theme.default_fields);
    }
  };
  
  // 🎨 Preview Theme-based Email - 🔥 FIX: Better error handling and validation
  const handlePreviewTheme = async () => {
    // 🔥 FIX 3: Log theme_id for debugging
    console.log('[EmailsPage] Preview theme:', {
      themeId: selectedThemeId,
      leadId: selectedLead?.id,
      subject: themeFields.subject,
      hasBody: !!themeFields.body
    });
    
    // 🔥 FIX 3: Validate required fields before preview
    if (!selectedThemeId) {
      setError('בחר תבנית לפני תצוגה מקדימה');
      return;
    }
    
    if (!selectedLead) {
      setError('אנא בחר ליד לפני תצוגה מקדימה');
      return;
    }
    
    setThemePreviewLoading(true);
    setShowThemePreview(true);
    setError(null);
    
    try {
      const response = await axios.post('/api/email/render-theme', {
        theme_id: selectedThemeId,
        fields: themeFields,
        lead_id: selectedLead.id
      });
      
      // 🔥 FIX: Support both response formats (ok/success)
      if (response.data.ok === false || response.data.success === false) {
        throw new Error(response.data.error || 'Render failed');
      }
      
      const html = response.data.rendered?.html || response.data.html;
      if (!html) {
        throw new Error('No HTML returned from render');
      }
      
      setThemePreviewHtml(html);
    } catch (err: any) {
      console.error('[EmailsPage] Failed to preview theme:', err);
      const errorMsg = err.response?.data?.error || err.message || 'שגיאה בטעינת תצוגה מקדימה';
      setError(errorMsg);
      setShowThemePreview(false);  // Close preview on error
    } finally {
      setThemePreviewLoading(false);
    }
  };
  
  const searchLeads = async () => {
    try {
      setLeadSearchLoading(true);
      console.log('[EmailsPage] Searching leads with query:', leadSearchQuery);
      const response = await axios.get(`/api/leads?q=${encodeURIComponent(leadSearchQuery)}&pageSize=20`);
      // 🔥 FIX: API returns 'items' not 'leads' - support both for compatibility
      const leads = response.data.items || response.data.leads || [];
      console.log('[EmailsPage] ✅ Found', leads.length, 'leads for search');
      setLeadSearchResults(leads.map((l: any) => ({
        id: l.id,
        first_name: l.first_name || '',
        last_name: l.last_name || '',
        email: l.email || '',
        phone_e164: l.phone_e164 || ''
      })));
    } catch (err: any) {
      console.error('[EmailsPage] ❌ Failed to search leads:', err);
      console.error('[EmailsPage] Error details:', {
        status: err.response?.status,
        data: err.response?.data,
        message: err.message
      });
    } finally {
      setLeadSearchLoading(false);
    }
  };
  
  const loadAllLeads = async (append = false) => {
    try {
      setAllLeadsLoading(true);
      setError(null); // Clear any previous errors
      
      const params = new URLSearchParams();
      if (leadsFilter) params.append('q', leadsFilter);
      if (leadsStatusFilter) params.append('status', leadsStatusFilter);
      params.append('page', append ? (leadsPage + 1).toString() : '1');
      params.append('pageSize', '50'); // Load 50 leads per page
      
      console.log('[EmailsPage] Loading leads with params:', params.toString());
      
      const response = await axios.get(`/api/leads?${params.toString()}`);
      // 🔥 FIX: API returns 'items' not 'leads'
      const leads = response.data.items || [];
      const total = response.data.total || 0;
      
      console.log('[EmailsPage] ✅ Loaded leads successfully:', leads.length, 'total:', total);
      console.log('[EmailsPage] Response data:', { leads: leads.length, total, hasLeads: leads.length > 0 });
      
      const mappedLeads = leads.map((l: any) => ({
        id: l.id,
        first_name: l.first_name || '',
        last_name: l.last_name || '',
        email: l.email || '',
        phone_e164: l.phone_e164 || '',
        status: l.status || 'new',
        source: l.source || '',
        created_at: l.created_at || ''
      }));
      
      if (append) {
        setAllLeads(prev => [...prev, ...mappedLeads]);
        setLeadsPage(prev => prev + 1);
      } else {
        setAllLeads(mappedLeads);
        setLeadsPage(1);
      }
      
      console.log('[EmailsPage] State updated with', mappedLeads.length, 'leads');
      
      // Check if there are more leads to load
      const currentTotal = append ? allLeads.length + mappedLeads.length : mappedLeads.length;
      setLeadsHasMore(currentTotal < total);
    } catch (err: any) {
      console.error('[EmailsPage] ❌ Failed to load leads:', err);
      console.error('[EmailsPage] Error details:', {
        status: err.response?.status,
        statusText: err.response?.statusText,
        data: err.response?.data,
        message: err.message
      });
      const errorMsg = err.response?.data?.error || err.message || 'שגיאה בטעינת לידים';
      setError(errorMsg);
    } finally {
      setAllLeadsLoading(false);
    }
  };
  
  const handleUpdateLeadStatus = async (leadId: number, newStatus: string) => {
    try {
      setLeadStatusUpdating(leadId);
      await axios.patch(`/api/leads/${leadId}`, { status: newStatus });
      
      // Update local state
      setAllLeads(prev => prev.map(lead => 
        lead.id === leadId ? { ...lead, status: newStatus } : lead
      ));
      
      setSuccessMessage('סטטוס הליד עודכן בהצלחה');
      setTimeout(() => setSuccessMessage(null), 3000);
    } catch (err: any) {
      console.error('Failed to update lead status:', err);
      setError('שגיאה בעדכון סטטוס הליד');
      setTimeout(() => setError(null), 3000);
    } finally {
      setLeadStatusUpdating(null);
    }
  };
  
  const handleComposeEmail = async (e: React.FormEvent) => {
    e.preventDefault();
    
    // 🔥 FIX 3: Log before compose for debugging
    console.log('[COMPOSE] Starting email composition:', {
      themeId: selectedThemeId,
      leadId: selectedLead?.id,
      leadEmail: selectedLead?.email,
      subject: themeFields.subject,
      bodyLength: themeFields.body?.length || 0
    });
    
    // 🔥 FIX: Validate required fields
    if (!selectedLead) {
      setError('נא לבחור ליד');
      return;
    }
    
    if (!selectedThemeId) {
      setError('נא לבחור תבנית עיצוב');
      console.error('[COMPOSE] ❌ Missing theme_id');
      return;
    }
    
    if (!themeFields.subject.trim() || !themeFields.body.trim()) {
      setError('נא למלא לפחות נושא ותוכן המייל');
      return;
    }
    
    setComposeLoading(true);
    setError(null);
    
    try {
      // 🔥 FIX 4: First, render the theme with user fields
      console.log('[COMPOSE] Rendering theme:', selectedThemeId, 'for lead:', selectedLead.id);
      const renderResponse = await axios.post('/api/email/render-theme', {
        theme_id: selectedThemeId,
        fields: themeFields,
        lead_id: selectedLead.id
      });
      
      // 🔥 FIX: Support both response formats (ok/success)
      if (renderResponse.data.ok === false || renderResponse.data.success === false) {
        throw new Error(renderResponse.data.error || 'Render failed');
      }
      
      const rendered = renderResponse.data.rendered || renderResponse.data;
      
      if (!rendered || !rendered.html) {
        throw new Error('No HTML returned from render');
      }
      
      // 🔥 FIX 4: Validate HTML length before sending
      const htmlLength = rendered.html.length;
      console.log('[COMPOSE] ✅ Render successful, HTML length:', htmlLength);
      
      if (htmlLength < MIN_HTML_LENGTH_FRONTEND) {
        throw new Error(`Rendered HTML too short (${htmlLength} chars) - render may have failed`);
      }
      
      console.log('[COMPOSE] Sending email to lead...');
      
      // 🔥 FIX: Then send the rendered email
      await axios.post(`/api/leads/${selectedLead.id}/email`, {
        to_email: selectedLead.email,
        subject: rendered.subject,
        html: rendered.html,  // 🔥 FIX: Use 'html' field (primary)
        body_html: rendered.html,  // Also send as body_html for compatibility
        text: rendered.text,
        body_text: rendered.text
      });
      
      console.log('[COMPOSE] ✅ Email sent successfully');
      setSuccessMessage('מייל נשלח בהצלחה');
      setShowComposeModal(false);
      resetComposeForm();
      loadEmails();
    } catch (err: any) {
      console.error('[COMPOSE] ❌ Failed:', err);
      const errorMsg = err.response?.data?.error || err.message || 'שגיאה בשליחת מייל';
      setError(errorMsg);
    } finally {
      setComposeLoading(false);
    }
  };
  
  const handlePreviewTemplate = async (template: EmailTemplate) => {
    setPreviewTemplate(template);
    setPreviewLoading(true);
    setShowPreviewModal(true);
    
    try {
      const response = await axios.post(`/api/email/templates/${template.id}/preview`, {
        lead: { first_name: 'דוגמא', last_name: 'לקוח', email: 'example@test.com' }
      });
      setPreviewSubject(response.data.preview.subject);
      setPreviewHtml(response.data.preview.html);
    } catch (err: any) {
      console.error('Failed to preview template:', err);
      setError('שגיאה בטעינת תצוגה מקדימה');
    } finally {
      setPreviewLoading(false);
    }
  };
  
  // Bulk selection handlers
  const handleSelectLead = (leadId: number) => {
    setSelectedLeadIds(prev => {
      const newSet = new Set(prev);
      if (newSet.has(leadId)) {
        newSet.delete(leadId);
      } else {
        newSet.add(leadId);
      }
      return newSet;
    });
  };
  
  const handleSelectAllLeads = () => {
    const leadsWithEmail = allLeads.filter(lead => lead.email);
    if (selectedLeadIds.size === leadsWithEmail.length) {
      // Deselect all
      setSelectedLeadIds(new Set());
    } else {
      // Select all leads with email
      setSelectedLeadIds(new Set(leadsWithEmail.map(lead => lead.id)));
    }
  };
  
  const handleBulkCompose = () => {
    if (selectedLeadIds.size === 0) {
      setError('אנא בחר לפחות ליד אחד');
      return;
    }
    setShowBulkComposeModal(true);
  };
  
  const handleSendBulkEmail = async (e: React.FormEvent) => {
    e.preventDefault();
    
    if (selectedLeadIds.size === 0) {
      setError('אנא בחר לפחות ליד אחד');
      return;
    }
    
    if (!selectedThemeId) {
      setError('נא לבחור תבנית עיצוב');
      return;
    }
    
    if (!themeFields.subject.trim() || !themeFields.body.trim()) {
      setError('נא למלא לפחות נושא ותוכן המייל');
      return;
    }
    
    setBulkComposeLoading(true);
    setError(null);
    
    try {
      const selectedLeads = allLeads.filter(lead => selectedLeadIds.has(lead.id));
      let successCount = 0;
      let failCount = 0;
      
      console.log('[BULK] Sending to', selectedLeads.length, 'leads');
      
      // Send to each selected lead
      for (const lead of selectedLeads) {
        try {
          // First, render the theme with user fields
          const renderResponse = await axios.post('/api/email/render-theme', {
            theme_id: selectedThemeId,
            fields: themeFields,
            lead_id: lead.id
          });
          
          // 🔥 FIX: Support both response formats
          if (renderResponse.data.ok === false || renderResponse.data.success === false) {
            throw new Error(renderResponse.data.error || 'Render failed');
          }
          
          const rendered = renderResponse.data.rendered || renderResponse.data;
          
          if (!rendered || !rendered.html) {
            throw new Error('No HTML returned');
          }
          
          // Then send the rendered email
          await axios.post(`/api/leads/${lead.id}/email`, {
            to_email: lead.email,
            subject: rendered.subject,
            html: rendered.html,
            body_html: rendered.html,
            text: rendered.text,
            body_text: rendered.text
          });
          
          successCount++;
          console.log('[BULK] ✅ Sent to', lead.first_name, lead.last_name);
        } catch (err) {
          console.error(`[BULK] ❌ Failed to send email to lead ${lead.id}:`, err);
          failCount++;
        }
      }
      
      console.log('[BULK] Complete:', successCount, 'success', failCount, 'failed');
      
      if (successCount > 0) {
        setSuccessMessage(`${successCount} מיילים נשלחו בהצלחה${failCount > 0 ? `, ${failCount} נכשלו` : ''}`);
      } else {
        setError('כל המיילים נכשלו בשליחה');
      }
      
      setShowBulkComposeModal(false);
      setSelectedLeadIds(new Set());
      resetComposeForm();
      loadEmails();
    } catch (err: any) {
      console.error('[BULK] ❌ Bulk send failed:', err);
      setError(err.response?.data?.error || 'שגיאה בשליחת מיילים');
    } finally {
      setBulkComposeLoading(false);
    }
  };
  
  const resetComposeForm = () => {
    setSelectedLead(null);
    setLeadSearchQuery('');
    setLeadSearchResults([]);
    // Reset theme fields to default
    if (availableThemes.length > 0) {
      const defaultTheme = availableThemes.find(t => t.id === selectedThemeId);
      if (defaultTheme) {
        setThemeFields(defaultTheme.default_fields);
      }
    }
    setShowThemePreview(false);
    setThemePreviewHtml('');
  };
  
  const isAdmin = ['system_admin', 'owner', 'admin'].includes(user?.role || '');
  
  // Helper function for status badges
  const getStatusBadge = (status: string) => {
    const statusConfig: Record<string, { color: string; label: string }> = {
      'new': { color: 'bg-blue-100 text-blue-800', label: 'חדש' },
      'attempting': { color: 'bg-yellow-100 text-yellow-800', label: 'מנסה ליצור קשר' },
      'contacted': { color: 'bg-purple-100 text-purple-800', label: 'יצר קשר' },
      'qualified': { color: 'bg-indigo-100 text-indigo-800', label: 'מוסמך' },
      'won': { color: 'bg-green-100 text-green-800', label: 'נסגר' },
      'lost': { color: 'bg-red-100 text-red-800', label: 'אבד' },
      'unqualified': { color: 'bg-gray-100 text-gray-800', label: 'לא מוסמך' }
    };
    
    const config = statusConfig[status.toLowerCase()] || statusConfig['new'];
    return (
      <span className={`inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium ${config.color}`}>
        {config.label}
      </span>
    );
  };
  
  // Available status options for dropdown
  const statusOptions = [
    { value: '', label: 'כל הסטטוסים' },
    { value: 'new', label: 'חדש' },
    { value: 'attempting', label: 'מנסה ליצור קשר' },
    { value: 'contacted', label: 'יצר קשר' },
    { value: 'qualified', label: 'מוסמך' },
    { value: 'won', label: 'נסגר' },
    { value: 'lost', label: 'אבד' },
    { value: 'unqualified', label: 'לא מוסמך' }
  ];
  
  return (
    <div className="container mx-auto px-3 sm:px-4 py-4 sm:py-6 max-w-7xl" dir="rtl">
      {/* Header - Mobile Optimized */}
      <div className="mb-4 sm:mb-6">
        <h1 className="text-xl sm:text-3xl font-bold text-gray-900 flex items-center gap-2">
          <Mail className="w-6 h-6 sm:w-8 sm:h-8 text-blue-600" />
          מיילים
        </h1>
        <p className="text-sm sm:text-base text-gray-600 mt-1">
          ניהול מיילים ושליחות לליידים
        </p>
      </div>
      
      {/* SendGrid Status Banner */}
      {!sendgridAvailable && (
        <div className="mb-6 bg-amber-50 border border-amber-200 rounded-lg p-4 flex items-start gap-3">
          <AlertCircle className="w-5 h-5 text-amber-600 flex-shrink-0 mt-0.5" />
          <div>
            <h3 className="font-medium text-amber-900">מפתח SendGrid לא מוגדר</h3>
            <p className="text-sm text-amber-700 mt-1">
              יש להגדיר SENDGRID_API_KEY בהגדרות השרת כדי לשלוח מיילים
            </p>
          </div>
        </div>
      )}
      
      {/* Tabs */}
      <div className="bg-white rounded-lg shadow-sm border border-gray-200 mb-6">
        <div className="border-b border-gray-200 overflow-x-auto">
          <nav className="flex -mb-px min-w-max">
            <button
              onClick={() => setActiveTab('all')}
              className={`px-4 sm:px-6 py-3 text-xs sm:text-sm font-medium border-b-2 transition-colors whitespace-nowrap ${
                activeTab === 'all'
                  ? 'border-blue-500 text-blue-600'
                  : 'border-transparent text-gray-500 hover:text-gray-700 hover:border-gray-300'
              }`}
            >
              כל המיילים
            </button>
            <button
              onClick={() => setActiveTab('sent')}
              className={`px-4 sm:px-6 py-3 text-xs sm:text-sm font-medium border-b-2 transition-colors whitespace-nowrap ${
                activeTab === 'sent'
                  ? 'border-blue-500 text-blue-600'
                  : 'border-transparent text-gray-500 hover:text-gray-700 hover:border-gray-300'
              }`}
            >
              נשלחו
            </button>
            <button
              onClick={() => setActiveTab('leads')}
              className={`px-4 sm:px-6 py-3 text-xs sm:text-sm font-medium border-b-2 transition-colors whitespace-nowrap ${
                activeTab === 'leads'
                  ? 'border-blue-500 text-blue-600'
                  : 'border-transparent text-gray-500 hover:text-gray-700 hover:border-gray-300'
              }`}
            >
              <Mail className="w-4 h-4 inline ml-1 sm:ml-2" />
              <span className="hidden sm:inline">שלח ללידים</span>
              <span className="sm:hidden">שלח</span>
            </button>
            <button
              onClick={() => setActiveTab('templates')}
              className={`px-4 sm:px-6 py-3 text-xs sm:text-sm font-medium border-b-2 transition-colors whitespace-nowrap ${
                activeTab === 'templates'
                  ? 'border-blue-500 text-blue-600'
                  : 'border-transparent text-gray-500 hover:text-gray-700 hover:border-gray-300'
              }`}
            >
              תבניות
            </button>
            {isAdmin && (
              <button
                onClick={() => setActiveTab('settings')}
                className={`px-4 sm:px-6 py-3 text-xs sm:text-sm font-medium border-b-2 transition-colors whitespace-nowrap ${
                  activeTab === 'settings'
                    ? 'border-blue-500 text-blue-600'
                    : 'border-transparent text-gray-500 hover:text-gray-700 hover:border-gray-300'
                }`}
              >
                <Settings className="w-4 h-4 inline ml-1 sm:ml-2" />
                הגדרות
              </button>
            )}
          </nav>
        </div>
        
        {/* Content - Mobile Optimized */}
        <div className="p-3 sm:p-6">
          {activeTab === 'leads' ? (
            // Leads Tab - Send emails to leads
            <div>
              {/* Header with title and description */}
              <div className="mb-6">
                <h2 className="text-xl md:text-2xl font-semibold">שלח מיילים ללידים</h2>
                <p className="text-sm text-gray-600 mt-1">בחר ליד ושלח מייל מותאם אישית עם תבנית</p>
              </div>
              
              {/* Error Display */}
              {error && (
                <div className="mb-4 bg-red-50 border border-red-200 rounded-lg p-3 text-sm text-red-800 flex items-start gap-2">
                  <AlertCircle className="w-5 h-5 flex-shrink-0 mt-0.5" />
                  <div>
                    <p className="font-medium">שגיאה בטעינת לידים</p>
                    <p className="mt-1">{error}</p>
                  </div>
                </div>
              )}
              
              {/* Filters - Mobile Responsive */}
              <div className="mb-6 space-y-3 md:space-y-0 md:flex md:items-center md:gap-3">
                {/* Search Input */}
                <div className="relative flex-1">
                  <Search className="absolute right-3 top-1/2 transform -translate-y-1/2 w-5 h-5 text-gray-400" />
                  <input
                    type="text"
                    value={leadsFilter}
                    onChange={(e) => setLeadsFilter(e.target.value)}
                    placeholder="חפש לפי שם, טלפון או מייל..."
                    className="w-full pr-10 pl-4 py-2.5 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent"
                  />
                </div>
                
                {/* Status Filter */}
                <div className="md:w-64">
                  <select
                    value={leadsStatusFilter}
                    onChange={(e) => setLeadsStatusFilter(e.target.value)}
                    className="w-full px-4 py-2.5 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent appearance-none bg-white"
                  >
                    {statusOptions.map((option) => (
                      <option key={option.value} value={option.value}>
                        {option.label}
                      </option>
                    ))}
                  </select>
                </div>
                
                {/* Clear Filters Button */}
                {(leadsFilter || leadsStatusFilter) && (
                  <button
                    onClick={() => {
                      setLeadsFilter('');
                      setLeadsStatusFilter('');
                    }}
                    className="px-4 py-2.5 text-sm text-gray-600 hover:text-gray-900 border border-gray-300 rounded-lg hover:bg-gray-50 transition-colors"
                  >
                    נקה סינון
                  </button>
                )}
              </div>
              
              {/* Results Count + Load Template Button */}
              {!allLeadsLoading && allLeads.length > 0 && (
                <>
                  {/* Load from Template Button - Above everything */}
                  <div className="mb-4 bg-gradient-to-r from-purple-50 to-blue-50 border-2 border-purple-200 rounded-xl p-4 shadow-sm">
                    <div className="flex flex-col sm:flex-row sm:items-center gap-3">
                      <div className="flex-1">
                        <h3 className="text-sm font-bold text-purple-900 flex items-center gap-2">
                          <span className="text-xl">📋</span>
                          <span>טען הגדרות מהתבנית השמורה</span>
                        </h3>
                        <p className="text-xs text-purple-700 mt-1">
                          טען ברכה, פוטר וכפתור CTA מהתבנית שהגדרת
                        </p>
                      </div>
                      <button
                        type="button"
                        onClick={() => {
                          setThemeFields(prev => ({
                            ...prev,
                            greeting: templateDefaultGreeting,
                            cta_text: templateDefaultCtaText,
                            cta_url: templateDefaultCtaUrl,
                            footer: templateDefaultFooter
                          }));
                          setSelectedThemeId(templateDefaultTheme);
                          setSuccessMessage('הגדרות התבנית נטענו בהצלחה!');
                          setTimeout(() => setSuccessMessage(null), 3000);
                        }}
                        className="px-4 py-2.5 bg-purple-600 text-white rounded-lg hover:bg-purple-700 transition-colors font-medium flex items-center gap-2 whitespace-nowrap"
                      >
                        <span>📥</span>
                        <span>טען תבנית</span>
                      </button>
                    </div>
                  </div>

                  <div className="mb-4 flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3">
                    <div className="text-sm text-gray-600">
                      מציג {allLeads.length} לידים {leadsHasMore && '(טען עוד לראות יותר)'}
                      {selectedLeadIds.size > 0 && (
                        <span className="mr-2 text-blue-600 font-medium">
                          • {selectedLeadIds.size} נבחרו
                        </span>
                      )}
                    </div>
                    
                    {/* Bulk Actions */}
                    <div className="flex items-center gap-2 flex-wrap">
                      {/* Select All Checkbox */}
                      <label className="flex items-center gap-2 text-sm font-medium text-gray-700 cursor-pointer bg-white px-3 py-2 rounded-lg border border-gray-300 hover:bg-gray-50 transition-colors">
                        <input
                          type="checkbox"
                          checked={selectedLeadIds.size > 0 && selectedLeadIds.size === allLeads.filter(l => l.email).length}
                          onChange={handleSelectAllLeads}
                          className="w-4 h-4 text-blue-600 border-gray-300 rounded focus:ring-blue-500"
                        />
                        <span>בחר הכל ({allLeads.filter(l => l.email).length})</span>
                      </label>
                    
                    {/* Bulk Send Button */}
                    {selectedLeadIds.size > 0 && (
                      <button
                        onClick={handleBulkCompose}
                        className="flex items-center gap-2 px-4 py-2 bg-green-600 text-white rounded-lg hover:bg-green-700 transition-colors font-medium"
                      >
                        <Send className="w-4 h-4" />
                        <span>שלח ל-{selectedLeadIds.size} לידים</span>
                      </button>
                    )}
                  </div>
                </div>
                </>
              )}
              
              {/* Loading State */}
              {allLeadsLoading && allLeads.length === 0 ? (
                <div className="text-center py-12">
                  <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-blue-600 mx-auto"></div>
                  <p className="text-sm text-gray-600 mt-2">טוען לידים...</p>
                </div>
              ) : allLeads.length === 0 ? (
                <div className="text-center py-12">
                  <Mail className="w-16 h-16 text-gray-400 mx-auto mb-4" />
                  <p className="text-gray-600">לא נמצאו לידים</p>
                  {(leadsFilter || leadsStatusFilter) && (
                    <button
                      onClick={() => {
                        setLeadsFilter('');
                        setLeadsStatusFilter('');
                      }}
                      className="mt-4 text-blue-600 hover:text-blue-800 text-sm"
                    >
                      נקה סינון
                    </button>
                  )}
                </div>
              ) : (
                <>
                  {/* Leads Grid - Mobile Responsive */}
                  <div className="space-y-3">
                    {allLeads.map((lead) => (
                      <div 
                        key={lead.id} 
                        className={`border rounded-lg p-4 hover:shadow-md transition-shadow bg-white ${
                          selectedLeadIds.has(lead.id) ? 'border-blue-500 bg-blue-50' : 'border-gray-200'
                        }`}
                      >
                        {/* Mobile: Stack layout, Desktop: Flex layout */}
                        <div className="space-y-3 md:space-y-0 md:flex md:justify-between md:items-start">
                          {/* Checkbox + Lead Info */}
                          <div className="flex items-start gap-3 flex-1 min-w-0">
                            {/* Selection Checkbox */}
                            {lead.email && (
                              <div className="pt-1">
                                <input
                                  type="checkbox"
                                  checked={selectedLeadIds.has(lead.id)}
                                  onChange={() => handleSelectLead(lead.id)}
                                  className="w-5 h-5 text-blue-600 border-gray-300 rounded focus:ring-blue-500 cursor-pointer"
                                />
                              </div>
                            )}
                            
                            {/* Lead Details */}
                            <div className="flex-1 min-w-0">
                              <div className="flex items-center gap-2 flex-wrap mb-2">
                                <h3 className="font-medium text-gray-900 text-lg">
                                  {lead.first_name} {lead.last_name}
                                </h3>
                                {getStatusBadge(lead.status)}
                              </div>
                              
                              {/* Contact Info - Wrap on mobile */}
                              <div className="space-y-1 text-sm text-gray-600">
                                {lead.email && (
                                  <div className="flex items-center gap-1 break-all">
                                    <Mail className="w-4 h-4 flex-shrink-0" />
                                    <span>{lead.email}</span>
                                  </div>
                                )}
                                {lead.phone_e164 && (
                                  <div className="flex items-center gap-1">
                                    <span className="text-base">📞</span>
                                    <span className="text-left" dir="ltr">{lead.phone_e164}</span>
                                  </div>
                                )}
                              </div>
                              
                              {/* Status Update Dropdown */}
                              <div className="mt-3">
                                <select
                                  value={lead.status}
                                  onChange={(e) => handleUpdateLeadStatus(lead.id, e.target.value)}
                                  disabled={leadStatusUpdating === lead.id}
                                  className="text-sm px-3 py-1.5 border border-gray-300 rounded-md focus:ring-2 focus:ring-blue-500 focus:border-transparent disabled:bg-gray-100 disabled:cursor-not-allowed"
                                >
                                  <option value="new">חדש</option>
                                  <option value="attempting">מנסה ליצור קשר</option>
                                  <option value="contacted">יצר קשר</option>
                                  <option value="qualified">מוסמך</option>
                                  <option value="won">נסגר</option>
                                  <option value="lost">אבד</option>
                                  <option value="unqualified">לא מוסמך</option>
                                </select>
                                {leadStatusUpdating === lead.id && (
                                  <span className="mr-2 text-xs text-gray-500">מעדכן...</span>
                                )}
                              </div>
                            </div>
                          </div>
                          
                          {/* Action Button - Full width on mobile */}
                          <div className="md:mr-4 md:flex-shrink-0">
                            <button
                              onClick={() => {
                                setSelectedLead(lead);
                                setShowComposeModal(true);
                              }}
                              disabled={!lead.email}
                              className={`w-full md:w-auto px-4 py-2.5 rounded-lg transition-colors flex items-center justify-center gap-2 font-medium ${
                                lead.email
                                  ? 'bg-blue-600 text-white hover:bg-blue-700 active:bg-blue-800'
                                  : 'bg-gray-200 text-gray-400 cursor-not-allowed'
                              }`}
                            >
                              <Send className="w-4 h-4" />
                              <span>שלח מייל</span>
                            </button>
                          </div>
                        </div>
                        
                        {/* No Email Warning */}
                        {!lead.email && (
                          <div className="mt-3 text-xs text-red-600 bg-red-50 px-3 py-2 rounded">
                            ⚠️ אין כתובת מייל לליד זה
                          </div>
                        )}
                      </div>
                    ))}
                  </div>
                  
                  {/* Load More Button */}
                  {leadsHasMore && (
                    <div className="mt-6 text-center">
                      <button
                        onClick={() => loadAllLeads(true)}
                        disabled={allLeadsLoading}
                        className="px-6 py-3 bg-white border-2 border-blue-600 text-blue-600 rounded-lg hover:bg-blue-50 transition-colors disabled:opacity-50 disabled:cursor-not-allowed font-medium"
                      >
                        {allLeadsLoading ? (
                          <span className="flex items-center gap-2">
                            <div className="animate-spin rounded-full h-4 w-4 border-b-2 border-blue-600"></div>
                            טוען...
                          </span>
                        ) : (
                          'טען עוד לידים'
                        )}
                      </button>
                    </div>
                  )}
                </>
              )}
            </div>
          ) : activeTab === 'templates' ? (
            // Templates Tab - With sub-tabs for Design and Text templates
            <div className="space-y-6">
              {/* Template Sub-tabs */}
              <div className="flex items-center gap-4 border-b border-gray-200">
                <button
                  onClick={() => setTemplateSubTab('design')}
                  className={`py-3 px-1 border-b-2 font-medium text-sm transition-colors flex items-center gap-2 ${
                    templateSubTab === 'design'
                      ? 'border-blue-500 text-blue-600'
                      : 'border-transparent text-gray-500 hover:text-gray-700 hover:border-gray-300'
                  }`}
                >
                  <Settings className="h-4 w-4" />
                  הגדרות עיצוב
                </button>
                <button
                  onClick={() => setTemplateSubTab('text')}
                  className={`py-3 px-1 border-b-2 font-medium text-sm transition-colors flex items-center gap-2 ${
                    templateSubTab === 'text'
                      ? 'border-blue-500 text-blue-600'
                      : 'border-transparent text-gray-500 hover:text-gray-700 hover:border-gray-300'
                  }`}
                >
                  <FileText className="h-4 w-4" />
                  תבניות טקסט ({textTemplates.length})
                </button>
              </div>

              {/* Design Templates Sub-tab */}
              {templateSubTab === 'design' && (
            <div className="max-w-3xl">
              <div className="mb-6">
                <h2 className="text-2xl font-semibold">הגדרות תבנית כלליות</h2>
                <p className="text-sm text-gray-600 mt-1">
                  ערוך את ההגדרות הכלליות של התבנית: פוטר, ברכה, צבעים ועיצוב
                </p>
                <p className="text-xs text-gray-500 mt-1">
                  💡 ההגדרות כאן משפיעות על המראה והטקסט הכללי - לא על תוכן ההודעות הספציפיות
                </p>
              </div>
              
              {error && (
                <div className="mb-4 bg-red-50 border border-red-200 rounded-lg p-3 text-sm text-red-800 flex items-start gap-2">
                  <AlertCircle className="w-5 h-5 flex-shrink-0" />
                  <span>{error}</span>
                </div>
              )}
              
              {successMessage && (
                <div className="mb-4 bg-green-50 border border-green-200 rounded-lg p-3 text-sm text-green-800 flex items-start gap-2">
                  <CheckCircle className="w-5 h-5 flex-shrink-0" />
                  <span>{successMessage}</span>
                </div>
              )}
              
              <form onSubmit={handleSaveTemplateSettings} className="space-y-6">
                {/* Theme Selection */}
                <div className="bg-gradient-to-br from-purple-50 to-blue-50 border-2 border-purple-200 rounded-xl p-5 shadow-sm">
                  <label className="block text-base font-bold text-purple-900 mb-3 flex items-center gap-2">
                    <span className="text-2xl">🎨</span>
                    <span>בחר עיצוב ברירת מחדל (Luxury Theme)</span>
                  </label>
                  <p className="text-xs text-purple-700 mb-3">
                    העיצוב הזה ישמש כברירת מחדל בשליחת מיילים
                  </p>
                  
                  {themesLoading ? (
                    <div className="text-sm text-gray-600">טוען עיצובים...</div>
                  ) : themesError ? (
                    <div className="text-sm text-red-600 bg-red-50 p-3 rounded-lg">
                      ⚠️ {themesError}
                    </div>
                  ) : availableThemes.length === 0 ? (
                    <div className="text-sm text-amber-600 bg-amber-50 p-3 rounded-lg">
                      ⚠️ לא נמצאו עיצובים
                    </div>
                  ) : (
                    <select
                      value={templateDefaultTheme}
                      onChange={(e) => setTemplateDefaultTheme(e.target.value)}
                      className="w-full px-4 py-3.5 border-2 border-purple-300 rounded-xl focus:ring-4 focus:ring-purple-200 focus:border-purple-500 bg-white font-medium shadow-sm text-base"
                    >
                      {availableThemes.map((theme) => (
                        <option key={theme.id} value={theme.id}>
                          {theme.name} - {theme.description}
                        </option>
                      ))}
                    </select>
                  )}
                </div>

                {/* Default Greeting */}
                <div className="bg-white border-2 border-gray-200 rounded-xl p-5">
                  <label className="block text-base font-bold text-gray-900 mb-2 flex items-center gap-2">
                    <span className="text-2xl">👋</span>
                    <span>ברכה כללית (ברירת מחדל)</span>
                  </label>
                  <p className="text-xs text-gray-600 mb-3">
                    הברכה שתופיע בכל מייל. השתמש ב-{"{{lead.first_name}}"} לשם הליד
                  </p>
                  <input
                    type="text"
                    value={templateDefaultGreeting}
                    onChange={(e) => setTemplateDefaultGreeting(e.target.value)}
                    placeholder="שלום {{lead.first_name}},"
                    className="w-full px-4 py-3 border-2 border-gray-300 rounded-lg focus:ring-4 focus:ring-blue-200 focus:border-blue-500 shadow-sm"
                  />
                </div>

                {/* Default CTA */}
                <div className="bg-white border-2 border-gray-200 rounded-xl p-5">
                  <label className="block text-base font-bold text-gray-900 mb-2 flex items-center gap-2">
                    <span className="text-2xl">🔘</span>
                    <span>כפתור קריאה לפעולה (CTA) ברירת מחדל</span>
                  </label>
                  <p className="text-xs text-gray-600 mb-3">
                    הטקסט והקישור שיופיעו בכפתור (אופציונלי)
                  </p>
                  <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                    <div>
                      <label className="block text-xs font-medium text-gray-700 mb-1">
                        טקסט הכפתור
                      </label>
                      <input
                        type="text"
                        value={templateDefaultCtaText}
                        onChange={(e) => setTemplateDefaultCtaText(e.target.value)}
                        placeholder="צור קשר עכשיו"
                        className="w-full px-3 py-2.5 border-2 border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-200 focus:border-blue-500 shadow-sm"
                      />
                    </div>
                    <div>
                      <label className="block text-xs font-medium text-gray-700 mb-1">
                        קישור
                      </label>
                      <input
                        type="url"
                        value={templateDefaultCtaUrl}
                        onChange={(e) => setTemplateDefaultCtaUrl(e.target.value)}
                        placeholder="https://example.com"
                        className="w-full px-3 py-2.5 border-2 border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-200 focus:border-blue-500 shadow-sm"
                      />
                    </div>
                  </div>
                </div>

                {/* Footer Text */}
                <div className="bg-gradient-to-br from-yellow-50 to-orange-50 border-2 border-yellow-300 rounded-xl p-5 shadow-md">
                  <label className="block text-base font-bold text-yellow-900 mb-2 flex items-center gap-2">
                    <span className="text-2xl">⚠️</span>
                    <span>פוטר כללי למיילים *</span>
                  </label>
                  <p className="text-xs text-yellow-800 mb-3">
                    הפוטר שיופיע בכל מייל שנשלח. חובה לכלול אפשרות להסרה מהרשימה
                  </p>
                  <textarea
                    value={templateDefaultFooter}
                    onChange={(e) => setTemplateDefaultFooter(e.target.value)}
                    placeholder="אם אינך מעוניין לקבל הודעות נוספות, אנא לחץ כאן להסרה מהרשימה.&#10;&#10;© {{business.name}} | כל הזכויות שמורות"
                    rows={4}
                    className="w-full px-4 py-3 border-2 border-yellow-400 rounded-lg focus:ring-4 focus:ring-yellow-200 focus:border-yellow-500 text-sm shadow-sm resize-none"
                    required
                  />
                  <p className="text-xs text-yellow-700 mt-2">
                    💡 השתמש ב-{"{{business.name}}"} לשם העסק
                  </p>
                </div>

                {/* Brand Colors */}
                <div className="bg-white border-2 border-gray-200 rounded-xl p-5">
                  <label className="block text-base font-bold text-gray-900 mb-2 flex items-center gap-2">
                    <span className="text-2xl">🎨</span>
                    <span>צבע מותג (אופציונלי)</span>
                  </label>
                  <p className="text-xs text-gray-600 mb-3">
                    הצבע העיקרי שישמש בעיצוב המיילים (למשל: כפתורים, קישורים)
                  </p>
                  <div className="flex items-center gap-3">
                    <input
                      type="color"
                      value={templateBrandColor}
                      onChange={(e) => setTemplateBrandColor(e.target.value)}
                      className="w-16 h-12 border-2 border-gray-300 rounded-lg cursor-pointer"
                    />
                    <input
                      type="text"
                      value={templateBrandColor}
                      onChange={(e) => setTemplateBrandColor(e.target.value)}
                      placeholder="#2563EB"
                      className="flex-1 px-3 py-2.5 border-2 border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-200 focus:border-blue-500 shadow-sm font-mono"
                    />
                  </div>
                </div>

                {/* Save Button */}
                <div className="flex gap-3 pt-4">
                  <button
                    type="submit"
                    disabled={saveLoading}
                    className="flex-1 bg-gradient-to-r from-blue-600 to-purple-600 text-white px-6 py-4 rounded-xl hover:from-blue-700 hover:to-purple-700 transition-all disabled:from-gray-400 disabled:to-gray-400 disabled:cursor-not-allowed font-bold text-lg flex items-center justify-center gap-2 shadow-lg"
                  >
                    {saveLoading ? (
                      <>
                        <div className="animate-spin rounded-full h-5 w-5 border-b-2 border-white"></div>
                        <span>שומר...</span>
                      </>
                    ) : (
                      <>
                        <Save className="w-5 h-5" />
                        <span>שמור הגדרות תבנית</span>
                      </>
                    )}
                  </button>
                </div>
              </form>
              
              {/* Info Section */}
              <div className="mt-8 bg-blue-50 border-l-4 border-blue-500 p-4 rounded-lg">
                <div className="flex items-start gap-3">
                  <div className="flex-shrink-0">
                    <Mail className="w-5 h-5 text-blue-600" />
                  </div>
                  <div>
                    <h3 className="text-sm font-medium text-blue-900">
                      💡 מה ההבדל בין הגדרות תבנית לתוכן ההודעה?
                    </h3>
                    <ul className="text-sm text-blue-700 mt-2 space-y-1 list-disc list-inside">
                      <li><strong>הגדרות עיצוב (כאן)</strong> - עיצוב, ברכה כללית, פוטר, צבעים - משפיע על כל המיילים</li>
                      <li><strong>תבניות טקסט</strong> - תוכן מוכן כמו הצעות מחיר, מחירונים, ברכות</li>
                      <li><strong>תוכן הודעה (בשליחה)</strong> - נושא ותוכן ספציפי לכל מייל שאתה שולח</li>
                    </ul>
                  </div>
                </div>
              </div>
            </div>
              )}

              {/* Text Templates Sub-tab */}
              {templateSubTab === 'text' && (
                <div className="max-w-3xl">
                  <div className="flex justify-between items-center mb-6">
                    <div>
                      <h2 className="text-2xl font-semibold">תבניות טקסט</h2>
                      <p className="text-sm text-gray-600 mt-1">
                        צור תבניות מוכנות לתוכן כמו הצעות מחיר, מחירונים, ברכות ועוד
                      </p>
                    </div>
                    <button
                      onClick={() => {
                        setEditingTextTemplate(null);
                        setNewTextTemplateName('');
                        setNewTextTemplateCategory('general');
                        setNewTextTemplateSubject('');
                        setNewTextTemplateBody('');
                        setNewTextTemplateButtonText('');
                        setNewTextTemplateButtonLink('');
                        setNewTextTemplateFooter('');
                        setShowCreateTextTemplate(true);
                      }}
                      className="flex items-center gap-2 px-4 py-2.5 bg-blue-600 text-white rounded-lg hover:bg-blue-700 transition-colors font-medium"
                    >
                      <Plus className="w-4 h-4" />
                      תבנית חדשה
                    </button>
                  </div>

                  {error && (
                    <div className="mb-4 bg-red-50 border border-red-200 rounded-lg p-3 text-sm text-red-800 flex items-start gap-2">
                      <AlertCircle className="w-5 h-5 flex-shrink-0" />
                      <span>{error}</span>
                    </div>
                  )}
                  
                  {successMessage && (
                    <div className="mb-4 bg-green-50 border border-green-200 rounded-lg p-3 text-sm text-green-800 flex items-start gap-2">
                      <CheckCircle className="w-5 h-5 flex-shrink-0" />
                      <span>{successMessage}</span>
                    </div>
                  )}

                  {textTemplatesLoading ? (
                    <div className="text-center py-12">
                      <RefreshCw className="w-8 h-8 animate-spin mx-auto text-gray-400" />
                      <p className="text-sm text-gray-600 mt-2">טוען תבניות...</p>
                    </div>
                  ) : textTemplates.length === 0 ? (
                    <div className="text-center py-12 bg-gray-50 rounded-xl border-2 border-dashed border-gray-300">
                      <FileText className="w-12 h-12 mx-auto mb-3 text-gray-400" />
                      <p className="text-gray-600 font-medium">אין תבניות טקסט</p>
                      <p className="text-sm text-gray-500 mt-1">לחץ על "תבנית חדשה" כדי ליצור את התבנית הראשונה שלך</p>
                    </div>
                  ) : (
                    <div className="space-y-4">
                      {textTemplates.map((template) => (
                        <div
                          key={template.id}
                          className="bg-white border-2 border-gray-200 rounded-xl p-5 hover:border-blue-300 transition-colors"
                        >
                          <div className="flex justify-between items-start">
                            <div className="flex-1 min-w-0">
                              <div className="flex items-center gap-2 mb-2">
                                <h3 className="font-semibold text-gray-900">{template.name}</h3>
                                <span className="px-2 py-0.5 bg-gray-100 text-gray-600 text-xs rounded-full">
                                  {template.category === 'quote' ? 'הצעת מחיר' :
                                   template.category === 'greeting' ? 'ברכה' :
                                   template.category === 'pricing' ? 'מחירים' :
                                   template.category === 'info' ? 'מידע' : 'כללי'}
                                </span>
                              </div>
                              {template.subject_line && (
                                <p className="text-sm text-blue-600 mb-2">
                                  📧 נושא: {template.subject_line}
                                </p>
                              )}
                              <p className="text-sm text-gray-600 whitespace-pre-wrap overflow-hidden" style={{ display: '-webkit-box', WebkitLineClamp: 3, WebkitBoxOrient: 'vertical' }}>
                                {template.body_text}
                              </p>
                            </div>
                            <div className="flex items-center gap-2 mr-4 flex-shrink-0">
                              <button
                                onClick={() => handleUseTextTemplate(template)}
                                className="flex items-center gap-1 px-3 py-1.5 bg-green-600 text-white text-sm rounded-lg hover:bg-green-700 transition-colors"
                              >
                                <Send className="w-3 h-3" />
                                השתמש
                              </button>
                              <button
                                onClick={() => handleEditTextTemplate(template)}
                                className="p-2 text-gray-600 hover:text-blue-600 hover:bg-blue-50 rounded-lg transition-colors"
                              >
                                <Edit2 className="w-4 h-4" />
                              </button>
                              <button
                                onClick={() => handleDeleteTextTemplate(template.id)}
                                className="p-2 text-gray-600 hover:text-red-600 hover:bg-red-50 rounded-lg transition-colors"
                              >
                                <Trash2 className="w-4 h-4" />
                              </button>
                            </div>
                          </div>
                        </div>
                      ))}
                    </div>
                  )}

                  {/* Create/Edit Text Template Modal */}
                  {showCreateTextTemplate && (
                    <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center p-4 z-50" onClick={() => setShowCreateTextTemplate(false)}>
                      <div className="bg-white rounded-xl max-w-2xl w-full max-h-[90vh] overflow-hidden shadow-2xl" onClick={(e) => e.stopPropagation()}>
                        <div className="p-6 border-b border-gray-200 bg-gradient-to-r from-blue-600 to-purple-600 text-white">
                          <div className="flex justify-between items-center">
                            <h2 className="text-xl font-bold">
                              {editingTextTemplate ? 'ערוך תבנית טקסט' : 'תבנית טקסט חדשה'}
                            </h2>
                            <button
                              onClick={() => setShowCreateTextTemplate(false)}
                              className="text-white hover:bg-white/20 rounded-lg p-2 transition-colors"
                            >
                              <X className="w-5 h-5" />
                            </button>
                          </div>
                        </div>
                        
                        <div className="p-6 space-y-4 overflow-y-auto max-h-[calc(90vh-150px)]">
                          <div>
                            <label className="block text-sm font-medium text-gray-700 mb-2">
                              שם התבנית *
                            </label>
                            <input
                              type="text"
                              value={newTextTemplateName}
                              onChange={(e) => setNewTextTemplateName(e.target.value)}
                              className="w-full px-4 py-2.5 border-2 border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
                              placeholder="לדוגמה: הצעת מחיר סטנדרטית"
                            />
                          </div>
                          
                          <div>
                            <label className="block text-sm font-medium text-gray-700 mb-2">
                              קטגוריה
                            </label>
                            <select
                              value={newTextTemplateCategory}
                              onChange={(e) => setNewTextTemplateCategory(e.target.value)}
                              className="w-full px-4 py-2.5 border-2 border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
                            >
                              <option value="general">כללי</option>
                              <option value="quote">הצעת מחיר</option>
                              <option value="greeting">ברכה</option>
                              <option value="pricing">מחירים</option>
                              <option value="info">מידע</option>
                            </select>
                          </div>
                          
                          <div>
                            <label className="block text-sm font-medium text-gray-700 mb-2">
                              נושא המייל (אופציונלי)
                            </label>
                            <input
                              type="text"
                              value={newTextTemplateSubject}
                              onChange={(e) => setNewTextTemplateSubject(e.target.value)}
                              className="w-full px-4 py-2.5 border-2 border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
                              placeholder="לדוגמה: הצעת מחיר מ-{{business.name}}"
                            />
                            <p className="text-xs text-gray-500 mt-1">
                              💡 ניתן להשתמש ב-{"{{lead.first_name}}"}, {"{{business.name}}"} ועוד
                            </p>
                          </div>
                          
                          <div>
                            <label className="block text-sm font-medium text-gray-700 mb-2">
                              תוכן התבנית *
                            </label>
                            <textarea
                              value={newTextTemplateBody}
                              onChange={(e) => setNewTextTemplateBody(e.target.value)}
                              className="w-full px-4 py-3 border-2 border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500 resize-none"
                              rows={8}
                              placeholder="כתוב כאן את תוכן התבנית..."
                              dir="rtl"
                            />
                          </div>
                          
                          {/* Button Settings */}
                          <div className="grid grid-cols-1 md:grid-cols-2 gap-4 p-4 bg-gray-50 rounded-lg">
                            <div>
                              <label className="block text-sm font-medium text-gray-700 mb-2">
                                טקסט כפתור (אופציונלי)
                              </label>
                              <input
                                type="text"
                                value={newTextTemplateButtonText}
                                onChange={(e) => setNewTextTemplateButtonText(e.target.value)}
                                className="w-full px-4 py-2.5 border-2 border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
                                placeholder="לדוגמה: צפה בהצעת מחיר"
                              />
                            </div>
                            <div>
                              <label className="block text-sm font-medium text-gray-700 mb-2">
                                קישור כפתור (אופציונלי)
                              </label>
                              <input
                                type="url"
                                value={newTextTemplateButtonLink}
                                onChange={(e) => setNewTextTemplateButtonLink(e.target.value)}
                                className="w-full px-4 py-2.5 border-2 border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
                                placeholder="https://example.com/quote"
                                dir="ltr"
                              />
                            </div>
                          </div>
                          
                          {/* Footer */}
                          <div>
                            <label className="block text-sm font-medium text-gray-700 mb-2">
                              פוטר מייל (אופציונלי)
                            </label>
                            <textarea
                              value={newTextTemplateFooter}
                              onChange={(e) => setNewTextTemplateFooter(e.target.value)}
                              className="w-full px-4 py-3 border-2 border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500 resize-none"
                              rows={3}
                              placeholder="לדוגמה: בברכה, צוות {{business.name}} | טלפון: 050-1234567"
                              dir="rtl"
                            />
                            <p className="text-xs text-gray-500 mt-1">
                              💡 טקסט שיופיע בתחתית המייל
                            </p>
                          </div>
                          
                          <div className="flex justify-end gap-3 pt-4 border-t border-gray-200">
                            <button
                              onClick={() => setShowCreateTextTemplate(false)}
                              className="px-4 py-2.5 border border-gray-300 text-gray-700 rounded-lg hover:bg-gray-50 transition-colors"
                            >
                              ביטול
                            </button>
                            <button
                              onClick={handleSaveTextTemplate}
                              disabled={savingTextTemplate || !newTextTemplateName.trim() || !newTextTemplateBody.trim()}
                              className="flex items-center gap-2 px-5 py-2.5 bg-blue-600 text-white rounded-lg hover:bg-blue-700 disabled:bg-gray-400 disabled:cursor-not-allowed transition-colors font-medium"
                            >
                              {savingTextTemplate ? (
                                <>
                                  <RefreshCw className="w-4 h-4 animate-spin" />
                                  שומר...
                                </>
                              ) : (
                                <>
                                  <CheckCircle className="w-4 h-4" />
                                  {editingTextTemplate ? 'עדכן תבנית' : 'צור תבנית'}
                                </>
                              )}
                            </button>
                          </div>
                        </div>
                      </div>
                    </div>
                  )}
                </div>
              )}
            </div>
          ) : activeTab === 'settings' ? (
            // Settings Tab
            <div className="max-w-2xl">
              <h2 className="text-xl font-semibold mb-4">הגדרות מייל</h2>
              
              {error && (
                <div className="mb-4 bg-red-50 border border-red-200 rounded-lg p-3 text-sm text-red-800">
                  {error}
                </div>
              )}
              
              {successMessage && (
                <div className="mb-4 bg-green-50 border border-green-200 rounded-lg p-3 text-sm text-green-800">
                  {successMessage}
                </div>
              )}
              
              <form onSubmit={handleSaveSettings} className="space-y-4">
                {/* From Email - Read Only */}
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">
                    כתובת שולח (From Email)
                  </label>
                  <input
                    type="text"
                    value="noreply@prosaas.pro"
                    disabled
                    className="w-full px-3 py-2 border border-gray-300 rounded-lg bg-gray-50 text-gray-600"
                  />
                  <p className="text-xs text-gray-500 mt-1">
                    🔒 כתובת זו נעולה ומאומתת ב-SendGrid. המיילים ישלחו מכתובת זו.
                  </p>
                </div>
                
                {/* From Name */}
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">
                    שם שולח (From Name) *
                  </label>
                  <input
                    type="text"
                    value={fromName}
                    onChange={(e) => setFromName(e.target.value)}
                    placeholder="שם העסק שלך"
                    className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent"
                    required
                  />
                  <p className="text-xs text-gray-500 mt-1">
                    השם שהלקוח יראה בתיבת הדואר שלו
                  </p>
                </div>
                
                {/* Reply To */}
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">
                    Reply-To (כתובת תשובה)
                  </label>
                  <input
                    type="email"
                    value={replyTo}
                    onChange={(e) => setReplyTo(e.target.value)}
                    placeholder="contact@mybusiness.com"
                    className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent"
                  />
                  <p className="text-xs text-gray-500 mt-1">
                    כתובת המייל שאליה יגיעו תשובות הלקוחות (יכולה להיות כל כתובת)
                  </p>
                </div>
                
                {/* Enabled Toggle */}
                <div className="flex items-center">
                  <input
                    type="checkbox"
                    id="is_enabled"
                    checked={isEnabled}
                    onChange={(e) => setIsEnabled(e.target.checked)}
                    className="w-4 h-4 text-blue-600 border-gray-300 rounded focus:ring-blue-500"
                  />
                  <label htmlFor="is_enabled" className="mr-2 text-sm font-medium text-gray-700">
                    הפעל שליחת מיילים
                  </label>
                </div>
                
                <button
                  type="submit"
                  disabled={saveLoading || !sendgridAvailable}
                  className="w-full bg-blue-600 text-white px-4 py-2 rounded-lg hover:bg-blue-700 transition-colors disabled:bg-gray-400 disabled:cursor-not-allowed"
                >
                  {saveLoading ? 'שומר...' : 'שמור הגדרות'}
                </button>
              </form>
              
              {/* Test Email Section */}
              {configured && sendgridAvailable && (
                <div className="mt-8 pt-8 border-t border-gray-200">
                  <h3 className="text-lg font-semibold mb-4">שלח מייל בדיקה</h3>
                  <div className="flex gap-2">
                    <input
                      type="email"
                      value={testEmail}
                      onChange={(e) => setTestEmail(e.target.value)}
                      placeholder="your@email.com"
                      className="flex-1 px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent"
                    />
                    <button
                      onClick={handleTestEmail}
                      disabled={testLoading || !testEmail.trim()}
                      className="bg-green-600 text-white px-4 py-2 rounded-lg hover:bg-green-700 transition-colors disabled:bg-gray-400 disabled:cursor-not-allowed flex items-center gap-2"
                    >
                      <Send className="w-4 h-4" />
                      {testLoading ? 'שולח...' : 'שלח'}
                    </button>
                  </div>
                </div>
              )}
            </div>
          ) : (
            // Emails List Tab
            <>
              {!configured ? (
                <div className="text-center py-12">
                  <Mail className="w-16 h-16 text-gray-400 mx-auto mb-4" />
                  <h3 className="text-lg font-medium text-gray-900 mb-2">
                    מערכת המיילים לא מוגדרת
                  </h3>
                  <p className="text-gray-600 mb-4">
                    יש להגדיר את הגדרות המייל כדי להתחיל לשלוח מיילים
                  </p>
                  {isAdmin && (
                    <button
                      onClick={() => setActiveTab('settings')}
                      className="bg-blue-600 text-white px-6 py-2 rounded-lg hover:bg-blue-700 transition-colors inline-flex items-center gap-2"
                    >
                      <Settings className="w-4 h-4" />
                      עבור להגדרות
                    </button>
                  )}
                </div>
              ) : (
                <>
                  {/* Filters */}
                  <div className="mb-4 flex gap-4">
                    <input
                      type="text"
                      placeholder="חיפוש..."
                      value={searchQuery}
                      onChange={(e) => setSearchQuery(e.target.value)}
                      className="flex-1 px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent"
                    />
                    <select
                      value={statusFilter}
                      onChange={(e) => setStatusFilter(e.target.value)}
                      className="px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent"
                    >
                      <option value="">כל הסטטוסים</option>
                      <option value="queued">בתור</option>
                      <option value="sent">נשלח</option>
                      <option value="failed">נכשל</option>
                    </select>
                  </div>
                  
                  {/* Emails Table */}
                  {loading ? (
                    <div className="text-center py-12">
                      <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-blue-600 mx-auto"></div>
                    </div>
                  ) : emails.length === 0 ? (
                    <div className="text-center py-12">
                      <Mail className="w-16 h-16 text-gray-400 mx-auto mb-4" />
                      <p className="text-gray-600">אין מיילים להצגה</p>
                    </div>
                  ) : (
                    <div className="overflow-x-auto">
                      <table className="min-w-full divide-y divide-gray-200">
                        <thead className="bg-gray-50">
                          <tr>
                            <th className="px-4 py-3 text-right text-xs font-medium text-gray-500 uppercase">תאריך</th>
                            <th className="px-4 py-3 text-right text-xs font-medium text-gray-500 uppercase">אל</th>
                            <th className="px-4 py-3 text-right text-xs font-medium text-gray-500 uppercase">נושא</th>
                            <th className="px-4 py-3 text-right text-xs font-medium text-gray-500 uppercase">ליד</th>
                            <th className="px-4 py-3 text-right text-xs font-medium text-gray-500 uppercase">סטטוס</th>
                            <th className="px-4 py-3 text-right text-xs font-medium text-gray-500 uppercase">נשלח על ידי</th>
                          </tr>
                        </thead>
                        <tbody className="bg-white divide-y divide-gray-200">
                          {emails.map((email) => (
                            <tr key={email.id} className="hover:bg-gray-50">
                              <td className="px-4 py-3 text-sm text-gray-900 whitespace-nowrap">
                                {new Date(email.created_at).toLocaleDateString('he-IL')}
                              </td>
                              <td className="px-4 py-3 text-sm text-gray-900">
                                {email.to_email}
                              </td>
                              <td className="px-4 py-3 text-sm text-gray-900">
                                {email.subject}
                                {email.error && (
                                  <div className="text-xs text-red-600 mt-1">{email.error}</div>
                                )}
                              </td>
                              <td className="px-4 py-3 text-sm text-gray-900">
                                {email.lead_name || '-'}
                              </td>
                              <td className="px-4 py-3 text-sm">
                                <StatusBadge status={email.status} />
                              </td>
                              <td className="px-4 py-3 text-sm text-gray-600">
                                {email.created_by?.name || '-'}
                              </td>
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    </div>
                  )}
                </>
              )}
            </>
          )}
        </div>
      </div>
      
      {/* Compose Email Button (Floating) */}
      {configured && (activeTab === 'all' || activeTab === 'sent') && (
        <button
          onClick={() => setShowComposeModal(true)}
          className="fixed bottom-8 left-8 bg-blue-600 text-white p-4 rounded-full shadow-lg hover:bg-blue-700 transition-colors flex items-center gap-2 z-10"
        >
          <Plus className="w-6 h-6" />
          <span className="font-medium">שליחת מייל חדש</span>
        </button>
      )}
      
      {/* Compose Email Modal */}
      {showComposeModal && (
        <div className="fixed inset-0 bg-black/60 backdrop-blur-sm flex items-center justify-center z-50 p-0 sm:p-4 overflow-y-auto">
          <div className="bg-white w-full h-full sm:h-auto sm:rounded-2xl sm:shadow-2xl sm:max-w-4xl sm:max-h-[95vh] overflow-y-auto">
            <div className="sticky top-0 bg-gradient-to-r from-blue-600 to-purple-600 text-white p-4 sm:p-6 z-10 shadow-lg sm:rounded-t-2xl">
              {/* Header - Mobile Optimized */}
              <div className="flex justify-between items-center">
                <div className="flex-1">
                  <h2 className="text-xl sm:text-2xl font-bold flex items-center gap-2">
                    <Mail className="w-5 h-5 sm:w-6 sm:h-6" />
                    שליחת מייל חדש
                  </h2>
                  <p className="text-xs sm:text-sm text-blue-100 mt-1">
                    עיצוב יוקרתי וקל לשימוש
                  </p>
                </div>
                <button
                  onClick={() => {
                    setShowComposeModal(false);
                    resetComposeForm();
                  }}
                  className="text-white hover:bg-white/20 rounded-lg p-2 transition-colors shrink-0"
                  aria-label="סגור"
                >
                  <X className="w-6 h-6" />
                </button>
              </div>
            </div>
            
            <div className="p-4 sm:p-6 pb-24 sm:pb-6">
              {/* Error Message - Mobile Optimized */}
              {error && (
                <div className="mb-4 bg-red-50 border-l-4 border-red-500 rounded-lg p-3 sm:p-4 text-sm sm:text-base text-red-800 flex items-start gap-2 animate-shake">
                  <AlertCircle className="w-5 h-5 shrink-0 mt-0.5" />
                  <span>{error}</span>
                </div>
              )}
              
              <form onSubmit={handleComposeEmail} className="space-y-4 sm:space-y-5 pb-24 sm:pb-0">
                {/* 🎨 Luxury Theme Selector - Mobile Optimized */}
                <div className="bg-gradient-to-br from-purple-50 to-blue-50 border-2 border-purple-200 rounded-xl p-3 sm:p-4 shadow-sm">
                  <label className="block text-sm sm:text-base font-bold text-purple-900 mb-2 flex items-center gap-2">
                    <span className="text-xl sm:text-2xl">🎨</span>
                    <span>בחר עיצוב יוקרתי למייל</span>
                  </label>
                  
                  {themesLoading ? (
                    <div className="flex items-center gap-2 text-sm text-gray-600">
                      <div className="animate-spin rounded-full h-4 w-4 border-b-2 border-purple-600"></div>
                      <span>טוען עיצובים...</span>
                    </div>
                  ) : themesError ? (
                    <div className="text-sm text-red-600 bg-red-50 p-3 rounded-lg border border-red-200">
                      ⚠️ שגיאה בטעינת עיצובים: {themesError}
                      <button
                        type="button"
                        onClick={loadLuxuryThemes}
                        className="mr-2 text-red-700 underline hover:text-red-900"
                      >
                        נסה שוב
                      </button>
                    </div>
                  ) : availableThemes.length === 0 ? (
                    <div className="text-sm text-amber-600 bg-amber-50 p-3 rounded-lg border border-amber-200">
                      ⚠️ לא נמצאו עיצובים זמינים
                      <button
                        type="button"
                        onClick={loadLuxuryThemes}
                        className="mr-2 text-amber-700 underline hover:text-amber-900"
                      >
                        טען מחדש
                      </button>
                    </div>
                  ) : (
                    <select
                      value={selectedThemeId}
                      onChange={(e) => handleThemeChange(e.target.value)}
                      className="w-full px-3 sm:px-4 py-3 sm:py-3.5 border-2 border-purple-300 rounded-xl focus:ring-4 focus:ring-purple-200 focus:border-purple-500 bg-white text-sm sm:text-base font-medium shadow-sm transition-all"
                    >
                      {availableThemes.map((theme) => (
                        <option key={theme.id} value={theme.id}>
                          {theme.name} - {theme.description}
                        </option>
                      ))}
                    </select>
                  )}
                  <p className="text-xs sm:text-sm text-purple-700 mt-2 flex items-center gap-1">
                    <span>✨</span>
                    <span>עיצובים מוכנים עם צבעים וסגנון מקצועי</span>
                  </p>
                </div>
                
                {/* Recipient - Lead Picker - Mobile Optimized */}
                <div className="bg-gray-50 border-2 border-gray-200 rounded-xl p-3 sm:p-4">
                  <label className="block text-sm sm:text-base font-bold text-gray-900 mb-2 flex items-center gap-2">
                    <span className="text-xl sm:text-2xl">👤</span>
                    <span>בחר ליד *</span>
                  </label>
                  
                  <div className="relative">
                    <div className="flex items-center border-2 border-gray-300 rounded-xl bg-white focus-within:ring-4 focus-within:ring-blue-200 focus-within:border-blue-500 transition-all">
                      <Search className="w-4 h-4 sm:w-5 sm:h-5 text-gray-400 mr-3 ml-2 shrink-0" />
                      <input
                        type="text"
                        value={leadSearchQuery}
                        onChange={(e) => setLeadSearchQuery(e.target.value)}
                        placeholder="חפש ליד (שם, טלפון, מייל)..."
                        className="flex-1 px-2 py-3 sm:py-3.5 border-0 focus:ring-0 text-sm sm:text-base bg-transparent"
                      />
                    </div>
                    
                    {selectedLead && (
                      <div className="mt-3 p-3 sm:p-4 bg-gradient-to-r from-blue-50 to-green-50 border-2 border-blue-300 rounded-xl flex justify-between items-center shadow-sm">
                        <div className="flex-1 min-w-0">
                          <div className="font-bold text-sm sm:text-base truncate">
                            {selectedLead.first_name} {selectedLead.last_name}
                          </div>
                          <div className="text-xs sm:text-sm text-gray-700 truncate">
                            {selectedLead.email}
                          </div>
                        </div>
                        <button
                          type="button"
                          onClick={() => setSelectedLead(null)}
                          className="text-red-600 hover:text-red-800 hover:bg-red-100 rounded-lg p-2 transition-colors shrink-0 ml-2"
                          aria-label="הסר ליד"
                        >
                          <X className="w-5 h-5" />
                        </button>
                      </div>
                    )}
                    
                    {!selectedLead && leadSearchResults.length > 0 && (
                      <div className="absolute z-20 w-full mt-2 bg-white border-2 border-gray-300 rounded-xl shadow-xl max-h-64 overflow-y-auto">
                        {leadSearchResults.map((lead, idx) => (
                          <button
                            key={lead.id}
                            type="button"
                            onClick={() => {
                              setSelectedLead(lead);
                              setLeadSearchQuery('');
                              setLeadSearchResults([]);
                            }}
                            className={`w-full text-right p-3 sm:p-4 hover:bg-blue-50 transition-colors ${
                              idx !== leadSearchResults.length - 1 ? 'border-b border-gray-200' : ''
                            }`}
                          >
                            <div className="font-semibold text-sm sm:text-base">
                              {lead.first_name} {lead.last_name}
                            </div>
                            <div className="text-xs sm:text-sm text-gray-600">{lead.email}</div>
                            <div className="text-xs text-gray-500">{lead.phone_e164}</div>
                          </button>
                        ))}
                      </div>
                    )}
                    
                    {leadSearchLoading && (
                      <div className="mt-2 text-sm text-gray-600 flex items-center gap-2">
                        <div className="animate-spin rounded-full h-4 w-4 border-b-2 border-blue-600"></div>
                        <span>מחפש...</span>
                      </div>
                    )}
                  </div>
                </div>
                
                {/* Subject - Mobile Optimized */}
                <div className="space-y-2">
                  <label className="block text-sm sm:text-base font-bold text-gray-900 flex items-center gap-2">
                    <span className="text-xl sm:text-2xl">📧</span>
                    <span>נושא המייל *</span>
                  </label>
                  <input
                    type="text"
                    value={themeFields.subject}
                    onChange={(e) => setThemeFields({...themeFields, subject: e.target.value})}
                    placeholder="לדוגמה: הצעה מיוחדת במיוחד בשבילך"
                    className="w-full px-3 sm:px-4 py-3 sm:py-3.5 border-2 border-gray-300 rounded-xl focus:ring-4 focus:ring-blue-200 focus:border-blue-500 text-sm sm:text-base transition-all shadow-sm"
                    required
                  />
                  <p className="text-xs text-gray-600 flex items-center gap-1">
                    <span>💡</span>
                    <span>נושא המייל שיוצג לנמען</span>
                  </p>
                </div>
                
                {/* Greeting - Mobile Optimized */}
                <div className="space-y-2">
                  <label className="block text-sm sm:text-base font-bold text-gray-900 flex items-center gap-2">
                    <span className="text-xl sm:text-2xl">👋</span>
                    <span>ברכה פותחת</span>
                  </label>
                  <input
                    type="text"
                    value={themeFields.greeting}
                    onChange={(e) => setThemeFields({...themeFields, greeting: e.target.value})}
                    placeholder='שלום {{lead.first_name}},'
                    className="w-full px-3 sm:px-4 py-3 sm:py-3.5 border-2 border-gray-300 rounded-xl focus:ring-4 focus:ring-blue-200 focus:border-blue-500 text-sm sm:text-base transition-all shadow-sm"
                  />
                  <p className="text-xs text-gray-600 flex items-center gap-1">
                    <span>💡</span>
                    <span>ניתן להשתמש ב-{"{{lead.first_name}}"} לשם הליד</span>
                  </p>
                </div>
                
                {/* Body - Mobile Optimized */}
                <div className="space-y-2">
                  <label className="block text-sm sm:text-base font-bold text-gray-900 flex items-center gap-2">
                    <span className="text-xl sm:text-2xl">📝</span>
                    <span>תוכן המייל *</span>
                  </label>
                  
                  {/* 🔥 NEW: Text Template Quick Select */}
                  {textTemplates.length > 0 && (
                    <div className="bg-green-50 border border-green-200 rounded-lg p-3 mb-2">
                      <label className="block text-xs font-medium text-green-800 mb-1.5 flex items-center gap-1">
                        <FileText className="w-3.5 h-3.5" />
                        טען מתבנית טקסט
                      </label>
                      <select
                        value=""
                        onChange={(e) => {
                          const template = textTemplates.find(t => t.id === parseInt(e.target.value));
                          if (template) {
                            setThemeFields(prev => ({
                              ...prev,
                              subject: template.subject_line || prev.subject,
                              body: template.body_text
                            }));
                          }
                        }}
                        className="w-full px-3 py-2 border border-green-300 rounded-lg bg-white text-sm focus:ring-2 focus:ring-green-200 focus:border-green-500"
                      >
                        <option value="">-- בחר תבנית טקסט לטעינה --</option>
                        {textTemplates.map(template => (
                          <option key={template.id} value={template.id}>
                            {template.name} {template.category ? `(${template.category === 'quote' ? 'הצעת מחיר' : template.category === 'greeting' ? 'ברכה' : template.category === 'pricing' ? 'מחירים' : 'כללי'})` : ''}
                          </option>
                        ))}
                      </select>
                    </div>
                  )}
                  
                  <textarea
                    value={themeFields.body}
                    onChange={(e) => setThemeFields({...themeFields, body: e.target.value})}
                    placeholder="כתוב כאן את תוכן המייל... &#10;&#10;אנחנו ב-{{business.name}} מספקים פתרונות מתקדמים.&#10;&#10;נשמח לשמוע ממך!"
                    rows={8}
                    className="w-full px-3 sm:px-4 py-3 sm:py-3.5 border-2 border-gray-300 rounded-xl focus:ring-4 focus:ring-blue-200 focus:border-blue-500 text-sm sm:text-base transition-all shadow-sm resize-none"
                    required
                  />
                  <p className="text-xs text-gray-600 flex items-center gap-1">
                    <span>✨</span>
                    <span>תוכן המייל - ללא HTML, עיצוב אוטומטי</span>
                  </p>
                </div>
                
                {/* CTA Fields - Mobile Optimized Grid */}
                <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 sm:gap-4">
                  <div className="space-y-2">
                    <label className="block text-xs sm:text-sm font-bold text-gray-900 flex items-center gap-1">
                      <span className="text-lg sm:text-xl">🔘</span>
                      <span>טקסט כפתור</span>
                    </label>
                    <input
                      type="text"
                      value={themeFields.cta_text}
                      onChange={(e) => setThemeFields({...themeFields, cta_text: e.target.value})}
                      placeholder="צור קשר עכשיו"
                      className="w-full px-3 py-2.5 sm:py-3 border-2 border-gray-300 rounded-lg focus:ring-4 focus:ring-blue-200 focus:border-blue-500 text-sm sm:text-base transition-all shadow-sm"
                    />
                  </div>
                  <div className="space-y-2">
                    <label className="block text-xs sm:text-sm font-bold text-gray-900 flex items-center gap-1">
                      <span className="text-lg sm:text-xl">🔗</span>
                      <span>קישור</span>
                    </label>
                    <input
                      type="url"
                      value={themeFields.cta_url}
                      onChange={(e) => setThemeFields({...themeFields, cta_url: e.target.value})}
                      placeholder="https://example.com"
                      className="w-full px-3 py-2.5 sm:py-3 border-2 border-gray-300 rounded-lg focus:ring-4 focus:ring-blue-200 focus:border-blue-500 text-sm sm:text-base transition-all shadow-sm"
                    />
                  </div>
                </div>
                
                {/* Footer - CRITICAL FIELD - Mobile Optimized */}
                <div className="bg-gradient-to-br from-yellow-50 to-orange-50 border-2 border-yellow-300 rounded-xl p-3 sm:p-4 shadow-md">
                  <label className="block text-sm sm:text-base font-bold text-yellow-900 mb-2 flex items-center gap-2">
                    <span className="text-xl sm:text-2xl">⚠️</span>
                    <span>פוטר המייל (חשוב!) *</span>
                  </label>
                  <textarea
                    value={themeFields.footer}
                    onChange={(e) => setThemeFields({...themeFields, footer: e.target.value})}
                    placeholder="אם אינך מעוניין לקבל הודעות נוספות, אנא לחץ כאן להסרה מהרשימה.&#10;&#10;© {{business.name}} | כל הזכויות שמורות"
                    rows={3}
                    className="w-full px-3 sm:px-4 py-2.5 sm:py-3 border-2 border-yellow-400 rounded-lg focus:ring-4 focus:ring-yellow-200 focus:border-yellow-500 text-xs sm:text-sm transition-all shadow-sm resize-none"
                    required
                  />
                  <p className="text-xs text-yellow-800 mt-2 flex items-start gap-1 bg-yellow-100/50 p-2 rounded-lg">
                    <span className="shrink-0">📌</span>
                    <span className="font-medium">הפוטר יופיע בכל המיילים שנשלחים מהעסק ונשמר אוטומטית</span>
                  </p>
                </div>
                
                {/* Preview Button - Mobile Optimized */}
                {selectedLead && (
                  <div className="flex justify-center pt-2">
                    <button
                      type="button"
                      onClick={handlePreviewTheme}
                      disabled={themePreviewLoading}
                      className="w-full sm:w-auto flex items-center justify-center gap-2 px-6 py-3 sm:py-3.5 bg-gradient-to-r from-purple-500 to-blue-500 text-white rounded-xl hover:from-purple-600 hover:to-blue-600 transition-all shadow-lg font-semibold text-sm sm:text-base disabled:opacity-50 disabled:cursor-not-allowed"
                    >
                      <Eye className="w-5 h-5" />
                      {themePreviewLoading ? (
                        <>
                          <div className="animate-spin rounded-full h-4 w-4 border-b-2 border-white"></div>
                          <span>טוען...</span>
                        </>
                      ) : (
                        <span>תצוגה מקדימה</span>
                      )}
                    </button>
                  </div>
                )}
                
                {/* Actions - Mobile Optimized with Sticky Bottom */}
                <div className="sm:pt-2">
                  <div className="flex flex-col-reverse sm:flex-row gap-3">
                    <button
                      type="button"
                      onClick={() => {
                        setShowComposeModal(false);
                        resetComposeForm();
                      }}
                      className="w-full sm:w-auto px-6 py-3 sm:py-3.5 border-2 border-gray-300 text-gray-700 rounded-xl hover:bg-gray-50 active:bg-gray-100 transition-colors font-semibold text-sm sm:text-base shadow-sm"
                    >
                      ביטול
                    </button>
                    <button
                      type="submit"
                      disabled={composeLoading || !selectedLead}
                      className="w-full sm:flex-1 bg-gradient-to-r from-blue-600 to-purple-600 text-white px-6 py-3 sm:py-4 rounded-xl hover:from-blue-700 hover:to-purple-700 active:from-blue-800 active:to-purple-800 transition-all disabled:from-gray-400 disabled:to-gray-400 disabled:cursor-not-allowed font-bold text-base sm:text-lg flex items-center justify-center gap-2 shadow-lg"
                    >
                      {composeLoading ? (
                        <>
                          <div className="animate-spin rounded-full h-5 w-5 border-b-2 border-white"></div>
                          <span>שולח...</span>
                        </>
                      ) : (
                        <>
                          <Send className="w-5 h-5" />
                          <span>שלח מייל עכשיו</span>
                        </>
                      )}
                    </button>
                  </div>
                  {!selectedLead && (
                    <p className="text-xs text-center text-red-600 mt-2 font-medium animate-pulse">
                      ⚠️ יש לבחור ליד לפני שליחה
                    </p>
                  )}
                </div>
              </form>
            </div>
            
            {/* Sticky Mobile Action Bar */}
            <div className="sm:hidden fixed bottom-0 left-0 right-0 bg-gradient-to-t from-white via-white to-white/90 border-t-2 border-gray-200 p-4 shadow-2xl z-30">
              <button
                onClick={(e) => {
                  e.preventDefault();
                  if (!selectedLead) {
                    setError('נא לבחור ליד');
                    return;
                  }
                  const form = document.querySelector('form[class*="space-y-4"]') as HTMLFormElement;
                  if (form) {
                    const event = new Event('submit', { bubbles: true, cancelable: true });
                    form.dispatchEvent(event);
                  }
                }}
                disabled={composeLoading || !selectedLead}
                className="w-full bg-gradient-to-r from-blue-600 to-purple-600 text-white px-6 py-4 rounded-xl font-bold text-lg flex items-center justify-center gap-2 shadow-xl disabled:from-gray-400 disabled:to-gray-400"
              >
                {composeLoading ? (
                  <>
                    <div className="animate-spin rounded-full h-5 w-5 border-b-2 border-white"></div>
                    <span>שולח...</span>
                  </>
                ) : (
                  <>
                    <Send className="w-5 h-5" />
                    <span>שלח מייל עכשיו</span>
                  </>
                )}
              </button>
            </div>
          </div>
        </div>
      )}
      
      {/* 🎨 Theme Preview Modal - Luxury Design */}
      {showThemePreview && (
        <div className="fixed inset-0 bg-black bg-opacity-60 flex items-center justify-center z-[60] p-2 sm:p-4">
          <div className="bg-white rounded-xl shadow-2xl w-full max-w-4xl max-h-[95vh] overflow-hidden flex flex-col">
            {/* Header - Mobile Optimized */}
            <div className="bg-gradient-to-r from-purple-600 to-blue-600 text-white p-4 sm:p-6 flex justify-between items-center shrink-0">
              <div>
                <h2 className="text-xl sm:text-2xl font-bold flex items-center gap-2">
                  <Eye className="w-5 h-5 sm:w-6 sm:h-6" />
                  תצוגה מקדימה
                </h2>
                <p className="text-xs sm:text-sm text-purple-100 mt-1">
                  כך יראה המייל שלך
                </p>
              </div>
              <button
                onClick={() => {
                  setShowThemePreview(false);
                  setThemePreviewHtml('');
                }}
                className="text-white hover:bg-white/20 rounded-lg p-2 transition-colors"
                aria-label="סגור"
              >
                <X className="w-6 h-6" />
              </button>
            </div>
            
            {/* Content - Scrollable */}
            <div className="flex-1 overflow-y-auto p-4 sm:p-6">
              {themePreviewLoading ? (
                <div className="text-center py-12">
                  <div className="animate-spin rounded-full h-12 w-12 border-b-4 border-purple-600 mx-auto"></div>
                  <p className="mt-4 text-gray-600">מכין את התצוגה המקדימה...</p>
                </div>
              ) : (
                <div>
                  {/* Subject Preview */}
                  <div className="mb-6">
                    <label className="block text-xs sm:text-sm font-semibold text-gray-700 mb-2">
                      📧 נושא המייל:
                    </label>
                    <div className="p-3 sm:p-4 bg-blue-50 border-2 border-blue-200 rounded-lg text-sm sm:text-base font-medium">
                      {themeFields.subject}
                    </div>
                  </div>
                  
                  {/* Email Preview - Mobile Responsive */}
                  <div className="mb-4">
                    <label className="block text-xs sm:text-sm font-semibold text-gray-700 mb-2">
                      ✨ תוכן המייל:
                    </label>
                    <div 
                      className="bg-white border-2 border-gray-200 rounded-lg overflow-auto"
                      style={{ minHeight: '400px', maxHeight: '60vh' }}
                      dangerouslySetInnerHTML={{ __html: themePreviewHtml }}
                    />
                  </div>
                  
                  {/* Info Box */}
                  <div className="bg-green-50 border border-green-200 rounded-lg p-3 sm:p-4">
                    <p className="text-xs sm:text-sm text-green-800 flex items-start gap-2">
                      <CheckCircle className="w-4 h-4 sm:w-5 sm:h-5 mt-0.5 shrink-0" />
                      <span>המייל מוכן לשליחה! לחץ על "שלח מייל" בחלון הקודם כדי לשלוח.</span>
                    </p>
                  </div>
                </div>
              )}
            </div>
            
            {/* Footer Actions - Mobile Optimized */}
            <div className="bg-gray-50 border-t border-gray-200 p-4 sm:p-6 shrink-0">
              <button
                onClick={() => {
                  setShowThemePreview(false);
                  setThemePreviewHtml('');
                }}
                className="w-full bg-purple-600 text-white px-6 py-3 sm:py-4 rounded-lg hover:bg-purple-700 transition-colors font-semibold text-base sm:text-lg shadow-lg"
              >
                סגור ותחזור לעריכה
              </button>
            </div>
          </div>
        </div>
      )}
      
      {/* Bulk Compose Modal */}
      {showBulkComposeModal && (
        <div className="fixed inset-0 bg-black/60 backdrop-blur-sm flex items-center justify-center z-50 p-0 sm:p-4 overflow-y-auto">
          <div className="bg-white w-full h-full sm:h-auto sm:rounded-2xl sm:shadow-2xl sm:max-w-4xl sm:max-h-[95vh] overflow-y-auto">
            <div className="sticky top-0 bg-gradient-to-r from-green-600 to-blue-600 text-white p-4 sm:p-6 z-10 shadow-lg sm:rounded-t-2xl">
              <div className="flex justify-between items-center">
                <div className="flex-1">
                  <h2 className="text-xl sm:text-2xl font-bold flex items-center gap-2">
                    <Mail className="w-5 h-5 sm:w-6 sm:h-6" />
                    שליחה ל-{selectedLeadIds.size} לידים
                  </h2>
                  <p className="text-xs sm:text-sm text-green-100 mt-1">
                    מייל קבוצתי עם נושא ותוכן משותפים
                  </p>
                </div>
                <button
                  onClick={() => {
                    setShowBulkComposeModal(false);
                    resetComposeForm();
                  }}
                  className="text-white hover:bg-white/20 rounded-lg p-2 transition-colors shrink-0"
                  aria-label="סגור"
                >
                  <X className="w-6 h-6" />
                </button>
              </div>
            </div>
            
            <div className="p-4 sm:p-6">
              {error && (
                <div className="mb-4 bg-red-50 border-l-4 border-red-500 rounded-lg p-3 sm:p-4 text-sm sm:text-base text-red-800 flex items-start gap-2">
                  <AlertCircle className="w-5 h-5 shrink-0 mt-0.5" />
                  <span>{error}</span>
                </div>
              )}
              
              <form onSubmit={handleSendBulkEmail} className="space-y-4 sm:space-y-5">
                {/* Theme Selector */}
                <div className="bg-gradient-to-br from-purple-50 to-blue-50 border-2 border-purple-200 rounded-xl p-3 sm:p-4 shadow-sm">
                  <label className="block text-sm sm:text-base font-bold text-purple-900 mb-2 flex items-center gap-2">
                    <span className="text-xl sm:text-2xl">🎨</span>
                    <span>בחר עיצוב יוקרתי למייל</span>
                  </label>
                  
                  {themesLoading ? (
                    <div className="flex items-center gap-2 text-sm text-gray-600">
                      <div className="animate-spin rounded-full h-4 w-4 border-b-2 border-purple-600"></div>
                      <span>טוען עיצובים...</span>
                    </div>
                  ) : themesError ? (
                    <div className="text-sm text-red-600 bg-red-50 p-3 rounded-lg border border-red-200">
                      ⚠️ {themesError}
                    </div>
                  ) : availableThemes.length === 0 ? (
                    <div className="text-sm text-amber-600 bg-amber-50 p-3 rounded-lg border border-amber-200">
                      ⚠️ לא נמצאו עיצובים זמינים
                    </div>
                  ) : (
                    <select
                      value={selectedThemeId}
                      onChange={(e) => handleThemeChange(e.target.value)}
                      className="w-full px-3 sm:px-4 py-3 sm:py-3.5 border-2 border-purple-300 rounded-xl focus:ring-4 focus:ring-purple-200 focus:border-purple-500 bg-white text-sm sm:text-base font-medium shadow-sm transition-all"
                    >
                      {availableThemes.map((theme) => (
                        <option key={theme.id} value={theme.id}>
                          {theme.name} - {theme.description}
                        </option>
                      ))}
                    </select>
                  )}
                </div>
                
                {/* Subject */}
                <div className="space-y-2">
                  <label className="block text-sm sm:text-base font-bold text-gray-900 flex items-center gap-2">
                    <span className="text-xl sm:text-2xl">📧</span>
                    <span>נושא המייל (משותף לכל הלידים) *</span>
                  </label>
                  <input
                    type="text"
                    value={themeFields.subject}
                    onChange={(e) => setThemeFields({...themeFields, subject: e.target.value})}
                    placeholder="לדוגמה: הצעה מיוחדת במיוחד בשבילך"
                    className="w-full px-3 sm:px-4 py-3 sm:py-3.5 border-2 border-gray-300 rounded-xl focus:ring-4 focus:ring-blue-200 focus:border-blue-500 text-sm sm:text-base transition-all shadow-sm"
                    required
                  />
                </div>
                
                {/* Greeting */}
                <div className="space-y-2">
                  <label className="block text-sm sm:text-base font-bold text-gray-900 flex items-center gap-2">
                    <span className="text-xl sm:text-2xl">👋</span>
                    <span>ברכה פותחת</span>
                  </label>
                  <input
                    type="text"
                    value={themeFields.greeting}
                    onChange={(e) => setThemeFields({...themeFields, greeting: e.target.value})}
                    placeholder='שלום {{lead.first_name}},'
                    className="w-full px-3 sm:px-4 py-3 sm:py-3.5 border-2 border-gray-300 rounded-xl focus:ring-4 focus:ring-blue-200 focus:border-blue-500 text-sm sm:text-base transition-all shadow-sm"
                  />
                  <p className="text-xs text-gray-600">
                    💡 {"{{lead.first_name}}"} יוחלף בשם כל ליד באופן אוטומטי
                  </p>
                </div>
                
                {/* Body */}
                <div className="space-y-2">
                  <label className="block text-sm sm:text-base font-bold text-gray-900 flex items-center gap-2">
                    <span className="text-xl sm:text-2xl">📝</span>
                    <span>תוכן המייל (משותף) *</span>
                  </label>
                  
                  {/* 🔥 NEW: Text Template Quick Select for Bulk */}
                  {textTemplates.length > 0 && (
                    <div className="bg-green-50 border border-green-200 rounded-lg p-3 mb-2">
                      <label className="block text-xs font-medium text-green-800 mb-1.5 flex items-center gap-1">
                        <FileText className="w-3.5 h-3.5" />
                        טען מתבנית טקסט
                      </label>
                      <select
                        value=""
                        onChange={(e) => {
                          const template = textTemplates.find(t => t.id === parseInt(e.target.value));
                          if (template) {
                            setThemeFields(prev => ({
                              ...prev,
                              subject: template.subject_line || prev.subject,
                              body: template.body_text
                            }));
                          }
                        }}
                        className="w-full px-3 py-2 border border-green-300 rounded-lg bg-white text-sm focus:ring-2 focus:ring-green-200 focus:border-green-500"
                      >
                        <option value="">-- בחר תבנית טקסט לטעינה --</option>
                        {textTemplates.map(template => (
                          <option key={template.id} value={template.id}>
                            {template.name} {template.category ? `(${template.category === 'quote' ? 'הצעת מחיר' : template.category === 'greeting' ? 'ברכה' : template.category === 'pricing' ? 'מחירים' : 'כללי'})` : ''}
                          </option>
                        ))}
                      </select>
                    </div>
                  )}
                  
                  <textarea
                    value={themeFields.body}
                    onChange={(e) => setThemeFields({...themeFields, body: e.target.value})}
                    placeholder="כתוב כאן את תוכן המייל... &#10;&#10;אנחנו ב-{{business.name}} מספקים פתרונות מתקדמים.&#10;&#10;נשמח לשמוע ממך!"
                    rows={8}
                    className="w-full px-3 sm:px-4 py-3 sm:py-3.5 border-2 border-gray-300 rounded-xl focus:ring-4 focus:ring-blue-200 focus:border-blue-500 text-sm sm:text-base transition-all shadow-sm resize-none"
                    required
                  />
                </div>
                
                {/* CTA Fields */}
                <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 sm:gap-4">
                  <div className="space-y-2">
                    <label className="block text-xs sm:text-sm font-bold text-gray-900 flex items-center gap-1">
                      <span className="text-lg sm:text-xl">🔘</span>
                      <span>טקסט כפתור</span>
                    </label>
                    <input
                      type="text"
                      value={themeFields.cta_text}
                      onChange={(e) => setThemeFields({...themeFields, cta_text: e.target.value})}
                      placeholder="צור קשר עכשיו"
                      className="w-full px-3 py-2.5 sm:py-3 border-2 border-gray-300 rounded-lg focus:ring-4 focus:ring-blue-200 focus:border-blue-500 text-sm sm:text-base transition-all shadow-sm"
                    />
                  </div>
                  <div className="space-y-2">
                    <label className="block text-xs sm:text-sm font-bold text-gray-900 flex items-center gap-1">
                      <span className="text-lg sm:text-xl">🔗</span>
                      <span>קישור</span>
                    </label>
                    <input
                      type="url"
                      value={themeFields.cta_url}
                      onChange={(e) => setThemeFields({...themeFields, cta_url: e.target.value})}
                      placeholder="https://example.com"
                      className="w-full px-3 py-2.5 sm:py-3 border-2 border-gray-300 rounded-lg focus:ring-4 focus:ring-blue-200 focus:border-blue-500 text-sm sm:text-base transition-all shadow-sm"
                    />
                  </div>
                </div>
                
                {/* Footer */}
                <div className="bg-gradient-to-br from-yellow-50 to-orange-50 border-2 border-yellow-300 rounded-xl p-3 sm:p-4 shadow-md">
                  <label className="block text-sm sm:text-base font-bold text-yellow-900 mb-2 flex items-center gap-2">
                    <span className="text-xl sm:text-2xl">⚠️</span>
                    <span>פוטר המייל *</span>
                  </label>
                  <textarea
                    value={themeFields.footer}
                    onChange={(e) => setThemeFields({...themeFields, footer: e.target.value})}
                    placeholder="אם אינך מעוניין לקבל הודעות נוספות, אנא לחץ כאן להסרה מהרשימה.&#10;&#10;© {{business.name}} | כל הזכויות שמורות"
                    rows={3}
                    className="w-full px-3 sm:px-4 py-2.5 sm:py-3 border-2 border-yellow-400 rounded-lg focus:ring-4 focus:ring-yellow-200 focus:border-yellow-500 text-xs sm:text-sm transition-all shadow-sm resize-none"
                    required
                  />
                </div>
                
                {/* Info Box */}
                <div className="bg-blue-50 border-l-4 border-blue-500 p-4 rounded-lg">
                  <div className="flex items-start gap-3">
                    <Mail className="w-5 h-5 text-blue-600 flex-shrink-0 mt-0.5" />
                    <div>
                      <p className="text-sm font-medium text-blue-900">
                        המייל יישלח ל-{selectedLeadIds.size} לידים
                      </p>
                      <p className="text-xs text-blue-700 mt-1">
                        כל ליד יקבל מייל אישי עם השם שלו (אם יש {"{{lead.first_name}}"})
                      </p>
                    </div>
                  </div>
                </div>
                
                {/* Actions */}
                <div className="flex flex-col-reverse sm:flex-row gap-3 pt-2">
                  <button
                    type="button"
                    onClick={() => {
                      setShowBulkComposeModal(false);
                      resetComposeForm();
                    }}
                    className="w-full sm:w-auto px-6 py-3 border-2 border-gray-300 text-gray-700 rounded-xl hover:bg-gray-50 transition-colors font-semibold"
                  >
                    ביטול
                  </button>
                  <button
                    type="submit"
                    disabled={bulkComposeLoading}
                    className="w-full sm:flex-1 bg-gradient-to-r from-green-600 to-blue-600 text-white px-6 py-4 rounded-xl hover:from-green-700 hover:to-blue-700 transition-all disabled:from-gray-400 disabled:to-gray-400 disabled:cursor-not-allowed font-bold text-lg flex items-center justify-center gap-2 shadow-lg"
                  >
                    {bulkComposeLoading ? (
                      <>
                        <div className="animate-spin rounded-full h-5 w-5 border-b-2 border-white"></div>
                        <span>שולח...</span>
                      </>
                    ) : (
                      <>
                        <Send className="w-5 h-5" />
                        <span>שלח ל-{selectedLeadIds.size} לידים</span>
                      </>
                    )}
                  </button>
                </div>
              </form>
            </div>
          </div>
        </div>
      )}
      
      {/* Template Preview Modal */}
      {showPreviewModal && previewTemplate && (
        <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50 p-4">
          <div className="bg-white rounded-lg shadow-xl max-w-4xl w-full max-h-[90vh] overflow-y-auto">
            <div className="p-6">
              <div className="flex justify-between items-center mb-4">
                <div>
                  <h2 className="text-2xl font-bold">{previewTemplate.name}</h2>
                  <p className="text-sm text-gray-600 mt-1">תצוגה מקדימה</p>
                </div>
                <button
                  onClick={() => {
                    setShowPreviewModal(false);
                    setPreviewTemplate(null);
                  }}
                  className="text-gray-500 hover:text-gray-700"
                >
                  <X className="w-6 h-6" />
                </button>
              </div>
              
              {previewLoading ? (
                <div className="text-center py-12">
                  <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-blue-600 mx-auto"></div>
                </div>
              ) : (
                <div>
                  <div className="mb-4">
                    <label className="block text-sm font-medium text-gray-700 mb-1">נושא:</label>
                    <div className="p-3 bg-gray-50 border border-gray-200 rounded-lg">
                      {previewSubject}
                    </div>
                  </div>
                  
                  <div className="mb-4">
                    <label className="block text-sm font-medium text-gray-700 mb-1">תוכן:</label>
                    <div 
                      className="p-4 bg-white border border-gray-200 rounded-lg"
                      dangerouslySetInnerHTML={{ __html: previewHtml }}
                    />
                  </div>
                  
                  <div className="flex gap-2">
                    <button
                      onClick={() => {
                        // Close preview and open settings tab with test email pre-filled
                        setShowPreviewModal(false);
                        setActiveTab('settings');
                        // Set test email to current user's email
                        if (user?.email) {
                          setTestEmail(user.email);
                        }
                      }}
                      className="bg-green-600 text-white px-4 py-2 rounded-lg hover:bg-green-700 transition-colors flex items-center gap-2"
                    >
                      <Send className="w-4 h-4" />
                      שלח טסט למייל שלי
                    </button>
                    <button
                      onClick={() => {
                        setShowPreviewModal(false);
                        setPreviewTemplate(null);
                      }}
                      className="px-4 py-2 border border-gray-300 rounded-lg hover:bg-gray-50 transition-colors"
                    >
                      סגור
                    </button>
                  </div>
                </div>
              )}
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
