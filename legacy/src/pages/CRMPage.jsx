import React, { useState, useEffect } from 'react';
import { Link } from 'wouter';
import { 
  Users, 
  Plus, 
  Search, 
  Filter,
  Phone,
  MessageCircle,
  Mail,
  Calendar,
  Star,
  MapPin,
  Edit,
  Eye,
  Trash2,
  UserPlus
} from 'lucide-react';

function CRMPage({ business }) {
  const [customers, setCustomers] = useState([]);
  const [stats, setStats] = useState({});
  const [loading, setLoading] = useState(true);
  const [searchTerm, setSearchTerm] = useState('');
  const [filters, setFilters] = useState({
    status: 'all',
    source: 'all',
    dateRange: 'all'
  });
  const [showAddModal, setShowAddModal] = useState(false);
  const [newCustomer, setNewCustomer] = useState({
    first_name: '',
    last_name: '',
    phone_number: '',
    email: '',
    company: '',
    status: 'lead'
  });

  useEffect(() => {
    fetchCRMData();
  }, [business?.id, filters, searchTerm]);

  const fetchCRMData = async () => {
    try {
      setLoading(true);
      const params = new URLSearchParams({
        business_id: business?.id,
        search: searchTerm,
        status: filters.status,
        source: filters.source,
        date_range: filters.dateRange
      });

      const [customersRes, statsRes] = await Promise.all([
        fetch(`/api/crm/customers?${params}`),
        fetch(`/api/crm/stats?business_id=${business?.id}`)
      ]);

      if (customersRes.ok) {
        const customersData = await customersRes.json();
        setCustomers(customersData.customers || []);
      }

      if (statsRes.ok) {
        const statsData = await statsRes.json();
        setStats(statsData);
      }
    } catch (error) {
      console.error('Failed to fetch CRM data:', error);
    } finally {
      setLoading(false);
    }
  };

  const addCustomer = async () => {
    try {
      const response = await fetch('/api/crm/customers', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          ...newCustomer,
          business_id: business?.id
        }),
      });

      if (response.ok) {
        setShowAddModal(false);
        setNewCustomer({
          first_name: '',
          last_name: '',
          phone_number: '',
          email: '',
          company: '',
          status: 'lead'
        });
        fetchCRMData();
      }
    } catch (error) {
      console.error('Failed to add customer:', error);
    }
  };

  const deleteCustomer = async (customerId) => {
    if (!confirm('האם אתה בטוח שברצונך למחוק לקוח זה?')) return;

    try {
      const response = await fetch(`/api/crm/customers/${customerId}`, {
        method: 'DELETE'
      });

      if (response.ok) {
        fetchCRMData();
      }
    } catch (error) {
      console.error('Failed to delete customer:', error);
    }
  };

  const getStatusColor = (status) => {
    switch (status) {
      case 'lead':
        return 'bg-yellow-100 text-yellow-800';
      case 'prospect':
        return 'bg-blue-100 text-blue-800';
      case 'customer':
        return 'bg-green-100 text-green-800';
      case 'inactive':
        return 'bg-gray-100 text-gray-800';
      default:
        return 'bg-gray-100 text-gray-800';
    }
  };

  const getStatusText = (status) => {
    switch (status) {
      case 'lead':
        return 'ליד';
      case 'prospect':
        return 'פרוספקט';
      case 'customer':
        return 'לקוח';
      case 'inactive':
        return 'לא פעיל';
      default:
        return status;
    }
  };

  if (loading) {
    return (
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
        <div className="animate-pulse">
          <div className="h-8 bg-gray-200 rounded w-1/4 mb-6"></div>
          <div className="grid grid-cols-1 md:grid-cols-4 gap-4 mb-8">
            {[...Array(4)].map((_, i) => (
              <div key={i} className="h-24 bg-gray-200 rounded-lg"></div>
            ))}
          </div>
        </div>
      </div>
    );
  }

  const crmStats = [
    {
      title: 'סה"כ לקוחות',
      value: stats.total_customers || 0,
      icon: Users,
      color: 'text-blue-600',
      bgColor: 'bg-blue-50'
    },
    {
      title: 'לקוחות חדשים החודש',
      value: stats.new_customers_this_month || 0,
      icon: UserPlus,
      color: 'text-green-600',
      bgColor: 'bg-green-50'
    },
    {
      title: 'לידים פעילים',
      value: stats.active_leads || 0,
      icon: Star,
      color: 'text-yellow-600',
      bgColor: 'bg-yellow-50'
    },
    {
      title: 'שיחות השבוע',
      value: stats.calls_this_week || 0,
      icon: Phone,
      color: 'text-purple-600',
      bgColor: 'bg-purple-50'
    }
  ];

  return (
    <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
      {/* Page Header */}
      <div className="mb-8">
        <div className="flex justify-between items-center">
          <div>
            <h1 className="text-2xl font-bold text-gray-900">
              ניהול לקוחות (CRM)
            </h1>
            <p className="text-gray-600 mt-1">
              ניהול מסד נתונים מלא של לקוחות וליידים
            </p>
          </div>
          <button
            onClick={() => setShowAddModal(true)}
            className="bg-blue-600 text-white px-4 py-2 rounded-md hover:bg-blue-700 flex items-center"
          >
            <Plus className="w-4 h-4 ml-2" />
            הוסף לקוח חדש
          </button>
        </div>
      </div>

      {/* CRM Stats */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4 mb-8">
        {crmStats.map((stat, index) => {
          const Icon = stat.icon;
          return (
            <div key={index} className="bg-white rounded-lg shadow p-6">
              <div className="flex items-center justify-between">
                <div>
                  <p className="text-sm font-medium text-gray-600 mb-1">
                    {stat.title}
                  </p>
                  <p className="text-2xl font-bold text-gray-900">
                    {stat.value}
                  </p>
                </div>
                <div className={`${stat.bgColor} p-3 rounded-lg`}>
                  <Icon className={`w-6 h-6 ${stat.color}`} />
                </div>
              </div>
            </div>
          );
        })}
      </div>

      {/* Filters and Search */}
      <div className="bg-white rounded-lg shadow mb-6">
        <div className="px-6 py-4 border-b border-gray-200">
          <div className="flex flex-wrap gap-4">
            <div className="flex-1 min-w-64">
              <div className="relative">
                <Search className="absolute right-3 top-1/2 transform -translate-y-1/2 text-gray-400 w-4 h-4" />
                <input
                  type="text"
                  placeholder="חיפוש לקוחות..."
                  value={searchTerm}
                  onChange={(e) => setSearchTerm(e.target.value)}
                  className="w-full pr-10 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-1 focus:ring-blue-500"
                />
              </div>
            </div>
            
            <div>
              <select
                value={filters.status}
                onChange={(e) => setFilters({ ...filters, status: e.target.value })}
                className="border border-gray-300 rounded-md px-3 py-2 text-sm"
              >
                <option value="all">כל הסטטוסים</option>
                <option value="lead">ליידים</option>
                <option value="prospect">פרוספקטים</option>
                <option value="customer">לקוחות</option>
                <option value="inactive">לא פעילים</option>
              </select>
            </div>

            <div>
              <select
                value={filters.source}
                onChange={(e) => setFilters({ ...filters, source: e.target.value })}
                className="border border-gray-300 rounded-md px-3 py-2 text-sm"
              >
                <option value="all">כל המקורות</option>
                <option value="website">אתר אינטרנט</option>
                <option value="phone">טלפון</option>
                <option value="whatsapp">וואטסאפ</option>
                <option value="referral">הפניה</option>
              </select>
            </div>
          </div>
        </div>
      </div>

      {/* Customers Table */}
      <div className="bg-white rounded-lg shadow">
        <div className="px-6 py-4 border-b border-gray-200">
          <h3 className="text-lg font-semibold text-gray-900">
            רשימת לקוחות ({customers.length})
          </h3>
        </div>
        
        <div className="overflow-x-auto">
          <table className="min-w-full divide-y divide-gray-200">
            <thead className="bg-gray-50">
              <tr>
                <th className="px-6 py-3 text-right text-xs font-medium text-gray-500 uppercase">
                  לקוח
                </th>
                <th className="px-6 py-3 text-right text-xs font-medium text-gray-500 uppercase">
                  פרטי קשר
                </th>
                <th className="px-6 py-3 text-right text-xs font-medium text-gray-500 uppercase">
                  סטטוס
                </th>
                <th className="px-6 py-3 text-right text-xs font-medium text-gray-500 uppercase">
                  פעילות אחרונה
                </th>
                <th className="px-6 py-3 text-right text-xs font-medium text-gray-500 uppercase">
                  פעולות
                </th>
              </tr>
            </thead>
            <tbody className="bg-white divide-y divide-gray-200">
              {customers.map((customer) => (
                <tr key={customer.id} className="hover:bg-gray-50">
                  <td className="px-6 py-4 whitespace-nowrap">
                    <div className="flex items-center">
                      <div className="w-10 h-10 bg-blue-100 rounded-full flex items-center justify-center ml-3">
                        <Users className="w-5 h-5 text-blue-600" />
                      </div>
                      <div>
                        <div className="text-sm font-medium text-gray-900">
                          {customer.first_name} {customer.last_name}
                        </div>
                        {customer.company && (
                          <div className="text-sm text-gray-500">
                            {customer.company}
                          </div>
                        )}
                      </div>
                    </div>
                  </td>
                  <td className="px-6 py-4 whitespace-nowrap">
                    <div className="space-y-1">
                      <div className="flex items-center text-sm text-gray-900">
                        <Phone className="w-4 h-4 ml-2 text-gray-400" />
                        {customer.phone_number}
                      </div>
                      {customer.email && (
                        <div className="flex items-center text-sm text-gray-500">
                          <Mail className="w-4 h-4 ml-2 text-gray-400" />
                          {customer.email}
                        </div>
                      )}
                    </div>
                  </td>
                  <td className="px-6 py-4 whitespace-nowrap">
                    <span className={`inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium ${getStatusColor(customer.status)}`}>
                      {getStatusText(customer.status)}
                    </span>
                  </td>
                  <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-900">
                    <div className="flex items-center">
                      <Calendar className="w-4 h-4 ml-2 text-gray-400" />
                      {customer.last_interaction ? 
                        new Date(customer.last_interaction).toLocaleDateString('he-IL') :
                        'אין פעילות'
                      }
                    </div>
                  </td>
                  <td className="px-6 py-4 whitespace-nowrap text-sm font-medium">
                    <div className="flex space-x-2 space-x-reverse">
                      <Link
                        href={`/crm/customer/${customer.id}`}
                        className="text-blue-600 hover:text-blue-900 flex items-center"
                      >
                        <Eye className="w-4 h-4 ml-1" />
                        צפה
                      </Link>
                      <button className="text-indigo-600 hover:text-indigo-900 flex items-center">
                        <Edit className="w-4 h-4 ml-1" />
                        ערוך
                      </button>
                      <button 
                        onClick={() => deleteCustomer(customer.id)}
                        className="text-red-600 hover:text-red-900 flex items-center"
                      >
                        <Trash2 className="w-4 h-4 ml-1" />
                        מחק
                      </button>
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>

        {customers.length === 0 && !loading && (
          <div className="text-center py-12">
            <Users className="w-12 h-12 text-gray-400 mx-auto mb-4" />
            <h3 className="text-lg font-medium text-gray-900 mb-2">
              אין לקוחות
            </h3>
            <p className="text-gray-500 mb-4">
              התחל על ידי הוספת הלקוח הראשון שלך
            </p>
            <button
              onClick={() => setShowAddModal(true)}
              className="bg-blue-600 text-white px-4 py-2 rounded-md hover:bg-blue-700"
            >
              הוסף לקוח ראשון
            </button>
          </div>
        )}
      </div>

      {/* Add Customer Modal */}
      {showAddModal && (
        <div className="fixed inset-0 bg-gray-600 bg-opacity-50 overflow-y-auto h-full w-full z-50">
          <div className="relative top-20 mx-auto p-5 border w-96 shadow-lg rounded-md bg-white">
            <div className="mt-3">
              <h3 className="text-lg font-medium text-gray-900 text-center mb-4">
                הוסף לקוח חדש
              </h3>
              
              <div className="space-y-4">
                <div className="grid grid-cols-2 gap-4">
                  <input
                    type="text"
                    placeholder="שם פרטי"
                    value={newCustomer.first_name}
                    onChange={(e) => setNewCustomer({...newCustomer, first_name: e.target.value})}
                    className="border border-gray-300 rounded-md px-3 py-2 w-full"
                  />
                  <input
                    type="text"
                    placeholder="שם משפחה"
                    value={newCustomer.last_name}
                    onChange={(e) => setNewCustomer({...newCustomer, last_name: e.target.value})}
                    className="border border-gray-300 rounded-md px-3 py-2 w-full"
                  />
                </div>
                
                <input
                  type="tel"
                  placeholder="מספר טלפון"
                  value={newCustomer.phone_number}
                  onChange={(e) => setNewCustomer({...newCustomer, phone_number: e.target.value})}
                  className="border border-gray-300 rounded-md px-3 py-2 w-full"
                />
                
                <input
                  type="email"
                  placeholder="כתובת אימייל"
                  value={newCustomer.email}
                  onChange={(e) => setNewCustomer({...newCustomer, email: e.target.value})}
                  className="border border-gray-300 rounded-md px-3 py-2 w-full"
                />
                
                <input
                  type="text"
                  placeholder="חברה"
                  value={newCustomer.company}
                  onChange={(e) => setNewCustomer({...newCustomer, company: e.target.value})}
                  className="border border-gray-300 rounded-md px-3 py-2 w-full"
                />
                
                <select
                  value={newCustomer.status}
                  onChange={(e) => setNewCustomer({...newCustomer, status: e.target.value})}
                  className="border border-gray-300 rounded-md px-3 py-2 w-full"
                >
                  <option value="lead">ליד</option>
                  <option value="prospect">פרוספקט</option>
                  <option value="customer">לקוח</option>
                </select>
              </div>
              
              <div className="flex justify-end space-x-3 space-x-reverse mt-6">
                <button
                  onClick={() => setShowAddModal(false)}
                  className="px-4 py-2 bg-gray-300 text-gray-700 rounded-md hover:bg-gray-400"
                >
                  ביטול
                </button>
                <button
                  onClick={addCustomer}
                  className="px-4 py-2 bg-blue-600 text-white rounded-md hover:bg-blue-700"
                >
                  הוסף לקוח
                </button>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

export default CRMPage;