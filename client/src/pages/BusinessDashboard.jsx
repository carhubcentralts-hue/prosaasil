import React, { useState, useEffect } from 'react';
import { Users, Phone, MessageCircle, Key, BarChart3, Clock, DollarSign } from 'lucide-react';

const BusinessDashboard = () => {
  const [businessData, setBusinessData] = useState(null);
  const [stats, setStats] = useState({
    todayCalls: 0,
    pendingTasks: 0,
    activeCustomers: 0,
    todayRevenue: 0
  });
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    // טוען נתוני העסק
    const fetchBusinessData = () => {
      // נתונים לדוגמה - בעתיד יגיעו מה-API
      const businessInfo = {
        name: 'טכנו סולושנס בע"מ',
        id: 1,
        services: {
          crm: true,
          calls: true,
          whatsapp: true
        },
        phone: '+972-33-763-8005',
        lastActivity: '2025-08-03 13:45'
      };
      
      const statsData = {
        todayCalls: 12,
        pendingTasks: 7,
        activeCustomers: 45,
        todayRevenue: 15750
      };
      
      setBusinessData(businessInfo);
      setStats(statsData);
      setLoading(false);
    };

    fetchBusinessData();
  }, []);

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

  const handleServiceNavigation = (service) => {
    console.log(`Navigation to: /business/${service}`);
    window.location.href = `/business/${service}`;
  };

  const handleChangePassword = () => {
    console.log('Change password for business');
    alert('שינוי סיסמה - יושם בעתיד');
  };

  const formatCurrency = (amount) => {
    return new Intl.NumberFormat('he-IL', {
      style: 'currency',
      currency: 'ILS'
    }).format(amount);
  };

  if (loading) {
    return (
      <div className="min-h-screen bg-gray-50 flex items-center justify-center">
        <div className="text-center">
          <BarChart3 className="w-8 h-8 text-blue-500 animate-spin mx-auto mb-4" />
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
          <h2 className="text-xl font-bold text-gray-900 mb-2">לא נמצאו נתוני עסק</h2>
          <p className="text-gray-600">אנא פנה למנהל המערכת</p>
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
            <div>
              <h1 className="text-3xl font-bold text-gray-900">שלום {businessData.name}</h1>
              <p className="text-gray-600 mt-1">{formatHebrewDate()}</p>
              <p className="text-sm text-gray-500">נראה לאחרונה: {businessData.lastActivity}</p>
            </div>
            <div className="flex items-center space-x-4 space-x-reverse">
              <button
                onClick={handleChangePassword}
                className="bg-yellow-600 text-white px-4 py-2 rounded-lg hover:bg-yellow-700 flex items-center transition-colors"
              >
                <Key className="w-4 h-4 ml-2" />
                שנה סיסמה
              </button>
              <button
                onClick={() => {
                  localStorage.removeItem('auth_token');
                  localStorage.removeItem('user_role');
                  window.location.reload();
                }}
                className="bg-red-600 text-white px-4 py-2 rounded-lg hover:bg-red-700 transition-colors"
              >
                יציאה מהמערכת
              </button>
            </div>
          </div>
        </div>
      </div>

      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
        {/* סטטיסטיקות יומיות */}
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
            <h2 className="text-xl font-bold text-gray-900">השירותים שלך</h2>
            <p className="text-gray-600 mt-1">השירותים הפעילים עבור העסק</p>
          </div>
          <div className="p-6">
            <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
              {/* CRM */}
              {businessData.services.crm && (
                <div className="bg-blue-50 p-6 rounded-lg border border-blue-200">
                  <div className="flex items-center justify-between mb-4">
                    <Users className="w-8 h-8 text-blue-600" />
                    <span className="bg-green-100 text-green-800 text-xs px-2 py-1 rounded-full">פעיל</span>
                  </div>
                  <h3 className="text-lg font-semibold text-blue-600 mb-2">📋 מערכת CRM</h3>
                  <p className="text-blue-500 text-sm mb-4">ניהול לקוחות ומשימות</p>
                  <button
                    onClick={() => handleServiceNavigation('crm')}
                    className="w-full bg-blue-600 text-white py-2 px-4 rounded-lg hover:bg-blue-700 transition-colors"
                  >
                    כניסה ל-CRM
                  </button>
                </div>
              )}

              {/* שיחות */}
              {businessData.services.calls && (
                <div className="bg-green-50 p-6 rounded-lg border border-green-200">
                  <div className="flex items-center justify-between mb-4">
                    <Phone className="w-8 h-8 text-green-600" />
                    <span className="bg-green-100 text-green-800 text-xs px-2 py-1 rounded-full">פעיל</span>
                  </div>
                  <h3 className="text-lg font-semibold text-green-600 mb-2">📞 מערכת שיחות</h3>
                  <p className="text-green-500 text-sm mb-4">שיחות AI והקלטות</p>
                  <button
                    onClick={() => handleServiceNavigation('calls')}
                    className="w-full bg-green-600 text-white py-2 px-4 rounded-lg hover:bg-green-700 transition-colors"
                  >
                    כניסה לשיחות
                  </button>
                </div>
              )}

              {/* WhatsApp */}
              {businessData.services.whatsapp && (
                <div className="bg-purple-50 p-6 rounded-lg border border-purple-200">
                  <div className="flex items-center justify-between mb-4">
                    <MessageCircle className="w-8 h-8 text-purple-600" />
                    <span className="bg-green-100 text-green-800 text-xs px-2 py-1 rounded-full">פעיל</span>
                  </div>
                  <h3 className="text-lg font-semibold text-purple-600 mb-2">💬 WhatsApp עסקי</h3>
                  <p className="text-purple-500 text-sm mb-4">הודעות ושיחות עם לקוחות</p>
                  <button
                    onClick={() => handleServiceNavigation('whatsapp')}
                    className="w-full bg-purple-600 text-white py-2 px-4 rounded-lg hover:bg-purple-700 transition-colors"
                  >
                    כניסה ל-WhatsApp
                  </button>
                </div>
              )}
            </div>

            {/* הודעה אם אין שירותים פעילים */}
            {!businessData.services.crm && !businessData.services.calls && !businessData.services.whatsapp && (
              <div className="text-center py-8">
                <Users className="w-12 h-12 text-gray-400 mx-auto mb-4" />
                <h3 className="text-lg font-medium text-gray-900 mb-2">אין שירותים פעילים</h3>
                <p className="text-gray-600">פנה למנהל המערכת להפעלת שירותים</p>
              </div>
            )}
          </div>
        </div>

        {/* פעולות מהירות */}
        <div className="bg-white rounded-xl shadow">
          <div className="p-6 border-b">
            <h2 className="text-xl font-bold text-gray-900">פעולות מהירות</h2>
            <p className="text-gray-600 mt-1">פעולות נפוצות ושימושיות</p>
          </div>
          <div className="p-6">
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
              <button
                onClick={() => handleServiceNavigation('crm')}
                className="flex items-center p-4 bg-gray-50 hover:bg-gray-100 rounded-lg transition-colors"
                disabled={!businessData.services.crm}
              >
                <Users className="w-6 h-6 text-blue-600 ml-3" />
                <div className="text-right">
                  <p className="font-medium text-gray-900">הוסף לקוח חדש</p>
                  <p className="text-sm text-gray-600">CRM</p>
                </div>
              </button>

              <button
                onClick={() => handleServiceNavigation('calls')}
                className="flex items-center p-4 bg-gray-50 hover:bg-gray-100 rounded-lg transition-colors"
                disabled={!businessData.services.calls}
              >
                <Phone className="w-6 h-6 text-green-600 ml-3" />
                <div className="text-right">
                  <p className="font-medium text-gray-900">צפה בשיחות</p>
                  <p className="text-sm text-gray-600">שיחות</p>
                </div>
              </button>

              <button
                onClick={() => handleServiceNavigation('whatsapp')}
                className="flex items-center p-4 bg-gray-50 hover:bg-gray-100 rounded-lg transition-colors"
                disabled={!businessData.services.whatsapp}
              >
                <MessageCircle className="w-6 h-6 text-purple-600 ml-3" />
                <div className="text-right">
                  <p className="font-medium text-gray-900">שלח הודעה</p>
                  <p className="text-sm text-gray-600">WhatsApp</p>
                </div>
              </button>

              <button
                onClick={handleChangePassword}
                className="flex items-center p-4 bg-gray-50 hover:bg-gray-100 rounded-lg transition-colors"
              >
                <Key className="w-6 h-6 text-yellow-600 ml-3" />
                <div className="text-right">
                  <p className="font-medium text-gray-900">שנה סיסמה</p>
                  <p className="text-sm text-gray-600">אבטחה</p>
                </div>
              </button>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};

export default BusinessDashboard;