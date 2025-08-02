import React, { useState, useEffect } from 'react';
import axios from 'axios';
import { 
  ArrowLeft,
  Phone, 
  MessageCircle, 
  Users, 
  FileText, 
  CheckCircle, 
  XCircle,
  TrendingUp,
  Calendar,
  DollarSign,
  Activity,
  Settings,
  AlertCircle,
  Building2
} from 'lucide-react';

// כרטיס סטטיסטיקה
const StatCard = ({ title, value, icon: Icon, trend, color = "blue" }) => {
  const colorClasses = {
    blue: "bg-blue-50 border-blue-200 text-blue-700",
    green: "bg-green-50 border-green-200 text-green-700", 
    purple: "bg-purple-50 border-purple-200 text-purple-700",
    orange: "bg-orange-50 border-orange-200 text-orange-700"
  };

  return (
    <div className={`p-6 rounded-lg border-2 ${colorClasses[color]} transition-all hover:shadow-lg`}>
      <div className="flex items-center justify-between">
        <div>
          <p className="text-sm font-medium opacity-75">{title}</p>
          <p className="text-2xl font-bold mt-1">{value}</p>
          {trend && (
            <div className="flex items-center mt-2 text-sm">
              <TrendingUp className="w-4 h-4 ml-1" />
              <span>{trend}</span>
            </div>
          )}
        </div>
        <Icon className="w-8 h-8 opacity-75" />
      </div>
    </div>
  );
};

// כפתור פעולה מהירה
const QuickActionButton = ({ title, icon: Icon, onClick, color = "primary", disabled = false }) => {
  const colorClasses = {
    primary: "bg-blue-600 hover:bg-blue-700 text-white",
    green: "bg-green-600 hover:bg-green-700 text-white",
    purple: "bg-purple-600 hover:bg-purple-700 text-white",
    orange: "bg-orange-600 hover:bg-orange-700 text-white",
    gray: "bg-gray-400 text-gray-600 cursor-not-allowed"
  };

  return (
    <button
      onClick={!disabled ? onClick : undefined}
      disabled={disabled}
      className={`p-4 rounded-lg transition-all flex flex-col items-center justify-center space-y-2 ${
        disabled ? colorClasses.gray : colorClasses[color]
      }`}
    >
      <Icon className="w-6 h-6" />
      <span className="text-sm font-medium">{title}</span>
      {disabled && <span className="text-xs opacity-75">לא זמין</span>}
    </button>
  );
};

