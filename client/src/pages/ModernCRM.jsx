import React, { useState, useEffect } from 'react';
import ModernLayout from '../components/ModernLayout';
import { 
  Users, Plus, Search, Filter, Star, Phone, MessageSquare,
  Eye, Edit3, Trash2, FileText, Receipt, PenTool, Calendar,
  ArrowUpRight, TrendingUp, Activity, UserCheck, Building2,
  Mail, MapPin, Clock, Tag, ChevronDown, MoreVertical
} from 'lucide-react';

export default function ModernCRM() {
  const [userRole, setUserRole] = useState('business');
  const [customers, setCustomers] = useState([]);
  const [loading, setLoading] = useState(true);
  const [searchTerm, setSearchTerm] = useState('');
  const [filterStatus, setFilterStatus] = useState('all');
  const [selectedCustomer, setSelectedCustomer] = useState(null);
  const [showCustomerModal, setShowCustomerModal] = useState(false);

  useEffect(() => {
    const role = localStorage.getItem('user_role') || localStorage.getItem('userRole');
    setUserRole(role || 'business');
    loadCustomers(role);
  }, []);

  const loadCustomers = async (role) => {
    try {
      const endpoint = role === 'admin' ? '/api/admin/all-customers' : '/api/customers';
      const token = localStorage.getItem('authToken');
      
      const response = await fetch(endpoint, {
        headers: {
          'Authorization': `Bearer ${token}`,
          'Content-Type': 'application/json'
        }
      });
      
      const data = await response.json();
      console.log('CRM customers data:', data);
      
      if (data.success && data.customers) {
        setCustomers(data.customers);
      } else {
        // Demo data based on user role
        const demoCustomers = role === 'admin' ? [
          {
            id: 1,
            name: 'יוסי כהן - מנהל',
            phone: '050-1234567',
            email: 'yossi@business-abc.com',
            status: 'active',
            business_name: 'עסק ABC - שירותי ייעוץ',
            business_type: 'שירותי ייעוץ',
            last_contact: '2025-08-07',
            value: '₪15,000',
            tags: ['VIP', 'ייעוץ'],
            source: 'טלפון'
          },
          {
            id: 2,
            name: 'רחל לוי - מנהל',
            phone: '052-9876543',
            email: 'rachel@business-xyz.com',
            status: 'potential',
            business_name: 'עסק XYZ - שירותי מכירות',
            business_type: 'מכירות',
            last_contact: '2025-08-06',
            value: '₪8,500',
            tags: ['חם', 'מכירות'],
            source: 'WhatsApp'
          }
        ] : [
          {
            id: 1,
            name: 'דני ישראלי',
            phone: '050-1111111',
            email: 'danny@gmail.com',
            status: 'active',
            last_contact: '2025-08-07',
            value: '₪25,000',
            tags: ['VIP', 'חוזה שנתי'],
            source: 'המלצה'
          },
          {
            id: 2,
            name: 'מיכל כהן',
            phone: '052-2222222',
            email: 'michal@company.co.il',
            status: 'potential',
            last_contact: '2025-08-05',
            value: '₪12,000',
            tags: ['חם', 'עוקב'],
            source: 'טלפון'
          }
        ];
        setCustomers(demoCustomers);
      }
      setLoading(false);
    } catch (error) {
      console.error('Error loading customers:', error);
      setLoading(false);
    }
  };

  const filteredCustomers = customers.filter(customer => {
    const matchesSearch = customer.name?.toLowerCase().includes(searchTerm.toLowerCase()) ||
                         customer.phone?.includes(searchTerm) ||
                         customer.email?.toLowerCase().includes(searchTerm.toLowerCase());
    const matchesFilter = filterStatus === 'all' || customer.status === filterStatus;
    return matchesSearch && matchesFilter;
  });

  const handleCustomerClick = (customer) => {
    setSelectedCustomer(customer);
    setShowCustomerModal(true);
  };

  const getStatusColor = (status) => {
    switch (status) {
      case 'active': return 'bg-green-100 text-green-800 border-green-200';
      case 'potential': return 'bg-yellow-100 text-yellow-800 border-yellow-200';
      case 'inactive': return 'bg-gray-100 text-gray-800 border-gray-200';
      default: return 'bg-blue-100 text-blue-800 border-blue-200';
    }
  };

  const getStatusText = (status) => {
    switch (status) {
      case 'active': return 'פעיל';
      case 'potential': return 'פוטנציאל';
      case 'inactive': return 'לא פעיל';
      default: return 'לקוח';
    }
  };

  if (loading) {
    return (
      <ModernLayout userRole={userRole}>
        <div className="flex items-center justify-center min-h-[400px]">
          <div className="text-center">
            <div className="animate-spin rounded-full h-32 w-32 border-b-2 border-blue-600 mx-auto mb-4"></div>
            <p className="text-gray-600">טוען נתוני לקוחות...</p>
          </div>
        </div>
      </ModernLayout>
    );
  }

  return (
    <ModernLayout userRole={userRole}>
      <div className="space-y-8">
        {/* Header Section */}
        <div className="bg-gradient-to-r from-purple-600 to-blue-700 rounded-3xl p-8 text-white">
          <div className="flex items-center justify-between">
            <div>
              <h1 className="text-4xl font-bold mb-2 flex items-center gap-3">
                <Users className="w-10 h-10" />
                {userRole === 'admin' ? '🏢 CRM כללי' : '💼 ניהול לקוחות'}
              </h1>
              <p className="text-purple-100 text-lg">
                {userRole === 'admin' 
                  ? 'ניהול לקוחות מכל העסקים במערכת' 
                  : 'ניהול מתקדם של לקוחות העסק'
                }
              </p>
            </div>
            <div className="text-left">
              <div className="text-3xl font-bold">{filteredCustomers.length}</div>
              <div className="text-purple-100">לקוחות סה"כ</div>
            </div>
          </div>
        </div>

        {/* Stats Cards */}
        <div className="grid grid-cols-1 md:grid-cols-4 gap-6">
          <div className="bg-white rounded-2xl p-6 shadow-lg border border-gray-100">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-gray-600 text-sm">לקוחות פעילים</p>
                <p className="text-3xl font-bold text-green-600">
                  {customers.filter(c => c.status === 'active').length}
                </p>
                <p className="text-green-500 text-sm flex items-center gap-1">
                  <ArrowUpRight className="w-4 h-4" />
                  +12% החודש
                </p>
              </div>
              <UserCheck className="w-12 h-12 text-green-500" />
            </div>
          </div>

          <div className="bg-white rounded-2xl p-6 shadow-lg border border-gray-100">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-gray-600 text-sm">פוטנציאליים</p>
                <p className="text-3xl font-bold text-yellow-600">
                  {customers.filter(c => c.status === 'potential').length}
                </p>
                <p className="text-yellow-500 text-sm flex items-center gap-1">
                  <TrendingUp className="w-4 h-4" />
                  +5 השבוע
                </p>
              </div>
              <Star className="w-12 h-12 text-yellow-500" />
            </div>
          </div>

          <div className="bg-white rounded-2xl p-6 shadow-lg border border-gray-100">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-gray-600 text-sm">שיחות היום</p>
                <p className="text-3xl font-bold text-blue-600">18</p>
                <p className="text-blue-500 text-sm flex items-center gap-1">
                  <Phone className="w-4 h-4" />
                  זמן אמת
                </p>
              </div>
              <Activity className="w-12 h-12 text-blue-500" />
            </div>
          </div>

          <div className="bg-white rounded-2xl p-6 shadow-lg border border-gray-100">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-gray-600 text-sm">ערך כולל</p>
                <p className="text-3xl font-bold text-purple-600">₪156K</p>
                <p className="text-purple-500 text-sm flex items-center gap-1">
                  <TrendingUp className="w-4 h-4" />
                  +18% החודש
                </p>
              </div>
              <Receipt className="w-12 h-12 text-purple-500" />
            </div>
          </div>
        </div>

        {/* Search and Filters */}
        <div className="bg-white rounded-2xl p-6 shadow-lg border border-gray-100">
          <div className="flex flex-col md:flex-row gap-4 items-center justify-between">
            <div className="flex gap-4 items-center flex-1">
              <div className="relative flex-1 max-w-md">
                <Search className="w-5 h-5 text-gray-400 absolute right-3 top-1/2 transform -translate-y-1/2" />
                <input
                  type="text"
                  placeholder="חיפוש לקוח, טלפון או אימייל..."
                  value={searchTerm}
                  onChange={(e) => setSearchTerm(e.target.value)}
                  className="w-full bg-gray-50 border border-gray-200 rounded-xl pr-10 pl-4 py-3 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent"
                />
              </div>
              
              <select
                value={filterStatus}
                onChange={(e) => setFilterStatus(e.target.value)}
                className="bg-gray-50 border border-gray-200 rounded-xl px-4 py-3 focus:outline-none focus:ring-2 focus:ring-blue-500"
              >
                <option value="all">כל הלקוחות</option>
                <option value="active">פעילים</option>
                <option value="potential">פוטנציאליים</option>
                <option value="inactive">לא פעילים</option>
              </select>
            </div>
            
            <button className="bg-gradient-to-r from-blue-500 to-purple-600 text-white px-6 py-3 rounded-xl hover:shadow-lg transition-all duration-200 flex items-center gap-2">
              <Plus className="w-5 h-5" />
              לקוח חדש
            </button>
          </div>
        </div>

        {/* Customers Table */}
        <div className="bg-white rounded-2xl shadow-lg border border-gray-100 overflow-hidden">
          <div className="px-8 py-6 border-b border-gray-200 bg-gradient-to-r from-gray-50 to-gray-100">
            <h2 className="text-2xl font-bold text-gray-900 flex items-center gap-3">
              <div className="w-8 h-8 bg-gradient-to-br from-blue-500 to-blue-600 rounded-xl flex items-center justify-center">
                <Users className="w-4 h-4 text-white" />
              </div>
              רשימת לקוחות ({filteredCustomers.length})
            </h2>
          </div>
          
          <div className="overflow-x-auto">
            <table className="w-full">
              <thead className="bg-gradient-to-r from-gray-50 to-gray-100">
                <tr>
                  <th className="px-6 py-4 text-right font-semibold text-gray-900">לקוח</th>
                  <th className="px-6 py-4 text-right font-semibold text-gray-900">פרטי קשר</th>
                  <th className="px-6 py-4 text-right font-semibold text-gray-900">סטטוס</th>
                  <th className="px-6 py-4 text-right font-semibold text-gray-900">ערך</th>
                  <th className="px-6 py-4 text-right font-semibold text-gray-900">תגיות</th>
                  <th className="px-6 py-4 text-right font-semibold text-gray-900">פעולות</th>
                </tr>
              </thead>
              <tbody className="bg-white divide-y divide-gray-100">
                {filteredCustomers.map((customer, index) => (
                  <tr key={customer.id || index} className="hover:bg-blue-50 transition-all duration-200 group">
                    <td className="px-6 py-4">
                      <div className="flex items-center gap-4">
                        <div className="w-12 h-12 bg-gradient-to-br from-blue-500 to-purple-600 rounded-full flex items-center justify-center text-white font-bold text-lg">
                          {customer.name?.charAt(0) || 'L'}
                        </div>
                        <div>
                          <div className="text-sm font-semibold text-gray-900">
                            {customer.name}
                          </div>
                          <div className="text-sm text-gray-500">
                            {customer.business_name ? (
                              <>
                                <Building2 className="w-4 h-4 inline ml-1" />
                                {customer.business_name}
                              </>
                            ) : (
                              `לקוח #${customer.id}`
                            )}
                          </div>
                        </div>
                      </div>
                    </td>
                    
                    <td className="px-6 py-4">
                      <div className="space-y-1">
                        <div className="text-sm text-gray-900 flex items-center gap-2">
                          <Phone className="w-4 h-4 text-blue-500" />
                          {customer.phone}
                        </div>
                        <div className="text-sm text-gray-500 flex items-center gap-2">
                          <Mail className="w-4 h-4 text-gray-400" />
                          {customer.email || 'לא זמין'}
                        </div>
                      </div>
                    </td>
                    
                    <td className="px-6 py-4">
                      <span className={`inline-flex items-center px-3 py-1 rounded-full text-sm font-medium border ${getStatusColor(customer.status)}`}>
                        {getStatusText(customer.status)}
                      </span>
                    </td>
                    
                    <td className="px-6 py-4">
                      <div className="text-sm font-semibold text-gray-900">
                        {customer.value || '₪0'}
                      </div>
                      <div className="text-xs text-gray-500">
                        עדכון: {customer.last_contact || 'אתמול'}
                      </div>
                    </td>
                    
                    <td className="px-6 py-4">
                      <div className="flex flex-wrap gap-1">
                        {customer.tags?.map((tag, tagIndex) => (
                          <span key={tagIndex} className="bg-blue-100 text-blue-700 px-2 py-1 rounded-full text-xs font-medium">
                            {tag}
                          </span>
                        )) || (
                          <span className="text-gray-400 text-xs">אין תגיות</span>
                        )}
                      </div>
                    </td>
                    
                    <td className="px-6 py-4">
                      <div className="flex items-center gap-2">
                        <button
                          onClick={() => handleCustomerClick(customer)}
                          className="p-2 text-blue-600 hover:bg-blue-50 rounded-xl transition-all duration-200 hover:shadow-md group-hover:scale-110"
                          title="פרטי לקוח מלאים"
                        >
                          <Eye className="w-4 h-4" />
                        </button>
                        
                        <a
                          href={`https://wa.me/${customer.phone?.replace(/[^\d]/g, '')}`}
                          target="_blank"
                          rel="noopener noreferrer"
                          className="p-2 text-green-600 hover:bg-green-50 rounded-xl transition-all duration-200 hover:shadow-md group-hover:scale-110"
                          title="שלח WhatsApp"
                        >
                          <MessageSquare className="w-4 h-4" />
                        </a>
                        
                        <a
                          href={`tel:${customer.phone}`}
                          className="p-2 text-purple-600 hover:bg-purple-50 rounded-xl transition-all duration-200 hover:shadow-md group-hover:scale-110"
                          title="התקשר"
                        >
                          <Phone className="w-4 h-4" />
                        </a>
                        
                        <button className="p-2 text-gray-600 hover:bg-gray-50 rounded-xl transition-all duration-200 hover:shadow-md group-hover:scale-110">
                          <MoreVertical className="w-4 h-4" />
                        </button>
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
                <h3 className="text-xl font-bold text-gray-900 mb-2">אין לקוחות</h3>
                <p className="text-gray-500 mb-6">לא נמצאו לקוחות התואמים את החיפוש</p>
                <button className="bg-gradient-to-r from-blue-500 to-purple-600 text-white px-6 py-3 rounded-xl hover:shadow-lg transition-all duration-200">
                  הוסף לקוח חדש
                </button>
              </div>
            )}
          </div>
        </div>
      </div>
    </ModernLayout>
  );
}