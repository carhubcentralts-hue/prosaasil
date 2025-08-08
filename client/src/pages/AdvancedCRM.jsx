import React, { useState, useEffect } from 'react';
import ModernLayout from '../components/ModernLayout';
import { 
  Users, Search, Filter, Plus, Edit, Trash2, Eye, 
  Phone, Mail, Calendar, MapPin, Building2, Tag, 
  Star, TrendingUp, DollarSign, FileText, Send, 
  Download, Upload, Link2, CreditCard, Check, X,
  AlertCircle, CheckCircle, Clock, MoreVertical,
  ArrowUpRight, Target, Award, Briefcase, Calculator,
  Receipt, Banknote, ExternalLink, Copy, Archive
} from 'lucide-react';

export default function AdvancedCRM() {
  const [userRole, setUserRole] = useState('business');
  const [activeTab, setActiveTab] = useState('leads');
  const [searchTerm, setSearchTerm] = useState('');
  const [selectedCustomer, setSelectedCustomer] = useState(null);
  const [showModal, setShowModal] = useState(false);
  const [modalType, setModalType] = useState(''); // 'invoice', 'contract', 'payment', 'customer'
  const [leads, setLeads] = useState([]);
  const [contracts, setContracts] = useState([]);
  const [invoices, setInvoices] = useState([]);
  const [tasks, setTasks] = useState([]);
  const [loading, setLoading] = useState(true);

  // Filters
  const [statusFilter, setStatusFilter] = useState('all');
  const [sourceFilter, setSourceFilter] = useState('all');
  const [probabilityFilter, setProbabilityFilter] = useState('all');
  const [dateRange, setDateRange] = useState('all');

  useEffect(() => {
    const role = localStorage.getItem('user_role') || localStorage.getItem('userRole');
    setUserRole(role || 'business');
    loadCRMData();
  }, []);

  const loadCRMData = async () => {
    // Enhanced demo data with comprehensive CRM features
    const demoLeads = [
      {
        id: 1,
        name: 'יוסי כהן',
        company: 'כהן טכנולוגיות',
        phone: '050-1234567',
        email: 'yossi@cohen-tech.co.il',
        status: 'negotiation',
        source: 'whatsapp',
        probability: 85,
        value: 45000,
        last_contact: '2025-08-07',
        next_action: 'קביעת פגישת הדגמה',
        tags: ['טכנולוגיה', 'ליד חם'],
        created_at: '2025-08-01',
        notes: 'מעוניין במערכת CRM מתקדמת לחברה שלו. חברה בת 50 עובדים.',
        interactions: 5,
        lead_score: 92
      },
      {
        id: 2,
        name: 'שרה לוי',
        company: 'לוי שיווק',
        phone: '052-9876543',
        email: 'sarah@levi-marketing.co.il',
        status: 'proposal_sent',
        source: 'phone',
        probability: 65,
        value: 25000,
        last_contact: '2025-08-06',
        next_action: 'שליחת הצעת מחיר מפורטת',
        tags: ['שיווק', 'חוזה שנתי'],
        created_at: '2025-07-28',
        notes: 'מחפשת פתרון שיווק דיגיטלי. תקציב מאושר.',
        interactions: 3,
        lead_score: 78
      },
      {
        id: 3,
        name: 'דני אברהם',
        company: 'אברהם יעוץ',
        phone: '053-5555555',
        email: 'danny@abraham-consulting.co.il',
        status: 'follow_up',
        source: 'website',
        probability: 30,
        value: 15000,
        last_contact: '2025-08-05',
        next_action: 'שיחת המשך',
        tags: ['ייעוץ', 'עסק קטן'],
        created_at: '2025-07-25',
        notes: 'עסק קטן, מתלבט בין כמה ספקים.',
        interactions: 2,
        lead_score: 45
      }
    ];

    const demoContracts = [
      {
        id: 1,
        customer_id: 1,
        customer_name: 'יוסי כהן',
        title: 'חוזה פיתוח מערכת CRM',
        value: 45000,
        status: 'active',
        start_date: '2025-08-01',
        end_date: '2025-12-01',
        milestones: [
          { id: 1, title: 'תכנון מערכת', status: 'completed', amount: 10000 },
          { id: 2, title: 'פיתוח בסיסי', status: 'in_progress', amount: 15000 },
          { id: 3, title: 'פיתוח מתקדם', status: 'pending', amount: 15000 },
          { id: 4, title: 'בדיקות והטמעה', status: 'pending', amount: 5000 }
        ],
        signed_date: '2025-08-01',
        payment_terms: '30 יום'
      },
      {
        id: 2,
        customer_id: 2,
        customer_name: 'שרה לוי',
        title: 'חוזה שיווק דיגיטלי',
        value: 25000,
        status: 'draft',
        start_date: '2025-09-01',
        end_date: '2025-12-31',
        milestones: [
          { id: 1, title: 'אסטרטגיה', status: 'pending', amount: 8000 },
          { id: 2, title: 'ביצוע קמפיינים', status: 'pending', amount: 12000 },
          { id: 3, title: 'אופטימיזציה', status: 'pending', amount: 5000 }
        ],
        signed_date: null,
        payment_terms: '15 יום'
      }
    ];

    const demoInvoices = [
      {
        id: 1,
        customer_id: 1,
        customer_name: 'יוסי כהן',
        contract_id: 1,
        invoice_number: 'INV-2025-001',
        amount: 10000,
        tax: 1700,
        total: 11700,
        status: 'paid',
        issue_date: '2025-08-01',
        due_date: '2025-08-31',
        paid_date: '2025-08-15',
        description: 'תכנון מערכת CRM - אבן דרך 1',
        payment_link: 'https://pay.example.com/inv001'
      },
      {
        id: 2,
        customer_id: 1,
        customer_name: 'יוסי כהן',
        contract_id: 1,
        invoice_number: 'INV-2025-002',
        amount: 15000,
        tax: 2550,
        total: 17550,
        status: 'pending',
        issue_date: '2025-08-15',
        due_date: '2025-09-14',
        paid_date: null,
        description: 'פיתוח בסיסי CRM - אבן דרך 2',
        payment_link: 'https://pay.example.com/inv002'
      },
      {
        id: 3,
        customer_id: 2,
        customer_name: 'שרה לוי',
        contract_id: null,
        invoice_number: 'INV-2025-003',
        amount: 5000,
        tax: 850,
        total: 5850,
        status: 'overdue',
        issue_date: '2025-07-01',
        due_date: '2025-07-16',
        paid_date: null,
        description: 'ייעוץ שיווקי - יולי 2025',
        payment_link: 'https://pay.example.com/inv003'
      }
    ];

    const demoTasks = [
      {
        id: 1,
        title: 'התקשר ליוסי כהן',
        description: 'לברר על התקדמות הפרוייקט',
        customer_id: 1,
        customer_name: 'יוסי כהן',
        priority: 'high',
        status: 'pending',
        due_date: '2025-08-08',
        created_at: '2025-08-07',
        assigned_to: 'מנהל פרויקטים'
      },
      {
        id: 2,
        title: 'שלח הצעת מחיר לשרה',
        description: 'הכן הצעת מחיר מפורטת לפרויקט השיווק',
        customer_id: 2,
        customer_name: 'שרה לוי',
        priority: 'medium',
        status: 'pending',
        due_date: '2025-08-09',
        created_at: '2025-08-06',
        assigned_to: 'מנהל מכירות'
      },
      {
        id: 3,
        title: 'הכן חוזה',
        description: 'הכן חוזה עבור יוסי כהן לאחר הסכמה',
        customer_id: 1,
        customer_name: 'יוסי כהן',
        priority: 'low',
        status: 'completed',
        due_date: '2025-08-05',
        created_at: '2025-08-01',
        assigned_to: 'מחלקה משפטית'
      }
    ];

    setLeads(demoLeads);
    setContracts(demoContracts);
    setInvoices(demoInvoices);
    // Add more leads with various statuses
    const additionalLeads = [
      {
        id: 4,
        name: 'מירי דוד',
        company: 'דוד דיגיטל',
        phone: '054-1111111',
        email: 'miri@david-digital.co.il',
        status: 'new',
        source: 'website',
        probability: 20,
        value: 8000,
        last_contact: '2025-08-08',
        next_action: 'יצירת קשר ראשוני',
        tags: ['דיגיטל', 'עסק קטן'],
        created_at: '2025-08-08',
        notes: 'נרשמה לניוזלטר היום, מעוניינת בשיווק דיגיטלי.',
        interactions: 1,
        lead_score: 30
      },
      {
        id: 5,
        name: 'אבי גרין',
        company: 'גרין ייעוץ',
        phone: '055-2222222',
        email: 'avi@green-consulting.co.il',
        status: 'contacted',
        source: 'phone',
        probability: 45,
        value: 18000,
        last_contact: '2025-08-07',
        next_action: 'שליחת חומרים נוספים',
        tags: ['ייעוץ', 'מתעניין'],
        created_at: '2025-08-05',
        notes: 'דיברנו היום בטלפון, מעוניין לשמוע יותר פרטים.',
        interactions: 2,
        lead_score: 55
      },
      {
        id: 6,
        name: 'רות כהן',
        company: 'כהן עיצוב',
        phone: '056-3333333',
        email: 'ruth@cohen-design.co.il',
        status: 'dormant',
        source: 'whatsapp',
        probability: 10,
        value: 12000,
        last_contact: '2025-07-20',
        next_action: 'נסיון יצירת קשר מחדש',
        tags: ['עיצוב', 'לא מגיב'],
        created_at: '2025-07-15',
        notes: 'התעניינה בעבר, אין מענה לפניותינו האחרונות.',
        interactions: 4,
        lead_score: 25
      }
    ];

    setLeads([...demoLeads, ...additionalLeads]);
    setContracts(demoContracts);
    setInvoices(demoInvoices);
    setTasks(demoTasks);
    setLoading(false);
  };

  // Function to update lead status
  const updateLeadStatus = async (leadId, newStatus) => {
    setLeads(prevLeads => 
      prevLeads.map(lead => 
        lead.id === leadId 
          ? { ...lead, status: newStatus, last_contact: new Date().toISOString().split('T')[0] }
          : lead
      )
    );
    
    // In real app, would call API here
    // await fetch(`/api/leads/${leadId}/status`, { method: 'PATCH', body: JSON.stringify({ status: newStatus }) });
  };

  // Function to get status display info
  const getStatusInfo = (status) => {
    const statusMap = {
      'new': { label: '🆕 ליד חדש', color: 'bg-blue-100 text-blue-800' },
      'contacted': { label: '☎️ יצרנו קשר', color: 'bg-yellow-100 text-yellow-800' },
      'interested': { label: '😊 מעוניין', color: 'bg-green-100 text-green-800' },
      'follow_up': { label: '🔄 לחזור אליו', color: 'bg-orange-100 text-orange-800' },
      'proposal_sent': { label: '📄 הצעה נשלחה', color: 'bg-purple-100 text-purple-800' },
      'negotiation': { label: '🤝 במשא ומתן', color: 'bg-indigo-100 text-indigo-800' },
      'won': { label: '✅ נסגר בהצלחה', color: 'bg-green-100 text-green-800' },
      'lost': { label: '❌ אבד', color: 'bg-red-100 text-red-800' },
      'dormant': { label: '😴 לא פעיל', color: 'bg-gray-100 text-gray-800' },
      // Legacy statuses
      'hot': { label: '🔥 חם', color: 'bg-red-100 text-red-800' },
      'warm': { label: '🌡️ חמים', color: 'bg-orange-100 text-orange-800' },
      'cold': { label: '🧊 קר', color: 'bg-blue-100 text-blue-800' }
    };
    return statusMap[status] || { label: status, color: 'bg-gray-100 text-gray-800' };
  };

  // Filter functions
  const filteredLeads = leads.filter(lead => {
    const matchesSearch = lead.name.toLowerCase().includes(searchTerm.toLowerCase()) ||
                         lead.company.toLowerCase().includes(searchTerm.toLowerCase()) ||
                         lead.phone.includes(searchTerm) ||
                         lead.email.toLowerCase().includes(searchTerm.toLowerCase());
    
    const matchesStatus = statusFilter === 'all' || lead.status === statusFilter;
    const matchesSource = sourceFilter === 'all' || lead.source === sourceFilter;
    const matchesProbability = probabilityFilter === 'all' || 
      (probabilityFilter === 'high' && lead.probability >= 80) ||
      (probabilityFilter === 'medium' && lead.probability >= 50 && lead.probability < 80) ||
      (probabilityFilter === 'low' && lead.probability < 50);
    
    return matchesSearch && matchesStatus && matchesSource && matchesProbability;
  });

  const getStatusColor = (status) => {
    switch (status) {
      case 'hot': return 'bg-red-100 text-red-800 border-red-200';
      case 'warm': return 'bg-orange-100 text-orange-800 border-orange-200';
      case 'cold': return 'bg-blue-100 text-blue-800 border-blue-200';
      case 'active': return 'bg-green-100 text-green-800 border-green-200';
      case 'draft': return 'bg-gray-100 text-gray-800 border-gray-200';
      case 'pending': return 'bg-yellow-100 text-yellow-800 border-yellow-200';
      case 'paid': return 'bg-green-100 text-green-800 border-green-200';
      case 'overdue': return 'bg-red-100 text-red-800 border-red-200';
      case 'completed': return 'bg-green-100 text-green-800 border-green-200';
      default: return 'bg-gray-100 text-gray-800 border-gray-200';
    }
  };

  const getStatusText = (status) => {
    switch (status) {
      case 'hot': return 'חם';
      case 'warm': return 'חמים';
      case 'cold': return 'קר';
      case 'active': return 'פעיל';
      case 'draft': return 'טיוטה';
      case 'pending': return 'ממתין';
      case 'paid': return 'שולם';
      case 'overdue': return 'באיחור';
      case 'completed': return 'הושלם';
      default: return status;
    }
  };

  const getPriorityColor = (priority) => {
    switch (priority) {
      case 'high': return 'bg-red-500';
      case 'medium': return 'bg-yellow-500';
      case 'low': return 'bg-green-500';
      default: return 'bg-gray-500';
    }
  };

  const createInvoice = (customer) => {
    setSelectedCustomer(customer);
    setModalType('invoice');
    setShowModal(true);
  };

  const createContract = (customer) => {
    setSelectedCustomer(customer);
    setModalType('contract');
    setShowModal(true);
  };

  const createPaymentLink = (invoice) => {
    // Copy payment link to clipboard
    navigator.clipboard.writeText(invoice.payment_link);
    alert('קישור תשלום הועתק ללוח!');
  };

  const markAsPaid = (invoiceId) => {
    setInvoices(prev => prev.map(inv => 
      inv.id === invoiceId 
        ? { ...inv, status: 'paid', paid_date: new Date().toISOString().split('T')[0] }
        : inv
    ));
  };

  const openCustomerDetails = (customer) => {
    setSelectedCustomer(customer);
    setModalType('customer');
    setShowModal(true);
  };

  if (loading) {
    return (
      <ModernLayout userRole={userRole}>
        <div className="flex items-center justify-center min-h-[400px]">
          <div className="text-center">
            <div className="animate-spin rounded-full h-32 w-32 border-b-2 border-purple-600 mx-auto mb-4"></div>
            <p className="text-gray-600">טוען CRM מתקדם...</p>
          </div>
        </div>
      </ModernLayout>
    );
  }

  return (
    <ModernLayout userRole={userRole}>
      <div className="space-y-8">
        {/* Header */}
        <div className="bg-gradient-to-r from-purple-600 to-indigo-700 rounded-3xl p-8 text-white">
          <div className="flex items-center justify-between">
            <div>
              <h1 className="text-4xl font-bold mb-2 flex items-center gap-3">
                <Briefcase className="w-10 h-10" />
                🚀 CRM מתקדם
              </h1>
              <p className="text-purple-100 text-lg">
                ניהול מתקדם של ליידים, חוזים, חשבוניות ומשימות
              </p>
            </div>
            <div className="text-left space-y-2">
              <div className="text-3xl font-bold">₪{invoices.reduce((sum, inv) => sum + inv.total, 0).toLocaleString()}</div>
              <div className="text-purple-100">סה"כ הכנסות</div>
            </div>
          </div>
        </div>

        {/* Stats Cards */}
        <div className="grid grid-cols-1 md:grid-cols-5 gap-6">
          <div className="bg-white rounded-2xl p-6 shadow-lg border border-gray-100">
            <div className="flex items-center justify-between mb-2">
              <Target className="w-8 h-8 text-red-500" />
              <span className="text-2xl font-bold text-red-600">
                {leads.filter(l => l.status === 'hot').length}
              </span>
            </div>
            <p className="text-gray-600 text-sm">ליידים חמים</p>
          </div>

          <div className="bg-white rounded-2xl p-6 shadow-lg border border-gray-100">
            <div className="flex items-center justify-between mb-2">
              <FileText className="w-8 h-8 text-blue-500" />
              <span className="text-2xl font-bold text-blue-600">
                {contracts.filter(c => c.status === 'active').length}
              </span>
            </div>
            <p className="text-gray-600 text-sm">חוזים פעילים</p>
          </div>

          <div className="bg-white rounded-2xl p-6 shadow-lg border border-gray-100">
            <div className="flex items-center justify-between mb-2">
              <Receipt className="w-8 h-8 text-green-500" />
              <span className="text-2xl font-bold text-green-600">
                {invoices.filter(i => i.status === 'paid').length}
              </span>
            </div>
            <p className="text-gray-600 text-sm">חשבוניות שולמו</p>
          </div>

          <div className="bg-white rounded-2xl p-6 shadow-lg border border-gray-100">
            <div className="flex items-center justify-between mb-2">
              <AlertCircle className="w-8 h-8 text-orange-500" />
              <span className="text-2xl font-bold text-orange-600">
                {tasks.filter(t => t.status === 'pending').length}
              </span>
            </div>
            <p className="text-gray-600 text-sm">משימות פתוחות</p>
          </div>

          <div className="bg-white rounded-2xl p-6 shadow-lg border border-gray-100">
            <div className="flex items-center justify-between mb-2">
              <TrendingUp className="w-8 h-8 text-purple-500" />
              <span className="text-2xl font-bold text-purple-600">
                {Math.round(leads.reduce((sum, l) => sum + l.probability, 0) / leads.length)}%
              </span>
            </div>
            <p className="text-gray-600 text-sm">ממוצע הצלחה</p>
          </div>
        </div>

        {/* Navigation Tabs */}
        <div className="bg-white rounded-2xl shadow-lg border border-gray-100 overflow-hidden">
          <div className="flex border-b border-gray-200">
            {[
              { id: 'leads', label: '🎯 ליידים', count: leads.length },
              { id: 'contracts', label: '📄 חוזים', count: contracts.length },
              { id: 'invoices', label: '🧾 חשבוניות', count: invoices.length },
              { id: 'tasks', label: '✅ משימות', count: tasks.filter(t => t.status === 'pending').length }
            ].map(tab => (
              <button
                key={tab.id}
                onClick={() => setActiveTab(tab.id)}
                className={`flex-1 px-6 py-4 text-center font-medium transition-colors relative ${
                  activeTab === tab.id
                    ? 'bg-purple-50 text-purple-600 border-b-2 border-purple-600'
                    : 'text-gray-600 hover:text-purple-600 hover:bg-gray-50'
                }`}
              >
                <span className="flex items-center justify-center gap-2">
                  {tab.label}
                  <span className={`px-2 py-1 rounded-full text-xs ${
                    activeTab === tab.id ? 'bg-purple-600 text-white' : 'bg-gray-200 text-gray-600'
                  }`}>
                    {tab.count}
                  </span>
                </span>
              </button>
            ))}
          </div>

          {/* Search and Filters */}
          <div className="p-6 border-b border-gray-200">
            <div className="flex flex-wrap gap-4 items-center">
              <div className="relative flex-1 min-w-[300px]">
                <Search className="w-5 h-5 text-gray-400 absolute right-3 top-1/2 transform -translate-y-1/2" />
                <input
                  type="text"
                  placeholder={`חיפוש ${activeTab === 'leads' ? 'ליידים' : activeTab === 'contracts' ? 'חוזים' : activeTab === 'invoices' ? 'חשבוניות' : 'משימות'}...`}
                  value={searchTerm}
                  onChange={(e) => setSearchTerm(e.target.value)}
                  className="w-full bg-gray-50 border border-gray-200 rounded-xl pr-10 pl-4 py-3 focus:outline-none focus:ring-2 focus:ring-purple-500"
                />
              </div>

              {activeTab === 'leads' && (
                <>
                  <select
                    value={statusFilter}
                    onChange={(e) => setStatusFilter(e.target.value)}
                    className="bg-gray-50 border border-gray-200 rounded-xl px-4 py-3 focus:outline-none focus:ring-2 focus:ring-purple-500"
                  >
                    <option value="all">כל הסטטוסים</option>
                    <option value="new">🆕 ליד חדש</option>
                    <option value="contacted">☎️ יצרנו קשר</option>
                    <option value="interested">😊 מעוניין</option>
                    <option value="follow_up">🔄 לחזור אליו</option>
                    <option value="proposal_sent">📄 הצעה נשלחה</option>
                    <option value="negotiation">🤝 במשא ומתן</option>
                    <option value="won">✅ נסגר בהצלחה</option>
                    <option value="lost">❌ אבד</option>
                    <option value="dormant">😴 לא פעיל</option>
                  </select>

                  <select
                    value={sourceFilter}
                    onChange={(e) => setSourceFilter(e.target.value)}
                    className="bg-gray-50 border border-gray-200 rounded-xl px-4 py-3 focus:outline-none focus:ring-2 focus:ring-purple-500"
                  >
                    <option value="all">כל המקורות</option>
                    <option value="whatsapp">WhatsApp</option>
                    <option value="phone">טלפון</option>
                    <option value="website">אתר</option>
                    <option value="referral">הפניה</option>
                  </select>

                  <select
                    value={probabilityFilter}
                    onChange={(e) => setProbabilityFilter(e.target.value)}
                    className="bg-gray-50 border border-gray-200 rounded-xl px-4 py-3 focus:outline-none focus:ring-2 focus:ring-purple-500"
                  >
                    <option value="all">כל הסיכויים</option>
                    <option value="high">גבוה (80%+)</option>
                    <option value="medium">בינוני (50-80%)</option>
                    <option value="low">נמוך (פחות מ-50%)</option>
                  </select>
                </>
              )}
              
              <button
                onClick={() => {
                  setModalType('customer');
                  setSelectedCustomer(null);
                  setShowModal(true);
                }}
                className="flex items-center gap-2 px-4 py-3 bg-purple-500 text-white rounded-xl hover:bg-purple-600"
              >
                <Plus className="w-4 h-4" />
                {activeTab === 'leads' ? 'ליד חדש' : activeTab === 'contracts' ? 'חוזה חדש' : activeTab === 'invoices' ? 'חשבונית חדשה' : 'משימה חדשה'}
              </button>
            </div>
          </div>

          {/* Content Area */}
          <div className="p-6">
            {/* Leads Tab */}
            {activeTab === 'leads' && (
              <div className="space-y-4">
                {filteredLeads.map(lead => (
                  <div key={lead.id} className="bg-gradient-to-r from-gray-50 to-white rounded-xl p-6 border border-gray-200 hover:shadow-lg transition-all">
                    <div className="flex items-start justify-between">
                      <div className="flex items-start gap-4">
                        <div className="w-12 h-12 bg-gradient-to-br from-purple-500 to-indigo-600 rounded-full flex items-center justify-center text-white font-bold">
                          {lead.name.charAt(0)}
                        </div>
                        
                        <div className="flex-1">
                          <div className="flex items-center gap-3 mb-2">
                            <h3 className="text-lg font-bold text-gray-900">{lead.name}</h3>
                            <select 
                              value={lead.status} 
                              onChange={(e) => updateLeadStatus(lead.id, e.target.value)}
                              className={`px-3 py-1 rounded-full text-sm font-medium border cursor-pointer focus:outline-none focus:ring-2 focus:ring-purple-500 ${getStatusInfo(lead.status).color}`}
                            >
                              <option value="new">🆕 ליד חדש</option>
                              <option value="contacted">☎️ יצרנו קשר</option>
                              <option value="interested">😊 מעוניין</option>
                              <option value="follow_up">🔄 לחזור אליו</option>
                              <option value="proposal_sent">📄 הצעה נשלחה</option>
                              <option value="negotiation">🤝 במשא ומתן</option>
                              <option value="won">✅ נסגר בהצלחה</option>
                              <option value="lost">❌ אבד</option>
                              <option value="dormant">😴 לא פעיל</option>
                            </select>
                            <div className="flex items-center gap-1">
                              <Star className="w-4 h-4 text-yellow-500" />
                              <span className="text-sm font-medium">{lead.lead_score}</span>
                            </div>
                          </div>
                          
                          <div className="grid md:grid-cols-2 gap-4 mb-3">
                            <div className="space-y-1">
                              <p className="text-gray-600 flex items-center gap-2">
                                <Building2 className="w-4 h-4" />
                                {lead.company}
                              </p>
                              <p className="text-gray-600 flex items-center gap-2">
                                <Phone className="w-4 h-4" />
                                {lead.phone}
                              </p>
                              <p className="text-gray-600 flex items-center gap-2">
                                <Mail className="w-4 h-4" />
                                {lead.email}
                              </p>
                            </div>
                            
                            <div className="space-y-1">
                              <p className="text-gray-600">
                                <span className="font-medium">ערך פוטנציאלי:</span> ₪{lead.value.toLocaleString()}
                              </p>
                              <p className="text-gray-600">
                                <span className="font-medium">הסתברות:</span> {lead.probability}%
                              </p>
                              <p className="text-gray-600">
                                <span className="font-medium">מקור:</span> {lead.source === 'whatsapp' ? 'WhatsApp' : lead.source === 'phone' ? 'טלפון' : lead.source === 'website' ? 'אתר' : 'אחר'}
                              </p>
                            </div>
                          </div>
                          
                          <div className="bg-blue-50 rounded-lg p-3 mb-3">
                            <p className="text-sm text-gray-700">
                              <span className="font-medium">פעולה הבאה:</span> {lead.next_action}
                            </p>
                          </div>
                          
                          <div className="flex flex-wrap gap-2 mb-3">
                            {lead.tags.map(tag => (
                              <span key={tag} className="px-2 py-1 bg-purple-100 text-purple-800 text-xs rounded-full">
                                {tag}
                              </span>
                            ))}
                          </div>
                        </div>
                      </div>
                      
                      <div className="flex items-center gap-2">
                        <button
                          onClick={() => openCustomerDetails(lead)}
                          className="p-2 text-gray-600 hover:text-blue-600 hover:bg-blue-50 rounded-lg"
                        >
                          <Eye className="w-5 h-5" />
                        </button>
                        
                        <button
                          onClick={() => createContract(lead)}
                          className="px-3 py-2 bg-green-500 text-white rounded-lg hover:bg-green-600 text-sm"
                        >
                          צור חוזה
                        </button>
                        
                        <button
                          onClick={() => createInvoice(lead)}
                          className="px-3 py-2 bg-blue-500 text-white rounded-lg hover:bg-blue-600 text-sm"
                        >
                          צור חשבונית
                        </button>
                        
                        <button className="p-2 text-gray-600 hover:text-gray-800 hover:bg-gray-100 rounded-lg">
                          <MoreVertical className="w-5 h-5" />
                        </button>
                      </div>
                    </div>
                  </div>
                ))}
              </div>
            )}

            {/* Contracts Tab */}
            {activeTab === 'contracts' && (
              <div className="space-y-6">
                {contracts.map(contract => (
                  <div key={contract.id} className="bg-gradient-to-r from-green-50 to-white rounded-xl p-6 border border-gray-200 hover:shadow-lg transition-all">
                    <div className="flex items-start justify-between mb-4">
                      <div>
                        <h3 className="text-xl font-bold text-gray-900 mb-2">{contract.title}</h3>
                        <p className="text-gray-600 mb-1">לקוח: {contract.customer_name}</p>
                        <p className="text-lg font-bold text-green-600">₪{contract.value.toLocaleString()}</p>
                      </div>
                      
                      <div className="flex items-center gap-3">
                        <span className={`inline-flex items-center px-3 py-1 rounded-full text-sm font-medium border ${getStatusColor(contract.status)}`}>
                          {getStatusText(contract.status)}
                        </span>
                        <button className="p-2 text-gray-600 hover:text-gray-800 hover:bg-gray-100 rounded-lg">
                          <MoreVertical className="w-5 h-5" />
                        </button>
                      </div>
                    </div>
                    
                    <div className="grid md:grid-cols-2 gap-6 mb-4">
                      <div>
                        <p className="text-sm text-gray-600 mb-1">תאריך התחלה</p>
                        <p className="font-medium">{new Date(contract.start_date).toLocaleDateString('he-IL')}</p>
                      </div>
                      <div>
                        <p className="text-sm text-gray-600 mb-1">תאריך סיום</p>
                        <p className="font-medium">{new Date(contract.end_date).toLocaleDateString('he-IL')}</p>
                      </div>
                    </div>
                    
                    <div className="mb-4">
                      <h4 className="font-medium text-gray-900 mb-3">אבני דרך</h4>
                      <div className="space-y-2">
                        {contract.milestones.map(milestone => (
                          <div key={milestone.id} className="flex items-center justify-between p-3 bg-gray-50 rounded-lg">
                            <div className="flex items-center gap-3">
                              <div className={`w-3 h-3 rounded-full ${
                                milestone.status === 'completed' ? 'bg-green-500' :
                                milestone.status === 'in_progress' ? 'bg-blue-500' : 'bg-gray-300'
                              }`}></div>
                              <span className="font-medium">{milestone.title}</span>
                            </div>
                            <div className="flex items-center gap-3">
                              <span className="text-green-600 font-medium">₪{milestone.amount.toLocaleString()}</span>
                              <span className={`px-2 py-1 rounded-full text-xs border ${getStatusColor(milestone.status)}`}>
                                {getStatusText(milestone.status)}
                              </span>
                            </div>
                          </div>
                        ))}
                      </div>
                    </div>
                    
                    <div className="flex gap-3">
                      <button className="px-4 py-2 bg-blue-500 text-white rounded-lg hover:bg-blue-600">
                        <Download className="w-4 h-4 inline mr-2" />
                        הורד חוזה
                      </button>
                      <button className="px-4 py-2 bg-purple-500 text-white rounded-lg hover:bg-purple-600">
                        <Edit className="w-4 h-4 inline mr-2" />
                        ערוך
                      </button>
                      {contract.status === 'draft' && (
                        <button className="px-4 py-2 bg-green-500 text-white rounded-lg hover:bg-green-600">
                          <Send className="w-4 h-4 inline mr-2" />
                          שלח לחתימה
                        </button>
                      )}
                    </div>
                  </div>
                ))}
              </div>
            )}

            {/* Invoices Tab */}
            {activeTab === 'invoices' && (
              <div className="space-y-4">
                {invoices.map(invoice => (
                  <div key={invoice.id} className="bg-gradient-to-r from-blue-50 to-white rounded-xl p-6 border border-gray-200 hover:shadow-lg transition-all">
                    <div className="flex items-start justify-between mb-4">
                      <div>
                        <h3 className="text-lg font-bold text-gray-900 mb-1">{invoice.invoice_number}</h3>
                        <p className="text-gray-600 mb-1">{invoice.customer_name}</p>
                        <p className="text-sm text-gray-500">{invoice.description}</p>
                      </div>
                      
                      <div className="text-left">
                        <p className="text-2xl font-bold text-gray-900">₪{invoice.total.toLocaleString()}</p>
                        <span className={`inline-flex items-center px-3 py-1 rounded-full text-sm font-medium border ${getStatusColor(invoice.status)}`}>
                          {getStatusText(invoice.status)}
                        </span>
                      </div>
                    </div>
                    
                    <div className="grid md:grid-cols-3 gap-4 mb-4">
                      <div>
                        <p className="text-sm text-gray-600">תאריך הנפקה</p>
                        <p className="font-medium">{new Date(invoice.issue_date).toLocaleDateString('he-IL')}</p>
                      </div>
                      <div>
                        <p className="text-sm text-gray-600">תאריך לתשלום</p>
                        <p className="font-medium">{new Date(invoice.due_date).toLocaleDateString('he-IL')}</p>
                      </div>
                      <div>
                        <p className="text-sm text-gray-600">תאריך תשלום</p>
                        <p className="font-medium">{invoice.paid_date ? new Date(invoice.paid_date).toLocaleDateString('he-IL') : 'לא שולם'}</p>
                      </div>
                    </div>
                    
                    <div className="flex gap-3">
                      <button className="px-4 py-2 bg-blue-500 text-white rounded-lg hover:bg-blue-600">
                        <Download className="w-4 h-4 inline mr-2" />
                        הורד PDF
                      </button>
                      
                      {invoice.status === 'pending' && (
                        <>
                          <button 
                            onClick={() => createPaymentLink(invoice)}
                            className="px-4 py-2 bg-green-500 text-white rounded-lg hover:bg-green-600"
                          >
                            <Link2 className="w-4 h-4 inline mr-2" />
                            קישור תשלום
                          </button>
                          
                          <button 
                            onClick={() => markAsPaid(invoice.id)}
                            className="px-4 py-2 bg-purple-500 text-white rounded-lg hover:bg-purple-600"
                          >
                            <CheckCircle className="w-4 h-4 inline mr-2" />
                            סמן כשולם
                          </button>
                        </>
                      )}
                      
                      {invoice.status === 'overdue' && (
                        <button className="px-4 py-2 bg-red-500 text-white rounded-lg hover:bg-red-600">
                          <AlertCircle className="w-4 h-4 inline mr-2" />
                          שלח תזכורת
                        </button>
                      )}
                    </div>
                  </div>
                ))}
              </div>
            )}

            {/* Tasks Tab */}
            {activeTab === 'tasks' && (
              <div className="space-y-4">
                {tasks.map(task => (
                  <div key={task.id} className="bg-gradient-to-r from-yellow-50 to-white rounded-xl p-6 border border-gray-200 hover:shadow-lg transition-all">
                    <div className="flex items-start justify-between mb-3">
                      <div className="flex items-start gap-4">
                        <div className={`w-1 h-full rounded-full ${getPriorityColor(task.priority)}`}></div>
                        
                        <div>
                          <h3 className="text-lg font-bold text-gray-900 mb-1">{task.title}</h3>
                          <p className="text-gray-600 mb-2">{task.description}</p>
                          <p className="text-sm text-gray-500">לקוח: {task.customer_name}</p>
                          <p className="text-sm text-gray-500">מוקצה ל: {task.assigned_to}</p>
                        </div>
                      </div>
                      
                      <div className="text-left">
                        <div className="flex items-center gap-2 mb-2">
                          <Clock className="w-4 h-4 text-gray-500" />
                          <span className="text-sm text-gray-600">{new Date(task.due_date).toLocaleDateString('he-IL')}</span>
                        </div>
                        <span className={`inline-flex items-center px-3 py-1 rounded-full text-sm font-medium border ${getStatusColor(task.status)}`}>
                          {getStatusText(task.status)}
                        </span>
                      </div>
                    </div>
                    
                    {task.status === 'pending' && (
                      <div className="flex gap-3">
                        <button className="px-4 py-2 bg-green-500 text-white rounded-lg hover:bg-green-600">
                          <Check className="w-4 h-4 inline mr-2" />
                          סמן כהושלם
                        </button>
                        <button className="px-4 py-2 bg-blue-500 text-white rounded-lg hover:bg-blue-600">
                          <Edit className="w-4 h-4 inline mr-2" />
                          ערוך
                        </button>
                      </div>
                    )}
                  </div>
                ))}
              </div>
            )}
          </div>
        </div>
      </div>

      {/* Modal */}
      {showModal && (
        <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50">
          <div className="bg-white rounded-2xl p-8 max-w-2xl w-full mx-4 max-h-[90vh] overflow-y-auto">
            <div className="flex items-center justify-between mb-6">
              <h2 className="text-2xl font-bold">
                {modalType === 'customer' && 'פרטי לקוח'}
                {modalType === 'invoice' && 'צור חשבונית חדשה'}
                {modalType === 'contract' && 'צור חוזה חדש'}
              </h2>
              <button 
                onClick={() => setShowModal(false)}
                className="p-2 hover:bg-gray-100 rounded-lg"
              >
                <X className="w-6 h-6" />
              </button>
            </div>
            
            {modalType === 'customer' && selectedCustomer && (
              <div className="space-y-6">
                <div className="bg-gray-50 rounded-xl p-6">
                  <h3 className="font-bold text-lg mb-4">{selectedCustomer.name}</h3>
                  <div className="grid md:grid-cols-2 gap-4">
                    <div>
                      <p><span className="font-medium">חברה:</span> {selectedCustomer.company}</p>
                      <p><span className="font-medium">טלפון:</span> {selectedCustomer.phone}</p>
                      <p><span className="font-medium">אימייל:</span> {selectedCustomer.email}</p>
                    </div>
                    <div>
                      <p><span className="font-medium">ערך:</span> ₪{selectedCustomer.value?.toLocaleString()}</p>
                      <p><span className="font-medium">הסתברות:</span> {selectedCustomer.probability}%</p>
                      <p><span className="font-medium">אינטראקציות:</span> {selectedCustomer.interactions}</p>
                    </div>
                  </div>
                </div>
                
                {selectedCustomer.notes && (
                  <div>
                    <h4 className="font-medium mb-2">הערות</h4>
                    <p className="text-gray-700 bg-gray-50 p-3 rounded-lg">{selectedCustomer.notes}</p>
                  </div>
                )}
                
                <div className="flex gap-3">
                  <button 
                    onClick={() => createContract(selectedCustomer)}
                    className="px-4 py-2 bg-green-500 text-white rounded-lg hover:bg-green-600"
                  >
                    צור חוזה
                  </button>
                  <button 
                    onClick={() => createInvoice(selectedCustomer)}
                    className="px-4 py-2 bg-blue-500 text-white rounded-lg hover:bg-blue-600"
                  >
                    צור חשבונית
                  </button>
                </div>
              </div>
            )}
            
            {modalType === 'invoice' && (
              <div className="space-y-4">
                <p className="text-gray-600">יצירת חשבונית חדשה עבור {selectedCustomer?.name}</p>
                <div className="grid md:grid-cols-2 gap-4">
                  <div>
                    <label className="block text-sm font-medium mb-2">סכום (לפני מס)</label>
                    <input type="number" className="w-full border border-gray-300 rounded-lg px-3 py-2" placeholder="0" />
                  </div>
                  <div>
                    <label className="block text-sm font-medium mb-2">תיאור</label>
                    <input type="text" className="w-full border border-gray-300 rounded-lg px-3 py-2" placeholder="תיאור השירות" />
                  </div>
                </div>
                <div className="flex gap-3 justify-end">
                  <button 
                    onClick={() => setShowModal(false)}
                    className="px-4 py-2 border border-gray-300 rounded-lg hover:bg-gray-50"
                  >
                    ביטול
                  </button>
                  <button className="px-4 py-2 bg-blue-500 text-white rounded-lg hover:bg-blue-600">
                    צור חשבונית
                  </button>
                </div>
              </div>
            )}
            
            {modalType === 'contract' && (
              <div className="space-y-4">
                <p className="text-gray-600">יצירת חוזה חדש עבור {selectedCustomer?.name}</p>
                <div className="grid md:grid-cols-2 gap-4">
                  <div>
                    <label className="block text-sm font-medium mb-2">כותרת החוזה</label>
                    <input type="text" className="w-full border border-gray-300 rounded-lg px-3 py-2" placeholder="שם הפרויקט" />
                  </div>
                  <div>
                    <label className="block text-sm font-medium mb-2">סכום</label>
                    <input type="number" className="w-full border border-gray-300 rounded-lg px-3 py-2" placeholder="0" />
                  </div>
                </div>
                <div className="grid md:grid-cols-2 gap-4">
                  <div>
                    <label className="block text-sm font-medium mb-2">תאריך התחלה</label>
                    <input type="date" className="w-full border border-gray-300 rounded-lg px-3 py-2" />
                  </div>
                  <div>
                    <label className="block text-sm font-medium mb-2">תאריך סיום</label>
                    <input type="date" className="w-full border border-gray-300 rounded-lg px-3 py-2" />
                  </div>
                </div>
                <div className="flex gap-3 justify-end">
                  <button 
                    onClick={() => setShowModal(false)}
                    className="px-4 py-2 border border-gray-300 rounded-lg hover:bg-gray-50"
                  >
                    ביטול
                  </button>
                  <button className="px-4 py-2 bg-green-500 text-white rounded-lg hover:bg-green-600">
                    צור חוזה
                  </button>
                </div>
              </div>
            )}
          </div>
        </div>
      )}
    </ModernLayout>
  );
}