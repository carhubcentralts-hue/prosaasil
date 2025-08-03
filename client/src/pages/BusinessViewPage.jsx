import React, { useState, useEffect } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { Users, Phone, MessageCircle, ArrowRight, Eye, BarChart3, Clock, DollarSign } from 'lucide-react';

const BusinessViewPage = () => {
  const { businessId } = useParams();
  const navigate = useNavigate();
  const [businessData, setBusinessData] = useState(null);
  const [stats, setStats] = useState({
    todayCalls: 0,
    pendingTasks: 0,
    activeCustomers: 0,
    todayRevenue: 0
  });
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    // טוען נתוני העסק לפי ה-ID
    const fetchBusinessData = () => {
      // נתונים לדוגמה - בעתיד יגיעו מה-API
      const businessesData = {
        1: {
          name: 'טכנו סולושנס בע"מ',
          id: 1,
          identifier: 'techno-solutions',
          services: { crm: true, calls: true, whatsapp: true },
          phone: '+972-33-763-8005',
          whatsapp_phone: '+972-50-123-4567',
          lastActivity: '2025-08-03 13:45',
          status: 'active',
          created_at: '2025-01-15',
          stats: {
            todayCalls: 12,
            pendingTasks: 7,
            activeCustomers: 45,
            todayRevenue: 15750
          }
        },
        2: {
          name: 'חברת השיווק הדיגיטלי',
          id: 2,
          identifier: 'digital-marketing',
          services: { crm: true, calls: false, whatsapp: true },
          phone: '+972-33-456-7890',
          whatsapp_phone: '+972-50-987-6543',
          lastActivity: '2025-08-03 12:30',
          status: 'active',
          created_at: '2025-02-20',
          stats: {
            todayCalls: 8,
            pendingTasks: 3,
            activeCustomers: 28,
            todayRevenue: 8200
          }
        },
        3: {
          name: 'פתרונות עסקיים',
          id: 3,
          identifier: 'business-solutions',
          services: { crm: false, calls: true, whatsapp: false },
          phone: '+972-33-111-2222',
          whatsapp_phone: null,
          lastActivity: '2025-08-02 16:45',
          status: 'inactive',
          created_at: '2025-03-10',
          stats: {
            todayCalls: 0,
            pendingTasks: 12,
            activeCustomers: 15,
            todayRevenue: 0
          }
        }
      };
      
      const business = businessesData[businessId];
      if (business) {
        setBusinessData(business);
        setStats(business.stats);
      }
      setLoading(false);
    };

    fetchBusinessData();
  }, [businessId]);

  const formatHebrewDate = () => {
    const now = new Date();
    const days = ['ראשון', 'שני', 'שלישי', 'רביעי', 'חמישי', 'שישי', 'שבת'];
    const months = ['ינואר', 'פברואר', 'מרץ', 'אפריל', 'מאי', 'יוני', 
                   'יולי', 'אוגוסט', 'ספטמבר', 'אוקטובר', 'נובמבר', 'דצמבר'];
    
    const dayName = days[now.getDay()];
    const day = now.getDate();
    const month = months[now.getMonth()];
    const year = now.getFullYear();
    
    return `יום ${dayName}, ${day} ב${month} ${year}`;
  };

  const formatCurrency = (amount) => {
    return new Intl.NumberFormat('he-IL', {
      style: 'currency',
      currency: 'ILS'
    }).format(amount);
  };

  const getStatusColor = (status) => {
    return status === 'active' ? 'text-green-600' : 'text-red-600';
  };

  const getStatusIcon = (status) => {
    return status === 'active' ? '🟢' : '🔴';
  };

  const goBackToAdmin = () => {
    navigate('/admin/dashboard');
  };

  if (loading) {
    return (
      <div className="min-h-screen bg-gray-50 flex items-center justify-center">
        <div className="text-center">
          <Eye className="w-8 h-8 text-blue-500 animate-spin mx-auto mb-4" />
          <p className="text-gray-600 font-hebrew">טוען נתוני עסק...</p>
        </div>
      </div>
    );
  }

  if (!businessData) {
    return (
      <div className="min-h-screen bg-gray-50 flex items-center justify-center">
        <div className="text-center">
          <Users className="w-12 h-12 text-gray-400 mx-auto mb-4" />
          <h2 className="text-xl font-bold text-gray-900 mb-2">עסק לא נמצא</h2>
          <p className="text-gray-600 mb-4">העסק עם מזהה {businessId} לא נמצא במערכת</p>
          <button
            onClick={goBackToAdmin}
            className="bg-blue-600 text-white px-4 py-2 rounded-lg hover:bg-blue-700"
          >
            חזרה לדשבורד מנהל
          </button>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-gray-50 font-hebrew rtl">
      {/* Header */}
      <div className="bg-white shadow-sm border-b">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-6">
          <div className="flex items-center justify-between">
            <div className="flex items-center">
              <button
                onClick={goBackToAdmin}
                className="ml-4 p-2 text-gray-600 hover:text-gray-900 hover:bg-gray-100 rounded-lg transition-colors"
                title="חזרה לדשבורד מנהל"
              >
                <ArrowRight className="w-5 h-5" />
              </button>
              <div>
                <div className="flex items-center mb-1">
                  <Eye className="w-6 h-6 text-blue-600 ml-2" />
                  <h1 className="text-3xl font-bold text-gray-900">צפייה בעסק: {businessData.name}</h1>
                </div>
                <p className="text-gray-600">{formatHebrewDate()}</p>
                <div className="flex items-center mt-1">
                  <span className="text-sm text-gray-500 ml-2">סטטוס:</span>
                  <span className={`flex items-center ${getStatusColor(businessData.status)}`}>
                    <span className="ml-1">{getStatusIcon(businessData.status)}</span>
                    {businessData.status === 'active' ? 'פעיל' : 'לא פעיל'}
                  </span>
                </div>
              </div>
            </div>
            <div className="bg-yellow-50 border border-yellow-200 rounded-lg p-3">
              <p className="text-yellow-800 text-sm font-medium">מצב תצוגה בלבד</p>
              <p className="text-yellow-600 text-xs">אין אפשרות לשנות או לבצע פעולות</p>
            </div>
          </div>
        </div>
      </div>

      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
        {/* פרטי העסק */}
        <div className="bg-white rounded-xl shadow mb-8">
          <div className="p-6 border-b">
            <h2 className="text-xl font-bold text-gray-900">פרטי העסק</h2>
          </div>
          <div className="p-6">
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">שם העסק</label>
                <p className="text-gray-900 font-medium">{businessData.name}</p>
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">מזהה העסק</label>
                <p className="text-gray-600">{businessData.identifier}</p>
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">תאריך הצטרפות</label>
                <p className="text-gray-600">{businessData.created_at}</p>
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">טלפון עסק</label>
                <p className="text-gray-600" dir="ltr">{businessData.phone}</p>
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">WhatsApp עסקי</label>
                <p className="text-gray-600" dir="ltr">{businessData.whatsapp_phone || 'לא מוגדר'}</p>
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">נראה לאחרונה</label>
                <p className="text-gray-600">{businessData.lastActivity}</p>
              </div>
            </div>
          </div>
        </div>

        {/* סטטיסטיקות העסק */}
        <div className="grid grid-cols-1 md:grid-cols-4 gap-6 mb-8">
          <div className="bg-white p-6 rounded-xl shadow">
            <div className="flex items-center">
              <Phone className="w-8 h-8 text-blue-500" />
              <div className="mr-4">
                <p className="text-2xl font-bold text-gray-900">{stats.todayCalls}</p>
                <p className="text-gray-600">שיחות היום</p>
              </div>
            </div>
          </div>
          
          <div className="bg-white p-6 rounded-xl shadow">
            <div className="flex items-center">
              <Clock className="w-8 h-8 text-orange-500" />
              <div className="mr-4">
                <p className="text-2xl font-bold text-gray-900">{stats.pendingTasks}</p>
                <p className="text-gray-600">משימות ממתינות</p>
              </div>
            </div>
          </div>
          
          <div className="bg-white p-6 rounded-xl shadow">
            <div className="flex items-center">
              <Users className="w-8 h-8 text-green-500" />
              <div className="mr-4">
                <p className="text-2xl font-bold text-gray-900">{stats.activeCustomers}</p>
                <p className="text-gray-600">לקוחות פעילים</p>
              </div>
            </div>
          </div>
          
          <div className="bg-white p-6 rounded-xl shadow">
            <div className="flex items-center">
              <DollarSign className="w-8 h-8 text-purple-500" />
              <div className="mr-4">
                <p className="text-2xl font-bold text-gray-900">{formatCurrency(stats.todayRevenue)}</p>
                <p className="text-gray-600">הכנסות היום</p>
              </div>
            </div>
          </div>
        </div>

        {/* שירותים פעילים */}
        <div className="bg-white rounded-xl shadow mb-8">
          <div className="p-6 border-b">
            <h2 className="text-xl font-bold text-gray-900">שירותים של העסק</h2>
            <p className="text-gray-600 mt-1">השירותים המוגדרים עבור העסק</p>
          </div>
          <div className="p-6">
            <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
              {/* CRM */}
              <div className={`p-6 rounded-lg border ${
                businessData.services.crm 
                  ? 'bg-blue-50 border-blue-200' 
                  : 'bg-gray-50 border-gray-200'
              }`}>
                <div className="flex items-center justify-between mb-4">
                  <Users className={`w-8 h-8 ${
                    businessData.services.crm ? 'text-blue-600' : 'text-gray-400'
                  }`} />
                  <span className={`text-xs px-2 py-1 rounded-full ${
                    businessData.services.crm 
                      ? 'bg-green-100 text-green-800' 
                      : 'bg-red-100 text-red-800'
                  }`}>
                    {businessData.services.crm ? 'פעיל' : 'לא פעיל'}
                  </span>
                </div>
                <h3 className={`text-lg font-semibold mb-2 ${
                  businessData.services.crm ? 'text-blue-600' : 'text-gray-600'
                }`}>
                  📋 מערכת CRM
                </h3>
                <p className={`text-sm ${
                  businessData.services.crm ? 'text-blue-500' : 'text-gray-500'
                }`}>
                  ניהול לקוחות ומשימות
                </p>
              </div>

              {/* שיחות */}
              <div className={`p-6 rounded-lg border ${
                businessData.services.calls 
                  ? 'bg-green-50 border-green-200' 
                  : 'bg-gray-50 border-gray-200'
              }`}>
                <div className="flex items-center justify-between mb-4">
                  <Phone className={`w-8 h-8 ${
                    businessData.services.calls ? 'text-green-600' : 'text-gray-400'
                  }`} />
                  <span className={`text-xs px-2 py-1 rounded-full ${
                    businessData.services.calls 
                      ? 'bg-green-100 text-green-800' 
                      : 'bg-red-100 text-red-800'
                  }`}>
                    {businessData.services.calls ? 'פעיל' : 'לא פעיל'}
                  </span>
                </div>
                <h3 className={`text-lg font-semibold mb-2 ${
                  businessData.services.calls ? 'text-green-600' : 'text-gray-600'
                }`}>
                  📞 מערכת שיחות
                </h3>
                <p className={`text-sm ${
                  businessData.services.calls ? 'text-green-500' : 'text-gray-500'
                }`}>
                  שיחות AI והקלטות
                </p>
              </div>

              {/* WhatsApp */}
              <div className={`p-6 rounded-lg border ${
                businessData.services.whatsapp 
                  ? 'bg-purple-50 border-purple-200' 
                  : 'bg-gray-50 border-gray-200'
              }`}>
                <div className="flex items-center justify-between mb-4">
                  <MessageCircle className={`w-8 h-8 ${
                    businessData.services.whatsapp ? 'text-purple-600' : 'text-gray-400'
                  }`} />
                  <span className={`text-xs px-2 py-1 rounded-full ${
                    businessData.services.whatsapp 
                      ? 'bg-green-100 text-green-800' 
                      : 'bg-red-100 text-red-800'
                  }`}>
                    {businessData.services.whatsapp ? 'פעיל' : 'לא פעיל'}
                  </span>
                </div>
                <h3 className={`text-lg font-semibold mb-2 ${
                  businessData.services.whatsapp ? 'text-purple-600' : 'text-gray-600'
                }`}>
                  💬 WhatsApp עסקי
                </h3>
                <p className={`text-sm ${
                  businessData.services.whatsapp ? 'text-purple-500' : 'text-gray-500'
                }`}>
                  הודעות ושיחות עם לקוחות
                </p>
              </div>
            </div>
          </div>
        </div>

        {/* כפתור חזרה */}
        <div className="text-center">
          <button
            onClick={goBackToAdmin}
            className="bg-blue-600 text-white px-6 py-3 rounded-lg hover:bg-blue-700 flex items-center mx-auto transition-colors"
          >
            <ArrowRight className="w-5 h-5 ml-2" />
            חזרה לדשבורד מנהל
          </button>
        </div>
      </div>
    </div>
  );
};

export default BusinessViewPage;