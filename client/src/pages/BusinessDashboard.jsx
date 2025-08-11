import React, { useState } from 'react';
import { useAuth } from '../contexts/AuthContext';
// Simple icons without lucide-react dependency
const IconBuilding = () => <span>🏢</span>;
const IconLogOut = () => <span>⇐</span>;
const IconPhone = () => <span>📞</span>;
const IconMessage = () => <span>💬</span>;
const IconUsers = () => <span>👥</span>;
const IconHome = () => <span>🏠</span>;
const IconActivity = () => <span>📊</span>;
const IconChart = () => <span>📈</span>;
const IconLock = () => <span>🔒</span>;

const BusinessDashboard = () => {
  const { user, logout } = useAuth();

  const businessInfo = {
    name: 'שי דירות ומשרדים בע״מ',
    hebrewName: 'שי דירות ומשרדים בע״מ',
    type: 'נדל"ן ותיווך',
    phone: '+972-3-555-7777',
    whatsapp: '+1-555-123-4567',
    status: 'פעיל',
    totalCalls: 127,
    totalContacts: 45,
    lastActivity: 'פעיל עכשיו'
  };

  const systemModules = [
    {
      id: 'crm',
      name: 'מערכת CRM שלי',
      icon: IconUsers,
      description: 'ניהול הלקוחות שלי',
      businessDescription: 'רק הלקוחות של שי דירות',
      color: 'bg-blue-500 hover:bg-blue-600',
      stats: `הלקוחות שלי: ${businessInfo.totalContacts}`,
      restricted: false
    },
    {
      id: 'calls',
      name: 'שיחות שלי',
      icon: IconPhone,
      description: 'השיחות של העסק שלי',
      businessDescription: 'רק השיחות של שי דירות',
      color: 'bg-green-500 hover:bg-green-600',
      stats: `השיחות שלי: ${businessInfo.totalCalls}`,
      restricted: false
    },
    {
      id: 'whatsapp',
      name: 'WhatsApp שלי',
      icon: IconMessage,
      description: 'הודעות WhatsApp שלי',
      businessDescription: 'רק הודעות WhatsApp של שי דירות',
      color: 'bg-purple-500 hover:bg-purple-600',
      stats: 'ההודעות שלי: 23',
      restricted: false
    }
  ];

  const handleSystemAccess = (systemId, systemName) => {
    alert(`כניסה למערכת ${systemName} - תצוגת עסק\nרואה רק את הנתונים של ${businessInfo.name}`);
  };

  const handleLogout = () => {
    logout();
  };

  return (
    <div className="min-h-screen bg-gradient-to-br from-blue-50 to-green-50">
      {/* Header */}
      <header className="bg-white shadow-lg border-b border-gray-200">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="flex justify-between items-center h-16">
            <div className="flex items-center space-x-4">
              <div className="flex items-center space-x-3">
                <div className="p-2 bg-gradient-to-r from-blue-500 to-green-500 rounded-lg shadow-lg">
                  <Building className="w-6 h-6 text-white" />
                </div>
                <div className="text-right">
                  <h1 className="text-xl font-bold text-gray-800">{businessInfo.name}</h1>
                  <p className="text-sm text-gray-600">דשבורד העסק שלי</p>
                </div>
              </div>
            </div>
            
            <div className="flex items-center space-x-4">
              <div className="text-right">
                <p className="text-sm font-semibold text-gray-700">{user?.email}</p>
                <p className="text-xs text-gray-500">בעל עסק</p>
              </div>
              <button
                onClick={handleLogout}
                className="flex items-center space-x-2 px-4 py-2 bg-red-500 text-white rounded-lg hover:bg-red-600 transition-colors duration-200 shadow-md"
              >
                <LogOut className="w-4 h-4" />
                <span>יציאה</span>
              </button>
            </div>
          </div>
        </div>
      </header>

      {/* Content */}
      <main className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
        {/* Welcome Section */}
        <div className="bg-gradient-to-r from-blue-500 to-green-500 rounded-xl shadow-lg p-6 text-white mb-8 animate-fade-in-up">
          <div className="text-center">
            <Home className="w-12 h-12 mx-auto mb-4" />
            <h2 className="text-2xl font-bold mb-2">ברוכים הבאים לדשבורד העסק שלכם</h2>
            <p className="opacity-90">
              אתם רואים ומנהלים רק את הנתונים של {businessInfo.name}
            </p>
          </div>
        </div>

        {/* Business Info */}
        <div className="bg-white rounded-xl shadow-lg p-6 mb-8 animate-slide-in-right">
          <h3 className="text-xl font-bold text-gray-800 mb-4 flex items-center">
            <Building className="w-5 h-5 ml-2 text-blue-500" />
            פרטי העסק
          </h3>
          
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
            <div className="text-center p-4 bg-gray-50 rounded-lg">
              <p className="text-sm text-gray-600">שם העסק</p>
              <p className="font-semibold text-gray-800">{businessInfo.name}</p>
            </div>
            
            <div className="text-center p-4 bg-gray-50 rounded-lg">
              <p className="text-sm text-gray-600">סוג עסק</p>
              <p className="font-semibold text-gray-800">{businessInfo.type}</p>
            </div>
            
            <div className="text-center p-4 bg-gray-50 rounded-lg">
              <p className="text-sm text-gray-600">טלפון</p>
              <p className="font-semibold text-gray-800">{businessInfo.phone}</p>
            </div>
            
            <div className="text-center p-4 bg-gray-50 rounded-lg">
              <p className="text-sm text-gray-600">WhatsApp</p>
              <p className="font-semibold text-gray-800">{businessInfo.whatsapp}</p>
            </div>
          </div>
        </div>

        {/* Stats Overview */}
        <div className="grid grid-cols-1 md:grid-cols-3 gap-6 mb-8">
          {[
            { title: 'השיחות שלי', value: businessInfo.totalCalls, icon: Phone, color: 'bg-green-500' },
            { title: 'הלקוחות שלי', value: businessInfo.totalContacts, icon: Users, color: 'bg-blue-500' },
            { title: 'הודעות WhatsApp', value: '23', icon: MessageSquare, color: 'bg-purple-500' }
          ].map((stat, index) => (
            <div key={index} className="bg-white rounded-xl shadow-lg p-6 hover-lift animate-fade-in-up" style={{ animationDelay: `${index * 100}ms` }}>
              <div className="flex items-center justify-between">
                <div className="text-right">
                  <p className="text-sm font-medium text-gray-600">{stat.title}</p>
                  <p className="text-3xl font-bold text-gray-900">{stat.value}</p>
                </div>
                <div className={`p-3 rounded-lg ${stat.color}`}>
                  <stat.icon className="w-8 h-8 text-white" />
                </div>
              </div>
            </div>
          ))}
        </div>

        {/* System Modules */}
        <div className="bg-white rounded-xl shadow-lg p-6 animate-slide-in-left">
          <h2 className="text-xl font-bold text-gray-800 mb-6 flex items-center">
            <Activity className="w-5 h-5 ml-2 text-green-500" />
            המערכות שלי
          </h2>
          
          <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
            {systemModules.map((module, index) => (
              <div key={module.id} className="border border-gray-200 rounded-lg p-6 hover:shadow-lg transition-all duration-300 hover-lift animate-fade-in-up" style={{ animationDelay: `${index * 200}ms` }}>
                <div className="text-center">
                  <div className={`inline-flex items-center justify-center w-16 h-16 ${module.color} rounded-full mb-4 shadow-lg`}>
                    <module.icon className="w-8 h-8 text-white" />
                  </div>
                  
                  <h3 className="text-lg font-semibold text-gray-800 mb-2">{module.name}</h3>
                  <p className="text-sm text-gray-600 mb-4">{module.businessDescription}</p>
                  
                  <div className="bg-blue-50 rounded-lg p-3 mb-4">
                    <p className="text-xs text-blue-600 font-semibold">{module.stats}</p>
                  </div>
                  
                  <button
                    onClick={() => handleSystemAccess(module.id, module.name)}
                    className={`w-full ${module.color} text-white py-3 rounded-lg font-semibold transition-all duration-200 shadow-md hover:shadow-lg`}
                  >
                    כניסה למערכת
                  </button>
                  
                  <p className="text-xs text-green-600 mt-2">
                    ✓ הנתונים שלי בלבד
                  </p>
                </div>
              </div>
            ))}
          </div>
        </div>

        {/* Business Notice */}
        <div className="mt-8 bg-gradient-to-r from-green-500 to-blue-500 rounded-xl shadow-lg p-6 text-white">
          <div className="flex items-center justify-center">
            <Lock className="w-6 h-6 ml-3" />
            <h3 className="text-lg font-bold">מצב עסק פרטי</h3>
          </div>
          <p className="text-center mt-2 opacity-90">
            אתם רואים ומנהלים רק את הנתונים של {businessInfo.name}. 
            בטיחות המידע והפרטיות מובטחות.
          </p>
        </div>
      </main>
    </div>
  );
};

export default BusinessDashboard;