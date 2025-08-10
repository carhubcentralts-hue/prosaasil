import React, { useState } from 'react';
import { useAuth } from '../contexts/AuthContext';
import { 
  Shield, 
  LogOut, 
  Phone, 
  MessageSquare, 
  Users, 
  Building, 
  Settings,
  Activity,
  BarChart3,
  Crown,
  Eye,
  UserCheck
} from 'lucide-react';

const AdminDashboard = () => {
  const { user, logout } = useAuth();
  const [selectedBusiness, setSelectedBusiness] = useState(null);

  const businesses = [
    {
      id: 1,
      name: 'שי דירות ומשרדים בע״מ',
      hebrewName: 'שי דירות ומשרדים בע״מ',
      type: 'נדל"ן ותיווך',
      phone: '+972-3-555-7777',
      whatsapp: '+1-555-123-4567',
      status: 'פעיל',
      totalCalls: 127,
      totalContacts: 45,
      lastActivity: 'לפני 2 שעות'
    }
  ];

  const systemModules = [
    {
      id: 'crm',
      name: 'מערכת CRM',
      icon: Users,
      description: 'ניהול לקוחות ורכישות',
      adminDescription: 'צפייה בכל הלקוחות של כל העסקים',
      color: 'bg-blue-500 hover:bg-blue-600',
      stats: 'כל הלקוחות: 1,247'
    },
    {
      id: 'calls',
      name: 'מערכת שיחות',
      icon: Phone,
      description: 'ניהול שיחות וטלפוניה',
      adminDescription: 'צפייה בכל השיחות של כל העסקים',
      color: 'bg-green-500 hover:bg-green-600',
      stats: 'כל השיחות: 3,891'
    },
    {
      id: 'whatsapp',
      name: 'מערכת WhatsApp',
      icon: MessageSquare,
      description: 'ניהול הודעות WhatsApp',
      adminDescription: 'צפייה בכל הודעות WhatsApp של כל העסקים',
      color: 'bg-purple-500 hover:bg-purple-600',
      stats: 'כל ההודעות: 567'
    }
  ];

  const handleSystemAccess = (systemId, systemName) => {
    alert(`כניסה למערכת ${systemName} - תצוגת מנהל\nרואה את כל הנתונים של כל העסקים`);
  };

  const handleTakeControl = (businessId, businessName) => {
    alert(`השתלטות על עסק: ${businessName}\nעכשיו אתה פועל בתפקיד העסק`);
  };

  const handleLogout = () => {
    logout();
  };

  return (
    <div className="min-h-screen bg-gradient-to-br from-gray-50 to-blue-50">
      {/* Header */}
      <header className="bg-white shadow-lg border-b border-gray-200">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="flex justify-between items-center h-16">
            <div className="flex items-center space-x-4">
              <div className="flex items-center space-x-3">
                <div className="p-2 bg-gradient-to-r from-red-500 to-pink-500 rounded-lg shadow-lg">
                  <Crown className="w-6 h-6 text-white" />
                </div>
                <div className="text-right">
                  <h1 className="text-xl font-bold text-gray-800">לוח בקרה מנהל</h1>
                  <p className="text-sm text-gray-600">גישה מלאה לכל המערכות</p>
                </div>
              </div>
            </div>
            
            <div className="flex items-center space-x-4">
              <div className="text-right">
                <p className="text-sm font-semibold text-gray-700">{user?.email}</p>
                <p className="text-xs text-gray-500">מנהל מערכת</p>
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
        {/* Stats Overview */}
        <div className="grid grid-cols-1 md:grid-cols-4 gap-6 mb-8">
          {[
            { title: 'סה"כ עסקים', value: '1', icon: Building, color: 'bg-blue-500' },
            { title: 'סה"כ שיחות', value: '3,891', icon: Phone, color: 'bg-green-500' },
            { title: 'סה"כ לקוחות', value: '1,247', icon: Users, color: 'bg-purple-500' },
            { title: 'הודעות WhatsApp', value: '567', icon: MessageSquare, color: 'bg-pink-500' }
          ].map((stat, index) => (
            <div key={index} className="bg-white rounded-xl shadow-lg p-6 hover-lift animate-fade-in-up" style={{ animationDelay: `${index * 100}ms` }}>
              <div className="flex items-center justify-between">
                <div className="text-right">
                  <p className="text-sm font-medium text-gray-600">{stat.title}</p>
                  <p className="text-2xl font-bold text-gray-900">{stat.value}</p>
                </div>
                <div className={`p-3 rounded-lg ${stat.color}`}>
                  <stat.icon className="w-6 h-6 text-white" />
                </div>
              </div>
            </div>
          ))}
        </div>

        {/* Businesses Management */}
        <div className="bg-white rounded-xl shadow-lg p-6 mb-8 animate-slide-in-right">
          <h2 className="text-xl font-bold text-gray-800 mb-4 flex items-center">
            <Building className="w-5 h-5 ml-2 text-blue-500" />
            ניהול עסקים
          </h2>
          
          <div className="space-y-4">
            {businesses.map((business) => (
              <div key={business.id} className="border border-gray-200 rounded-lg p-4 hover:shadow-md transition-all duration-200">
                <div className="flex items-center justify-between">
                  <div className="text-right flex-1">
                    <h3 className="text-lg font-semibold text-gray-800">{business.name}</h3>
                    <p className="text-sm text-gray-600">סוג עסק: {business.type}</p>
                    <div className="flex items-center space-x-4 mt-2 text-sm text-gray-500">
                      <span>📞 {business.phone}</span>
                      <span>💬 {business.whatsapp}</span>
                      <span className="text-green-600 font-semibold">{business.status}</span>
                    </div>
                    <div className="flex items-center space-x-4 mt-1 text-xs text-gray-400">
                      <span>שיחות: {business.totalCalls}</span>
                      <span>אנשי קשר: {business.totalContacts}</span>
                      <span>פעילות אחרונה: {business.lastActivity}</span>
                    </div>
                  </div>
                  
                  <div className="flex items-center space-x-2">
                    <button
                      onClick={() => handleTakeControl(business.id, business.name)}
                      className="flex items-center space-x-2 px-4 py-2 bg-orange-500 text-white rounded-lg hover:bg-orange-600 transition-colors duration-200 shadow-md"
                    >
                      <UserCheck className="w-4 h-4" />
                      <span>השתלטות</span>
                    </button>
                    
                    <button className="flex items-center space-x-2 px-4 py-2 bg-gray-500 text-white rounded-lg hover:bg-gray-600 transition-colors duration-200">
                      <Eye className="w-4 h-4" />
                      <span>צפייה</span>
                    </button>
                  </div>
                </div>
              </div>
            ))}
          </div>
        </div>

        {/* System Modules */}
        <div className="bg-white rounded-xl shadow-lg p-6 animate-slide-in-left">
          <h2 className="text-xl font-bold text-gray-800 mb-6 flex items-center">
            <Shield className="w-5 h-5 ml-2 text-purple-500" />
            מערכות המערכת - תצוגת מנהל
          </h2>
          
          <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
            {systemModules.map((module, index) => (
              <div key={module.id} className="border border-gray-200 rounded-lg p-6 hover:shadow-lg transition-all duration-300 hover-lift animate-fade-in-up" style={{ animationDelay: `${index * 200}ms` }}>
                <div className="text-center">
                  <div className={`inline-flex items-center justify-center w-16 h-16 ${module.color} rounded-full mb-4 shadow-lg`}>
                    <module.icon className="w-8 h-8 text-white" />
                  </div>
                  
                  <h3 className="text-lg font-semibold text-gray-800 mb-2">{module.name}</h3>
                  <p className="text-sm text-gray-600 mb-4">{module.adminDescription}</p>
                  
                  <div className="bg-gray-50 rounded-lg p-3 mb-4">
                    <p className="text-xs text-gray-500 font-semibold">{module.stats}</p>
                  </div>
                  
                  <button
                    onClick={() => handleSystemAccess(module.id, module.name)}
                    className={`w-full ${module.color} text-white py-3 rounded-lg font-semibold transition-all duration-200 shadow-md hover:shadow-lg`}
                  >
                    כניסה למערכת
                  </button>
                  
                  <p className="text-xs text-gray-500 mt-2">
                    ⚠️ תצוגת מנהל - רואה הכל
                  </p>
                </div>
              </div>
            ))}
          </div>
        </div>

        {/* Admin Notice */}
        <div className="mt-8 bg-gradient-to-r from-red-500 to-pink-500 rounded-xl shadow-lg p-6 text-white">
          <div className="flex items-center justify-center">
            <Crown className="w-6 h-6 ml-3" />
            <h3 className="text-lg font-bold">מצב מנהל מערכת</h3>
          </div>
          <p className="text-center mt-2 opacity-90">
            יש לך גישה מלאה לכל הנתונים של כל העסקים במערכת. 
            השתמש בהרשאות האלה באחריות.
          </p>
        </div>
      </main>
    </div>
  );
};

export default AdminDashboard;