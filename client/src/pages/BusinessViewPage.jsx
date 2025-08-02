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
  
  // קבלת מזהה העסק מה-URL
  const getBusinessIdFromUrl = () => {
    const path = window.location.pathname;
    const matches = path.match(/\/business\/(\d+)\/dashboard/);
    return matches ? parseInt(matches[1]) : null;
  };

  useEffect(() => {
    const fetchBusinessData = async () => {
      try {
        const businessId = getBusinessIdFromUrl();
        if (!businessId) {
          setError('מזהה עסק לא תקין');
          return;
        }

        console.log('Fetching business data for ID:', businessId);
        const response = await axios.get(`/api/admin/businesses/${businessId}`);
        console.log('Business data received:', response.data);
        setBusiness(response.data);
      } catch (error) {
        console.error('Error fetching business data:', error);
        setError('שגיאה בטעינת נתוני העסק');
      } finally {
        setLoading(false);
      }
    };

    fetchBusinessData();
  }, []);

  const handleGoBack = () => {
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
          <p className="text-gray-600 font-hebrew mb-4">{error || 'עסק לא נמצא'}</p>
          <button
            onClick={handleGoBack}
            className="bg-blue-600 text-white px-4 py-2 rounded-lg hover:bg-blue-700"
          >
            חזרה לפאנל מנהל
          </button>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-gray-50" dir="rtl">
      {/* Header */}
      <div className="bg-white shadow-sm border-b">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="flex items-center justify-between h-16">
            <div className="flex items-center space-x-4 space-x-reverse">
              <button
                onClick={handleGoBack}
                className="flex items-center space-x-2 space-x-reverse text-gray-600 hover:text-gray-900 transition-colors"
              >
                <ArrowLeft className="w-5 h-5" />
                <span>חזרה לפאנל מנהל</span>
              </button>
              <div className="w-px h-6 bg-gray-300"></div>
              <div className="flex items-center space-x-3 space-x-reverse">
                <Building2 className="w-6 h-6 text-blue-600" />
                <h1 className="text-xl font-bold text-gray-900">{business.name}</h1>
              </div>
            </div>
            <div className="flex items-center space-x-2 space-x-reverse">
              <span className="text-sm text-gray-500">ID: {business.id}</span>
              <span className="text-sm text-gray-500">•</span>
              <span className="text-sm text-gray-500">{business.type}</span>
            </div>
          </div>
        </div>
      </div>

      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-6">
        {/* Business Info Card */}
        <div className="bg-white rounded-lg shadow mb-6">
          <div className="p-6 border-b">
            <h2 className="text-lg font-bold text-gray-900 mb-4">פרטי העסק</h2>
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">
                  שם העסק
                </label>
                <p className="text-gray-900 font-medium">{business.name}</p>
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">
                  סוג העסק
                </label>
                <p className="text-gray-900">{business.type}</p>
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">
                  טלפון שיחות (ישראלי)
                </label>
                <p className="text-gray-900 font-mono">{business.phone}</p>
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">
                  טלפון WhatsApp (אמריקאי)
                </label>
                <p className="text-gray-900 font-mono">{business.whatsapp_phone}</p>
              </div>
            </div>
          </div>
          
          <div className="p-6">
            <label className="block text-sm font-medium text-gray-700 mb-2">
              הוראות AI (Prompt)
            </label>
            <div className="bg-gray-50 rounded-lg p-4 text-sm text-gray-700 leading-relaxed whitespace-pre-line">
              {business.ai_prompt}
            </div>
          </div>
        </div>

        {/* Services Status */}
        <div className="bg-white rounded-lg shadow mb-6">
          <div className="p-6 border-b">
            <h2 className="text-lg font-bold text-gray-900">סטטוס מערכות</h2>
          </div>
          <div className="p-6">
            <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
              <div className="flex items-center space-x-3 space-x-reverse p-4 rounded-lg border-2 border-blue-200 bg-blue-50">
                <Phone className="w-6 h-6 text-blue-600" />
                <div>
                  <p className="font-medium text-blue-900">שיחות AI</p>
                  <div className="flex items-center space-x-2 space-x-reverse mt-1">
                    {business.services?.calls ? (
                      <>
                        <CheckCircle className="w-4 h-4 text-green-600" />
                        <span className="text-sm text-green-700 font-medium">פעיל</span>
                      </>
                    ) : (
                      <>
                        <XCircle className="w-4 h-4 text-red-600" />
                        <span className="text-sm text-red-700 font-medium">כבוי</span>
                      </>
                    )}
                  </div>
                </div>
              </div>

              <div className="flex items-center space-x-3 space-x-reverse p-4 rounded-lg border-2 border-green-200 bg-green-50">
                <MessageCircle className="w-6 h-6 text-green-600" />
                <div>
                  <p className="font-medium text-green-900">WhatsApp</p>
                  <div className="flex items-center space-x-2 space-x-reverse mt-1">
                    {business.services?.whatsapp ? (
                      <>
                        <CheckCircle className="w-4 h-4 text-green-600" />
                        <span className="text-sm text-green-700 font-medium">פעיל</span>
                      </>
                    ) : (
                      <>
                        <XCircle className="w-4 h-4 text-red-600" />
                        <span className="text-sm text-red-700 font-medium">כבוי</span>
                      </>
                    )}
                  </div>
                </div>
              </div>

              <div className="flex items-center space-x-3 space-x-reverse p-4 rounded-lg border-2 border-purple-200 bg-purple-50">
                <Users className="w-6 h-6 text-purple-600" />
                <div>
                  <p className="font-medium text-purple-900">CRM מתקדם</p>
                  <div className="flex items-center space-x-2 space-x-reverse mt-1">
                    {business.services?.crm ? (
                      <>
                        <CheckCircle className="w-4 h-4 text-green-600" />
                        <span className="text-sm text-green-700 font-medium">פעיל</span>
                      </>
                    ) : (
                      <>
                        <XCircle className="w-4 h-4 text-red-600" />
                        <span className="text-sm text-red-700 font-medium">כבוי</span>
                      </>
                    )}
                  </div>
                </div>
              </div>
            </div>
          </div>
        </div>

        {/* Statistics */}
        <div className="bg-white rounded-lg shadow mb-6">
          <div className="p-6 border-b">
            <h2 className="text-lg font-bold text-gray-900">סטטיסטיקות העסק</h2>
          </div>
          <div className="p-6">
            <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
              <StatCard
                title="שיחות החודש"
                value="47"
                icon={Phone}
                trend="+12% מהחודש הקודם"
                color="blue"
              />
              <StatCard
                title="הודעות WhatsApp"
                value="168"
                icon={MessageCircle}
                trend="+8% מהחודש הקודם"
                color="green"
              />
              <StatCard
                title="לקוחות פעילים"
                value="23"
                icon={Users}
                trend="+5 לקוחות חדשים"
                color="purple"
              />
              <StatCard
                title="המרה לפגישות"
                value="34%"
                icon={Calendar}
                trend="+3% שיפור"
                color="orange"
              />
            </div>
          </div>
        </div>

        {/* Quick Actions */}
        <div className="bg-white rounded-lg shadow">
          <div className="p-6 border-b">
            <h2 className="text-lg font-bold text-gray-900">פעולות מהירות</h2>
          </div>
          <div className="p-6">
            <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
              <QuickActionButton
                title="ניהול שיחות"
                icon={Phone}
                onClick={() => alert('מעבר לניהול שיחות')}
                color="primary"
                disabled={!business.services?.calls}
              />
              <QuickActionButton
                title="צ'אט WhatsApp"
                icon={MessageCircle}
                onClick={() => alert('מעבר לצ\'אט WhatsApp')}
                color="green"
                disabled={!business.services?.whatsapp}
              />
              <QuickActionButton
                title="ניהול לקוחות"
                icon={Users}
                onClick={() => alert('מעבר לניהול לקוחות')}
                color="purple"
                disabled={!business.services?.crm}
              />
              <QuickActionButton
                title="דוחות ואנליטיקה"
                icon={Activity}
                onClick={() => alert('מעבר לדוחות')}
                color="orange"
              />
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};

export default BusinessViewPage;