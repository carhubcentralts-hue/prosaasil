import React from 'react';
import { Users, MessageCircle, Phone, Building2, Calendar, TrendingUp, Activity, CheckCircle, Clock } from 'lucide-react';

// Sample data for demo
const sampleStats = {
  calls: { today: 24, avgHandleSec: 185, total: 1247 },
  whatsapp: { today: 18, unread: 3, total: 892 },
  leads: { today: 12, converted: 4, total: 356 },
  businesses: { active: 8, total: 12 }
};

const sampleActivity = [
  { time: '14:32', action: 'שיחה חדשה מ-054-123-4567', status: 'completed' },
  { time: '14:18', action: 'WhatsApp מלאה בן דוד - מעוניין בדירה', status: 'pending' },
  { time: '13:45', action: 'ליד חדש נוסף למערכת', status: 'success' },
  { time: '13:22', action: 'פגישה נקבעה - יום ראשון 16:00', status: 'scheduled' },
  { time: '12:58', action: 'שיחה הושלמה - 3 דקות', status: 'completed' }
];

export function AdminHomePage() {

  return (
    <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-6" dir="rtl">
      {/* Page Header */}
      <div className="mb-6">
        <h1 className="text-2xl md:text-3xl font-bold text-gray-900">
          לוח בקרה מנהל 👋
        </h1>
        <p className="text-gray-600 mt-2">
          היום: {new Date().toLocaleDateString('he-IL', { weekday: 'long', year: 'numeric', month: 'long', day: 'numeric' })}
        </p>
      </div>

      {/* Quick Status */}
      <div className="mb-6">
        <div className="bg-gradient-to-l from-blue-600 to-blue-700 rounded-2xl p-6 text-white">
          <div className="flex items-center justify-between">
            <div>
              <h3 className="text-lg font-semibold mb-2">סטטוס מערכת</h3>
              <div className="flex items-center space-x-reverse space-x-4">
                <div className="flex items-center">
                  <CheckCircle className="h-5 w-5 text-green-300 ml-2" />
                  <span className="text-sm">Twilio מחובר</span>
                </div>
                <div className="flex items-center">
                  <CheckCircle className="h-5 w-5 text-green-300 ml-2" />
                  <span className="text-sm">WhatsApp פעיל</span>
                </div>
              </div>
            </div>
            <Activity className="h-12 w-12 text-blue-200" />
          </div>
        </div>
      </div>

      {/* KPI Cards */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4 mb-6">
        <div className="bg-white rounded-2xl p-4 shadow-sm border border-gray-100">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-gray-600 text-sm">שיחות היום</p>
              <p className="text-2xl font-bold text-gray-900">{sampleStats.calls.today}</p>
              <p className="text-xs text-green-600 flex items-center">
                <TrendingUp className="h-3 w-3 ml-1" />
                +15% מאתמול
              </p>
            </div>
            <Phone className="h-8 w-8 text-blue-600" />
          </div>
        </div>
        
        <div className="bg-white rounded-2xl p-4 shadow-sm border border-gray-100">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-gray-600 text-sm">WhatsApp</p>
              <p className="text-2xl font-bold text-gray-900">{sampleStats.whatsapp.today}</p>
              <p className="text-xs text-orange-600">{sampleStats.whatsapp.unread} לא נקראו</p>
            </div>
            <MessageCircle className="h-8 w-8 text-green-600" />
          </div>
        </div>
        
        <div className="bg-white rounded-2xl p-4 shadow-sm border border-gray-100">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-gray-600 text-sm">לידים חדשים</p>
              <p className="text-2xl font-bold text-gray-900">{sampleStats.leads.today}</p>
              <p className="text-xs text-blue-600">{sampleStats.leads.converted} הומרו</p>
            </div>
            <Users className="h-8 w-8 text-purple-600" />
          </div>
        </div>
        
        <div className="bg-white rounded-2xl p-4 shadow-sm border border-gray-100">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-gray-600 text-sm">עסקים פעילים</p>
              <p className="text-2xl font-bold text-gray-900">{sampleStats.businesses.active}</p>
              <p className="text-xs text-gray-600">מתוך {sampleStats.businesses.total}</p>
            </div>
            <Building2 className="h-8 w-8 text-indigo-600" />
          </div>
        </div>
      </div>

      {/* Performance Overview */}
      <div className="mb-6">
        <div className="bg-white rounded-2xl border border-gray-100 shadow-sm p-6">
          <h3 className="text-lg font-semibold text-gray-900 mb-4">
            סיכום שבועי
          </h3>
          <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
            <div className="text-center p-4 bg-blue-50 rounded-xl">
              <div className="text-2xl font-bold text-blue-700 mb-1">156</div>
              <div className="text-sm text-blue-600">שיחות שבוע זה</div>
              <div className="text-xs text-green-600 mt-1">+12% משבוע שעבר</div>
            </div>
            <div className="text-center p-4 bg-green-50 rounded-xl">
              <div className="text-2xl font-bold text-green-700 mb-1">89</div>
              <div className="text-sm text-green-600">לידים חדשים</div>
              <div className="text-xs text-green-600 mt-1">+8% משבוע שעבר</div>
            </div>
            <div className="text-center p-4 bg-purple-50 rounded-xl">
              <div className="text-2xl font-bold text-purple-700 mb-1">23</div>
              <div className="text-sm text-purple-600">פגישות נקבעו</div>
              <div className="text-xs text-green-600 mt-1">+5% משבוע שעבר</div>
            </div>
          </div>
        </div>
      </div>

      {/* Recent Activity */}
      <div className="bg-white rounded-2xl border border-gray-100 shadow-sm p-6">
        <div className="flex items-center justify-between mb-4">
          <h3 className="text-lg font-semibold text-gray-900">
            פעילות אחרונה
          </h3>
          <Clock className="h-5 w-5 text-gray-400" />
        </div>
        <div className="space-y-3">
          {sampleActivity.map((item, index) => (
            <div key={index} className="flex items-center p-3 bg-gray-50 rounded-xl">
              <div className={`w-3 h-3 rounded-full ml-3 ${
                item.status === 'completed' ? 'bg-green-500' :
                item.status === 'pending' ? 'bg-yellow-500' :
                item.status === 'success' ? 'bg-blue-500' :
                'bg-purple-500'
              }`} />
              <div className="flex-1">
                <div className="text-sm font-medium text-gray-900">{item.action}</div>
                <div className="text-xs text-gray-500">{item.time}</div>
              </div>
            </div>
          ))}
        </div>
        <div className="mt-4 text-center">
          <button className="text-sm text-blue-600 hover:text-blue-800 font-medium">
            ראה עוד פעילות
          </button>
        </div>
      </div>
    </div>
  );
}