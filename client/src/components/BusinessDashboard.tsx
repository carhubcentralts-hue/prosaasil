import { useState, useEffect } from 'react';
import { PasswordChangeModal } from './PasswordChangeModal';

interface BusinessDashboardProps {
  user: any;
  onLogout: () => void;
}

export function BusinessDashboard({ user, onLogout }: BusinessDashboardProps) {
  const [activeTab, setActiveTab] = useState('overview');
  const [showPasswordModal, setShowPasswordModal] = useState(false);
  const [realTimeData, setRealTimeData] = useState({
    activeCalls: 3,
    todayCalls: 47,
    pendingLeads: 12,
    monthlyRevenue: 125000,
    conversionRate: 24.5,
    customerSatisfaction: 4.8
  });

  // Simulate real-time updates
  useEffect(() => {
    const interval = setInterval(() => {
      setRealTimeData(prev => ({
        ...prev,
        activeCalls: Math.floor(Math.random() * 8) + 1,
        todayCalls: prev.todayCalls + Math.floor(Math.random() * 3)
      }));
    }, 10000);

    return () => clearInterval(interval);
  }, []);

  const StatCard = ({ icon, title, value, subtitle, trend, color = "blue" }: any) => (
    <div className="bg-white rounded-2xl p-6 shadow-sm border border-slate-200 hover:shadow-md transition-all duration-300">
      <div className="flex items-center justify-between">
        <div className={`p-3 rounded-xl bg-${color}-50 text-2xl`}>
          {icon}
        </div>
        {trend && (
          <div className={`text-sm font-medium ${trend > 0 ? 'text-green-600' : 'text-red-600'}`}>
            {trend > 0 ? '+' : ''}{trend}%
          </div>
        )}
      </div>
      <div className="mt-4">
        <h3 className="text-2xl font-bold text-slate-900">{value}</h3>
        <p className="text-sm text-slate-600 mt-1">{title}</p>
        {subtitle && <p className="text-xs text-slate-500 mt-1">{subtitle}</p>}
      </div>
    </div>
  );

  return (
    <div className="min-h-screen bg-slate-50">
      {/* Professional Header */}
      <header className="bg-white border-b border-slate-200 sticky top-0 z-40">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="flex justify-between items-center h-16">
            <div className="flex items-center">
              <div className="w-8 h-8 bg-gradient-to-br from-blue-500 to-blue-700 rounded-lg flex items-center justify-center text-white text-lg">
                🏢
              </div>
              <div className="mr-3">
                <h1 className="text-lg font-semibold text-slate-900">לוח בקרה עסקי</h1>
                <p className="text-sm text-slate-600">מערכת CRM</p>
              </div>
            </div>
            
            <div className="flex items-center space-x-4">
              <button
                onClick={() => setShowPasswordModal(true)}
                className="bg-blue-50 hover:bg-blue-100 text-blue-700 px-4 py-2 rounded-lg text-sm font-medium transition-colors flex items-center"
              >
                <span className="ml-2">⚙️</span>
                שינוי סיסמה
              </button>
              <div className="text-right">
                <p className="text-sm font-medium text-slate-900">{user.firstName} {user.lastName}</p>
                <p className="text-xs text-slate-600">משתמש עסק</p>
              </div>
              <button
                onClick={onLogout}
                className="bg-slate-100 hover:bg-slate-200 text-slate-700 px-4 py-2 rounded-lg text-sm font-medium transition-colors"
              >
                יציאה
              </button>
            </div>
          </div>
        </div>
      </header>

      {/* Navigation Tabs */}
      <div className="bg-white border-b border-slate-200">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <nav className="flex space-x-8" dir="rtl">
            {[
              { id: 'overview', label: 'סקירה כללית', icon: '📊' },
              { id: 'calls', label: 'שיחות', icon: '📞' },
              { id: 'customers', label: 'לקוחות', icon: '👥' },
              { id: 'analytics', label: 'אנליטיקס', icon: '📈' }
            ].map(tab => (
              <button
                key={tab.id}
                onClick={() => setActiveTab(tab.id)}
                className={`flex items-center px-3 py-4 text-sm font-medium border-b-2 transition-colors ${
                  activeTab === tab.id
                    ? 'border-blue-500 text-blue-600'
                    : 'border-transparent text-slate-600 hover:text-slate-900 hover:border-slate-300'
                }`}
              >
                <span className="ml-2">{tab.icon}</span>
                {tab.label}
              </button>
            ))}
          </nav>
        </div>
      </div>

      {/* Main Content */}
      <main className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
        {activeTab === 'overview' && (
          <div className="space-y-8">
            {/* Key Metrics */}
            <div>
              <h2 className="text-2xl font-bold text-slate-900 mb-6">מטריקות עיקריות</h2>
              <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
                <StatCard
                  icon="📞"
                  title="שיחות פעילות"
                  value={realTimeData.activeCalls}
                  subtitle="עכשיו בזמן אמת"
                  color="green"
                />
                <StatCard
                  icon="📅"
                  title="שיחות היום"
                  value={realTimeData.todayCalls}
                  trend={12}
                  subtitle="לעומת אתמול"
                  color="blue"
                />
                <StatCard
                  icon="👥"
                  title="לידים ממתינים"
                  value={realTimeData.pendingLeads}
                  subtitle="דורש מעקב"
                  color="orange"
                />
                <StatCard
                  icon="💰"
                  title="הכנסות החודש"
                  value={`₪${realTimeData.monthlyRevenue.toLocaleString()}`}
                  trend={18}
                  subtitle="עד כה החודש"
                  color="emerald"
                />
                <StatCard
                  icon="📈"
                  title="שיעור המרה"
                  value={`${realTimeData.conversionRate}%`}
                  trend={3.2}
                  subtitle="שיפור לעומת חודש קודם"
                  color="purple"
                />
                <StatCard
                  icon="⭐"
                  title="שביעות רצון"
                  value={realTimeData.customerSatisfaction}
                  subtitle="דירוג ממוצע (5.0)"
                  color="yellow"
                />
              </div>
            </div>

            {/* Recent Activity */}
            <div className="bg-white rounded-2xl p-6 shadow-sm border border-slate-200">
              <h3 className="text-lg font-semibold text-slate-900 mb-4">פעילות אחרונה</h3>
              <div className="space-y-4">
                {[
                  { time: '10:23', action: 'שיחה חדשה התקבלה', details: 'לקוח מעוניין בדירת 3 חדרים' },
                  { time: '10:15', action: 'לקוח חדש נוסף למערכת', details: 'יוסי כהן - 052-1234567' },
                  { time: '09:45', action: 'פגישה נקבעה', details: 'מחר 14:00 - צפיית דירה' },
                  { time: '09:30', action: 'עסקה נסגרה', details: 'דירת 4 חדרים בתל אביב - ₪1,850,000' }
                ].map((activity, index) => (
                  <div key={index} className="flex items-start space-x-3" dir="rtl">
                    <div className="flex-shrink-0">
                      <div className="w-2 h-2 bg-blue-500 rounded-full mt-2"></div>
                    </div>
                    <div className="flex-1">
                      <div className="flex items-center justify-between">
                        <p className="text-sm font-medium text-slate-900">{activity.action}</p>
                        <span className="text-xs text-slate-500">{activity.time}</span>
                      </div>
                      <p className="text-sm text-slate-600 mt-1">{activity.details}</p>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          </div>
        )}

        {activeTab === 'calls' && (
          <div className="space-y-6">
            <h2 className="text-2xl font-bold text-slate-900">ניהול שיחות</h2>
            <div className="bg-white rounded-2xl p-6 shadow-sm border border-slate-200">
              <p className="text-slate-600">מערכת ניהול שיחות מתקדמת בפיתוח...</p>
            </div>
          </div>
        )}

        {activeTab === 'customers' && (
          <div className="space-y-6">
            <h2 className="text-2xl font-bold text-slate-900">ניהול לקוחות</h2>
            <div className="bg-white rounded-2xl p-6 shadow-sm border border-slate-200">
              <p className="text-slate-600">מערכת CRM מתקדמת בפיתוח...</p>
            </div>
          </div>
        )}

        {activeTab === 'analytics' && (
          <div className="space-y-6">
            <h2 className="text-2xl font-bold text-slate-900">אנליטיקס ודוחות</h2>
            <div className="bg-white rounded-2xl p-6 shadow-sm border border-slate-200">
              <p className="text-slate-600">מערכת אנליטיקס מתקדמת בפיתוח...</p>
            </div>
          </div>
        )}
      </main>
      
      {/* Password Change Modal */}
      <PasswordChangeModal
        isOpen={showPasswordModal}
        onClose={() => setShowPasswordModal(false)}
        onSuccess={() => {
          // Show success message or handle success
          console.log('Password changed successfully');
        }}
      />
    </div>
  );
}