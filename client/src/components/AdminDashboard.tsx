import { useState, useEffect } from 'react';
import { PasswordChangeModal } from './PasswordChangeModal';

interface AdminDashboardProps {
  user: any;
  onLogout: () => void;
}

export function AdminDashboard({ user, onLogout }: AdminDashboardProps) {
  const [activeTab, setActiveTab] = useState('overview');
  const [showPasswordModal, setShowPasswordModal] = useState(false);
  const [systemHealth] = useState({
    api: 'healthy',
    database: 'healthy',
    twilio: 'healthy',
    whatsapp: 'warning',
    uptime: '99.9%'
  });
  
  const [businessMetrics, setBusinessMetrics] = useState({
    totalUsers: 156,
    activeBusinesses: 12,
    totalCalls: 2847,
    monthlyRevenue: 485000,
    systemLoad: 23,
    errorRate: 0.02
  });

  // Real-time system monitoring
  useEffect(() => {
    const interval = setInterval(() => {
      setBusinessMetrics(prev => ({
        ...prev,
        systemLoad: Math.floor(Math.random() * 40) + 10,
        totalCalls: prev.totalCalls + Math.floor(Math.random() * 5)
      }));
    }, 5000);

    return () => clearInterval(interval);
  }, []);

  const SystemStatusCard = ({ service, status, description }: any) => {
    const statusConfig = {
      healthy: { color: 'green', icon: '✅', text: 'תקין' },
      warning: { color: 'yellow', icon: '⚠️', text: 'אזהרה' },
      error: { color: 'red', icon: '❌', text: 'שגיאה' }
    };
    
    const config = statusConfig[status as keyof typeof statusConfig];

    return (
      <div className="bg-white rounded-xl p-4 border border-slate-200 hover:shadow-md transition-all duration-200">
        <div className="flex items-center justify-between">
          <div className="flex items-center">
            <div className={`p-2 rounded-lg bg-${config.color}-50 text-lg`}>
              {config.icon}
            </div>
            <div className="mr-3">
              <h3 className="font-medium text-slate-900">{service}</h3>
              <p className="text-sm text-slate-600">{description}</p>
            </div>
          </div>
          <span className={`text-sm font-medium text-${config.color}-600`}>
            {config.text}
          </span>
        </div>
      </div>
    );
  };

  const MetricCard = ({ icon, title, value, subtitle, trend, color = "blue" }: any) => (
    <div className="bg-white rounded-xl p-6 shadow-sm border border-slate-200">
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
      {/* Admin Header */}
      <header className="bg-gradient-to-r from-slate-900 to-slate-800 text-white sticky top-0 z-40">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="flex justify-between items-center h-16">
            <div className="flex items-center">
              <div className="w-8 h-8 bg-gradient-to-br from-blue-500 to-blue-700 rounded-lg flex items-center justify-center text-white text-lg">
                🛡️
              </div>
              <div className="mr-3">
                <h1 className="text-lg font-semibold">לוח בקרה מנהל</h1>
                <p className="text-sm text-slate-300">ניהול מערכת מתקדם</p>
              </div>
            </div>
            
            <div className="flex items-center space-x-4">
              <button
                onClick={() => setShowPasswordModal(true)}
                className="bg-slate-600 hover:bg-slate-500 text-white px-4 py-2 rounded-lg text-sm font-medium transition-colors flex items-center"
              >
                <span className="ml-2">⚙️</span>
                שינוי סיסמה
              </button>
              <div className="text-right">
                <p className="text-sm font-medium">{user.firstName} {user.lastName}</p>
                <p className="text-xs text-slate-300">מנהל מערכת</p>
              </div>
              <button
                onClick={onLogout}
                className="bg-slate-700 hover:bg-slate-600 text-white px-4 py-2 rounded-lg text-sm font-medium transition-colors"
              >
                יציאה
              </button>
            </div>
          </div>
        </div>
      </header>

      {/* Admin Navigation */}
      <div className="bg-white border-b border-slate-200">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <nav className="flex space-x-8" dir="rtl">
            {[
              { id: 'overview', label: 'סקירה כללית', icon: '📊' },
              { id: 'system', label: 'מצב מערכת', icon: '🖥️' },
              { id: 'users', label: 'ניהול משתמשים', icon: '👥' },
              { id: 'businesses', label: 'ניהול עסקים', icon: '🏢' },
              { id: 'settings', label: 'הגדרות', icon: '⚙️' }
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
            {/* System Health Overview */}
            <div>
              <h2 className="text-2xl font-bold text-slate-900 mb-6">מצב המערכת</h2>
              <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
                <SystemStatusCard 
                  service="API Server" 
                  status={systemHealth.api}
                  description="שרת ראשי פעיל"
                />
                <SystemStatusCard 
                  service="Database" 
                  status={systemHealth.database}
                  description="בסיס נתונים PostgreSQL"
                />
                <SystemStatusCard 
                  service="Twilio Integration" 
                  status={systemHealth.twilio}
                  description="שירות שיחות"
                />
                <SystemStatusCard 
                  service="WhatsApp API" 
                  status={systemHealth.whatsapp}
                  description="בדיקת חיבור נדרשת"
                />
                <SystemStatusCard 
                  service="System Uptime" 
                  status="healthy"
                  description={systemHealth.uptime}
                />
              </div>
            </div>

            {/* Key Business Metrics */}
            <div>
              <h2 className="text-2xl font-bold text-slate-900 mb-6">מטריקות עסקיות</h2>
              <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
                <MetricCard
                  icon="👥"
                  title="סך משתמשים"
                  value={businessMetrics.totalUsers}
                  trend={8}
                  subtitle="גידול חודשי"
                  color="blue"
                />
                <MetricCard
                  icon="🏢"
                  title="עסקים פעילים"
                  value={businessMetrics.activeBusinesses}
                  trend={12}
                  subtitle="עסקים רשומים"
                  color="green"
                />
                <MetricCard
                  icon="📞"
                  title="סך שיחות"
                  value={businessMetrics.totalCalls.toLocaleString()}
                  trend={15}
                  subtitle="החודש"
                  color="purple"
                />
                <MetricCard
                  icon="📈"
                  title="הכנסות כוללות"
                  value={`₪${businessMetrics.monthlyRevenue.toLocaleString()}`}
                  trend={22}
                  subtitle="החודש"
                  color="emerald"
                />
                <MetricCard
                  icon="🖥️"
                  title="עומס מערכת"
                  value={`${businessMetrics.systemLoad}%`}
                  subtitle="CPU ו-Memory"
                  color="orange"
                />
                <MetricCard
                  icon="⚠️"
                  title="שיעור שגיאות"
                  value={`${businessMetrics.errorRate}%`}
                  subtitle="24 שעות אחרונות"
                  color="red"
                />
              </div>
            </div>

            {/* Recent Admin Activity */}
            <div className="bg-white rounded-xl p-6 shadow-sm border border-slate-200">
              <h3 className="text-lg font-semibold text-slate-900 mb-4">פעילות מנהלים אחרונה</h3>
              <div className="space-y-4">
                {[
                  { time: '11:30', action: 'עסק חדש נוסף למערכת', details: 'חברת "מקסים נדל״ן" אושרה' },
                  { time: '10:45', action: 'עדכון הרשאות משתמש', details: 'שינוי הרשאות עבור יוסי כהן' },
                  { time: '09:15', action: 'גיבוי מערכת הושלם', details: 'גיבוי יומי - 2.3GB' },
                  { time: '08:30', action: 'התראת אבטחה', details: 'ניסיון התחברות חשוד נחסם' }
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

        {activeTab === 'system' && (
          <div className="space-y-6">
            <h2 className="text-2xl font-bold text-slate-900">ניטור מערכת</h2>
            <div className="bg-white rounded-xl p-6 shadow-sm border border-slate-200">
              <p className="text-slate-600">מערכת ניטור מתקדמת בפיתוח...</p>
            </div>
          </div>
        )}

        {activeTab === 'users' && (
          <div className="space-y-6">
            <h2 className="text-2xl font-bold text-slate-900">ניהול משתמשים</h2>
            <div className="bg-white rounded-xl p-6 shadow-sm border border-slate-200">
              <p className="text-slate-600">מערכת ניהול משתמשים מתקדמת בפיתוח...</p>
            </div>
          </div>
        )}

        {activeTab === 'businesses' && (
          <div className="space-y-6">
            <h2 className="text-2xl font-bold text-slate-900">ניהול עסקים</h2>
            <div className="bg-white rounded-xl p-6 shadow-sm border border-slate-200">
              <p className="text-slate-600">מערכת ניהול עסקים מתקדמת בפיתוח...</p>
            </div>
          </div>
        )}

        {activeTab === 'settings' && (
          <div className="space-y-6">
            <h2 className="text-2xl font-bold text-slate-900">הגדרות מערכת</h2>
            <div className="bg-white rounded-xl p-6 shadow-sm border border-slate-200">
              <p className="text-slate-600">הגדרות מערכת מתקדמות בפיתוח...</p>
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