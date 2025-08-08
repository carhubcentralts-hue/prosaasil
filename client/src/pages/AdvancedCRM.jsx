import React, { useState, useEffect } from 'react';
import ModernLayout from '../components/ModernLayout';
import { 
  Users, Plus, Search, Filter, Star, Phone, MessageSquare,
  Eye, Edit3, Trash2, FileText, Receipt, PenTool, Calendar,
  ArrowUpRight, TrendingUp, Activity, UserCheck, Building2,
  Mail, MapPin, Clock, Tag, ChevronDown, MoreVertical,
  Target, DollarSign, CheckCircle2, AlertTriangle, 
  XCircle, RefreshCw, Bell, Archive, Send, Copy,
  Download, Upload, Settings, BarChart3, Zap,
  Shield, Lock, User, Briefcase, CreditCard, 
  FileContract, Calculator, CalendarCheck, Timer
} from 'lucide-react';

export default function AdvancedCRM() {
  const [userRole, setUserRole] = useState('business');
  const [activeTab, setActiveTab] = useState('leads');
  const [leads, setLeads] = useState([]);
  const [contracts, setContracts] = useState([]);
  const [invoices, setInvoices] = useState([]);
  const [tasks, setTasks] = useState([]);
  const [loading, setLoading] = useState(true);
  const [searchTerm, setSearchTerm] = useState('');
  const [filterStatus, setFilterStatus] = useState('all');
  const [showTaskNotification, setShowTaskNotification] = useState(null);

  useEffect(() => {
    const role = localStorage.getItem('user_role') || localStorage.getItem('userRole');
    setUserRole(role || 'business');
    loadCRMData(role);
    checkTaskNotifications();
    
    // Check for task notifications every minute
    const interval = setInterval(checkTaskNotifications, 60000);
    return () => clearInterval(interval);
  }, []);

  const checkTaskNotifications = () => {
    const now = new Date();
    const dueTasks = tasks.filter(task => {
      if (task.status === 'completed') return false;
      const dueDate = new Date(task.due_date + ' ' + task.due_time);
      return dueDate <= now && dueDate > new Date(now.getTime() - 5 * 60000); // Within last 5 minutes
    });
    
    if (dueTasks.length > 0) {
      setShowTaskNotification(dueTasks[0]);
    }
  };

  const loadCRMData = async (role) => {
    try {
      // Demo leads data
      const demoLeads = [
        {
          id: 1,
          name: 'אליעזר רוזנברג',
          phone: '050-1234567',
          email: 'eliezer@example.com',
          status: 'new',
          source: 'שיחה טלפונית',
          value: 25000,
          probability: 75,
          created_at: '2025-08-07',
          last_contact: '2025-08-07',
          next_action: 'קביעת פגישה',
          tags: ['VIP', 'דחוף'],
          notes: 'לקוח פוטנציאלי חזק, מעוניין בפתרון מלא',
          business_id: 1,
          assigned_to: 'יוסי כהן'
        },
        {
          id: 2,
          name: 'שרה לוי',
          phone: '052-9876543',
          email: 'sarah@business.com',
          status: 'qualified',
          source: 'WhatsApp',
          value: 15000,
          probability: 60,
          created_at: '2025-08-06',
          last_contact: '2025-08-06',
          next_action: 'שליחת הצעת מחיר',
          tags: ['חם', 'מעקב'],
          notes: 'לקוח חוזר, זקוק לפתרון מותאם אישית',
          business_id: 1,
          assigned_to: 'רחל כהן'
        },
        {
          id: 3,
          name: 'דוד אברהם',
          phone: '053-5555555',
          email: 'david@company.co.il',
          status: 'proposal',
          source: 'אתר אינטרנט',
          value: 40000,
          probability: 85,
          created_at: '2025-08-05',
          last_contact: '2025-08-06',
          next_action: 'חתימה על חוזה',
          tags: ['חוזה', 'VIP'],
          notes: 'הצעת מחיר אושרה, ממתין לחתימה',
          business_id: 1,
          assigned_to: 'יוסי כהן'
        }
      ];

      // Demo contracts data
      const demoContracts = [
        {
          id: 1,
          title: 'חוזה שירותי ייעוץ - אליעזר רוזנברג',
          client_name: 'אליעזר רוזנברג',
          value: 25000,
          status: 'active',
          start_date: '2025-08-01',
          end_date: '2025-12-31',
          payment_terms: '30 ימים',
          signed_date: '2025-07-28',
          services: 'ייעוץ עסקי ואסטרטגי למשך 5 חודשים',
          milestones: [
            { name: 'תכנון אסטרטגי', due_date: '2025-08-15', status: 'completed' },
            { name: 'יישום שלב ראשון', due_date: '2025-09-15', status: 'in_progress' },
            { name: 'הערכת ביניים', due_date: '2025-10-15', status: 'pending' }
          ]
        },
        {
          id: 2,
          title: 'חוזה פיתוח מערכת - שרה לוי',
          client_name: 'שרה לוי',
          value: 15000,
          status: 'pending_signature',
          start_date: '2025-08-15',
          end_date: '2025-11-15',
          payment_terms: '50% מקדמה, יתרה בסיום',
          signed_date: null,
          services: 'פיתוח מערכת CRM מותאמת',
          milestones: [
            { name: 'תכנון מערכת', due_date: '2025-08-30', status: 'pending' },
            { name: 'פיתוח', due_date: '2025-10-15', status: 'pending' },
            { name: 'בדיקות והטמעה', due_date: '2025-11-15', status: 'pending' }
          ]
        }
      ];

      // Demo invoices data
      const demoInvoices = [
        {
          id: 1,
          number: 'INV-2025-001',
          client_name: 'אליעזר רוזנברג',
          amount: 12500,
          tax: 2125,
          total: 14625,
          status: 'paid',
          issue_date: '2025-08-01',
          due_date: '2025-08-31',
          paid_date: '2025-08-15',
          items: [
            { description: 'ייעוץ אסטרטגי - שלב 1', quantity: 1, price: 12500 }
          ],
          contract_id: 1
        },
        {
          id: 2,
          number: 'INV-2025-002',
          client_name: 'שרה לוי',
          amount: 7500,
          tax: 1275,
          total: 8775,
          status: 'pending',
          issue_date: '2025-08-05',
          due_date: '2025-09-04',
          paid_date: null,
          items: [
            { description: 'מקדמה - פיתוח מערכת CRM', quantity: 1, price: 7500 }
          ],
          contract_id: 2
        }
      ];

      // Demo tasks data
      const demoTasks = [
        {
          id: 1,
          title: 'התקשרות לאליעזר רוזנברג - מעקב פרויקט',
          description: 'לבדוק התקדמות בתכנון האסטרטגי ולקבוע פגישת מעקב',
          lead_id: 1,
          contract_id: 1,
          priority: 'high',
          status: 'pending',
          due_date: '2025-08-08',
          due_time: '10:00',
          assigned_to: 'יוסי כהן',
          created_at: '2025-08-07'
        },
        {
          id: 2,
          title: 'שליחת הצעת מחיר לשרה לוי',
          description: 'להכין הצעת מחיר מפורטת לפיתוח מערכת CRM',
          lead_id: 2,
          contract_id: null,
          priority: 'medium',
          status: 'in_progress',
          due_date: '2025-08-09',
          due_time: '14:00',
          assigned_to: 'רחל כהן',
          created_at: '2025-08-06'
        },
        {
          id: 3,
          title: 'חתימה על חוזה - דוד אברהם',
          description: 'לתאם פגישה לחתימה על החוזה',
          lead_id: 3,
          contract_id: null,
          priority: 'high',
          status: 'pending',
          due_date: '2025-08-08',
          due_time: '16:00',
          assigned_to: 'יוסי כהן',
          created_at: '2025-08-05'
        }
      ];

      setLeads(demoLeads);
      setContracts(demoContracts);
      setInvoices(demoInvoices);
      setTasks(demoTasks);
      setLoading(false);
    } catch (error) {
      console.error('Error loading CRM data:', error);
      setLoading(false);
    }
  };

  const getLeadStatusColor = (status) => {
    switch (status) {
      case 'new': return 'bg-blue-100 text-blue-800 border-blue-200';
      case 'qualified': return 'bg-yellow-100 text-yellow-800 border-yellow-200';
      case 'proposal': return 'bg-purple-100 text-purple-800 border-purple-200';
      case 'negotiation': return 'bg-orange-100 text-orange-800 border-orange-200';
      case 'closed_won': return 'bg-green-100 text-green-800 border-green-200';
      case 'closed_lost': return 'bg-red-100 text-red-800 border-red-200';
      default: return 'bg-gray-100 text-gray-800 border-gray-200';
    }
  };

  const getLeadStatusText = (status) => {
    switch (status) {
      case 'new': return 'חדש';
      case 'qualified': return 'מוכשר';
      case 'proposal': return 'הצעת מחיר';
      case 'negotiation': return 'משא ומתן';
      case 'closed_won': return 'נסגר בהצלחה';
      case 'closed_lost': return 'נסגר ללא הצלחה';
      default: return 'לא ידוע';
    }
  };

  const getPriorityColor = (priority) => {
    switch (priority) {
      case 'high': return 'text-red-600';
      case 'medium': return 'text-yellow-600';
      case 'low': return 'text-green-600';
      default: return 'text-gray-600';
    }
  };

  const getTaskStatusColor = (status) => {
    switch (status) {
      case 'pending': return 'bg-gray-100 text-gray-800 border-gray-200';
      case 'in_progress': return 'bg-blue-100 text-blue-800 border-blue-200';
      case 'completed': return 'bg-green-100 text-green-800 border-green-200';
      case 'overdue': return 'bg-red-100 text-red-800 border-red-200';
      default: return 'bg-gray-100 text-gray-800 border-gray-200';
    }
  };

  const formatCurrency = (amount) => {
    return new Intl.NumberFormat('he-IL', {
      style: 'currency',
      currency: 'ILS'
    }).format(amount);
  };

  const filteredLeads = leads.filter(lead => {
    const matchesSearch = lead.name.toLowerCase().includes(searchTerm.toLowerCase()) ||
                         lead.phone.includes(searchTerm) ||
                         lead.email.toLowerCase().includes(searchTerm.toLowerCase());
    const matchesStatus = filterStatus === 'all' || lead.status === filterStatus;
    return matchesSearch && matchesStatus;
  });

  if (loading) {
    return (
      <ModernLayout userRole={userRole}>
        <div className="flex items-center justify-center min-h-[400px]">
          <div className="text-center">
            <div className="animate-spin rounded-full h-32 w-32 border-b-2 border-blue-600 mx-auto mb-4"></div>
            <p className="text-gray-600">טוען נתוני CRM...</p>
          </div>
        </div>
      </ModernLayout>
    );
  }

  return (
    <ModernLayout userRole={userRole}>
      {/* Task Notification Popup */}
      {showTaskNotification && (
        <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50">
          <div className="bg-white rounded-2xl p-8 max-w-md w-full mx-4 shadow-2xl">
            <div className="text-center">
              <div className="w-16 h-16 bg-red-100 rounded-full flex items-center justify-center mx-auto mb-4">
                <Bell className="w-8 h-8 text-red-600" />
              </div>
              <h3 className="text-xl font-bold text-gray-900 mb-2">⏰ משימה דחופה!</h3>
              <p className="text-gray-600 mb-6">{showTaskNotification.title}</p>
              <div className="flex gap-4 justify-center">
                <button
                  onClick={() => setShowTaskNotification(null)}
                  className="px-6 py-2 bg-gray-500 text-white rounded-xl hover:bg-gray-600"
                >
                  סגור
                </button>
                <button
                  onClick={() => {
                    setActiveTab('tasks');
                    setShowTaskNotification(null);
                  }}
                  className="px-6 py-2 bg-blue-500 text-white rounded-xl hover:bg-blue-600"
                >
                  עבור למשימה
                </button>
              </div>
            </div>
          </div>
        </div>
      )}

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
                ניהול לקוחות, חוזים, חשבוניות ומשימות במקום אחד
              </p>
            </div>
            <div className="text-left">
              <div className="text-3xl font-bold">{leads.length}</div>
              <div className="text-purple-100">ליידים פעילים</div>
            </div>
          </div>
        </div>

        {/* Stats Cards */}
        <div className="grid grid-cols-1 md:grid-cols-4 gap-6">
          <div className="bg-white rounded-2xl p-6 shadow-lg border border-gray-100">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-gray-600 text-sm">ליידים חדשים</p>
                <p className="text-3xl font-bold text-blue-600">
                  {leads.filter(l => l.status === 'new').length}
                </p>
              </div>
              <Target className="w-12 h-12 text-blue-500" />
            </div>
          </div>
          
          <div className="bg-white rounded-2xl p-6 shadow-lg border border-gray-100">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-gray-600 text-sm">חוזים פעילים</p>
                <p className="text-3xl font-bold text-green-600">
                  {contracts.filter(c => c.status === 'active').length}
                </p>
              </div>
              <FileContract className="w-12 h-12 text-green-500" />
            </div>
          </div>

          <div className="bg-white rounded-2xl p-6 shadow-lg border border-gray-100">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-gray-600 text-sm">הכנסות החודש</p>
                <p className="text-3xl font-bold text-purple-600">
                  {formatCurrency(invoices.filter(i => i.status === 'paid').reduce((sum, i) => sum + i.total, 0))}
                </p>
              </div>
              <DollarSign className="w-12 h-12 text-purple-500" />
            </div>
          </div>

          <div className="bg-white rounded-2xl p-6 shadow-lg border border-gray-100">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-gray-600 text-sm">משימות דחופות</p>
                <p className="text-3xl font-bold text-red-600">
                  {tasks.filter(t => t.priority === 'high' && t.status !== 'completed').length}
                </p>
              </div>
              <Timer className="w-12 h-12 text-red-500" />
            </div>
          </div>
        </div>

        {/* Navigation Tabs */}
        <div className="bg-white rounded-2xl shadow-lg border border-gray-100 overflow-hidden">
          <div className="flex">
            {[
              { key: 'leads', label: 'ליידים', icon: Target },
              { key: 'contracts', label: 'חוזים', icon: FileContract },
              { key: 'invoices', label: 'חשבוניות', icon: Receipt },
              { key: 'tasks', label: 'משימות', icon: CalendarCheck }
            ].map(tab => {
              const Icon = tab.icon;
              return (
                <button
                  key={tab.key}
                  onClick={() => setActiveTab(tab.key)}
                  className={`flex-1 px-6 py-4 flex items-center justify-center gap-2 transition-all ${
                    activeTab === tab.key
                      ? 'bg-blue-500 text-white'
                      : 'text-gray-600 hover:bg-gray-50'
                  }`}
                >
                  <Icon className="w-5 h-5" />
                  {tab.label}
                </button>
              );
            })}
          </div>
        </div>

        {/* Tab Content */}
        <div className="bg-white rounded-2xl shadow-lg border border-gray-100 overflow-hidden">
          {/* Search Bar */}
          <div className="p-6 border-b border-gray-200">
            <div className="flex flex-wrap gap-4 items-center justify-between">
              <div className="relative flex-1 min-w-[300px]">
                <Search className="w-5 h-5 text-gray-400 absolute right-3 top-1/2 transform -translate-y-1/2" />
                <input
                  type="text"
                  placeholder={`חיפוש ${activeTab === 'leads' ? 'ליידים' : activeTab === 'contracts' ? 'חוזים' : activeTab === 'invoices' ? 'חשבוניות' : 'משימות'}...`}
                  value={searchTerm}
                  onChange={(e) => setSearchTerm(e.target.value)}
                  className="w-full bg-gray-50 border border-gray-200 rounded-xl pr-10 pl-4 py-3 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent"
                />
              </div>
              
              <div className="flex gap-4">
                <select
                  value={filterStatus}
                  onChange={(e) => setFilterStatus(e.target.value)}
                  className="bg-gray-50 border border-gray-200 rounded-xl px-4 py-3 focus:outline-none focus:ring-2 focus:ring-blue-500"
                >
                  <option value="all">כל הסטטוסים</option>
                  {activeTab === 'leads' && (
                    <>
                      <option value="new">חדש</option>
                      <option value="qualified">מוכשר</option>
                      <option value="proposal">הצעת מחיר</option>
                      <option value="negotiation">משא ומתן</option>
                      <option value="closed_won">נסגר בהצלחה</option>
                      <option value="closed_lost">נסגר ללא הצלחה</option>
                    </>
                  )}
                </select>
                
                <button className="bg-blue-500 text-white px-6 py-3 rounded-xl hover:bg-blue-600 flex items-center gap-2">
                  <Plus className="w-5 h-5" />
                  הוסף חדש
                </button>
              </div>
            </div>
          </div>

          {/* Leads Tab */}
          {activeTab === 'leads' && (
            <div className="space-y-4 p-6">
              {filteredLeads.map((lead) => (
                <div key={lead.id} className="bg-gray-50 rounded-2xl p-6 hover:bg-gray-100 transition-all duration-200 border border-gray-100">
                  <div className="flex items-start gap-4">
                    <div className="w-12 h-12 bg-gradient-to-br from-blue-500 to-purple-600 rounded-full flex items-center justify-center text-white font-bold">
                      {lead.name.charAt(0)}
                    </div>
                    
                    <div className="flex-1">
                      <div className="flex items-center justify-between mb-3">
                        <div>
                          <h3 className="text-lg font-bold text-gray-900 flex items-center gap-2">
                            {lead.name}
                            {lead.tags && lead.tags.map(tag => (
                              <span key={tag} className="text-xs bg-blue-100 text-blue-800 px-2 py-1 rounded-full">
                                {tag}
                              </span>
                            ))}
                          </h3>
                          <p className="text-sm text-gray-600 flex items-center gap-2">
                            <Phone className="w-4 h-4" />
                            {lead.phone}
                            <span className="mx-2">•</span>
                            <Mail className="w-4 h-4" />
                            {lead.email}
                          </p>
                        </div>
                        <div className="flex items-center gap-3">
                          <span className={`inline-flex items-center px-3 py-1 rounded-full text-sm font-medium border ${getLeadStatusColor(lead.status)}`}>
                            {getLeadStatusText(lead.status)}
                          </span>
                          <div className="text-right">
                            <div className="font-bold text-green-600">{formatCurrency(lead.value)}</div>
                            <div className="text-xs text-gray-500">{lead.probability}% סיכוי</div>
                          </div>
                        </div>
                      </div>

                      <div className="grid grid-cols-1 md:grid-cols-3 gap-4 mb-4">
                        <div className="bg-white rounded-lg p-3">
                          <div className="text-xs text-gray-500 mb-1">מקור הליד</div>
                          <div className="font-medium">{lead.source}</div>
                        </div>
                        <div className="bg-white rounded-lg p-3">
                          <div className="text-xs text-gray-500 mb-1">פעולה הבאה</div>
                          <div className="font-medium">{lead.next_action}</div>
                        </div>
                        <div className="bg-white rounded-lg p-3">
                          <div className="text-xs text-gray-500 mb-1">אחראי</div>
                          <div className="font-medium">{lead.assigned_to}</div>
                        </div>
                      </div>

                      {lead.notes && (
                        <div className="bg-white rounded-lg p-4 mb-4">
                          <div className="text-xs text-gray-500 mb-2">הערות</div>
                          <div className="text-sm text-gray-700">{lead.notes}</div>
                        </div>
                      )}

                      <div className="flex items-center gap-3">
                        <button className="flex items-center gap-2 px-4 py-2 bg-blue-500 text-white rounded-xl hover:bg-blue-600">
                          <Phone className="w-4 h-4" />
                          התקשר
                        </button>
                        <button className="flex items-center gap-2 px-4 py-2 bg-green-500 text-white rounded-xl hover:bg-green-600">
                          <MessageSquare className="w-4 h-4" />
                          WhatsApp
                        </button>
                        <button className="flex items-center gap-2 px-4 py-2 bg-purple-500 text-white rounded-xl hover:bg-purple-600">
                          <FileText className="w-4 h-4" />
                          הצעת מחיר
                        </button>
                        <button className="flex items-center gap-2 px-4 py-2 bg-orange-500 text-white rounded-xl hover:bg-orange-600">
                          <CalendarCheck className="w-4 h-4" />
                          הוסף משימה
                        </button>
                      </div>
                    </div>
                  </div>
                </div>
              ))}
            </div>
          )}

          {/* Contracts Tab */}
          {activeTab === 'contracts' && (
            <div className="space-y-4 p-6">
              {contracts.map((contract) => (
                <div key={contract.id} className="bg-gray-50 rounded-2xl p-6 border border-gray-100">
                  <div className="flex items-start justify-between mb-4">
                    <div>
                      <h3 className="text-lg font-bold text-gray-900">{contract.title}</h3>
                      <p className="text-gray-600">{contract.client_name}</p>
                    </div>
                    <div className="text-right">
                      <div className="text-2xl font-bold text-green-600">{formatCurrency(contract.value)}</div>
                      <span className={`inline-flex items-center px-3 py-1 rounded-full text-sm font-medium ${
                        contract.status === 'active' ? 'bg-green-100 text-green-800' : 'bg-yellow-100 text-yellow-800'
                      }`}>
                        {contract.status === 'active' ? 'פעיל' : 'ממתין לחתימה'}
                      </span>
                    </div>
                  </div>

                  <div className="grid grid-cols-1 md:grid-cols-4 gap-4 mb-4">
                    <div className="bg-white rounded-lg p-3">
                      <div className="text-xs text-gray-500 mb-1">תאריך התחלה</div>
                      <div className="font-medium">{new Date(contract.start_date).toLocaleDateString('he-IL')}</div>
                    </div>
                    <div className="bg-white rounded-lg p-3">
                      <div className="text-xs text-gray-500 mb-1">תאריך סיום</div>
                      <div className="font-medium">{new Date(contract.end_date).toLocaleDateString('he-IL')}</div>
                    </div>
                    <div className="bg-white rounded-lg p-3">
                      <div className="text-xs text-gray-500 mb-1">תנאי תשלום</div>
                      <div className="font-medium">{contract.payment_terms}</div>
                    </div>
                    <div className="bg-white rounded-lg p-3">
                      <div className="text-xs text-gray-500 mb-1">תאריך חתימה</div>
                      <div className="font-medium">
                        {contract.signed_date ? new Date(contract.signed_date).toLocaleDateString('he-IL') : 'לא נחתם'}
                      </div>
                    </div>
                  </div>

                  <div className="bg-white rounded-lg p-4 mb-4">
                    <div className="text-xs text-gray-500 mb-2">תיאור השירותים</div>
                    <div className="text-sm text-gray-700">{contract.services}</div>
                  </div>

                  <div className="mb-4">
                    <div className="text-sm font-medium text-gray-900 mb-3">אבני דרך</div>
                    <div className="space-y-2">
                      {contract.milestones.map((milestone, index) => (
                        <div key={index} className="flex items-center justify-between bg-white rounded-lg p-3">
                          <div className="flex items-center gap-3">
                            {milestone.status === 'completed' && <CheckCircle2 className="w-5 h-5 text-green-500" />}
                            {milestone.status === 'in_progress' && <RefreshCw className="w-5 h-5 text-blue-500" />}
                            {milestone.status === 'pending' && <Clock className="w-5 h-5 text-gray-400" />}
                            <span className="font-medium">{milestone.name}</span>
                          </div>
                          <div className="text-sm text-gray-500">
                            {new Date(milestone.due_date).toLocaleDateString('he-IL')}
                          </div>
                        </div>
                      ))}
                    </div>
                  </div>

                  <div className="flex items-center gap-3">
                    <button className="flex items-center gap-2 px-4 py-2 bg-blue-500 text-white rounded-xl hover:bg-blue-600">
                      <Eye className="w-4 h-4" />
                      צפייה מלאה
                    </button>
                    <button className="flex items-center gap-2 px-4 py-2 bg-green-500 text-white rounded-xl hover:bg-green-600">
                      <Download className="w-4 h-4" />
                      הורד PDF
                    </button>
                    <button className="flex items-center gap-2 px-4 py-2 bg-purple-500 text-white rounded-xl hover:bg-purple-600">
                      <Receipt className="w-4 h-4" />
                      צור חשבונית
                    </button>
                    <button className="flex items-center gap-2 px-4 py-2 bg-orange-500 text-white rounded-xl hover:bg-orange-600">
                      <Edit3 className="w-4 h-4" />
                      עריכה
                    </button>
                  </div>
                </div>
              ))}
            </div>
          )}

          {/* Invoices Tab */}
          {activeTab === 'invoices' && (
            <div className="space-y-4 p-6">
              {invoices.map((invoice) => (
                <div key={invoice.id} className="bg-gray-50 rounded-2xl p-6 border border-gray-100">
                  <div className="flex items-start justify-between mb-4">
                    <div>
                      <h3 className="text-lg font-bold text-gray-900">חשבונית {invoice.number}</h3>
                      <p className="text-gray-600">{invoice.client_name}</p>
                    </div>
                    <div className="text-right">
                      <div className="text-2xl font-bold text-blue-600">{formatCurrency(invoice.total)}</div>
                      <span className={`inline-flex items-center px-3 py-1 rounded-full text-sm font-medium ${
                        invoice.status === 'paid' ? 'bg-green-100 text-green-800' : 
                        invoice.status === 'overdue' ? 'bg-red-100 text-red-800' : 'bg-yellow-100 text-yellow-800'
                      }`}>
                        {invoice.status === 'paid' ? 'שולם' : 
                         invoice.status === 'overdue' ? 'באיחור' : 'ממתין לתשלום'}
                      </span>
                    </div>
                  </div>

                  <div className="grid grid-cols-1 md:grid-cols-4 gap-4 mb-4">
                    <div className="bg-white rounded-lg p-3">
                      <div className="text-xs text-gray-500 mb-1">תאריך הנפקה</div>
                      <div className="font-medium">{new Date(invoice.issue_date).toLocaleDateString('he-IL')}</div>
                    </div>
                    <div className="bg-white rounded-lg p-3">
                      <div className="text-xs text-gray-500 mb-1">תאריך פירעון</div>
                      <div className="font-medium">{new Date(invoice.due_date).toLocaleDateString('he-IL')}</div>
                    </div>
                    <div className="bg-white rounded-lg p-3">
                      <div className="text-xs text-gray-500 mb-1">סכום לפני מע"מ</div>
                      <div className="font-medium">{formatCurrency(invoice.amount)}</div>
                    </div>
                    <div className="bg-white rounded-lg p-3">
                      <div className="text-xs text-gray-500 mb-1">מע"מ</div>
                      <div className="font-medium">{formatCurrency(invoice.tax)}</div>
                    </div>
                  </div>

                  <div className="bg-white rounded-lg p-4 mb-4">
                    <div className="text-sm font-medium text-gray-900 mb-3">פריטים</div>
                    {invoice.items.map((item, index) => (
                      <div key={index} className="flex justify-between items-center py-2 border-b border-gray-100 last:border-b-0">
                        <div>{item.description}</div>
                        <div className="font-medium">{formatCurrency(item.price)}</div>
                      </div>
                    ))}
                  </div>

                  <div className="flex items-center gap-3">
                    <button className="flex items-center gap-2 px-4 py-2 bg-blue-500 text-white rounded-xl hover:bg-blue-600">
                      <Eye className="w-4 h-4" />
                      צפייה מלאה
                    </button>
                    <button className="flex items-center gap-2 px-4 py-2 bg-green-500 text-white rounded-xl hover:bg-green-600">
                      <Download className="w-4 h-4" />
                      הורד PDF
                    </button>
                    <button className="flex items-center gap-2 px-4 py-2 bg-purple-500 text-white rounded-xl hover:bg-purple-600">
                      <Send className="w-4 h-4" />
                      שלח ללקוח
                    </button>
                    {invoice.status === 'pending' && (
                      <button className="flex items-center gap-2 px-4 py-2 bg-orange-500 text-white rounded-xl hover:bg-orange-600">
                        <CheckCircle2 className="w-4 h-4" />
                        סמן כשולם
                      </button>
                    )}
                  </div>
                </div>
              ))}
            </div>
          )}

          {/* Tasks Tab */}
          {activeTab === 'tasks' && (
            <div className="space-y-4 p-6">
              {tasks.map((task) => (
                <div key={task.id} className="bg-gray-50 rounded-2xl p-6 border border-gray-100">
                  <div className="flex items-start justify-between mb-4">
                    <div className="flex-1">
                      <h3 className="text-lg font-bold text-gray-900 flex items-center gap-2">
                        {task.title}
                        <span className={`w-3 h-3 rounded-full ${getPriorityColor(task.priority)} bg-current`}></span>
                      </h3>
                      <p className="text-gray-600 text-sm mt-1">{task.description}</p>
                    </div>
                    <span className={`inline-flex items-center px-3 py-1 rounded-full text-sm font-medium border ${getTaskStatusColor(task.status)}`}>
                      {task.status === 'pending' ? 'ממתין' :
                       task.status === 'in_progress' ? 'בביצוע' :
                       task.status === 'completed' ? 'הושלם' : 'באיחור'}
                    </span>
                  </div>

                  <div className="grid grid-cols-1 md:grid-cols-4 gap-4 mb-4">
                    <div className="bg-white rounded-lg p-3">
                      <div className="text-xs text-gray-500 mb-1">תאריך ביצוע</div>
                      <div className="font-medium">{new Date(task.due_date).toLocaleDateString('he-IL')}</div>
                    </div>
                    <div className="bg-white rounded-lg p-3">
                      <div className="text-xs text-gray-500 mb-1">שעה</div>
                      <div className="font-medium">{task.due_time}</div>
                    </div>
                    <div className="bg-white rounded-lg p-3">
                      <div className="text-xs text-gray-500 mb-1">אחראי</div>
                      <div className="font-medium">{task.assigned_to}</div>
                    </div>
                    <div className="bg-white rounded-lg p-3">
                      <div className="text-xs text-gray-500 mb-1">עדיפות</div>
                      <div className={`font-medium ${getPriorityColor(task.priority)}`}>
                        {task.priority === 'high' ? 'גבוהה' :
                         task.priority === 'medium' ? 'בינונית' : 'נמוכה'}
                      </div>
                    </div>
                  </div>

                  <div className="flex items-center gap-3">
                    <button 
                      className={`flex items-center gap-2 px-4 py-2 rounded-xl ${
                        task.status === 'completed' 
                          ? 'bg-green-500 text-white' 
                          : 'bg-blue-500 text-white hover:bg-blue-600'
                      }`}
                    >
                      <CheckCircle2 className="w-4 h-4" />
                      {task.status === 'completed' ? 'הושלם' : 'סמן כהושלם'}
                    </button>
                    <button className="flex items-center gap-2 px-4 py-2 bg-orange-500 text-white rounded-xl hover:bg-orange-600">
                      <Edit3 className="w-4 h-4" />
                      עריכה
                    </button>
                    <button className="flex items-center gap-2 px-4 py-2 bg-purple-500 text-white rounded-xl hover:bg-purple-600">
                      <Calendar className="w-4 h-4" />
                      דחה תאריך
                    </button>
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      </div>
    </ModernLayout>
  );
}