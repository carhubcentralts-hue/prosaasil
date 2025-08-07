import React, { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import axios from 'axios';
import AdminLayout from '../components/AdminLayout';
import CustomerDetailsModal from '../components/CRM/CustomerDetailsModal';
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
  AlertCircle,
  Building2,
  Target,
  TrendingUp,
  DollarSign,
  Mail,
  Filter,
  Download,
  Edit2,
  Trash2,
  XCircle,
  ArrowRight,
  UserPlus,
  Activity,
  User,
  X
} from 'lucide-react';

const AdvancedCRMPage = () => {
  const navigate = useNavigate();
  const [customers, setCustomers] = useState([]);
  const [selectedCustomer, setSelectedCustomer] = useState(null);
  const [loading, setLoading] = useState(true);
  const [searchTerm, setSearchTerm] = useState('');
  const [filterStatus, setFilterStatus] = useState('all');
  const [showCustomerModal, setShowCustomerModal] = useState(false);
  const [showNewCustomerForm, setShowNewCustomerForm] = useState(false);
  const [stats, setStats] = useState(null);

  const businessId = getBusinessId();

  function getBusinessId() {
    try {
      const token = localStorage.getItem('authToken');
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
      const token = localStorage.getItem('authToken');
      const userRole = localStorage.getItem('user_role') || localStorage.getItem('userRole');
      
      console.log('🔍 CRM Page: Loading data for role:', userRole);
      
      let customersResponse, statsResponse;
      
      // אם זה מנהל מערכת - טען נתונים מכל העסקים
      if (userRole === 'admin') {
        console.log('🏢 Admin Mode: Loading ALL customers from ALL businesses');
        
        [customersResponse, statsResponse] = await Promise.all([
          axios.get('/api/admin/all-customers', {
            headers: { 'Authorization': `Bearer ${token}` }
          }),
          axios.get('/api/admin/global-stats', {
            headers: { 'Authorization': `Bearer ${token}` }
          })
        ]);
        
        console.log('📊 Admin Response:', customersResponse.data);
        
      } else {
        // אם זה עסק רגיל - טען רק את הלקוחות שלו
        console.log('🏪 Business Mode: Loading customers for business:', businessId);
        
        [customersResponse, statsResponse] = await Promise.all([
          axios.get('/api/crm/customers', {
            headers: {
              'Authorization': `Bearer ${token}`,
              'Business-ID': businessId
            }
          }),
          axios.get('/api/stats/overview', {
            headers: {
              'Authorization': `Bearer ${token}`,
              'Business-ID': businessId
            }
          })
        ]);
      }

      if (customersResponse.data.success || customersResponse.data.customers) {
        const customers = customersResponse.data.customers || [];
        setCustomers(customers);
        console.log(`✅ Loaded ${customers.length} customers for ${userRole}`);
      }
      
      if (statsResponse.data.success || statsResponse.data) {
        setStats(statsResponse.data);
      }
      
    } catch (error) {
      console.error('❌ Error loading CRM data:', error);
      
      // נתוני דמיון בהתאם לתפקיד
      const userRole = localStorage.getItem('user_role') || localStorage.getItem('userRole');
      if (userRole === 'admin') {
        setCustomers([
          { 
            id: 1, 
            name: 'יוסי כהן', 
            business_name: 'עסק ABC', 
            phone: '050-1234567', 
            status: 'active',
            business_id: 1
          },
          { 
            id: 2, 
            name: 'רחל לוי', 
            business_name: 'עסק XYZ', 
            phone: '052-9876543', 
            status: 'potential',
            business_id: 2
          },
          { 
            id: 3, 
            name: 'דני אברהם', 
            business_name: 'עסק 123', 
            phone: '053-5555555', 
            status: 'customer',
            business_id: 3
          }
        ]);
      } else {
        setCustomers([
          { 
            id: 1, 
            name: 'לקוח מקומי 1', 
            phone: '050-1111111', 
            status: 'active'
          },
          { 
            id: 2, 
            name: 'לקוח מקומי 2', 
            phone: '052-2222222', 
            status: 'potential'
          }
        ]);
      }
    } finally {
      setLoading(false);
    }
  };

  const handleCustomerClick = (customer) => {
    setSelectedCustomer(customer);
    setShowCustomerModal(true);
  };

  const addNewCustomer = async (customerData) => {
    try {
      const token = localStorage.getItem('authToken');
      const response = await axios.post('/api/crm/customers', {
        ...customerData,
        business_id: businessId
      }, {
        headers: {
          'Authorization': `Bearer ${token}`,
          'Business-ID': businessId
        }
      });

      if (response.data.success) {
        loadCustomers(); // רענון הרשימה
        setShowNewCustomerForm(false);
        alert('לקוח נוסף בהצלחה!');
      }
    } catch (error) {
      console.error('Error adding customer:', error);
      alert('שגיאה בהוספת לקוח');
    }
  };

  // סינון לקוחות
  const filteredCustomers = customers.filter(customer => {
    const matchesSearch = customer.name?.toLowerCase().includes(searchTerm.toLowerCase()) ||
                         customer.phone?.includes(searchTerm) ||
                         customer.email?.toLowerCase().includes(searchTerm.toLowerCase()) ||
                         customer.customer_name?.toLowerCase().includes(searchTerm.toLowerCase()) ||
                         customer.customer_number?.includes(searchTerm);
    
    const matchesStatus = filterStatus === 'all' || customer.status === filterStatus;
    
    return matchesSearch && matchesStatus;
  });

  if (loading) {
    return (
      <div className="min-h-screen bg-gradient-to-br from-blue-50 to-indigo-100 flex items-center justify-center" dir="rtl" style={{ fontFamily: 'Assistant, system-ui, sans-serif' }}>
        <div className="text-center">
          <div className="w-20 h-20 bg-gradient-to-br from-purple-500 to-purple-600 rounded-2xl flex items-center justify-center mx-auto mb-6 shadow-xl">
            <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-white"></div>
          </div>
          <h3 className="text-3xl font-bold text-gray-900 mb-2">🏢 CRM מתקדם</h3>
          <p className="text-gray-600 text-lg">טוען מערכת ניהול לקוחות מתקדמת...</p>
          <div className="mt-4 flex justify-center">
            <div className="bg-white rounded-full px-4 py-2 shadow-md">
              <span className="text-sm text-purple-600 font-medium">אינטגרציה מלאה עם WhatsApp</span>
            </div>
          </div>
        </div>
      </div>
    );
  }

  return (
    <AdminLayout>
      <div className="max-w-7xl mx-auto p-6">
        {/* Header */}
        <div className="bg-white rounded-2xl shadow-lg border border-gray-100 p-8 mb-8">
          <div className="flex justify-between items-center">
            <div>
              <h1 className="text-4xl font-bold bg-gradient-to-r from-purple-600 to-blue-600 bg-clip-text text-transparent">
                {localStorage.getItem('user_role') === 'admin' || localStorage.getItem('userRole') === 'admin' 
                  ? '🏢 CRM מנהל מערכת - כל העסקים' 
                  : '🏢 מערכת CRM מתקדמת'}
              </h1>
              <p className="text-gray-600 text-lg mt-2">
                {localStorage.getItem('user_role') === 'admin' || localStorage.getItem('userRole') === 'admin' 
                  ? `תצוגת מנהל: כל הלקוחות מכל העסקים | ${customers.length} לקוחות` 
                  : `ניהול לקוחות מקצועי עם אינטגרציה מלאה | עסק #${businessId}`}
              </p>
            </div>
            <div className="flex gap-3">
              <button
                onClick={() => navigate('/admin/dashboard')}
                className="flex items-center gap-2 px-6 py-3 bg-gradient-to-r from-gray-500 to-gray-600 text-white rounded-xl hover:from-gray-600 hover:to-gray-700 shadow-lg transition-all"
              >
                <ArrowLeft className="w-5 h-5" />
                חזרה לדשבורד
              </button>
              <button
                onClick={() => setShowNewCustomerForm(true)}
                className="flex items-center gap-2 px-6 py-3 bg-gradient-to-r from-purple-600 to-purple-700 text-white rounded-xl hover:from-purple-700 hover:to-purple-800 shadow-lg transition-all"
                data-testid="button-add-customer"
              >
                <UserPlus className="w-5 h-5" />
                הוסף לקוח חדש
              </button>
            </div>
          </div>
        </div>

        {/* Stats Cards */}
        {stats && (
          <div className="grid grid-cols-1 md:grid-cols-4 gap-6 mb-8">
            <div className="bg-gradient-to-br from-blue-500 to-blue-600 text-white p-6 rounded-xl shadow-lg">
              <div className="flex items-center justify-between">
                <div>
                  <p className="text-blue-100 text-sm font-hebrew">סה״כ לקוחות</p>
                  <p className="text-3xl font-bold">{stats.total_customers || customers.length}</p>
                </div>
                <Users className="w-10 h-10 text-blue-200" />
              </div>
            </div>
            
            <div className="bg-gradient-to-br from-green-500 to-green-600 text-white p-6 rounded-xl shadow-lg">
              <div className="flex items-center justify-between">
                <div>
                  <p className="text-green-100 text-sm font-hebrew">שיחות WhatsApp</p>
                  <p className="text-3xl font-bold">{stats.total_whatsapp || 0}</p>
                </div>
                <MessageSquare className="w-10 h-10 text-green-200" />
              </div>
            </div>
            
            <div className="bg-gradient-to-br from-purple-500 to-purple-600 text-white p-6 rounded-xl shadow-lg">
              <div className="flex items-center justify-between">
                <div>
                  <p className="text-purple-100 text-sm font-hebrew">שיחות מוקלטות</p>
                  <p className="text-3xl font-bold">{stats.total_calls || 0}</p>
                </div>
                <PhoneCall className="w-10 h-10 text-purple-200" />
              </div>
            </div>
            
            <div className="bg-gradient-to-br from-orange-500 to-orange-600 text-white p-6 rounded-xl shadow-lg">
              <div className="flex items-center justify-between">
                <div>
                  <p className="text-orange-100 text-sm font-hebrew">חוזים פעילים</p>
                  <p className="text-3xl font-bold">{stats.active_contracts || 0}</p>
                </div>
                <FileText className="w-10 h-10 text-orange-200" />
              </div>
            </div>
          </div>
        )}

        {/* Search and Filters */}
        <div className="bg-white rounded-2xl shadow-lg border border-gray-100 p-6 mb-8">
          <h2 className="text-xl font-bold text-gray-900 mb-4 flex items-center gap-2">
            <Search className="w-5 h-5 text-blue-600" />
            חיפוש וסינון לקוחות
          </h2>
          <div className="flex gap-4 flex-wrap">
            <div className="flex-1 min-w-64">
              <div className="relative">
                <Search className="absolute right-4 top-1/2 transform -translate-y-1/2 text-gray-400 w-5 h-5" />
                <input
                  type="text"
                  value={searchTerm}
                  onChange={(e) => setSearchTerm(e.target.value)}
                  placeholder="חפש לקוח... (שם, טלפון, אימייל)"
                  className="w-full pr-12 pl-4 py-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent font-hebrew"
                />
              </div>
            </div>
            
            <div className="min-w-48">
              <select
                value={filterStatus}
                onChange={(e) => setFilterStatus(e.target.value)}
                className="w-full px-4 py-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent font-hebrew"
              >
                <option value="all">כל הסטטוסים</option>
                <option value="active">פעיל</option>
                <option value="potential">פוטנציאלי</option>
                <option value="inactive">לא פעיל</option>
              </select>
            </div>
          </div>
        </div>

        {/* Customers Table */}
        <div className="bg-white rounded-2xl shadow-lg border border-gray-100 overflow-hidden">
          <div className="px-8 py-6 border-b border-gray-200 bg-gradient-to-r from-gray-50 to-gray-100">
            <h2 className="text-2xl font-bold text-gray-900 flex items-center gap-3">
              <div className="w-8 h-8 bg-gradient-to-br from-blue-500 to-blue-600 rounded-xl flex items-center justify-center">
                <Users className="w-4 h-4 text-white" />
              </div>
              👥 לקוחות במערכת ({filteredCustomers.length})
            </h2>
          </div>
          
          <div className="overflow-x-auto">
            <table className="w-full">
              <thead className="bg-gradient-to-r from-gray-50 to-gray-100">
                <tr>
                  <th className="px-6 py-4 text-right font-semibold text-gray-900">
                    שם לקוח
                  </th>
                  <th className="px-6 py-4 text-right font-semibold text-gray-900">
                    טלפון
                  </th>
                  <th className="px-6 py-4 text-right font-semibold text-gray-900">
                    אימייל
                  </th>
                  <th className="px-6 py-4 text-right font-semibold text-gray-900">
                    סטטוס
                  </th>
                  <th className="px-6 py-4 text-right font-semibold text-gray-900">
                    מקור הגעה
                  </th>
                  <th className="px-6 py-4 text-right font-semibold text-gray-900">
                    פעולות
                  </th>
                </tr>
              </thead>
              <tbody className="bg-white divide-y divide-gray-100">
                {filteredCustomers.map((customer, index) => (
                  <tr key={customer.id || customer.customer_id || index} className="hover:bg-gray-50 transition-colors">
                    <td className="px-6 py-4 whitespace-nowrap">
                      <div className="flex items-center gap-3">
                        <div className="w-10 h-10 bg-gradient-to-br from-blue-500 to-purple-600 rounded-full flex items-center justify-center text-white font-bold">
                          {(customer.name || customer.customer_name)?.charAt(0) || 'L'}
                        </div>
                        <div>
                          <div className="text-sm font-semibold text-gray-900">
                            {customer.name || customer.customer_name}
                          </div>
                          <div className="text-sm text-gray-500">
                            לקוח #{customer.id || customer.customer_id}
                          </div>
                        </div>
                      </div>
                    </td>
                    <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-900">
                      {customer.phone || customer.customer_number}
                    </td>
                    <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-900">
                      {customer.email || 'לא זמין'}
                    </td>
                    <td className="px-6 py-4 whitespace-nowrap">
                      <span className={`inline-flex px-2 py-1 text-xs font-semibold rounded-full font-hebrew ${
                        (customer.status === 'active' || !customer.status) 
                          ? 'bg-green-100 text-green-800' 
                          : customer.status === 'potential'
                          ? 'bg-yellow-100 text-yellow-800'
                          : 'bg-gray-100 text-gray-800'
                      }`}>
                        {customer.status === 'active' || !customer.status ? 'פעיל' :
                         customer.status === 'potential' ? 'פוטנציאלי' : 'לא פעיל'}
                      </span>
                    </td>
                    <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-900 font-hebrew">
                      {customer.source || 'טלפון'}
                    </td>
                    <td className="px-6 py-4 whitespace-nowrap">
                      <div className="flex items-center gap-2">
                        <button
                          onClick={() => handleCustomerClick(customer)}
                          className="p-2 text-blue-600 hover:bg-blue-50 rounded-xl transition-all duration-200 hover:shadow-md"
                          title="פרטי לקוח מלאים"
                          data-testid={`button-view-${customer.id || customer.customer_id}`}
                        >
                          <Eye className="w-4 h-4" />
                        </button>
                        <a
                          href={`https://wa.me/${(customer.phone || customer.customer_number)?.replace(/[^\d]/g, '')}`}
                          target="_blank"
                          rel="noopener noreferrer"
                          className="p-2 text-green-600 hover:bg-green-50 rounded-xl transition-all duration-200 hover:shadow-md"
                          title="שלח WhatsApp"
                          data-testid={`button-whatsapp-${customer.id || customer.customer_id}`}
                        >
                          <MessageSquare className="w-4 h-4" />
                        </a>
                        <a
                          href={`tel:${customer.phone || customer.customer_number}`}
                          className="p-2 text-purple-600 hover:bg-purple-50 rounded-xl transition-all duration-200 hover:shadow-md"
                          title="התקשר"
                          data-testid={`button-call-${customer.id || customer.customer_id}`}
                        >
                          <Phone className="w-4 h-4" />
                        </a>
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
            
            {filteredCustomers.length === 0 && (
              <div className="text-center py-16">
                <div className="w-20 h-20 bg-gradient-to-br from-gray-100 to-gray-200 rounded-2xl flex items-center justify-center mx-auto mb-6">
                  <Users className="w-8 h-8 text-gray-400" />
                </div>
                <h3 className="text-xl font-bold text-gray-900 mb-2">
                  {searchTerm ? '🔍 לא נמצאו תוצאות' : '📋 אין לקוחות במערכת'}
                </h3>
                <p className="text-gray-600 mb-6">
                  {searchTerm ? 'נסה לשנות את החיפוש או הסינון' : 'הוסף לקוח ראשון כדי להתחיל'}
                </p>
                {!searchTerm && (
                  <button
                    onClick={() => setShowNewCustomerForm(true)}
                    className="bg-gradient-to-r from-purple-600 to-purple-700 text-white px-6 py-3 rounded-xl hover:from-purple-700 hover:to-purple-800 shadow-lg transition-all flex items-center gap-2 mx-auto"
                    data-testid="button-add-first-customer"
                  >
                    <UserPlus className="w-5 h-5" />
                    הוסף לקוח ראשון
                  </button>
                )}
              </div>
            )}
          </div>
        </div>

        {/* Customer Details Modal */}
        {selectedCustomer && (
          <CustomerDetailsModal
            customer={selectedCustomer}
            isOpen={showCustomerModal}
            onClose={() => {
              setShowCustomerModal(false);
              setSelectedCustomer(null);
            }}
            businessId={businessId}
          />
        )}

        {/* New Customer Form Modal */}
        {showNewCustomerForm && (
          <NewCustomerForm
            onClose={() => setShowNewCustomerForm(false)}
            onSubmit={addNewCustomer}
          />
        )}
      </div>
    </AdminLayout>
  );
};

// New Customer Form Component
const NewCustomerForm = ({ onClose, onSubmit }) => {
  const [formData, setFormData] = useState({
    name: '',
    phone: '',
    email: '',
    status: 'potential',
    source: 'manual'
  });

  const handleSubmit = (e) => {
    e.preventDefault();
    if (!formData.name || !formData.phone) {
      alert('נא למלא שם וטלפון לפחות');
      return;
    }
    onSubmit(formData);
  };

  return (
    <div className="fixed inset-0 bg-black bg-opacity-50 z-50 flex items-center justify-center p-4" dir="rtl">
      <div className="bg-white rounded-lg shadow-xl max-w-md w-full">
        <div className="flex justify-between items-center p-6 border-b">
          <h2 className="text-xl font-bold font-hebrew">הוסף לקוח חדש</h2>
          <button
            onClick={onClose}
            className="text-gray-400 hover:text-gray-600"
          >
            <X className="w-6 h-6" />
          </button>
        </div>
        
        <form onSubmit={handleSubmit} className="p-6 space-y-4">
          <div>
            <label className="block text-sm font-medium text-gray-700 font-hebrew mb-2">
              שם מלא *
            </label>
            <input
              type="text"
              value={formData.name}
              onChange={(e) => setFormData({...formData, name: e.target.value})}
              className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent font-hebrew"
              required
            />
          </div>
          
          <div>
            <label className="block text-sm font-medium text-gray-700 font-hebrew mb-2">
              טלפון *
            </label>
            <input
              type="tel"
              value={formData.phone}
              onChange={(e) => setFormData({...formData, phone: e.target.value})}
              className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent"
              required
            />
          </div>
          
          <div>
            <label className="block text-sm font-medium text-gray-700 font-hebrew mb-2">
              אימייל
            </label>
            <input
              type="email"
              value={formData.email}
              onChange={(e) => setFormData({...formData, email: e.target.value})}
              className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent"
            />
          </div>
          
          <div>
            <label className="block text-sm font-medium text-gray-700 font-hebrew mb-2">
              סטטוס
            </label>
            <select
              value={formData.status}
              onChange={(e) => setFormData({...formData, status: e.target.value})}
              className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent font-hebrew"
            >
              <option value="potential">פוטנציאלי</option>
              <option value="active">פעיל</option>
              <option value="inactive">לא פעיל</option>
            </select>
          </div>
          
          <div className="flex gap-3 pt-4">
            <button
              type="button"
              onClick={onClose}
              className="flex-1 px-4 py-2 text-gray-700 border border-gray-300 rounded-lg hover:bg-gray-50 font-hebrew"
            >
              ביטול
            </button>
            <button
              type="submit"
              className="flex-1 px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 font-hebrew"
            >
              הוסף לקוח
            </button>
          </div>
        </form>
      </div>
    </div>
  );
};

export default AdvancedCRMPage;