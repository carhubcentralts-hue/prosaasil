import React, { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import axios from 'axios';
import { 
  Users, 
  Phone, 
  MessageSquare, 
  FileText, 
  CreditCard,
  Calendar,
  Search,
  Plus,
  Edit,
  Eye,
  PhoneCall,
  Send,
  ArrowLeft,
  CheckCircle,
  Clock,
  AlertCircle
} from 'lucide-react';

const AdvancedCRMPage = () => {
  const navigate = useNavigate();
  const [customers, setCustomers] = useState([]);
  const [selectedCustomer, setSelectedCustomer] = useState(null);
  const [customerDetails, setCustomerDetails] = useState(null);
  const [loading, setLoading] = useState(true);
  const [searchTerm, setSearchTerm] = useState('');
  const [activeTab, setActiveTab] = useState('overview');
  const [showNewCustomer, setShowNewCustomer] = useState(false);
  const [showNewContract, setShowNewContract] = useState(false);
  const [showNewInvoice, setShowNewInvoice] = useState(false);

  const businessId = getBusinessId();

  function getBusinessId() {
    try {
      const token = localStorage.getItem('auth_token');
      if (token && token !== 'null' && token !== 'undefined') {
        const parts = token.split('.');
        if (parts.length === 3) {
          const base64Url = parts[1];
          const base64 = base64Url.replace(/-/g, '+').replace(/_/g, '/');
          const decoded = JSON.parse(atob(base64));
          return decoded.business_id || 1;
        }
      }
    } catch (error) {
      console.error('Error decoding token:', error);
    }
    return 1;
  }

  useEffect(() => {
    loadCustomers();
  }, []);

  const loadCustomers = async () => {
    try {
      const token = localStorage.getItem('auth_token');
      const response = await axios.get('/api/crm/integration/whatsapp-calls', {
        headers: {
          'Authorization': `Bearer ${token}`,
          'Business-ID': businessId
        }
      });

      if (response.data.success) {
        setCustomers(response.data.integrated_communications || []);
      }
    } catch (error) {
      console.error('Error loading customers:', error);
    } finally {
      setLoading(false);
    }
  };

  const loadCustomerDetails = async (customerId) => {
    try {
      const token = localStorage.getItem('auth_token');
      const response = await axios.get(`/api/customers/${customerId}/advanced`, {
        headers: {
          'Authorization': `Bearer ${token}`,
          'Business-ID': businessId
        }
      });

      if (response.data.success) {
        setCustomerDetails(response.data.customer);
      }
    } catch (error) {
      console.error('Error loading customer details:', error);
    }
  };

  const handleCustomerClick = (customer) => {
    setSelectedCustomer(customer);
    loadCustomerDetails(customer.customer_id);
  };

  const createContract = async (contractData) => {
    try {
      const token = localStorage.getItem('auth_token');
      const response = await axios.post(
        `/api/customers/${selectedCustomer.customer_id}/contracts`,
        contractData,
        {
          headers: {
            'Authorization': `Bearer ${token}`,
            'Business-ID': businessId
          }
        }
      );

      if (response.data.success) {
        alert('החוזה נוצר בהצלחה!');
        loadCustomerDetails(selectedCustomer.customer_id);
        setShowNewContract(false);
      }
    } catch (error) {
      console.error('Error creating contract:', error);
      alert('שגיאה ביצירת החוזה');
    }
  };

  const createInvoice = async (invoiceData) => {
    try {
      const token = localStorage.getItem('auth_token');
      const response = await axios.post(
        `/api/customers/${selectedCustomer.customer_id}/invoices`,
        invoiceData,
        {
          headers: {
            'Authorization': `Bearer ${token}`,
            'Business-ID': businessId
          }
        }
      );

      if (response.data.success) {
        alert('החשבונית נוצרה בהצלחה!');
        loadCustomerDetails(selectedCustomer.customer_id);
        setShowNewInvoice(false);
      }
    } catch (error) {
      console.error('Error creating invoice:', error);
      alert('שגיאה ביצירת החשבונית');
    }
  };

  const filteredCustomers = customers.filter(customer =>
    customer.customer_name.toLowerCase().includes(searchTerm.toLowerCase()) ||
    customer.phone.includes(searchTerm)
  );

  const getStatusColor = (status) => {
    switch (status) {
      case 'active': return 'text-green-600 bg-green-100';
      case 'lead': return 'text-blue-600 bg-blue-100';
      case 'inactive': return 'text-gray-600 bg-gray-100';
      default: return 'text-gray-600 bg-gray-100';
    }
  };

  const getActivityIcon = (type) => {
    switch (type) {
      case 'call': return <PhoneCall className="w-4 h-4 text-purple-600" />;
      case 'whatsapp': return <MessageSquare className="w-4 h-4 text-green-600" />;
      case 'contract': return <FileText className="w-4 h-4 text-blue-600" />;
      case 'invoice': return <CreditCard className="w-4 h-4 text-orange-600" />;
      default: return <AlertCircle className="w-4 h-4 text-gray-600" />;
    }
  };

  return (
    <div className="min-h-screen bg-gray-50" dir="rtl">
      <div className="bg-white shadow-sm border-b border-gray-200">
        <div className="max-w-7xl mx-auto px-4 py-4">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-4">
              <button
                onClick={() => navigate('/business/dashboard')}
                className="flex items-center gap-2 text-gray-600 hover:text-gray-900"
              >
                <ArrowLeft className="w-5 h-5" />
                <span className="font-hebrew">חזרה לדשבורד</span>
              </button>
              <h1 className="text-2xl font-bold text-gray-900 font-hebrew">
                מערכת CRM מתקדמת
              </h1>
            </div>
            <div className="flex items-center gap-3">
              <button
                onClick={() => setShowNewCustomer(true)}
                className="flex items-center gap-2 bg-blue-600 text-white px-4 py-2 rounded-lg hover:bg-blue-700 font-hebrew"
              >
                <Plus className="w-4 h-4" />
                לקוח חדש
              </button>
            </div>
          </div>
        </div>
      </div>

      <div className="max-w-7xl mx-auto px-4 py-6">
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
          {/* רשימת לקוחות */}
          <div className="lg:col-span-1">
            <div className="bg-white rounded-xl shadow-sm border border-gray-200">
              <div className="p-4 border-b border-gray-200">
                <div className="relative">
                  <Search className="absolute right-3 top-3 w-4 h-4 text-gray-400" />
                  <input
                    type="text"
                    placeholder="חיפוש לקוחות..."
                    value={searchTerm}
                    onChange={(e) => setSearchTerm(e.target.value)}
                    className="w-full pr-10 pl-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500 font-hebrew"
                  />
                </div>
              </div>
              <div className="max-h-96 overflow-y-auto">
                {loading ? (
                  <div className="p-4 text-center text-gray-500 font-hebrew">טוען...</div>
                ) : (
                  filteredCustomers.map((customer) => (
                    <div
                      key={customer.customer_id}
                      onClick={() => handleCustomerClick(customer)}
                      className={`p-4 border-b border-gray-100 cursor-pointer hover:bg-gray-50 transition-colors ${
                        selectedCustomer?.customer_id === customer.customer_id ? 'bg-blue-50 border-r-4 border-r-blue-500' : ''
                      }`}
                    >
                      <div className="flex items-center justify-between">
                        <div>
                          <h3 className="font-medium text-gray-900 font-hebrew">
                            {customer.customer_name}
                          </h3>
                          <p className="text-sm text-gray-500 font-hebrew">
                            {customer.phone}
                          </p>
                        </div>
                        <div className="flex items-center gap-2">
                          {customer.stats.whatsapp_messages > 0 && (
                            <MessageSquare className="w-4 h-4 text-green-500" />
                          )}
                          {customer.stats.call_logs > 0 && (
                            <Phone className="w-4 h-4 text-purple-500" />
                          )}
                        </div>
                      </div>
                      <div className="mt-2 flex items-center gap-4 text-xs text-gray-500">
                        <span>הודעות: {customer.stats.whatsapp_messages}</span>
                        <span>שיחות: {customer.stats.call_logs}</span>
                      </div>
                    </div>
                  ))
                )}
              </div>
            </div>
          </div>

          {/* פרטי לקוח */}
          <div className="lg:col-span-2">
            {selectedCustomer && customerDetails ? (
              <div className="bg-white rounded-xl shadow-sm border border-gray-200">
                <div className="p-6 border-b border-gray-200">
                  <div className="flex items-center justify-between mb-4">
                    <h2 className="text-xl font-bold text-gray-900 font-hebrew">
                      {customerDetails.name}
                    </h2>
                    <span className={`px-3 py-1 rounded-full text-sm font-medium ${getStatusColor(customerDetails.status)}`}>
                      {customerDetails.status}
                    </span>
                  </div>
                  <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
                    <div>
                      <p className="text-sm text-gray-500 font-hebrew">טלפון</p>
                      <p className="font-medium font-hebrew">{customerDetails.phone}</p>
                    </div>
                    <div>
                      <p className="text-sm text-gray-500 font-hebrew">אימייל</p>
                      <p className="font-medium font-hebrew">{customerDetails.email || 'לא זמין'}</p>
                    </div>
                    <div>
                      <p className="text-sm text-gray-500 font-hebrew">מקור</p>
                      <p className="font-medium font-hebrew">{customerDetails.source}</p>
                    </div>
                    <div>
                      <p className="text-sm text-gray-500 font-hebrew">תאריך יצירה</p>
                      <p className="font-medium font-hebrew">
                        {new Date(customerDetails.created_at).toLocaleDateString('he-IL')}
                      </p>
                    </div>
                  </div>
                </div>

                {/* טאבים */}
                <div className="border-b border-gray-200">
                  <nav className="flex gap-6 px-6">
                    {[
                      { id: 'overview', label: 'סקירה כללית', icon: Eye },
                      { id: 'communications', label: 'תקשורת', icon: MessageSquare },
                      { id: 'contracts', label: 'חוזים', icon: FileText },
                      { id: 'invoices', label: 'חשבוניות', icon: CreditCard },
                      { id: 'tasks', label: 'משימות', icon: CheckCircle }
                    ].map((tab) => (
                      <button
                        key={tab.id}
                        onClick={() => setActiveTab(tab.id)}
                        className={`flex items-center gap-2 py-3 border-b-2 font-medium text-sm transition-colors font-hebrew ${
                          activeTab === tab.id
                            ? 'border-blue-500 text-blue-600'
                            : 'border-transparent text-gray-500 hover:text-gray-700'
                        }`}
                      >
                        <tab.icon className="w-4 h-4" />
                        {tab.label}
                      </button>
                    ))}
                  </nav>
                </div>

                {/* תוכן הטאבים */}
                <div className="p-6">
                  {activeTab === 'overview' && (
                    <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
                      <div className="bg-blue-50 p-4 rounded-lg">
                        <div className="flex items-center gap-2 mb-2">
                          <MessageSquare className="w-5 h-5 text-blue-600" />
                          <span className="font-medium text-blue-900 font-hebrew">הודעות WhatsApp</span>
                        </div>
                        <p className="text-2xl font-bold text-blue-600">{customerDetails.stats.total_messages}</p>
                        <p className="text-sm text-blue-700 font-hebrew">30 יום אחרונים: {customerDetails.stats.recent_messages_30d}</p>
                      </div>
                      <div className="bg-purple-50 p-4 rounded-lg">
                        <div className="flex items-center gap-2 mb-2">
                          <Phone className="w-5 h-5 text-purple-600" />
                          <span className="font-medium text-purple-900 font-hebrew">שיחות</span>
                        </div>
                        <p className="text-2xl font-bold text-purple-600">{customerDetails.stats.total_calls}</p>
                        <p className="text-sm text-purple-700 font-hebrew">30 יום אחרונים: {customerDetails.stats.recent_calls_30d}</p>
                      </div>
                      <div className="bg-green-50 p-4 rounded-lg">
                        <div className="flex items-center gap-2 mb-2">
                          <CheckCircle className="w-5 h-5 text-green-600" />
                          <span className="font-medium text-green-900 font-hebrew">משימות פתוחות</span>
                        </div>
                        <p className="text-2xl font-bold text-green-600">{customerDetails.stats.open_tasks}</p>
                      </div>
                      <div className="bg-orange-50 p-4 rounded-lg">
                        <div className="flex items-center gap-2 mb-2">
                          <Clock className="w-5 h-5 text-orange-600" />
                          <span className="font-medium text-orange-900 font-hebrew">קשר אחרון</span>
                        </div>
                        <p className="text-sm font-bold text-orange-600 font-hebrew">
                          {customerDetails.last_contact_date 
                            ? new Date(customerDetails.last_contact_date).toLocaleDateString('he-IL')
                            : 'אין מידע'
                          }
                        </p>
                      </div>
                    </div>
                  )}

                  {activeTab === 'communications' && (
                    <div className="space-y-4">
                      <div className="flex items-center justify-between">
                        <h3 className="text-lg font-medium text-gray-900 font-hebrew">היסטוריית תקשורת</h3>
                        <button className="flex items-center gap-2 bg-green-600 text-white px-3 py-1 rounded-lg hover:bg-green-700 text-sm font-hebrew">
                          <Send className="w-4 h-4" />
                          שלח הודעה
                        </button>
                      </div>
                      
                      {/* WhatsApp Messages */}
                      {customerDetails.recent_whatsapp.length > 0 && (
                        <div>
                          <h4 className="font-medium text-gray-700 mb-3 font-hebrew">הודעות WhatsApp אחרונות</h4>
                          <div className="space-y-2">
                            {customerDetails.recent_whatsapp.map((message) => (
                              <div key={message.id} className={`p-3 rounded-lg ${
                                message.direction === 'inbound' ? 'bg-gray-100 mr-8' : 'bg-blue-100 ml-8'
                              }`}>
                                <p className="text-sm font-hebrew">{message.message_body}</p>
                                <div className="flex items-center justify-between mt-2">
                                  <span className={`text-xs px-2 py-1 rounded ${
                                    message.direction === 'inbound' ? 'bg-gray-200 text-gray-700' : 'bg-blue-200 text-blue-700'
                                  } font-hebrew`}>
                                    {message.direction === 'inbound' ? 'נכנס' : 'יוצא'}
                                  </span>
                                  <span className="text-xs text-gray-500">
                                    {new Date(message.created_at).toLocaleString('he-IL')}
                                  </span>
                                </div>
                              </div>
                            ))}
                          </div>
                        </div>
                      )}
                      
                      {/* Call Logs */}
                      {customerDetails.recent_calls.length > 0 && (
                        <div>
                          <h4 className="font-medium text-gray-700 mb-3 font-hebrew">שיחות אחרונות</h4>
                          <div className="space-y-2">
                            {customerDetails.recent_calls.map((call) => (
                              <div key={call.id} className="p-3 bg-purple-50 rounded-lg">
                                <div className="flex items-center justify-between">
                                  <div>
                                    <p className="font-medium text-gray-900 font-hebrew">
                                      שיחה - {call.call_status}
                                    </p>
                                    {call.call_duration && (
                                      <p className="text-sm text-gray-600 font-hebrew">משך: {call.call_duration} שניות</p>
                                    )}
                                  </div>
                                  <span className="text-xs text-gray-500">
                                    {new Date(call.created_at).toLocaleString('he-IL')}
                                  </span>
                                </div>
                                {call.transcription && (
                                  <div className="mt-2 p-2 bg-white rounded border">
                                    <p className="text-sm text-gray-700 font-hebrew">תמלול: {call.transcription}</p>
                                  </div>
                                )}
                                {call.ai_response && (
                                  <div className="mt-2 p-2 bg-blue-50 rounded border">
                                    <p className="text-sm text-blue-700 font-hebrew">תגובת AI: {call.ai_response}</p>
                                  </div>
                                )}
                              </div>
                            ))}
                          </div>
                        </div>
                      )}
                    </div>
                  )}

                  {activeTab === 'contracts' && (
                    <div className="space-y-4">
                      <div className="flex items-center justify-between">
                        <h3 className="text-lg font-medium text-gray-900 font-hebrew">חוזים דיגיטליים</h3>
                        <button
                          onClick={() => setShowNewContract(true)}
                          className="flex items-center gap-2 bg-blue-600 text-white px-3 py-1 rounded-lg hover:bg-blue-700 text-sm font-hebrew"
                        >
                          <Plus className="w-4 h-4" />
                          חוזה חדש
                        </button>
                      </div>
                      <div className="text-center py-8 text-gray-500 font-hebrew">
                        טוען חוזים...
                      </div>
                    </div>
                  )}

                  {activeTab === 'invoices' && (
                    <div className="space-y-4">
                      <div className="flex items-center justify-between">
                        <h3 className="text-lg font-medium text-gray-900 font-hebrew">חשבוניות</h3>
                        <button
                          onClick={() => setShowNewInvoice(true)}
                          className="flex items-center gap-2 bg-orange-600 text-white px-3 py-1 rounded-lg hover:bg-orange-700 text-sm font-hebrew"
                        >
                          <Plus className="w-4 h-4" />
                          חשבונית חדשה
                        </button>
                      </div>
                      <div className="text-center py-8 text-gray-500 font-hebrew">
                        טוען חשבוניות...
                      </div>
                    </div>
                  )}

                  {activeTab === 'tasks' && (
                    <div className="space-y-4">
                      <div className="flex items-center justify-between">
                        <h3 className="text-lg font-medium text-gray-900 font-hebrew">משימות</h3>
                        <button className="flex items-center gap-2 bg-green-600 text-white px-3 py-1 rounded-lg hover:bg-green-700 text-sm font-hebrew">
                          <Plus className="w-4 h-4" />
                          משימה חדשה
                        </button>
                      </div>
                      {customerDetails.tasks.length > 0 ? (
                        <div className="space-y-2">
                          {customerDetails.tasks.map((task) => (
                            <div key={task.id} className="p-3 border rounded-lg">
                              <div className="flex items-center justify-between">
                                <h4 className="font-medium text-gray-900 font-hebrew">{task.title}</h4>
                                <span className={`px-2 py-1 rounded text-xs ${
                                  task.status === 'completed' ? 'bg-green-100 text-green-800' :
                                  task.status === 'in_progress' ? 'bg-blue-100 text-blue-800' :
                                  'bg-gray-100 text-gray-800'
                                } font-hebrew`}>
                                  {task.status}
                                </span>
                              </div>
                              {task.description && (
                                <p className="text-sm text-gray-600 mt-1 font-hebrew">{task.description}</p>
                              )}
                              <div className="flex items-center justify-between mt-2 text-xs text-gray-500">
                                <span className="font-hebrew">עדיפות: {task.priority}</span>
                                <span>
                                  {task.due_date && new Date(task.due_date).toLocaleDateString('he-IL')}
                                </span>
                              </div>
                            </div>
                          ))}
                        </div>
                      ) : (
                        <div className="text-center py-8 text-gray-500 font-hebrew">
                          אין משימות ללקוח זה
                        </div>
                      )}
                    </div>
                  )}
                </div>
              </div>
            ) : (
              <div className="bg-white rounded-xl shadow-sm border border-gray-200 h-96 flex items-center justify-center">
                <div className="text-center text-gray-500">
                  <Users className="w-12 h-12 mx-auto mb-4 text-gray-300" />
                  <p className="text-lg font-medium font-hebrew">בחר לקוח מהרשימה</p>
                  <p className="text-sm font-hebrew">כדי לראות פרטים מלאים</p>
                </div>
              </div>
            )}
          </div>
        </div>
      </div>

      {/* Modals for new contract and invoice would be here */}
    </div>
  );
};

export default AdvancedCRMPage;