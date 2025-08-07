import React, { useState, useEffect } from 'react';
import ModernLayout from '../components/ModernLayout';
import { 
  Building2, Plus, Search, Filter, Star, Phone, MessageSquare,
  Eye, Edit3, Trash2, FileText, Settings, Users,
  ArrowUpRight, TrendingUp, Activity, CheckCircle,
  Mail, MapPin, Clock, Tag, ChevronDown, MoreVertical,
  Shield, Key, Globe, Calendar
} from 'lucide-react';

export default function AdminBusinesses() {
  const [businesses, setBusinesses] = useState([]);
  const [loading, setLoading] = useState(true);
  const [searchTerm, setSearchTerm] = useState('');
  const [filterStatus, setFilterStatus] = useState('all');
  const [selectedBusiness, setSelectedBusiness] = useState(null);
  const [showBusinessModal, setShowBusinessModal] = useState(false);

  useEffect(() => {
    loadBusinesses();
  }, []);

  const loadBusinesses = async () => {
    try {
      // Demo business data for admin
      const demoBusinesses = [
        {
          id: 1,
          name: 'שירותי ייעוץ ABC',
          owner: 'יוסי כהן',
          phone: '050-1234567',
          email: 'yossi@abc-consulting.com',
          status: 'active',
          plan: 'premium',
          customers: 156,
          calls_today: 23,
          whatsapp_messages: 45,
          revenue: '₪25,600',
          created_at: '2024-01-15',
          last_activity: '2025-08-07 14:30',
          address: 'תל אביב, רחוב הארבעה 12',
          website: 'www.abc-consulting.com',
          industry: 'ייעוץ עסקי',
          tags: ['VIP', 'ייעוץ', 'מובילים']
        },
        {
          id: 2,
          name: 'מכירות דיגיטליות XYZ',
          owner: 'רחל לוי',
          phone: '052-9876543',
          email: 'rachel@xyz-digital.co.il',
          status: 'active',
          plan: 'standard',
          customers: 89,
          calls_today: 15,
          whatsapp_messages: 28,
          revenue: '₪18,900',
          created_at: '2024-03-20',
          last_activity: '2025-08-07 13:45',
          address: 'חיפה, שדרות בן גוריון 45',
          website: 'www.xyz-digital.co.il',
          industry: 'מכירות דיגיטליות',
          tags: ['מכירות', 'דיגיטל']
        },
        {
          id: 3,
          name: 'שירותי לקוחות DEF',
          owner: 'דני אברהם',
          phone: '053-5555555',
          email: 'danny@def-services.com',
          status: 'trial',
          plan: 'trial',
          customers: 34,
          calls_today: 7,
          whatsapp_messages: 12,
          revenue: '₪5,400',
          created_at: '2025-07-28',
          last_activity: '2025-08-07 12:15',
          address: 'ירושלים, רחוב יפו 89',
          website: 'www.def-services.com',
          industry: 'שירותי לקוחות',
          tags: ['חדש', 'ניסיון']
        }
      ];
      
      setBusinesses(demoBusinesses);
      setLoading(false);
    } catch (error) {
      console.error('Error loading businesses:', error);
      setLoading(false);
    }
  };

  const filteredBusinesses = businesses.filter(business => {
    const matchesSearch = business.name?.toLowerCase().includes(searchTerm.toLowerCase()) ||
                         business.owner?.toLowerCase().includes(searchTerm.toLowerCase()) ||
                         business.phone?.includes(searchTerm) ||
                         business.email?.toLowerCase().includes(searchTerm.toLowerCase());
    const matchesFilter = filterStatus === 'all' || business.status === filterStatus;
    return matchesSearch && matchesFilter;
  });

  const handleBusinessClick = (business) => {
    setSelectedBusiness(business);
    setShowBusinessModal(true);
  };

  const getStatusColor = (status) => {
    switch (status) {
      case 'active': return 'bg-green-100 text-green-800 border-green-200';
      case 'trial': return 'bg-blue-100 text-blue-800 border-blue-200';
      case 'suspended': return 'bg-red-100 text-red-800 border-red-200';
      case 'pending': return 'bg-yellow-100 text-yellow-800 border-yellow-200';
      default: return 'bg-gray-100 text-gray-800 border-gray-200';
    }
  };

  const getStatusText = (status) => {
    switch (status) {
      case 'active': return 'פעיל';
      case 'trial': return 'ניסיון';
      case 'suspended': return 'מושעה';
      case 'pending': return 'ממתין';
      default: return 'לא ידוע';
    }
  };

  const getPlanColor = (plan) => {
    switch (plan) {
      case 'premium': return 'bg-purple-100 text-purple-800 border-purple-200';
      case 'standard': return 'bg-blue-100 text-blue-800 border-blue-200';
      case 'trial': return 'bg-gray-100 text-gray-800 border-gray-200';
      default: return 'bg-gray-100 text-gray-800 border-gray-200';
    }
  };

  const getPlanText = (plan) => {
    switch (plan) {
      case 'premium': return 'פרימיום';
      case 'standard': return 'רגיל';
      case 'trial': return 'ניסיון';
      default: return 'לא ידוע';
    }
  };

  if (loading) {
    return (
      <ModernLayout userRole="admin">
        <div className="flex items-center justify-center min-h-[400px]">
          <div className="text-center">
            <div className="animate-spin rounded-full h-32 w-32 border-b-2 border-blue-600 mx-auto mb-4"></div>
            <p className="text-gray-600">טוען נתוני עסקים...</p>
          </div>
        </div>
      </ModernLayout>
    );
  }

  return (
    <ModernLayout userRole="admin">
      <div className="space-y-8">
        {/* Header Section */}
        <div className="bg-gradient-to-r from-blue-600 to-indigo-700 rounded-3xl p-8 text-white">
          <div className="flex items-center justify-between">
            <div>
              <h1 className="text-4xl font-bold mb-2 flex items-center gap-3">
                <Building2 className="w-10 h-10" />
                🏢 ניהול עסקים
              </h1>
              <p className="text-blue-100 text-lg">
                ניהול כל העסקים במערכת והגדרות מתקדמות
              </p>
            </div>
            <div className="text-left">
              <div className="text-3xl font-bold">{filteredBusinesses.length}</div>
              <div className="text-blue-100">עסקים פעילים</div>
            </div>
          </div>
        </div>

        {/* Stats Cards */}
        <div className="grid grid-cols-1 md:grid-cols-4 gap-6">
          <div className="bg-white rounded-2xl p-6 shadow-lg border border-gray-100">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-gray-600 text-sm">עסקים פעילים</p>
                <p className="text-3xl font-bold text-green-600">
                  {businesses.filter(b => b.status === 'active').length}
                </p>
                <p className="text-green-500 text-sm flex items-center gap-1">
                  <ArrowUpRight className="w-4 h-4" />
                  +8% החודש
                </p>
              </div>
              <CheckCircle className="w-12 h-12 text-green-500" />
            </div>
          </div>

          <div className="bg-white rounded-2xl p-6 shadow-lg border border-gray-100">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-gray-600 text-sm">בניסיון</p>
                <p className="text-3xl font-bold text-blue-600">
                  {businesses.filter(b => b.status === 'trial').length}
                </p>
                <p className="text-blue-500 text-sm flex items-center gap-1">
                  <Calendar className="w-4 h-4" />
                  +3 השבוע
                </p>
              </div>
              <Star className="w-12 h-12 text-blue-500" />
            </div>
          </div>

          <div className="bg-white rounded-2xl p-6 shadow-lg border border-gray-100">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-gray-600 text-sm">שיחות היום</p>
                <p className="text-3xl font-bold text-purple-600">
                  {businesses.reduce((sum, b) => sum + b.calls_today, 0)}
                </p>
                <p className="text-purple-500 text-sm flex items-center gap-1">
                  <Phone className="w-4 h-4" />
                  זמן אמת
                </p>
              </div>
              <Activity className="w-12 h-12 text-purple-500" />
            </div>
          </div>

          <div className="bg-white rounded-2xl p-6 shadow-lg border border-gray-100">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-gray-600 text-sm">הכנסות החודש</p>
                <p className="text-3xl font-bold text-orange-600">₪487K</p>
                <p className="text-orange-500 text-sm flex items-center gap-1">
                  <TrendingUp className="w-4 h-4" />
                  +23% גידול
                </p>
              </div>
              <TrendingUp className="w-12 h-12 text-orange-500" />
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
                  placeholder="חיפוש עסק, בעלים או מייל..."
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
                <option value="all">כל הסטטוסים</option>
                <option value="active">פעילים</option>
                <option value="trial">בניסיון</option>
                <option value="suspended">מושעים</option>
                <option value="pending">ממתינים</option>
              </select>
            </div>
            
            <button className="bg-gradient-to-r from-blue-500 to-purple-600 text-white px-6 py-3 rounded-xl hover:shadow-lg transition-all duration-200 flex items-center gap-2">
              <Plus className="w-5 h-5" />
              עסק חדש
            </button>
          </div>
        </div>

        {/* Businesses Table */}
        <div className="bg-white rounded-2xl shadow-lg border border-gray-100 overflow-hidden">
          <div className="px-8 py-6 border-b border-gray-200 bg-gradient-to-r from-gray-50 to-gray-100">
            <h2 className="text-2xl font-bold text-gray-900 flex items-center gap-3">
              <div className="w-8 h-8 bg-gradient-to-br from-blue-500 to-blue-600 rounded-xl flex items-center justify-center">
                <Building2 className="w-4 h-4 text-white" />
              </div>
              רשימת עסקים ({filteredBusinesses.length})
            </h2>
          </div>
          
          <div className="overflow-x-auto">
            <table className="w-full">
              <thead className="bg-gradient-to-r from-gray-50 to-gray-100">
                <tr>
                  <th className="px-6 py-4 text-right font-semibold text-gray-900">עסק</th>
                  <th className="px-6 py-4 text-right font-semibold text-gray-900">בעלים</th>
                  <th className="px-6 py-4 text-right font-semibold text-gray-900">סטטוס</th>
                  <th className="px-6 py-4 text-right font-semibold text-gray-900">תוכנית</th>
                  <th className="px-6 py-4 text-right font-semibold text-gray-900">פעילות</th>
                  <th className="px-6 py-4 text-right font-semibold text-gray-900">הכנסות</th>
                  <th className="px-6 py-4 text-right font-semibold text-gray-900">פעולות</th>
                </tr>
              </thead>
              <tbody className="bg-white divide-y divide-gray-100">
                {filteredBusinesses.map((business, index) => (
                  <tr key={business.id || index} className="hover:bg-blue-50 transition-all duration-200 group">
                    <td className="px-6 py-4">
                      <div className="flex items-center gap-4">
                        <div className="w-12 h-12 bg-gradient-to-br from-blue-500 to-purple-600 rounded-full flex items-center justify-center text-white font-bold text-lg">
                          {business.name?.charAt(0) || 'B'}
                        </div>
                        <div>
                          <div className="text-sm font-semibold text-gray-900">
                            {business.name}
                          </div>
                          <div className="text-sm text-gray-500 flex items-center gap-2">
                            <Globe className="w-4 h-4" />
                            {business.industry}
                          </div>
                        </div>
                      </div>
                    </td>
                    
                    <td className="px-6 py-4">
                      <div className="space-y-1">
                        <div className="text-sm font-medium text-gray-900">{business.owner}</div>
                        <div className="text-sm text-gray-500 flex items-center gap-2">
                          <Phone className="w-4 h-4 text-blue-500" />
                          {business.phone}
                        </div>
                        <div className="text-sm text-gray-500 flex items-center gap-2">
                          <Mail className="w-4 h-4 text-gray-400" />
                          {business.email}
                        </div>
                      </div>
                    </td>
                    
                    <td className="px-6 py-4">
                      <span className={`inline-flex items-center px-3 py-1 rounded-full text-sm font-medium border ${getStatusColor(business.status)}`}>
                        {getStatusText(business.status)}
                      </span>
                    </td>
                    
                    <td className="px-6 py-4">
                      <span className={`inline-flex items-center px-3 py-1 rounded-full text-sm font-medium border ${getPlanColor(business.plan)}`}>
                        {getPlanText(business.plan)}
                      </span>
                    </td>
                    
                    <td className="px-6 py-4">
                      <div className="space-y-1">
                        <div className="text-sm text-gray-900">
                          <span className="font-medium">{business.customers}</span> לקוחות
                        </div>
                        <div className="text-sm text-blue-600">
                          <span className="font-medium">{business.calls_today}</span> שיחות היום
                        </div>
                        <div className="text-sm text-green-600">
                          <span className="font-medium">{business.whatsapp_messages}</span> הודעות WA
                        </div>
                      </div>
                    </td>
                    
                    <td className="px-6 py-4">
                      <div className="text-sm font-semibold text-gray-900">
                        {business.revenue}
                      </div>
                      <div className="text-xs text-gray-500">
                        החודש
                      </div>
                    </td>
                    
                    <td className="px-6 py-4">
                      <div className="flex items-center gap-2">
                        <button
                          onClick={() => handleBusinessClick(business)}
                          className="p-2 text-blue-600 hover:bg-blue-50 rounded-xl transition-all duration-200 hover:shadow-md group-hover:scale-110"
                          title="צפה בפרטים"
                        >
                          <Eye className="w-4 h-4" />
                        </button>
                        
                        <button className="p-2 text-green-600 hover:bg-green-50 rounded-xl transition-all duration-200 hover:shadow-md group-hover:scale-110">
                          <Settings className="w-4 h-4" />
                        </button>
                        
                        <button className="p-2 text-purple-600 hover:bg-purple-50 rounded-xl transition-all duration-200 hover:shadow-md group-hover:scale-110">
                          <Shield className="w-4 h-4" />
                        </button>
                        
                        <button className="p-2 text-gray-600 hover:bg-gray-50 rounded-xl transition-all duration-200 hover:shadow-md group-hover:scale-110">
                          <MoreVertical className="w-4 h-4" />
                        </button>
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
            
            {filteredBusinesses.length === 0 && (
              <div className="text-center py-16">
                <div className="w-20 h-20 bg-gradient-to-br from-gray-100 to-gray-200 rounded-2xl flex items-center justify-center mx-auto mb-6">
                  <Building2 className="w-8 h-8 text-gray-400" />
                </div>
                <h3 className="text-xl font-bold text-gray-900 mb-2">אין עסקים</h3>
                <p className="text-gray-500 mb-6">לא נמצאו עסקים התואמים את החיפוש</p>
                <button className="bg-gradient-to-r from-blue-500 to-purple-600 text-white px-6 py-3 rounded-xl hover:shadow-lg transition-all duration-200">
                  הוסף עסק חדש
                </button>
              </div>
            )}
          </div>
        </div>

        {/* Quick Actions */}
        <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
          <div className="bg-white rounded-2xl p-6 shadow-lg border border-gray-100">
            <h3 className="text-lg font-bold text-gray-900 mb-4 flex items-center gap-2">
              <Activity className="w-5 h-5 text-blue-600" />
              פעילות אחרונה
            </h3>
            <div className="space-y-3">
              <div className="flex items-center gap-3 p-3 bg-green-50 rounded-lg">
                <div className="w-2 h-2 bg-green-500 rounded-full"></div>
                <span className="text-sm">שירותי לקוחות DEF הצטרף לניסיון</span>
                <span className="text-xs text-gray-500 mr-auto">לפני 2 שעות</span>
              </div>
              <div className="flex items-center gap-3 p-3 bg-blue-50 rounded-lg">
                <div className="w-2 h-2 bg-blue-500 rounded-full"></div>
                <span className="text-sm">שירותי ייעוץ ABC שדרג לפרימיום</span>
                <span className="text-xs text-gray-500 mr-auto">אתמול</span>
              </div>
              <div className="flex items-center gap-3 p-3 bg-purple-50 rounded-lg">
                <div className="w-2 h-2 bg-purple-500 rounded-full"></div>
                <span className="text-sm">מכירות דיגיטליות XYZ חידש מנוי</span>
                <span className="text-xs text-gray-500 mr-auto">לפני 3 ימים</span>
              </div>
            </div>
          </div>

          <div className="bg-white rounded-2xl p-6 shadow-lg border border-gray-100">
            <h3 className="text-lg font-bold text-gray-900 mb-4 flex items-center gap-2">
              <TrendingUp className="w-5 h-5 text-green-600" />
              מגמות שבועיות
            </h3>
            <div className="space-y-3">
              <div className="flex justify-between items-center">
                <span className="text-gray-600">עסקים חדשים</span>
                <span className="font-bold text-green-600 flex items-center gap-1">
                  <ArrowUpRight className="w-4 h-4" />
                  +12%
                </span>
              </div>
              <div className="flex justify-between items-center">
                <span className="text-gray-600">שיחות</span>
                <span className="font-bold text-blue-600 flex items-center gap-1">
                  <ArrowUpRight className="w-4 h-4" />
                  +28%
                </span>
              </div>
              <div className="flex justify-between items-center">
                <span className="text-gray-600">הכנסות</span>
                <span className="font-bold text-purple-600 flex items-center gap-1">
                  <ArrowUpRight className="w-4 h-4" />
                  +35%
                </span>
              </div>
            </div>
          </div>

          <div className="bg-white rounded-2xl p-6 shadow-lg border border-gray-100">
            <h3 className="text-lg font-bold text-gray-900 mb-4 flex items-center gap-2">
              <Shield className="w-5 h-5 text-red-600" />
              פעולות מנהל
            </h3>
            <div className="space-y-2">
              <button className="w-full text-right p-3 bg-blue-50 rounded-lg hover:bg-blue-100 transition-all text-sm text-blue-700">
                שלח הודעה לכל העסקים
              </button>
              <button className="w-full text-right p-3 bg-green-50 rounded-lg hover:bg-green-100 transition-all text-sm text-green-700">
                ייצא דוח כללי
              </button>
              <button className="w-full text-right p-3 bg-purple-50 rounded-lg hover:bg-purple-100 transition-all text-sm text-purple-700">
                הגדרות מערכת
              </button>
              <button className="w-full text-right p-3 bg-red-50 rounded-lg hover:bg-red-100 transition-all text-sm text-red-700">
                גיבוי מסד נתונים
              </button>
            </div>
          </div>
        </div>
      </div>
    </ModernLayout>
  );
}