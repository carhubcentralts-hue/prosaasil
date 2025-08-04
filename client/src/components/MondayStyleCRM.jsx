import React, { useState, useEffect } from 'react';
import axios from 'axios';
import { 
  Search, 
  Filter, 
  Plus, 
  Users, 
  Phone, 
  Mail, 
  Calendar,
  Activity,
  Trash2,
  Edit,
  Eye,
  Download,
  Upload,
  MoreHorizontal,
  UserPlus,
  PhoneCall,
  CheckCircle,
  Clock,
  AlertCircle,
  Star,
  ArrowUp,
  ArrowDown,
  Building2,
  MessageSquare
} from 'lucide-react';

const MondayStyleCRM = ({ businessId, isAdmin = false }) => {
  const [customers, setCustomers] = useState([]);
  const [phoneNumbers, setPhoneNumbers] = useState([]);
  const [callReadiness, setCallReadiness] = useState({});
  const [loading, setLoading] = useState(true);
  const [searchTerm, setSearchTerm] = useState('');
  const [filterStatus, setFilterStatus] = useState('all');
  const [selectedCustomers, setSelectedCustomers] = useState([]);
  const [viewMode, setViewMode] = useState('table');
  const [sortBy, setSortBy] = useState('created_at');
  const [sortOrder, setSortOrder] = useState('desc');

  useEffect(() => {
    fetchAllCRMData();
  }, [businessId, searchTerm, filterStatus, sortBy, sortOrder]);

  const fetchAllCRMData = async () => {
    try {
      setLoading(true);
      
      const userRole = localStorage.getItem('user_role');
      const currentBusinessId = businessId || localStorage.getItem('business_id');
      
      // Fetch customers data
      let customersEndpoint = '/api/crm/customers';
      if (userRole === 'admin' && isAdmin) {
        customersEndpoint = '/api/admin/crm/all-customers';
      } else if (currentBusinessId) {
        customersEndpoint = `${customersEndpoint}?business_id=${currentBusinessId}`;
      }
      
      // Fetch +972 phone numbers analysis
      const phoneNumbersEndpoint = '/api/crm/phone-analysis';
      
      const [customersRes, phoneRes] = await Promise.all([
        axios.get(customersEndpoint),
        axios.get(phoneNumbersEndpoint)
      ]);

      setCustomers(customersRes.data.customers || customersRes.data || []);
      setPhoneNumbers(phoneRes.data.phone_numbers || []);
      setCallReadiness(phoneRes.data.call_readiness || {});
      
    } catch (error) {
      console.error('Error fetching CRM data:', error);
      if (error.response?.status === 401) {
        localStorage.clear();
        window.location.href = '/login';
      }
    } finally {
      setLoading(false);
    }
  };

  const handleSort = (column) => {
    if (sortBy === column) {
      setSortOrder(sortOrder === 'asc' ? 'desc' : 'asc');
    } else {
      setSortBy(column);
      setSortOrder('asc');
    }
  };

  const handleCustomerAction = async (action, customerId) => {
    try {
      switch (action) {
        case 'call':
          await axios.post(`/api/crm/customer/${customerId}/call`);
          alert('שיחה התחילה');
          break;
        case 'edit':
          // Open edit modal
          break;
        case 'delete':
          if (window.confirm('האם למחוק את הלקוח?')) {
            await axios.delete(`/api/crm/customer/${customerId}`);
            fetchAllCRMData();
            alert('הלקוח נמחק');
          }
          break;
        default:
          break;
      }
    } catch (error) {
      console.error(`Error with ${action}:`, error);
      alert(`שגיאה בביצוע ${action}`);
    }
  };

  const getStatusColor = (status) => {
    const colors = {
      'new': 'bg-blue-500',
      'contacted': 'bg-yellow-500',
      'qualified': 'bg-green-500',
      'proposal': 'bg-purple-500',
      'closed_won': 'bg-emerald-600',
      'closed_lost': 'bg-red-500',
      'active': 'bg-green-500',
      'inactive': 'bg-gray-400'
    };
    return colors[status] || 'bg-gray-400';
  };

  const getPriorityColor = (priority) => {
    const colors = {
      'high': 'text-red-600',
      'medium': 'text-yellow-600',
      'low': 'text-green-600'
    };
    return colors[priority] || 'text-gray-600';
  };

  const formatPhoneNumber = (phone) => {
    if (phone?.startsWith('+972')) {
      return phone;
    }
    return phone || 'לא זמין';
  };

  if (loading) {
    return (
      <div className="min-h-screen bg-gradient-to-br from-blue-50 to-indigo-100 flex items-center justify-center" dir="rtl">
        <div className="text-center">
          <div className="animate-spin rounded-full h-16 w-16 border-4 border-blue-600 border-t-transparent mx-auto mb-4"></div>
          <p className="text-xl font-semibold text-gray-700 font-hebrew">טוען מערכת CRM מתקדמת...</p>
          <p className="text-gray-500 font-hebrew">מנתח מספרי +972 ובודק מוכנות לשיחות</p>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-gradient-to-br from-blue-50 to-indigo-100" dir="rtl">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
        
        {/* Monday.com Style Header */}
        <div className="bg-white rounded-2xl shadow-lg border border-gray-100 p-8 mb-8">
          <div className="flex justify-between items-center mb-6">
            <div>
              <h1 className="text-4xl font-bold bg-gradient-to-r from-blue-600 to-purple-600 bg-clip-text text-transparent font-hebrew">
                Agent Locator CRM
              </h1>
              <p className="text-gray-600 font-hebrew text-lg mt-2">מערכת ניהול לקוחות מתקדמת ברמה של Monday.com</p>
            </div>
            <div className="flex gap-3">
              <button 
                onClick={() => window.location.href = '/business/crm/new'}
                className="flex items-center gap-2 px-6 py-3 bg-gradient-to-r from-blue-600 to-blue-700 text-white rounded-xl hover:from-blue-700 hover:to-blue-800 shadow-lg transition-all font-hebrew"
              >
                <UserPlus className="w-5 h-5" />
                לקוח חדש
              </button>
              <button className="flex items-center gap-2 px-6 py-3 bg-gradient-to-r from-green-600 to-green-700 text-white rounded-xl hover:from-green-700 hover:to-green-800 shadow-lg transition-all font-hebrew">
                <Upload className="w-5 h-5" />
                ייבוא נתונים
              </button>
              <button className="flex items-center gap-2 px-6 py-3 bg-gradient-to-r from-purple-600 to-purple-700 text-white rounded-xl hover:from-purple-700 hover:to-purple-800 shadow-lg transition-all font-hebrew">
                <Download className="w-5 h-5" />
                ייצוא דוח
              </button>
            </div>
          </div>

          {/* Stats Cards - Monday.com Style */}
          <div className="grid grid-cols-1 md:grid-cols-4 gap-6">
            <div className="bg-gradient-to-br from-blue-500 to-blue-600 rounded-xl p-6 text-white">
              <div className="flex items-center justify-between">
                <div>
                  <p className="text-blue-100 font-hebrew">סך הכל לקוחות</p>
                  <p className="text-3xl font-bold">{customers.length}</p>
                </div>
                <Users className="w-12 h-12 text-blue-200" />
              </div>
            </div>
            <div className="bg-gradient-to-br from-green-500 to-green-600 rounded-xl p-6 text-white">
              <div className="flex items-center justify-between">
                <div>
                  <p className="text-green-100 font-hebrew">מספרי +972</p>
                  <p className="text-3xl font-bold">{phoneNumbers.length}</p>
                </div>
                <Phone className="w-12 h-12 text-green-200" />
              </div>
            </div>
            <div className="bg-gradient-to-br from-purple-500 to-purple-600 rounded-xl p-6 text-white">
              <div className="flex items-center justify-between">
                <div>
                  <p className="text-purple-100 font-hebrew">מוכן לשיחות</p>
                  <p className="text-3xl font-bold">{Object.values(callReadiness).filter(r => r === 'ready').length}</p>
                </div>
                <PhoneCall className="w-12 h-12 text-purple-200" />
              </div>
            </div>
            <div className="bg-gradient-to-br from-orange-500 to-orange-600 rounded-xl p-6 text-white">
              <div className="flex items-center justify-between">
                <div>
                  <p className="text-orange-100 font-hebrew">פעילים היום</p>
                  <p className="text-3xl font-bold">{customers.filter(c => c.status === 'active').length}</p>
                </div>
                <Activity className="w-12 h-12 text-orange-200" />
              </div>
            </div>
          </div>
        </div>

        {/* +972 Phone Numbers Analysis */}
        <div className="bg-white rounded-2xl shadow-lg border border-gray-100 p-6 mb-8">
          <h2 className="text-2xl font-bold text-gray-900 font-hebrew mb-4 flex items-center gap-2">
            <Phone className="w-6 h-6 text-blue-600" />
            ניתוח מספרי +972 במסד הנתונים
          </h2>
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
            {phoneNumbers.map((phone, index) => (
              <div key={index} className="border border-gray-200 rounded-lg p-4 hover:shadow-md transition-shadow">
                <div className="flex items-center justify-between mb-2">
                  <span className="font-mono text-lg text-gray-900">{phone.number}</span>
                  <div className={`w-3 h-3 rounded-full ${
                    callReadiness[phone.number] === 'ready' ? 'bg-green-500' :
                    callReadiness[phone.number] === 'pending' ? 'bg-yellow-500' : 'bg-red-500'
                  }`}></div>
                </div>
                <div className="text-sm text-gray-600 font-hebrew">
                  <p>עסק: {phone.business_name || 'לא מוקצה'}</p>
                  <p>מוכנות לשיחה: {
                    callReadiness[phone.number] === 'ready' ? 'מוכן' :
                    callReadiness[phone.number] === 'pending' ? 'בהמתנה' : 'לא מוכן'
                  }</p>
                  <p>עדכון אחרון: {phone.last_updated || 'לא זמין'}</p>
                </div>
                <button 
                  onClick={() => handleCustomerAction('call', phone.customer_id)}
                  className="mt-2 w-full bg-blue-50 hover:bg-blue-100 text-blue-600 py-2 rounded-lg transition-colors font-hebrew"
                >
                  <PhoneCall className="w-4 h-4 inline-block ml-2" />
                  התחל שיחה
                </button>
              </div>
            ))}
          </div>
        </div>

        {/* Advanced Filters - Monday.com Style */}
        <div className="bg-white rounded-2xl shadow-lg border border-gray-100 p-6 mb-8">
          <div className="flex flex-wrap items-center gap-4">
            <div className="relative flex-1 min-w-80">
              <Search className="absolute right-4 top-1/2 transform -translate-y-1/2 text-gray-400 w-5 h-5" />
              <input
                type="text"
                placeholder="חיפוש מתקדם בלקוחות, מספרי טלפון, אימיילים..."
                value={searchTerm}
                onChange={(e) => setSearchTerm(e.target.value)}
                className="w-full pl-12 pr-12 py-3 border border-gray-300 rounded-xl focus:ring-4 focus:ring-blue-100 focus:border-blue-500 transition-all font-hebrew"
              />
            </div>
            <select 
              value={filterStatus}
              onChange={(e) => setFilterStatus(e.target.value)}
              className="px-4 py-3 border border-gray-300 rounded-xl focus:ring-4 focus:ring-blue-100 focus:border-blue-500 font-hebrew"
            >
              <option value="all">כל הסטטוסים</option>
              <option value="new">חדש</option>
              <option value="contacted">נוצר קשר</option>
              <option value="qualified">מוכשר</option>
              <option value="active">פעיל</option>
              <option value="inactive">לא פעיל</option>
            </select>
            <div className="flex gap-2">
              <button 
                onClick={() => setViewMode('table')}
                className={`p-3 rounded-xl transition-all ${viewMode === 'table' ? 'bg-blue-600 text-white' : 'bg-gray-100 text-gray-600 hover:bg-gray-200'}`}
              >
                טבלה
              </button>
              <button 
                onClick={() => setViewMode('cards')}
                className={`p-3 rounded-xl transition-all ${viewMode === 'cards' ? 'bg-blue-600 text-white' : 'bg-gray-100 text-gray-600 hover:bg-gray-200'}`}
              >
                כרטיסים
              </button>
            </div>
          </div>
        </div>

        {/* Advanced Table - Monday.com Style */}
        <div className="bg-white rounded-2xl shadow-lg border border-gray-100 overflow-hidden">
          <div className="overflow-x-auto">
            <table className="w-full">
              <thead className="bg-gradient-to-r from-gray-50 to-gray-100">
                <tr>
                  <th className="px-6 py-4 text-right font-semibold text-gray-900 font-hebrew">
                    <input type="checkbox" className="rounded border-gray-300" />
                  </th>
                  <th 
                    className="px-6 py-4 text-right font-semibold text-gray-900 font-hebrew cursor-pointer hover:bg-gray-200 transition-colors"
                    onClick={() => handleSort('name')}
                  >
                    <div className="flex items-center gap-2">
                      שם הלקוח
                      {sortBy === 'name' && (sortOrder === 'asc' ? <ArrowUp className="w-4 h-4" /> : <ArrowDown className="w-4 h-4" />)}
                    </div>
                  </th>
                  <th className="px-6 py-4 text-right font-semibold text-gray-900 font-hebrew">מספר טלפון</th>
                  <th className="px-6 py-4 text-right font-semibold text-gray-900 font-hebrew">אימייל</th>
                  <th className="px-6 py-4 text-right font-semibold text-gray-900 font-hebrew">עסק</th>
                  <th className="px-6 py-4 text-right font-semibold text-gray-900 font-hebrew">סטטוס</th>
                  <th className="px-6 py-4 text-right font-semibold text-gray-900 font-hebrew">עדיפות</th>
                  <th className="px-6 py-4 text-right font-semibold text-gray-900 font-hebrew">מוכנות שיחה</th>
                  <th className="px-6 py-4 text-right font-semibold text-gray-900 font-hebrew">פעולות</th>
                </tr>
              </thead>
              <tbody>
                {customers.map((customer, index) => (
                  <tr key={customer.id || index} className="border-b border-gray-100 hover:bg-gray-50 transition-colors">
                    <td className="px-6 py-4">
                      <input type="checkbox" className="rounded border-gray-300" />
                    </td>
                    <td className="px-6 py-4">
                      <div className="flex items-center gap-3">
                        <div className="w-10 h-10 bg-gradient-to-br from-blue-500 to-purple-600 rounded-full flex items-center justify-center text-white font-bold">
                          {customer.name?.charAt(0) || 'L'}
                        </div>
                        <div>
                          <p className="font-semibold text-gray-900 font-hebrew">{customer.name || 'לקוח'}</p>
                          <p className="text-sm text-gray-500 font-hebrew">לקוח #{customer.id || index + 1}</p>
                        </div>
                      </div>
                    </td>
                    <td className="px-6 py-4">
                      <div className="flex items-center gap-2">
                        <Phone className="w-4 h-4 text-gray-400" />
                        <span className="font-mono text-gray-900">{formatPhoneNumber(customer.phone)}</span>
                        {customer.phone?.startsWith('+972') && (
                          <span className="bg-green-100 text-green-800 px-2 py-1 rounded-full text-xs font-hebrew">ישראל</span>
                        )}
                      </div>
                    </td>
                    <td className="px-6 py-4">
                      <div className="flex items-center gap-2">
                        <Mail className="w-4 h-4 text-gray-400" />
                        <span className="text-gray-900">{customer.email || 'לא זמין'}</span>
                      </div>
                    </td>
                    <td className="px-6 py-4">
                      <div className="flex items-center gap-2">
                        <Building2 className="w-4 h-4 text-gray-400" />
                        <span className="font-hebrew text-gray-900">{customer.business_name || 'לא משויך'}</span>
                      </div>
                    </td>
                    <td className="px-6 py-4">
                      <span className={`inline-flex items-center px-3 py-1 rounded-full text-xs font-medium text-white ${getStatusColor(customer.status)}`}>
                        {customer.status === 'new' ? 'חדש' :
                         customer.status === 'contacted' ? 'נוצר קשר' :
                         customer.status === 'qualified' ? 'מוכשר' :
                         customer.status === 'active' ? 'פעיל' : 'לא פעיל'}
                      </span>
                    </td>
                    <td className="px-6 py-4">
                      <Star className={`w-5 h-5 ${getPriorityColor(customer.priority)}`} />
                    </td>
                    <td className="px-6 py-4">
                      <div className="flex items-center gap-2">
                        <div className={`w-3 h-3 rounded-full ${
                          callReadiness[customer.phone] === 'ready' ? 'bg-green-500' :
                          callReadiness[customer.phone] === 'pending' ? 'bg-yellow-500' : 'bg-red-500'
                        }`}></div>
                        <span className="text-sm font-hebrew">
                          {callReadiness[customer.phone] === 'ready' ? 'מוכן' :
                           callReadiness[customer.phone] === 'pending' ? 'בהמתנה' : 'לא מוכן'}
                        </span>
                      </div>
                    </td>
                    <td className="px-6 py-4">
                      <div className="flex items-center gap-2">
                        <button 
                          onClick={() => handleCustomerAction('call', customer.id)}
                          className="p-2 text-green-600 hover:bg-green-50 rounded-lg transition-colors"
                          title="התחל שיחה"
                        >
                          <PhoneCall className="w-4 h-4" />
                        </button>
                        <button 
                          onClick={() => handleCustomerAction('edit', customer.id)}
                          className="p-2 text-blue-600 hover:bg-blue-50 rounded-lg transition-colors"
                          title="ערוך לקוח"
                        >
                          <Edit className="w-4 h-4" />
                        </button>
                        <button 
                          onClick={() => handleCustomerAction('delete', customer.id)}
                          className="p-2 text-red-600 hover:bg-red-50 rounded-lg transition-colors"
                          title="מחק לקוח"
                        >
                          <Trash2 className="w-4 h-4" />
                        </button>
                        <button className="p-2 text-gray-600 hover:bg-gray-50 rounded-lg transition-colors">
                          <MoreHorizontal className="w-4 h-4" />
                        </button>
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      </div>
    </div>
  );
};

export default MondayStyleCRM;