const BusinessViewPage = () => {
  const [business, setBusiness] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  // קבלת ID מה-URL
  const businessId = window.location.pathname.split('/')[2];

  useEffect(() => {
    fetchBusiness();
  }, [businessId]);

  const fetchBusiness = async () => {
    try {
      const response = await axios.get(`/api/admin/businesses/${businessId}`);
      setBusiness(response.data);
    } catch (error) {
      console.error('Error fetching business:', error);
      setError('שגיאה בטעינת נתוני העסק');
    } finally {
      setLoading(false);
    }
  };

  const handleQuickAction = (action) => {
    console.log(`Action: ${action} for business:`, business.name);
    alert(`פעולה: ${action} - ${business.name}`);
  };

  const goBackToAdmin = () => {
    window.location.href = '/?role=admin';
  };

  if (loading) {
    return (
      <div className="min-h-screen bg-gray-50 flex items-center justify-center">
        <div className="text-center">
          <Settings className="w-8 h-8 text-blue-500 animate-spin mx-auto mb-4" />
          <p className="text-gray-600 font-hebrew">טוען נתוני עסק...</p>
        </div>
      </div>
    );
  }

  if (error || !business) {
    return (
      <div className="min-h-screen bg-gray-50 flex items-center justify-center">
        <div className="text-center">
          <AlertCircle className="w-12 h-12 text-red-500 mx-auto mb-4" />
          <p className="text-red-600 font-hebrew text-lg mb-4">{error || 'עסק לא נמצא'}</p>
          <button
            onClick={goBackToAdmin}
            className="bg-blue-600 text-white px-4 py-2 rounded-lg hover:bg-blue-700"
          >
            חזור לפאנל מנהל
          </button>
        </div>
      </div>
    );
  }

  // חישוב הרשאות פעילות
  const hasPermissions = business.services || {};
  const activeSystems = Object.values(hasPermissions).filter(Boolean).length;

  return (
    <div className="min-h-screen bg-gray-50 font-hebrew rtl">
      {/* Header */}
      <div className="bg-white shadow-sm border-b">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-6">
          <div className="flex items-center justify-between">
            <div className="flex items-center">
              <button
                onClick={goBackToAdmin}
                className="flex items-center px-3 py-2 text-gray-600 hover:bg-gray-100 rounded-lg transition-colors ml-4"
              >
                <ArrowLeft className="w-5 h-5 ml-2" />
                <span>חזור לפאנל מנהל</span>
              </button>
              <div>
                <h1 className="text-3xl font-bold text-gray-900">
                  {business.name}
                </h1>
                <p className="text-gray-500 mt-1">{business.type || 'עסק כללי'}</p>
              </div>
            </div>
            <div className="flex items-center space-x-4 space-x-reverse">
              <div className="text-center">
                <p className="text-sm text-gray-500">מערכות פעילות</p>
                <p className="text-2xl font-bold text-blue-600">{activeSystems}/3</p>
              </div>
              <Building2 className="w-12 h-12 text-gray-400" />
            </div>
          </div>
        </div>
      </div>

      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
        {/* Business Info Cards */}
        <div className="grid grid-cols-1 md:grid-cols-3 gap-6 mb-8">
          <div className="bg-white p-6 rounded-lg shadow">
            <div className="flex items-center justify-between">
              <div>
                <h3 className="text-lg font-bold text-gray-900">טלפון לשיחות</h3>
                <p className="text-gray-600 mt-1">{business.phone || 'לא הוגדר'}</p>
              </div>
              <Phone className="w-8 h-8 text-blue-500" />
            </div>
          </div>

          <div className="bg-white p-6 rounded-lg shadow">
            <div className="flex items-center justify-between">
              <div>
                <h3 className="text-lg font-bold text-gray-900">WhatsApp</h3>
                <p className="text-gray-600 mt-1">{business.whatsapp_phone || 'לא הוגדר'}</p>
              </div>
              <MessageCircle className="w-8 h-8 text-green-500" />
            </div>
          </div>

          <div className="bg-white p-6 rounded-lg shadow">
            <div className="flex items-center justify-between">
              <div>
                <h3 className="text-lg font-bold text-gray-900">AI Prompt</h3>
                <p className="text-gray-600 mt-1 text-sm">
                  {business.ai_prompt ? 
                    `${business.ai_prompt.substring(0, 50)}...` : 
                    'לא הוגדר'
                  }
                </p>
              </div>
              <Settings className="w-8 h-8 text-purple-500" />
            </div>
          </div>
        </div>

        {/* Statistics */}
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6 mb-8">
          <StatCard
            title="לידים פתוחים"
            value="12"
            icon={Users}
            trend="+8% השבוע"
            color="blue"
          />
          <StatCard
            title="שיחות היום"
            value="5"
            icon={Phone}
            trend="+2 מאתמול"
            color="green"
          />
          <StatCard
            title="WhatsApp פעיל"
            value={hasPermissions.whatsapp ? "זמין" : "כבוי"}
            icon={MessageCircle}
            trend={hasPermissions.whatsapp ? "פעיל" : "לא פעיל"}
            color={hasPermissions.whatsapp ? "green" : "orange"}
          />
          <StatCard
            title="CRM פעיל"
            value={hasPermissions.crm ? "זמין" : "כבוי"}
            icon={FileText}
            trend={hasPermissions.crm ? "פעיל" : "לא פעיל"}
            color={hasPermissions.crm ? "blue" : "orange"}
          />
        </div>

        <div className="grid grid-cols-1 lg:grid-cols-3 gap-8">
          {/* Quick Actions */}
          <div className="lg:col-span-2">
            <div className="bg-white rounded-lg shadow p-6">
              <h2 className="text-xl font-bold text-gray-900 mb-6">פעולות זמינות</h2>
              <div className="grid grid-cols-2 md:grid-cols-3 gap-4">
                <QuickActionButton
                  title="שיחות AI"
                  icon={Phone}
                  onClick={() => handleQuickAction('calls')}
                  color="blue"
                  disabled={!hasPermissions.calls}
                />
                <QuickActionButton
                  title="WhatsApp"
                  icon={MessageCircle}
                  onClick={() => handleQuickAction('whatsapp')}
                  color="green"
                  disabled={!hasPermissions.whatsapp}
                />
                <QuickActionButton
                  title="CRM"
                  icon={Users}
                  onClick={() => handleQuickAction('crm')}
                  color="purple"
                  disabled={!hasPermissions.crm}
                />
                <QuickActionButton
                  title="דוחות"
                  icon={Activity}
                  onClick={() => handleQuickAction('reports')}
                  color="orange"
                />
                <QuickActionButton
                  title="לוח שנה"
                  icon={Calendar}
                  onClick={() => handleQuickAction('calendar')}
                  color="blue"
                />
                <QuickActionButton
                  title="הגדרות"
                  icon={Settings}
                  onClick={() => handleQuickAction('settings')}
                  color="gray"
                />
              </div>
            </div>
          </div>

          {/* System Status */}
          <div>
            <div className="bg-white rounded-lg shadow p-6">
              <h2 className="text-xl font-bold text-gray-900 mb-6">סטטוס מערכות</h2>
              <div className="space-y-4">
                <div className="flex items-center justify-between">
                  <div className="flex items-center">
                    <Phone className="w-5 h-5 text-blue-500 ml-2" />
                    <span>שיחות AI</span>
                  </div>
                  {hasPermissions.calls ? (
                    <CheckCircle className="w-5 h-5 text-green-500" />
                  ) : (
                    <XCircle className="w-5 h-5 text-red-500" />
                  )}
                </div>
                
                <div className="flex items-center justify-between">
                  <div className="flex items-center">
                    <MessageCircle className="w-5 h-5 text-green-500 ml-2" />
                    <span>WhatsApp</span>
                  </div>
                  {hasPermissions.whatsapp ? (
                    <CheckCircle className="w-5 h-5 text-green-500" />
                  ) : (
                    <XCircle className="w-5 h-5 text-red-500" />
                  )}
                </div>
                
                <div className="flex items-center justify-between">
                  <div className="flex items-center">
                    <Users className="w-5 h-5 text-purple-500 ml-2" />
                    <span>CRM</span>
                  </div>
                  {hasPermissions.crm ? (
                    <CheckCircle className="w-5 h-5 text-green-500" />
                  ) : (
                    <XCircle className="w-5 h-5 text-red-500" />
                  )}
                </div>
              </div>
            </div>

            {/* Business Details */}
            <div className="bg-white rounded-lg shadow p-6 mt-6">
              <h2 className="text-xl font-bold text-gray-900 mb-4">פרטי עסק</h2>
              <div className="space-y-3 text-sm">
                <div>
                  <span className="font-medium text-gray-600">סוג עסק:</span>
                  <span className="mr-2">{business.type || 'לא צוין'}</span>
                </div>
                <div>
                  <span className="font-medium text-gray-600">תאריך הקמה:</span>
                  <span className="mr-2">
                    {business.created_at ? 
                      new Date(business.created_at).toLocaleDateString('he-IL') : 
                      'לא ידוע'
                    }
                  </span>
                </div>
                <div>
                  <span className="font-medium text-gray-600">מזהה:</span>
                  <span className="mr-2 font-mono text-gray-500">#{business.id}</span>
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};

export default BusinessViewPage;