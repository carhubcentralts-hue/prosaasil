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
  AlertCircle
} from 'lucide-react';

const CRMDashboard = ({ businessId, isAdmin = false }) => {
  const [customers, setCustomers] = useState([]);
  const [stats, setStats] = useState({});
  const [loading, setLoading] = useState(true);
  const [searchTerm, setSearchTerm] = useState('');
  const [statusFilter, setStatusFilter] = useState('');
  const [sourceFilter, setSourceFilter] = useState('');
  const [selectedCustomers, setSelectedCustomers] = useState([]);
  const [showNewCustomerModal, setShowNewCustomerModal] = useState(false);
  const [viewMode, setViewMode] = useState('table'); // table, cards, pipeline

  useEffect(() => {
    fetchCRMData();
  }, [businessId, searchTerm, statusFilter, sourceFilter]);

  const fetchCRMData = async () => {
    try {
      setLoading(true);
      
      // Get user role and business ID for proper permissions
      const userRole = localStorage.getItem('user_role');
      const currentBusinessId = businessId || localStorage.getItem('business_id');
      
      const params = new URLSearchParams();
      if (searchTerm) params.append('search', searchTerm);
      if (statusFilter) params.append('status', statusFilter);
      if (sourceFilter) params.append('source', sourceFilter);
      
      let customersEndpoint = `/api/crm/customers?business_id=${currentBusinessId}&${params}`;
      let statsEndpoint = `/api/crm/stats?business_id=${currentBusinessId}`;
      
      // Admin can access all data, business users only their own data
      if (userRole === 'admin' && isAdmin) {
        customersEndpoint = `/api/admin/customers?${params}`;
        statsEndpoint = `/api/admin/stats`;
      } else if (userRole === 'business' && currentBusinessId) {
        customersEndpoint = `/api/business/leads?business_id=${currentBusinessId}&${params}`;
        statsEndpoint = `/api/business/stats?business_id=${currentBusinessId}`;
      }
      
      const [customersRes, statsRes] = await Promise.all([
        axios.get(customersEndpoint),
        axios.get(statsEndpoint)
      ]);

      setCustomers(customersRes.data.customers || customersRes.data || []);
      setStats(statsRes.data || {});
    } catch (error) {
      console.error('Error fetching CRM data:', error);
      // Handle unauthorized access
      if (error.response?.status === 401) {
        localStorage.clear();
        window.location.href = '/login';
      }
    } finally {
      setLoading(false);
    }
  };

  const getStatusColor = (status) => {
    const colors = {
      'new': 'bg-blue-100 text-blue-800',
      'contacted': 'bg-yellow-100 text-yellow-800', 
      'qualified': 'bg-green-100 text-green-800',
      'proposal': 'bg-purple-100 text-purple-800',
      'negotiation': 'bg-orange-100 text-orange-800',
      'closed_won': 'bg-green-200 text-green-900',
      'closed_lost': 'bg-red-100 text-red-800',
      'active': 'bg-green-100 text-green-800',
      'inactive': 'bg-gray-100 text-gray-800'
    };
    return colors[status] || 'bg-gray-100 text-gray-800';
  };

  const getStatusIcon = (status) => {
    const icons = {
      'new': Clock,
      'contacted': Phone,
      'qualified': CheckCircle,
      'proposal': Edit,
      'closed_won': CheckCircle,
      'closed_lost': AlertCircle,
      'active': CheckCircle,
      'inactive': Clock
    };
    const Icon = icons[status] || Clock;
    return <Icon className="w-4 h-4" />;
  };

  const StatCard = ({ title, value, subtitle, icon: Icon, color = "blue" }) => (
    <div className="bg-white rounded-lg shadow-sm border border-gray-200 p-6">
      <div className="flex items-center justify-between">
        <div>
          <p className="text-sm font-medium text-gray-600 font-hebrew">{title}</p>
          <p className={`text-3xl font-bold text-${color}-600 font-hebrew`}>{value}</p>
          {subtitle && <p className="text-sm text-gray-500 font-hebrew">{subtitle}</p>}
        </div>
        <div className={`w-12 h-12 bg-${color}-100 rounded-lg flex items-center justify-center`}>
          <Icon className={`w-6 h-6 text-${color}-600`} />
        </div>
      </div>
    </div>
  );

  const CustomerRow = ({ customer, onSelect, isSelected }) => (
    <tr className={`hover:bg-gray-50 ${isSelected ? 'bg-blue-50' : ''}`}>
      <td className="px-6 py-4 whitespace-nowrap">
        <input
          type="checkbox"
          checked={isSelected}
          onChange={() => onSelect(customer.id)}
          className="rounded border-gray-300 text-blue-600 focus:ring-blue-500"
        />
      </td>
      <td className="px-6 py-4 whitespace-nowrap">
        <div className="flex items-center">
          <div className="w-10 h-10 bg-blue-100 rounded-full flex items-center justify-center">
            <span className="text-blue-600 font-medium text-sm font-hebrew">
              {customer.name?.charAt(0) || 'N'}
            </span>
          </div>
          <div className="mr-4">
            <div className="text-sm font-medium text-gray-900 font-hebrew">{customer.name}</div>
            <div className="text-sm text-gray-500 font-hebrew">{customer.company || '-'}</div>
          </div>
        </div>
      </td>
      <td className="px-6 py-4 whitespace-nowrap">
        <div className="text-sm text-gray-900 font-hebrew">{customer.phone}</div>
      </td>
      <td className="px-6 py-4 whitespace-nowrap">
        <div className="text-sm text-gray-900 font-hebrew">{customer.email}</div>
      </td>
      <td className="px-6 py-4 whitespace-nowrap">
        <span className={`inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium font-hebrew ${getStatusColor(customer.status)}`}>
          {getStatusIcon(customer.status)}
          <span className="mr-1">{customer.status_hebrew || customer.status}</span>
        </span>
      </td>
      <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-500 font-hebrew">
        {customer.source_hebrew || customer.source}
      </td>
      <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-500 font-hebrew">
        {new Date(customer.created_at).toLocaleDateString('he-IL')}
      </td>
      <td className="px-6 py-4 whitespace-nowrap text-right text-sm font-medium">
        <div className="flex space-x-2">
          <button className="text-blue-600 hover:text-blue-900">
            <Eye className="w-4 h-4" />
          </button>
          <button className="text-green-600 hover:text-green-900">
            <PhoneCall className="w-4 h-4" />
          </button>
          <button className="text-yellow-600 hover:text-yellow-900">
            <Edit className="w-4 h-4" />
          </button>
          <button className="text-red-600 hover:text-red-900">
            <Trash2 className="w-4 h-4" />
          </button>
        </div>
      </td>
    </tr>
  );

  if (loading) {
    return (
      <div className="min-h-screen bg-gray-50 flex items-center justify-center" dir="rtl">
        <div className="text-center font-hebrew">
          <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-blue-600 mx-auto mb-4"></div>
          <p className="text-gray-600">טוען נתוני CRM...</p>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-gray-50" dir="rtl">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
        
        {/* Header */}
        <div className="flex justify-between items-center mb-8">
          <div>
            <h1 className="text-3xl font-bold text-gray-900 font-hebrew">ניהול לקוחות CRM</h1>
            <p className="text-gray-600 font-hebrew">ניהול מתקדם של לקוחות ולידים</p>
          </div>
          <div className="flex gap-3">
            <button 
              onClick={() => setShowNewCustomerModal(true)}
              className="flex items-center gap-2 px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 font-hebrew"
            >
              <UserPlus className="w-4 h-4" />
              לקוח חדש
            </button>
            <button className="flex items-center gap-2 px-4 py-2 bg-green-600 text-white rounded-lg hover:bg-green-700 font-hebrew">
              <Upload className="w-4 h-4" />
              ייבוא
            </button>
            <button className="flex items-center gap-2 px-4 py-2 bg-gray-600 text-white rounded-lg hover:bg-gray-700 font-hebrew">
              <Download className="w-4 h-4" />
              ייצוא
            </button>
          </div>
        </div>

        {/* Stats Cards */}
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6 mb-8">
          <StatCard 
            title="סך הכל לקוחות" 
            value={stats.total_customers || 0}
            subtitle="כל הלקוחות במערכת"
            icon={Users} 
            color="blue" 
          />
          <StatCard 
            title="לקוחות פעילים" 
            value={stats.active_customers || 0}
            subtitle="לקוחות פעילים החודש"
            icon={Activity} 
            color="green" 
          />
          <StatCard 
            title="לידים חדשים" 
            value={stats.new_leads || 0}
            subtitle="השבוע האחרון"
            icon={UserPlus} 
            color="yellow" 
          />
          <StatCard 
            title="שיעור המרה" 
            value={`${stats.conversion_rate || 0}%`}
            subtitle="החודש האחרון"
            icon={CheckCircle} 
            color="purple" 
          />
        </div>

        {/* Filters and Search */}
        <div className="bg-white rounded-lg shadow-sm border border-gray-200 p-6 mb-6">
          <div className="flex flex-wrap items-center justify-between gap-4">
            <div className="flex items-center gap-4 flex-1">
              <div className="relative">
                <Search className="absolute right-3 top-1/2 transform -translate-y-1/2 text-gray-400 w-5 h-5" />
                <input
                  type="text"
                  placeholder="חיפוש לקוחות..."
                  value={searchTerm}
                  onChange={(e) => setSearchTerm(e.target.value)}
                  className="pl-10 pr-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent w-64 font-hebrew"
                />
              </div>
              
              <select 
                value={statusFilter} 
                onChange={(e) => setStatusFilter(e.target.value)}
                className="px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 font-hebrew"
              >
                <option value="">כל הסטטוסים</option>
                <option value="new">חדש</option>
                <option value="contacted">יצירת קשר</option>
                <option value="qualified">מוכשר</option>
                <option value="proposal">הצעה</option>
                <option value="closed_won">נסגר - הצליח</option>
                <option value="closed_lost">נסגר - נכשל</option>
              </select>

              <select 
                value={sourceFilter} 
                onChange={(e) => setSourceFilter(e.target.value)}
                className="px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 font-hebrew"
              >
                <option value="">כל המקורות</option>
                <option value="website">אתר</option>
                <option value="phone">טלפון</option>
                <option value="whatsapp">WhatsApp</option>
                <option value="referral">הפניה</option>
                <option value="social">רשתות חברתיות</option>
              </select>
            </div>

            <div className="flex items-center gap-2">
              <button 
                onClick={() => setViewMode('table')}
                className={`p-2 rounded-lg ${viewMode === 'table' ? 'bg-blue-100 text-blue-600' : 'text-gray-400'}`}
              >
                <Users className="w-5 h-5" />
              </button>
              <button 
                onClick={() => setViewMode('cards')}
                className={`p-2 rounded-lg ${viewMode === 'cards' ? 'bg-blue-100 text-blue-600' : 'text-gray-400'}`}
              >
                <Activity className="w-5 h-5" />
              </button>
            </div>
          </div>
        </div>

        {/* Customers Table */}
        <div className="bg-white rounded-lg shadow-sm border border-gray-200">
          {selectedCustomers.length > 0 && (
            <div className="px-6 py-3 bg-blue-50 border-b border-gray-200">
              <div className="flex items-center justify-between">
                <span className="text-sm text-blue-600 font-hebrew">
                  נבחרו {selectedCustomers.length} לקוחות
                </span>
                <div className="flex gap-2">
                  <button className="text-sm px-3 py-1 bg-blue-600 text-white rounded font-hebrew">
                    שלח הודעה
                  </button>
                  <button className="text-sm px-3 py-1 bg-red-600 text-white rounded font-hebrew">
                    מחק
                  </button>
                </div>
              </div>
            </div>
          )}
          
          <div className="overflow-x-auto">
            <table className="min-w-full divide-y divide-gray-200">
              <thead className="bg-gray-50">
                <tr>
                  <th className="px-6 py-3 text-right text-xs font-medium text-gray-500 uppercase tracking-wider">
                    <input
                      type="checkbox"
                      className="rounded border-gray-300 text-blue-600 focus:ring-blue-500"
                      onChange={(e) => {
                        if (e.target.checked) {
                          setSelectedCustomers(customers.map(c => c.id));
                        } else {
                          setSelectedCustomers([]);
                        }
                      }}
                    />
                  </th>
                  <th className="px-6 py-3 text-right text-xs font-medium text-gray-500 uppercase tracking-wider font-hebrew">
                    לקוח
                  </th>
                  <th className="px-6 py-3 text-right text-xs font-medium text-gray-500 uppercase tracking-wider font-hebrew">
                    טלפון
                  </th>
                  <th className="px-6 py-3 text-right text-xs font-medium text-gray-500 uppercase tracking-wider font-hebrew">
                    אימייל
                  </th>
                  <th className="px-6 py-3 text-right text-xs font-medium text-gray-500 uppercase tracking-wider font-hebrew">
                    סטטוס
                  </th>
                  <th className="px-6 py-3 text-right text-xs font-medium text-gray-500 uppercase tracking-wider font-hebrew">
                    מקור
                  </th>
                  <th className="px-6 py-3 text-right text-xs font-medium text-gray-500 uppercase tracking-wider font-hebrew">
                    תאריך יצירה
                  </th>
                  <th className="px-6 py-3 text-right text-xs font-medium text-gray-500 uppercase tracking-wider font-hebrew">
                    פעולות
                  </th>
                </tr>
              </thead>
              <tbody className="bg-white divide-y divide-gray-200">
                {customers.map((customer) => (
                  <CustomerRow
                    key={customer.id}
                    customer={customer}
                    onSelect={(id) => {
                      setSelectedCustomers(prev => 
                        prev.includes(id) 
                          ? prev.filter(cId => cId !== id)
                          : [...prev, id]
                      );
                    }}
                    isSelected={selectedCustomers.includes(customer.id)}
                  />
                ))}
              </tbody>
            </table>
          </div>

          {customers.length === 0 && (
            <div className="text-center py-12">
              <Users className="w-12 h-12 text-gray-400 mx-auto mb-4" />
              <h3 className="text-lg font-medium text-gray-900 font-hebrew">אין לקוחות</h3>
              <p className="text-gray-500 font-hebrew">התחל בהוספת הלקוח הראשון שלך</p>
              <button 
                onClick={() => setShowNewCustomerModal(true)}
                className="mt-4 px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 font-hebrew"
              >
                הוסף לקוח חדש
              </button>
            </div>
          )}
        </div>
      </div>
    </div>
  );
};

export default CRMDashboard;