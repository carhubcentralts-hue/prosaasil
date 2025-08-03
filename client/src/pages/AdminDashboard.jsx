import React, { useState, useEffect } from 'react';
import { Settings, Users, Phone, MessageCircle, Eye, Edit, Key, Plus, Activity } from 'lucide-react';

const AdminDashboard = () => {
  // נתונים קבועים (בעתיד יבואו מה-API)
  const stats = {
    totalBusinesses: 3,
    activeUsers: 8,
    activeConnections: 3,
    totalCalls: 47
  };
  
  const businesses = [
    {
      id: 1,
      name: 'טכנו סולושנס בע"מ',
      identifier: 'techno-solutions',
      services: { crm: true, calls: true, whatsapp: true },
      status: 'active',
      lastSeen: '2025-08-03 13:15'
    },
    {
      id: 2,
      name: 'חברת השיווק הדיגיטלי',
      identifier: 'digital-marketing',
      services: { crm: true, calls: false, whatsapp: true },
      status: 'active',
      lastSeen: '2025-08-03 12:30'
    },
    {
      id: 3,
      name: 'פתרונות עסקיים',
      identifier: 'business-solutions',
      services: { crm: false, calls: true, whatsapp: false },
      status: 'inactive',
      lastSeen: '2025-08-02 16:45'
    }
  ];

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

  const handleSystemAction = (system) => {
    console.log(`Navigation to: /admin/${system}`);
    alert(`ניווט ל${system} - יושם בעתיד`);
  };

  const handleBusinessView = (businessId) => {
    console.log(`View business: ${businessId}`);
    window.location.href = `/admin/business/${businessId}/view`;
  };

  const handleEditBusiness = (businessId) => {
    console.log(`Edit business: ${businessId}`);
    alert(`עריכת עסק ${businessId} - יושם בעתיד`);
  };

  const handleChangePassword = (businessId) => {
    console.log(`Change password for business: ${businessId}`);
    alert(`שינוי סיסמה לעסק ${businessId} - יושם בעתיד`);
  };

  const handleAddBusiness = () => {
    console.log('Add new business');
    alert('הוספת עסק חדש - יושם בעתיד');
  };

  const getStatusColor = (status) => {
    return status === 'active' ? 'text-green-600' : 'text-red-600';
  };

  const getStatusIcon = (status) => {
    return status === 'active' ? '🟢' : '🔴';
  };

  return (
    <div className="min-h-screen bg-gray-50 font-hebrew rtl">
      {/* Header */}
      <div className="bg-white shadow-sm border-b">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-6">
          <div className="flex items-center justify-between">
            <div>
              <h1 className="text-3xl font-bold text-gray-900">ברוך הבא למערכת Agent Locator - מערכת CRM מתקדמת</h1>
              <p className="text-gray-600 mt-1">{formatHebrewDate()}</p>
            </div>
            <div className="flex items-center space-x-4 space-x-reverse">
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
        {/* סטטיסטיקות מערכת */}
        <div className="grid grid-cols-1 md:grid-cols-4 gap-6 mb-8">
          <div className="bg-white p-6 rounded-xl shadow">
            <div className="flex items-center">
              <Users className="w-8 h-8 text-blue-500" />
              <div className="mr-4">
                <p className="text-2xl font-bold text-gray-900">{stats.totalBusinesses}</p>
                <p className="text-gray-600">עסקים פעילים</p>
              </div>
            </div>
          </div>
          
          <div className="bg-white p-6 rounded-xl shadow">
            <div className="flex items-center">
              <Activity className="w-8 h-8 text-green-500" />
              <div className="mr-4">
                <p className="text-2xl font-bold text-gray-900">{stats.activeUsers}</p>
                <p className="text-gray-600">משתמשים</p>
              </div>
            </div>
          </div>
          
          <div className="bg-white p-6 rounded-xl shadow">
            <div className="flex items-center">
              <Settings className="w-8 h-8 text-purple-500" />
              <div className="mr-4">
                <p className="text-2xl font-bold text-gray-900">{stats.activeConnections}</p>
                <p className="text-gray-600">חיבורים פעילים</p>
              </div>
            </div>
          </div>
          
          <div className="bg-white p-6 rounded-xl shadow">
            <div className="flex items-center">
              <Phone className="w-8 h-8 text-orange-500" />
              <div className="mr-4">
                <p className="text-2xl font-bold text-gray-900">{stats.totalCalls}</p>
                <p className="text-gray-600">שיחות היום</p>
              </div>
            </div>
          </div>
        </div>

        {/* גישה למערכות הכלליות */}
        <div className="bg-white rounded-xl shadow mb-8">
          <div className="p-6 border-b">
            <h2 className="text-xl font-bold text-gray-900">גישה למערכות הכלליות</h2>
          </div>
          <div className="p-6">
            <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
              <button
                onClick={() => handleSystemAction('crm')}
                className="flex flex-col items-center p-6 bg-blue-50 hover:bg-blue-100 rounded-lg transition-colors border border-blue-200"
              >
                <Users className="w-8 h-8 text-blue-600 mb-2" />
                <span className="text-blue-600 font-medium">📋 CRM ראשי</span>
                <span className="text-xs text-blue-500">כל העסקים</span>
              </button>
              
              <button
                onClick={() => handleSystemAction('calls')}
                className="flex flex-col items-center p-6 bg-green-50 hover:bg-green-100 rounded-lg transition-colors border border-green-200"
              >
                <Phone className="w-8 h-8 text-green-600 mb-2" />
                <span className="text-green-600 font-medium">📞 כל השיחות</span>
                <span className="text-xs text-green-500">מערכת כללית</span>
              </button>
              
              <button
                onClick={() => handleSystemAction('whatsapp')}
                className="flex flex-col items-center p-6 bg-purple-50 hover:bg-purple-100 rounded-lg transition-colors border border-purple-200"
              >
                <MessageCircle className="w-8 h-8 text-purple-600 mb-2" />
                <span className="text-purple-600 font-medium">💬 WhatsApp כלל־מערכתי</span>
                <span className="text-xs text-purple-500">כל העסקים</span>
              </button>
            </div>
          </div>
        </div>

        {/* ניהול עסקים */}
        <div className="bg-white rounded-xl shadow">
          <div className="p-6 border-b flex items-center justify-between">
            <h2 className="text-xl font-bold text-gray-900">ניהול עסקים</h2>
            <button
              onClick={handleAddBusiness}
              className="bg-blue-600 text-white px-4 py-2 rounded-lg hover:bg-blue-700 flex items-center transition-colors"
            >
              <Plus className="w-5 h-5 ml-2" />
              הוסף עסק
            </button>
          </div>
          <div className="p-6">
            <div className="overflow-x-auto">
              <table className="min-w-full divide-y divide-gray-200">
                <thead className="bg-gray-50">
                  <tr>
                    <th className="px-6 py-3 text-right text-xs font-medium text-gray-500 uppercase tracking-wider">
                      שם העסק
                    </th>
                    <th className="px-6 py-3 text-right text-xs font-medium text-gray-500 uppercase tracking-wider">
                      מזהה
                    </th>
                    <th className="px-6 py-3 text-right text-xs font-medium text-gray-500 uppercase tracking-wider">
                      שירותים פעילים
                    </th>
                    <th className="px-6 py-3 text-right text-xs font-medium text-gray-500 uppercase tracking-wider">
                      סטטוס
                    </th>
                    <th className="px-6 py-3 text-right text-xs font-medium text-gray-500 uppercase tracking-wider">
                      נראה לאחרונה
                    </th>
                    <th className="px-6 py-3 text-right text-xs font-medium text-gray-500 uppercase tracking-wider">
                      פעולות
                    </th>
                  </tr>
                </thead>
                <tbody className="bg-white divide-y divide-gray-200">
                  {businesses.map((business) => (
                    <tr key={business.id} className="hover:bg-gray-50">
                      <td className="px-6 py-4 whitespace-nowrap">
                        <div className="text-sm font-medium text-gray-900">{business.name}</div>
                      </td>
                      <td className="px-6 py-4 whitespace-nowrap">
                        <div className="text-sm text-gray-600">{business.identifier}</div>
                      </td>
                      <td className="px-6 py-4 whitespace-nowrap">
                        <div className="flex space-x-2 space-x-reverse">
                          {business.services.crm && (
                            <span className="inline-flex px-2 py-1 text-xs font-semibold rounded-full bg-blue-100 text-blue-800">
                              CRM
                            </span>
                          )}
                          {business.services.calls && (
                            <span className="inline-flex px-2 py-1 text-xs font-semibold rounded-full bg-green-100 text-green-800">
                              שיחות
                            </span>
                          )}
                          {business.services.whatsapp && (
                            <span className="inline-flex px-2 py-1 text-xs font-semibold rounded-full bg-purple-100 text-purple-800">
                              WhatsApp
                            </span>
                          )}
                        </div>
                      </td>
                      <td className="px-6 py-4 whitespace-nowrap">
                        <span className={`flex items-center ${getStatusColor(business.status)}`}>
                          <span className="ml-2">{getStatusIcon(business.status)}</span>
                          {business.status === 'active' ? 'פעיל' : 'לא פעיל'}
                        </span>
                      </td>
                      <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-600">
                        {business.lastSeen}
                      </td>
                      <td className="px-6 py-4 whitespace-nowrap text-sm font-medium">
                        <div className="flex space-x-2 space-x-reverse">
                          <button
                            onClick={() => handleBusinessView(business.id)}
                            className="text-blue-600 hover:text-blue-900 p-1 rounded"
                            title="צפה בעסק"
                          >
                            <Eye className="w-4 h-4" />
                          </button>
                          <button
                            onClick={() => handleEditBusiness(business.id)}
                            className="text-yellow-600 hover:text-yellow-900 p-1 rounded"
                            title="ערוך עסק"
                          >
                            <Edit className="w-4 h-4" />
                          </button>
                          <button
                            onClick={() => handleChangePassword(business.id)}
                            className="text-green-600 hover:text-green-900 p-1 rounded"
                            title="שנה סיסמה"
                          >
                            <Key className="w-4 h-4" />
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
    </div>
  );
};

export default AdminDashboard;