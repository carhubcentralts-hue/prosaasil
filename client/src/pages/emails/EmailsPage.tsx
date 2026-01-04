import React, { useState, useEffect } from 'react';
import { Mail, Send, Settings, AlertCircle, CheckCircle, Clock, XCircle, Plus, Eye, Search, X } from 'lucide-react';
import { useAuth } from '../../features/auth/hooks';
import axios from 'axios';

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
  const [activeTab, setActiveTab] = useState<'all' | 'sent' | 'templates' | 'settings'>('all');
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
  const [composeMode, setComposeMode] = useState<'lead' | 'manual'>('lead');
  const [selectedLead, setSelectedLead] = useState<Lead | null>(null);
  const [selectedTemplate, setSelectedTemplate] = useState<EmailTemplate | null>(null);
  const [manualEmail, setManualEmail] = useState('');
  const [emailSubject, setEmailSubject] = useState('');
  const [emailHtml, setEmailHtml] = useState('');
  const [composeLoading, setComposeLoading] = useState(false);
  const [leadSearchQuery, setLeadSearchQuery] = useState('');
  const [leadSearchResults, setLeadSearchResults] = useState<Lead[]>([]);
  const [leadSearchLoading, setLeadSearchLoading] = useState(false);
  
  // Templates state
  const [templates, setTemplates] = useState<EmailTemplate[]>([]);
  const [templatesLoading, setTemplatesLoading] = useState(false);
  const [showPreviewModal, setShowPreviewModal] = useState(false);
  const [previewTemplate, setPreviewTemplate] = useState<EmailTemplate | null>(null);
  const [previewHtml, setPreviewHtml] = useState('');
  const [previewSubject, setPreviewSubject] = useState('');
  const [previewLoading, setPreviewLoading] = useState(false);
  
  useEffect(() => {
    loadSettings();
    if (activeTab === 'all' || activeTab === 'sent') {
      loadEmails();
    } else if (activeTab === 'templates') {
      loadTemplates();
    }
  }, [activeTab, statusFilter, searchQuery]);
  
  // Load templates when compose modal opens
  useEffect(() => {
    if (showComposeModal && templates.length === 0) {
      loadTemplates();
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
  
  const searchLeads = async () => {
    try {
      setLeadSearchLoading(true);
      const response = await axios.get(`/api/leads?q=${encodeURIComponent(leadSearchQuery)}&pageSize=20`);
      const leads = response.data.leads || [];
      setLeadSearchResults(leads.map((l: any) => ({
        id: l.id,
        first_name: l.first_name || '',
        last_name: l.last_name || '',
        email: l.email || '',
        phone_e164: l.phone_e164 || ''
      })));
    } catch (err: any) {
      console.error('Failed to search leads:', err);
    } finally {
      setLeadSearchLoading(false);
    }
  };
  
  const handleComposeEmail = async (e: React.FormEvent) => {
    e.preventDefault();
    
    if (!selectedLead || !emailSubject.trim() || !emailHtml.trim()) {
      setError('נא למלא את כל השדות ולבחור ליד');
      return;
    }
    
    setComposeLoading(true);
    setError(null);
    
    try {
      await axios.post(`/api/leads/${selectedLead.id}/email`, {
        to_email: selectedLead.email,
        subject: emailSubject.trim(),
        html: emailHtml.trim()
      });
      
      setSuccessMessage('מייל נשלח בהצלחה');
      setShowComposeModal(false);
      resetComposeForm();
      loadEmails();
    } catch (err: any) {
      setError(err.response?.data?.error || 'שגיאה בשליחת מייל');
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
  
  const handleSelectTemplate = async (template: EmailTemplate) => {
    setSelectedTemplate(template);
    
    // Load template content and populate form
    try {
      const leadData = selectedLead ? {
        first_name: selectedLead.first_name,
        last_name: selectedLead.last_name,
        email: selectedLead.email
      } : {
        first_name: 'שם',
        last_name: 'לקוח',
        email: 'example@test.com'
      };
      
      const response = await axios.post(`/api/email/templates/${template.id}/preview`, {
        lead: leadData
      });
      
      setEmailSubject(response.data.preview.subject);
      setEmailHtml(response.data.preview.html);
    } catch (err: any) {
      console.error('Failed to load template:', err);
      // Fallback to template content directly
      setEmailSubject(template.subject_template);
      setEmailHtml(template.html_template);
    }
  };
  
  const handleResetToTemplate = () => {
    if (selectedTemplate) {
      handleSelectTemplate(selectedTemplate);
    }
  };
  
  const resetComposeForm = () => {
    setSelectedLead(null);
    setSelectedTemplate(null);
    setManualEmail('');
    setEmailSubject('');
    setEmailHtml('');
    setLeadSearchQuery('');
    setLeadSearchResults([]);
  };
  
  const isAdmin = ['system_admin', 'owner', 'admin'].includes(user?.role || '');
  
  return (
    <div className="container mx-auto px-4 py-6 max-w-7xl">
      {/* Header */}
      <div className="mb-6">
        <h1 className="text-3xl font-bold text-gray-900 flex items-center gap-2">
          <Mail className="w-8 h-8 text-blue-600" />
          מיילים
        </h1>
        <p className="text-gray-600 mt-1">
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
        <div className="border-b border-gray-200">
          <nav className="flex -mb-px">
            <button
              onClick={() => setActiveTab('all')}
              className={`px-6 py-3 text-sm font-medium border-b-2 transition-colors ${
                activeTab === 'all'
                  ? 'border-blue-500 text-blue-600'
                  : 'border-transparent text-gray-500 hover:text-gray-700 hover:border-gray-300'
              }`}
            >
              כל המיילים
            </button>
            <button
              onClick={() => setActiveTab('sent')}
              className={`px-6 py-3 text-sm font-medium border-b-2 transition-colors ${
                activeTab === 'sent'
                  ? 'border-blue-500 text-blue-600'
                  : 'border-transparent text-gray-500 hover:text-gray-700 hover:border-gray-300'
              }`}
            >
              נשלחו
            </button>
            <button
              onClick={() => setActiveTab('templates')}
              className={`px-6 py-3 text-sm font-medium border-b-2 transition-colors ${
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
                className={`px-6 py-3 text-sm font-medium border-b-2 transition-colors ${
                  activeTab === 'settings'
                    ? 'border-blue-500 text-blue-600'
                    : 'border-transparent text-gray-500 hover:text-gray-700 hover:border-gray-300'
                }`}
              >
                <Settings className="w-4 h-4 inline ml-2" />
                הגדרות
              </button>
            )}
          </nav>
        </div>
        
        {/* Content */}
        <div className="p-6">
          {activeTab === 'templates' ? (
            // Templates Tab
            <div>
              <div className="flex justify-between items-center mb-4">
                <h2 className="text-xl font-semibold">תבניות מייל</h2>
              </div>
              
              {templatesLoading ? (
                <div className="text-center py-12">
                  <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-blue-600 mx-auto"></div>
                </div>
              ) : templates.length === 0 ? (
                <div className="text-center py-12">
                  <Mail className="w-16 h-16 text-gray-400 mx-auto mb-4" />
                  <p className="text-gray-600">אין תבניות להצגה</p>
                </div>
              ) : (
                <div className="grid gap-4">
                  {templates.map((template) => (
                    <div key={template.id} className="border border-gray-200 rounded-lg p-4 hover:shadow-md transition-shadow">
                      <div className="flex justify-between items-start">
                        <div className="flex-1">
                          <h3 className="font-medium text-gray-900">{template.name}</h3>
                          <p className="text-sm text-gray-600 mt-1">{template.subject_template}</p>
                          <span className="inline-flex items-center px-2 py-1 rounded-full text-xs font-medium bg-blue-100 text-blue-800 mt-2">
                            {template.type}
                          </span>
                        </div>
                        <button
                          onClick={() => handlePreviewTemplate(template)}
                          className="bg-blue-600 text-white px-4 py-2 rounded-lg hover:bg-blue-700 transition-colors flex items-center gap-2"
                        >
                          <Eye className="w-4 h-4" />
                          תצוגה מקדימה
                        </button>
                      </div>
                    </div>
                  ))}
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
        <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50 p-4">
          <div className="bg-white rounded-lg shadow-xl max-w-2xl w-full max-h-[90vh] overflow-y-auto">
            <div className="p-6">
              <div className="flex justify-between items-center mb-4">
                <h2 className="text-2xl font-bold">שליחת מייל חדש</h2>
                <button
                  onClick={() => {
                    setShowComposeModal(false);
                    resetComposeForm();
                  }}
                  className="text-gray-500 hover:text-gray-700"
                >
                  <X className="w-6 h-6" />
                </button>
              </div>
              
              {error && (
                <div className="mb-4 bg-red-50 border border-red-200 rounded-lg p-3 text-sm text-red-800">
                  {error}
                </div>
              )}
              
              <form onSubmit={handleComposeEmail} className="space-y-4">
                {/* Template Selector */}
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-2">
                    בחר תבנית (אופציונלי):
                  </label>
                  
                  <div className="space-y-2">
                    {templatesLoading ? (
                      <div className="text-sm text-gray-600">טוען תבניות...</div>
                    ) : templates.length > 0 ? (
                      <>
                        <select
                          value={selectedTemplate?.id || ''}
                          onChange={(e) => {
                            const templateId = parseInt(e.target.value);
                            const template = templates.find(t => t.id === templateId);
                            if (template) {
                              handleSelectTemplate(template);
                            } else {
                              setSelectedTemplate(null);
                            }
                          }}
                          className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500"
                        >
                          <option value="">-- בחר תבנית --</option>
                          {templates.filter(t => t.is_active).map((template) => (
                            <option key={template.id} value={template.id}>
                              {template.name}
                            </option>
                          ))}
                        </select>
                        
                        {selectedTemplate && (
                          <button
                            type="button"
                            onClick={handleResetToTemplate}
                            className="text-sm text-blue-600 hover:text-blue-800"
                          >
                            🔄 אפס לתבנית המקורית
                          </button>
                        )}
                      </>
                    ) : (
                      <div className="text-sm text-gray-500">אין תבניות זמינות</div>
                    )}
                  </div>
                </div>
                
                {/* Recipient - Lead Picker */}
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-2">
                    בחר ליד:
                  </label>
                  
                  <div className="relative">
                    <div className="flex items-center border border-gray-300 rounded-lg">
                      <Search className="w-5 h-5 text-gray-400 mr-3 ml-2" />
                      <input
                        type="text"
                        value={leadSearchQuery}
                        onChange={(e) => setLeadSearchQuery(e.target.value)}
                        placeholder="חפש ליד (שם, טלפון, מייל)..."
                        className="flex-1 px-3 py-2 border-0 focus:ring-0"
                      />
                    </div>
                    
                    {selectedLead && (
                      <div className="mt-2 p-3 bg-blue-50 border border-blue-200 rounded-lg flex justify-between items-center">
                        <div>
                          <div className="font-medium">{selectedLead.first_name} {selectedLead.last_name}</div>
                          <div className="text-sm text-gray-600">{selectedLead.email}</div>
                        </div>
                        <button
                          type="button"
                          onClick={() => setSelectedLead(null)}
                          className="text-red-600 hover:text-red-800"
                        >
                          <X className="w-5 h-5" />
                        </button>
                      </div>
                    )}
                    
                    {!selectedLead && leadSearchResults.length > 0 && (
                      <div className="absolute z-10 w-full mt-1 bg-white border border-gray-300 rounded-lg shadow-lg max-h-60 overflow-y-auto">
                        {leadSearchResults.map((lead) => (
                          <button
                            key={lead.id}
                            type="button"
                            onClick={() => {
                              setSelectedLead(lead);
                              setLeadSearchQuery('');
                              setLeadSearchResults([]);
                            }}
                            className="w-full text-right p-3 hover:bg-gray-50 border-b border-gray-100 last:border-0"
                          >
                            <div className="font-medium">{lead.first_name} {lead.last_name}</div>
                            <div className="text-sm text-gray-600">{lead.email}</div>
                            <div className="text-xs text-gray-500">{lead.phone_e164}</div>
                          </button>
                        ))}
                      </div>
                    )}
                    
                    {leadSearchLoading && (
                      <div className="mt-2 text-sm text-gray-600">מחפש...</div>
                    )}
                  </div>
                </div>
                
                {/* Subject */}
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">
                    נושא *
                  </label>
                  <input
                    type="text"
                    value={emailSubject}
                    onChange={(e) => setEmailSubject(e.target.value)}
                    placeholder="נושא המייל"
                    className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500"
                    required
                  />
                </div>
                
                {/* Body */}
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">
                    תוכן המייל *
                  </label>
                  <textarea
                    value={emailHtml}
                    onChange={(e) => setEmailHtml(e.target.value)}
                    placeholder="תוכן המייל (HTML)"
                    rows={8}
                    className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500"
                    required
                  />
                </div>
                
                {/* Actions */}
                <div className="flex gap-2">
                  <button
                    type="submit"
                    disabled={composeLoading}
                    className="flex-1 bg-blue-600 text-white px-4 py-2 rounded-lg hover:bg-blue-700 transition-colors disabled:bg-gray-400 disabled:cursor-not-allowed"
                  >
                    {composeLoading ? 'שולח...' : 'שלח מייל'}
                  </button>
                  <button
                    type="button"
                    onClick={() => {
                      setShowComposeModal(false);
                      resetComposeForm();
                    }}
                    className="px-4 py-2 border border-gray-300 rounded-lg hover:bg-gray-50 transition-colors"
                  >
                    ביטול
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
